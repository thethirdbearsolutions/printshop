import itertools
import os
import shutil
import subprocess
import zipfile

import numpy as np
import pytest
from manifold3d import Manifold

from printshop.bricks import brick
from printshop.checks import check
from printshop.colour import merge
from printshop.export import write_3mf
from printshop.profiles import FDM_04
from printshop.sources import burritos as bu

KINDS = ["madison", "yuri", "sebastian", "firework"]


def soup(m: Manifold) -> list:
    """A solid as the exporter writes it: three.js y-up triangle soup (undoing TO_Z_UP, at 1 mm per unit)."""
    mesh = m.to_mesh()
    v = mesh.vert_properties[:, :3].astype(float)[np.asarray(mesh.tri_verts)].reshape(-1, 3)
    return (v @ bu.TO_Z_UP).ravel().tolist()


def grid_plane(w=10.0, h=6.0, n=4):
    xs, ys = np.linspace(-w / 2, w / 2, n + 1), np.linspace(-h / 2, h / 2, n + 1)
    tris = []
    for i in range(n):
        for j in range(n):
            a, b = (xs[i], ys[j], 0), (xs[i + 1], ys[j], 0)
            c, d = (xs[i + 1], ys[j + 1], 0), (xs[i], ys[j + 1], 0)
            tris += [a, b, c, a, c, d]
    return np.array(tris, float).ravel().tolist()


def test_a_double_sided_plane_is_thickened_to_the_minimum_wall():
    part = {"triangles": grid_plane(), "double_sided": True}
    m, how = bu.part_solid(part, 1.0, FDM_04.min_wall)
    assert how == "thickened" and len(m.decompose()) == 1
    assert m.volume() == pytest.approx(10 * 6 * FDM_04.min_wall, rel=0.01)


def test_an_open_one_sided_tube_is_capped_into_a_solid():
    tube = Manifold.cylinder(10.0, 2.0, 2.0, 24)
    mesh = tube.to_mesh()
    v = mesh.vert_properties[:, :3]
    t = np.asarray(mesh.tri_verts)
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    side = t[np.abs(n[:, 2]) < 1e-6 * np.linalg.norm(n, axis=1).max()]  # drop the end discs
    tri = (v[side].reshape(-1, 3) @ bu.TO_Z_UP).ravel().tolist()
    m, how = bu.part_solid({"triangles": tri}, 1.0, FDM_04.min_wall)
    assert how == "capped" and m.volume() == pytest.approx(tube.volume(), rel=0.01)


def test_a_part_thinner_than_the_wall_is_fattened():
    part = {"triangles": soup(Manifold.cube([5.0, 0.3, 0.4], center=True))}
    m, how = bu.part_solid(part, 1.0, FDM_04.min_wall)
    lo, hi = np.array(m.bounding_box()).reshape(2, 3)
    assert how == "closed+fattened" and min(hi - lo) >= FDM_04.min_wall - 1e-6


def test_colours_merge_down_to_the_slots_keeping_what_shows_most():
    weights = {"#ffffff": 1.0, "#fefefe": 1.0, "#ff0000": 5.0, "#00ff00": 5.0, "#0000ff": 5.0, "#111111": 2.0}
    printed = merge(weights, 4)
    assert len(set(printed.values())) == 4
    assert printed["#fefefe"] == printed["#ffffff"]  # near-identical shades go together first
    assert {"#ff0000", "#00ff00", "#0000ff"} <= set(printed.values())


@pytest.fixture(scope="module", params=KINDS)
def burrito(request):
    return bu.figure(bu.load(request.param), FDM_04)


def test_burrito_is_one_piece_that_stands(burrito):
    r = check(burrito.solid)
    assert r.pieces == 1 and r.stands and r.stability_margin_mm > 5


def test_burrito_base_fits_the_stud_grid(burrito):
    """Everything below the plate height is exactly a plate's underside: the hollow and its tubes."""
    p = FDM_04
    w, l = burrito.info["base_studs"]
    x, y = burrito.info["base_centre_mm"]
    under = burrito.solid.translate([-x, -y, 0])
    plate = brick(w, l, plates=1, profile=p, studs=False)
    for z in (0.5, 1.5, 2.0):
        cut = [m.trim_by_plane([0, 0, -1], -z).trim_by_plane([0, 0, 1], z - 0.1) for m in (under, plate)]
        assert cut[0].volume() == pytest.approx(cut[1].volume(), rel=0.01)


def test_colour_groups_fit_the_slots_and_partition_the_figure(burrito):
    groups = burrito.colours
    assert len(groups) <= burrito.info["slots"]
    assert sum(g.volume() for _, g, _ in groups) == pytest.approx(burrito.solid.volume(), rel=0.005)
    for (_, a, _), (_, b, _) in itertools.combinations(groups, 2):
        assert (a ^ b).volume() < 0.002 * burrito.solid.volume()


def test_multicolour_3mf_is_one_object_with_a_part_per_colour(burrito, tmp_path):
    path = tmp_path / "b.3mf"
    write_3mf(burrito.colours, str(path), assembly=burrito.name)
    with zipfile.ZipFile(path) as z:
        model = z.read("3D/3dmodel.model").decode()
    assert model.count("<component ") == len(burrito.colours) and model.count("<item ") == 1


@pytest.mark.skipif(not (shutil.which("node") and os.environ.get("CHAOTIC_ATTACK")),
                    reason="needs node and CHAOTIC_ATTACK=<chaotic-attack checkout>")
def test_exporter_reproduces_the_bundled_madison(tmp_path):
    tool = os.path.join(os.path.dirname(__file__), "..", "tools", "burrito-export")
    subprocess.run(["node", "--experimental-strip-types", "export.mjs", os.environ["CHAOTIC_ATTACK"], str(tmp_path),
                    "madison", "--hero"], cwd=tool, check=True, capture_output=True)
    fresh, bundled = bu.load(str(tmp_path / "madison-hero.json.gz")), bu.load("madison")
    assert [(p["name"], p["colour"]) for p in fresh["parts"]] == [(p["name"], p["colour"]) for p in bundled["parts"]]
