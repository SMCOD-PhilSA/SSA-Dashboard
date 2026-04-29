import streamlit as st

from src.pages import reentry_event_analyzer
from src.pages import reentry_event_predictor


def render():
    is_dark = st.session_state.get("theme", "dark") == "dark"

    if is_dark:
        sel_bg     = "#0d1b2a"
        sel_text   = "#e6f1f5"
        sel_border = "#1e3a50"
        sel_hover  = "#1a3a52"
        sel_sel    = "#1e4a68"
    else:
        sel_bg     = "#ffffff"
        sel_text   = "#0d2137"
        sel_border = "#c5d8ec"
        sel_hover  = "#e3f0fb"
        sel_sel    = "#cce0f5"

    st.markdown(f"""
    <style>
    /* ── selectbox control ── */
    div[data-baseweb="select"] > div {{
        background-color: {sel_bg} !important;
        color: {sel_text} !important;
        border: 1px solid {sel_border} !important;
    }}
    div[data-baseweb="select"] > div:focus-within {{
        border-color: {sel_border} !important;
        box-shadow: 0 0 0 1px {sel_border} !important;
    }}
    /* selected value text */
    div[data-baseweb="select"] span {{
        color: {sel_text} !important;
    }}
    /* dropdown popover + menu container */
    div[data-baseweb="popover"] > div,
    div[data-baseweb="menu"] {{
        background-color: {sel_bg} !important;
        border: 1px solid {sel_border} !important;
    }}
    /* listbox */
    ul[role="listbox"] {{
        background-color: {sel_bg} !important;
        color: {sel_text} !important;
    }}
    /* each option */
    li[role="option"] {{
        background-color: {sel_bg} !important;
        color: {sel_text} !important;
    }}
    li[role="option"]:hover {{
        background-color: {sel_hover} !important;
    }}
    li[aria-selected="true"] {{
        background-color: {sel_sel} !important;
        color: {sel_text} !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("# Reentry Module")

    if "reentry_view" not in st.session_state:
        st.session_state["reentry_view"] = "Analyzer"

    col1, col2 = st.columns([3, 1])

    with col1:
        if st.button("← Back to Home", key="back_home_reentry"):
            st.query_params["page"] = "home"
            st.session_state["page"] = "home"
            st.rerun()

    with col2:
        view = st.selectbox(
            "View",
            ["Analyzer", "Predictor"],
            index=0 if st.session_state["reentry_view"] == "Analyzer" else 1,
            key="reentry_selector"
        )
        st.session_state["reentry_view"] = view

    st.markdown("---")

    if st.session_state["reentry_view"] == "Analyzer":
        reentry_event_analyzer.render()
    else:
        reentry_event_predictor.render()