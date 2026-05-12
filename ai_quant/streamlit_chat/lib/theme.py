from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp { background-color: #f8fafc; }
        [data-testid="stChatMessageContainer"] {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 8px;
            border: 1px solid #e2e8f0;
        }
        [data-testid="stChatInputContainer"] {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            padding: 12px 24px;
            border-top: 1px solid #e2e8f0;
            z-index: 100;
        }
        .stButton > button {
            border-radius: 8px;
            font-weight: 500;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
