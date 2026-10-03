"""A cradle that holds a figure in a pose it cannot keep by itself.

The figure is set with its lowest point `base` mm above the bed. The cradle is the
figure's outline (its projection, hulled, plus a margin) built up to `rise` of the
figure's height, less each piece swept straight up and grown by `gap`. So the figure
drops in from above and lifts straight out, but cannot tip: leaning, it runs into
the walls. Each piece's sweep is its convex hull, so the cradle never reaches into a
notch the figure could not be lifted out of.
"""
from __future__ import annotations

import numpy as np
from manifold3d import CrossSection, Manifold

from .articulate import union
from .geom import sphere


def cradle(solids: list, gap: float = 0.3, base: float = 3.0, margin: float = 3.0, rise: float = 0.35):
    """(cradle, the figure's pieces moved to sit in it). Solids are the posed figure, standing."""
    whole = union(solids)
    lo, hi = np.array(whole.bounding_box()).reshape(2, 3)
    shift = [-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, base - lo[2]]
    placed = [s.translate(shift) for s in solids]
    top = base + rise * (hi[2] - lo[2])
    outline = CrossSection.hull(whole.translate(shift).project()).offset(margin, circular_segments=48)
    block = Manifold.extrude(outline, top)
    grow = sphere(gap / np.cos(np.pi / 12) ** 2, 12)  # circumscribed, so the gap is never under `gap`
    carve = union([Manifold.batch_hull([p, p.translate([0, 0, hi[2] - lo[2] + top])]).minkowski_sum(grow)
                   for p in placed])
    return block - carve, placed
