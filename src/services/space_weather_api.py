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


def classify_kp(kp):
    if kp < 3:
        return "Quiet"
    elif kp < 5:
        return "Unsettled"
    elif kp < 6:
        return "Minor Storm"
    elif kp < 7:
        return "Moderate Storm"
    elif kp < 8:
        return "Strong Storm"
    return "Severe Storm"


def get_kp_index():
    url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
    data = safe_json(url)

    if not data:
        return {"kp": "N/A", "status": "No Data"}

    try:
        latest = data[-1]
        kp = float(latest["kp"])
    except Exception:
        return {"kp": "N/A", "status": "No Data"}

    return {"kp": kp, "status": classify_kp(kp)}


def get_daily_kp():
    url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
    data = safe_json(url)

    if not data:
        return ["No Data"], [0]

    today = date.today()
    start_date = today - timedelta(days=7)
    end_date = today + timedelta(days=2)

    daily = defaultdict(list)

    for row in data:
        try:
            dt = datetime.strptime(row["time_tag"], "%Y-%m-%dT%H:%M:%S")
            d = dt.date()

            if start_date <= d <= end_date:
                kp = float(row["kp"])
                daily[d].append(kp)

        except Exception:
            continue

    if not daily:
        return ["No Data"], [0]

    ordered_days = sorted(daily.keys())

    labels = [d.strftime("%b %d") for d in ordered_days]
    values = [round(sum(daily[d]) / len(daily[d]), 2) for d in ordered_days]

    return labels, values