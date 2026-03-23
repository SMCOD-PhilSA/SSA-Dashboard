import streamlit as st

def render():
    st.title("Conjunction Data Messages")

    st.write("Active CDMs: 3")
    st.write("Max Collision Probability: 2.3e-4")

    if st.button("Back"):
        st.session_state["page"] = "home"