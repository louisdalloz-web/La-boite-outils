from datetime import date

import pandas as pd

from tools.revue_lettrage_balance.logic import (
    LettrageCandidate,
    run_lettrage,
    select_best_candidates_by_rc,
)


def _sample_df():
    data = [
        {
            "id_ligne": 0,
            "Code Société": "A",
            "No facture": "F1",
            "Code Tiers": "T1",
            "Raison sociale": "Client A",
            "Libellé écriture": "Facture",
            "Type de pièce": "FV",
            "Date facture": date(2024, 1, 1),
            "Date d'échéance": date(2024, 1, 10),
            "montant_cents": 10000,
            "montant_eur": 100.0,
            "Devise comptabilisation": "EUR",
            "Code du compte général": "41100000",
            "Numéro d'écriture": "E1",
        },
        {
            "id_ligne": 1,
            "Code Société": "A",
            "No facture": "RC1",
            "Code Tiers": "T1",
            "Raison sociale": "Client A",
            "Libellé écriture": "Reglement",
            "Type de pièce": "RC",
            "Date facture": date(2024, 1, 5),
            "Date d'échéance": date(2024, 1, 15),
            "montant_cents": -10000,
            "montant_eur": -100.0,
            "Devise comptabilisation": "EUR",
            "Code du compte général": "41100000",
            "Numéro d'écriture": "E2",
        },
    ]
    return pd.DataFrame(data)


def test_select_best_candidate_by_rc():
    candidate_a = LettrageCandidate(
        code_tiers="T1",
        raison_sociale="Client A",
        rc_ids=(1,),
        non_rc_ids=(0,),
        sum_cents=0,
        ecart_cents=0,
        score_proximite_date=5,
        nb_lignes=2,
        nb_rc=1,
        date_min=date(2024, 1, 10),
        date_max=date(2024, 1, 15),
        no_facture_resume="F1",
        numero_ecriture_resume="E1",
    )
    candidate_b = LettrageCandidate(
        code_tiers="T1",
        raison_sociale="Client A",
        rc_ids=(1,),
        non_rc_ids=(0,),
        sum_cents=0,
        ecart_cents=0,
        score_proximite_date=2,
        nb_lignes=2,
        nb_rc=1,
        date_min=date(2024, 1, 10),
        date_max=date(2024, 1, 15),
        no_facture_resume="F1",
        numero_ecriture_resume="E1",
    )
    best = select_best_candidates_by_rc([candidate_a, candidate_b])
    assert best[1] == candidate_b


def test_run_lettrage_basic():
    df = _sample_df()
    result = run_lettrage(
        df,
        today=date(2024, 2, 1),
        tolerance_eur=0.05,
        max_k_lignes_non_rc=2,
        max_lignes_par_tiers=200,
        autoriser_multi_rc=True,
        max_rc_par_lettrage=2,
        max_candidats_par_rc=50,
    )
    assert result.metrics["lettrages_retenus"] == 1
    assert len(result.lignes_lettrees) == 2
    assert result.lignes_restantes.empty
