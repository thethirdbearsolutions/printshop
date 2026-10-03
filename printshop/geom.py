"""Solid-building helpers on top of manifold3d. All lengths are millimetres."""
from __future__ import annotations

import numpy as np
from manifold3d import Manifold

SEGMENTS = 64


def quat_matrix(q) -> np.ndarray:
    """Rotation matrix of a (w, x, y, z) quaternion."""
    w, x, y, z = np.asarray(q, dtype=float) / np.linalg.norm(q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def place(m: Manifold, rot: np.ndarray, pos) -> Manifold:
    """Rotate by a 3x3 matrix, then move to pos."""
    return m.transform(np.hstack([rot, np.asarray(pos, dtype=float).reshape(3, 1)]))


def box(size, center: bool = True) -> Manifold:
    return Manifold.cube(list(map(float, size)), center=center)


def cylinder(height: float, radius: float, center: bool = False, segments: int = SEGMENTS) -> Manifold:
    return Manifold.cylinder(float(height), float(radius), float(radius), segments, center)


def sphere(radius: float, segments: int = SEGMENTS) -> Manifold:
    return Manifold.sphere(float(radius), segments)


def union(parts: list) -> Manifold:
    return _sum(parts)


def _sum(parts: list) -> Manifold:
    out = parts[0]
    for p in parts[1:]:
        out = out + p
    return out


def strut(p, q, radius: float, segments: int = 24) -> Manifold:
    """A round rod from p to q (ends rounded off by its own radius of overshoot)."""
    p, q = np.asarray(p, dtype=float), np.asarray(q, dtype=float)
    v = q - p
    length = float(np.linalg.norm(v))
    z = v / length
    x = np.cross(z, [0, 0, 1] if abs(z[2]) < 0.9 else [1, 0, 0])
    x /= np.linalg.norm(x)
    rot = np.column_stack([x, np.cross(z, x), z])
    return place(cylinder(length + 2 * radius, radius, segments=segments), rot, p - z * radius)


def closest_points(a: Manifold, b: Manifold, chunk: int = 256):
    """The closest pair of vertices, one on each solid (memory stays at chunk x len(b))."""
    va = a.to_mesh().vert_properties[:, :3].astype(float)
    vb = b.to_mesh().vert_properties[:, :3].astype(float)
    nb = (vb * vb).sum(1)
    best = (np.inf, None, None)
    for i in range(0, len(va), chunk):
        part = va[i:i + chunk]
        d2 = (part * part).sum(1)[:, None] + nb[None, :] - 2 * part @ vb.T
        j = np.unravel_index(np.argmin(d2), d2.shape)
        if d2[j] < best[0]:
            best = (d2[j], part[j[0]], vb[j[1]])
    return best[1], best[2]


def fuse(parts: list, bridge_radius: float) -> Manifold:
    """Union parts into one solid; any piece left floating is bridged to the largest by a strut."""
    pieces = sorted(_sum(parts).decompose(), key=lambda m: -m.volume())
    main = pieces[0]
    for piece in pieces[1:]:
        p, q = closest_points(piece, main)
        main = main + piece + strut(p, q, bridge_radius)
    return main


def bounds(m: Manifold) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = np.array(m.bounding_box()).reshape(2, 3)
    return lo, hi


def sit_on_bed(m: Manifold) -> Manifold:
    """Centre in x/y and put the lowest point on z = 0."""
    lo, hi = bounds(m)
    return m.translate([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
