import base64
from datetime import datetime, timezone, timedelta

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.services.space_weather_api import get_daily_kp
from src.services.spacetrack_api import get_active_leo_by_country
from src.services.launch_scraper import fetch_china_launches
from src.services.cdm_fetcher import fetch_cdm_data


def get_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def tile(title, image_path, page_key, height=220):
    img_b64 = get_base64(image_path)
    ext = image_path.rsplit(".", 1)[-1].lower()
    mime = "image/png" if ext == "png" else "image/jpeg"

    components.html(
        f"""
        <html>
        <style>
        body {{margin:0;overflow:hidden;}}
        .tile {{
            height:{height}px;
            border-radius:14px;
            background-image:url("data:{mime};base64,{img_b64}");
            background-size:cover;
            background-position:center;
            position:relative;
        }}
        .overlay {{
            position:absolute;
            inset:0;
            background:linear-gradient(to bottom, rgba(0,0,0,0.0), rgba(0,0,0,0.75));
        }}
        </style>
        <body>
            <div class="tile">
                <div class="overlay"></div>
            </div>
        </body>
        </html>
        """,
        height=height,
    )

    if st.button(f"Open {title}", key=f"btn_{page_key}", use_container_width=True):
        st.session_state["page"] = page_key
        st.query_params["page"] = page_key
        st.rerun()


def clean_rocket_name(text):
    if not text:
        return "TBD"
    for k in ["Unknown Payload", "Demo Flight", "Chang'e"]:
        text = text.replace(k, "")
    return text.strip()


def format_hours(hours):
    if pd.isna(hours):
        return "TBD"
    total_minutes = int(abs(hours) * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d} H {m:02d} M ago" if hours < 0 else f"in {h:02d} H {m:02d} M"


def render_cdm_table(data):
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


def render():
    st.markdown("<style>.block-container { padding-top:0.1rem !important; }</style>", unsafe_allow_html=True)

    FIG_SIZE = (8, 4)

    top1, top2 = st.columns(2)

    with top1:
        st.markdown("### Geomagnetic Storm Forecast")
        days, values = get_daily_kp()

        if values:
            fig, ax = plt.subplots(figsize=FIG_SIZE)
            x = list(range(len(values)))
            bars = ax.bar(x, values)

            colors = ["green" if v < 3 else "yellow" if v < 5 else "orange" if v < 7 else "red" for v in values]
            for b, c in zip(bars, colors):
                b.set_color(c)

            ax.set_ylabel("Kp Index")
            ax.set_xticks(x)
            ax.set_xticklabels(days, rotation=30, ha="right")
            ax.set_ylim(0, 9)
            ax.set_xlim(-0.5, len(values) - 0.5)

            for i, v in enumerate(values):
                ax.text(i, v + 0.2, f"{v:.1f}", ha="center", fontsize=8)

            fig.subplots_adjust(left=0.12, right=0.95, top=0.88, bottom=0.25)
            st.pyplot(fig, use_container_width=True)

    with top2:
        st.markdown("### Countries by Active LEO Satellites")
        labels, values, _ = get_active_leo_by_country()

        if values:
            fig2, ax2 = plt.subplots(figsize=FIG_SIZE)
            ax2.barh(labels, values)

            max_val = max(values)
            ax2.set_xlim(0, max_val * 1.2)

            for i, v in enumerate(values):
                ax2.text(v + max_val * 0.02, i, str(v), va="center")

            fig2.subplots_adjust(left=0.12, right=0.95, top=0.88, bottom=0.25)
            st.pyplot(fig2, use_container_width=True)

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
        st.markdown("### High Risk Conjunctions")

        df, _ = fetch_cdm_data()

        if df is not None and not df.empty:
            df["TCA_UTC"] = pd.to_datetime(df["TCA_UTC"], errors="coerce")
            df["Pc"] = pd.to_numeric(df["Pc"], errors="coerce")
            df["Miss_Distance"] = pd.to_numeric(df["Miss_Distance"], errors="coerce")

            df = df.dropna(subset=["TCA_UTC", "Pc", "Miss_Distance"]).copy()

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            one_week_ago = now - timedelta(days=7)

            df["HOURS_TO_TCA"] = (df["TCA_UTC"] - now).dt.total_seconds() / 3600

            df = df[df["TCA_UTC"] >= one_week_ago]

            tab1, tab2, tab3 = st.tabs(["Nearest TCA", "Highest PC", "Lowest MD"])

            with tab1:
                render_cdm_table(df.sort_values("HOURS_TO_TCA").head(10))

            with tab2:
                render_cdm_table(df.sort_values("Pc", ascending=False).head(10))

            with tab3:
                render_cdm_table(df.sort_values("Miss_Distance").head(10))

        else:
            st.warning("No CDM data available")

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