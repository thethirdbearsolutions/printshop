"""Articulated figures: rigid bodies joined by printed joints, carved so they move without colliding.

A figure is a set of bodies (each a list of convex primitives) and the joints
between them. Every joint gets a mechanism at its anchor (mechanisms.py), and
then every body gives way, with the profile's joint clearance, to everything
that moves relative to it:

  * a parent's bulk yields to its children's mechanisms swept through their range;
  * a moving body (the joint's child and everything hanging from it) yields to all
    the parts that stay put, swept backwards through the same range; a ball joint's
    free twist turns that sweep all the way round the joint's axis.

Swept volumes are hulls of each primitive at neighbouring poses, so they are
continuous, not samples. Mechanism material is added after carving, so a socket
or knuckle is never eaten by its own clearance cut.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from manifold3d import Manifold, OpType

from . import mechanisms as mech
from .mechanisms import Mechanism, Prim, rotation
from .profiles import Profile


@dataclass
class Body:
    name: str
    prims: list  # Prims in mm, the body at rest


@dataclass
class Joint:
    name: str
    kind: str  # "ball" | "hinge" | "slide"
    parent: str
    child: str
    anchor: np.ndarray  # mm
    axis: np.ndarray  # hinge / slide axis (unit); unused by a ball
    out: np.ndarray  # unit vector from the parent into the child
    limits: tuple | None = None  # hinge (lo, hi) rad; slide (lo, hi) mm; ball (0, cone) rad; None = unlimited


class DoesNotFit(ValueError):
    """No printable mechanism fits at this joint at this scale."""


@dataclass
class Figure:
    solids: dict  # body name -> Manifold
    joints: list
    mechs: dict  # joint name -> Mechanism
    subtree: dict  # joint name -> names of the bodies that move with it
    profile: Profile
    raw: dict = field(default_factory=dict)  # body name -> uncarved Manifold (the simulated shape)


def union(parts) -> Manifold:
    parts = [p for p in parts if not p.is_empty()]
    return Manifold.batch_boolean(parts, OpType.Add) if parts else Manifold()


def solid_of(prims, segments: int = 48) -> Manifold:
    return union([p.solid(segments=segments) for p in prims])


def depth(m: Manifold, start, direction, reach: float = 1000.0, tol: float = 0.5) -> float:
    """How far `m` runs from `start` along `direction` (0 if it does not start within tol)."""
    d = np.asarray(direction, float) / np.linalg.norm(direction)
    a = np.asarray(start, float) - d * reach
    hits = m.ray_cast(a, np.asarray(start, float) + d * reach)
    ts = [float(np.dot(np.asarray(h.position) - start, d)) for h in hits]
    for t0, t1 in zip(ts[0::2], ts[1::2]):
        if t0 <= tol and t1 > 0:
            return t1
    return 0.0


def _bound(p: Prim) -> float:
    s = np.asarray(p.size, float)
    if p.kind == "box":
        return float(np.linalg.norm(s) / 2)
    return float(s[0] if p.kind == "sphere" else np.hypot(s[0], s[1] / 2))


def _on_axis(p: Prim, anchor, axis, tol: float = 1e-6) -> bool:
    """Is the primitive unchanged by spinning it about the line (anchor, axis)?"""
    r = p.pos - anchor
    centred = np.linalg.norm(r - (r @ axis) * axis) < tol
    return p.kind == "sphere" and centred or p.kind == "cylinder" and centred and abs(abs(p.rot[:, 2] @ axis) - 1) < tol


def _unmoved(p: Prim, groups, tol: float = 1e-6) -> bool:
    """Does every pose leave the primitive where it was (a sphere at the pivot, a pin on its axis)?"""
    for g in groups:
        for T in g:
            q = p.moved(T)
            if np.linalg.norm(q.pos - p.pos) > tol or p.kind == "box":
                return False
            if p.kind == "cylinder" and abs(abs(q.rot[:, 2] @ p.rot[:, 2]) - 1) > tol:
                return False
    return True


def _spin_envelope(m: Manifold, anchor, axis, segments: int = 32) -> Manifold:
    """The convex cylinder round (anchor, axis) that holds `m` however far it spins."""
    v = m.to_mesh().vert_properties[:, :3] - anchor
    t = v @ axis
    radius = float(np.linalg.norm(v - np.outer(t, axis), axis=1).max())
    c = Prim("cylinder", (radius, float(t.max() - t.min())), mech.frame(anchor, z=axis)[:3, :3],
             anchor + axis * (t.max() + t.min()) / 2)
    return c.solid(segments=segments, outer=True)


#: mm a swept volume may be simplified by (it is grown by more than this beyond the clearance).
SIMPLIFY = 0.01


def sweep(prims, groups, grow: float, inverse: bool = False, twist=None, near=None, segments: int = 32) -> Manifold:
    """Union of each primitive hulled across each group of poses (continuous between neighbours).
    inverse=True moves by the inverse poses: what a moving part sees of the parts that stay.
    twist=(anchor, axis): the joint also spins freely about that line (a ball joint), so anything
    not round about it is replaced by the cylinder it fills when spun. near=(centre, radius) drops
    primitives that cannot reach that ball."""
    if near is not None:
        prims = [p for p in prims if np.linalg.norm(p.pos - near[0]) - _bound(p) - grow < near[1]]
    hulls = []
    for p in prims:
        if _unmoved(p, groups):  # e.g. a socket's sphere on its own pivot: one solid, not a hundred
            hulls.append(p.solid(grow, segments, outer=True))
            continue
        spins = twist is not None and not _on_axis(p, *twist)
        if spins and inverse and np.linalg.norm(p.pos - twist[0]) < 1e-6 and p.kind == "sphere":
            spins = False  # a sphere on the pivot is unchanged by any rotation about it
        if spins and not inverse:  # spin first, then swing
            base = _spin_envelope(p.solid(grow, segments, outer=True), *twist, segments)
            hulls += [Manifold.batch_hull([base.transform(T[:3]) for T in g]) for g in groups]
            continue
        for g in groups:
            Ts = [np.linalg.inv(T) for T in g] if inverse else g
            h = Manifold.batch_hull([p.moved(T).solid(grow, segments, outer=True) for T in Ts])
            hulls.append(_spin_envelope(h, *twist, segments) if spins else h)  # swing back, then spin
    return union(hulls).simplify(SIMPLIFY)


def nearest_prim(prims, point) -> Prim:
    dot = Manifold.sphere(0.01, 8).translate(point)
    return min(prims, key=lambda p: dot.min_gap(p.solid(segments=32), 1e3))


def mechanism_for(j: Joint, parent: Body, child: Body, profile: Profile) -> Mechanism:
    """The joint's mechanism, sized to the parent part it sits on (a housing no thicker than that
    part) and to how deep the child runs along `out` (where the neck or web must land)."""
    dp = nearest_prim(parent.prims, j.anchor).thickness() / 2
    by_child, child = child, solid_of(child.prims)
    dc = depth(child, j.anchor, j.out)
    if j.kind == "ball":
        cone = None if j.limits is None else np.degrees(j.limits[1])
        m = mech.ball(j.anchor, j.out, dp, dc, profile, cone)
    elif j.kind == "hinge":
        half = min(dp, nearest_prim(by_child.prims, j.anchor).thickness() / 2)  # no longer than the parts are thick
        m = mech.hinge(j.anchor, j.axis, j.out, dp, dc, half, profile, j.limits)
    elif j.kind == "slide":
        m = mech.slide(j.anchor, j.axis, j.out, dp, dc, profile, j.limits or (-5.0, 5.0))
    else:
        raise ValueError(f"unknown joint kind {j.kind!r}")
    if m is None:
        raise DoesNotFit(f"{j.name}: no {j.kind} fits (parent part half-thickness {dp:.1f} mm, child depth {dc:.1f} mm)")
    m.info.update(parent_half_thickness_mm=round(dp, 2), child_depth_mm=round(dc, 2))
    return m


def subtrees(bodies, joints) -> dict:
    kids = {}
    for j in joints:
        kids.setdefault(j.parent, []).append(j.child)

    def below(b):
        return [b] + [x for k in kids.get(b, []) for x in below(k)]

    return {j.name: below(j.child) for j in joints}


def articulate(bodies, joints, profile: Profile) -> Figure:
    """Mechanisms at every joint, then the carving rules: bulk always gives way to mechanisms, a
    parent's mechanism to its own child's cut (socket, slot, channel) and to its other children,
    and where bulk meets bulk the part that stays gives way to the part that moves."""
    by = {b.name: b for b in bodies}
    raw = {b.name: solid_of(b.prims) for b in bodies}
    mechs = {j.name: mechanism_for(j, by[j.parent], by[j.child], profile) for j in joints}
    sub = subtrees(bodies, joints)
    c = profile.joint_clearance
    menv = {b: [] for b in by}  # mechanism envelopes each body carries
    for j in joints:
        menv[j.parent] += mechs[j.name].parent_env
        menv[j.child] += mechs[j.name].child_env
    bulk_cuts = {b: [] for b in by}
    mech_cuts = {j.name: [] for j in joints}
    for j in joints:
        m, moving = mechs[j.name], sub[j.name]
        lo, hi = np.array(union([raw[b] for b in moving]).bounding_box()).reshape(2, 3)
        reach = float(max(np.linalg.norm(lo - j.anchor), np.linalg.norm(hi - j.anchor)))
        g = c + reach * (1 - np.cos(np.radians(8) / 2)) + 0.02  # clearance + the most a hull chord cuts inside an arc
        twist = (j.anchor, j.out) if m.twist else None
        near = (j.anchor, reach + 2 * g)
        move_all = [p for b in moving for p in by[b].prims + menv[b]]
        fwd = sweep(move_all, m.groups, g, twist=twist)
        for b in by:
            if b not in moving:
                bulk_cuts[b].append(fwd)
        static_mech = [p for b in by if b not in moving for p in menv[b]]
        inv = sweep(static_mech, m.groups, g, inverse=True, twist=twist, near=near)
        for b in moving:
            bulk_cuts[b].append(inv)
        for k in joints:  # mechanisms that stay give way to everything of this joint's that moves
            if k.parent not in moving:
                own = sweep(m.child_cut, m.groups, g, twist=twist) if k is j else fwd
                mech_cuts[k.name].append(own)
    solids = {}
    for name in by:
        s = raw[name] - union(bulk_cuts[name])
        for j in joints:
            if j.parent == name:
                s += mechs[j.name].parent_solid - union(mech_cuts[j.name])
            if j.child == name:
                s += mechs[j.name].child_solid
        solids[name] = s
    return Figure(solids, list(joints), mechs, sub, profile, raw)
