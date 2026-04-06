import base64
import matplotlib.pyplot as plt
import streamlit as st
import streamlit.components.v1 as components

from src.services.space_weather_api import get_daily_kp
from src.services.spacetrack_api import get_active_leo_by_country
from src.services.launch_scraper import fetch_china_launches


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
        st.query_params["page"] = page_key
        st.session_state["page"] = page_key
        st.rerun()


def clean_rocket_name(text):
    if not text:
        return "TBD"
    for k in ["Unknown Payload", "Demo Flight", "Chang'e"]:
        text = text.replace(k, "")
    return text.strip()


def render():
    st.markdown("""
    <style>
    .block-container { padding-top:0.1rem !important; }
    </style>
    """, unsafe_allow_html=True)

    FIG_SIZE = (8, 4)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Geomagnetic Storm Forecast")
        days, values = get_daily_kp()

        if values:
            fig, ax = plt.subplots(figsize=FIG_SIZE)

            x = list(range(len(values)))
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

            ax.set_ylabel("Kp Index")
            ax.set_xticks(x)
            ax.set_xticklabels(days, rotation=30, ha="right")
            ax.set_ylim(0, 9)
            ax.set_xlim(-0.5, len(values) - 0.5)

            for i, v in enumerate(values):
                ax.text(i, v + 0.2, f"{v:.1f}", ha="center", fontsize=8)

            from matplotlib.patches import Patch
            ax.legend(handles=[
                Patch(color="green", label="Quiet (<3)"),
                Patch(color="yellow", label="Unsettled (3–4)"),
                Patch(color="orange", label="Active (5–6)"),
                Patch(color="red", label="Storm (≥7)")
            ], fontsize=8)

            fig.subplots_adjust(left=0.12, right=0.95, top=0.88, bottom=0.25)

            st.pyplot(fig, use_container_width=True)

    with col2:
        st.markdown("### Countries by Active LEO Satellites")
        labels, values, error = get_active_leo_by_country()

        if values:
            fig2, ax2 = plt.subplots(figsize=FIG_SIZE)

            ax2.barh(labels, values)
            ax2.set_xlabel("Number of Satellites")

            max_val = max(values)
            ax2.set_xlim(0, max_val * 1.15)

            for i, v in enumerate(values):
                ax2.text(v + max_val * 0.02, i, str(v), va="center", fontsize=9)

            fig2.subplots_adjust(left=0.12, right=0.95, top=0.88, bottom=0.25)

            st.pyplot(fig2, use_container_width=True)

    l1, l2 = st.columns(2)

    with l1:
        st.markdown("### Upcoming Launches")
        launches, error = fetch_china_launches()

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
                    ax3.plot([0.02, 0.98], [y - 0.17, y - 0.17],
                             transform=ax3.transAxes, color="#cccccc", linewidth=1)

                y -= 0.23

            st.pyplot(fig3, use_container_width=True)

    with l2:
        st.empty()

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