"""Bricks and plates compatible with the common 8 mm stud system.

Sizes are in studs (width x length) and plates (one brick = 3 plates). The
underside follows the usual pattern: hollow shell, tubes between studs for
parts at least 2x2, a solid pin between studs for 1xN parts.
"""
from __future__ import annotations

from manifold3d import Manifold

from .geom import box, cylinder, sphere
from .profiles import FDM_04, Profile


def brick(width: int, length: int, plates: int = 3, profile: Profile = FDM_04,
          stud_delta: float = 0.0, tube_delta: float = 0.0, dots: int = 0, studs: bool = True) -> Manifold:
    """A width x length brick `plates` plates tall (3 = brick, 1 = plate), studs up, origin at the bottom centre.

    stud_delta / tube_delta nudge the gripping diameters for tolerance testing;
    dots engraves that many marks on one long side so test pieces can be told apart;
    studs=False leaves the top flat (a base for something to stand on).
    """
    p = profile
    h = plates * p.plate_height
    ox, oy = width * p.pitch - 2 * p.side_gap, length * p.pitch - 2 * p.side_gap
    body = box([ox, oy, h], center=False).translate([-ox / 2, -oy / 2, 0])
    ix, iy = ox - 2 * p.wall, oy - 2 * p.wall
    cavity_h = h - p.top
    body -= box([ix, iy, cavity_h], center=False).translate([-ix / 2, -iy / 2, -0.01])

    def grid(n):  # stud centres along one axis
        return [(i + 0.5) * p.pitch - n * p.pitch / 2 for i in range(n)]

    stud_r = (p.stud_diameter + stud_delta - p.xy_compensation) / 2
    for x in grid(width) if studs else []:
        for y in grid(length):
            body += cylinder(p.stud_height, stud_r).translate([x, y, h - 0.01])

    if width >= 2 and length >= 2:
        to = (p.tube_outer + tube_delta - p.xy_compensation) / 2
        ti = (p.tube_inner + p.xy_compensation) / 2
        for i in range(1, width):
            for j in range(1, length):
                x, y = i * p.pitch - width * p.pitch / 2, j * p.pitch - length * p.pitch / 2
                tube = cylinder(cavity_h, to) - cylinder(cavity_h + 0.02, ti).translate([0, 0, -0.01])
                body += tube.translate([x, y, 0])
    elif max(width, length) >= 2:
        pr = (p.pin_diameter + tube_delta - p.xy_compensation) / 2
        n = max(width, length)
        for i in range(1, n):
            c = i * p.pitch - n * p.pitch / 2
            body += cylinder(cavity_h, pr).translate([c, 0, 0] if width > length else [0, c, 0])

    for k in range(dots):  # small hemispherical dimples on the -y face
        x = (k - (dots - 1) / 2) * 1.6
        body -= sphere(0.45, 16).translate([x, -oy / 2, h / 2])
    return body


def plate(width: int, length: int, profile: Profile = FDM_04, **kw) -> Manifold:
    return brick(width, length, plates=1, profile=profile, **kw)


#: The fits a tolerance card sweeps, in mm added to the profile's stud and tube diameters.
CARD_DELTAS = (-0.10, -0.05, 0.0, 0.05, 0.10)


def tolerance_card(profile: Profile = FDM_04, deltas=CARD_DELTAS) -> list[tuple[str, Manifold]]:
    """2x2 plates whose studs and tubes step through `deltas`; dimple count = position in the list.

    Press each onto real bricks (studs down onto a plate, and a real 2x2 on top). Pick the
    one that clicks and holds without splitting, then set the profile from its delta.
    """
    pieces = []
    for k, d in enumerate(deltas):
        name = f"card-{k + 1}-delta{d:+.2f}"
        piece = plate(2, 2, profile, stud_delta=d, tube_delta=d, dots=k + 1)
        pieces.append((name, piece.translate([(k - (len(deltas) - 1) / 2) * 20.0, 0, 0])))
    return pieces
