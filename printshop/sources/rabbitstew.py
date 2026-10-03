"""Rabbitstew champions as figurines: a re-simulated pose, every unit a solid, set on a plinth.

Ported from rabbitstew's ``scripts/print_champion.py``. A solo bout is recorded
exactly as rabbitstew's ``scripts/shots.py`` does (the run's config, opponent
proxy on, spawn from SEED), the robot's pose is taken at T seconds, and each
unit (box, sphere, cylinder) becomes a solid at that pose. Units are grown by
half the minimum wall so parts that only touch fuse, any piece still floating
is bridged to the main body, and the feet sink into a round plinth.

Needs the ``rabbitstew`` extra (``pip install -e .[rabbitstew]``): rabbitstew
itself and MuJoCo 3.14.0, the version the runs were made with.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace

import numpy as np
from manifold3d import Manifold

from ..geom import box, cylinder, fuse, place, quat_matrix, sphere, union
from ..profiles import FDM_04, Profile

#: Runs bundled with printshop (see data/rabbitstew/README.md); any rabbitstew run directory works too.
DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rabbitstew")
BOX, SPHERE, CYLINDER = 0, 1, 2  # rabbitstew.genotype.Shape


def _require():
    try:
        import mujoco  # noqa: F401
        import rabbitstew  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise ImportError("rabbitstew champions need the extra: pip install -e .[rabbitstew]") from e


def run_dir(run: str) -> str:
    """A run directory: a path that exists, or the name of a bundled run (``RBT-19-P-801``)."""
    if os.path.isdir(run):
        return run
    bundled = os.path.join(DATA, run.replace("/", "-"))
    if os.path.isdir(bundled):
        return bundled
    raise FileNotFoundError(f"no run directory {run!r} (and no bundled run of that name in {DATA})")


@dataclass
class Champion:
    """One committed genome and the simulation config of the run it evolved in."""

    run: str
    kind: str
    generation: int
    genotype: object  # rabbitstew.genotype.Genotype
    config: object  # rabbitstew.simulation.SimConfig, opponent proxy on

    @property
    def name(self) -> str:
        return f"{os.path.basename(os.path.normpath(self.run)).lower()}-{self.kind}-g{self.generation}"


def load(run: str, kind: str, generation: int) -> Champion:
    _require()
    from rabbitstew.genotype import Genotype
    from rabbitstew.simulation import SimConfig

    d = run_dir(run)
    with open(os.path.join(d, "config.json")) as f:
        cfg = replace(SimConfig.from_dict(json.load(f)["sim"]), opponent_proxy=True)
    g = Genotype.load(os.path.join(d, kind, f"best_gen{generation:04d}.json"))
    return Champion(run=d, kind=kind, generation=generation, genotype=g, config=cfg)


def bout_pose(ch: Champion, seed: int = 3, time: float | None = None):
    """Re-simulate the champion's solo bout. Returns (frame, time_s, units, pose): units are
    rabbitstew UnitSpecs, pose an (n_units, 7) array of world position + (w, x, y, z) quaternion."""
    _require()
    from rabbitstew.simulation import Simulation, spawn_layout

    sim = Simulation([ch.genotype], ch.config, spawns=[spawn_layout(2, ch.config, seed)[0]])
    sim.start_recording()
    sim.run()
    traj = sim.trajectory
    n = traj.robots[0]
    frames = traj.as_array()[:, :n]
    k = traj.n_frames // 2 if time is None else min(traj.n_frames - 1, max(0, round(time / traj.dt)))
    return k, k * traj.dt, traj.units[:n], frames[k]


def unit_solid(shape: int, dims, pos, quat, mm: float, grow: float = 0.0, floor: float = 0.0) -> Manifold:
    """A unit in millimetres. dims (metres) are full extents (box), radius (sphere), or radius and
    length (cylinder, along its local z as MuJoCo's geom frame has it); grow and floor are mm."""
    d = [max(v * mm, floor) for v in dims]
    if shape == BOX:
        m = box([d[0] + 2 * grow, d[1] + 2 * grow, d[2] + 2 * grow])
    elif shape == SPHERE:
        m = sphere(d[0] + grow, 48)
    else:
        m = cylinder(d[1] + 2 * grow, d[0] + grow, center=True, segments=48)
    return place(m, quat_matrix(quat), np.asarray(pos, dtype=float) * mm)


def plinth_under(body: Manifold, thickness: float, margin: float = 4.0, sink: float = 0.6) -> Manifold:
    """Centre the body, sink its lowest points `sink` mm into a round plinth, and join them."""
    lo, hi = np.array(body.bounding_box()).reshape(2, 3)
    body = body.translate([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    v = body.to_mesh().vert_properties[:, :3]
    radius = float(np.linalg.norm(v[:, :2], axis=1).max()) + margin
    return body.translate([0, 0, thickness - sink]) + cylinder(thickness, radius, segments=128)


def figurine(ch: Champion, seed: int = 3, time: float | None = None, length: float = 90.0,
             profile: Profile = FDM_04, min_wall: float | None = None, plinth: float = 4.0):
    """The champion posed as in its bout, one solid. Returns (Manifold, provenance dict).

    The figure is scaled so its longest horizontal extent is `length` mm; units thinner than
    `min_wall` (default: the profile's) are thickened to it.
    """
    import mujoco

    w = profile.min_wall if min_wall is None else min_wall
    k, t, units, pose = bout_pose(ch, seed, time)
    rough = union([unit_solid(u.shape, u.dims, pose[i, :3], pose[i, 3:], 1.0) for i, u in enumerate(units)])
    lo, hi = np.array(rough.bounding_box()).reshape(2, 3)
    mm = length / max(hi[0] - lo[0], hi[1] - lo[1])  # mm per model metre; set before thickening so length holds
    parts = [unit_solid(u.shape, u.dims, pose[i, :3], pose[i, 3:], mm, 0.5 * w, w) for i, u in enumerate(units)]
    n_pieces = len(union(parts).decompose())
    body = fuse(parts, bridge_radius=w)
    if plinth > 0:
        body = plinth_under(body, plinth)
    else:
        lo, hi = np.array(body.bounding_box()).reshape(2, 3)
        body = body.translate([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    lo, hi = np.array(body.bounding_box()).reshape(2, 3)
    info = {
        "run": os.path.basename(os.path.normpath(ch.run)), "kind": ch.kind, "generation": ch.generation, "seed": seed,
        "frame": int(k), "time_s": round(t, 3), "mujoco": mujoco.__version__, "units": len(units),
        "shapes": [("box", "sphere", "cylinder")[int(u.shape)] for u in units],
        "pieces_before_bridging": n_pieces, "genus": body.genus(), "mm_per_model_m": round(float(mm), 2),
        "size_mm": [round(float(x), 1) for x in hi - lo], "volume_cm3": round(body.volume() / 1000.0, 2),
        "min_wall_mm": w, "plinth_mm": plinth, "profile": profile.name,
    }
    return body, info
