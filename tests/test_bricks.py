import pytest

from printshop.bricks import CARD_DELTAS, brick, plate, tolerance_card
from printshop.checks import check
from printshop.profiles import FDM_04


@pytest.mark.parametrize("w,l,plates", [(1, 1, 1), (1, 4, 1), (2, 2, 1), (2, 4, 3), (4, 6, 3)])
def test_brick_is_one_watertight_solid_at_nominal_size(w, l, plates):
    m = brick(w, l, plates)
    r = check(m)
    assert r.pieces == 1 and r.stands
    p = FDM_04
    assert r.size_mm[0] == pytest.approx(w * p.pitch - 2 * p.side_gap, abs=0.05)
    assert r.size_mm[1] == pytest.approx(l * p.pitch - 2 * p.side_gap, abs=0.05)
    assert r.size_mm[2] == pytest.approx(plates * p.plate_height + p.stud_height, abs=0.05)


def test_bigger_studs_make_more_material():
    assert plate(2, 2, stud_delta=0.1).volume() > plate(2, 2).volume() > plate(2, 2, stud_delta=-0.1).volume()


def test_tolerance_card_pieces_are_separate_and_labelled_in_order():
    card = tolerance_card()
    assert len(card) == len(CARD_DELTAS)
    assert [name.split("-")[1] for name, _ in card] == [str(i + 1) for i in range(len(CARD_DELTAS))]
    total = card[0][1]
    for _, m in card[1:]:
        total = total + m
    assert len(total.decompose()) == len(CARD_DELTAS)
