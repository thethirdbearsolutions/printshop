"""Brick-system figures: parts that go together with studs, pins and clips, every fit from the profile.

    head   a socket underneath presses onto the torso's neck stud; a stud on top takes a hat
    torso  a socket underneath onto the hips' stud (it turns at the waist), a hole in each
           shoulder, a neck stud
    arm    a shoulder pin, and a hand: a C clip that grips the bar (profile.pin_diameter)
    hips   a stud on top; underneath, a keel between the legs carrying the hip pin
    leg    a hole in its inner face turns on the hip pin; a stud socket in the foot. The two
           feet are one pitch apart, so the figure stands on a plate; another socket in the
           back of each leg lets it sit on studs with its legs swung forward

The shapes are printshop's own. Sizes below are proportions; every fit (stud, socket,
pin, hole, clip, clearance) comes from the profile, so a calibrated profile retunes them all.
Parts are built assembled, at z = 0 on the feet, facing -y.
"""
from __future__ import annotations

import numpy as np
from manifold3d import Manifold

from .geom import box, cylinder, sphere
from .profiles import FDM_04, Profile

LEG_H = 12.0  # foot to the top of the leg
DEPTH = 7.2  # front to back, legs and hips
TORSO_H, TORSO_W, TORSO_ROUND = 11.0, 14.4, 2.4  # a rounded barrel, straight-sided
HEAD_D, HEAD_H = 9.6, 8.8
ARM_R, ARM_LEN = 2.0, 10.0
PIN_IN = 3.0  # how far a pin goes into its hole
SEAT_Z = 5.3  # height of the stud socket in the back of each leg: legs swung forward, the figure sits on studs
CLIP_LEN = 3.2  # along the bar


def stud(p: Profile) -> Manifold:
    return cylinder(p.stud_height, (p.stud_diameter - p.xy_compensation) / 2)


def socket(p: Profile, depth: float) -> Manifold:
    """A hole a stud presses into (a brick's tube inside: the same diameter as the stud)."""
    return cylinder(depth, (p.stud_diameter + p.socket_delta + p.xy_compensation) / 2).translate([0, 0, -0.01])


def pin_radius(p: Profile) -> float:
    return (p.pin_diameter - p.xy_compensation) / 2


def hole_radius(p: Profile) -> float:
    return (p.pin_diameter + p.pin_fit + p.xy_compensation) / 2


def clip_bore(p: Profile) -> float:
    return (p.pin_diameter + p.clip_fit + p.xy_compensation) / 2


def along_x(x0: float, x1: float, r: float, y: float = 0.0, z: float = 0.0) -> Manifold:
    return cylinder(x1 - x0, r).rotate([0, 90, 0]).translate([x0, y, z])


def along_y(y0: float, y1: float, r: float, x: float = 0.0, z: float = 0.0) -> Manifold:
    return cylinder(y1 - y0, r).rotate([-90, 0, 0]).translate([x, y0, z])


def span(x0, x1, y0, y1, z0, z1) -> Manifold:
    return box([x1 - x0, y1 - y0, z1 - z0], center=False).translate([x0, y0, z0])


class Layout:
    """Where everything sits in the assembled figure (mm), from the profile."""

    def __init__(self, p: Profile):
        self.p = p
        self.c = p.joint_clearance
        self.keel = p.min_wall  # half-width of the keel between the legs
        self.outer = p.pitch - p.side_gap  # outside face of each leg
        self.hip_axis = LEG_H - DEPTH / 2  # the leg's rounded top turns about this
        self.keel_r = pin_radius(p) + p.min_wall
        self.hips = LEG_H + self.c  # underside of the hips
        self.waist = self.hips + p.plate_height  # top of the hips, bottom of the torso
        self.neck = self.waist + TORSO_H
        self.shoulder = self.neck - 2.6
        self.arm_x = self.outer + self.c  # an arm's inner face: clear of the torso's widest part

    def torso_half_width(self, z: float = 0.0) -> float:
        return TORSO_W / 2


def leg(p: Profile = FDM_04, side: int = 1) -> Manifold:
    """One leg (side +1 is the figure's left, at +x; -1 the right)."""
    L = Layout(p)
    inner = 0.2  # the legs nearly touch below the keel
    m = span(inner, L.outer, -DEPTH / 2, DEPTH / 2, 0, L.hip_axis) + along_x(inner, L.outer, DEPTH / 2, z=L.hip_axis)
    notch_floor = L.hip_axis - L.keel_r - L.c
    m -= span(inner - 1, L.keel + L.c, -DEPTH, DEPTH, notch_floor, LEG_H + 1)
    m -= along_x(L.keel + L.c - 0.01, L.keel + L.c + PIN_IN + 0.3, hole_radius(p), z=L.hip_axis)
    m -= socket(p, p.stud_height + 0.3).translate([p.pitch / 2, 0, 0])
    seat = socket(p, p.stud_height + 0.1).rotate([90, 0, 0])  # opens towards +y, the back
    m -= seat.translate([p.pitch / 2, DEPTH / 2, SEAT_Z])
    return m if side > 0 else m.mirror([1, 0, 0])


def hips(p: Profile = FDM_04) -> Manifold:
    L = Layout(p)
    m = span(-L.outer, L.outer, -DEPTH / 2, DEPTH / 2, L.hips, L.waist)
    m += span(-L.keel, L.keel, -L.keel_r, L.keel_r, L.hip_axis, L.hips + 0.01)
    m += along_x(-L.keel, L.keel, L.keel_r, z=L.hip_axis)
    reach = L.keel + L.c + PIN_IN
    m += along_x(-reach, reach, pin_radius(p), z=L.hip_axis)
    return m + stud(p).translate([0, 0, L.waist - 0.01])


def torso(p: Profile = FDM_04) -> Manifold:
    """A barrel with rounded edges: a socket under it, a hole in each side for the arms, a neck stud."""
    L = Layout(p)
    w, d, r = TORSO_W / 2 - TORSO_ROUND, DEPTH / 2 - TORSO_ROUND, TORSO_ROUND
    posts = [cylinder(TORSO_H - 2 * r, r).translate([sx * w, sy * d, L.waist + r]) for sx in (1, -1) for sy in (1, -1)]
    balls = [sphere(r, 32).translate([sx * w, sy * d, z]) for sx in (1, -1) for sy in (1, -1)
             for z in (L.waist + r, L.neck - r)]
    m = Manifold.batch_hull(posts + balls)
    m = m.trim_by_plane([0, 0, 1], L.waist + 0.6) + span(-w, w, -d, d, L.waist, L.waist + r)  # flat seat
    m -= socket(p, p.stud_height + 0.3).translate([0, 0, L.waist])
    x = TORSO_W / 2
    hole = along_x(x - PIN_IN - 0.3, x + 1, hole_radius(p), z=L.shoulder)
    m -= hole + hole.mirror([1, 0, 0])
    return m + stud(p).translate([0, 0, L.neck - 0.01])


def hand(p: Profile = FDM_04) -> tuple[Manifold, float]:
    """A C clip round the y axis at the origin, mouth down. Returns (clip, outer radius)."""
    ri = clip_bore(p)
    ro = ri + max(p.min_wall, 1.2)
    ring = along_y(-CLIP_LEN / 2, CLIP_LEN / 2, ro) - along_y(-CLIP_LEN, CLIP_LEN, ri)
    mouth = p.clip_opening * p.pin_diameter + p.xy_compensation
    return ring - span(-mouth / 2, mouth / 2, -CLIP_LEN, CLIP_LEN, -ro - 1, 0), ro


def arm(p: Profile = FDM_04, side: int = 1) -> Manifold:
    L = Layout(p)
    clip, ro = hand(p)
    x = L.arm_x + max(ARM_R, ro) + 0.4  # the arm's centre line, the hand clear of the legs
    m = along_x(L.arm_x, x + ARM_R + 0.4, ARM_R + 0.6, z=L.shoulder)  # shoulder
    m += sphere(ARM_R + 0.6, 32).translate([x + ARM_R + 0.4, 0, L.shoulder])
    m += along_x(L.torso_half_width(L.shoulder) - PIN_IN, L.arm_x + 0.5, pin_radius(p), z=L.shoulder)
    wrist = L.shoulder - ARM_LEN
    m += cylinder(ARM_LEN, ARM_R).translate([x, 0, wrist])
    m += clip.translate([x, 0, wrist - ro + 0.6])
    return m if side > 0 else m.mirror([1, 0, 0])


def hand_centre(p: Profile = FDM_04, side: int = 1) -> np.ndarray:
    """Where the bar's axis runs through a hand (along y)."""
    L = Layout(p)
    _, ro = hand(p)
    return np.array([side * (L.arm_x + max(ARM_R, ro) + 0.4), 0.0, L.shoulder - ARM_LEN - ro + 0.6])


def head(p: Profile = FDM_04) -> Manifold:
    """A dome, like the end of a wrap: socket underneath, a face, a stud on top for a hat."""
    L = Layout(p)
    r = HEAD_D / 2
    m = cylinder(HEAD_H - r, r).translate([0, 0, L.neck]) + sphere(r, 64).translate([0, 0, L.neck + HEAD_H - r])
    m = m.trim_by_plane([0, 0, -1], -(L.neck + HEAD_H - 0.8)).trim_by_plane([0, 0, 1], L.neck)  # flat crown, flat base
    m -= socket(p, p.stud_height + 0.3).translate([0, 0, L.neck])
    for s in (1, -1):  # eyes
        m -= sphere(0.75, 24).translate([s * 1.9, -r, L.neck + 4.6])
    for a in np.radians(np.linspace(205, 335, 6)):  # a smile of little dimples
        m -= sphere(0.45, 16).translate([1.9 * np.cos(a), -r, L.neck + 3.2 + 1.9 * np.sin(a)])
    return m + stud(p).translate([0, 0, L.neck + HEAD_H - 0.81])


def figure(p: Profile = FDM_04) -> dict:
    """All the parts, assembled: name -> Manifold."""
    return {"head": head(p), "torso": torso(p), "arm-left": arm(p, 1), "arm-right": arm(p, -1),
            "hips": hips(p), "leg-left": leg(p, 1), "leg-right": leg(p, -1)}


def rotate_about_x(m: Manifold, deg: float, z: float) -> Manifold:
    """Swing a part about an x-direction axis at height z (a leg on its hip pin, an arm at the shoulder)."""
    return m.translate([0, 0, -z]).rotate([deg, 0, 0]).translate([0, 0, z])


def plate_layout(groups: dict, gap: float = 4.0, orient: bool = True) -> list:
    """Lay each group (name -> list of (part, Manifold, colour)) side by side along x on z = 0, nothing
    trimmed: turned the least-support way up, or (orient=False) as given. Returns (part, Manifold, colour)."""
    from .orient import lay_flat

    out, x = [], 0.0
    for parts in groups.values():
        if orient:
            laid, _ = lay_flat({n: m for n, m, _ in parts}, flat=0.0)
        else:
            z0 = min(m.bounding_box()[2] for _, m, _ in parts)
            laid = {n: m.translate([0, 0, -z0]) for n, m, _ in parts}
        lo = np.min([np.array(m.bounding_box())[:3] for m in laid.values()], axis=0)
        hi = np.max([np.array(m.bounding_box())[3:] for m in laid.values()], axis=0)
        for n, _, c in parts:
            out.append((n, laid[n].translate([x - lo[0], -(lo[1] + hi[1]) / 2, 0]), c))
        x += hi[0] - lo[0] + gap
    return out
