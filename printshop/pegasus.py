"""A Pegasus for the brick-system figure: a winged horse with a saddle the figure sits on.

The saddle carries two studs one pitch apart: the figure swings its legs forward and
sits on them by the sockets in the backs of its legs. The wings are separate pieces
that print flat; each has a pin at its root that turns in a hole in the shoulder
(profile.pin_fit, like the figure's hips), so they sweep forward and back and stay
where they are put. The pins tip down 25 degrees, so the wings, square to them, lean
out by as much and still print flat. Built standing, facing -y, hooves on z = 0.
"""
from __future__ import annotations

import numpy as np
from manifold3d import CrossSection, Manifold, OpType

from .figures import PIN_IN, along_x, hole_radius, pin_radius, span, stud
from .geom import cylinder, drop_slivers, sphere
from .profiles import FDM_04, Profile

WHITE, MANE, GOLD, SADDLE, WING = "#f4f1ea", "#b48aff", "#e8b030", "#7a4a2a", "#cfe3ff"
BODY_C, BODY_R = np.array([0.0, 0.0, 22.0]), np.array([7.5, 17.0, 8.5])  # the barrel, an ellipsoid
SEAT_Y = 2.0  # where along the back the saddle's studs are
STANCE = 5.6  # half the distance between the left and right legs: wide enough to stand a rider
SHOULDER = np.array([0.0, -6.0, 27.0])  # the wings' pivot line, along x through here
BOSS_R, BOSS_W = 2.6, 3.0  # the wing's root, a disc round its pin
LEAN = 25.0  # degrees the wings lean out (their pins tip down as much)


def _ellipsoid(c, r) -> Manifold:
    return sphere(1.0, 64).scale(list(r)).translate(list(c))


def _chain(points, radii) -> Manifold:
    """Spheres along a path, hulled pairwise: a neck, a tail, a mane."""
    balls = [sphere(r, 32).translate(list(p)) for p, r in zip(points, radii)]
    out = Manifold.batch_hull(balls[:2])
    for a, b in zip(balls[1:], balls[2:]):
        out += Manifold.batch_hull([a, b])
    return out


def surface_x(y: float, z: float) -> float:
    """The barrel's half-width at (y, z)."""
    t = 1 - ((y - BODY_C[1]) / BODY_R[1]) ** 2 - ((z - BODY_C[2]) / BODY_R[2]) ** 2
    return float(BODY_R[0] * np.sqrt(max(t, 0.0)))


def saddle_top() -> float:
    return float(BODY_C[2] + BODY_R[2] + 0.8)


def horse(p: Profile = FDM_04) -> list:
    """Everything but the wings: (name, Manifold, colour) parts that print as one piece."""
    body = _ellipsoid(BODY_C, BODY_R) + sphere(7.0, 48).translate([0, -12, 23])
    body += _chain([(0, -14, 27), (0, -21, 37)], [4.6, 3.6])  # neck
    body += _chain([(0, -22, 39), (0, -29, 36)], [3.8, 2.6])  # head and muzzle
    for sx in (1, -1):
        body += Manifold.cylinder(3.0, 1.0, 0.1, 16).translate([sx * 1.8, -20.5, 41.5])  # ears
        body -= sphere(0.6, 16).translate([sx * 3.3, -25.0, 39.0])  # eyes
    hooves = Manifold()
    for sx in (1, -1):
        for y in (-11.0, 12.0):
            body += Manifold.cylinder(16.5, 2.1, 2.8, 32).translate([sx * STANCE, y, 2.0])  # slimmer at the hoof
            hooves += cylinder(2.2, 3.0).translate([sx * STANCE, y, 0.0])
    hair = _chain([(0, 16, 24), (0, 21, 20), (0, 23, 12)], [2.6, 2.2, 1.6])  # tail
    hair += _chain([(0, -13.5, 31.5), (0, -18.5, 40.0), (0, -21.5, 42.6)], [1.5, 1.4, 1.1])  # mane
    top = saddle_top()
    pad = span(-6.6, 6.6, SEAT_Y - 5.0, SEAT_Y + 5.0, top - 0.01, top)  # flat on top, for the studs
    seat = Manifold.batch_hull([_ellipsoid(BODY_C, BODY_R + 0.8), pad]) ^ span(-6.6, 6.6, SEAT_Y - 5.0, SEAT_Y + 5.0,
                                                                             top - 4.5, top)
    for sx in (1, -1):
        seat += stud(p).translate([sx * p.pitch / 2, SEAT_Y, top - 0.01])
    shoulder = wing_seat(p)  # the left shoulder's; the right is its mirror
    shoulders = shoulder + shoulder.mirror([1, 0, 0])
    body -= shoulders
    seat -= shoulders
    body -= hooves + hair + seat
    parts = [("pegasus", body, WHITE), ("pegasus-hooves", hooves - hair, GOLD),
             ("pegasus-mane", hair - seat, MANE), ("pegasus-saddle", seat, SADDLE)]
    return [(n, drop_slivers(m), c) for n, m, c in parts]


def wing_outline() -> CrossSection:
    """A wing in its own plane: up from the root (0, 0), leading edge forward (-y), feathers trailing."""
    pts = [(-4.0, 0.0), (-6.0, 8.0), (-6.5, 16.0), (-4.5, 23.0), (-1.0, 27.0), (2.0, 26.0), (3.0, 22.5),
           (6.0, 21.5), (4.5, 18.0), (8.0, 16.5), (6.0, 13.0), (9.0, 11.0), (6.5, 8.0), (8.5, 5.0), (4.0, 2.5),
           (3.0, 0.0)]
    return CrossSection([pts[::-1]])  # counter-clockwise


def wing_frame(side: int = 1, lean_deg: float = LEAN) -> np.ndarray:
    """Where a wing pivots: local x is its pin's axis, out of the shoulder and tipped down `lean_deg`,
    so the wing (square to its pin) leans out by as much; the origin is the seat's flat face."""
    a = np.radians(lean_deg)
    R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, [surface_x(*SHOULDER[1:]) - 0.8, *SHOULDER[1:]]
    if side < 0:
        T = np.diag([-1.0, 1, 1, 1]) @ T @ np.diag([-1.0, 1, 1, 1])
    return T


def wing_seat(p: Profile = FDM_04, sweep: float = 45.0) -> Manifold:
    """What the left shoulder gives up to its wing: the hole the pin turns in, and room for the root disc
    and the blade's root to sweep `sweep` degrees either way (hulled between 5-degree steps, plus clearance)."""
    c = p.joint_clearance
    root = (wing_local(p) ^ along_x(c, 20.0, 10.0)).hull()  # boss and blade near the pin, not the pin
    root = root.minkowski_sum(sphere(c / np.cos(np.pi / 12) ** 2, 12))  # convex, so this is quick
    steps = [root.rotate([a, 0, 0]) for a in np.arange(-sweep, sweep + 5, 5.0)]
    swept = Manifold.batch_boolean([Manifold.batch_hull([a, b]) for a, b in zip(steps[:-1], steps[1:])], OpType.Add)
    room = swept + along_x(0.0, 20.0, BOSS_R + c)
    hole = along_x(-PIN_IN - 0.3, 0.01, hole_radius(p))
    return (room + hole).transform(wing_frame(1)[:3])


def wing_local(p: Profile = FDM_04, side: int = 1) -> Manifold:
    """A wing in its pivot frame: root disc on the pin, blade flush with the disc's outer face."""
    t, c = max(p.min_wall, 1.6), p.joint_clearance
    blade = Manifold.extrude(wing_outline(), t).rotate([90, 0, 90])  # outline -> (y, z), thickness -> x
    blade = blade.translate([c + BOSS_W - t, 0, 0])
    m = along_x(c, c + BOSS_W, BOSS_R) + along_x(-PIN_IN, c + 0.01, pin_radius(p)) + blade
    return m if side > 0 else m.mirror([1, 0, 0])


def wing(p: Profile = FDM_04, side: int = 1, sweep_deg: float = 0.0) -> Manifold:
    """One wing in place on the horse, swept forward `sweep_deg` about its pin."""
    return wing_local(p, side).rotate([sweep_deg * side, 0, 0]).transform(wing_frame(side)[:3])


def wing_print(p: Profile = FDM_04, side: int = 1) -> Manifold:
    """A wing the way it prints: blade flat on the bed, pin up."""
    m = wing_local(p, side).rotate([0, 90 * side, 0])
    return m.translate([0, 0, -m.bounding_box()[2]])


def pegasus(p: Profile = FDM_04) -> dict:
    """name -> list of (part, Manifold, colour), each the way it prints: the horse standing, wings flat."""
    return {"pegasus": horse(p), "wing-left": [("wing-left", wing_print(p, 1), WING)],
            "wing-right": [("wing-right", wing_print(p, -1), WING)]}
