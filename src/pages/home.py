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
from src.pages.auth import logout


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


def render_cdm_table(data, is_dark):
    if is_dark:
        wrap_bg     = "#0d1b2a"
        wrap_border = "#1e3a50"
        hdr_bg      = "#0a1520"
        hdr_text    = "#7a9bb5"
        row_border  = "#1a2e42"
        cell_text   = "#e6f1f5"
    else:
        wrap_bg     = "#ffffff"
        wrap_border = "#d0d7de"
        hdr_bg      = "#f2f6fa"
        hdr_text    = "#4a6b85"
        row_border  = "#e8edf2"
        cell_text   = "#0d2137"

    st.markdown(f"""
    <style>
    .cdm-wrap {{
        border-radius: 12px;
        overflow: hidden;
        background: {wrap_bg};
        border: 1px solid {wrap_border};
    }}
    .cdm-header {{
        display: grid;
        grid-template-columns: 1.3fr 1.35fr 0.9fr 0.8fr 0.8fr;
        padding: 10px 14px;
        font-weight: 700;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        background: {hdr_bg};
        color: {hdr_text};
        border-bottom: 1px solid {wrap_border};
    }}
    .cdm-row {{
        display: grid;
        grid-template-columns: 1.3fr 1.35fr 0.9fr 0.8fr 0.8fr;
        padding: 10px 14px;
        border-bottom: 1px solid {row_border};
        color: {cell_text};
        font-size: 0.85rem;
    }}
    .cdm-row:last-child {{
        border-bottom: none;
    }}
    .cdm-cell {{
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="cdm-wrap">
        <div class="cdm-header">
            <div>Primary Object</div>
            <div>Secondary Object</div>
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
    is_dark = st.session_state.get("theme", "dark") == "dark"

    user  = st.session_state.get("user", {})
    name  = user.get("displayName", "User")
    email = user.get("mail") or user.get("userPrincipalName", "")

    toggle_label = "☀️  Light Mode" if is_dark else "🌙  Dark Mode"
    next_theme   = "light" if is_dark else "dark"

    # ── theme-aware matplotlib style ─────────────────────────────────────────
    if is_dark:
        plt.style.use("dark_background")
        fig_fc   = "#0d1b2a"   # figure facecolor
        ax_fc    = "#0d1b2a"   # axes facecolor
        txt_col  = "#e6f1f5"
        grid_col = "#1e3a50"
    else:
        plt.style.use("default")
        fig_fc   = "#ffffff"
        ax_fc    = "#ffffff"
        txt_col  = "#0d2137"
        grid_col = "#e0e8f0"

    col1, col2, col3 = st.columns([6, 2, 2])
    with col1:
        st.markdown(f"**{name}**  \n{email}")
    with col2:
        if st.button(toggle_label, use_container_width=True, key="home_theme"):
            st.session_state["theme"] = next_theme
            st.rerun()
    with col3:
        if st.button("🚪  Sign Out", use_container_width=True, key="home_signout"):
            logout()
            st.rerun()

    st.markdown("---")
    st.markdown("<style>.block-container { padding-top:0.1rem !important; }</style>",
                unsafe_allow_html=True)

    FIG_SIZE = (8, 4)

    # ── Geomagnetic Storm Forecast ────────────────────────────────────────────
    top1, top2 = st.columns(2)

    with top1:
        st.markdown("### Geomagnetic Storm Forecast")
        days, values = get_daily_kp()

        if values:
            fig, ax = plt.subplots(figsize=FIG_SIZE, facecolor=fig_fc)
            ax.set_facecolor(ax_fc)

            x    = list(range(len(values)))
            bars = ax.bar(x, values)

            colors = [
                "green" if v < 3 else
                "yellow" if v < 5 else
                "orange" if v < 7 else
                "red"
                for v in values
            ]
            for b, c in zip(bars, colors):
                b.set_color(c)

            ax.set_ylabel("Kp Index", color=txt_col)
            ax.tick_params(colors=txt_col)
            ax.set_xticks(x)
            ax.set_xticklabels(days, rotation=30, ha="right", color=txt_col)
            ax.set_ylim(0, 9)
            ax.set_xlim(-0.5, len(values) - 0.5)
            ax.spines[["top","right","left","bottom"]].set_color(grid_col)

            for i, v in enumerate(values):
                ax.text(i, v + 0.2, f"{v:.1f}", ha="center", fontsize=8, color=txt_col)

            from matplotlib.patches import Patch
            ax.legend(handles=[
                Patch(color="green",  label="Quiet (<3)"),
                Patch(color="yellow", label="Unsettled (3–4)"),
                Patch(color="orange", label="Active (5–6)"),
                Patch(color="red",    label="Storm (≥7)")
            ], fontsize=8, facecolor=fig_fc, labelcolor=txt_col)

            fig.subplots_adjust(left=0.12, right=0.95, top=0.88, bottom=0.25)
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

    with top2:
        st.markdown("### Countries by Active LEO Satellites")
        labels, values, _ = get_active_leo_by_country()

        if values:
            fig2, ax2 = plt.subplots(figsize=FIG_SIZE, facecolor=fig_fc)
            ax2.set_facecolor(ax_fc)
            ax2.barh(labels, values, color="#2196f3")

            max_val = max(values)
            ax2.set_xlim(0, max_val * 1.2)
            ax2.tick_params(colors=txt_col)
            ax2.spines[["top","right","left","bottom"]].set_color(grid_col)

            for i, v in enumerate(values):
                ax2.text(v + max_val * 0.02, i, str(v), va="center", color=txt_col)

            fig2.subplots_adjust(left=0.12, right=0.95, top=0.88, bottom=0.25)
            st.pyplot(fig2, use_container_width=True)
            plt.close(fig2)

    # ── Upcoming Launches & High Risk Conjunctions ────────────────────────────
    bottom1, bottom2 = st.columns(2)

    with bottom1:
        st.markdown("### Upcoming Launches")
        launches, _ = fetch_china_launches()

        if launches:
            fig3, ax3 = plt.subplots(figsize=FIG_SIZE, facecolor=fig_fc)
            ax3.set_facecolor(ax_fc)
            ax3.axis("off")

            y = 0.9
            for i, launch in enumerate(launches[:4]):
                rocket = clean_rocket_name(launch.get("rocket"))
                date   = launch.get("date") or "TBD"
                site   = launch.get("site") or "TBD"

                ax3.text(0.02, y,        rocket, fontsize=12, fontweight="bold",
                         transform=ax3.transAxes, color=txt_col)
                ax3.text(0.02, y - 0.07, date,   fontsize=10,
                         transform=ax3.transAxes, color=txt_col)
                ax3.text(0.02, y - 0.13, site,   fontsize=9,
                         transform=ax3.transAxes, color=grid_col)

                if i < 3:
                    ax3.plot([0.02, 0.98], [y - 0.17, y - 0.17],
                             transform=ax3.transAxes, color=grid_col)
                y -= 0.23

            st.pyplot(fig3, use_container_width=True)
            plt.close(fig3)

    with bottom2:
        st.markdown("### High Risk Conjunctions")
        df, _ = fetch_cdm_data()

        if df is not None and not df.empty:
            df["TCA_UTC"]      = pd.to_datetime(df["TCA_UTC"], errors="coerce")
            df["Pc"]           = pd.to_numeric(df["Pc"], errors="coerce")
            df["Miss_Distance"]= pd.to_numeric(df["Miss_Distance"], errors="coerce")
            df = df.dropna(subset=["TCA_UTC", "Pc", "Miss_Distance"]).copy()

            now          = datetime.now(timezone.utc).replace(tzinfo=None)
            one_week_ago = now - timedelta(days=7)
            df["HOURS_TO_TCA"] = (df["TCA_UTC"] - now).dt.total_seconds() / 3600
            df = df[df["TCA_UTC"] >= one_week_ago]

            tab1, tab2, tab3 = st.tabs(["Nearest TCA", "Highest PC", "Lowest MD"])
            with tab1:
                render_cdm_table(df.sort_values("HOURS_TO_TCA").head(10), is_dark)
            with tab2:
                render_cdm_table(df.sort_values("Pc", ascending=False).head(10), is_dark)
            with tab3:
                render_cdm_table(df.sort_values("Miss_Distance").head(10), is_dark)
        else:
            st.warning("No CDM data available")

    # ── Navigation tiles ──────────────────────────────────────────────────────
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