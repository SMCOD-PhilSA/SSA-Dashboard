import base64
from datetime import datetime, timezone, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from src.services.space_weather_api import get_daily_kp
from src.services.spacetrack_api import get_active_leo_by_country
from src.services.launch_scraper import fetch_china_launches
from src.services.cdm_fetcher import fetch_cdm_data
from src.pages.auth import logout

# ====================== CONFIG ======================
st.set_page_config(
    page_title="Space Dashboard",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ====================== CACHING ======================
@st.cache_data(ttl=1800)  # 30 minutes
def get_kp_data():
    return get_daily_kp()

@st.cache_data(ttl=3600)  # 1 hour
def get_leo_by_country():
    return get_active_leo_by_country()

@st.cache_data(ttl=1800)
def get_china_launches():
    return fetch_china_launches()

@st.cache_data(ttl=600)   # 10 minutes - CDM changes faster
def get_cdm_data():
    return fetch_cdm_data()

# ====================== HELPERS ======================

def get_base64_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def tile(title: str, image_path: str, page_key: str):
    """Clickable image tile"""
    img_b64 = get_base64_image(image_path)
    ext = image_path.rsplit(".", 1)[-1].lower()
    mime = "image/png" if ext == "png" else "image/jpeg"

    st.markdown(
        f"""
        <div style="position: relative; border-radius: 14px; overflow: hidden; cursor: pointer;"
             onclick="document.getElementById('btn_{page_key}').click()">
            <img src="data:{mime};base64,{img_b64}" 
                 style="width:100%; height:220px; object-fit:cover; display:block;">
            <div style="position:absolute; inset:0; 
                        background:linear-gradient(to bottom, rgba(0,0,0,0.1), rgba(0,0,0,0.85));"></div>
            <div style="position:absolute; bottom:20px; left:20px; color:white; 
                        font-size:1.35rem; font-weight:600; text-shadow: 0 2px 4px rgba(0,0,0,0.6);">
                {title}
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
    .cdm-wrap {
        border-radius: 12px;
        overflow: hidden;
        background: white;
        color: black;
        border: 1px solid #ddd;
    }
    .cdm-header {
        display: grid;
        grid-template-columns: 1.3fr 1.35fr 0.9fr 0.8fr 0.8fr;
        padding: 12px 14px;
        font-weight: bold;
        background: #f2f2f2;
        border-bottom: 1px solid #ddd;
    }
    .cdm-row {
        display: grid;
        grid-template-columns: 1.3fr 1.35fr 0.9fr 0.8fr 0.8fr;
        padding: 12px 14px;
        border-bottom: 1px solid #eee;
    }
    .cdm-cell {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="cdm-wrap">
        <div class="cdm-header">
            <div>PRIMARY OBJECT</div>
            <div>SECONDARY OBJECT</div>
            <div>TCA</div>
            <div>PC</div>
            <div>MD (M)</div>
        </div>
    """, unsafe_allow_html=True)

    for _, row in data.iterrows():
        st.markdown(
            f"""
            <div class="cdm-row">
                <div class="cdm-cell">{row['Primary_Object']}</div>
                <div class="cdm-cell">{row['Secondary_Object']}</div>
                <div class="cdm-cell">{format_hours(row['HOURS_TO_TCA'])}</div>
                <div class="cdm-cell">{row['Pc']:.2e}</div>
                <div class="cdm-cell">{int(row['Miss_Distance'])}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ====================== MAIN RENDER ======================

def render():
    user = st.session_state.get("user", {})
    name = user.get("displayName", "User")
    email = user.get("mail") or user.get("userPrincipalName", "")

    # Theme handling
    if "theme" not in st.session_state:
        st.session_state["theme"] = "dark"

    is_dark = st.session_state["theme"] == "dark"
    toggle_label = "☀️ Light Mode" if is_dark else "🌙 Dark Mode"

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

    # ====================== DASHBOARD CHARTS ======================

    top1, top2 = st.columns(2)

    with top1:
        st.subheader("Geomagnetic Storm Forecast")
        days, values = get_kp_data()

        if values:
            df_kp = pd.DataFrame({"Day": days, "Kp Index": values})

            fig = px.bar(
                df_kp,
                x="Day",
                y="Kp Index",
                color="Kp Index",
                color_continuous_scale=["#00cc00", "#ffcc00", "#ff9900", "#ff3333"],
                range_color=[0, 9],
                height=400
            )

            fig.update_traces(texttemplate="%{y:.1f}", textposition="outside", marker_line_width=0)
            fig.update_layout(
                yaxis_title="Kp Index",
                yaxis_range=[0, 9.5],
                xaxis_tickangle=-30,
                margin=dict(l=40, r=20, t=40, b=80),
                coloraxis_showscale=False,
            )

            # Legend annotations
            fig.add_annotation(text="Quiet (<3)", xref="paper", yref="paper", x=0.05, y=1.12, showarrow=False, font=dict(color="#00cc00"))
            fig.add_annotation(text="Unsettled (3–4)", xref="paper", yref="paper", x=0.32, y=1.12, showarrow=False, font=dict(color="#ffcc00"))
            fig.add_annotation(text="Active (5–6)", xref="paper", yref="paper", x=0.62, y=1.12, showarrow=False, font=dict(color="#ff9900"))
            fig.add_annotation(text="Storm (≥7)", xref="paper", yref="paper", x=0.88, y=1.12, showarrow=False, font=dict(color="#ff3333"))

            st.plotly_chart(fig, use_container_width=True)

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
                height=400,
            )

            fig2.update_layout(
                xaxis_title="Number of Active LEO Satellites",
                yaxis_title=None,
                margin=dict(l=20, r=20, t=40, b=60),
            )

            st.plotly_chart(fig2, use_container_width=True)

    # Bottom Section
    bottom1, bottom2 = st.columns(2)

    with bottom1:
        st.subheader("Upcoming China Launches")
        launches, _ = get_china_launches()

        if launches:
            for launch in launches[:5]:
                rocket = clean_rocket_name(launch.get("rocket"))
                date = launch.get("date") or "TBD"
                site = launch.get("site") or "TBD"

                st.markdown(f"""
                <div style="padding: 16px; border-radius: 10px; 
                            background-color: {'#1e1e1e' if is_dark else '#f8f9fa'}; 
                            border-left: 5px solid #00b4d8; margin-bottom: 12px;">
                    <strong>{rocket}</strong><br>
                    <span style="color: #888; font-size: 0.95rem;">{date}</span><br>
                    <small style="color: #666;">{site}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No upcoming launches found.")

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

    t1, t2 = st.columns(2)
    with t1:
        tile("Space Weather Monitoring", "graphics/space_weather.jpg", "space_weather")
    with t2:
        tile("Orbital Debris Reentry", "graphics/reentry.jpg", "reentry")

    t3, t4 = st.columns(2)
    with t3:
        tile("Conjunction Analysis", "graphics/cdm.png", "cdm")
    with t4:
        tile("Rocket Launch Monitoring", "graphics/rocket.jpg", "rocket")