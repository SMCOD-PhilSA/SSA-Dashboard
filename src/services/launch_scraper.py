import requests
from bs4 import BeautifulSoup


URL = "https://www.spacelaunchschedule.com/category/china-aerospace-science-and-technology-corporation/"

VALID_SITES = [
    "Xichang Satellite Launch Center",
    "Naro Space Center",
    "Wenchang Space Launch Site",
    "Hainan Commercial Space Launch Site",
    "Hainan International Commercial Launch Center"
]


def fetch_china_launches():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        res = requests.get(URL, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        launches = []

        cards = soup.select("div.launch-list-thumbnail")

        for card in cards:
            try:
                title_tag = card.select_one("h2.entry-title")
                rocket = title_tag.get_text(strip=True).replace("\n", " ") if title_tag else "Unknown"

                time_tag = card.select_one("time.launchDateTime")
                if time_tag:
                    date = time_tag.get_text(" ", strip=True)
                else:
                    date = "TBD"

                site_tag = card.select_one("div.col.h6.mb-0.pt-2")
                site = site_tag.get_text(strip=True) if site_tag else None

                if site:
                    if not any(valid in site for valid in VALID_SITES):
                        continue

                launches.append({
                    "rocket": rocket,
                    "date": clean_time(date),
                    "site": site if site else "TBD"
                })

            except Exception:
                continue

        return launches[:5], None

    except Exception as e:
        return [], str(e)


def clean_time(text):
    text = text.replace("GMT+8", "").strip()
    text = text.replace("•", "-")
    text = " ".join(text.split())
    return text