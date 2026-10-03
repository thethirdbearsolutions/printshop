"""Assembled scenes: the figure kitted out, and riding. For previews and fit tests, not for printing.

Each scene is a list of (name, Manifold, colour) in place: every part as it would sit
once put together, so the tests can check that nothing runs into anything else.
"""
from __future__ import annotations

import numpy as np

from . import armory, figures as F
from .pegasus import SEAT_Y, horse, saddle_top, wing
from .profiles import FDM_04, Profile

COLOURS = {"head": "#f2d9a8", "torso": "#2f6fff", "arm-left": "#2f6fff", "arm-right": "#2f6fff",
           "hips": "#3a3a48", "leg-left": "#3a3a48", "leg-right": "#3a3a48"}


def _place_rot(m, R, t):
    return m.transform(np.hstack([R, np.reshape(t, (3, 1))]))


def knight(p: Profile = FDM_04, seated: bool = False) -> list:
    """The figure in helmet and armour, sword raised in its right hand, shield on its left arm.
    seated=True swings the legs forward, ready for a saddle."""
    L = F.Layout(p)
    parts = F.figure(p)
    parts["head"] = parts["head"].translate([0, 0, armory.YOKE])  # the armour's yoke lifts it
    parts["arm-right"] = F.rotate_about_x(parts["arm-right"], -90, L.shoulder)
    if seated:
        for leg in ("leg-left", "leg-right"):
            parts[leg] = F.rotate_about_x(parts[leg], -90, L.hip_axis)
    out = [(n, m, COLOURS[n]) for n, m in parts.items()]
    out += armory.helmet(p) + armory.armour(p)
    # The sword along the right hand's clip (y), grip centred in it, then raised with the arm.
    c = F.hand_centre(p, -1)
    out += [(n, F.rotate_about_x(m.rotate([90, 0, 0]).translate(c + [0, 4.5, 0]), -90, L.shoulder), col)
            for n, m, col in armory.sword(p)]
    # The shield on the left hand: its bar along the clip (y), its face outwards (+x).
    c = F.hand_centre(p, 1)
    R = np.array([[0.0, -1.0, 0.0], [0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]])  # shield z -> y, -y -> +x
    t = c + [armory.shield_bar_axis(p), 0, 0]
    out += [(n, _place_rot(m, R, t), col) for n, m, col in armory.shield(p)]
    return out


def rider(p: Profile = FDM_04, sweep_deg: float = 25.0) -> list:
    """The knight sitting on the Pegasus, the sockets in the backs of its legs on the saddle's studs,
    the wings swept forward `sweep_deg` on their pins, clear of the shield."""
    L = F.Layout(p)
    seat_y = F.SEAT_Z - L.hip_axis  # a seat socket's centre once the leg swings forward (figure frame)
    lift = [0.0, SEAT_Y - seat_y, saddle_top() - (L.hip_axis - F.DEPTH / 2)]
    out = [(n, m.translate(lift), c) for n, m, c in knight(p, seated=True)]
    wings = [(f"wing-{s}", wing(p, k, sweep_deg), "#cfe3ff") for s, k in (("left", 1), ("right", -1))]
    return out + horse(p) + wings
