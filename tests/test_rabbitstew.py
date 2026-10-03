import pytest

pytest.importorskip("mujoco")
pytest.importorskip("rabbitstew")

from printshop.checks import check  # noqa: E402
from printshop.sources import rabbitstew as rs  # noqa: E402


@pytest.fixture(scope="module")
def champion():
    return rs.load("RBT-19-P-801", "holistic", 590)


def test_figurine_matches_rabbitstews_own_print(champion):
    """rabbitstew's docs/prints/rbt19-p801-holistic-g590.txt: frame 188, 85.84 mm/m, 108.3 x 108.3 x 51.8 mm, 94.04 cm3."""
    body, info = rs.figurine(champion, min_wall=1.6)
    assert (info["frame"], info["time_s"], info["mujoco"]) == (188, 7.52, "3.14.0")
    assert info["mm_per_model_m"] == pytest.approx(85.84, abs=0.01)
    assert info["size_mm"] == pytest.approx([108.3, 108.3, 51.8], abs=0.1)
    assert info["volume_cm3"] == pytest.approx(94.04, abs=0.05)


def test_figurine_is_one_solid_that_stands_at_the_asked_length(champion):
    body, info = rs.figurine(champion, length=60.0, plinth=3.0)
    r = check(body)
    assert r.pieces == 1 and r.stands
    assert info["mm_per_model_m"] < 85.84 and max(r.size_mm[:2]) < 80


def test_run_dir_finds_bundled_runs_and_refuses_unknown_ones():
    assert rs.run_dir("RBT-19-P-801").endswith("RBT-19-P-801")
    with pytest.raises(FileNotFoundError):
        rs.run_dir("RBT-0-nope")
