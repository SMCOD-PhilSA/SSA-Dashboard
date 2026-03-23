import streamlit as st

def render():
    st.title("Rocket Launch Monitoring")

    st.write("Latest Object: CZ-6A Debris")
    st.write("Orbit Status: Decaying")

    if st.button("Back"):
        st.session_state["page"] = "home"