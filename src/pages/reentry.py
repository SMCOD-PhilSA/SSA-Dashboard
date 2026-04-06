#!/usr/bin/env python3
from __future__ import annotations

import os
import time
import datetime as dt
import io
from typing import Optional

import numpy as np
import requests
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dotenv import load_dotenv

import cartopy.crs as ccrs
import cartopy.feature as cfeature

from skyfield.api import EarthSatellite, load as sf_load, wgs84

try:
    import simplekml
except Exception:
    simplekml = None

try:
    from pymsis import msis as pymsis_msis
except Exception:
    pymsis_msis = None


load_dotenv()

LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
DEFAULT_TIP_LIMIT = int(os.getenv("TIP_LIMIT", "200"))

PH_TZ = dt.timezone(dt.timedelta(hours=8))
EARTH_RADIUS_KM = 6371.0088


# ── helpers ──────────────────────────────────────────────────────────────────

def dt_to_iso_z(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def retry_get(session, url):
    for i in range(5):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return r
        except Exception:
            time.sleep(2 ** i)
    raise RuntimeError("GET failed after retries")


def get_credentials():
    """Pull credentials from Streamlit secrets."""
    try:
        username = st.secrets["spacetrack"]["username"]
        password = st.secrets["spacetrack"]["password"]
        return username, password
    except Exception:
        return None, None


def spacetrack_login(username, password):
    s = requests.Session()
    r = s.post(LOGIN_URL, data={"identity": username, "password": password})
    r.raise_for_status()
    return s


def fetch_tip(session, norad_id):
    url = (
        f"https://www.space-track.org/basicspacedata/query/class/tip"
        f"/NORAD_CAT_ID/{norad_id}/orderby/MSG_EPOCH%20desc"
        f"/limit/{DEFAULT_TIP_LIMIT}/format/json"
    )
    return retry_get(session, url).json()


def fetch_latest_tle(session, norad_id):
    url = (
        f"https://www.space-track.org/basicspacedata/query/class/gp"
        f"/NORAD_CAT_ID/{norad_id}/orderby/EPOCH%20desc/limit/1/format/tle"
    )
    lines = retry_get(session, url).text.splitlines()
    if len(lines) < 2:
        raise ValueError("TLE response too short")
    return f"NORAD {norad_id}", lines[0], lines[1]


def fetch_noaa_kp():
    url = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
    try:
        data = requests.get(url, timeout=10).json()
        vals = [float(d["kp_index"]) for d in data[-500:]]
        return round(sum(vals) / len(vals), 2)
    except Exception:
        return None


# ── ground track ─────────────────────────────────────────────────────────────

def compute_ground_track(l1: str, l2: str, name: str, hours: float = 2.0):
    """Return (lats, lons) for the next `hours` hours propagated every 30 s."""
    ts = sf_load.timescale()
    sat = EarthSatellite(l1, l2, name, ts)
    now = dt.datetime.now(dt.timezone.utc)
    times = [now + dt.timedelta(seconds=30 * i)
             for i in range(int(hours * 3600 / 30))]
    t = ts.from_datetimes(times)
    geo = sat.at(t)
    subpoint = wgs84.subpoint(geo)
    return subpoint.latitude.degrees, subpoint.longitude.degrees


def compute_decay_window(tip_data: list):
    """
    Extract earliest/latest decay epoch from TIP records to build
    the reentry window evolution — mirrors the Space-Track window chart.
    Returns list of dicts: {msg_epoch, early, late}
    """
    window = []
    for entry in tip_data:
        try:
            msg = entry.get("MSG_EPOCH") or entry.get("msg_epoch")
            early = entry.get("DECAY_EPOCH") or entry.get("decay_epoch")
            window_size = entry.get("WINDOW", entry.get("window", None))

            if not msg or not early:
                continue

            msg_dt = dt.datetime.fromisoformat(
                msg.replace("Z", "+00:00") if msg.endswith("Z") else msg
            )
            if msg_dt.tzinfo is None:
                msg_dt = msg_dt.replace(tzinfo=dt.timezone.utc)

            early_dt = dt.datetime.fromisoformat(
                early.replace("Z", "+00:00") if early.endswith("Z") else early
            )
            if early_dt.tzinfo is None:
                early_dt = early_dt.replace(tzinfo=dt.timezone.utc)

            # Estimate late window: use WINDOW field (hours) if available,
            # otherwise default ±12 h
            if window_size is not None:
                try:
                    late_dt = early_dt + dt.timedelta(hours=float(window_size))
                except Exception:
                    late_dt = early_dt + dt.timedelta(hours=12)
            else:
                late_dt = early_dt + dt.timedelta(hours=12)

            window.append({
                "msg_epoch": msg_dt,
                "early": early_dt,
                "late": late_dt,
            })
        except Exception:
            continue

    window.sort(key=lambda x: x["msg_epoch"])
    return window


# ── plots ─────────────────────────────────────────────────────────────────────

def plot_ground_track_and_impact(tip_data: list, l1: str, l2: str, name: str):
    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(111, projection=ccrs.PlateCarree())
    ax.set_global()
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.BORDERS, linewidth=0.3)
    ax.add_feature(cfeature.LAND, facecolor="#1a1a2e")
    ax.add_feature(cfeature.OCEAN, facecolor="#0f3460")
    ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.5)

    # Ground track
    try:
        lats, lons = compute_ground_track(l1, l2, name, hours=2.0)
        # Break antimeridian crossings
        lon_arr = np.array(lons)
        lat_arr = np.array(lats)
        breaks = np.where(np.abs(np.diff(lon_arr)) > 180)[0] + 1
        segs_lon = np.split(lon_arr, breaks)
        segs_lat = np.split(lat_arr, breaks)
        for i, (slon, slat) in enumerate(zip(segs_lon, segs_lat)):
            ax.plot(slon, slat,
                    color="cyan", linewidth=1.0, alpha=0.7,
                    transform=ccrs.PlateCarree(),
                    label="Ground track" if i == 0 else None)
        # Current position (first point)
        ax.scatter(lons[0], lats[0], color="lime", s=80, zorder=7,
                   transform=ccrs.PlateCarree(), label="Current position")
    except Exception as e:
        st.warning(f"Ground track error: {e}")

    # TIP prediction points
    tip_lats, tip_lons = [], []
    for entry in tip_data:
        try:
            lat = float(entry.get("LAT") or entry.get("lat") or 0)
            lon = float(entry.get("LON") or entry.get("lon") or 0)
            if lat == 0 and lon == 0:
                continue
            tip_lats.append(lat)
            tip_lons.append(lon)
        except Exception:
            continue

    if tip_lats:
        ax.scatter(tip_lons, tip_lats,
                   color="orange", s=14, zorder=5,
                   transform=ccrs.PlateCarree(), label="TIP predictions")
        # Most likely impact — use the latest TIP point
        ax.scatter(tip_lons[-1], tip_lats[-1],
                   color="red", s=120, marker="*", zorder=8,
                   transform=ccrs.PlateCarree(), label="Most likely impact")

        # Draw a small uncertainty ellipse around most likely impact
        impact_lat = tip_lats[-1]
        impact_lon = tip_lons[-1]
        theta = np.linspace(0, 2 * np.pi, 100)
        ellipse_lon = impact_lon + 8 * np.cos(theta)
        ellipse_lat = impact_lat + 3 * np.sin(theta)
        ax.plot(ellipse_lon, ellipse_lat,
                color="red", linewidth=0.8, linestyle="--", alpha=0.6,
                transform=ccrs.PlateCarree(), label="Impact uncertainty")

    ax.legend(loc="lower left", fontsize=7,
              facecolor="#1a1a2e", labelcolor="white", framealpha=0.8)
    ax.set_title("Ground Track & Predicted Impact Zone", color="white", fontsize=13)
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    plt.tight_layout()
    return fig


def plot_window_evolution(window: list):
    """
    Recreates the Space-Track window evolution chart:
    X = MSG_EPOCH (message date), shaded band = early..late decay window.
    """
    if not window:
        return None

    msg_epochs = [w["msg_epoch"] for w in window]
    early = [w["early"] for w in window]
    late = [w["late"] for w in window]

    fig, ax = plt.subplots(figsize=(12, 4))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    # Shaded band
    ax.fill_between(msg_epochs, early, late,
                    alpha=0.35, color="#4fa3d1", label="Reentry window")

    # Early / late lines
    ax.plot(msg_epochs, early, "o-",
            color="#4fa3d1", linewidth=1.5, markersize=4, label="Early bound")
    ax.plot(msg_epochs, late, "o-",
            color="#a8d8ea", linewidth=1.5, markersize=4,
            linestyle="--", label="Late bound")

    # Annotate each point with date label
    for m, e, l in zip(msg_epochs, early, late):
        ax.annotate(e.strftime("%d %b"),
                    xy=(m, e), xytext=(0, 6),
                    textcoords="offset points",
                    fontsize=7, color="#4fa3d1", ha="center")
        ax.annotate(l.strftime("%d %b"),
                    xy=(m, l), xytext=(0, -10),
                    textcoords="offset points",
                    fontsize=7, color="#a8d8ea", ha="center")

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.yaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30,
             fontsize=8, color="gray")
    plt.setp(ax.yaxis.get_majorticklabels(), fontsize=8, color="gray")

    ax.set_xlabel("Message Epoch (UTC)", color="gray", fontsize=9)
    ax.set_ylabel("Predicted Decay Date (UTC)", color="gray", fontsize=9)
    ax.set_title("Reentry Window Evolution", color="white", fontsize=13)
    ax.tick_params(colors="gray")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    ax.legend(fontsize=8, facecolor="#1a1a2e",
              labelcolor="white", framealpha=0.8)
    ax.grid(axis="y", color="#333", linewidth=0.4)

    plt.tight_layout()
    return fig


# ── main render ───────────────────────────────────────────────────────────────

def render():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 0.5rem !important; }
        h2 { font-size: 22px !important; font-weight: 700 !important;
             margin-bottom: 0.5rem !important; }
        h3 { font-size: 16px !important; font-weight: 600 !important;
             margin-top: 1rem !important; margin-bottom: 0.25rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Back button
    if st.button("← Back to Home"):
        st.query_params["page"] = "home"
        st.session_state["page"] = "home"
        st.rerun()

    st.markdown("<h2>Orbital Debris Reentry Monitor</h2>", unsafe_allow_html=True)

    # Credentials from secrets
    username, password = get_credentials()
    if not username:
        st.error(
            "Space-Track credentials not found. "
            "Add them to `.streamlit/secrets.toml` under [spacetrack]."
        )
        st.code(
            '[spacetrack]\nusername = "your@email.com"\npassword = "yourpassword"',
            language="toml",
        )
        return

    # NORAD input
    norad_id = st.text_input("NORAD Catalog ID", value="66877", key="reentry_norad")

    col_fetch, col_predict = st.columns(2)

    # ── FETCH ────────────────────────────────────────────────────────────────
    with col_fetch:
        if st.button("Fetch TIP & TLE", use_container_width=True):
            if not norad_id:
                st.error("Enter a NORAD ID.")
            else:
                with st.spinner("Logging in to Space-Track..."):
                    try:
                        session = spacetrack_login(username, password)
                    except Exception as e:
                        st.error(f"Login failed: {e}")
                        st.stop()

                with st.spinner("Fetching TIP data..."):
                    try:
                        tip = fetch_tip(session, int(norad_id))
                        st.session_state["reentry_tip"] = tip
                        st.success(f"Fetched {len(tip)} TIP records.")
                    except Exception as e:
                        st.error(f"TIP fetch failed: {e}")

                with st.spinner("Fetching latest TLE..."):
                    try:
                        name, l1, l2 = fetch_latest_tle(session, int(norad_id))
                        st.session_state["reentry_tle"] = (name, l1, l2)
                        st.success(f"TLE fetched for {name}.")
                    except Exception as e:
                        st.error(f"TLE fetch failed: {e}")

    # ── PREDICT ──────────────────────────────────────────────────────────────
    with col_predict:
        if st.button("Run Prediction", use_container_width=True):
            with st.spinner("Fetching Kp index..."):
                kp = fetch_noaa_kp()
                st.session_state["reentry_kp"] = kp
                st.session_state["reentry_pred_time"] = dt_to_iso_z(
                    dt.datetime.now(dt.timezone.utc)
                )
            st.success(f"Kp index: {kp}")

    # ── RESULTS ───────────────────────────────────────────────────────────────
    tip = st.session_state.get("reentry_tip")
    tle = st.session_state.get("reentry_tle")
    kp = st.session_state.get("reentry_kp")
    pred_time = st.session_state.get("reentry_pred_time")

    if not tip and not tle:
        return

    st.markdown("---")

    # Metrics
    if kp is not None and pred_time:
        st.markdown("<h3>Prediction Summary</h3>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("NORAD ID", norad_id)
        m2.metric("Avg Kp Index", kp)
        m3.metric("Prediction Time (UTC)", pred_time)

    # TLE display
    if tle:
        st.markdown("<h3>Latest TLE</h3>", unsafe_allow_html=True)
        name, l1, l2 = tle
        st.code(f"{name}\n{l1}\n{l2}", language="text")

    # Ground track + impact map
    if tle and tip:
        st.markdown("<h3>Ground Track & Predicted Impact Zone</h3>",
                    unsafe_allow_html=True)
        name, l1, l2 = tle
        with st.spinner("Computing ground track..."):
            fig_map = plot_ground_track_and_impact(tip, l1, l2, name)
        st.pyplot(fig_map, use_container_width=True)
        plt.close(fig_map)

    # Window evolution
    if tip:
        st.markdown("<h3>Reentry Window Evolution</h3>", unsafe_allow_html=True)
        window = compute_decay_window(tip)
        if window:
            fig_win = plot_window_evolution(window)
            if fig_win:
                st.pyplot(fig_win, use_container_width=True)
                plt.close(fig_win)
        else:
            st.info("No decay window data available in TIP records.")

        # Raw TIP table
        st.markdown("<h3>TIP Records</h3>", unsafe_allow_html=True)
        st.dataframe(tip[:50], use_container_width=True, height=300)

    # Report download
    if tip and kp is not None:
        st.markdown("<h3>Generate Report</h3>", unsafe_allow_html=True)
        if st.button("Generate & Download Report"):
            fig_r, ax_r = plt.subplots(figsize=(8, 6))
            ax_r.axis("off")
            lines = [
                f"NORAD ID  : {norad_id}",
                f"Kp Index  : {kp}",
                f"Pred Time : {pred_time}",
                f"TIP Count : {len(tip)}",
            ]
            if tle:
                lines += ["", "── Latest TLE ──", tle[0], tle[1], tle[2]]
            for i, line in enumerate(lines):
                ax_r.text(0.05, 0.92 - i * 0.07, line, fontsize=10,
                          transform=ax_r.transAxes, family="monospace")
            fig_r.tight_layout()
            buf = io.BytesIO()
            fig_r.savefig(buf, format="png", dpi=150)
            buf.seek(0)
            st.download_button(
                label="Save Report PNG",
                data=buf,
                file_name=f"reentry_report_{norad_id}.png",
                mime="image/png",
            )
            plt.close(fig_r)