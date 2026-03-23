import json
import os
from collections import Counter
import streamlit as st

LOCAL_PATH = "data/satcat.json"


def infer_country(name):
    name = name.upper()

    mapping = {
        "STARLINK": "US",
        "GPS": "US",
        "NAVSTAR": "US",

        "COSMOS": "RU",
        "GLONASS": "RU",

        "YAOGAN": "CN",
        "BEIDOU": "CN",

        "ONEWEB": "UK",

        "GSAT": "IN",
        "IRNSS": "IN",

        "QZS": "JP"
    }

    for key, val in mapping.items():
        if key in name:
            return val

    return None


@st.cache_data(ttl=600)
def get_active_leo_by_country(limit=10):
    if not os.path.exists(LOCAL_PATH):
        return [], [], "satcat.json not found"

    with open(LOCAL_PATH, "r") as f:
        data = json.load(f)

    countries = []

    for obj in data:
        try:
            mm = float(obj.get("MEAN_MOTION", 0))
            name = obj.get("OBJECT_NAME", "")

            if mm > 11:
                country = obj.get("COUNTRY")

                if not country or country in ["UNK", ""]:
                    country = infer_country(name)

                if country:
                    countries.append(country)

        except:
            continue

    if not countries:
        return [], [], "No valid LEO satellites"

    counter = Counter(countries)
    top = counter.most_common(limit)

    labels = [c[0] for c in top]
    values = [c[1] for c in top]

    return labels, values, None