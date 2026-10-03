import numpy as np
import pytest

from printshop.articulate import Body, DoesNotFit, Joint, articulate
from printshop.mechanisms import Prim
from printshop.motion import captured, collisions, gaps, posed
from printshop.orient import lay_flat
from printshop.profiles import FDM_04, RESIN


def two_boxes(kind, limits, child_size=20.0):
    """A 30 x 30 x 12 slab with a cube standing on it, joined at the middle of the slab's top.
    A free hinge gets a ball and a wider slab, and a ball joint a round limb: a cube spinning
    freely on a slab's face would saw the slab in two."""
    free = kind == "hinge" and limits is None
    base = Body("base", [Prim("box", (30.0, 50.0 if free else 30.0, 12.0))])
    shape = Prim("box", (child_size,) * 3, pos=np.array([0, 0, 6 + child_size / 2]))
    if free:
        shape = Prim("sphere", (8.0,), pos=np.array([0, 0, 14.0]))
    elif kind == "ball":  # a limb, round about its own axis as rabbitstew's are
        shape = Prim("cylinder", (child_size / 2, child_size), pos=np.array([0, 0, 6 + child_size / 2]))
    top = Body("top", [shape])
    j = Joint("j", kind, "base", "top", np.array([0.0, 0, 6]), np.array([1.0, 0, 0]), np.array([0.0, 0, 1]), limits)
    return [base, top], [j]


CASES = [("hinge", (-0.7, 0.7)), ("hinge", None), ("ball", None), ("slide", (-4.0, 4.0))]


@pytest.fixture(scope="module", params=CASES, ids=[f"{k}-{'limited' if r else 'free'}" for k, r in CASES])
def figure(request):
    bodies, joints = two_boxes(*request.param)
    return articulate(bodies, joints, FDM_04)


def test_each_body_is_one_separate_piece(figure):
    assert all(len(s.decompose()) == 1 for s in figure.solids.values())
    assert (figure.solids["base"] ^ figure.solids["top"]).volume() == pytest.approx(0, abs=1e-6)


def test_every_gap_is_at_least_the_clearance(figure):
    assert min(gaps(figure).values()) >= figure.profile.joint_clearance - 0.005


def test_joint_is_captured(figure):
    assert captured(figure, figure.joints[0])


def test_sweeping_the_joint_through_its_range_never_collides(figure):
    assert max(collisions(figure, figure.joints[0], n=16)) < 0.01


def test_the_uncarved_bodies_would_collide(figure):
    """The honesty check has teeth: without carving, the moving cube runs into the slab."""
    j = figure.joints[0]
    if j.kind == "slide":  # a cube sliding across a flat top never touches it
        return
    assert max(collisions(figure, j, figure.raw, n=16)) > 1.0


def test_hinge_stops_at_its_range():
    fig = articulate(*two_boxes("hinge", (-0.5, 0.5)), FDM_04)
    j = fig.joints[0]
    from printshop.mechanisms import rotation
    past = posed(fig, {"j": rotation(j.axis, 0.5 + np.radians(8), j.anchor)})
    assert (past["top"] ^ past["base"]).volume() > 0.01  # the web hits the end of its slot


def test_ball_cone_is_recorded_and_capped_by_capture():
    fig = articulate(*two_boxes("ball", (0.0, np.radians(80))), FDM_04)
    info = fig.mechs["j"].info
    assert info["cone_deg"] == info["cone_max_deg"] < 45


@pytest.mark.parametrize("profile", [FDM_04, RESIN])
def test_too_thin_a_child_does_not_fit(profile):
    with pytest.raises(DoesNotFit):
        articulate(*two_boxes("ball", None, child_size=3.0), profile)


def test_lay_flat_puts_something_on_the_bed_and_keeps_pieces_whole(figure):
    laid, info = lay_flat(figure.solids)
    assert info["on_bed"] and info["bed_contact_mm2"] > 0
    assert min(float(np.array(m.bounding_box())[2]) for m in laid.values()) == pytest.approx(0, abs=1e-6)
    assert all(len(m.decompose()) == 1 for m in laid.values())
