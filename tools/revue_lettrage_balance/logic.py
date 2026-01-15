from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from datetime import date
from typing import Iterable

import pandas as pd

from core.utils import cents_to_eur, score_proximite_dates


@dataclass(frozen=True)
class LettrageCandidate:
    code_tiers: str
    raison_sociale: str
    rc_ids: tuple[int, ...]
    non_rc_ids: tuple[int, ...]
    sum_cents: int
    ecart_cents: int
    score_proximite_date: int
    nb_lignes: int
    nb_rc: int
    date_min: date
    date_max: date
    no_facture_resume: str
    numero_ecriture_resume: str


@dataclass(frozen=True)
class LettrageResult:
    lettrages: list[LettrageCandidate]
    lettrages_df: pd.DataFrame
    lignes_lettrees: pd.DataFrame
    lignes_restantes: pd.DataFrame
    metrics: dict[str, int | float]


def filter_base(df: pd.DataFrame, today: date) -> pd.DataFrame:
    return df[
        (df["Date d'échéance"].notna())
        & (df["Date d'échéance"] <= today)
        & (df["Code du compte général"] == "41100000")
    ].copy()


def reduce_tier_lines(df: pd.DataFrame, max_lines: int) -> pd.DataFrame:
    if len(df) <= max_lines:
        return df
    rc_mask = df["Type de pièce"].eq("RC")
    rc_df = df[rc_mask]
    non_rc_df = df[~rc_mask].copy()
    non_rc_df["rank_date"] = non_rc_df["Date d'échéance"].fillna(date.today())
    non_rc_df["rank_abs"] = non_rc_df["montant_cents"].abs()
    non_rc_df = non_rc_df.sort_values(["rank_date", "rank_abs"], ascending=[True, False])
    kept_non_rc = non_rc_df.head(max_lines - len(rc_df)).drop(columns=["rank_date", "rank_abs"])
    return pd.concat([rc_df, kept_non_rc], ignore_index=True)


def should_skip_tier(df: pd.DataFrame, tolerance_cents: int) -> bool:
    negative = df[df["montant_cents"] < 0]
    if negative.empty:
        return True
    positives = df[df["montant_cents"] > 0]
    if positives.empty:
        return True
    min_positive = positives["montant_cents"].min()
    sum_negative = negative["montant_cents"].abs().sum()
    return min_positive > sum_negative + tolerance_cents


def _find_combinations(
    amounts: list[tuple[int, int]],
    target: int,
    tolerance: int,
    max_k: int,
    max_results: int,
) -> list[list[int]]:
    results: list[list[int]] = []
    non_negative = all(amount >= 0 for _, amount in amounts)

    def dfs(start: int, current_ids: list[int], current_sum: int) -> None:
        if len(results) >= max_results:
            return
        if current_ids and abs(current_sum - target) <= tolerance:
            results.append(list(current_ids))
        if len(current_ids) >= max_k:
            return
        for i in range(start, len(amounts)):
            line_id, amount = amounts[i]
            new_sum = current_sum + amount
            if non_negative and new_sum > target + tolerance:
                continue
            dfs(i + 1, current_ids + [line_id], new_sum)

    dfs(0, [], 0)
    return results


def build_candidates_for_tier(
    df: pd.DataFrame,
    tolerance_cents: int,
    max_k: int,
    allow_multi_rc: bool,
    max_rc_per_lettrage: int,
    max_candidates_per_rc: int,
) -> list[LettrageCandidate]:
    if df.empty:
        return []
    code_tiers = str(df["Code Tiers"].iloc[0])
    raison_sociale = str(df["Raison sociale"].iloc[0])

    if should_skip_tier(df, tolerance_cents):
        return []

    rc_df = df[(df["Type de pièce"] == "RC") & (df["montant_cents"] < 0)]
    non_rc_df = df[df["Type de pièce"] != "RC"]
    if rc_df.empty or non_rc_df.empty:
        return []

    rc_groups: list[list[pd.Series]] = []
    rc_rows = [row for _, row in rc_df.iterrows()]
    for row in rc_rows:
        rc_groups.append([row])
    if allow_multi_rc and max_rc_per_lettrage >= 2:
        for row_a, row_b in itertools.combinations(rc_rows, 2):
            rc_groups.append([row_a, row_b])

    non_rc_amounts = [(int(row.id_ligne), int(row.montant_cents)) for _, row in non_rc_df.iterrows()]
    candidates: list[LettrageCandidate] = []

    for rc_group in rc_groups:
        rc_ids = tuple(int(row.id_ligne) for row in rc_group)
        rc_sum = sum(int(row.montant_cents) for row in rc_group)
        target = -rc_sum
        if target <= 0:
            continue
        combos = _find_combinations(
            non_rc_amounts,
            target=target,
            tolerance=tolerance_cents,
            max_k=max_k,
            max_results=max_candidates_per_rc,
        )
        for combo in combos:
            non_rc_ids = tuple(combo)
            selected_df = df[df["id_ligne"].isin(rc_ids + non_rc_ids)]
            sum_cents = int(selected_df["montant_cents"].sum())
            ecart_cents = abs(sum_cents)
            if ecart_cents > tolerance_cents:
                continue
            rc_dates = [row["Date d'échéance"] for _, row in selected_df.iterrows() if row["Type de pièce"] == "RC"]
            non_rc_dates = [
                row["Date d'échéance"] for _, row in selected_df.iterrows() if row["Type de pièce"] != "RC"
            ]
            score = score_proximite_dates(non_rc_dates, rc_dates)
            date_min = selected_df["Date d'échéance"].min()
            date_max = selected_df["Date d'échéance"].max()
            no_facture = ", ".join(selected_df["No facture"].astype(str).unique())
            numero_ecriture = ", ".join(selected_df["Numéro d'écriture"].astype(str).unique())
            candidates.append(
                LettrageCandidate(
                    code_tiers=code_tiers,
                    raison_sociale=raison_sociale,
                    rc_ids=rc_ids,
                    non_rc_ids=non_rc_ids,
                    sum_cents=sum_cents,
                    ecart_cents=ecart_cents,
                    score_proximite_date=score,
                    nb_lignes=len(selected_df),
                    nb_rc=len(rc_ids),
                    date_min=date_min,
                    date_max=date_max,
                    no_facture_resume=no_facture,
                    numero_ecriture_resume=numero_ecriture,
                )
            )
    return candidates


def select_best_candidates_by_rc(candidates: Iterable[LettrageCandidate]) -> dict[int, LettrageCandidate]:
    best: dict[int, LettrageCandidate] = {}
    for candidate in candidates:
        for rc_id in candidate.rc_ids:
            existing = best.get(rc_id)
            if existing is None:
                best[rc_id] = candidate
                continue
            if _is_better_candidate(candidate, existing):
                best[rc_id] = candidate
    return best


def _is_better_candidate(a: LettrageCandidate, b: LettrageCandidate) -> bool:
    return (
        a.score_proximite_date,
        a.ecart_cents,
        a.nb_lignes,
    ) < (
        b.score_proximite_date,
        b.ecart_cents,
        b.nb_lignes,
    )


def resolve_candidates(best_candidates: Iterable[LettrageCandidate]) -> list[LettrageCandidate]:
    selected: list[LettrageCandidate] = []
    used_lines: set[int] = set()
    sorted_candidates = sorted(
        best_candidates,
        key=lambda cand: (cand.score_proximite_date, cand.ecart_cents, cand.nb_lignes),
    )
    for candidate in sorted_candidates:
        candidate_lines = set(candidate.rc_ids + candidate.non_rc_ids)
        if candidate_lines & used_lines:
            continue
        selected.append(candidate)
        used_lines.update(candidate_lines)
    return selected


def build_outputs(
    df: pd.DataFrame,
    selected: list[LettrageCandidate],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lettrage_rows = []
    lignes_lettrees_rows = []
    used_lines: set[int] = set()

    for idx, candidate in enumerate(selected, start=1):
        lettrage_id = f"LET-{idx:04d}"
        lines = df[df["id_ligne"].isin(candidate.rc_ids + candidate.non_rc_ids)].copy()
        lines["id_lettrage"] = lettrage_id
        lignes_lettrees_rows.append(lines)
        used_lines.update(lines["id_ligne"].tolist())
        lettrage_rows.append(
            {
                "id_lettrage": lettrage_id,
                "Code Tiers": candidate.code_tiers,
                "Raison sociale": candidate.raison_sociale,
                "nb_lignes": candidate.nb_lignes,
                "somme": cents_to_eur(candidate.sum_cents),
                "ecart": cents_to_eur(candidate.ecart_cents),
                "nb_rc": candidate.nb_rc,
                "date_echeance_min": candidate.date_min,
                "date_echeance_max": candidate.date_max,
                "score_proximite_date": candidate.score_proximite_date,
                "no_facture": candidate.no_facture_resume,
                "numero_ecriture": candidate.numero_ecriture_resume,
                "ids_lignes": ",".join(map(str, candidate.rc_ids + candidate.non_rc_ids)),
            }
        )

    lettrages_df = pd.DataFrame(lettrage_rows)
    lignes_lettrees_df = pd.concat(lignes_lettrees_rows, ignore_index=True) if lignes_lettrees_rows else df.head(0)
    lignes_restantes_df = df[~df["id_ligne"].isin(used_lines)].copy()
    return lettrages_df, lignes_lettrees_df, lignes_restantes_df


def run_lettrage(
    df: pd.DataFrame,
    today: date,
    tolerance_eur: float,
    max_k_lignes_non_rc: int,
    max_lignes_par_tiers: int,
    autoriser_multi_rc: bool,
    max_rc_par_lettrage: int,
    max_candidats_par_rc: int,
) -> LettrageResult:
    start = time.perf_counter()
    tolerance_cents = int(round(tolerance_eur * 100))

    filtered_df = filter_base(df, today)
    tiers_total = filtered_df["Code Tiers"].nunique()
    candidates: list[LettrageCandidate] = []

    for _, tier_df in filtered_df.groupby("Code Tiers"):
        reduced_df = reduce_tier_lines(tier_df, max_lignes_par_tiers)
        tier_candidates = build_candidates_for_tier(
            reduced_df,
            tolerance_cents=tolerance_cents,
            max_k=max_k_lignes_non_rc,
            allow_multi_rc=autoriser_multi_rc,
            max_rc_per_lettrage=max_rc_par_lettrage,
            max_candidates_per_rc=max_candidats_par_rc,
        )
        candidates.extend(tier_candidates)

    best_by_rc = select_best_candidates_by_rc(candidates)
    selected = resolve_candidates(best_by_rc.values())
    lettrages_df, lignes_lettrees_df, lignes_restantes_df = build_outputs(filtered_df, selected)

    duration = round(time.perf_counter() - start, 3)
    metrics = {
        "tiers_total": tiers_total,
        "candidats": len(candidates),
        "lettrages_retenus": len(selected),
        "temps_s": duration,
    }

    return LettrageResult(
        lettrages=selected,
        lettrages_df=lettrages_df,
        lignes_lettrees=lignes_lettrees_df,
        lignes_restantes=lignes_restantes_df,
        metrics=metrics,
    )
