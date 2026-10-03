"""Chaotic Attack burritos as figures that stand on brick plates.

The parts come from ``tools/burrito-export`` (``buildBurrito()`` run headlessly):
world-space triangles and a representative colour for every visible mesh. Here
each part becomes a solid. Closed meshes are used as they are; open one-sided ones
(a tube, a half torus: the outside of a solid) get their ends capped; double-sided
ones, three.js's sheets (a cape, a lens), are thickened to the profile's minimum wall, and any part thinner than that is
fattened across its thin direction. The parts are fused into one figure (anything
floating is bridged), set into a base whose underside fits the stud grid, and split
into colour groups no larger in number than the printer's filament slots, so the
3MF prints in colour.
"""
from __future__ import annotations

import gzip
import json
import math
import os
from dataclasses import dataclass, field

import numpy as np
from manifold3d import Manifold, Mesh, OpType

from ..bricks import brick
from ..colour import merge
from ..geom import box, fuse
from ..profiles import FDM_04, Profile

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "burritos")
TO_Z_UP = np.array([[-1.0, 0, 0], [0, 0, 1], [0, 1, 0]])  # three.js y-up facing -z, to z-up facing -y
MM_PER_UNIT = 22.0
SLIVER = 0.01  # mm^3: colour regions this small are left over from booleans, not features  # a full-size burrito (2.4 units with its filling) stands about 53 mm


def load(kind: str, hero: bool = True) -> dict:
    """An exported burrito: a bundled kind (``madison``) or a path to an exporter .json.gz."""
    path = kind if os.path.exists(kind) else os.path.join(DATA, f"{kind}{'-hero' if hero else ''}.json.gz")
    with gzip.open(path) as f:
        return json.load(f)


def _weld(v: np.ndarray):
    """Triangle soup to shared vertices, dropping triangles that collapse."""
    verts, inv = np.unique(np.round(v, 4), axis=0, return_inverse=True)
    tri = inv.reshape(-1, 3)
    keep = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
    return verts, tri[keep]


def _solid(verts, tri) -> Manifold:
    m = Manifold(Mesh(vert_properties=np.asarray(verts, np.float32), tri_verts=np.asarray(tri, np.uint32)))
    return m if not m.is_empty() and m.volume() > 0 else Manifold()


def _boundary(tri) -> dict:
    """Directed boundary edges a -> b (edges no other triangle shares), as {a: b}."""
    edges = {(int(a), int(b)) for t in tri for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0]))}
    return {a: b for a, b in edges if (b, a) not in edges}


def cap(verts, tri):
    """Close every boundary loop with a fan round its centre (the ends of a tube, a half torus)."""
    nxt, verts, extra = _boundary(tri), list(map(tuple, verts)), []
    while nxt:
        start = next(iter(nxt))
        loop, a = [], start
        while a in nxt:
            loop.append(a)
            a = nxt.pop(a)
        verts.append(tuple(np.mean([verts[i] for i in loop], axis=0)))
        c = len(verts) - 1
        extra += [(loop[(i + 1) % len(loop)], loop[i], c) for i in range(len(loop))]
    return np.array(verts), np.vstack([tri, extra]) if extra else tri


def shell(verts, tri, thickness: float) -> Manifold:
    """A sheet made solid: offset both ways along the vertex normals, with walls round its edges."""
    n = np.zeros_like(verts)
    fn = np.cross(verts[tri[:, 1]] - verts[tri[:, 0]], verts[tri[:, 2]] - verts[tri[:, 0]])
    for k in range(3):
        np.add.at(n, tri[:, k], fn)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    k = len(verts)
    top, bottom = verts + n * thickness / 2, verts - n * thickness / 2
    faces = [tri, tri[:, ::-1] + k]
    for a, b in _boundary(tri).items():
        faces.append(np.array([[b, a, a + k], [b, a + k, b + k]]))
    return _solid(np.vstack([top, bottom]), np.vstack(faces))


def fatten(m: Manifold, min_wall: float) -> tuple[Manifold, bool]:
    """Stretch a part across any direction it is thinner than min_wall (its principal axes)."""
    v = m.to_mesh().vert_properties[:, :3].astype(float)
    c = v.mean(0)
    _, axes = np.linalg.eigh(np.cov((v - c).T))
    ext = np.ptp((v - c) @ axes, axis=0)
    s = np.where(ext < min_wall, min_wall / np.maximum(ext, 1e-6), 1.0)
    if np.all(s == 1.0):
        return m, False
    A = axes @ np.diag(s) @ axes.T
    return m.transform(np.hstack([A, (c - A @ c).reshape(3, 1)])), True


def part_solid(part: dict, mm: float, min_wall: float) -> tuple[Manifold, str]:
    """(solid in mm, how it was made: closed, capped or thickened; '+fattened' if it was too thin)."""
    v = np.asarray(part["triangles"], float).reshape(-1, 3) @ TO_Z_UP.T * mm
    verts, tri = _weld(v)
    how, m = "closed", _solid(verts, tri)
    if m.is_empty() and not part.get("double_sided"):  # one-sided and open: the outside of a solid
        m, how = _solid(*cap(verts, tri)), "capped"
    if m.is_empty():  # double-sided (three.js's sign of a sheet: a cape, a lens) or uncappable
        m, how = shell(verts, tri, min_wall), "thickened"
    m, fat = fatten(m, min_wall)
    return m, how + ("+fattened" if fat else "")


@dataclass
class Figure:
    name: str
    solid: Manifold  # the whole figure, base included, one piece
    colours: list  # (name, Manifold, "#rrggbb"): a partition of `solid` for a multi-colour print
    info: dict = field(default_factory=dict)


def socket_base(footprint, profile: Profile, depth: float) -> tuple[Manifold, tuple]:
    """A plate-sized base with a flat top `depth` mm thicker than a plate, its underside the stud grid's
    (hollow with tubes), big enough for `footprint` (dx, dy) mm. Top at z = 0, centred."""
    p = profile
    w, l = (max(2, math.ceil((d + 2.0 + 2 * p.side_gap) / p.pitch)) for d in footprint)
    plate = brick(w, l, plates=1, profile=p, studs=False)
    ox, oy = w * p.pitch - 2 * p.side_gap, l * p.pitch - 2 * p.side_gap
    slab = box([ox, oy, depth], center=False).translate([-ox / 2, -oy / 2, p.plate_height - 0.01])
    return (plate + slab).translate([0, 0, -(p.plate_height + depth)]), (w, l)


def figure(data: dict, profile: Profile = FDM_04, mm: float = MM_PER_UNIT, slots: int = 4, base: bool = True) -> Figure:
    """The burrito as one printable figure on a stud-grid base, with at most `slots` colours."""
    w = profile.min_wall
    parts = [(p["name"], *part_solid(p, mm, w), p["colour"]) for p in data["parts"]]
    solids = [s for _, s, _, _ in parts]
    body = fuse(solids, bridge_radius=w)
    lo, hi = np.array(body.bounding_box()).reshape(2, 3)
    biggest = max(range(len(parts)), key=lambda i: solids[i].volume())
    sink = float(np.array(solids[biggest].bounding_box())[2] - lo[2]) + 0.6  # the wrap, not just the toes, sits in
    pieces, base_colour, studs, base_xy = [], None, None, None
    if base:
        v = body.to_mesh().vert_properties[:, :3]
        wrap = np.array(solids[biggest].bounding_box()).reshape(2, 3)
        low = np.vstack([v[v[:, 2] < lo[2] + sink], wrap])  # the feet and the wrap above them
        foot_lo, foot_hi = low[:, :2].min(0), low[:, :2].max(0)
        plinth, studs = socket_base(foot_hi - foot_lo, profile, sink + 0.6)
        centre = [(foot_lo[0] + foot_hi[0]) / 2, (foot_lo[1] + foot_hi[1]) / 2, lo[2] + sink]
        plinth = plinth.translate(centre)
        base_xy = [round(float(x), 3) for x in centre[:2]]
        body = body + plinth
        base_colour = parts[int(np.argmin([np.array(s.bounding_box())[2] for s in solids]))][3]  # the feet's
        pieces.append(("base", plinth, base_colour))
    weights = {}  # how much each colour shows; square-rooted so a pupil still counts against a wrap
    for _, s, _, c in parts:
        weights[c] = weights.get(c, 0.0) + s.surface_area()
    if base_colour:
        weights[base_colour] = weights.get(base_colour, 0.0) + plinth.surface_area()
    weights = {c: float(np.sqrt(a)) for c, a in weights.items()}
    printed = merge(weights, slots)
    # Small parts are details that sit on bigger ones (pupils on eyes on the wrap): each claims its
    # own volume before anything bigger does; what no part claims (struts) joins the main colour.
    order = pieces + sorted([(n, s, c) for n, s, _, c in parts], key=lambda t: t[1].volume())
    claimed, regions = Manifold(), {}
    body = body.as_original()
    for _, s, c in order:  # as_original() evaluates now: chained lazy booleans grow without bound
        mine = ((s ^ body) - claimed).as_original()
        claimed = (claimed + mine).as_original()
        regions.setdefault(printed[c], []).append(mine)
    main = max(regions, key=lambda c: sum(weights[k] for k in printed if printed[k] == c))
    regions[main].append(body - claimed)
    colours = []
    for c, rs in regions.items():
        g = Manifold.batch_boolean(rs, OpType.Add)
        g = Manifold.batch_boolean([p for p in g.decompose() if p.volume() > SLIVER], OpType.Add)
        colours.append((f"{data['kind']}-{c[1:]}", g, c))
    colours.sort(key=lambda t: t[2] != main)
    lo = np.array(body.bounding_box())[:3]
    shift = [0, 0, -lo[2]]
    body = body.translate(shift)
    colours = [(n, g.translate(shift), c) for n, g, c in colours if not g.is_empty()]
    how = {}
    for n, _, h, _ in parts:
        how.setdefault(h, []).append(n)
    info = {"kind": data["kind"], "name": data["name"], "hero": data.get("hero", False), "mm_per_unit": mm,
            "parts": len(parts), "made": how, "colours_in_model": len(weights), "slots": slots,
            "printed_colours": sorted(set(printed.values())), "colour_map": printed, "base_studs": studs,
            "base_centre_mm": base_xy}
    return Figure(data["name"], body, colours, info)
