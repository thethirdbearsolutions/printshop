import pytest

from printshop.joints import ball_joint, gap, hinge
from printshop.profiles import FDM_04, RESIN


def _trapped(a, b, moves):
    """True if every listed move of b collides with a (so b cannot leave that way)."""
    return all((a ^ b.translate(m)).volume() > 1e-3 for m in moves)


@pytest.mark.parametrize("profile", [FDM_04, RESIN])
def test_hinge_prints_as_two_free_parts_with_the_profile_clearance(profile):
    a, b = hinge(profile=profile)
    assert len(a.decompose()) == 1 and len(b.decompose()) == 1
    assert (a ^ b).volume() == pytest.approx(0, abs=1e-6)
    assert gap(a, b) == pytest.approx(profile.joint_clearance, abs=0.02)


def test_hinge_leaves_cannot_pull_apart():
    a, b = hinge()
    assert _trapped(a, b, [(0, 2, 0), (0, -2, 0), (0, 0, 2), (0, 0, -2)])


@pytest.mark.parametrize("profile", [FDM_04, RESIN])
def test_ball_joint_is_captured_but_free(profile):
    socket, ball = ball_joint(profile=profile)
    assert (socket ^ ball).volume() == pytest.approx(0, abs=1e-6)
    assert gap(socket, ball) == pytest.approx(profile.joint_clearance, abs=0.02)
    assert _trapped(socket, ball, [(0, 0, 2), (0, 0, 4), (2, 0, 0), (0, -2, 0)])
