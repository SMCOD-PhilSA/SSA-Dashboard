import base64
import streamlit as st


def get_base64_image(path):
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


def render_header():
    logo_base64 = get_base64_image("graphics/logo.png")

    is_dark = st.session_state.get("theme", "dark") == "dark"

    if is_dark:
        header_grad = "linear-gradient(90deg, #081c2c, #0b3d5c)"
        page_bg = "#0a0f14"
        text_color = "#e6f1f5"
        input_bg = "#111827"
        border = "#2a2f3a"
        alert_bg = "#1f2937"
    else:
        header_grad = "linear-gradient(90deg, #1565c0, #1e88e5)"
        page_bg = "#f0f2f6"
        text_color = "#000000"
        input_bg = "#ffffff"
        border = "#cccccc"
        alert_bg = "#e5e7eb"

    st.markdown(
        f"""
        <style>
        header {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}
        #MainMenu {{ visibility: hidden; }}

        [data-testid="stSidebar"] {{
            display: none !important;
        }}

        [data-testid="collapsedControl"] {{
            display: none !important;
        }}

        html, body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {{
            background-color: {page_bg} !important;
            color: {text_color} !important;
        }}

        h1, h2, h3, h4, h5, h6,
        p, span, div, label {{
            color: {text_color} !important;
        }}

        .stMarkdown, .stText, .stCaption {{
            color: {text_color} !important;
        }}

        /* INPUT BOXES */
        input, textarea {{
            background-color: {input_bg} !important;
            color: {text_color} !important;
            border: 1px solid {border} !important;
        }}

        /* STREAMLIT INPUT WRAPPERS */
        .stTextInput div[data-baseweb="input"] {{
            background-color: {input_bg} !important;
            border: 1px solid {border} !important;
        }}

        .stTextInput input {{
            color: {text_color} !important;
        }}

        /* BUTTONS */
        .stButton button {{
            background-color: {input_bg} !important;
            color: {text_color} !important;
            border: 1px solid {border} !important;
        }}

        .stButton button:hover {{
            opacity: 0.9;
        }}

        /* ALERT BOXES (SUCCESS / INFO / WARNING) */
        div[data-testid="stAlert"] {{
            background-color: {alert_bg} !important;
            color: {text_color} !important;
            border: 1px solid {border} !important;
        }}

        /* CODE BLOCK (TLE) */
        pre {{
            background-color: {input_bg} !important;
            color: {text_color} !important;
            border: 1px solid {border} !important;
        }}

        /* HEADER */
        .ssa-header {{
            position: fixed;
            top: 0; left: 0; right: 0;
            height: 60px;
            background: {header_grad};
            display: flex;
            align-items: center;
            padding: 0 32px;
            z-index: 9999;
            box-shadow: 0 2px 12px rgba(0,0,0,0.35);
        }}

        .ssa-logo {{
            width: 40px;
            height: 40px;
        }}

        .ssa-title {{
            color: #e6f1f5;
            font-size: 20px;
            font-weight: 500;
            margin-left: 14px;
        }}

        .page-content {{
            margin-top: 80px;
            padding: 20px 40px;
        }}
        </style>

        <div class="ssa-header">
            <img class="ssa-logo" src="data:image/png;base64,{logo_base64}">
            <div class="ssa-title">Space Situational Awareness Dashboard</div>
        </div>

        <div class="page-content">
        """,
        unsafe_allow_html=True,
    )