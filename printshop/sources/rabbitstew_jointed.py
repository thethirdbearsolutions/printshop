"""Jointed rabbitstew champions: every MuJoCo joint becomes a printed joint, no plinth.

The body comes from rabbitstew's ``build_model()`` at rest (every joint at zero).
Parts welded together (rabbitstew's FIXED links) become one printed body, with a
strut between their centres so parts that only touch are joined. Each moving
joint's anchor, axis, type and range come from MuJoCo (``jnt_type``, ``jnt_range``;
``xanchor``, ``xaxis`` after ``mj_forward``):

    hinge  pin hinge with hard stops at the joint range
    ball   captured socket; the simulation's ball joints are unlimited, so the cone is
           chosen (mechanisms.ball) and recorded
    slide  captive rail with stops at the range (5 mm either way if unlimited)

The scale starts where the largest housing (a 12 mm ball socket) is as thick as the
thinnest part a joint touches, and grows until every joint's mechanism fits.
"""
from __future__ import annotations

import numpy as np

from ..articulate import Body, DoesNotFit, Figure, Joint, articulate
from ..mechanisms import Prim
from ..profiles import FDM_04, Profile
from .rabbitstew import Champion, _require

JOINT_KINDS = {1: "ball", 2: "slide", 3: "hinge"}  # mjtJoint; 0 is the root's free joint
HOUSING_MM = 12.0  # the ball socket the scale is first sized for


def rest_model(ch: Champion):
    """(model, data, RobotIndex) for the champion alone at rest: joints at zero, root yaw zero."""
    _require()
    from rabbitstew.synthesis import synthesize
    from rabbitstew.world import Spawn, build_model

    ph = synthesize(ch.genotype, ch.config.synthesis)
    model, data, idx = build_model([ph], [Spawn()], ch.config.world)
    return model, data, idx[0]


def _prim(model, data, g: int, mm: float, floor: float) -> Prim:
    rot, pos, s = data.geom_xmat[g].reshape(3, 3).copy(), data.geom_xpos[g] * mm, model.geom_size[g] * mm
    t = int(model.geom_type[g])
    if t == 6:
        return Prim("box", tuple(max(2 * v, floor) for v in s), rot, pos)
    if t == 2:
        return Prim("sphere", (max(s[0], floor / 2),), rot, pos)
    if t == 5:
        return Prim("cylinder", (max(s[0], floor / 2), max(2 * s[1], floor)), rot, pos)
    raise NotImplementedError(f"geom type {t} is not a rabbitstew unit")


def strut_prim(p, q, radius: float) -> Prim:
    v = np.asarray(q, float) - np.asarray(p, float)
    z = v / np.linalg.norm(v)
    x = np.cross(z, [0, 0, 1] if abs(z[2]) < 0.9 else [1, 0, 0])
    x /= np.linalg.norm(x)
    return Prim("cylinder", (radius, float(np.linalg.norm(v))), np.column_stack([x, np.cross(z, x), z]), (p + q) / 2)


def thinnest_jointed_part(model, idx) -> float:
    """Thinnest part (metres) on either side of a moving joint: a box's least side, a round part's diameter."""
    part_of = {b: k for k, b in enumerate(idx.bodies)}
    out = np.inf
    for j in range(model.njnt):
        if int(model.jnt_type[j]) == 0:
            continue
        b = int(model.jnt_bodyid[j])
        for body in (b, int(model.body_parentid[b])):
            g = idx.geoms[part_of[body]]
            s = model.geom_size[g]
            out = min(out, 2 * (s.min() if int(model.geom_type[g]) == 6 else s[0]))
    return float(out)


def bodies_and_joints(ch: Champion, mm: float, profile: Profile = FDM_04):
    """The champion at rest in mm: (bodies, joints), one Body per rigid group of parts."""
    model, data, idx = rest_model(ch)
    group = {}
    for b in idx.bodies:  # a body with no joint is welded to its parent
        root = b
        while int(model.body_jntnum[root]) == 0 and int(model.body_parentid[root]) != 0:
            root = int(model.body_parentid[root])
        group[b] = f"b{root}"
    floor = profile.min_wall
    prims = {}
    for k, (b, g) in enumerate(zip(idx.bodies, idx.geoms)):
        prims.setdefault(group[b], []).append(_prim(model, data, g, mm, floor))
        parent = int(model.body_parentid[b])
        if int(model.body_jntnum[b]) == 0 and parent != 0:  # a weld: join the two parts' centres
            pg = idx.geoms[idx.bodies.index(parent)]
            p, q = data.geom_xpos[pg] * mm, data.geom_xpos[g] * mm
            thin = min(prims[group[b]][-1].thickness(), _prim(model, data, pg, mm, floor).thickness())
            if np.linalg.norm(q - p) > 1e-6:
                prims[group[b]].append(strut_prim(p, q, max(profile.min_wall, 0.2 * thin)))
    joints = []
    for j in range(model.njnt):
        kind = JOINT_KINDS.get(int(model.jnt_type[j]))
        if kind is None:
            continue
        b = int(model.jnt_bodyid[j])
        anchor, axis = data.xanchor[j] * mm, data.xaxis[j].copy()
        out = data.geom_xpos[idx.geoms[idx.bodies.index(b)]] * mm - anchor
        if kind != "ball":
            out -= (out @ axis) * axis
        r = model.jnt_range[j]
        limits = None
        if model.jnt_limited[j]:
            limits = (0.0, float(r[1])) if kind == "ball" else (float(r[0]) * (mm if kind == "slide" else 1), float(r[1]) * (mm if kind == "slide" else 1))
        joints.append(Joint(model.joint(j).name, kind, group[int(model.body_parentid[b])], group[b], anchor, axis,
                            out / np.linalg.norm(out), limits))
    bodies = [Body(n, ps) for n, ps in prims.items()]
    return bodies, joints


def jointed(ch: Champion, profile: Profile = FDM_04, mm: float | None = None, grow: float = 1.06, tries: int = 15):
    """The articulated champion. Returns (Figure, info); mm (per model metre) is found if not given."""
    model, _, idx = rest_model(ch)
    thin = thinnest_jointed_part(model, idx)
    scale = HOUSING_MM / thin if mm is None else mm
    for _ in range(tries):
        bodies, joints = bodies_and_joints(ch, scale, profile)
        try:
            fig = articulate(bodies, joints, profile)
            break
        except DoesNotFit as e:
            if mm is not None:
                raise
            last, scale = str(e), scale * grow
    else:
        raise DoesNotFit(f"no scale up to {scale:.0f} mm/m fits: {last}")
    info = {"name": ch.name, "mm_per_model_m": round(scale, 2), "thinnest_jointed_part_m": round(thin, 4),
            "joints": {j.name: dict(fig.mechs[j.name].info, kind=j.kind,
                                    sim_range=None if j.limits is None else [round(float(v), 4) for v in j.limits])
                       for j in joints}}
    return fig, info
