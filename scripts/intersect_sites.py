"""
intersect_sites.py — the sensitive-site counterpart to intersect_addresses.py.

That script exists for the 16,029 Metro address points; this one didn't exist
at all before this run — build_explorer_data.py has always expected an
overflights_by_site.json that nothing in this repo produced. Same distance
math, same SWATH_M, applied to sensitive_sites.json's 1,743 candidate schools/
childcare/playgrounds/houses of worship instead of address points.

sensitive_sites.json itself (the candidate pool) still isn't fetched by any
script here — no committed source for the underlying Metro GIS + OSM layers
it was built from. Left as a known follow-up; the file is stable (schools and
churches don't move), so re-deriving it wasn't necessary to close this gap.
"""
import json, math
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np

SWATH_M = 82.0
CT = ZoneInfo("America/Chicago")

def gdist_vec(lat0, lon0, lats, lons):
    R = 6371000.0
    lat0r = math.radians(lat0); lon0r = math.radians(lon0)
    latr = np.radians(lats); lonr = np.radians(lons)
    dL = latr - lat0r
    dG = lonr - lon0r
    a = np.sin(dL/2)**2 + np.cos(lat0r)*np.cos(latr)*np.sin(dG/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

def _min_seg_dist(lat0, lon0, X, Y):
    """Distance to one connected polyline — never call across a part boundary."""
    n = len(X)
    if n == 1:
        return gdist_vec(lat0, lon0, np.array([Y[0]]), np.array([X[0]]))[0]
    ax, ay = X[:-1], Y[:-1]
    bx, by = X[1:], Y[1:]
    dx = bx - ax; dy = by - ay
    dxx = dx*dx + dy*dy
    with np.errstate(divide='ignore', invalid='ignore'):
        t = np.where(dxx > 0, ((lon0-ax)*dx + (lat0-ay)*dy) / np.where(dxx > 0, dxx, 1), 0.0)
    t = np.clip(t, 0, 1)
    px = ax + t*dx; py = ay + t*dy
    return gdist_vec(lat0, lon0, py, px).min()

def min_path_dist(lat0, lon0, parts):
    """Min distance across every disconnected part of a flight's path —
    each part's own polyline only, never a phantom segment stitching one
    part's last point to the next part's first (see module docstring)."""
    return min(_min_seg_dist(lat0, lon0, X, Y) for X, Y in parts)

fcoll = json.load(open('nashville_flights.geojson'))
seen = {}
for f in fcoll['features']:
    p = f['properties']
    g = f['geometry']
    if g['type'] == 'LineString':
        part_coords = [g['coordinates']]
    elif g['type'] == 'MultiLineString':
        part_coords = g['coordinates']
    else:
        continue
    fid = p['flight_id']
    if fid in seen:
        continue
    parts = [(np.array([c[0] for c in part], dtype=float),
              np.array([c[1] for c in part], dtype=float))
             for part in part_coords if part]
    if not parts:
        continue
    allX = np.concatenate([X for X, Y in parts])
    allY = np.concatenate([Y for X, Y in parts])
    seen[fid] = {
        'id': fid,
        'purpose': (p.get('flight_purpose') or '').strip(),
        'external': p.get('external_id') or '',
        'takeoff': p.get('takeoff'),
        'landing': p.get('landing'),
        'parts': parts,      # kept separate — the actual distance calc
        'X': allX,           # union only, for the coarse bbox pre-filter
        'Y': allY,
    }
flights = list(seen.values())
print(f"flights: {len(flights)}")

KM_EXP = SWATH_M / 1000.0
def bbox(f):
    lonmin, lonmax = f['X'].min(), f['X'].max()
    latmin, latmax = f['Y'].min(), f['Y'].max()
    c = math.cos(math.radians((latmin+latmax)/2))
    return (lonmin-KM_EXP/(111.32*c), lonmax+KM_EXP/(111.32*c),
            latmin-KM_EXP/110.574, latmax+KM_EXP/110.574)
for f in flights:
    f['bbox'] = bbox(f)

pool = json.load(open('sensitive_sites.json'))
sites = pool['sites']
print(f"candidate sites: {len(sites)}")

def t_str(ms):
    if not ms: return ""
    return datetime.fromtimestamp(ms/1000, CT).strftime('%Y-%m-%d %H:%M')

hits = []
for s in sites:
    lat, lon = s['lat'], s['lng']
    sflights = []
    for fl in flights:
        lo, hi, la, ha = fl['bbox']
        if not (lo <= lon <= hi and la <= lat <= ha):
            continue
        d = min_path_dist(lat, lon, fl['parts'])
        if d <= SWATH_M:
            sflights.append({
                'flight_id': fl['id'], 'purpose': fl['purpose'],
                'external': fl['external'],
                'takeoff_ct': t_str(fl['takeoff']), 'landing_ct': t_str(fl['landing']),
                'min_dist_m': round(d, 2),
            })
    if sflights:
        sflights.sort(key=lambda x: x['takeoff_ct'])
        hits.append({
            'name': s['name'], 'type': s['type'], 'lat': lat, 'lng': lon,
            'flights': sflights,
        })

hits.sort(key=lambda s: min(x['min_dist_m'] for x in s['flights']))
print(f"sites overflown (<= {SWATH_M}m): {len(hits)}")
json.dump(hits, open('overflights_by_site.json', 'w'), indent=1)
print("wrote overflights_by_site.json")
