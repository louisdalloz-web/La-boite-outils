from datetime import date

from core.utils import score_proximite_dates, to_cents


def test_to_cents_handles_commas_and_spaces():
    assert to_cents("1 234,56") == 123456
    assert to_cents("10.50") == 1050


def test_score_proximite_dates():
    rc_dates = [date(2024, 1, 10)]
    non_rc_dates = [date(2024, 1, 12), date(2024, 1, 9)]
    assert score_proximite_dates(non_rc_dates, rc_dates) == 3
