

import math
import time
from datetime import datetime, timezone, timedelta

import requests
import streamlit as st

# ── optional deps ─────────────────────────────────────────────────────────────
try:
    from sgp4.api import Satrec, jday
    SGP4_OK = True
except ImportError:
    SGP4_OK = False

try:
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ── constants ─────────────────────────────────────────────────────────────────
NOAA_AURORA_NORTH   = "https://services.swpc.noaa.gov/images/animations/ovation/north/latest.jpg"
NOAA_AURORA_SOUTH   = "https://services.swpc.noaa.gov/images/animations/ovation/south/latest.jpg"
KP_FORECAST_URL     = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
SPACETRACK_LOGIN   = "https://www.space-track.org/ajaxauth/login"
SPACETRACK_TLE_URL = "https://www.space-track.org/basicspacedata/query/class/gp/OBJECT_NAME/{name}/orderby/EPOCH%20desc/limit/1/format/tle"

AURORA_LAT_MIN = 60.0
AURORA_LAT_MAX = 75.0

# key = display label, value = (norad_id, display_name)
POPULAR_SATS = {
    "ISS (ZARYA)       — 25544" : (25544,  "ISS"),
    "DIWATA-2          — 43678" : (43678,  "DIWATA-2"),
    "HUBBLE (HST)      — 20580" : (20580,  "Hubble"),
    "TERRA             — 25994" : (25994,  "TERRA"),
    "AQUA              — 27424" : (27424,  "AQUA"),
    "SENTINEL-2A       — 40697" : (40697,  "SENTINEL-2A"),
    "NOAA-20           — 43013" : (43013,  "NOAA-20"),
    "SUOMI NPP         — 37849" : (37849,  "SUOMI NPP"),
    "STARLINK-1007     — 44713" : (44713,  "STARLINK-1007"),
}

OPERATIONAL_EFFECTS = [
    ("Increased Radiation",      "Single Event Upsets (SEUs) in electronics"),
    ("Surface Charging",         "Electrostatic discharge on solar panels / MLI"),
    ("Deep Dielectric Charging", "Internal charging in thick insulators"),
    ("Attitude Disturbance",     "Torque changes from enhanced magnetic field"),
    ("Increased Drag",           "Atmosphere heating → density rise → faster decay"),
    ("Comms Degradation",        "Ionospheric scintillation on UHF/VHF links"),
]


# ── helpers ───────────────────────────────────────────────────────────────────
def kp_risk_label(kp: float):
    if kp < 4:  return "Low",      "#4caf50"
    if kp < 6:  return "Moderate", "#ff9800"
    if kp < 8:  return "High",     "#f44336"
    return          "Extreme",      "#9c27b0"


def effect_severity(effect_name: str, kp: float):
    high   = {"Increased Radiation", "Surface Charging", "Deep Dielectric Charging"}
    medium = {"Attitude Disturbance", "Comms Degradation"}
    if kp >= 6 and effect_name in high:    return "#f44336", "HIGH"
    if kp >= 4 and effect_name in high:    return "#ff9800", "MOD"
    if kp >= 4 and effect_name in medium:  return "#ff9800", "MOD"
    return "#4caf50", "LOW"


# ── data fetching ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_kp_forecast():
    try:
        r = requests.get(KP_FORECAST_URL, timeout=10)
        r.raise_for_status()
        rows = []
        for item in r.json()[1:]:
            try:
                dt  = datetime.strptime(item[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                rows.append((dt, float(item[1])))
            except Exception:
                pass
        return rows
    except Exception as e:
        return []


import http.cookiejar as _cookiejar
import urllib.request as _urllib_req
import urllib.parse as _urllib_parse
import ssl as _ssl

try:
    import certifi as _certifi
except ImportError:
    _certifi = None


def _get_spacetrack_creds():
    """Read Space-Track credentials from st.secrets or environment."""
    try:
        return (
            st.secrets["spacetrack"]["username"],
            st.secrets["spacetrack"]["password"],
        )
    except (KeyError, FileNotFoundError):
        import os
        username = os.getenv("SPACETRACK_USERNAME")
        password = os.getenv("SPACETRACK_PASSWORD")
        if username and password:
            return username, password
        return None, None


def _build_opener():
    """Build a urllib opener with cookie support — mirrors the reference script."""
    cj = _cookiejar.CookieJar()
    handlers = [_urllib_req.HTTPCookieProcessor(cj)]
    if _certifi is not None:
        ssl_ctx = _ssl.create_default_context(cafile=_certifi.where())
        handlers.append(_urllib_req.HTTPSHandler(context=ssl_ctx))
    else:
        handlers.append(_urllib_req.HTTPSHandler())
    opener = _urllib_req.build_opener(*handlers)
    opener.addheaders = [
        ("User-Agent", "SSA-Dashboard/1.0 (Python urllib)"),
        ("Accept", "*/*"),
    ]
    return opener


def _spacetrack_login(opener, username, password):
    """POST login to Space-Track. Returns True on success."""
    data = _urllib_parse.urlencode({
        "identity": username,
        "password": password,
    }).encode("utf-8")
    req = _urllib_req.Request(SPACETRACK_LOGIN, data=data)
    try:
        resp = opener.open(req, timeout=30)
        body = resp.read().decode("utf-8", "replace")
        # Space-Track returns "Failed" in the body on bad credentials
        if "Failed" in body:
            return False, "Bad credentials — check username/password in secrets.toml"
        return True, None
    except Exception as e:
        return False, str(e)


@st.cache_data(ttl=600)
def fetch_tle(norad_id: int):
    """
    Fetch the latest TLE for a satellite from Space-Track.org by NORAD ID.
    Uses urllib + cookie jar — same method as the reference fetch script.
    Credentials from .streamlit/secrets.toml [spacetrack] or env vars.
    Returns (line1, line2) or None.
    """
    username, password = _get_spacetrack_creds()
    if not username or not password:
        st.error(
            "Space-Track credentials not found. "
            "Add [spacetrack] username and password to .streamlit/secrets.toml"
        )
        return None

    opener = _build_opener()

    # Step 1 — login
    ok, err = _spacetrack_login(opener, username, password)
    if not ok:
        st.error(f"Space-Track login failed: {err}")
        return None

    # Step 2 — query by NORAD CAT ID, same URL pattern as reference script
    url = (
        "https://www.space-track.org/basicspacedata/query/class/gp"
        f"/NORAD_CAT_ID/{int(norad_id)}"
        "/orderby/NORAD_CAT_ID%20ASC,EPOCH%20DESC"
        "/format/tle"
    )
    try:
        resp     = opener.open(url, timeout=60)
        tle_text = resp.read().decode("utf-8", "replace")
    except Exception as e:
        st.error(f"Space-Track TLE fetch failed: {e}")
        return None

    # Step 3 — parse TLE lines (same parser as reference script)
    lines = [ln.strip() for ln in tle_text.splitlines() if ln.strip()]
    i = 0
    while i + 1 < len(lines):
        l1, l2 = lines[i], lines[i + 1]
        if l1.startswith("1 ") and l2.startswith("2 "):
            return l1, l2
        i += 1

    st.warning(f"No TLE found for NORAD ID {norad_id}. "
               "Verify the ID exists on space-track.org.")
    return None


def propagate_orbit(tle1, tle2, minutes_ahead=100, step_sec=60):
    if not SGP4_OK:
        return []
    try:
        sat = Satrec.twoline2rv(tle1, tle2)
        now = datetime.now(timezone.utc)
        pts = []
        for s in range(0, minutes_ahead * 60, step_sec):
            t = now + timedelta(seconds=s)
            jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute,
                          t.second + t.microsecond / 1e6)
            e, r, v = sat.sgp4(jd, fr)
            if e != 0:
                continue
            x, y, z = r
            alt = math.sqrt(x**2 + y**2 + z**2) - 6371.0
            lat = math.degrees(math.asin(z / math.sqrt(x**2 + y**2 + z**2)))
            t_j2000 = (jd + fr - 2451545.0)
            gmst    = math.fmod(280.46061837 + 360.98564736629 * t_j2000, 360.0)
            lon     = (math.degrees(math.atan2(y, x)) - gmst + 180) % 360 - 180
            pts.append((lat, lon, alt, t))
        return pts
    except Exception:
        return []


def aurora_crossings(orbit_pts, kp):
    crossings, inside, entry_t = [], False, None
    for lat, lon, alt, t in orbit_pts:
        in_oval = AURORA_LAT_MIN <= abs(lat) <= AURORA_LAT_MAX
        if in_oval and not inside:
            inside, entry_t = True, t
        elif not in_oval and inside:
            inside = False
            crossings.append({"entry": entry_t, "exit": t,
                               "duration": (t - entry_t).total_seconds() / 60, "kp": kp})
    if inside and entry_t:
        crossings.append({"entry": entry_t, "exit": orbit_pts[-1][3],
                          "duration": (orbit_pts[-1][3] - entry_t).total_seconds() / 60, "kp": kp})
    return crossings


# ── UI sections ───────────────────────────────────────────────────────────────
def render_kp_strip(curr_kp, is_dark):
    bg, border, tc, sc = _palette(is_dark)
    risk_lbl, risk_col = kp_risk_label(curr_kp)
    st.markdown(f"""
    <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
      <div style="background:{bg};border:1px solid {border};border-radius:10px;
           padding:12px 20px;flex:1;min-width:130px;text-align:center;">
        <div style="font-size:0.7rem;color:{sc};text-transform:uppercase;
             letter-spacing:.06em;margin-bottom:4px;">Current Kp</div>
        <div style="font-size:2rem;font-weight:800;color:{risk_col};">{curr_kp:.1f}</div>
        <div style="font-size:0.78rem;color:{risk_col};font-weight:600;">{risk_lbl}</div>
      </div>
      <div style="background:{bg};border:1px solid {border};border-radius:10px;
           padding:12px 20px;flex:1;min-width:130px;text-align:center;">
        <div style="font-size:0.7rem;color:{sc};text-transform:uppercase;
             letter-spacing:.06em;margin-bottom:4px;">Aurora Oval</div>
        <div style="font-size:1rem;font-weight:700;color:{tc};margin-top:8px;">60°–75° lat</div>
        <div style="font-size:0.78rem;color:{sc};">Both hemispheres</div>
      </div>
      <div style="background:{bg};border:1px solid {border};border-radius:10px;
           padding:12px 20px;flex:1;min-width:130px;text-align:center;">
        <div style="font-size:0.7rem;color:{sc};text-transform:uppercase;
             letter-spacing:.06em;margin-bottom:4px;">Data Source</div>
        <div style="font-size:0.85rem;font-weight:600;color:{tc};margin-top:8px;">NOAA SWPC</div>
        <div style="font-size:0.78rem;color:{sc};">Updated every 5 min</div>
      </div>
    </div>""", unsafe_allow_html=True)


def render_kp_chart(kp_rows, curr_kp, is_dark):
    if not kp_rows or not PLOTLY_OK:
        return
    _, border, tc, sc = _palette(is_dark)
    now    = datetime.now(timezone.utc)
    future = [(dt, kp) for dt, kp in kp_rows if dt >= now - timedelta(hours=1)][:28]
    if not future:
        return
    dts  = [r[0].strftime("%d %b %H:%M") for r in future]
    kps  = [r[1] for r in future]
    cols = [kp_risk_label(k)[1] for k in kps]
    fig  = go.Figure()
    fig.add_trace(go.Bar(x=dts, y=kps, marker_color=cols,
                         hovertemplate="%{x}<br>Kp: %{y}<extra></extra>"))
    fig.add_hline(y=4, line_dash="dot", line_color="#ff9800",
                  annotation_text="Moderate (4)", annotation_font_color="#ff9800",
                  annotation_position="top left")
    fig.add_hline(y=6, line_dash="dot", line_color="#f44336",
                  annotation_text="High (6)", annotation_font_color="#f44336",
                  annotation_position="top left")
    fig.update_layout(
        title       = dict(text="Kp Index Forecast (next ~24 h)",
                           font=dict(color=tc, size=13)),
        height      = 220,
        margin      = dict(l=40, r=20, t=40, b=70),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor ="rgba(0,0,0,0)",
        yaxis=dict(range=[0, 9], gridcolor=border, color=sc, title="Kp"),
        xaxis=dict(tickangle=-45, color=sc, gridcolor="rgba(0,0,0,0)"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_globe(orbit_pts, sat_name, curr_kp, is_dark):
    if not PLOTLY_OK or not orbit_pts:
        return
    _, risk_col = kp_risk_label(curr_kp)
    fig = go.Figure()

    # aurora band fill — northern
    band_lats, band_lons = [], []
    for lon in range(-180, 181, 5):
        band_lats.append(AURORA_LAT_MIN); band_lons.append(lon)
    for lon in range(180, -181, -5):
        band_lats.append(AURORA_LAT_MAX); band_lons.append(lon)
    alpha = min(0.15 + curr_kp * 0.03, 0.5)
    for hem, name in [(1, "Aurora (N)"), (-1, "Aurora (S)")]:
        fig.add_trace(go.Scattergeo(
            lat=[hem * l for l in band_lats], lon=band_lons,
            mode="lines", fill="toself",
            fillcolor=f"rgba(0,220,100,{alpha})",
            line=dict(width=0), name=name))

    # ground track
    lats  = [p[0] for p in orbit_pts]
    lons  = [p[1] for p in orbit_pts]
    times = [p[3].strftime("%H:%M UTC") for p in orbit_pts]
    alts  = [p[2] for p in orbit_pts]
    fig.add_trace(go.Scattergeo(
        lat=lats, lon=lons, mode="lines",
        line=dict(color="#00aaff", width=2),
        name=f"{sat_name} track",
        text=[f"{t}<br>Alt: {a:.0f} km" for t, a in zip(times, alts)],
        hovertemplate="%{text}<extra></extra>"))
    # current position
    fig.add_trace(go.Scattergeo(
        lat=[lats[0]], lon=[lons[0]],
        mode="markers+text",
        marker=dict(size=12, color="#ffeb3b",
                    line=dict(color="#000", width=1)),
        text=[f"  {sat_name}"],
        textfont=dict(color="#ffeb3b", size=11),
        textposition="middle right",
        name="Now",
        hovertemplate=f"Lat: %{{lat:.2f}}°  Lon: %{{lon:.2f}}°<extra></extra>"))

    fig.update_geos(
        projection_type="orthographic",
        showland=True,    landcolor="#1a2a3a",
        showocean=True,   oceancolor="#0a1520",
        showcountries=True, countrycolor="#2a4a6a",
        showcoastlines=True, coastlinecolor="#2a4a6a",
        showframe=False,  bgcolor="#050d14",
        lataxis_showgrid=True, lonaxis_showgrid=True,
        lataxis_gridcolor="rgba(100,150,200,0.12)",
        lonaxis_gridcolor="rgba(100,150,200,0.12)",
    )
    fig.update_layout(
        height=500, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#050d14",
        legend=dict(bgcolor="rgba(10,20,35,0.85)",
                    bordercolor="#1e3a50", borderwidth=1,
                    font=dict(color="#c8dce8", size=11),
                    x=0.01, y=0.99),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_crossing_cards(crossings, curr_kp, is_dark):
    bg, border, tc, sc = _palette(is_dark)
    now = datetime.now(timezone.utc)
    for c in crossings[:4]:
        risk, col = kp_risk_label(c["kp"])
        is_active = c["entry"] <= now <= c["exit"]
        status    = "🔴 ACTIVE NOW" if is_active else f"Entry: {c['entry'].strftime('%H:%M UTC')}"
        dur_m     = int(c["duration"])
        dur_s     = int((c["duration"] % 1) * 60)
        warning   = ""
        if c["kp"] >= 6:
            warning = f"""<div style="margin-top:10px;background:rgba(244,67,54,0.12);
                border-left:3px solid #f44336;padding:8px 12px;border-radius:6px;
                font-size:0.8rem;color:#f44336;">
                ⚠️ Kp ≥ 6 — avoid non-critical commands. Increase telemetry monitoring.</div>"""
        st.markdown(f"""
        <div style="background:{bg};border:1px solid {col};border-radius:10px;
             padding:14px 16px;margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-weight:700;color:{tc};font-size:0.9rem;">Aurora Crossing</span>
            <span style="background:{col};color:#fff;font-size:0.72rem;font-weight:700;
                  padding:2px 9px;border-radius:20px;">{risk}</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px;">
            <div>
              <div style="font-size:0.7rem;color:{sc};text-transform:uppercase;
                   letter-spacing:.05em;">Status</div>
              <div style="font-weight:600;color:{col};font-size:0.85rem;">{status}</div>
            </div>
            <div>
              <div style="font-size:0.7rem;color:{sc};text-transform:uppercase;
                   letter-spacing:.05em;">Duration</div>
              <div style="font-weight:600;color:{tc};font-size:0.85rem;">
                  {dur_m} min {dur_s:02d} sec</div>
            </div>
            <div>
              <div style="font-size:0.7rem;color:{sc};text-transform:uppercase;
                   letter-spacing:.05em;">Kp</div>
              <div style="font-weight:700;color:{col};font-size:1.1rem;">{c['kp']:.1f}</div>
            </div>
            <div>
              <div style="font-size:0.7rem;color:{sc};text-transform:uppercase;
                   letter-spacing:.05em;">Exit</div>
              <div style="font-weight:600;color:{tc};font-size:0.85rem;">
                  {c['exit'].strftime('%H:%M UTC')}</div>
            </div>
          </div>
          {warning}
        </div>""", unsafe_allow_html=True)


def render_commanding_rule(curr_kp, in_aurora, is_dark):
    bg, border, tc, sc = _palette(is_dark)

    # theme-aware code block colours
    code_bg   = "#0d1b2a" if is_dark else "#f0f6fc"
    code_text = "#a8d8ea" if is_dark else "#1a3a52"
    kw_col    = "#7a9bb5" if is_dark else "#4a6b85"
    act_col   = "#e6f1f5" if is_dark else "#0d2137"

    if in_aurora and curr_kp >= 6:
        sbg, sbdr, ico, stxt, scol = ("rgba(244,67,54,0.12)", "#f44336", "🔴",
                                       "RULE ACTIVE — Restrictions apply", "#f44336")
        action = "Avoid non-critical commands. Increase telemetry monitoring frequency."
    elif in_aurora and curr_kp >= 4:
        sbg, sbdr, ico, stxt, scol = ("rgba(255,152,0,0.12)", "#ff9800", "🟡",
                                       "CAUTION — Satellite in auroral region", "#ff9800")
        action = "Monitor telemetry closely. Defer non-essential operations."
    else:
        sbg, sbdr, ico, stxt, scol = ("rgba(76,175,80,0.12)", "#4caf50", "🟢",
                                       "NOMINAL — No restrictions", "#4caf50")
        action = "Normal operations permitted. Continue routine monitoring."

    cond_col = "#f44336" if (in_aurora and curr_kp >= 6) else ("#ff9800" if in_aurora else "#4caf50")
    st.markdown(f"""
    <div style="background:{bg};border:1px solid {border};border-radius:10px;
         padding:16px 18px;margin-bottom:16px;">
      <div style="font-weight:700;color:{tc};font-size:0.9rem;margin-bottom:12px;">
          Commanding Rule Evaluation</div>
      <div style="font-family:monospace;background:{code_bg};border:1px solid {border};
           border-radius:8px;padding:12px 14px;font-size:0.8rem;
           color:{code_text};margin-bottom:12px;line-height:1.8;">
        <span style="color:{kw_col};font-weight:600;">IF</span>
        <span style="color:{cond_col};font-weight:700;">
            satellite {"inside" if in_aurora else "outside"} auroral oval
        </span>
        <span style="color:{kw_col};"> AND </span>
        <span style="color:{cond_col};font-weight:700;">Kp = {curr_kp:.1f}</span><br>
        <span style="color:{kw_col};font-weight:600;">THEN</span>
        <span style="color:{act_col};"> {action}</span>
      </div>
      <div style="background:{sbg};border-left:3px solid {sbdr};
           padding:9px 13px;border-radius:6px;">
        <span style="font-weight:700;color:{scol};">{ico} {stxt}</span>
      </div>
    </div>""", unsafe_allow_html=True)


def render_effects_table(curr_kp, is_dark):
    bg, border, tc, sc = _palette(is_dark)
    hdr = "#0a1520" if is_dark else "#e8f0f8"
    rows = ""
    for effect, desc in OPERATIONAL_EFFECTS:
        col, sev = effect_severity(effect, curr_kp)
        rows += f"""<tr>
          <td style="padding:8px 12px;color:{tc};font-weight:600;
               font-size:0.82rem;">{effect}</td>
          <td style="padding:8px 12px;color:{sc};font-size:0.81rem;">{desc}</td>
          <td style="padding:8px 12px;text-align:center;">
            <span style="background:{col};color:#fff;font-size:0.7rem;font-weight:700;
                  padding:2px 8px;border-radius:12px;">{sev}</span>
          </td></tr>"""
    st.markdown(f"""
    <div style="background:{bg};border:1px solid {border};border-radius:10px;
         overflow:hidden;margin-bottom:16px;">
      <div style="padding:12px 16px;font-weight:700;font-size:0.9rem;color:{tc};
           border-bottom:1px solid {border};">Operational Effects at Kp {curr_kp:.1f}</div>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:{hdr};">
            <th style="padding:7px 12px;text-align:left;font-size:0.72rem;
                 color:{sc};text-transform:uppercase;letter-spacing:.05em;">Risk</th>
            <th style="padding:7px 12px;text-align:left;font-size:0.72rem;
                 color:{sc};text-transform:uppercase;letter-spacing:.05em;">Effect</th>
            <th style="padding:7px 12px;text-align:center;font-size:0.72rem;
                 color:{sc};text-transform:uppercase;letter-spacing:.05em;">Level</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>""", unsafe_allow_html=True)


def _palette(is_dark):
    if is_dark:
        return "#0d1b2a", "#1e3a50", "#e6f1f5", "#7a9bb5"
    return "#ffffff", "#c5d8ec", "#0d2137", "#4a6b85"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def render():
    is_dark = st.session_state.get("theme", "dark") == "dark"
    bg, border, tc, sc = _palette(is_dark)

    # ── Theme-aware selectbox / dropdown CSS ──────────────────────────────────
    # Streamlit's baseweb select ignores Streamlit's own theme vars for dropdowns,
    # so we override manually based on the current theme.
    if is_dark:
        sel_bg      = "#0d1b2a"
        sel_text    = "#e6f1f5"
        sel_border  = "#1e3a50"
        sel_hover   = "#1a3a52"
        sel_sel     = "#1e4a68"
    else:
        sel_bg      = "#ffffff"
        sel_text    = "#0d2137"
        sel_border  = "#c5d8ec"
        sel_hover   = "#e3f0fb"
        sel_sel     = "#cce0f5"

    st.markdown(f"""
    <style>
    /* ── selectbox control ── */
    div[data-baseweb="select"] > div {{
        background-color: {sel_bg} !important;
        color: {sel_text} !important;
        border: 1px solid {sel_border} !important;
    }}
    div[data-baseweb="select"] > div:focus-within {{
        border-color: {sel_border} !important;
        box-shadow: 0 0 0 1px {sel_border} !important;
    }}
    /* selected value text */
    div[data-baseweb="select"] span {{
        color: {sel_text} !important;
    }}
    /* dropdown popover container */
    div[data-baseweb="popover"] > div,
    div[data-baseweb="menu"] {{
        background-color: {sel_bg} !important;
        border: 1px solid {sel_border} !important;
    }}
    /* each option row */
    li[role="option"] {{
        background-color: {sel_bg} !important;
        color: {sel_text} !important;
    }}
    li[role="option"]:hover {{
        background-color: {sel_hover} !important;
    }}
    li[aria-selected="true"] {{
        background-color: {sel_sel} !important;
        color: {sel_text} !important;
    }}
    /* radio buttons label text */
    div[data-testid="stRadio"] label p {{
        color: {sel_text} !important;
    }}
    /* text input */
    div[data-testid="stTextInput"] input {{
        background-color: {sel_bg} !important;
        color: {sel_text} !important;
        border: 1px solid {sel_border} !important;
    }}
    div[data-testid="stTextInput"] input::placeholder {{
        color: {"#4a6a85" if is_dark else "#8aaac0"} !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    # ── Back to Home + page title row ─────────────────────────────────────────
    col_title, col_back = st.columns([3, 1])
    with col_title:
        st.markdown(
            f"<h2 style='color:{tc};margin:0 0 2px;font-size:1.4rem;'>"
            f"Space Weather Monitoring</h2>"
            f"<p style='color:{sc};font-size:0.83rem;margin-bottom:14px;'>"
            f"Live aurora forecast · Satellite orbit tracking · Operational risk</p>",
            unsafe_allow_html=True)
    with col_back:
        if st.button("← Back to Home", key="sw_back_home"):
            st.session_state["page"] = "home"
            st.query_params["page"]  = "home"
            st.rerun()

    # ── fetch Kp (always runs) ────────────────────────────────────────────────
    kp_rows = fetch_kp_forecast()
    now     = datetime.now(timezone.utc)
    past_kp = [(dt, kp) for dt, kp in kp_rows if dt <= now]
    curr_kp = past_kp[-1][1] if past_kp else (kp_rows[0][1] if kp_rows else 2.0)

    # ── top Kp strip ──────────────────────────────────────────────────────────
    render_kp_strip(curr_kp, is_dark)

    # ── missing deps warning ──────────────────────────────────────────────────
    if not SGP4_OK or not PLOTLY_OK:
        missing = []
        if not SGP4_OK:   missing.append("`sgp4`")
        if not PLOTLY_OK: missing.append("`plotly`")
        st.warning(
            f"⚠️ Install {' and '.join(missing)} for orbit tracking and globe: "
            f"`pip install {' '.join(m.strip('`') for m in missing)}`"
        )

    # ── two-column layout ─────────────────────────────────────────────────────
    col_left, col_right = st.columns([1.6, 1], gap="medium")

    # ════ LEFT — aurora images + globe ═══════════════════════════════════════
    with col_left:
        tab_n, tab_s = st.tabs(["🌐 Northern Hemisphere", "🌐 Southern Hemisphere"])
        with tab_n:
            st.image(
                NOAA_AURORA_NORTH + f"?cb={int(time.time() // 300)}",
                caption="NOAA OVATION Aurora Forecast — Northern Hemisphere",
                use_container_width=True,
            )
        with tab_s:
            st.image(
                NOAA_AURORA_SOUTH + f"?cb={int(time.time() // 300)}",
                caption="NOAA OVATION Aurora Forecast — Southern Hemisphere",
                use_container_width=True,
            )

        if PLOTLY_OK and st.session_state.get("orbit_pts"):
            st.markdown(
                f"<div style='font-weight:700;color:{tc};font-size:0.9rem;"
                f"margin:14px 0 6px;'>Satellite Orbit Globe</div>",
                unsafe_allow_html=True)
            render_globe(
                st.session_state["orbit_pts"],
                st.session_state.get("last_sat_label", "Satellite"),
                curr_kp, is_dark)

    # ════ RIGHT — selector + intelligence panels ══════════════════════════════
    with col_right:
        st.markdown(
            f"<div style='font-weight:700;color:{tc};font-size:0.9rem;"
            f"margin-bottom:8px;'>Satellite Selection</div>",
            unsafe_allow_html=True)

        mode = st.radio("mode", ["Quick pick", "Enter NORAD ID"],
                        horizontal=True, label_visibility="collapsed",
                        key="sat_mode")

        norad_id    = None
        sat_label   = ""

        if mode == "Quick pick":
            choice    = st.selectbox("sat", list(POPULAR_SATS.keys()),
                                     label_visibility="collapsed", key="sat_quick")
            norad_id, sat_label = POPULAR_SATS[choice]

        else:
            norad_input = st.text_input(
                "NORAD Catalog ID",
                placeholder="e.g. 25544 (ISS), 43678 (DIWATA-2)",
                label_visibility="collapsed",
                key="sat_norad_input",
            )
            # show a handy reference table
            with st.expander("📋 Common NORAD IDs"):
                ref_bg  = "#0a1520" if is_dark else "#f0f6fc"
                ref_col = "#a8d8ea" if is_dark else "#1a3a52"
                rows_html = "".join(
                    f"<tr><td style='padding:4px 10px;color:{ref_col};font-family:monospace;"
                    f"font-size:0.8rem;'>{nid}</td>"
                    f"<td style='padding:4px 10px;color:{sc};font-size:0.8rem;'>{lbl}</td></tr>"
                    for lbl, (nid, _) in POPULAR_SATS.items()
                )
                st.markdown(
                    f"<table style='width:100%;background:{ref_bg};"
                    f"border-radius:8px;overflow:hidden;'>"
                    f"<tr><th style='padding:5px 10px;text-align:left;font-size:0.72rem;"
                    f"color:{sc};'>NORAD ID</th>"
                    f"<th style='padding:5px 10px;text-align:left;font-size:0.72rem;"
                    f"color:{sc};'>Satellite</th></tr>"
                    f"{rows_html}</table>",
                    unsafe_allow_html=True,
                )

            if norad_input.strip().isdigit():
                norad_id  = int(norad_input.strip())
                sat_label = f"NORAD {norad_id}"
            elif norad_input.strip():
                st.warning("NORAD ID must be a number (e.g. 25544).")

        mins = st.slider("Ground track (minutes)", 30, 200, 100, 10, key="sat_mins")

        if st.button("🔄  Load Satellite", use_container_width=True, key="load_sat"):
            if norad_id is None:
                st.warning("Select or enter a NORAD ID first.")
            elif not SGP4_OK:
                st.error("Install sgp4 first: `pip install sgp4`")
            else:
                with st.spinner(f"Fetching TLE for NORAD {norad_id}…"):
                    tle = fetch_tle(norad_id)
                if not tle:
                    st.error(f"No TLE returned for NORAD ID {norad_id}.")
                else:
                    with st.spinner("Propagating orbit…"):
                        pts = propagate_orbit(tle[0], tle[1], mins)
                    if pts:
                        st.session_state["orbit_pts"]       = pts
                        st.session_state["last_sat_label"]  = sat_label
                        st.session_state["last_norad_id"]   = norad_id
                        st.success(f"✅ {sat_label} loaded — {len(pts)} track points")
                        st.rerun()
                    else:
                        st.error("Orbit propagation returned no points.")

        st.divider()

        # ── aurora crossings & commanding rule ────────────────────────────────
        orbit_pts = st.session_state.get("orbit_pts", [])

        if orbit_pts:
            sat_name  = st.session_state.get("last_sat_label", "Satellite")
            crossings = aurora_crossings(orbit_pts, curr_kp)
            cur_lat   = orbit_pts[0][0]
            in_aurora = AURORA_LAT_MIN <= abs(cur_lat) <= AURORA_LAT_MAX

            st.markdown(
                f"<div style='font-weight:700;color:{tc};font-size:0.9rem;"
                f"margin-bottom:8px;'>Aurora Crossings — {sat_name}</div>",
                unsafe_allow_html=True)

            if crossings:
                render_crossing_cards(crossings, curr_kp, is_dark)
            else:
                st.markdown(
                    f"<div style='background:{bg};border:1px solid {border};"
                    f"border-radius:10px;padding:12px 14px;color:{sc};font-size:0.83rem;'>"
                    f"✅ No aurora crossings in the next {mins} min.</div>",
                    unsafe_allow_html=True)

            render_commanding_rule(curr_kp, in_aurora, is_dark)

        else:
            st.markdown(
                f"<div style='background:{bg};border:1px dashed {border};"
                f"border-radius:10px;padding:24px;text-align:center;color:{sc};"
                f"font-size:0.85rem;'>Select a satellite and click<br>"
                f"<b style='color:{tc};'>🔄 Load Satellite</b><br>"
                f"to see aurora crossings,<br>orbit globe, and commanding rules.</div>",
                unsafe_allow_html=True)

    # ── full-width bottom panels ──────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    render_effects_table(curr_kp, is_dark)

    if PLOTLY_OK:
        render_kp_chart(kp_rows, curr_kp, is_dark)

    # ── bottom back-to-home button ────────────────────────────────────────────
    st.markdown("---")
    if st.button("← Back to Home", key="sw_back_home_bottom"):
        st.session_state["page"] = "home"
        st.query_params["page"]  = "home"
        st.rerun()