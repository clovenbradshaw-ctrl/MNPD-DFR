import json, time, sys
import requests

BASE = "https://maps.nashville.gov/arcgis/rest/services/Addressing/AddressPoints/MapServer/0/query"
XMIN, YMIN, XMAX, YMAX = -86.730, 36.246, -86.655, 36.305   # flight bbox + margin

def page(start_oid, count=2000):
    where = "1=1"
    url = (f"{BASE}?where={where}&geometry={XMIN},{YMIN},{XMAX},{YMAX}"
           "&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326"
           f"&outFields=*&returnGeometry=true&f=geojson"
           f"&resultOffset={start_oid}&resultRecordCount={count}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()

fc = {"type": "FeatureCollection", "features": []}
oid = 0
total = None
while True:
    d = page(oid)
    if total is None:
        total = d.get("properties", {}).get("totalFeatures")
        print("totalFeatures in extent:", total)
    feats = d.get("features", [])
    if not feats:
        break
    fc["features"].extend(feats)
    oid += len(feats)
    print(f"  fetched {len(fc['features'])} ...")
    if len(feats) < 2000:
        break
    time.sleep(0.3)

print("total:", len(fc["features"]))
with open("nashville_addresses.json", "w") as fh:
    json.dump(fc, fh)

# sanity sample
feat = fc["features"][0]
print("sample props:", {k: feat["properties"].get(k) for k in
      ["FullAddress", "Number", "StreetName", "City", "Zip", "apn"]})
print("geom type:", feat["geometry"]["type"], feat["geometry"]["coordinates"])