import requests
from datetime import datetime, date, timedelta
from collections import defaultdict


def safe_json(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        return []


def get_kp_index():
    url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    data = safe_json(url)

    if not data or len(data) < 2:
        return {"kp": "N/A", "status": "No Data"}

    try:
        latest = data[-1]
        kp = float(latest[1])
    except Exception:
        return {"kp": "N/A", "status": "No Data"}

    if kp < 3:
        status = "Quiet"
    elif kp < 5:
        status = "Unsettled"
    elif kp < 6:
        status = "Minor Storm"
    elif kp < 7:
        status = "Moderate Storm"
    elif kp < 8:
        status = "Strong Storm"
    else:
        status = "Severe Storm"

    return {"kp": kp, "status": status}


def get_daily_kp():
    url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
    data = safe_json(url)

    if not data or len(data) < 2:
        return [], []

    today = date.today()
    history_start = today - timedelta(days=7)
    forecast_end = today + timedelta(days=2)

    daily = defaultdict(list)

    for row in data[1:]:
        try:
            time_tag = row[0]
            kp = float(row[1])
            dt = datetime.strptime(time_tag, "%Y-%m-%d %H:%M:%S")
            d = dt.date()

            if history_start <= d <= forecast_end:
                daily[d].append(kp)
        except Exception:
            continue

    if not daily:
        return [], []

    ordered_days = sorted(daily.keys())
    labels = [d.strftime("%b %d") for d in ordered_days]
    values = [sum(daily[d]) / len(daily[d]) for d in ordered_days]

    return labels, values