"""Checks a part should pass before it is worth slicing."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from manifold3d import Manifold


@dataclass
class Report:
    pieces: int
    genus: int
    volume_cm3: float
    size_mm: tuple
    stands: bool
    stability_margin_mm: float

    def ok(self) -> bool:
        return self.pieces == 1 and self.stands


def _hull_2d(points: np.ndarray) -> np.ndarray:
    """Monotone-chain convex hull, counter-clockwise."""
    pts = sorted(map(tuple, np.unique(points.round(4), axis=0)))
    if len(pts) < 3:
        return np.array(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.array(lower[:-1] + upper[:-1])


def stability(m: Manifold, contact_band: float = 0.3) -> tuple[bool, float]:
    """Does the part stand on its lowest face? Returns (stands, margin): the margin is how far
    the centre of mass sits inside the footprint's edge (negative = it tips over)."""
    mesh = m.to_mesh()
    v = mesh.vert_properties[:, :3].astype(float)
    t = np.asarray(mesh.tri_verts)
    # Centre of mass of a closed triangle mesh, by signed tetrahedra from the origin.
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    vol = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
    com = ((a + b + c) / 4.0 * vol[:, None]).sum(0) / vol.sum()
    foot = v[v[:, 2] <= v[:, 2].min() + contact_band][:, :2]
    hull = _hull_2d(foot)
    if len(hull) < 3:
        return False, -np.inf
    margins = []
    for i in range(len(hull)):
        p, q = hull[i], hull[(i + 1) % len(hull)]
        e = q - p
        normal = np.array([e[1], -e[0]]) / np.linalg.norm(e)  # outward for a CCW hull
        margins.append(-float((com[:2] - p) @ normal))
    margin = min(margins)
    return margin > 0, margin


def check(m: Manifold) -> Report:
    lo, hi = np.array(m.bounding_box()).reshape(2, 3)
    stands, margin = stability(m)
    return Report(pieces=len(m.decompose()), genus=m.genus(), volume_cm3=round(m.volume() / 1000, 2),
                  size_mm=tuple(round(float(x), 1) for x in hi - lo), stands=stands,
                  stability_margin_mm=round(margin, 2))
