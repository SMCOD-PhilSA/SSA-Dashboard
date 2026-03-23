import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.components.header import render_header
from src.utils.navigation import init_navigation, navigate

from src.pages import home
from src.pages import space_weather
from src.pages import reentry
from src.pages import cdm
from src.pages import rocket

st.set_page_config(layout="wide")

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