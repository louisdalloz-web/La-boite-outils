from __future__ import annotations

import importlib

import streamlit as st


TOOLS = {
    "Revue lettrage balance": "tools.revue_lettrage_balance.ui",
}


st.set_page_config(page_title="Boîte à outils", layout="wide")

st.sidebar.title("Boîte à outils")
selected_tool = st.sidebar.selectbox("Choisir un outil", list(TOOLS.keys()))

module_path = TOOLS[selected_tool]
module = importlib.import_module(module_path)
module.render()
