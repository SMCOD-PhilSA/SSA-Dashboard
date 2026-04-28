import os
import streamlit as st
import pandas as pd
import gspread
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SHEET_ID = "1isa_rOueh0yDY9OM43Q2AWZoKPGrlvEo7JOSHJdW3jE"
DATA_SHEET = "Data"
ACK_SHEET = "ACK"


def inject_css():
    st.markdown(
        """
        <style>

        .reentry-card {
            border: 1px solid var(--secondary-background-color) !important;
            padding: 12px !important;
            border-radius: 10px !important;
            margin-bottom: 12px !important;
            background-color: var(--background-color) !important;
            color: var(--text-color) !important;
        }

        .reentry-card span.major {
            color: #ff4d4f !important;
            font-weight: 700 !important;
        }

        .reentry-card span.minor {
            color: #2ecc71 !important;
            font-weight: 700 !important;
        }

        div[data-testid="stDataFrame"] {
            background-color: var(--background-color) !important;
        }

        div[data-testid="stDataFrame"] * {
            color: var(--text-color) !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def get_spacetrack_creds():
    try:
        return (
            st.secrets["spacetrack"]["username"],
            st.secrets["spacetrack"]["password"],
        )
    except Exception:
        return (
            os.getenv("SPACETRACK_USER"),
            os.getenv("SPACETRACK_PASS"),
        )


def get_gspread_client():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account_odr"],
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
    except Exception:
        path = os.getenv("GCP_JSON_ODR")
        if not path or not os.path.exists(path):
            st.error("GCP_JSON_ODR not found")
            st.stop()

        creds = Credentials.from_service_account_file(
            path,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )

    return gspread.authorize(creds)


@st.cache_data(ttl=60)
def load_data():
    client = get_gspread_client()
    ws = client.open_by_key(SHEET_ID).worksheet(DATA_SHEET)
    df = pd.DataFrame(ws.get_all_records())

    if df.empty:
        return df

    df.columns = [c.strip() for c in df.columns]
    df["Hit UTC"] = pd.to_datetime(df["Hit UTC"], errors="coerce")
    df["Distance"] = pd.to_numeric(df["Distance"], errors="coerce")

    return df


def load_acknowledged():
    client = get_gspread_client()
    try:
        ws = client.open_by_key(SHEET_ID).worksheet(ACK_SHEET)
        df = pd.DataFrame(ws.get_all_records())
        return set(df["NORAD"].astype(str)) if not df.empty else set()
    except Exception:
        return set()


def acknowledge(norad):
    client = get_gspread_client()

    try:
        ws = client.open_by_key(SHEET_ID).worksheet(ACK_SHEET)
    except Exception:
        ws = client.open_by_key(SHEET_ID).add_worksheet(
            title=ACK_SHEET, rows=1000, cols=5
        )
        ws.append_row(["NORAD", "User", "Time"])

    user = st.session_state.get("user", {}).get("displayName", "local_user")

    ws.append_row(
        [
            str(norad),
            user,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        ]
    )


def spacetrack_login():
    user, pw = get_spacetrack_creds()
    s = requests.Session()
    s.post(
        "https://www.space-track.org/ajaxauth/login",
        data={"identity": user, "password": pw},
    )
    return s


@st.cache_data(ttl=86400)
def get_object_name(norad):
    try:
        s = spacetrack_login()
        url = f"https://www.space-track.org/basicspacedata/query/class/satcat/NORAD_CAT_ID/{norad}/format/json"
        data = s.get(url).json()
        if data:
            return data[0].get("OBJECT_NAME", "UNKNOWN")
    except Exception:
        pass
    return "UNKNOWN"


def render():

    inject_css()

    st.title("Reentry Monitoring")

    df = load_data()

    if df.empty:
        st.warning("No data available")
        return

    df = df.dropna(subset=["Hit UTC"])

    cutoff = df["Hit UTC"].max() - pd.Timedelta(days=7)
    df = df[df["Hit UTC"] >= cutoff]

    df = df.drop(columns=[c for c in df.columns if "__PowerAppsId__" in c], errors="ignore")

    acknowledged = load_acknowledged()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total", len(df))
    col2.metric("MAJOR", int((df["Severity"] == "MAJOR").sum()))
    col3.metric("MINOR", int((df["Severity"] == "MINOR").sum()))

    st.subheader("Events Over Time")

    ts = df.set_index("Hit UTC").resample("6h").size()

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor("none")
    ax.set_facecolor("none")

    ax.plot(ts.index, ts.values, marker="o")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())

    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    ax.grid(True)

    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)

    cols = st.columns(2)

    for i, (norad, group) in enumerate(df.groupby("NORAD")):
        col = cols[i % 2]

        with col:

            group = group.sort_values("Hit UTC", ascending=False)

            latest_row = group.iloc[0]
            severity = latest_row["Severity"]

            severity_class = "major" if severity == "MAJOR" else "minor"

            min_dist = group["Distance"].min()
            earliest = group["Hit UTC"].min()

            name = get_object_name(norad)
            is_ack = str(norad) in acknowledged

            st.markdown(
                f"""
                <div class="reentry-card">
                    <b>NORAD:</b> {norad}<br>
                    <b>Name:</b> {name}<br>
                    <b>Severity:</b> <span class="{severity_class}">{severity}</span><br>
                    <b>Closest Distance to PH:</b> {min_dist}<br>
                    <b>Earliest Hit:</b> {earliest.strftime("%Y-%m-%d %H:%M")}<br>
                    <b>Latest Hit:</b> {latest_row["Hit UTC"].strftime("%Y-%m-%d %H:%M")}<br>
                    <b>Events:</b> {len(group)}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if not is_ack:
                if st.button(f"Acknowledge {norad}", key=f"ack_{norad}"):
                    acknowledge(norad)
                    st.rerun()
            else:
                st.success(f"NORAD {norad} acknowledged")

            st.dataframe(group, use_container_width=True)