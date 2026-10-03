"""Accessories built on the bar a figure's hand grips (profile.pin_diameter).

Each is built standing up, its bar along z from z = 0, and returned as a list of
(name, Manifold, colour) so a multi-colour printer can do the shiny bits in their
own filament. The bar is a peg: the profile's xy_compensation comes off it, as off a stud.
"""
from __future__ import annotations

import numpy as np
from manifold3d import CrossSection, Manifold

from .figures import along_y, pin_radius
from .geom import cylinder
from .profiles import FDM_04, Profile


def bar(p: Profile = FDM_04, length: float = 16.0) -> Manifold:
    """A plain bar with chamfered ends, so it starts easily into a clip."""
    r, ch = pin_radius(p), 0.3
    return Manifold.batch_hull([cylinder(length, r - ch), cylinder(length - 2 * ch, r).translate([0, 0, ch])])


def star(r: float, thickness: float, points: int = 5) -> Manifold:
    """A flat star in the x-z plane, `thickness` along y, centred on the origin."""
    a = np.pi / 2 + np.arange(2 * points) * np.pi / points
    rr = np.where(np.arange(2 * points) % 2 == 0, r, r * 0.45)
    poly = CrossSection([np.column_stack([rr * np.cos(a), rr * np.sin(a)]).tolist()])
    return Manifold.extrude(poly, thickness).translate([0, 0, -thickness / 2]).rotate([90, 0, 0])


def wand(p: Profile = FDM_04, length: float = 18.0) -> list:
    """A wishing-star wand."""
    t = max(p.min_wall, 1.6)
    s = star(4.8, t).translate([0, 0, length + 4.0])
    return [("wand-bar", bar(p, length + 1.0) - s, "#e8e4dc"), ("wand-star", s, "#ffd21f")]


def mirror(p: Profile = FDM_04, length: float = 12.0) -> list:
    """A hand mirror: a handle, a round frame, and the glass set into its face."""
    r, t, z = 5.0, max(p.min_wall, 1.2) + 0.8, length + 4.6
    frame = along_y(-t / 2, t / 2, r, z=z) + bar(p, length + 0.6)
    glass = along_y(-t / 2 - 0.01, -t / 2 + 0.6, r - 1.0, z=z)
    return [("mirror-frame", frame - glass, "#c8a8ff"), ("mirror-glass", glass, "#d8dce4")]


def magnet(p: Profile = FDM_04, length: float = 10.0) -> list:
    """A horseshoe magnet held by its arch, tips down: red, with silver ends."""
    R, tube = 4.0, max(p.min_wall, 1.6)
    arch = Manifold.revolve(CrossSection.circle(tube, 32).translate([R, 0]), 64, 180)  # in x-z, arch up
    legs = [cylinder(R, tube).translate([sx * R, 0, -R]) for sx in (1, -1)]
    tips = [cylinder(2.4, tube + 0.05).translate([sx * R, 0, -R - 2.4]) for sx in (1, -1)]
    body = arch.rotate([90, 0, 0]) + legs[0] + legs[1]
    lift = R + 2.4  # tips on z = 0, the bar on top of the arch
    handle = bar(p, length).translate([0, 0, lift + R + tube - 0.6])
    return [("magnet", (body + handle.translate([0, 0, -lift])).translate([0, 0, lift]), "#e8323a"),
            ("magnet-tips", (tips[0] + tips[1]).translate([0, 0, lift]), "#d8dce4")]


def accessories(p: Profile = FDM_04) -> dict:
    """name -> list of (part name, Manifold, colour)."""
    return {"bar": [("bar", bar(p), "#e8e4dc")], "wand": wand(p), "mirror": mirror(p), "magnet": magnet(p)}
