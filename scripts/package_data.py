"""
package_data.py — the last, previously-missing step: takes build_explorer_data.py's
raw output plus the intersection inputs and produces exactly what data/ ships
and index.html reads: dfr_sensitive.json, dfr_addresses_light.json (summary,
no per-flight detail, loads instantly), dfr_addresses.json.gz (full detail),
nashville_flights.geojson.gz, and sensitive_sites.json — all landed in data/.

Run last, after build_explorer_data.py.
"""
import gzip, json, shutil

LIGHT_KEYS = ["apn", "full_address", "city", "zip", "lat", "lng",
              "closest_pass_m", "n_flights", "first_overflight_ct", "last_overflight_ct"]

# --- addresses: split into light (summary) + full (gzipped) ---
addr = json.load(open("dfr_addresses.json"))
light = [{k: a.get(k) for k in LIGHT_KEYS} for a in addr]
json.dump(light, open("data/dfr_addresses_light.json", "w"))
print("data/dfr_addresses_light.json:", len(light), "addresses")

with gzip.open("data/dfr_addresses.json.gz", "wt") as fh:
    json.dump(addr, fh)
print("data/dfr_addresses.json.gz:", len(addr), "addresses (full detail)")

# --- flights: gzip the raw pull as-is ---
flights = json.load(open("nashville_flights.geojson"))
with gzip.open("data/nashville_flights.geojson.gz", "wt") as fh:
    json.dump(flights, fh)
print("data/nashville_flights.geojson.gz:", len(flights["features"]), "features")

# --- sensitive sites + the candidate pool: carried through as-is ---
shutil.copy("dfr_sensitive.json", "data/dfr_sensitive.json")
shutil.copy("sensitive_sites.json", "data/sensitive_sites.json")
print("data/dfr_sensitive.json + data/sensitive_sites.json copied")
