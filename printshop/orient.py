"""Laying a part or an assembly out for printing: which way up, how much support, flat feet.

Candidate orientations put one face of the convex hull of everything on the bed
(the biggest faces first, plus the six axis directions). Every piece is trimmed
`flat` mm off the bottom, so whatever touches the bed stands on a flat foot
instead of a point or a line. The orientation chosen has the least support (the
area of downward faces steeper than the overhang limit, not on the bed) less its
contact area with the bed, both in mm^2: a big foot is worth some support.
"""
from __future__ import annotations

import numpy as np
from manifold3d import Manifold


def _tris(m: Manifold):
    mesh = m.to_mesh()
    v = mesh.vert_properties[:, :3].astype(float)
    return v[np.asarray(mesh.tri_verts)]


def support_area(solids, overhang_deg: float = 45.0, bed: float = 0.3) -> float:
    """mm^2 of downward faces steeper than `overhang_deg` from vertical, above the bed (z = lowest point)."""
    tris = [_tris(m) for m in solids]
    z0 = min(t[:, :, 2].min() for t in tris)
    total = 0.0
    for t in tris:
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        area = np.linalg.norm(n, axis=1) / 2
        nz = n[:, 2] / np.maximum(2 * area, 1e-12)
        down = (nz < -np.cos(np.radians(overhang_deg))) & (t[:, :, 2].max(1) > z0 + bed)
        total += float(area[down].sum())
    return total


def bed_contact(solids, tol: float = 0.05) -> float:
    """mm^2 of flat face on the bed."""
    tris = [_tris(m) for m in solids]
    z0 = min(t[:, :, 2].min() for t in tris)
    total = 0.0
    for t in tris:
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        on = (t[:, :, 2].max(1) < z0 + tol) & (n[:, 2] < 0)
        total += float(np.linalg.norm(n[on], axis=1).sum() / 2)
    return total


def turn_to_bed(normal) -> np.ndarray:
    """Rotation taking `normal` to -z (straight down)."""
    a = np.asarray(normal, float) / np.linalg.norm(normal)
    b = np.array([0.0, 0.0, -1.0])
    v, c = np.cross(a, b), float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def candidates(solids, n: int = 24) -> list:
    """Downward normals to try: the hull's biggest faces, then the six axis directions."""
    t = _tris(Manifold.batch_hull(list(solids)))
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    area = np.linalg.norm(nrm, axis=1)
    keys = np.round(nrm / np.maximum(area[:, None], 1e-12), 2)
    faces = {}
    for k, a in zip(map(tuple, keys), area):
        faces[k] = faces.get(k, 0.0) + a / 2
    best = sorted(faces, key=lambda k: -faces[k])[:n]
    return [np.array(k) for k in best] + [np.array(d, float) for d in np.vstack([np.eye(3), -np.eye(3)])]


def _place(parts, R, flat: float):
    turned = [m.transform(np.hstack([R, np.zeros((3, 1))])) for m in parts]
    lo = np.min([np.array(m.bounding_box())[:3] for m in turned], axis=0)
    hi = np.max([np.array(m.bounding_box())[3:] for m in turned], axis=0)
    shift = [-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2] - flat]
    moved = [m.translate(shift) for m in turned]
    return [m.trim_by_plane([0, 0, 1], 0.0) if m.bounding_box()[2] < 0 else m for m in moved]


def lay_flat(solids: dict, flat: float = 1.0, overhang_deg: float = 45.0):
    """Turn `solids` (name -> Manifold, assembled) the best way up, set them on z = 0 with flat
    feet. Returns (laid-out solids, info)."""
    names, parts = list(solids), list(solids.values())
    best = None
    for d in candidates(parts):
        laid = _place(parts, turn_to_bed(d), flat)
        support, contact = support_area(laid, overhang_deg), bed_contact(laid)
        if best is None or support - contact < best[0]:
            best = (support - contact, support, contact, d, laid)
    _, support, contact, down, laid = best
    out = dict(zip(names, laid))
    lo, hi = np.array(Manifold.batch_hull(laid).bounding_box()).reshape(2, 3)
    info = {"down": [round(float(x), 3) for x in down], "support_mm2": round(support, 1),
            "bed_contact_mm2": round(contact, 1), "flat_mm": flat,
            "on_bed": [n for n, m in out.items() if m.bounding_box()[2] < 1e-3],
            "trimmed_mm3": {n: round(solids[n].volume() - out[n].volume(), 1) for n in names},
            "size_mm": [round(float(x), 1) for x in hi - lo]}
    return out, info
