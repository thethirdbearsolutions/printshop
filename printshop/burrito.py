"""Chaotic Attack burritos as printable, multi-colour figures that stand on the stud grid.

The game builds each burrito from three.js primitives (`buildBurrito()`); `tools/dump_burrito.mts`
writes those as coloured triangle soup. This module turns a dump into solids:

1. Weld each mesh. A closed one becomes a solid as it is. One that isn't closed (a cape is a
   single plane; a smile is half a torus with open ends) is thickened: every triangle is swept
   into a thin prism and the prisms are unioned.
2. Scale to the asked height, Z up, face towards -Y.
3. Resolve overlaps. The game stacks parts inside each other freely; a multi-colour print can't.
   Smaller parts win, so eyes and pins cut into the wrap instead of being buried by it.
4. Merge to at most `max_colours` colours (the AMS holds four), weighting by volume.
5. Seat it on a stud-grid base: a plate underside that clicks onto studs, a flat lid on top.

The result is a list of (name, solid, colour), ready for `write_3mf`.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np
from manifold3d import Manifold, Mesh

from .bricks import plate
from .geom import box
from .profiles import FDM_04, Profile


@dataclass
class Part:
    name: str
    colour: str
    solid: Manifold
    thickened: bool = False


@dataclass
class Figure:
    kind: str
    name: str
    objects: list  # (name, Manifold, "#RRGGBB")
    notes: list = field(default_factory=list)


def _rgb(c: str) -> np.ndarray:
    return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def _lab(c: str) -> np.ndarray:
    """CIE L*a*b* (D65) of an sRGB hex colour, so merging follows what eyes see, not raw RGB."""
    rgb = _rgb(c) / 255
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]) @ lin
    xyz /= [0.95047, 1.0, 1.08883]
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def _hex(v) -> str:
    return "#" + "".join(f"{int(round(x)):02x}" for x in np.clip(v, 0, 255))


def _weld(positions, index, tol=1e-5):
    v = np.asarray(positions, dtype=float).reshape(-1, 3)
    t = np.asarray(index, dtype=np.int64).reshape(-1, 3)
    key = np.round(v / tol).astype(np.int64)
    uniq, inverse = np.unique(key, axis=0, return_inverse=True)
    verts = np.zeros((len(uniq), 3))
    verts[inverse.ravel()] = v
    t = inverse.ravel()[t]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]  # drop collapsed triangles
    return verts, t


def _closed(t) -> bool:
    """Every edge used exactly twice, once in each direction."""
    e = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    fwd = {tuple(x) for x in e}
    return len(fwd) == len(e) and all((b, a) in fwd for a, b in fwd)


def _solid(verts, t) -> Manifold | None:
    if len(t) < 4 or not _closed(t):
        return None
    m = Manifold(Mesh(vert_properties=verts.astype(np.float32), tri_verts=t.astype(np.uint32)))
    if m.status().name != "NoError" or m.is_empty():
        return None
    if m.volume() < 0:  # inside out
        m = Manifold(Mesh(vert_properties=verts.astype(np.float32), tri_verts=t[:, ::-1].astype(np.uint32)))
    return m if m.volume() > 0 else None


def _fatten(solid: Manifold, verts, min_wall: float) -> tuple[Manifold, bool]:
    """A closed part thinner than min_wall in one direction (an extruded bolt, a flat star) is
    stretched along that direction, about its own centre, until it is min_wall thick."""
    c = verts.mean(0)
    w, vecs = np.linalg.eigh(np.cov((verts - c).T))
    e = vecs[:, 0]  # the thinnest direction
    proj = (verts - c) @ e
    extent = proj.max() - proj.min()
    if extent >= min_wall or extent <= 1e-9:
        return solid, False
    f = min_wall / extent
    m = np.eye(3) + (f - 1) * np.outer(e, e)
    off = c - m @ c
    return solid.transform(np.hstack([m, off.reshape(3, 1)])), True


def _shell(verts, t, thickness: float) -> Manifold | None:
    """Turn an open surface into a closed one: copy it out and in along its vertex normals by
    half the thickness each way, and stitch the two copies together along every open edge."""
    tri = verts[t]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])  # area-weighted face normals
    vn = np.zeros_like(verts)
    for k in range(3):
        np.add.at(vn, t[:, k], fn)
    ln = np.linalg.norm(vn, axis=1, keepdims=True)
    vn = np.where(ln > 1e-12, vn / np.maximum(ln, 1e-12), 0)
    n = len(verts)
    v2 = np.vstack([verts + vn * thickness / 2, verts - vn * thickness / 2])
    faces = [t, t[:, ::-1] + n]
    edges = np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]])
    seen = {tuple(e) for e in edges}
    for a, b in edges:
        if (b, a) not in seen:  # an open edge: wall it off
            faces.append(np.array([[b, a, a + n], [b, a + n, b + n]]))
    f = np.vstack(faces)
    m = Manifold(Mesh(vert_properties=v2.astype(np.float32), tri_verts=f.astype(np.uint32)))
    if m.status().name != "NoError" or m.is_empty():
        return None
    if m.volume() < 0:
        m = Manifold(Mesh(vert_properties=v2.astype(np.float32), tri_verts=f[:, ::-1].astype(np.uint32)))
    return m if m.volume() > 0 else None


def _thicken(verts, t, thickness: float) -> Manifold:
    """An open surface made printable: a clean shell if the surface allows one, else every
    triangle swept into a thin prism and the prisms unioned."""
    shell = _shell(verts, t, thickness)
    if shell is not None:
        return shell
    prisms = []
    for a, b, c in verts[t]:
        nrm = np.cross(b - a, c - a)
        ln = np.linalg.norm(nrm)
        if ln < 1e-12:
            continue
        o = nrm / ln * thickness / 2
        prisms.append(Manifold.hull_points(np.array([a - o, b - o, c - o, a + o, b + o, c + o])))
    return Manifold.batch_boolean(prisms, _ADD) if prisms else Manifold()


try:  # manifold3d >= 3 names the op OpType
    from manifold3d import OpType as _Op
    _ADD = _Op.Add
except ImportError:  # pragma: no cover
    from manifold3d import OpType  # type: ignore
    _ADD = OpType.Add


def load_parts(dump: dict, height_mm: float, min_wall: float) -> tuple[list[Part], list[str]]:
    """Solids in millimetres, Z up, standing on z = 0, centred, front towards -Y."""
    meshes = []
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for m in dump["meshes"]:
        v = np.asarray(m["positions"], dtype=float).reshape(-1, 3)
        # game: Y up, face towards -Z  ->  print: Z up, face towards -Y (a proper rotation)
        v = np.column_stack([v[:, 0], v[:, 2], v[:, 1]]) * [1, 1, 1]
        v[:, 0] *= -1  # (x, z, y) alone mirrors; flipping x makes it a rotation about Z
        meshes.append((m, v))
        lo, hi = np.minimum(lo, v.min(0)), np.maximum(hi, v.max(0))
    scale = height_mm / (hi[2] - lo[2])
    centre = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    parts, notes = [], []
    for m, v in meshes:
        v = (v - centre) * scale
        verts, t = _weld(v.ravel(), m["index"], tol=1e-4)
        solid = _solid(verts, t)
        thick = solid is None
        if thick:
            solid = _thicken(verts, t, min_wall)
        elif not solid.is_empty():
            solid, grew = _fatten(solid, verts, min_wall)
            thick = grew
        if solid.is_empty():
            notes.append(f"skipped {m['name']} ({m['color']}): nothing printable")
            continue
        parts.append(Part(m["name"], m["color"], solid, thick))
    return parts, notes


def resolve_overlaps(parts: list[Part]) -> list[Part]:
    """Smaller parts win: each part keeps only what no smaller part already claims."""
    out, claimed = [], Manifold()
    for p in sorted(parts, key=lambda p: p.solid.volume()):
        piece = p.solid - claimed
        claimed = claimed + p.solid
        if piece.volume() > 1e-3:
            out.append(Part(p.name, p.colour, piece, p.thickened))
    return out


def merge_colours(parts: list[Part], max_colours: int) -> dict[str, str]:
    """Map each colour to one of at most `max_colours`, merging the closest pair (by L*a*b*
    distance, the smaller-volume colour joining the larger) until few enough remain."""
    vol: dict[str, float] = {}
    for p in parts:
        vol[p.colour] = vol.get(p.colour, 0) + p.solid.volume()
    groups = {c: [c] for c in vol}
    while len(groups) > max_colours:
        keys = list(groups)
        best = None
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                d = np.linalg.norm(_lab(a) - _lab(b))
                if best is None or d < best[0]:
                    best = (d, a, b)
        _, a, b = best
        keep, drop = (a, b) if vol[a] >= vol[b] else (b, a)
        groups[keep] += groups.pop(drop)
        vol[keep] += vol.pop(drop)
    return {c: k for k, members in groups.items() for c in members}


def _clean(m: Manifold, min_volume: float) -> Manifold:
    """Drop the near-zero slivers that boolean cuts leave behind."""
    keep = [p for p in m.decompose() if p.volume() >= min_volume]
    return Manifold.batch_boolean(keep, _ADD) if keep else Manifold()


def anchor_floaters(parts: list[Part], profile: Profile, min_volume: float = 1.0) -> tuple[list[Part], list[str]]:
    """The game can hold things in midair (a staff beside a hand); a print can't. Every piece that
    doesn't touch the main body gets a short strut, in its own colour, to the nearest part of it.
    Specks smaller than `min_volume` mm3 are dropped instead."""
    from .geom import closest_points, strut
    notes = []
    for p in parts:
        p.solid = _clean(p.solid, 0.05)
    tiny = sum(p.solid.is_empty() for p in parts)
    parts = [p for p in parts if not p.solid.is_empty()]
    whole = Manifold.batch_boolean([p.solid for p in parts], _ADD)
    pieces = sorted(whole.decompose(), key=lambda m: -m.volume())
    main, dropped = pieces[0], tiny
    for piece in pieces[1:]:
        members = [p for p in parts if not (p.solid ^ piece).is_empty()]
        if piece.volume() < min_volume or not members:
            for p in members:
                p.solid = p.solid - piece
            dropped += 1
            continue
        owner = max(members, key=lambda p: (p.solid ^ piece).volume())
        a, b = closest_points(piece, main)
        parts.append(Part(owner.name + "-strut", owner.colour, strut(a, b, profile.min_wall / 2 + 0.2, segments=16)))
        main = main + piece
        notes.append(f"added a support strut for {owner.name} ({owner.colour}), which floats in the game")
    if dropped:
        notes.append(f"dropped {dropped} speck(s) too small to print")
    return [p for p in parts if not p.solid.is_empty()], notes


def base_for(footprint_mm: float, profile: Profile = FDM_04, lid: float = 1.6) -> tuple[Manifold, float, int]:
    """A square stud-grid base big enough for the footprint: a plate's underside (tubes that grip
    studs), no studs on top, and a solid lid. Returns (base, top z, studs per side)."""
    n = max(2, math.ceil((footprint_mm + 2.0) / profile.pitch))
    p = plate(n, n, profile)
    h = profile.plate_height
    side = n * profile.pitch - 2 * profile.side_gap
    p = p ^ box([side, side, h], center=False).translate([-side / 2, -side / 2, 0])  # drop the studs
    p = p + box([side, side, lid], center=False).translate([-side / 2, -side / 2, h - 0.01])
    return p, h + lid, n


def figure(dump: dict, height_mm: float = 40.0, max_colours: int = 4, with_base: bool = True,
           base_colour: str | None = None, sink_mm: float = 1.0, profile: Profile = FDM_04) -> Figure:
    parts, notes = load_parts(dump, height_mm, profile.min_wall)
    parts, more = anchor_floaters(parts, profile)
    notes += more
    parts = resolve_overlaps(parts)
    mapping = merge_colours(parts, max(1, max_colours))
    by_colour: dict[str, list[Manifold]] = {}
    for p in parts:
        by_colour.setdefault(mapping[p.colour], []).append(p.solid)
    solids = {c: _clean(Manifold.batch_boolean(ms, _ADD), 0.5) for c, ms in by_colour.items()}
    objects = []
    if with_base:
        # Size the base by what's near the ground (feet, wrap), not by a cape or a raised arm.
        low = box([1e4, 1e4, height_mm * 0.3], center=False).translate([-5e3, -5e3, -1])
        lo, hi = np.array((Manifold.batch_boolean(list(solids.values()), _ADD) ^ low).bounding_box()).reshape(2, 3)
        footprint = float(max(hi[0] - lo[0], hi[1] - lo[1]))
        base, top, n = base_for(footprint, profile)
        lift = top - sink_mm  # the figure sinks into the lid, never through it into the stud cavity
        solids = {c: s.translate([0, 0, lift]) for c, s in solids.items()}
        everything = Manifold.batch_boolean(list(solids.values()), _ADD)
        base = _clean(base - everything, 0.5)
        if base_colour is None:  # share the figure's darkest filament, so the base costs no AMS slot
            base_colour = min(solids, key=lambda c: _lab(c)[0])
        objects.append(("base", base, base_colour))
        notes.append(f"base: {n}x{n} studs, clicks onto a plate")
    for c, s in sorted(solids.items(), key=lambda kv: -kv[1].volume()):
        if not s.is_empty():
            objects.append((f"{dump['kind']}-{c[1:]}", s, c))
    thick = sum(p.thickened for p in parts)
    if thick:
        notes.append(f"{thick} open surface(s) thickened to {profile.min_wall} mm")
    return Figure(dump["kind"], dump.get("name", dump["kind"]), objects, notes)


def load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)
