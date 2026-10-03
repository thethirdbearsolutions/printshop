import itertools
import os
import re

import numpy as np
import pytest

from printshop import figures as F
from printshop.accessories import accessories, bar
from printshop.bricks import plate
from printshop.checks import stability
from printshop.geom import union
from printshop.profiles import FDM_04, RESIN

PROFILES = [FDM_04, RESIN, FDM_04.tuned(name="thin-bar", pin_diameter=3.0, clip_fit=-0.15, pin_fit=0.2)]


def bore_across(m, centre, axis_dir):
    """Inner diameter of a hole through `centre`, measured by a ray across it along axis_dir."""
    d = np.asarray(axis_dir, float)
    hits = m.ray_cast(np.asarray(centre) - 20 * d, np.asarray(centre) + 20 * d)
    ts = sorted(float(np.dot(np.asarray(h.position) - centre, d)) for h in hits)
    inside = [t for t in ts if abs(t) < 5]
    return min(t for t in inside if t > 0) - max(t for t in inside if t < 0)


@pytest.fixture(scope="module", params=PROFILES, ids=[p.name for p in PROFILES])
def built(request):
    return request.param, F.figure(request.param)


def test_every_part_is_one_piece_and_parts_do_not_overlap(built):
    _, parts = built
    assert all(len(m.decompose()) == 1 for m in parts.values())
    for a, b in itertools.combinations(parts.values(), 2):
        assert (a ^ b).volume() < 1e-6


def test_hand_grips_the_bar_by_the_profiles_clip_fit(built):
    """Printed sizes: holes come out xy_compensation smaller, pegs that much bigger."""
    p, parts = built
    c = F.hand_centre(p, 1)
    bore = bore_across(parts["arm-left"], c, [1, 0, 0])
    assert bore - p.xy_compensation == pytest.approx(p.pin_diameter + p.clip_fit, abs=0.02)
    rod = bar(p)
    lo, hi = np.array(rod.bounding_box()).reshape(2, 3)
    assert (hi - lo)[0] + p.xy_compensation == pytest.approx(p.pin_diameter, abs=0.01)


def test_bar_snaps_into_the_hand_and_cannot_drop_out(built):
    p, parts = built
    c = F.hand_centre(p, 1)
    held = bar(p, 12.0).translate([0, 0, -6]).rotate([90, 0, 0]).translate(c)  # along y through the clip
    hand = parts["arm-left"]
    squeeze = max(0.0, (p.pin_diameter - p.xy_compensation) - 2 * F.clip_bore(p)) / 2  # modelled grip
    assert (held ^ hand).volume() <= np.pi * p.pin_diameter * squeeze * F.CLIP_LEN + 0.05  # it sits in the bore
    mouth = p.clip_opening * p.pin_diameter
    assert 0.6 * p.pin_diameter < mouth < p.pin_diameter  # it snaps through the mouth, then holds
    for d in ([0, 0, -1], [0, 0, 1], [1, 0, 0], [-1, 0, 0]):
        assert (held.translate(np.multiply(d, 1.0)) ^ hand).volume() > 0.05


def test_head_sits_on_the_neck_stud(built):
    p, parts = built
    L = F.Layout(p)
    head, torso = parts["head"], parts["torso"]
    stud_top = L.neck + p.stud_height
    socket = bore_across(head, [0, 0, L.neck + 0.5], [1, 0, 0])
    assert socket - p.xy_compensation == pytest.approx(p.stud_diameter + p.socket_delta, abs=0.02)
    assert (head ^ torso).volume() < 1e-6 and head.min_gap(torso, 1.0) < 0.05  # seated, not floating
    assert np.array(head.bounding_box())[5] > stud_top + 2  # with room above the stud


def test_legs_turn_on_the_hip_pins_and_stay_on(built):
    p, parts = built
    L = F.Layout(p)
    hips = parts["hips"]
    for side in ("leg-left", "leg-right"):
        leg = parts[side]
        for deg in (-90, -45, 45, 90):
            assert (F.rotate_about_x(leg, deg, L.hip_axis) ^ hips).volume() < 0.01, (side, deg)
        for d in ([0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]):
            assert (leg.translate(np.multiply(d, 1.0)) ^ hips).volume() > 0.01  # the pin holds it
    hole = bore_across(parts["leg-left"], [L.keel + L.c + 1.5, 0, L.hip_axis], [0, 0, 1])
    pin = 2 * F.pin_radius(p)
    assert hole - pin == pytest.approx(p.pin_fit + 2 * p.xy_compensation, abs=0.03)


def test_arms_swing_all_the_way_round_the_shoulder(built):
    p, parts = built
    L = F.Layout(p)
    for side in ("arm-left", "arm-right"):
        for deg in range(0, 360, 30):
            arm = F.rotate_about_x(parts[side], deg, L.shoulder)
            assert (arm ^ parts["torso"]).volume() < 0.01, (side, deg)


def test_figure_stands_on_a_plate(built):
    """The feet sockets drop onto two studs one pitch apart, and the figure stays up."""
    p, parts = built
    base = plate(2, 2, p).translate([0, -p.pitch / 2, -p.plate_height])
    figure = union(list(parts.values()))
    assert (figure ^ base).volume() < 1e-6
    stands, margin = stability(figure)
    assert stands and margin > 2.0


def test_accessories_are_whole_and_their_colours_do_not_overlap():
    for name, parts in accessories().items():
        for _, m, _ in parts:
            assert len(m.decompose()) >= 1 and m.volume() > 1, name
        for (_, a, _), (_, b, _) in itertools.combinations(parts, 2):
            assert (a ^ b).volume() < 0.01, name


def test_plate_layout_puts_every_part_on_the_bed():
    out = F.plate_layout({n: [(n, m, None)] for n, m in F.figure().items()})
    assert all(abs(m.bounding_box()[2]) < 1e-6 for _, m, _ in out)
    boxes = [np.array(m.bounding_box()) for _, m, _ in out]
    for a, b in itertools.combinations(boxes, 2):
        assert a[3] <= b[0] or b[3] <= a[0]  # side by side, not on top of each other


def test_the_trademark_appears_nowhere_but_the_compatibility_note():
    word = "le" + "go"  # spelt in two halves so this file does not trip its own check
    root = os.path.join(os.path.dirname(__file__), "..")
    for d, _, files in os.walk(root):
        if any(x in d for x in (".git", "node_modules", ".src", "__pycache__", ".egg-info")):
            continue
        for f in files:
            path = os.path.join(d, f)
            assert not re.search(word, f, re.I), path
            if f.endswith((".py", ".md", ".mjs", ".json", ".toml")) and f != "README.md":
                assert not re.search(rf"\b{word}\b", open(path, errors="ignore").read(), re.I), path
