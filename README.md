# MNPD-DFR — Nashville DFR Overflight Explorer

Citizen-verification dataset of drone flights from Metro Nashville Police
Department's **Drone-as-First-Responder (DFR)** pilot in Madison, Tennessee
(launched May 26, 2026). This repository maps **every flight path** against
**every Metro address** and **sensitive locations** (schools, childcare,
playgrounds, places of worship), using the same 82 m threshold the project's
published map uses (`SWATH_M=82`).

> Not an official government source. All data originates from MNPD's publicly
> disclosed DFR feed (served by Skydio ArcGIS) and Metro Nashville GIS. Times
> are Central (America/Chicago).

## Live explorer

`index.html` — single-file Leaflet app. Run a local server in this folder:

```bash
python3 -m http.server
# open http://localhost:8000/
```

Two tabs:

- **Sensitive locations** (17 sites overflown) — schools, worship, playgrounds.
- **Every address** (10,536 of the 16,029 Metro address points in the trial
  area were within 82 m of at least one flight). Addresses lazy-load: a light
  ~3 MB list renders instantly, then full per-flight detail is fetched from a
  gzipped binary in the background. Tap any row for date-and-time details.

## Data

| Path | What it is |
|---|---|
| `data/dfr_sensitive.json` | 17 sensitive locations overflown, with per-flight detail |
| `data/dfr_addresses_light.json` | 10,536 overflown addresses (summary; loads first) |
| `data/dfr_addresses.json.gz` | **Binary (gzip)** full address dataset — 10,536 records × per-flight detail (**29 MB JSON, 2.5 MB gz**) |
| `data/nashville_flights.geojson.gz` | Binary (gzip) 409-row deduped flight-path geometry (395 unique flights) |
| `data/sensitive_sites.json` | All 1,743 Metro/OSM sensitive sites in the area |
| `satellite/*.png` | 500×500 m satellite crops (Esri World Imagery) of each overflown sensitive site, annotated with flight IDs; `manifest.json` ties images → flights |

The address data is stored **gzipped binary** to keep the repo lean; the
explorer decompresses it in-browser with `DecompressionStream('gzip')`.

## Methods

- **"Flew over"** = the site is within **82 m** of any flight-path segment
  (`SWATH_M` from `clovenbradshaw-ctrl/DFR`'s `index.html`).
- Flights deduplicated by `flight_id` (the upstream feed double-logs some rows).
- Addresses: Metro Nashville GIS **Addressing/AddressPoints** layer, filtered
  to the trial bounding box, intersected with the deduped flight paths.

## Reproduce

```bash
# 1. pull all Nashville/Madison flights from the live Skydio ArcGIS feed
python3 scripts/analyze_api.py     # fetches nashville_flights.geojson from the live API
# 2. pull Metro address points in the flight area
python3 scripts/get_addresses.py   # writes nashville_addresses.json
# 3. intersect addresses (or sensitive sites) against 82 m swaths
python3 scripts/intersect_addresses.py   # writes overflown_addresses.json
# 4. rebuild explorer data + gzip binary
python3 scripts/build_explorer_data.py   # writes dfr_*.json (+ .gz)
```

Adjust the threshold by changing `SWATH_M` at the top of `intersect_addresses.py`.

## Credits

- Flights: MNPD DFR / Skydio ArcGIS FeatureServer
  `mnhQTdIYDA7UoY2l/678dee26-6aa8-4d60-bf1c-30c7b0f6b517-production`
- Addresses: Metro Nashville GIS (Addressing/AddressPoints)
- Sensitive sites + SWATH_M definition: `clovenbradshaw-ctrl/DFR`, `.../plain-text`
- Imagery: Esri World Imagery (attribution required)