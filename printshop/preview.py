"""Shaded PNG previews of solids with a small software rasteriser (no GPU, no Blender)."""
from __future__ import annotations

import numpy as np
from PIL import Image

PALETTE = ["#4f9ea6", "#e0a84f", "#c8553d", "#7a8b5a", "#8a6fb0", "#3d6e8f"]


def render(objects, path: str, size: int = 900, azimuth: float = -55.0, elevation: float = 32.0) -> None:
    """objects: list of (Manifold, "#RRGGBB" or None), drawn in one scene from an orbit camera."""
    az, el = np.radians(azimuth), np.radians(elevation)
    d = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])  # towards the camera
    r = np.cross([0, 0, 1], d)
    r /= np.linalg.norm(r)
    u = np.cross(d, r)
    meshes = []
    for i, (m, colour) in enumerate(objects):
        mesh = m.to_mesh()
        meshes.append((mesh.vert_properties[:, :3].astype(float), np.asarray(mesh.tri_verts), colour or PALETTE[i % len(PALETTE)]))
    allv = np.concatenate([v for v, _, _ in meshes])
    sxy = np.column_stack([allv @ r, allv @ u])
    lo, hi = sxy.min(0), sxy.max(0)
    scale = 0.86 * size / max((hi - lo).max(), 1e-9)
    img = np.full((size, size, 3), 244.0)
    zbuf = np.full((size, size), np.inf)
    light = d + np.array([0.3, 0.2, 0.6])
    light /= np.linalg.norm(light)
    for v, t, colour in meshes:
        xy = (np.column_stack([v @ r, v @ u]) - (lo + hi) / 2) * scale + size / 2
        xy[:, 1] = size - xy[:, 1]
        depth = -(v @ d)
        tri = v[t]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
        base = np.array([int(colour[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)
        for k in range(len(t)):
            a, b, c = xy[t[k]]
            x0, x1 = int(max(min(a[0], b[0], c[0]), 0)), int(min(max(a[0], b[0], c[0]) + 1, size))
            y0, y1 = int(max(min(a[1], b[1], c[1]), 0)), int(min(max(a[1], b[1], c[1]) + 1, size))
            if x1 <= x0 or y1 <= y0:
                continue
            den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(den) < 1e-9:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
            w0 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / den
            w1 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / den
            w2 = 1 - w0 - w1
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            z = w0 * depth[t[k][0]] + w1 * depth[t[k][1]] + w2 * depth[t[k][2]]
            sub = zbuf[y0:y1, x0:x1]
            hit = inside & (z < sub)
            sub[hit] = z[hit]
            img[y0:y1, x0:x1][hit] = base * shade[k]
    Image.fromarray(img.clip(0, 255).astype(np.uint8)).save(path)
