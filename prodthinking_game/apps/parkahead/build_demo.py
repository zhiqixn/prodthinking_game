"""Build the ParkAhead artifact demo: the same page with a data snapshot embedded.

Claude artifacts can't fetch from data.gov.sg or OneMap, so the demo carries a
snapshot of HDB carpark info + live lots (taken when this runs) and a few
destinations geocoded now. The live app is apps/parkahead/index.html on GitHub Pages.

Usage: python3 apps/parkahead/build_demo.py   (from prodthinking_game/)
Writes build/parkahead-demo.html
"""
import json
import re
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LIVE_URL = "https://zhiqixn.github.io/prodthinking_game/apps/parkahead/"
INFO_URL = "https://data.gov.sg/api/action/datastore_search?resource_id=d_23f946fa557947f93a8043bbef41dd09&limit=5000"
AVAIL_URL = "https://api.data.gov.sg/v1/transport/carpark-availability"
SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search?returnGeom=Y&getAddrDetails=Y&pageNum=1&searchVal="
PRESETS = [
    ("Toa Payoh HDB Hub", "HDB HUB"),
    ("Ang Mo Kio Hub", "AMK HUB"),
    ("Our Tampines Hub", "OUR TAMPINES HUB"),
    ("Clementi Mall", "CLEMENTI MALL"),
    ("Punggol Waterway Point", "WATERWAY POINT"),
    ("Bedok Mall", "BEDOK MALL"),
    ("Chinatown Complex", "CHINATOWN COMPLEX"),
    ("Jurong East MRT", "JURONG EAST MRT STATION"),
]


def get(url, tries=5):
    req = urllib.request.Request(url, headers={"User-Agent": "parkahead-demo-build", "Accept": "application/json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))  # rate-limited: back off and retry


def main():
    info = get(INFO_URL)["result"]["records"]
    rows = [[r["car_park_no"], r["address"], r["x_coord"], r["y_coord"], r["car_park_type"], r["type_of_parking_system"],
             r["short_term_parking"], r["free_parking"], r["night_parking"], r["car_park_decks"], r["gantry_height"]] for r in info]
    av = get(AVAIL_URL)["items"][0]
    taken_at = int(time.time() * 1000)
    presets = []
    for label, q in PRESETS:
        res = get(SEARCH_URL + urllib.parse.quote(q)).get("results") or []
        if not res:
            print("no geocode for", q)
            continue
        presets.append({"label": label, "x": float(res[0]["X"]), "y": float(res[0]["Y"])})
        time.sleep(2)
    snap = {"takenAt": taken_at, "liveUrl": LIVE_URL, "info": rows, "avail": av["carpark_data"], "presets": presets}
    data = json.dumps(snap, separators=(",", ":")).replace("</", "<\\/")

    html = (HERE / "index.html").read_text()
    marker = '<script id="snapshot" type="application/json">null</script>'
    assert marker in html
    html = html.replace(marker, f'<script id="snapshot" type="application/json">{data}</script>')
    # The Artifact host adds its own document skeleton
    html = re.sub(r"<!DOCTYPE html>\s*", "", html, flags=re.I)
    html = re.sub(r"</?(html|head|body)\b[^>]*>\s*", "", html, flags=re.I)
    html = re.sub(r'<meta (charset|name="viewport")[^>]*>\s*', "", html, flags=re.I)

    out = ROOT / "build" / "parkahead-demo.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(out.relative_to(ROOT), f"{len(html) // 1024} KB", f"{len(rows)} carparks", f"{len(av['carpark_data'])} live", f"{len(presets)} presets")


if __name__ == "__main__":
    main()
