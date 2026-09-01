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

- **Sensitive locations** (24 sites overflown) — 18 places of worship, 5
  schools, 1 playground.
- **Every address** (10,240 of the 16,029 Metro address points in the trial
  area were within 82 m of at least one flight). Addresses lazy-load: a light
  ~3 MB list renders instantly, then full per-flight detail is fetched from a
  gzipped binary in the background. Tap any row for date-and-time details.

## Data

| Path | What it is |
|---|---|
| `data/dfr_sensitive.json` | 24 sensitive locations overflown, with per-flight detail |
| `data/dfr_addresses_light.json` | 10,240 overflown addresses (summary; loads first) |
| `data/dfr_addresses.json.gz` | **Binary (gzip)** full address dataset — 10,240 records × per-flight detail (**28 MB JSON, 2.3 MB gz**) |
| `data/nashville_flights.geojson.gz` | Binary (gzip) 409-row deduped flight-path geometry (395 unique flights) |
| `data/sensitive_sites.json` | All 1,743 Metro/OSM sensitive sites in the area |
| `satellite/*.png` | 500×500 m satellite crops (Esri World Imagery), annotated with flight IDs; `manifest.json` ties images → flights. Predates the correction below — covers the original 17, not the 8 sites found since (one of which, on closer check, didn't hold up either — see below). The live app no longer uses these; it fetches a satellite crop live per-record instead. |

The address data is stored **gzipped binary** to keep the repo lean; the
explorer decompresses it in-browser with `DecompressionStream('gzip')`.

## Methods

- **"Flew over"** = the site is within **82 m** of any flight-path segment
  (`SWATH_M` from `clovenbradshaw-ctrl/DFR`'s `index.html`).
- Flights deduplicated by `flight_id` (the upstream feed double-logs some rows).
- Addresses: Metro Nashville GIS **Addressing/AddressPoints** layer, filtered
  to the trial bounding box, intersected with the deduped flight paths.
- Sensitive sites: the same intersection against `data/sensitive_sites.json`'s
  1,743 candidate schools/childcare/playgrounds/houses of worship.

**Correction (Sep 2026):** earlier published counts said 17 sensitive sites
were overflown. The intersection had never been fully scripted (see
Reproduce below) — writing `scripts/intersect_sites.py` to do it for the
first time found 25: the same 17 plus 8 real sites the original pass
missed, including two schools (Amqui Elementary, Madison High) at 7.7 m and
11.5 m. All eight are 280 m+ from the nearest already-published site, so
this is missed sites, not duplicates.

Checking that result surfaced a second bug, in the new script itself:
`min_path_dist` measured distance against each flight's path flattened into
one coordinate array, but 370 of 409 flights have multiple *disconnected*
path segments (GPS gaps mid-flight) — flattening them creates a phantom
segment bridging the end of one real segment to the start of the next,
which the drone never actually flew. Fixed in both `intersect_sites.py` and
`intersect_addresses.py` (same bug, same origin — copied verbatim between
the two) to measure each real segment independently. That dropped one of
the 25 (Jehovah's Witnesses Kingdom Hall, Slayton Dr — its reported 58 m
pass was entirely a phantom segment) and corrected several other sites'
distances, a few considerably: three sites previously shown within a few
meters were actually 40–66 m out. **24** is the verified count.

The same bug had been in `intersect_addresses.py` from the start (this
repo's original script, copied into `intersect_sites.py` rather than the
other way around), so it affected the main address dataset too. Re-run
fixed: **10,240** addresses overflown, down from 10,536 — 296 false
positives removed, 0 added, consistent with the fix only ever being able to
remove a fabricated close pass, never hide a real one. Independently
verified by brute-force checking a dropped address's true nearest flight
point across all 395 flights (121 m — well outside 82 m — against a
previously-reported 0.28 m, entirely a phantom segment).

## Reproduce

```bash
# 1. pull this trial's flights straight from MNPD's one Skydio FeatureServer
python3 scripts/fetch_nashville_flights.py   # writes nashville_flights.geojson
# 2. pull Metro address points in the flight area
python3 scripts/get_addresses.py   # writes nashville_addresses.json
# 3. intersect addresses against 82 m swaths
python3 scripts/intersect_addresses.py   # writes overflown_addresses.json
# 4. intersect sensitive sites against 82 m swaths
python3 scripts/intersect_sites.py   # writes overflights_by_site.json
# 5. combine both intersections into the explorer's raw shape
python3 scripts/build_explorer_data.py   # writes dfr_sensitive.json, dfr_addresses.json
# 6. split/gzip into what data/ actually ships
python3 scripts/package_data.py      # writes data/dfr_*.json(.gz), copies sensitive_sites.json
```

Steps 3 and 4 need `numpy`; steps 1, 2, 5, and 6 are stdlib-only. `python3 -m
venv .venv && .venv/bin/pip install numpy requests` covers it.

`scripts/fetch_nashville_flights.py` talks to one specific, already-known
FeatureServer (the same one credited below) — it's the hardcoded, single-agency
counterpart to `scripts/dfr.py`, which discovers and polls *every* agency on
Skydio's public ArcGIS org (900+ as of this writing) on a timer for the
broader DFR-transparency effort. That's the right tool if you're standing up
coverage for a new city; it's overkill for reproducing this one trial's data,
which is why step 1 above skips straight to the one service this repo needs.

`scripts/intersect_sites.py` is `intersect_addresses.py`'s counterpart for
`data/sensitive_sites.json` instead of address points — same distance math,
same threshold. Nothing in this repo fetches that candidate pool itself yet
(no committed source for the underlying Metro GIS + OSM layers it was built
from); the shipped file is reused as-is since schools and churches don't
move. That's the one real gap still open in this pipeline.

`scripts/analyze_api.py` is a separate, later-stage script — it reads an
already-built `nashville_flights.geojson` (not the live API, despite the
name) to cross-check sensitive-site overflights outside the main explorer
pipeline. It isn't part of the reproduce steps above.

Adjust the threshold by changing `SWATH_M` at the top of `intersect_addresses.py`
**and** `intersect_sites.py` — the two aren't linked, so a threshold change
needs both edited to stay consistent.

## Credits

- Flights: MNPD DFR / Skydio ArcGIS FeatureServer
  `mnhQTdIYDA7UoY2l/678dee26-6aa8-4d60-bf1c-30c7b0f6b517-production`
- Addresses: Metro Nashville GIS (Addressing/AddressPoints)
- Sensitive sites + SWATH_M definition: `clovenbradshaw-ctrl/DFR`, `.../plain-text`
- Imagery: Esri World Imagery (attribution required)