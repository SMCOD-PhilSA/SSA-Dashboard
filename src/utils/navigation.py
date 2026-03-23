import streamlit as st

def init_navigation():
    if "page" not in st.session_state:
        st.session_state["page"] = "home"

def navigate():
    return st.session_state["page"]