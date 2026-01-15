from __future__ import annotations

from datetime import date

import streamlit as st

from core import io
from core.settings import ToolSettings
from tools.revue_lettrage_balance.logic import run_lettrage


@st.cache_data(show_spinner=False)
def _load_data(uploaded_file) -> io.ParsedData:
    return io.load_csv(uploaded_file)


def render() -> None:
    st.header("Revue lettrage balance")
    st.write(
        "Analyse les écritures clients pour proposer des lettrages, en respectant les règles comptables "
        "et les contraintes de proximité de dates d'échéance."
    )

    uploaded_file = st.file_uploader("Importer un CSV", type=["csv"])

    st.subheader("Paramètres")
    col1, col2 = st.columns(2)
    with col1:
        tolerance_eur = st.number_input("Tolérance (€)", min_value=0.0, value=0.05, step=0.01)
        max_k_lignes_non_rc = st.number_input(
            "Max lignes non-RC par lettrage", min_value=1, value=6, step=1
        )
        max_lignes_par_tiers = st.number_input(
            "Max lignes par tiers", min_value=20, value=200, step=10
        )
    with col2:
        autoriser_multi_rc = st.checkbox("Autoriser multi-RC", value=True)
        max_rc_par_lettrage = st.number_input("Max RC par lettrage", min_value=1, value=2, step=1)
        max_candidats_par_rc = st.number_input(
            "Max candidats par RC", min_value=50, value=500, step=50
        )

    run = st.button("Lancer")

    if not uploaded_file:
        st.info("Veuillez importer un fichier CSV.")
        return

    if not run:
        st.caption("Ajustez les paramètres puis cliquez sur 'Lancer'.")
        return

    with st.spinner("Chargement et analyse..."):
        parsed = _load_data(uploaded_file)
        df = parsed.dataframe

    if parsed.warnings:
        for warning in parsed.warnings:
            st.warning(warning)

    settings = ToolSettings(
        tolerance_eur=tolerance_eur,
        max_k_lignes_non_rc=int(max_k_lignes_non_rc),
        max_lignes_par_tiers=int(max_lignes_par_tiers),
        autoriser_multi_rc=autoriser_multi_rc,
        max_rc_par_lettrage=int(max_rc_par_lettrage),
        max_candidats_par_rc=int(max_candidats_par_rc),
    )

    result = run_lettrage(
        df,
        today=date.today(),
        tolerance_eur=settings.tolerance_eur,
        max_k_lignes_non_rc=settings.max_k_lignes_non_rc,
        max_lignes_par_tiers=settings.max_lignes_par_tiers,
        autoriser_multi_rc=settings.autoriser_multi_rc,
        max_rc_par_lettrage=settings.max_rc_par_lettrage,
        max_candidats_par_rc=settings.max_candidats_par_rc,
    )

    st.subheader("Résultats")
    metrics = result.metrics
    metric_cols = st.columns(4)
    metric_cols[0].metric("Tiers analysés", metrics["tiers_total"])
    metric_cols[1].metric("Candidats", metrics["candidats"])
    metric_cols[2].metric("Lettrages retenus", metrics["lettrages_retenus"])
    metric_cols[3].metric("Temps (s)", metrics["temps_s"])

    lettrages = result.lettrages
    lettrages_df = result.lettrages_df
    lignes_lettrees_df = result.lignes_lettrees
    lignes_restantes_df = result.lignes_restantes

    if lettrages:
        st.dataframe(lettrages_df, use_container_width=True)

        st.subheader("Détails par lettrage")
        for idx, candidate in enumerate(lettrages, start=1):
            lettrage_id = f"LET-{idx:04d}"
            with st.expander(f"{lettrage_id} - {candidate.code_tiers}"):
                lines = df[df["id_ligne"].isin(candidate.rc_ids + candidate.non_rc_ids)].copy()
                st.dataframe(lines, use_container_width=True)

        st.subheader("Exports")
        st.download_button(
            "Télécharger lettrages_synthese.csv",
            lettrages_df.to_csv(index=False).encode("utf-8"),
            file_name="lettrages_synthese.csv",
            mime="text/csv",
        )
        st.download_button(
            "Télécharger lignes_lettrees.csv",
            lignes_lettrees_df.to_csv(index=False).encode("utf-8"),
            file_name="lignes_lettrees.csv",
            mime="text/csv",
        )
    else:
        st.info("Aucun lettrage trouvé avec les paramètres actuels.")

    st.download_button(
        "Télécharger lignes_restantes.csv",
        lignes_restantes_df.to_csv(index=False).encode("utf-8"),
        file_name="lignes_restantes.csv",
        mime="text/csv",
    )
