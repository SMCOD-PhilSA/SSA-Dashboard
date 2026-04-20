import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


def fetch_cdm_data():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets.readonly"
        ]

        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scope
        )

        client = gspread.authorize(creds)

        SHEET_ID = "1ZVJSVdJFGYsh3PohioIuH-u7W84DRjRs-5LKeZ2snAs"

        sheet = client.open_by_key(SHEET_ID).worksheet("Sheet1")

        records = sheet.get_all_records()

        if not records:
            return None, "No records found"

        df = pd.DataFrame(records)

        df.columns = [c.strip() for c in df.columns]

        required_cols = ["TCA_UTC", "Pc", "Miss_Distance"]

        for col in required_cols:
            if col not in df.columns:
                return None, f"Missing column: {col}"

        df["TCA_UTC"] = pd.to_datetime(df["TCA_UTC"], errors="coerce")
        df["Pc"] = pd.to_numeric(df["Pc"], errors="coerce")
        df["Miss_Distance"] = pd.to_numeric(df["Miss_Distance"], errors="coerce")

        df = df.dropna(subset=["TCA_UTC", "Pc", "Miss_Distance"])

        if df.empty:
            return None, "Parsed data is empty"

        return df, None

    except Exception as e:
        return None, str(e)