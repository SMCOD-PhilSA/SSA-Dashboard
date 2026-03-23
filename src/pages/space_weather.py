import streamlit as st
import matplotlib.pyplot as plt

from src.services.space_weather_api import get_daily_kp, get_kp_index


def render():
    st.title("Space Weather")

    kp_now = get_kp_index()

    st.metric("Current Kp Index", kp_now["kp"])
    st.write("Condition:", kp_now["status"])

    days, values = get_daily_kp()

    if values:
        fig, ax = plt.subplots(figsize=(7, 3))

        bars = ax.bar(days, values)

        for i, v in enumerate(values):
            if v < 3:
                bars[i].set_color("green")
            elif v < 5:
                bars[i].set_color("yellow")
            elif v < 7:
                bars[i].set_color("orange")
            else:
                bars[i].set_color("red")

        ax.set_ylim(0, 9)
        ax.set_ylabel("Kp Index")

        for i, v in enumerate(values):
            ax.text(i, v + 0.2, f"{v:.1f}", ha='center', fontsize=8)

        fig.tight_layout()

        st.pyplot(fig)

    else:
        st.warning("No data available")