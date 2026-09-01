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
    """Min distance across every disconnected part of a flight's path — each
    part's own polyline only. A flight's geometry can be a MultiLineString
    with dozens of disjoint fragments (GPS gaps); concatenating them into one
    array (the previous approach) creates a phantom segment bridging the last
    point of one fragment to the first point of the next, which doesn't
    correspond to anywhere the drone actually flew."""
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

fc = json.load(open('nashville_addresses.json'))
print(f"addresses: {len(fc['features'])}")

def t_str(ms):
    if not ms: return ""
    return datetime.fromtimestamp(ms/1000, CT).strftime('%Y-%m-%d %H:%M')

hits = []  # dict per address with flights list
for f in fc['features']:
    lon, lat = f['geometry']['coordinates']
    p = f['properties']
    addr = {
        'apn': p.get('apn'), 'full_address': p.get('FullAddress'),
        'number': p.get('Number'), 'street': p.get('StreetName'),
        'street_type': p.get('StreetTypeCode'), 'city': p.get('City'),
        'zip': p.get('Zip'), 'lat': lat, 'lng': lon,
    }
    fflights = []
    for fl in flights:
        lo, hi, la, ha = fl['bbox']
        if not (lo <= lon <= hi and la <= lat <= ha):
            continue
        d = min_path_dist(lat, lon, fl['parts'])
        if d <= SWATH_M:
            fflights.append({
                'flight_id': fl['id'], 'purpose': fl['purpose'],
                'external': fl['external'],
                'takeoff_ct': t_str(fl['takeoff']), 'landing_ct': t_str(fl['landing']),
                'min_dist_m': round(d, 2),
            })
    if fflights:
        fflights.sort(key=lambda x: x['takeoff_ct'])
        addr['n_flights'] = len(fflights)
        addr['n_flights_unique'] = len({x['flight_id'] for x in fflights})
        addr['closest_pass_m'] = min(x['min_dist_m'] for x in fflights)
        addr['flights'] = fflights
        hits.append(addr)

hits.sort(key=lambda a: (-a['n_flights'], a['closest_pass_m']))
print(f"addresses overflown (<= {SWATH_M}m): {len(hits)}")
json.dump(hits, open('overflown_addresses.json', 'w'), indent=1)

import csv
with open('overflown_addresses.csv', 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['apn','full_address','city','zip','lat','lng',
                'n_flights','closest_pass_m','flight_id','purpose','external_id',
                'takeoff_ct','landing_ct','min_dist_m'])
    for a in hits:
        for x in a['flights']:
            w.writerow([a['apn'], a['full_address'], a['city'], a['zip'],
                        a['lat'], a['lng'], a['n_flights'], a['closest_pass_m'],
                        x['flight_id'], x['purpose'], x['external'],
                        x['takeoff_ct'], x['landing_ct'], x['min_dist_m']])
print("wrote overflown_addresses.json / .csv")