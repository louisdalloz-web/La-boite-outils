from __future__ import annotations

from datetime import date
from typing import Iterable


def to_cents(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(round(float(value) * 100))
    raw = str(value).strip()
    if raw == "":
        return 0
    cleaned = raw.replace(" ", "").replace("\u00a0", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return int(round(float(cleaned) * 100))
    except ValueError as exc:
        raise ValueError(f"Montant invalide: {value}") from exc


def cents_to_eur(value_cents: int) -> float:
    return round(value_cents / 100.0, 2)


def score_proximite_dates(non_rc_dates: Iterable[date], rc_dates: Iterable[date]) -> int:
    rc_list = list(rc_dates)
    if not rc_list:
        return 0
    total = 0
    for piece_date in non_rc_dates:
        diffs = [abs((piece_date - rc_date).days) for rc_date in rc_list]
        total += min(diffs) if diffs else 0
    return total
