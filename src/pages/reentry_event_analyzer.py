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

SHEET_ID   = "1isa_rOueh0yDY9OM43Q2AWZoKPGrlvEo7JOSHJdW3jE"
DATA_SHEET = "Data"
ACK_SHEET  = "ACK"


# ── CSS ───────────────────────────────────────────────────────────────────────
def inject_css(is_dark):
    if is_dark:
        card_bg     = "#0d1b2a"
        card_border = "#1e3a50"
        card_text   = "#e6f1f5"
        sub_text    = "#7a9bb5"
        hdr_bg      = "#0a1520"
        row_border  = "#1a2e42"
        metric_bg   = "#0d1b2a"
        metric_bdr  = "#1e3a50"
        metric_val  = "#e6f1f5"
        metric_lbl  = "#7a9bb5"
        badge_ack   = "#1a4a2a"
        badge_ack_t = "#2ecc71"
    else:
        card_bg     = "#ffffff"
        card_border = "#d0d7de"
        card_text   = "#0d2137"
        sub_text    = "#4a6b85"
        hdr_bg      = "#f2f6fa"
        row_border  = "#e8edf2"
        metric_bg   = "#f0f6fc"
        metric_bdr  = "#c5d8ec"
        metric_val  = "#0d2137"
        metric_lbl  = "#4a6b85"
        badge_ack   = "#e6f9ee"
        badge_ack_t = "#1a8a40"

    st.markdown(f"""
    <style>
    .re-card {{
        border: 1px solid {card_border};
        padding: 14px 16px;
        border-radius: 12px;
        margin-bottom: 14px;
        background: {card_bg};
        color: {card_text};
        font-size: 0.88rem;
        line-height: 1.7;
    }}
    .re-card b {{ color: {sub_text}; font-weight: 600; }}
    .re-card .val {{ color: {card_text}; font-weight: 500; }}
    .re-card .major {{ color: #f44336; font-weight: 700; }}
    .re-card .minor {{ color: #2ecc71; font-weight: 700; }}

    /* latest-row badge */
    .re-row-badge {{
        display: inline-block;
        background: {metric_bg};
        border: 1px solid {metric_bdr};
        color: {sub_text};
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 20px;
        margin-left: 8px;
        vertical-align: middle;
    }}

    /* ack badge */
    .re-ack-badge {{
        display: inline-block;
        background: {badge_ack};
        color: {badge_ack_t};
        font-size: 0.78rem;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 8px;
        margin-bottom: 10px;
    }}

    /* summary metrics strip */
    .re-metrics {{
        display: flex;
        gap: 12px;
        margin-bottom: 18px;
        flex-wrap: wrap;
    }}
    .re-metric {{
        background: {metric_bg};
        border: 1px solid {metric_bdr};
        border-radius: 10px;
        padding: 12px 20px;
        flex: 1;
        min-width: 110px;
        text-align: center;
    }}
    .re-metric .m-val {{
        font-size: 1.8rem;
        font-weight: 800;
        color: {metric_val};
    }}
    .re-metric .m-lbl {{
        font-size: 0.72rem;
        color: {metric_lbl};
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-top: 2px;
    }}

    /* dataframe overrides */
    div[data-testid="stDataFrame"] thead th {{
        background: {hdr_bg} !important;
        color: {sub_text} !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
    }}
    div[data-testid="stDataFrame"] td {{
        color: {card_text} !important;
        font-size: 0.82rem !important;
        border-bottom: 1px solid {row_border} !important;
    }}
    </style>""", unsafe_allow_html=True)


# ── credentials ───────────────────────────────────────────────────────────────
def get_spacetrack_creds():
    try:
        return st.secrets["spacetrack"]["username"], st.secrets["spacetrack"]["password"]
    except Exception:
        return os.getenv("SPACETRACK_USER"), os.getenv("SPACETRACK_PASS")


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
            path, scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
    return gspread.authorize(creds)


# ── data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_data():
    client = get_gspread_client()
    ws     = client.open_by_key(SHEET_ID).worksheet(DATA_SHEET)
    rows   = ws.get_all_records()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.columns = [c.strip() for c in df.columns]

    # ── preserve the original sheet row order as an explicit column ──────────
    # Row 2 in the sheet = index 0 here (row 1 is the header).
    # The highest sheet_row for a NORAD ID = the most recently appended TIP.
    df["sheet_row"] = df.index + 2   # +2 because header is row 1

    df["Hit UTC"]   = pd.to_datetime(df["Hit UTC"],   errors="coerce")
    df["Distance"]  = pd.to_numeric(df["Distance"],   errors="coerce")
    df = df.drop(columns=[c for c in df.columns if "__PowerAppsId__" in c], errors="ignore")

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
        ws = client.open_by_key(SHEET_ID).add_worksheet(title=ACK_SHEET, rows=1000, cols=5)
        ws.append_row(["NORAD", "User", "Time"])
    user = st.session_state.get("user", {}).get("displayName", "local_user")
    ws.append_row([str(norad), user, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")])


# ── Space-Track object name ───────────────────────────────────────────────────
def spacetrack_login():
    user, pw = get_spacetrack_creds()
    s = requests.Session()
    s.post("https://www.space-track.org/ajaxauth/login",
           data={"identity": user, "password": pw})
    return s


@st.cache_data(ttl=86400)
def get_object_name(norad):
    try:
        s    = spacetrack_login()
        url  = (f"https://www.space-track.org/basicspacedata/query"
                f"/class/satcat/NORAD_CAT_ID/{norad}/format/json")
        data = s.get(url, timeout=10).json()
        if data:
            return data[0].get("OBJECT_NAME", "UNKNOWN")
    except Exception:
        pass
    return "UNKNOWN"


# ── per-NORAD summary derived from LATEST sheet row ──────────────────────────
def build_latest_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each NORAD ID, pick the row with the HIGHEST sheet_row number.
    That row reflects the most recent TIP update — regardless of what
    Hit UTC / Hit PH say (those change with every TIP revision).

    Summary columns returned:
        NORAD, name (fetched), latest_sheet_row,
        severity (from latest row), hit_utc (from latest row),
        hit_ph (from latest row), distance (min across all rows for that NORAD),
        total_rows, has_major
    """
    records = []
    for norad, grp in df.groupby("NORAD"):
        # sort by sheet row — highest = most recent TIP
        grp_sorted = grp.sort_values("sheet_row", ascending=False)
        latest     = grp_sorted.iloc[0]

        records.append({
            "NORAD"           : norad,
            "latest_sheet_row": int(latest["sheet_row"]),
            "severity"        : latest["Severity"],
            "hit_utc"         : latest["Hit UTC"],
            "hit_ph"          : latest.get("Hit PH", ""),
            "min_distance"    : grp["Distance"].min(),
            "total_rows"      : len(grp),
            "has_major"       : (grp["Severity"] == "MAJOR").any(),
        })

    summary = pd.DataFrame(records)
    # show highest-risk (MAJOR first) then by most recent sheet row
    summary["_sev_rank"] = summary["severity"].map({"MAJOR": 0, "MINOR": 1}).fillna(2)
    summary = summary.sort_values(["_sev_rank", "latest_sheet_row"],
                                  ascending=[True, False]).drop(columns="_sev_rank")
    return summary


# ── chart ─────────────────────────────────────────────────────────────────────
def render_timeline_chart(df: pd.DataFrame, is_dark: bool):
    """
    Plot event count per 6h bucket using sheet_row order, not Hit UTC order.
    We still use Hit UTC for the time axis but bucket by insertion order
    to show activity over the past 7 days.
    """
    fig_fc  = "#0d1b2a" if is_dark else "#ffffff"
    ax_fc   = "#0d1b2a" if is_dark else "#ffffff"
    txt_col = "#e6f1f5" if is_dark else "#0d2137"
    grd_col = "#1e3a50" if is_dark else "#e0e8f0"
    line_col= "#2196f3"

    ts = df.set_index("Hit UTC").resample("6h").size()

    fig, ax = plt.subplots(figsize=(10, 3), facecolor=fig_fc)
    ax.set_facecolor(ax_fc)
    ax.plot(ts.index, ts.values, marker="o", color=line_col, linewidth=2, markersize=5)
    ax.fill_between(ts.index, ts.values, alpha=0.15, color=line_col)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", color=txt_col)
    ax.tick_params(colors=txt_col)
    ax.spines[["top","right","left","bottom"]].set_color(grd_col)
    ax.grid(True, color=grd_col, linewidth=0.5)
    ax.set_ylabel("Events", color=txt_col)
    plt.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


# ── NORAD card ────────────────────────────────────────────────────────────────
def render_norad_card(row: pd.Series, all_rows: pd.DataFrame,
                      acknowledged: set, is_dark: bool):
    norad      = row["NORAD"]
    name       = get_object_name(norad)
    severity   = row["severity"]
    sev_class  = "major" if severity == "MAJOR" else "minor"
    is_ack     = str(norad) in acknowledged

    hit_utc_str = (row["hit_utc"].strftime("%Y-%m-%d %H:%M")
                   if pd.notna(row["hit_utc"]) else "N/A")
    hit_ph_str  = str(row["hit_ph"]) if row["hit_ph"] else "N/A"
    min_dist    = row["min_distance"]
    dist_str    = f"{min_dist:.1f} km" if pd.notna(min_dist) else "N/A"

    # flag if any row for this NORAD is MAJOR (even if latest is MINOR)
    any_major_badge = ""
    if row["has_major"] and severity != "MAJOR":
        any_major_badge = "<span style='color:#ff9800;font-size:0.75rem;'> ⚠ had MAJOR events</span>"

    st.markdown(f"""
    <div class="re-card">
      <div style="display:flex;justify-content:space-between;align-items:center;
                  margin-bottom:8px;">
        <span style="font-size:1rem;font-weight:700;">
            NORAD {norad}
            <span class="re-row-badge">row {row['latest_sheet_row']}</span>
        </span>
        <span class="{sev_class}" style="font-size:0.85rem;">{severity}{any_major_badge}</span>
      </div>
      <b>Name:</b> <span class="val">{name}</span><br>
      <b>Latest TIP — Hit UTC:</b> <span class="val">{hit_utc_str}</span><br>
      <b>Latest TIP — Hit PH:</b> <span class="val">{hit_ph_str}</span><br>
      <b>Closest Distance to PH:</b> <span class="val">{dist_str}</span><br>
      <b>Total TIP rows:</b> <span class="val">{row['total_rows']}</span>
    </div>
    """, unsafe_allow_html=True)

    if is_ack:
        st.markdown(
            f'<div class="re-ack-badge">✓ Acknowledged</div>',
            unsafe_allow_html=True)
    else:
        if st.button(f"Acknowledge {norad}", key=f"ack_{norad}"):
            acknowledge(norad)
            st.rerun()

    # detail table — all rows for this NORAD sorted by sheet_row desc
    with st.expander(f"📋 All rows for NORAD {norad} ({row['total_rows']} entries)"):
        detail = (all_rows[all_rows["NORAD"] == norad]
                  .sort_values("sheet_row", ascending=False)
                  .drop(columns=["sheet_row"], errors="ignore"))
        st.dataframe(detail, use_container_width=True, hide_index=True)


# ── main render ───────────────────────────────────────────────────────────────
def render():
    is_dark = st.session_state.get("theme", "dark") == "dark"
    inject_css(is_dark)

    tc = "#e6f1f5" if is_dark else "#0d2137"
    sc = "#7a9bb5" if is_dark else "#4a6b85"

    st.markdown(
        f"<h2 style='color:{tc};margin:0 0 4px;'>Reentry Event Analyzer</h2>"
        f"<p style='color:{sc};font-size:0.85rem;margin-bottom:16px;'>",
        unsafe_allow_html=True)

    df = load_data()
    if df.empty:
        st.warning("No data available.")
        return

    # ── filter to last 7 days by Hit UTC (still useful for chart window) ──────
    valid = df.dropna(subset=["Hit UTC"])
    if valid.empty:
        st.warning("No valid Hit UTC values found.")
        return

    cutoff = valid["Hit UTC"].max() - pd.Timedelta(days=7)
    df_week = valid[valid["Hit UTC"] >= cutoff].copy()

    # ── summary metrics ───────────────────────────────────────────────────────
    n_total  = len(df_week)
    n_major  = int((df_week["Severity"] == "MAJOR").sum())
    n_minor  = int((df_week["Severity"] == "MINOR").sum())
    n_norads = df_week["NORAD"].nunique()

    st.markdown(f"""
    <div class="re-metrics">
      <div class="re-metric">
        <div class="m-val">{n_norads}</div>
        <div class="m-lbl">Objects</div>
      </div>
      <div class="re-metric">
        <div class="m-val">{n_total}</div>
        <div class="m-lbl">Total Rows</div>
      </div>
      <div class="re-metric">
        <div class="m-val" style="color:#f44336;">{n_major}</div>
        <div class="m-lbl">MAJOR Rows</div>
      </div>
      <div class="re-metric">
        <div class="m-val" style="color:#2ecc71;">{n_minor}</div>
        <div class="m-lbl">MINOR Rows</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── timeline chart ────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='font-weight:700;color:{tc};font-size:0.95rem;"
        f"margin-bottom:8px;'>Events Over Time (6h buckets)</div>",
        unsafe_allow_html=True)
    render_timeline_chart(df_week, is_dark)

    # ── per-NORAD cards ───────────────────────────────────────────────────────
    st.markdown(
        f"<div style='font-weight:700;color:{tc};font-size:0.95rem;"
        f"margin:16px 0 4px;'>Latest TIP per Object</div>"
        f"<p style='color:{sc};font-size:0.8rem;margin-bottom:12px;'>"
        f"Card shows the <b>highest sheet row</b> for each NORAD ID — "
        f"the most recent TIP update regardless of Hit UTC changes.</p>",
        unsafe_allow_html=True)

    acknowledged = load_acknowledged()
    summary      = build_latest_summary(df_week)

    cols = st.columns(2)
    for i, (_, row) in enumerate(summary.iterrows()):
        with cols[i % 2]:
            render_norad_card(row, df_week, acknowledged, is_dark)