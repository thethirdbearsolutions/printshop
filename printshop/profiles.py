"""Printer profiles: the few numbers that decide whether parts fit.

Every generator takes a Profile instead of hard-coding sizes, so once a test
card has been printed on a real machine the winning values go here and every
brick, joint and figure picks them up.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Profile:
    name: str
    #: Brick-system nominal sizes (mm). Nominal values come from the published brick geometry.
    pitch: float = 8.0
    plate_height: float = 3.2
    stud_diameter: float = 4.8
    stud_height: float = 1.7
    wall: float = 1.2
    top: float = 1.0
    tube_outer: float = 6.51
    tube_inner: float = 4.8
    pin_diameter: float = 3.2  # the underside pin of 1xN parts; also the bar a figure's hand grips
    side_gap: float = 0.1  # each outer face is pulled in by this much so neighbours sit flush
    #: Figure fits (mm): the bar a hand grips is pin_diameter.
    clip_fit: float = -0.10  # a hand's clip bore is this much off the bar's diameter (negative grips)
    clip_opening: float = 0.75  # the clip's mouth as a fraction of the bar's diameter: it snaps over, then holds
    pin_fit: float = 0.15  # a hole is this much wider than the pin turning in it (hips, shoulders): stiff but turns
    socket_delta: float = 0.0  # added to a stud socket (a head on a neck stud, a foot on a plate) to tune its grip
    #: Printer behaviour (mm).
    min_wall: float = 1.2  # thinnest feature worth printing
    joint_clearance: float = 0.35  # gap between moving parts printed in place
    xy_compensation: float = 0.0  # added to holes, subtracted from pegs, to undo the printer's bulge

    def tuned(self, **kw) -> "Profile":
        return replace(self, **kw)


#: Starting point for a well-calibrated FDM printer with a 0.4 mm nozzle.
FDM_04 = Profile(name="fdm-0.4", min_wall=1.2, joint_clearance=0.35, xy_compensation=0.05)
#: Starting point for a hobby resin printer. Fits are tighter; parts are stiffer, so clutch is less forgiving.
RESIN = Profile(name="resin", min_wall=0.8, joint_clearance=0.2, xy_compensation=0.0, pin_fit=0.08)

PROFILES = {p.name: p for p in (FDM_04, RESIN)}
