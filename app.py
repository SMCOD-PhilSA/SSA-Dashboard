import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(layout="wide", initial_sidebar_state="collapsed")

from src.pages.auth import require_login, logout
from src.components.header import render_header
from src.utils.navigation import init_navigation, navigate
from src.pages import home, space_weather, reentry, cdm, rocket


if not require_login():
    st.stop()


init_navigation()
render_header()

page = navigate()

if page == "home":
    home.render()
elif page == "space_weather":
    space_weather.render()
elif page == "reentry":
    reentry.render()
elif page == "cdm":
    cdm.render()
elif page == "rocket":
    rocket.render()

st.markdown("</div>", unsafe_allow_html=True)