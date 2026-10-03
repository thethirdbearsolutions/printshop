import itertools

import numpy as np
import pytest

from printshop import figures as F
from printshop.armory import armour, armoury, helmet, sword
from printshop.geom import union
from printshop.pegasus import horse, wing, wing_print
from printshop.profiles import FDM_04, RESIN
from printshop.scenes import knight, rider

PROFILES = [FDM_04, RESIN]


def clashes(scene, tol=0.05, p=FDM_04):
    """Pairs that run into each other. A hand and what it holds may overlap by the clip's grip, which a
    profile with no xy_compensation (resin) models as overlap rather than leaving to the printer."""
    squeeze = max(0.0, (p.pin_diameter - p.xy_compensation) - 2 * F.clip_bore(p)) / 2
    held = np.pi * p.pin_diameter * squeeze * F.CLIP_LEN + tol
    out = []
    for (a, ma, _), (b, mb, _) in itertools.combinations(scene, 2):
        grip = {a, b} & {"arm-left", "arm-right"} and {a, b} & {"shield", "sword-grip"}
        if (ma ^ mb).volume() > (held if grip else tol):
            out.append((a, b))
    return out


@pytest.mark.parametrize("p", PROFILES, ids=[p.name for p in PROFILES])
def test_every_armoury_piece_is_whole_and_its_colours_do_not_overlap(p):
    for name, parts in armoury(p).items():
        assert all(m.volume() > 1 for _, m, _ in parts), name
        assert len(union([m for _, m, _ in parts]).decompose()) == 1, name  # the colours make one piece
        assert not clashes(parts, 0.01), name


@pytest.mark.parametrize("p", PROFILES, ids=[p.name for p in PROFILES])
def test_kitted_out_knight_has_nothing_running_into_anything(p):
    assert not clashes(knight(p), p=p)


def test_sword_grip_is_the_bar_a_hand_grips():
    grip = sword()[0][1]
    lo, hi = np.array(grip.bounding_box()).reshape(2, 3)
    assert (hi - lo)[0] + FDM_04.xy_compensation == pytest.approx(FDM_04.pin_diameter, abs=0.01)


def test_helmet_grips_the_head_stud_and_lifts_off():
    p = FDM_04
    head = F.figure(p)["head"].translate([0, 0, 0.8])  # on the armour's yoke, as in the scene
    helm = helmet(p)[0][1]
    assert (helm ^ head).volume() < 1e-6
    assert helm.min_gap(head, 1.0) == pytest.approx(p.xy_compensation, abs=0.01)  # the stud fit, nothing looser
    assert (helm.translate([0, 0, 4]) ^ head).volume() < 1e-6  # straight off upwards
    assert (helm.translate([1.0, 0, 0]) ^ head).volume() > 0.1  # but not sideways: it is on the stud


def test_armour_is_held_down_by_the_head():
    p = FDM_04
    plate = armour(p)[0][1]
    head = F.figure(p)["head"].translate([0, 0, 0.8])
    assert (plate ^ head).volume() < 1e-6 and (plate.translate([0, 0, 1.0]) ^ head).volume() > 0.1


def test_figure_sits_on_two_studs_with_its_legs_forward():
    """Seated on the saddle: the saddle's studs are in the sockets in the backs of the legs."""
    scene = {n: m for n, m, _ in rider()}
    saddle, legs = scene["pegasus-saddle"], scene["leg-left"] + scene["leg-right"]
    assert (saddle ^ legs).volume() < 0.01 and saddle.min_gap(legs, 1.0) < 0.01  # sat down, not hovering
    assert (saddle ^ legs.translate([0, 1.5, 0])).volume() > 0.1  # and the studs stop it sliding off


def test_wings_sweep_on_their_pins_without_touching_the_horse():
    body = union([m for _, m, _ in horse()])
    for side in (1, -1):
        for deg in (-45, -20, 0, 20, 45):
            assert (wing(side=side, sweep_deg=deg) ^ body).volume() < 0.01, (side, deg)
        w = wing(side=side)
        assert w.min_gap(body, 1.0) == pytest.approx((FDM_04.pin_fit + 2 * FDM_04.xy_compensation) / 2, abs=0.01)
        assert (w.translate([0, 0, 1.0]) ^ body).volume() > 0.01  # the pin holds it


def test_wings_print_flat_and_the_horse_on_its_hooves():
    for side in (1, -1):
        w = wing_print(side=side)
        lo, hi = np.array(w.bounding_box()).reshape(2, 3)
        assert lo[2] == pytest.approx(0, abs=1e-6) and hi[2] < 8  # lying down, the pin standing up
    parts = horse()
    assert all(len(m.decompose()) == 1 for n, m, _ in parts if n in ("pegasus", "pegasus-saddle"))
    hooves = dict((n, m) for n, m, _ in parts)["pegasus-hooves"]
    assert len(hooves.decompose()) == 4 and hooves.bounding_box()[2] == pytest.approx(0, abs=1e-6)


def test_rider_scene_is_clear():
    assert not clashes(rider())


def test_pegasus_and_rider_stay_up():
    pytest.importorskip("mujoco")
    from printshop.stability import drop_test

    for scene in (horse() + [("w1", wing(side=1), None), ("w2", wing(side=-1), None)], rider()):
        r = drop_test(union([m for _, m, _ in scene]), trials=6, height=10.0, tilt_deg=5.0)
        assert r["stayed_up"] == r["trials"] and r["tip_angle_deg"] > 12
