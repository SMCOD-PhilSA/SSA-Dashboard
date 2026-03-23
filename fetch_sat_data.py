import requests
import json

URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json"

resp = requests.get(URL, timeout=30)

if resp.status_code != 200:
    raise Exception(f"Fetch failed: {resp.status_code}")

data = resp.json()

with open("data/sat_data.json", "w") as f:
    json.dump(data, f)

print("Data saved successfully")