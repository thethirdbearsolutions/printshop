import numpy as np
import pytest
from manifold3d import Manifold

from printshop.burrito import figure, merge_colours, Part
from printshop.geom import box, sphere
from printshop.profiles import FDM_04


def _mesh(m: Manifold, colour: str, name: str, shift=(0, 0, 0)):
    """A solid as the game would dump it: Y up, face towards -Z."""
    mesh = m.translate(list(shift)).to_mesh()
    v = mesh.vert_properties[:, :3]
    yup = np.column_stack([-v[:, 0], v[:, 2], v[:, 1]])  # inverse of the exporter's mapping
    return {"name": name, "color": colour, "positions": yup.ravel().tolist(),
            "index": np.asarray(mesh.tri_verts).ravel().tolist()}


def _plane(colour, w=0.8, h=1.0, at=(0, 0.6, 0.6)):
    """One open, zero-thickness quad (a cape), in game coordinates."""
    x, y, z = at
    pos = [x - w / 2, y, z, x + w / 2, y, z, x + w / 2, y + h, z, x - w / 2, y + h, z]
    return {"name": "cape", "color": colour, "positions": pos, "index": [0, 1, 2, 0, 2, 3]}


@pytest.fixture(scope="module")
def dump():
    body = Manifold.cylinder(2.0, 0.55, 0.55, 32).translate([0, 0, 0.05]) + sphere(0.55, 32).translate([0, 0, 2.05])
    eye_white = sphere(0.16, 16).scale([1, 0.55, 1])
    meshes = [
        _mesh(body, "#e8c990", "wrap"),
        _mesh(eye_white, "#ffffff", "eye", (-0.24, -0.52, 1.6)),
        _mesh(eye_white, "#ffffff", "eye", (0.24, -0.52, 1.6)),
        _mesh(sphere(0.07, 12), "#1a1418", "pupil", (-0.24, -0.6, 1.6)),
        _mesh(sphere(0.07, 12), "#1a1418", "pupil", (0.24, -0.6, 1.6)),
        _mesh(sphere(0.2, 16), "#6fae4a", "filling", (0, 0, 2.6)),
        _mesh(sphere(0.12, 16), "#ff3b30", "orb", (1.2, 0, 1.0)),  # floats beside the body
        _mesh(sphere(0.002, 6), "#ffe135", "speck", (2.0, 0, 2.0)),  # too small to print
        _plane("#d41f3a"),
    ]
    return {"kind": "test", "name": "Test Burrito", "meshes": meshes}


@pytest.fixture(scope="module")
def fig(dump):
    return figure(dump, height_mm=40, max_colours=4)


def test_colours_fit_the_ams(fig):
    assert len({c for _, _, c in fig.objects}) <= 4


def test_objects_do_not_overlap(fig):
    objs = [m for _, m, _ in fig.objects]
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            assert (objs[i] ^ objs[j]).volume() < 0.5


def test_every_object_is_watertight(fig):
    for name, m, _ in fig.objects:
        assert m.status().name == "NoError" and m.volume() > 0, name


def test_floating_part_gets_a_strut_and_specks_are_dropped(fig):
    assert any("strut" in n for n in fig.notes)
    assert any("speck" in n or "skipped" in n for n in fig.notes)
    assert not any(c == "#ffe135" for _, _, c in fig.objects)


def test_open_cape_is_thickened(fig):
    assert any("thickened" in n for n in fig.notes)


def test_base_fits_the_stud_grid_and_figure_stands(fig):
    from printshop.checks import stability
    base = dict((n, m) for n, m, _ in fig.objects)["base"]
    lo, hi = np.array(base.bounding_box()).reshape(2, 3)
    side = hi[0] - lo[0]
    n = round((side + 2 * FDM_04.side_gap) / FDM_04.pitch)
    assert side == pytest.approx(n * FDM_04.pitch - 2 * FDM_04.side_gap, abs=0.05)
    assert lo[2] == pytest.approx(0, abs=1e-6)
    whole = fig.objects[0][1]
    for _, m, _ in fig.objects[1:]:
        whole = whole + m
    assert stability(whole)[0]


def test_height_is_the_asked_height_plus_the_base(fig):
    whole = fig.objects[0][1]
    for _, m, _ in fig.objects[1:]:
        whole = whole + m
    lo, hi = np.array(whole.bounding_box()).reshape(2, 3)
    top_of_base = FDM_04.plate_height + 1.6
    assert hi[2] == pytest.approx(40 + top_of_base - 1.0, abs=0.5)


def test_merge_keeps_far_apart_colours_and_joins_near_ones():
    parts = [Part("a", "#ffffff", box([10, 10, 10])), Part("b", "#fefefe", box([1, 1, 1])),
             Part("c", "#000000", box([5, 5, 5]))]
    mapping = merge_colours(parts, 2)
    assert mapping["#fefefe"] == "#ffffff" and mapping["#000000"] == "#000000"
