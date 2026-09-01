"""
fetch_nashville_flights.py — pulls this trial's flights straight from MNPD's
one Skydio FeatureServer and writes nashville_flights.geojson.

scripts/dfr.py is the general tool this is derived from: it discovers and
polls every agency on Skydio's public ArcGIS org (900+, as of writing) on a
timer. That's the right tool for running the whole DFR-transparency effort,
but wrong for this repo, which only ever needs one already-known agency.
Rather than run the 900-agency crawl (and its Nominatim geocoding pass) just
to reach the one service this trial uses, this hardcodes that service's URL
— found in this repo's own README credits — and fetches it directly, with
the same pagination logic dfr.py uses (real maxRecordCount, page while
exceededTransferLimit or a full page came back).

Stdlib only (urllib) — no pip install needed to run this one.

Run: python3 scripts/fetch_nashville_flights.py
Writes: nashville_flights.geojson (raw pull, one row per upstream record —
the feed double-logs some flights; build_explorer_data.py dedupes by
flight_id downstream, same as it already does today).
"""
import json
from urllib.parse import urlencode
from urllib.request import urlopen

FS = ("https://services7.arcgis.com/mnhQTdIYDA7UoY2l/arcgis/rest/services/"
      "678dee26-6aa8-4d60-bf1c-30c7b0f6b517-production/FeatureServer")
OUT = "nashville_flights.geojson"


def get(params):
    with urlopen(f"{FS}/0/query?{urlencode(params)}", timeout=60) as r:
        return json.load(r)


def fetch_all():
    page = 2000
    try:
        with urlopen(f"{FS}/0?f=json", timeout=60) as r:
            meta = json.load(r)
        srv = meta.get("maxRecordCount")
        if srv:
            page = min(page, int(srv))
    except Exception:
        pass

    feats, offset, pages = [], 0, 0
    while True:
        j = get({
            "where": "1=1", "outFields": "*", "returnGeometry": "true",
            "outSR": "4326", "orderByFields": "OBJECTID ASC",
            "resultOffset": offset, "resultRecordCount": page, "f": "geojson",
        })
        batch = j.get("features", []) or []
        feats.extend(batch)
        pages += 1
        more = bool(j.get("properties", {}).get("exceededTransferLimit")
                     or j.get("exceededTransferLimit")) or len(batch) == page
        print(f"  page {pages}: +{len(batch)} (total {len(feats)})")
        if not batch or not more:
            break
        offset += len(batch)
    return feats


if __name__ == "__main__":
    count = get({"where": "1=1", "returnCountOnly": "true", "f": "json"}).get("count")
    print(f"server reports {count} features")
    features = fetch_all()
    if count is not None and len(features) < count:
        print(f"! WARNING: fetched {len(features)} but count says {count} "
              f"-- possible server cap; not all flights retrieved")
    with open(OUT, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)
    print(f"wrote {len(features)} features -> {OUT}")
