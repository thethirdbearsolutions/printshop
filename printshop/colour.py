"""Colours for multi-colour prints: merge a model's many colours down to the filaments a printer holds."""
from __future__ import annotations

import numpy as np


def rgb(hex_colour: str) -> np.ndarray:
    h = hex_colour.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def lab(hex_colour: str) -> np.ndarray:
    """CIE L*a*b* (D65) of an sRGB colour, where distances are roughly how different colours look."""
    c = rgb(hex_colour) / 255
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]) @ c
    xyz /= [0.95047, 1.0, 1.08883]
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def merge(weights: dict, slots: int) -> dict:
    """Merge colours ({"#rrggbb": weight}) until at most `slots` remain, Ward's way: each step merges
    the pair whose merge adds the least weighted colour error, so a big area keeps its own colour
    and close shades go together first. The merged pair prints in the colour with more weight (a
    real filament colour, not a blend). Returns {original colour: the colour it prints in}."""
    groups = {c: [c] for c in weights}
    w = dict(weights)
    centre = {c: lab(c) for c in weights}
    while len(groups) > slots:
        keys = list(groups)
        best = None
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                cost = w[a] * w[b] / (w[a] + w[b]) * float(np.sum((centre[a] - centre[b]) ** 2))
                if best is None or cost < best[0]:
                    best = (cost, a, b)
        _, a, b = best
        keep, drop = (a, b) if w[a] >= w[b] else (b, a)
        centre[keep] = (w[a] * centre[a] + w[b] * centre[b]) / (w[a] + w[b])
        groups[keep] += groups.pop(drop)
        w[keep] += w.pop(drop)
    return {c: k for k, members in groups.items() for c in members}
