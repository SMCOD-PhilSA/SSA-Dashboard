import base64
from datetime import datetime, timezone, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
import matplotlib as plt

from src.services.space_weather_api import get_daily_kp
from src.services.spacetrack_api import get_active_leo_by_country
from src.services.launch_scraper import fetch_china_launches
from src.services.cdm_fetcher import fetch_cdm_data
from src.pages.auth import logout

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Space Dashboard",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ====================== CACHING ======================
@st.cache_data(ttl=1800)
def get_kp_data():
    return get_daily_kp()

@st.cache_data(ttl=3600)
def get_leo_by_country():
    return get_active_leo_by_country()

@st.cache_data(ttl=1800)
def get_china_launches():
    return fetch_china_launches()

@st.cache_data(ttl=600)
def get_cdm_data():
    return fetch_cdm_data()

# ====================== HELPERS ======================

def get_base64_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def tile(title: str, image_path: str, page_key: str):
    img_b64 = get_base64_image(image_path)
    ext = image_path.rsplit(".", 1)[-1].lower()
    mime = "image/png" if ext == "png" else "image/jpeg"

    st.markdown(
        f"""
        <div style="position: relative; border-radius: 12px; overflow: hidden; 
                    border: 1px solid #ddd; margin-bottom: 8px;">
            <img src="data:{mime};base64,{img_b64}" 
                 style="width:100%; height:210px; object-fit:cover;">
            <div style="position:absolute; bottom:0; left:0; right:0; 
                        background:linear-gradient(transparent, rgba(0,0,0,0.75)); 
                        padding: 20px 16px 16px;">
                <h4 style="color:white; margin:0; font-size:1.25rem;">{title}</h4>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(f"Open {title}", key=f"btn_{page_key}", use_container_width=True):
        st.session_state["page"] = page_key
        st.query_params["page"] = page_key
        st.rerun()


def clean_rocket_name(text: str) -> str:
    if not text:
        return "TBD"
    for k in ["Unknown Payload", "Demo Flight", "Chang'e"]:
        text = text.replace(k, "")
    return text.strip()


def format_hours(hours: float) -> str:
    if pd.isna(hours):
        return "TBD"
    total_minutes = int(abs(hours) * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d} H {m:02d} M ago" if hours < 0 else f"in {h:02d} H {m:02d} M"


def render_cdm_table(data: pd.DataFrame):
    st.markdown("""
    <style>
    .cdm-table { border-collapse: collapse; width: 100%; }
    .cdm-table th, .cdm-table td { 
        padding: 12px 10px; 
        text-align: left; 
        border-bottom: 1px solid #ddd;
    }
    .cdm-table th { background-color: #f8f9fa; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

    html = '<table class="cdm-table"><thead><tr>'
    headers = ["Primary Object", "Secondary Object", "TCA", "Pc", "Miss Distance (m)"]
    for h in headers:
        html += f"<th>{h}</th>"
    html += "</tr></thead><tbody>"

    for _, row in data.iterrows():
        html += f"""
        <tr>
            <td>{row['Primary_Object']}</td>
            <td>{row['Secondary_Object']}</td>
            <td>{format_hours(row['HOURS_TO_TCA'])}</td>
            <td>{row['Pc']:.2e}</td>
            <td>{int(row['Miss_Distance'])}</td>
        </tr>
        """
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)


# ====================== MAIN RENDER ======================
def render():
    user = st.session_state.get("user", {})
    name = user.get("displayName", "User")
    email = user.get("mail") or user.get("userPrincipalName", "")

    if "theme" not in st.session_state:
        st.session_state["theme"] = "dark"

    is_dark = st.session_state["theme"] == "dark"
    toggle_label = "☀️ Light Mode" if is_dark else "🌙 Dark Mode"

    # Header
    col1, col2, col3 = st.columns([6, 2, 2])
    with col1:
        st.markdown(f"**{name}**  \n{email}")
    with col2:
        if st.button(toggle_label, use_container_width=True):
            st.session_state["theme"] = "light" if is_dark else "dark"
            st.rerun()
    with col3:
        if st.button("Sign Out", use_container_width=True):
            logout()
            st.rerun()

    st.divider()

    # ====================== DASHBOARD ======================
    top1, top2 = st.columns(2)

    with top1:
        st.subheader("Geomagnetic Storm Forecast")
        days, values = get_kp_data()

        if values:
            df_kp = pd.DataFrame({"Day": days, "Kp Index": values})

            fig1 = px.bar(
                df_kp,
                x="Day",
                y="Kp Index",
                color="Kp Index",
                color_continuous_scale=["green", "yellow", "orange", "red"],
                range_color=[0, 9],
                height=380,
            )

            # Apply transparent background
            fig1.update_layout({
                'plot_bgcolor': 'rgba(0, 0, 0, 0)',
                'paper_bgcolor': 'rgba(0, 0, 0, 0)',
            })

            fig1.update_layout(
                yaxis_range=[0, 9.5],
                xaxis_tickangle=-30,
                margin=dict(t=20, b=60),
                coloraxis_showscale=False,
            )

            st.plotly_chart(fig1, use_container_width=True)

    with top2:
        st.subheader("Countries by Active LEO Satellites")
        labels, values, _ = get_leo_by_country()

        if values:
            df_leo = pd.DataFrame({"Country": labels, "Satellites": values})

            fig2 = px.bar(
                df_leo,
                x="Satellites",
                y="Country",
                orientation='h',
                color="Satellites",
                color_continuous_scale=px.colors.sequential.Blues_r,
                height=380,
            )

            # Apply transparent background
            fig2.update_layout({
                'plot_bgcolor': 'rgba(0, 0, 0, 0)',
                'paper_bgcolor': 'rgba(0, 0, 0, 0)',
            })

            fig2.update_layout(margin=dict(t=20, b=40))

            st.plotly_chart(fig2, use_container_width=True)

    # Bottom Row
    bottom1, bottom2 = st.columns(2)

    with bottom1:
        st.markdown("### Upcoming Launches")
        launches, _ = fetch_china_launches()

        if launches:
            fig3, ax3 = plt.subplots(figsize=FIG_SIZE)
            ax3.axis("off")

            y = 0.9
            for i, launch in enumerate(launches[:4]):
                rocket = clean_rocket_name(launch.get("rocket"))
                date = launch.get("date") or "TBD"
                site = launch.get("site") or "TBD"

                ax3.text(0.02, y, rocket, fontsize=12, fontweight="bold", transform=ax3.transAxes)
                ax3.text(0.02, y - 0.07, date, fontsize=10, transform=ax3.transAxes)
                ax3.text(0.02, y - 0.13, site, fontsize=9, color="#444", transform=ax3.transAxes)

                if i < 3:
                    ax3.plot([0.02, 0.98], [y - 0.17, y - 0.17], transform=ax3.transAxes)

                y -= 0.23

            st.pyplot(fig3, use_container_width=True)

    with bottom2:
        st.subheader("High Risk Conjunctions")
        df_raw, _ = get_cdm_data()

        if df_raw is not None and not df_raw.empty:
            df = df_raw.copy()
            df["TCA_UTC"] = pd.to_datetime(df["TCA_UTC"], errors="coerce")
            df["Pc"] = pd.to_numeric(df["Pc"], errors="coerce")
            df["Miss_Distance"] = pd.to_numeric(df["Miss_Distance"], errors="coerce")

            df = df.dropna(subset=["TCA_UTC", "Pc", "Miss_Distance"]).copy()

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            df["HOURS_TO_TCA"] = (df["TCA_UTC"] - now).dt.total_seconds() / 3600
            df = df[df["TCA_UTC"] >= (now - timedelta(days=7))]

            tab1, tab2, tab3 = st.tabs(["Nearest TCA", "Highest PC", "Lowest MD"])

            with tab1:
                render_cdm_table(df.sort_values("HOURS_TO_TCA").head(10))
            with tab2:
                render_cdm_table(df.sort_values("Pc", ascending=False).head(10))
            with tab3:
                render_cdm_table(df.sort_values("Miss_Distance").head(10))
        else:
            st.warning("No CDM data available at the moment.")

    # Navigation Tiles
    st.divider()

    col_tile1, col_tile2 = st.columns(2)
    with col_tile1:
        tile("Space Weather Monitoring", "graphics/space_weather.jpg", "space_weather")
    with col_tile2:
        tile("Orbital Debris Reentry", "graphics/reentry.jpg", "reentry")

    col_tile3, col_tile4 = st.columns(2)
    with col_tile3:
        tile("Conjunction Analysis", "graphics/cdm.png", "cdm")
    with col_tile4:
        tile("Rocket Launch Monitoring", "graphics/rocket.jpg", "rocket")