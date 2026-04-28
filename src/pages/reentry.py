import streamlit as st

from src.pages import reentry_event_analyzer
from src.pages import reentry_event_predictor


def render():

    st.markdown("""
    <style>

    /* Select input */
    div[data-baseweb="select"] > div {
        background-color: var(--background-color) !important;
        color: var(--text-color) !important;
        border: 1px solid var(--secondary-background-color) !important;
    }

    /* Dropdown container */
    div[data-baseweb="popover"] {
        background-color: var(--background-color) !important;
    }

    /* Dropdown list */
    ul[role="listbox"] {
        background-color: var(--background-color) !important;
        color: var(--text-color) !important;
    }

    /* Each option */
    li[role="option"] {
        background-color: var(--background-color) !important;
        color: var(--text-color) !important;
    }

    /* Hover */
    li[role="option"]:hover {
        background-color: var(--secondary-background-color) !important;
    }

    /* Selected */
    li[aria-selected="true"] {
        background-color: var(--secondary-background-color) !important;
        color: var(--text-color) !important;
    }

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