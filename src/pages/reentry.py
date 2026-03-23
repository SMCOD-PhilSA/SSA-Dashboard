import streamlit as st

def render():
    st.title("Orbital Debris Reentry")

    st.write("Object ID: 54231")
    st.write("Window: 03:39 – 04:27 UTC")
    st.write("Uncertainty: ±24 minutes")

    if st.button("Back"):
        st.session_state["page"] = "home"