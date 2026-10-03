"""Checks for articulated figures: separate pieces, clearance, capture, and sweeping every joint.

The sweep moves a joint's child (and everything hanging from it) through test
poses that fall between the poses the carving used, and measures how much of it
lands inside the parts that stay. The same sweep run on the uncarved, simulated
shapes is the honesty report: it says where MuJoCo lets parts pass through each
other, which is exactly what the carving had to remove.
"""
from __future__ import annotations

import itertools

import numpy as np

from .articulate import Figure, union
from .mechanisms import rotation


def check_poses(fig: Figure, joint, n: int = 24, seed: int = 0) -> list:
    """4x4 child motions for a joint: through the range (ends included) and in between the carving samples."""
    m = fig.mechs[joint.name]
    rng = np.random.default_rng(seed)
    if joint.kind == "hinge":
        lo, hi = joint.limits or (-np.pi, np.pi)
        return [rotation(joint.axis, a, joint.anchor) for a in np.linspace(lo, hi, n)]
    if joint.kind == "slide":
        lo, hi = m.info["travel_mm"]
        out = []
        for s in np.linspace(lo, hi, n):
            T = np.eye(4)
            T[:3, 3] = s * joint.axis
            out.append(T)
        return out
    cone = np.radians(m.info["cone_deg"])
    z = joint.out
    x = np.cross(z, [1, 0, 0] if abs(z[0]) < 0.9 else [0, 1, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    out = []
    for k in range(n):  # the rim of the cone, then random tilts; each with a random twist
        tilt = cone if k < n // 2 else cone * np.sqrt(rng.uniform())
        phi = 2 * np.pi * (k / (n // 2) if k < n // 2 else rng.uniform())
        swing = rotation(np.cos(phi) * x + np.sin(phi) * y, tilt, joint.anchor)
        out.append(swing @ rotation(z, rng.uniform(0, 2 * np.pi), joint.anchor))
    return out


def collisions(fig: Figure, joint, solids=None, n: int = 24) -> list:
    """Overlap volume (mm^3) between the moving and the staying parts at each test pose."""
    solids = fig.solids if solids is None else solids
    moving = union([solids[b] for b in fig.subtree[joint.name]])
    static = union([s for b, s in solids.items() if b not in fig.subtree[joint.name]])
    return [float((moving.transform(T[:3]) ^ static).volume()) for T in check_poses(fig, joint, n)]


def captured(fig: Figure, joint, step: float = 1.5) -> bool:
    """True if the child cannot be pulled off its parent in any of the six axis directions
    (a slide's own travel excepted)."""
    moving = union([fig.solids[b] for b in fig.subtree[joint.name]])
    parent = fig.solids[joint.parent]
    dirs = [d for d in np.vstack([np.eye(3), -np.eye(3)])
            if joint.kind != "slide" or abs(d @ joint.axis) < 0.9]
    return all((parent ^ moving.translate(step * d)).volume() > 1e-3 for d in dirs)


def gaps(fig: Figure) -> dict:
    """Smallest gap (mm) between every pair of pieces (search capped at 2 mm)."""
    return {(a, b): float(fig.solids[a].min_gap(fig.solids[b], 2.0))
            for a, b in itertools.combinations(fig.solids, 2)}


def report(fig: Figure, n: int = 24) -> dict:
    """Everything the tests assert, plus the honesty report on the simulated shapes."""
    c = fig.profile.joint_clearance
    pieces = {b: len(s.decompose()) for b, s in fig.solids.items()}
    g = gaps(fig)
    joints = {}
    for j in fig.joints:
        hit = collisions(fig, j, n=n)
        raw = collisions(fig, j, fig.raw, n=n)
        joints[j.name] = {"kind": j.kind, "captured": captured(fig, j), "max_overlap_mm3": round(max(hit), 4),
                          "simulated_overlap_mm3": round(max(raw), 1)}
    rest = {f"{a}/{b}": round(float((fig.raw[a] ^ fig.raw[b]).volume()), 1)
            for a, b in itertools.combinations(fig.raw, 2)}
    kept = {b: round(fig.solids[b].volume() / fig.raw[b].volume(), 3) for b in fig.solids}
    return {
        "pieces": pieces,
        "min_gap_mm": round(min(g.values()), 3), "clearance_mm": c,
        "joints": joints,
        "honesty": {"simulated_rest_overlap_mm3": {k: v for k, v in rest.items() if v > 0},
                    "volume_kept": kept},
    }


def posed(fig: Figure, motions: dict) -> dict:
    """The solids with joints moved: motions maps joint name -> 4x4 motion at rest (as check_poses gives).
    A body moves by every joint between it and the root, the one nearest the root applied last."""
    out = {}
    for b, s in fig.solids.items():
        T = np.eye(4)
        for j in fig.joints:  # joints are listed parents first, so nearer-root motions compose on the left
            if b in fig.subtree[j.name] and j.name in motions:
                T = T @ motions[j.name]
        out[b] = s.transform(T[:3])
    return out
