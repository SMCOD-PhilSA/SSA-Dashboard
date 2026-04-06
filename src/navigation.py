import streamlit as st

def init_navigation():
    if "page" not in st.session_state:
        st.session_state.page = "home"
    
    page_from_query = st.query_params.get("page", None)
    if page_from_query and page_from_query != st.session_state.get("page"):
        st.session_state.page = page_from_query

def navigate():
    return st.session_state.get("page", "home")