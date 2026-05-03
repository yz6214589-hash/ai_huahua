from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    st.set_page_config(page_title="AI Quant Chat", page_icon="C", layout="wide")
    st.markdown(
        """
        <style>
        .stApp { background-color: #f9fafb; }
        .block-container { padding-top: 1.5rem; }
        h1,h2,h3 { color: #18181b; }
        </style>
        """,
        unsafe_allow_html=True,
    )
