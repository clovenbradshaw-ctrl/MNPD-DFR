import json, math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import numpy as np

SWATH_M = 82.0  # project's own "flew over" threshold (index.html SWATH_M)
CT = ZoneInfo("America/Chicago")  # pilot's local timezone (Madison, TN)

def gdist_vec(lat0, lon0, lats, lons):
    R = 6371000.0
    lat0r = math.radians(lat0); lon0r = math.radians(lon0)
    latr = np.radians(lats); lonr = np.radians(lons)
    dL = latr - lat0r
    dG = lonr - lon0r
    a = np.sin(dL/2)**2 + np.cos(lat0r)*np.cos(latr)*np.sin(dG/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

def min_path_dist(lat0, lon0, X, Y, km_bbox):
    # X,Y: arrays of lon,lat of path points
    n = len(X)
    if n == 1:
        return gdist_vec(lat0, lon0, np.array([Y[0]]), np.array([X[0]]))[0]
    ax, ay = X[:-1], Y[:-1]
    bx, by = X[1:], Y[1:]
    dx = bx - ax; dy = by - ay
    dxx = dx*dx + dy*dy
    # projection parameter of (lon0,lat0) projected onto segment in lon/lat plane
    t = ((lon0-ax)*dx + (lat0-ay)*dy) / dxx
    t = np.clip(t, 0, 1)
    px = ax + t*dx; py = ay + t*dy
    return gdist_vec(lat0, lon0, py, px).min()

# load flights from the API, dedup by flight_id (feed double-logs some rows)
fcoll = json.load(open('nashville_flights.geojson'))
seen = {}
for f in fcoll['features']:
    p = f['properties']
    g = f['geometry']
    if g['type'] == 'LineString':
        coords = g['coordinates']
    elif g['type'] == 'MultiLineString':
        coords = [c for part in g['coordinates'] for c in part]
    else:
        coords = []
    if not coords:
        continue
    fid = p['flight_id']
    if fid in seen:
        continue
    seen[fid] = {
        'id': fid,
        'purpose': (p.get('flight_purpose') or '').strip(),
        'external': p.get('external_id') or '',
        'takeoff': p.get('takeoff'),
        'landing': p.get('landing'),
        'X': np.array([c[0] for c in coords], dtype=float),
        'Y': np.array([c[1] for c in coords], dtype=float),
    }
flights = list(seen.values())
print(f"flights (deduped): {len(flights)}")

# flight bboxes in lon/lat, expanded by SWATH_M (approx in lon/lat)
KM_EXP = SWATH_M / 1000.0
def bbox_lonlat(f):
    lonmin, lonmax = f['X'].min(), f['X'].max()
    latmin, latmax = f['Y'].min(), f['Y'].max()
    c = math.cos(math.radians((latmin+latmax)/2))
    dlon = KM_EXP / (111.32 * c)
    dlat = KM_EXP / 110.574
    return (lonmin-dlon, lonmax+dlon, latmin-dlat, latmax+dlat)
for f in flights:
    f['bbox'] = bbox_lonlat(f)

# load sensitive sites
sites = json.load(open('data/sensitive_sites.json'))['sites']
print(f"sites: {len(sites)}")

def t_str(ms):
    if not ms: return ""
    return datetime.fromtimestamp(ms/1000, CT).strftime('%Y-%m-%d %H:%M')

# for each site, test only flights whose bbox contains it
overflights = []  # (site, flight, dist)
site_index = []
for s in sites:
    lat, lng = s['lat'], s['lng']
    for f in flights:
        lo, hi, la, ha = f['bbox']
        if not (lo <= lng <= hi and la <= lat <= ha):
            continue
        d = min_path_dist(lat, lng, f['X'], f['Y'], SWATH_M)
        if d <= SWATH_M:
            overflights.append((s, f, d))

print(f"site-flight overflights (<= {SWATH_M}m): {len(overflights)}")
print(f"distinct flights over any site: {len(set(r[1]['id'] for r in overflights))}")
print(f"distinct sites overflown: {len(set((r[0]['name'],r[0]['lat'],r[0]['lng']) for r in overflights))}")

json.dump([{'site': s['name'], 'type': s['type'], 'lat': s['lat'], 'lng': s['lng'],
            'flight_id': f['id'], 'purpose': f['purpose'], 'external': f['external'],
            'takeoff_ct': t_str(f['takeoff']), 'landing_ct': t_str(f['landing']),
            'min_dist_m': round(d,2)}
           for s,f,d in overflights], open('overflights_raw.json','w'), indent=1)

# summarize per site
from collections import defaultdict
by_site = defaultdict(list)
for s,f,d in overflights:
    by_site[(s['name'], s['type'], s['lat'], s['lng'])].append((f,d))

summary = []
for (name,typ,lat,lng), fs in sorted(by_site.items(), key=lambda k:(k[0][1], k[0][0])):
    fs_sorted = sorted(fs, key=lambda x: x[0]['takeoff'])
    summary.append({
        'name': name, 'type': typ, 'lat': lat, 'lng': lng,
        'n_flights': len(fs),
        'n_flights_unique': len({f['id'] for f,_ in fs}),
        'first_overflight_ct': t_str(fs_sorted[0][0]['takeoff']),
        'last_overflight_ct': t_str(fs_sorted[-1][0]['landing']),
        'min_dist_m': min(d for _,d in fs_sorted),
        'flights': [{
            'flight_id': f['id'], 'purpose': f['purpose'],
            'external': f['external'],
            'takeoff_ct': t_str(f['takeoff']), 'landing_ct': t_str(f['landing']),
            'min_dist_m': round(d,2)
        } for f,d in fs_sorted],
    })
json.dump(summary, open('overflights_by_site.json','w'), indent=1)
print("wrote overflights_by_site.json")
