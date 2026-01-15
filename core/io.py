from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from typing import Iterable

import pandas as pd

from core.utils import to_cents


REQUIRED_COLUMNS = [
    "Code Société",
    "No facture",
    "Code Tiers",
    "Raison sociale",
    "Libellé écriture",
    "Type de pièce",
    "Date facture",
    "Date d'échéance",
    "Montant Signé",
    "Devise comptabilisation",
    "Code du compte général",
    "Numéro d'écriture",
]

DATE_COLUMNS = ["Date facture", "Date d'échéance"]


@dataclass(frozen=True)
class ParsedData:
    dataframe: pd.DataFrame
    warnings: list[str]


def detect_separator(sample: str) -> str:
    return ";" if sample.count(";") >= sample.count(",") else ","


def _decode_sample(raw: bytes) -> str:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _read_csv_with_fallback(raw: bytes, sep: str) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(io.BytesIO(raw), sep=sep, dtype=str, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return pd.read_csv(io.BytesIO(raw), sep=sep, dtype=str)


def _validate_columns(columns: Iterable[str]) -> list[str]:
    missing = [col for col in REQUIRED_COLUMNS if col not in columns]
    return missing


def load_csv(file: io.BytesIO | str) -> ParsedData:
    if hasattr(file, "getvalue"):
        raw = file.getvalue()
    else:
        with open(file, "rb") as handle:
            raw = handle.read()
    sample = _decode_sample(raw).splitlines()[0]
    sep = detect_separator(sample)
    df = _read_csv_with_fallback(raw, sep=sep)
    missing = _validate_columns(df.columns)
    if missing:
        raise ValueError(
            "Colonnes manquantes: " + ", ".join(missing)
        )

    warnings: list[str] = []
    for column in DATE_COLUMNS:
        df[column] = pd.to_datetime(df[column], dayfirst=True, errors="coerce")
        if df[column].isna().any():
            warnings.append(f"Dates invalides détectées dans la colonne {column}.")

    df["Montant Signé"] = df["Montant Signé"].apply(to_cents)
    df = df.rename(columns={"Montant Signé": "montant_cents"})
    df["montant_eur"] = df["montant_cents"].astype(float) / 100.0
    df["Code du compte général"] = df["Code du compte général"].astype(str)
    df = df.reset_index(drop=True)
    df.insert(0, "id_ligne", df.index.astype(int))
    df["Date d'échéance"] = df["Date d'échéance"].dt.date
    df["Date facture"] = df["Date facture"].dt.date
    df["date_import"] = date.today()

    return ParsedData(dataframe=df, warnings=warnings)
