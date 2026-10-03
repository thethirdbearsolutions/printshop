"""Print-in-place joints: parts that come off the printer already assembled and moving.

These are the building blocks for articulated figures (a rabbitstew champion's
hinges and ball joints, a figure's shoulders). Each joint is returned as its
separate moving parts, so tests can check they really are separate and that
the gap between them is at least the profile's clearance.
"""
from __future__ import annotations

import numpy as np
from manifold3d import Manifold

from .geom import box, cylinder, sphere
from .profiles import FDM_04, Profile


def hinge(pin_radius: float = 2.5, length: float = 16.0, leaf: float = 12.0, thickness: float = 3.0,
          knuckles: int = 3, profile: Profile = FDM_04) -> tuple[Manifold, Manifold]:
    """A print-in-place hinge lying flat: two leaves around one axis (x), knuckles alternating.

    The pin belongs to leaf A; leaf B's knuckles ring it with `joint_clearance` all round,
    so it swings but cannot fall off. Cone ends on the pin print without support.
    """
    c = profile.joint_clearance
    seg = length / knuckles
    knuckle_r = pin_radius + c + max(profile.min_wall, 1.2)

    def barrel(x0, x1):  # a knuckle along x, axis at y=0, z=knuckle_r
        return cylinder(x1 - x0, knuckle_r).rotate([0, 90, 0]).translate([x0, 0, knuckle_r])

    a = box([length, leaf, thickness], center=False).translate([0, -leaf - knuckle_r + 0.5, 0])
    b = box([length, leaf, thickness], center=False).translate([0, knuckle_r - 0.5, 0])
    for k in range(knuckles):
        x0, x1 = k * seg, (k + 1) * seg
        mine = a if k % 2 == 0 else b
        lo = x0 + (c if k else 0)
        hi = x1 - (c if k < knuckles - 1 else 0)
        mine += barrel(lo, hi)
        if k % 2 == 0:
            a = mine
        else:
            b = mine
    # Each leaf gives way to the other leaf's knuckles (a clearance-sized envelope round each).
    for k in range(knuckles):
        x0, x1 = k * seg, (k + 1) * seg
        env = cylinder(x1 - x0 + 2 * c, knuckle_r + c).rotate([0, 90, 0]).translate([x0 - c, 0, knuckle_r])
        if k % 2 == 0:
            b -= env
        else:
            a -= env
    # B's knuckles are bored out round the pin; the pin runs the full length and belongs to A.
    b -= cylinder(length + 2, pin_radius + c).rotate([0, 90, 0]).translate([-1, 0, knuckle_r])
    a += cylinder(length, pin_radius).rotate([0, 90, 0]).translate([0, 0, knuckle_r])
    return a, b


def ball_joint(ball_radius: float = 4.0, stem: float = 6.0, profile: Profile = FDM_04,
               cone_deg: float = 35.0) -> tuple[Manifold, Manifold]:
    """A captured ball-and-socket printed in place, ball stem pointing up (+z).

    The socket shell wraps the ball past its equator, so the ball cannot pull out;
    the opening's half-angle `cone_deg` limits how far the stem can tilt, which is
    how a ball joint's cone limit in the simulation becomes a physical stop.
    """
    c, w = profile.joint_clearance, max(profile.min_wall, 1.6)
    stem_r = ball_radius * np.sin(np.radians(cone_deg)) * 0.75
    ball = sphere(ball_radius).translate([0, 0, ball_radius + w + c])
    ball += cylinder(stem + ball_radius, stem_r).translate([0, 0, ball_radius + w + c])
    centre = [0, 0, ball_radius + w + c]
    shell_r = ball_radius + c + w
    socket = sphere(shell_r).translate(centre) - sphere(ball_radius + c).translate(centre)
    # Open the top in a cone of half-angle cone_deg (plus clearance for the stem).
    open_r = (ball_radius + 2 * c + w) * np.tan(np.radians(cone_deg)) + stem_r + c
    cone = Manifold.cylinder(shell_r + 1, 0.01, open_r + 1, 64).translate(centre)
    socket -= cone
    # A flat foot so the socket sits on the bed; trim the shell's bottom flat.
    socket = socket.trim_by_plane([0, 0, 1], 0.0)
    socket += cylinder(w, shell_r).translate([0, 0, 0])
    socket -= sphere(ball_radius + c).translate(centre)
    return socket, ball


def gap(a: Manifold, b: Manifold, search: float = 5.0) -> float:
    """Smallest distance between two parts (0 if they touch or overlap)."""
    return float(a.min_gap(b, search))
