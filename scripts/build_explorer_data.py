import json
from datetime import datetime
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")

def t_str(ms):
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, CT).strftime("%Y-%m-%d %H:%M")

# --- sensitive locations overflown ---
sites = json.load(open("overflights_by_site.json"))
sensitive = []
for s in sites:
    fl = sorted(s["flights"], key=lambda x: x["takeoff_ct"])
    alltimes = sorted(
        (x["landing_ct"], x["takeoff_ct"]) for x in fl
    )  # (landing, takeoff)
    sensitive.append({
        "name": s["name"],
        "type": s["type"],
        "lat": s["lat"],
        "lng": s["lng"],
        "n_flights": len(fl),
        "n_flights_unique": len({x["flight_id"] for x in fl}),
        "closest_pass_m": min(x["min_dist_m"] for x in fl),
        "first_overflight_ct": fl[0]["takeoff_ct"],
        "last_overflight_ct": fl[-1]["landing_ct"],
        "flights": fl,
    })
with open("dfr_sensitive.json", "w") as fh:
    json.dump(sensitive, fh, indent=1)
print("dfr_sensitive.json:", len(sensitive), "sites")

# --- addresses overflown ---
addr = json.load(open("overflown_addresses.json"))
n = 0
for a in addr:
    fl = a["flights"]
    a["first_overflight_ct"] = fl[0]["takeoff_ct"]
    a["last_overflight_ct"] = fl[-1]["landing_ct"]
    n += len(fl)
with open("dfr_addresses.json", "w") as fh:
    json.dump(addr, fh)
print("dfr_addresses.json:", len(addr), "addresses,", n, "passes")