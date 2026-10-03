"""Printed joint mechanisms placed at an arbitrary anchor and axis, for articulated figures.

Each mechanism is built in a joint frame (origin at the anchor, `out` pointing from
the parent into the child) and returned as material for the parent and the child,
the convex primitives that stand for them when other parts are carved, and the
child's motions relative to the parent. ``articulate.py`` carves the bodies with
those motions, so the clearance, the socket opening and the hinge's stop slot all
come from sweeping the moving part through its range.

    ball   a captured socket on the parent, ball and neck on the child; the opening is the cone limit
    hinge  pin and end knuckles on the parent, a bored middle knuckle on a web on the child;
           when the joint is limited a ring round the middle knuckle has a slot the web stops against
    slide  a closed channel on the parent, a T key on the child; the channel ends are the stops
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from manifold3d import Manifold

from .geom import box, cylinder, sphere
from .profiles import Profile


@dataclass
class Prim:
    """A convex primitive in mm: box (full extents), sphere (r,), cylinder (r, h) centred along local z."""

    kind: str
    size: tuple
    rot: np.ndarray = field(default_factory=lambda: np.eye(3))
    pos: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def solid(self, grow: float = 0.0, segments: int = 48, outer: bool = False) -> Manifold:
        """The primitive grown by `grow`. outer=True circumscribes round faces, so a coarse
        polygon still contains the true surface (what carving needs)."""
        k = 1.0 / np.cos(np.pi / segments) if outer else 1.0
        if self.kind == "box":
            m = box([s + 2 * grow for s in self.size])
        elif self.kind == "sphere":
            m = sphere((self.size[0] + grow) * k * k, segments)  # latitude and longitude both facet
        else:
            m = cylinder(self.size[1] + 2 * grow, (self.size[0] + grow) * k, center=True, segments=segments)
        return m.transform(np.hstack([self.rot, np.asarray(self.pos, dtype=float).reshape(3, 1)]))

    def moved(self, T: np.ndarray) -> "Prim":
        """This primitive after the rigid motion T (4x4)."""
        return Prim(self.kind, self.size, T[:3, :3] @ self.rot, T[:3, :3] @ self.pos + T[:3, 3])

    def thickness(self) -> float:
        return min(self.size) if self.kind == "box" else 2 * self.size[0]


@dataclass
class Mechanism:
    parent_solid: Manifold
    parent_env: list  # Prims enclosing parent_solid
    child_solid: Manifold
    child_env: list  # Prims enclosing child_solid
    child_cut: list  # Prims of the child that carve the parent's own mechanism (socket, slot, channel)
    groups: list  # lists of 4x4 child-relative-to-parent motions; each list is hulled into one swept piece
    twist: bool = False  # free spin about `out` on top of the groups (a ball joint's twist)
    info: dict = field(default_factory=dict)


def frame(anchor, x=None, z=None) -> np.ndarray:
    """4x4 joint frame at anchor with local z along `z` and x along `x` (made orthogonal)."""
    z = np.asarray(z, float) / np.linalg.norm(z)
    x = np.asarray(x if x is not None else ([1, 0, 0] if abs(z[0]) < 0.9 else [0, 1, 0]), float)
    x = x - (x @ z) * z
    x /= np.linalg.norm(x)
    F = np.eye(4)
    F[:3, :3] = np.column_stack([x, np.cross(z, x), z])
    F[:3, 3] = anchor
    return F


def rotation(axis, angle: float, about) -> np.ndarray:
    """4x4 rotation by `angle` about the line through `about` along `axis`."""
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, np.asarray(about) - R @ np.asarray(about)
    return T


def _place(F, prims):
    return [p.moved(F) for p in prims]


def _union(prims, segments=64):
    out = prims[0].solid(segments=segments)
    for p in prims[1:]:
        out = out + p.solid(segments=segments)
    return out


def steps(lo: float, hi: float, step: float) -> np.ndarray:
    return np.linspace(lo, hi, max(2, int(np.ceil((hi - lo) / step)) + 1))


def ball(anchor, out, depth_parent, depth_child, profile: Profile, cone_deg=None,
         r_max: float = 4.5, neck_ratio: float = 0.45, step_deg: float = 7.5):
    """A captured ball joint, or None if no printable ball fits the given depths (mm)."""
    c, w = profile.joint_clearance, max(profile.min_wall, 1.6)
    keep = profile.min_wall  # child material left beyond the pocket for the neck to land in
    r_min = 2 * profile.min_wall
    r = min(r_max, depth_child - 2 * c - w - keep, depth_parent - c - w)
    if r < r_min:
        return None
    rn = max(neck_ratio * r, profile.min_wall)
    # The cavity's opening must stay narrower than the ball: (r + c) sin(opening) < r - c.
    opening = np.degrees(np.arcsin((r - c) / (r + c)))
    cone_max = opening - np.degrees(np.arcsin((rn + c) / (r + c))) - 3.0
    cone = min(30.0 if cone_deg is None else cone_deg, cone_max)
    shell = r + c + w
    F = frame(anchor, z=out)
    neck_len = depth_child - keep / 2
    ball_p = Prim("sphere", (r,))
    neck_p = Prim("cylinder", (rn, neck_len), pos=np.array([0, 0, neck_len / 2]))
    shell_p = Prim("sphere", (shell,))
    child = _place(F, [ball_p, neck_p])
    zaxis, x, y = F[:3, 2], F[:3, 0], F[:3, 1]
    rings = steps(0, np.radians(cone), np.radians(step_deg))
    n_az = max(8, int(np.ceil(2 * np.pi * np.sin(np.radians(cone)) / np.radians(step_deg))))
    az = np.linspace(0, 2 * np.pi, n_az, endpoint=False)

    def swing(t, phi):
        return rotation(np.cos(phi) * x + np.sin(phi) * y, t, anchor)

    groups = []
    for i in range(len(rings) - 1):
        for j in range(n_az):
            a, b = az[j], az[(j + 1) % n_az]
            groups.append([swing(rings[i], a), swing(rings[i], b), swing(rings[i + 1], a), swing(rings[i + 1], b)])
    info = {"type": "ball", "ball_radius": round(r, 2), "neck_radius": round(rn, 2), "housing_mm": round(2 * shell, 2),
            "cone_deg": round(float(cone), 1), "cone_max_deg": round(float(cone_max), 1)}
    return Mechanism(_union(_place(F, [shell_p])), _place(F, [shell_p]), _union(child), child, child, groups,
                     twist=True, info=info)


def hinge(anchor, axis, out, depth_parent, depth_child, half_length, profile: Profile, limits=None,
          r_max: float = 2.0, step_deg: float = 4.0):
    """A pin hinge along `axis`, or None if none fits. limits: (lo, hi) radians, or None for free spin."""
    c, w = profile.joint_clearance, max(profile.min_wall, 1.2)
    keep, seg_min = profile.min_wall, 2 * profile.min_wall
    ring = 0.0 if limits is None else c + w
    rp = min(r_max, depth_child - 2 * c - w - ring - keep, depth_parent - c - w - ring)
    length = min(2 * half_length, 15.0)
    if rp < profile.min_wall or length < 3 * seg_min + 2 * c:
        return None
    rk = rp + c + w  # knuckle radius
    rr = rk + ring  # outer radius of the whole hinge
    mid = length / 3 - c  # middle (child) knuckle
    F = frame(anchor, x=out, z=axis)  # local z = hinge axis, local x = out
    reach = depth_child - keep / 2
    web_w = max(2 * profile.min_wall, rk)
    knuckle = Prim("cylinder", (rk, mid))
    web = Prim("box", (reach - rp, web_w, mid), pos=np.array([(reach + rp) / 2, 0, 0]))
    child_solid = _union(_place(F, [knuckle, web])) - Prim("cylinder", (rp + c, length + 2)).moved(F).solid(outer=True)
    body = Prim("cylinder", (rr, length))
    parent_solid = body.moved(F).solid() - Prim("cylinder", (rk + c, mid + 2 * c)).moved(F).solid(outer=True)
    parent_solid += Prim("cylinder", (rp, length)).moved(F).solid()
    lo, hi = (-np.pi, np.pi) if limits is None else limits
    angles = steps(lo, hi, np.radians(step_deg))
    groups = [[rotation(axis, a, anchor), rotation(axis, b, anchor)] for a, b in zip(angles[:-1], angles[1:])]
    info = {"type": "hinge", "pin_radius": round(rp, 2), "knuckle_radius": round(rk, 2), "housing_mm": round(2 * rr, 2),
            "length_mm": round(length, 2), "stops_deg": None if limits is None else [round(np.degrees(v), 1) for v in limits]}
    return Mechanism(parent_solid, [body.moved(F)], child_solid, _place(F, [knuckle, web]), _place(F, [web]),
                     groups, info=info)


def slide(anchor, axis, out, depth_parent, depth_child, profile: Profile, limits=(-5.0, 5.0), step: float = 1.0):
    """A captive T rail along `axis`, travel `limits` (mm), or None if it does not fit."""
    c, w, keep = profile.joint_clearance, max(profile.min_wall, 1.2), profile.min_wall
    neck_w = 2 * profile.min_wall
    head_w, head_h, key_l = neck_w + 2 * w, w, max(3 * neck_w, 6.0)
    depth = w + c + head_h + c + w  # housing below the anchor
    if 2 * depth_parent < depth or depth_child < c + keep + w:
        return None
    lo, hi = limits
    F = frame(anchor, x=axis, z=out)  # local x = rail, local z = out
    top = -(w + c)  # underside of the lip the head is held by
    head = Prim("box", (key_l, head_w, head_h), pos=np.array([0, 0, top - head_h / 2]))
    reach = depth_child - keep / 2
    neck = Prim("box", (key_l, neck_w, reach - top), pos=np.array([0, 0, (reach + top) / 2]))
    hl = (hi - lo) + key_l + 2 * (c + w)
    housing = Prim("box", (hl, head_w + 2 * (c + w), depth), pos=np.array([(lo + hi) / 2, 0, -depth / 2]))
    child = _place(F, [head, neck])
    xs = steps(lo, hi, step)
    ax = F[:3, 0]

    def shift(s):
        T = np.eye(4)
        T[:3, 3] = s * ax
        return T

    groups = [[shift(a), shift(b)] for a, b in zip(xs[:-1], xs[1:])]
    info = {"type": "slide", "travel_mm": [round(lo, 2), round(hi, 2)], "housing_mm": round(depth, 2)}
    h = housing.moved(F)
    return Mechanism(h.solid(), [h], _union(child), child, child, groups, info=info)
