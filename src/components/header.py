import streamlit as st
import base64

def get_base64_image(path):
    with open(path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def render_header():
    logo_base64 = get_base64_image("graphics/logo.png")

    st.markdown("""
        <style>
        header {visibility: hidden;}
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}

        .stApp {
            background-color: #0a0f14;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
        <style>
        .header {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 90px;
            background: linear-gradient(90deg, #081c2c, #0b3d5c);
            display: flex;
            align-items: center;
            padding: 0 40px;
            z-index: 9999;
        }}

        .header-title {{
            color: #e6f1f5;
            font-size: 26px;
            font-weight: 500;
            margin-left: 20px;
        }}

        .logo {{
            width: 60px;
            height: 60px;
            border-radius: 50%;
            overflow: hidden;
        }}

        .logo img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .page-content {{
            margin-top: 120px;
            padding: 20px 40px;
        }}
        </style>

        <div class="header">
            <div class="logo">
                <img src="data:image/png;base64,{logo_base64}">
            </div>
            <div class="header-title">
                Space Situational Awareness Dashboard
            </div>
        </div>

        <div class="page-content">
    """, unsafe_allow_html=True)