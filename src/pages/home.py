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
        <!DOCTYPE html>
        <html>
        <head>
        <style>
          * {{ margin: 0; padding: 0; box-sizing: border-box; }}

          html, body {{
            width: 100%;
            height: {height}px;
            background: transparent;
            overflow: hidden;
          }}

          .tile {{
            width: 100%;
            height: {height}px;
            border-radius: 14px;
            border: 1.5px solid rgba(255, 255, 255, 0.25);
            overflow: hidden;
            position: relative;
            background-image: url('data:{mime};base64,{img_b64}');
            background-size: cover;
            background-position: center;
          }}

          .overlay {{
            position: absolute;
            inset: 0;
            background: linear-gradient(
              to bottom,
              rgba(0,0,0,0.0) 30%,
              rgba(0,0,0,0.75) 100%
            );
          }}

          .label {{
            position: absolute;
            bottom: 14px;
            left: 16px;
            color: white;
            font-size: 15px;
            font-weight: 600;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            text-shadow: 0 1px 6px rgba(0,0,0,0.8);
            z-index: 2;
          }}
        </style>
        </head>
        <body>
          <div class="tile">
            <div class="overlay"></div>
            <div class="label">{title}</div>
          </div>
        </body>
        </html>
        """,
        height=height + 2,
        scrolling=False,
    )

    # BUTTON BELOW TILE (THIS IS THE FIX)
    if st.button(f"Open {title}", key=f"btn_{page_key}", use_container_width=True):
        st.query_params["page"] = page_key
        st.session_state["page"] = page_key
        st.rerun()


def clean_rocket_name(text):
    if not text:
        return "TBD"
    text = text.replace("\n", " ").strip()
    keywords_to_remove = ["Unknown Payload", "Demo Flight", "Chang'e 7", "Chang'e"]
    for k in keywords_to_remove:
        text = text.replace(k, "").strip()
    import re
    match = re.search(r"(Long March\s?[0-9A-Za-z\/\-]+)", text)
    if match:
        return match.group(1)
    return text


def render():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.1rem !important;
            padding-bottom: 0rem !important;
        }
        h3 {
            margin-top: 0rem !important;
            margin-bottom: 0.25rem !important;
            font-size: 18px !important;
            font-weight: 700 !important;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 1rem !important;
        }
        iframe {
            border: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "page" not in st.session_state:
        st.session_state["page"] = "home"

    page_from_query = st.query_params.get("page", None)
    if page_from_query and page_from_query != st.session_state.get("page"):
        st.session_state["page"] = page_from_query
        st.rerun()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<h3>Geomagnetic Storm Forecast</h3>", unsafe_allow_html=True)
        try:
            days, values = get_daily_kp()
            if values:
                fig, ax = plt.subplots(figsize=(6, 3))
                bars = ax.bar(days, values)

                colors = []
                for v in values:
                    if v < 3:
                        colors.append("green")
                    elif v < 5:
                        colors.append("yellow")
                    elif v < 7:
                        colors.append("orange")
                    else:
                        colors.append("red")

                for bar, c in zip(bars, colors):
                    bar.set_color(c)

                ax.set_ylabel("Kp Index")
                ax.set_ylim(0, 9)

                for i, v in enumerate(values):
                    ax.text(i, v + 0.15, f"{v:.1f}", ha="center", fontsize=8)

                plt.tight_layout()
                st.pyplot(fig, width="stretch")
            else:
                st.warning("No Kp data available.")
        except Exception as e:
            st.error(str(e))

    with col2:
        st.markdown("<h3>Countries by Active LEO Satellites</h3>", unsafe_allow_html=True)
        try:
            labels, values, error = get_active_leo_by_country()
            if error:
                st.error(error)
            elif values:
                fig2, ax2 = plt.subplots(figsize=(6, 3))
                ax2.barh(labels, values)
                plt.tight_layout()
                st.pyplot(fig2, width="stretch")
            else:
                st.warning("No satellite data available.")
        except Exception as e:
            st.error(str(e))

    launch_col1, launch_col2 = st.columns(2)

    with launch_col1:
        st.markdown("<h3>Upcoming Launches</h3>", unsafe_allow_html=True)
        try:
            launches, error = fetch_china_launches()
            if error:
                st.error(error)
            elif launches:
                fig3, ax3 = plt.subplots(figsize=(6, 3))
                ax3.axis("off")

                for i, launch in enumerate(launches[:4]):
                    y = 0.85 - i * 0.22
                    ax3.text(0.03, y, clean_rocket_name(launch.get("rocket")),
                             transform=ax3.transAxes)
                    ax3.text(0.03, y - 0.07, launch.get("date") or "TBD",
                             transform=ax3.transAxes)
                    ax3.text(0.03, y - 0.13, launch.get("site") or "TBD",
                             transform=ax3.transAxes)

                plt.tight_layout()
                st.pyplot(fig3, width="stretch")
            else:
                st.warning("No upcoming launches")
        except Exception as e:
            st.error(str(e))

    with launch_col2:
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