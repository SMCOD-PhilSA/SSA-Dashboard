import os
import streamlit as st
import msal
import requests
import base64
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def _secret(key: str) -> str:
    try:
        return st.secrets["azure"][key]
    except (KeyError, FileNotFoundError):
        value = os.getenv(key.upper())
        if not value:
            raise RuntimeError(f"Missing Azure credential '{key}'")
        return value


CLIENT_ID     = _secret("client_id")
CLIENT_SECRET = _secret("client_secret")
TENANT_ID     = _secret("tenant_id")
REDIRECT_URI  = _secret("redirect_uri")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES    = ["User.Read"]


def _build_msal_app():
    return msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )


def get_auth_url() -> str:
    return _build_msal_app().get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def exchange_code_for_token(auth_code: str) -> dict | None:
    result = _build_msal_app().acquire_token_by_authorization_code(
        auth_code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    if "access_token" in result:
        return result
    st.error("Token exchange failed")
    return None


def get_user_info(access_token: str) -> dict | None:
    resp = requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)


def logout():
    for key in ["authenticated", "user", "access_token"]:
        st.session_state.pop(key, None)
    st.query_params.clear()


def _get_logo():
    with open("graphics/PhilSA_v4-01.png", "rb") as f:
        return base64.b64encode(f.read()).decode()


def require_login() -> bool:
    if is_authenticated():
        return True

    auth_code = st.query_params.get("code")
    if auth_code:
        token_result = exchange_code_for_token(auth_code)
        if token_result:
            user_info = get_user_info(token_result["access_token"])
            if user_info:
                st.session_state["authenticated"] = True
                st.session_state["user"] = user_info
                st.session_state["access_token"] = token_result["access_token"]
                st.query_params.clear()
                st.rerun()

    _render_login_page()
    return False


def _render_login_page():
    logo = _get_logo()

    st.markdown(
        f"""
        <style>
        #MainMenu, footer, header {{ visibility: hidden; }}

        .login-wrapper {{
            display:flex;
            justify-content:center;
            align-items:center;
            height:80vh;
        }}

        .login-card {{
            text-align:center;
        }}

        .login-title {{
            font-size:22px;
            font-weight:600;
            margin-top:10px;
        }}
        </style>

        <div class="login-wrapper">
            <div class="login-card">
                <img src="data:image/png;base64,{logo}" width="180">
                <div class="login-title">Space Situational Awareness Dashboard</div>
                <br>
                <a href="{get_auth_url()}">Sign in with your PhilSA account</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )