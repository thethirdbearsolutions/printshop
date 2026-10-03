import numpy as np
import pytest

pytest.importorskip("mujoco")

from manifold3d import Manifold  # noqa: E402

from printshop import figures as F  # noqa: E402
from printshop.geom import union  # noqa: E402
from printshop.sources import burritos as bu  # noqa: E402
from printshop.stability import drop, drop_test, mass_properties, settle, tip_angle  # noqa: E402

POLE = Manifold.cube([10.0, 10.0, 60.0]).translate([-5, -5, 0])  # tips at atan(5 / 30) = 9.46 degrees


def test_mass_properties_of_a_box_are_exact():
    m, com, inertia = mass_properties(Manifold.cube([10.0, 20.0, 30.0], center=True).translate([1, 2, 3]))
    assert m == pytest.approx(6e-6 * 1240.0)
    assert com == pytest.approx([0.001, 0.002, 0.003], abs=1e-12)
    expected = m * np.array([20**2 + 30**2, 10**2 + 30**2, 10**2 + 20**2]) / 12 * 1e-6
    assert np.diag(inertia) == pytest.approx(expected) and abs(inertia[0, 1]) < 1e-15


def test_tip_angle_is_the_lean_at_which_the_centre_of_mass_passes_the_edge():
    assert tip_angle(POLE) == pytest.approx(np.degrees(np.arctan(5 / 30)), abs=1e-6)


@pytest.mark.parametrize("lean,stays", [(6.5, True), (12.5, False)])
def test_simulation_agrees_with_the_tip_angle(lean, stays):
    r = drop(POLE, height=0.5, tilt_deg=lean, direction_deg=30)
    assert r["upright"] is stays and r["resting"]


def test_a_dropped_figure_lands_in_the_pose_it_settles_in():
    lying, r = settle(POLE.rotate([80, 0, 0]))  # nearly over: it should finish the fall
    lo, hi = np.array(lying.bounding_box()).reshape(2, 3)
    assert r["resting"] and (hi - lo)[2] == pytest.approx(10.0, abs=0.2) and lo[2] == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize("kind", ["madison", "firework"])
def test_burritos_stay_up_after_a_drop(kind):
    r = drop_test(bu.figure(bu.load(kind)).solid, trials=6, height=20.0, tilt_deg=5.0)
    assert r["stayed_up"] == r["trials"] and r["tip_angle_deg"] > 25


def test_brick_figure_stands_with_its_arms_down():
    r = drop_test(union(list(F.figure().values())), trials=6, height=10.0, tilt_deg=3.0)
    assert r["stayed_up"] == r["trials"] and r["tip_angle_deg"] > 8
