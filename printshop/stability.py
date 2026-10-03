"""Does a posed figure stay up? A MuJoCo drop test, checked against the static tip angle.

A posed figure is taken as one rigid body (a print's joints are stiff enough to hold
a pose). Its mass, centre of mass and inertia come from the mesh itself (solid PLA);
MuJoCo collides with the convex hull, which is exact for resting on a flat floor,
since only the hull can touch it. Each trial drops the figure from `height` mm with a
random tilt (and optionally a sideways shove) and lets it settle; it stayed up if it
ends back on its own base.

The static tip angle is how far the figure can lean before its centre of mass passes
the edge of its footprint: tilted less, it rights itself; more, it falls.
"""
from __future__ import annotations

import numpy as np
from manifold3d import Manifold

from .checks import _hull_2d
from .mechanisms import rotation

DENSITY = 1240.0  # kg/m^3, PLA
UPRIGHT_DEG = 5.0  # a figure that ends tilted less than this is back on its base
STILL_S = 0.25  # s without moving (every speed under 1 cm/s or 0.01 rad/s) that counts as at rest


def mass_properties(m: Manifold, density: float = DENSITY):
    """(mass kg, centre of mass m, inertia about the centre kg m^2) of a closed mesh in mm."""
    mesh = m.to_mesh()
    v = mesh.vert_properties[:, :3].astype(float) / 1000.0
    t = np.asarray(mesh.tri_verts)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    vol = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
    V = vol.sum()
    com = ((a + b + c) / 4.0 * vol[:, None]).sum(0) / V
    # Second moments of each tetrahedron (origin, a, b, c): sum over its vertices and their pairwise sums.
    P = np.zeros((3, 3))
    for x in (a, b, c):
        P += np.einsum("i,ij,ik->jk", vol, x, x)
    s = a + b + c
    P += np.einsum("i,ij,ik->jk", vol, s, s)
    P /= 20.0
    P -= V * np.outer(com, com)
    inertia = (np.trace(P) * np.eye(3) - P) * density
    return V * density, com, inertia


def tip_angle(m: Manifold, contact_band: float = 0.3) -> float:
    """Degrees the figure (standing as it is, lowest point on the floor) can lean before it falls."""
    _, com, _ = mass_properties(m)
    com = com * 1000.0
    v = m.to_mesh().vert_properties[:, :3].astype(float)
    z0 = v[:, 2].min()
    hull = _hull_2d(v[v[:, 2] <= z0 + contact_band][:, :2])
    if len(hull) < 3:
        return 0.0
    out = []
    for i in range(len(hull)):
        p, q = hull[i], hull[(i + 1) % len(hull)]
        e = q - p
        n = np.array([e[1], -e[0]]) / np.linalg.norm(e)
        out.append(np.degrees(np.arctan2(-float((com[:2] - p) @ n), com[2] - z0)))
    return float(min(out))


def mjcf(m: Manifold, friction: float = 0.6, timestep: float = 0.0005) -> str:
    """The figure (its convex hull for contact, its own mass properties) above a floor."""
    hull = m.hull().to_mesh()
    v = hull.vert_properties[:, :3].astype(float) / 1000.0
    f = np.asarray(hull.tri_verts)
    mass, com, inertia = mass_properties(m)
    full = [inertia[0, 0], inertia[1, 1], inertia[2, 2], inertia[0, 1], inertia[0, 2], inertia[1, 2]]
    fmt = lambda xs: " ".join(f"{float(x):.9g}" for x in np.ravel(xs))  # noqa: E731
    return f"""<mujoco model="drop">
  <option timestep="{timestep}" gravity="0 0 -9.81"/>
  <default><geom friction="{friction} 0.005 0.0001" condim="3" solref="0.004 1" solimp="0.95 0.99 0.0005"/></default>
  <asset><mesh name="figure" vertex="{fmt(v)}" face="{fmt(f)}"/></asset>
  <worldbody>
    <geom name="floor" type="plane" size="1 1 0.1"/>
    <body name="figure"><freejoint/>
      <inertial pos="{fmt(com)}" mass="{mass:.9g}" fullinertia="{fmt(full)}"/>
      <geom type="mesh" mesh="figure" contype="1" conaffinity="1"/>
    </body>
  </worldbody>
</mujoco>"""


def drop(m: Manifold, height: float = 20.0, tilt_deg: float = 0.0, direction_deg: float = 0.0,
         shove: float = 0.0, seconds: float = 8.0, model=None) -> dict:
    """Drop the figure from `height` mm above the floor (its lowest point), leaning `tilt_deg` towards
    `direction_deg`, with a sideways shove of `shove` m/s that way. Returns its final and greatest tilt."""
    import mujoco

    model = model or mujoco.MjModel.from_xml_string(mjcf(m))
    data = mujoco.MjData(model)
    _, com, _ = mass_properties(m)
    d = np.radians(direction_deg)
    lean = rotation([-np.sin(d), np.cos(d), 0.0], np.radians(tilt_deg), com * 1000.0)  # top moves towards d
    v = m.to_mesh().vert_properties[:, :3].astype(float)
    lift = height - (v @ lean[:3, :3].T + lean[:3, 3])[:, 2].min()
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, lean[:3, :3].ravel())
    data.qpos[:3] = (lean[:3, 3] + [0, 0, lift]) / 1000.0
    data.qpos[3:7] = quat
    data.qvel[:2] = shove * np.array([np.cos(d), np.sin(d)])
    worst, still, dt = 0.0, 0.0, model.opt.timestep
    for _ in range(int(seconds / dt)):  # until it has been still for STILL_S, or time runs out
        mujoco.mj_step(model, data)
        worst = max(worst, float(np.degrees(np.arccos(np.clip(data.xmat[1][8], -1, 1)))))
        still = still + dt if np.abs(data.qvel).max() < 0.01 else 0.0
        if still >= STILL_S and data.time > 0.3:
            break
    final = float(np.degrees(np.arccos(np.clip(data.xmat[1].reshape(3, 3)[2, 2], -1, 1))))
    pose = np.eye(4)
    pose[:3, :3], pose[:3, 3] = data.xmat[1].reshape(3, 3), data.xpos[1] * 1000.0
    return {"final_tilt_deg": round(final, 2), "max_tilt_deg": round(worst, 2), "upright": final < UPRIGHT_DEG,
            "resting": still >= STILL_S, "seconds": round(float(data.time), 2), "pose": pose}  # pose: built frame -> world (mm)


def settle(m: Manifold, seconds: float = 8.0) -> tuple[Manifold, dict]:
    """Set the figure on the floor as it is and let it come to rest; returns it in the pose it ends in
    (lowest point on z = 0) and how far it went over."""
    r = drop(m, height=0.5, seconds=seconds)
    rested = m.transform(r["pose"][:3])
    return rested.translate([0, 0, -rested.bounding_box()[2]]), r


def drop_test(m: Manifold, trials: int = 8, height: float = 20.0, tilt_deg: float = 5.0, shove: float = 0.0,
              seed: int = 0, seconds: float = 8.0) -> dict:
    """`trials` drops with random lean directions; how many ended upright, and the static tip angle."""
    import mujoco

    model = mujoco.MjModel.from_xml_string(mjcf(m))
    rng = np.random.default_rng(seed)
    runs = [drop(m, height, tilt_deg, float(rng.uniform(0, 360)), shove, seconds, model) for _ in range(trials)]
    mass, _, _ = mass_properties(m)
    return {"stayed_up": sum(r["upright"] for r in runs), "trials": trials, "height_mm": height,
            "tilt_deg": tilt_deg, "shove_m_s": shove, "tip_angle_deg": round(tip_angle(m), 1),
            "mass_g": round(mass * 1000, 1), "mujoco": mujoco.__version__, "runs": runs}


def stand_search(fig, trials: int = 8, height: float = 20.0, tilt_deg: float = 5.0) -> dict:
    """Try an articulated figure in every combination of a few poses per joint (motion.pose_options),
    stood the way it was built. Each is set down and left to settle; the one that ends nearest its
    stance is then drop-tested. Returns the ranking, the best pose (joint -> option index) and its test."""
    import itertools

    from .articulate import union
    from .motion import pose_options, posed

    opts = [pose_options(fig, j) for j in fig.joints]
    ranked = []
    for combo in itertools.product(*[range(len(o)) for o in opts]):
        motions = {j.name: opts[i][c] for i, (j, c) in enumerate(zip(fig.joints, combo))}
        r = drop(union(list(posed(fig, motions).values())), height=0.5)
        ranked.append((r["final_tilt_deg"], combo))
    ranked.sort()
    tilt, combo = ranked[0]
    best = union(list(posed(fig, {j.name: opts[i][c] for i, (j, c) in enumerate(zip(fig.joints, combo))}).values()))
    rested, _ = settle(best)
    test = drop_test(rested, trials, height, tilt_deg)
    test.pop("runs")
    return {"poses_tried": len(ranked), "best": {j.name: c for j, c in zip(fig.joints, combo)},
            "best_settles_deg": tilt, "upright_poses": sum(t < UPRIGHT_DEG for t, _ in ranked),
            "settle_deg": [t for t, _ in ranked], "best_drop_test": test, "best_solid": rested}
