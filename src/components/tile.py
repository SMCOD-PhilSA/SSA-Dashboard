import streamlit as st

def tile(title, page_key):
    if st.button(title, key=page_key, use_container_width=True):
        st.session_state["page"] = page_key