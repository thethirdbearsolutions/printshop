from dataclasses import replace

import numpy as np
import pytest

pytest.importorskip("mujoco")
pytest.importorskip("rabbitstew")

from printshop.motion import captured, collisions, gaps  # noqa: E402
from printshop.orient import _place, lay_flat, support_area  # noqa: E402
from printshop.profiles import FDM_04  # noqa: E402
from printshop.sources import rabbitstew as rs  # noqa: E402
from printshop.sources.rabbitstew_jointed import jointed  # noqa: E402


@pytest.fixture(scope="module")
def built():
    """RBT-19 P-801 holistic generation 590: ball, +-36.6 degree hinge, ball."""
    return jointed(rs.load("RBT-19-P-801", "holistic", 590), FDM_04)


def test_joints_come_from_mujoco(built):
    fig, info = built
    assert [j.kind for j in fig.joints] == ["ball", "hinge", "ball"]
    hinge = info["joints"]["r0_j3"]
    assert hinge["stops_deg"] == pytest.approx([-36.6, 36.6], abs=0.1)  # hard stops at the simulated range
    for name in ("r0_j1", "r0_j4"):  # unlimited in the simulation; the print records the cone it chose
        assert info["joints"][name]["sim_range"] is None and 5 < info["joints"][name]["cone_deg"] <= 30


def test_scale_is_about_a_hundred_mm_per_model_metre(built):
    _, info = built
    assert info["thinnest_jointed_part_m"] == pytest.approx(0.119, abs=0.001)
    assert 100 <= info["mm_per_model_m"] <= 130  # grown from 101 until the thin disc's ball fits


def test_every_body_is_one_separate_piece(built):
    fig, _ = built
    assert len(fig.solids) == 4  # three moving joints; the welded parts fused into their bodies
    assert all(len(s.decompose()) == 1 for s in fig.solids.values())


def test_every_gap_is_at_least_the_joint_clearance(built):
    fig, _ = built
    assert min(gaps(fig).values()) >= FDM_04.joint_clearance - 0.005


def test_every_joint_is_captured(built):
    fig, _ = built
    assert all(captured(fig, j) for j in fig.joints)


def test_sweeping_every_joint_never_collides_but_the_simulated_body_does(built):
    fig, _ = built
    for j in fig.joints:
        assert max(collisions(fig, j, n=20)) < 0.01, j.name
        assert max(collisions(fig, j, fig.raw, n=20)) > 100, j.name  # MuJoCo lets these parts interpenetrate


def test_prints_flat_on_a_real_foot_with_less_support_than_standing(built):
    fig, _ = built
    laid, info = lay_flat(fig.solids)
    assert info["bed_contact_mm2"] > 300 and len(info["on_bed"]) >= 2
    standing = _place(list(fig.solids.values()), np.eye(3), info["flat_mm"])
    assert info["support_mm2"] < support_area(standing)
    assert all(len(m.decompose()) == 1 for m in laid.values())
    flat = replace(fig, solids=laid)
    assert min(gaps(flat).values()) >= FDM_04.joint_clearance - 0.005
    assert all(captured(flat, j) for j in fig.joints)
