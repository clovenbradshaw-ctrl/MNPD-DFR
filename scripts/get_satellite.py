import json, math, os, time, io, sys
import requests
from PIL import Image, ImageDraw

TILE = 256
ZOOM = 19              # ~0.6 m/px ESRI World Imagery at zoom 19
EXTENT_PX = 500        # output image is EXTENT_PX x EXTENT_PX pixels centered on site
OUT = "satellite"
TILESRV = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

def lonlat_to_pixel(lon, lat, z):
    """Return (x, y) in global pixel coordinates at zoom z."""
    lat = max(min(lat, 85.0511), -85.0511)
    n = 2.0 ** z
    x = (lon + 180.0) / 360.0 * n
    latr = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(latr)) / math.pi) / 2.0 * n
    return x * TILE, y * TILE

def fetch_tile(x, y, z):
    url = f"{TILESRV}/{z}/{y}/{x}"
    for _ in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=20)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception as e:
            print(f"    retry {x},{y}: {e}")
            time.sleep(1)
    return None

def make_map(lon, lat, name, i, total):
    gx, gy = lonlat_to_pixel(lon, lat, ZOOM)
    half = EXTENT_PX // 2
    # top-left pixel of the crop region
    x0 = int(gx) - half
    y0 = int(gy) - half
    # tile range covering [x0, x0+EXTENT_PX) x [y0, y0+EXTENT_PX)
    tx0, ty0 = x0 // TILE, y0 // TILE
    tx1, ty1 = (x0 + EXTENT_PX - 1) // TILE, (y0 + EXTENT_PX - 1) // TILE
    cols, rows = tx1 - tx0 + 1, ty1 - ty0 + 1

    canvas = Image.new("RGB", (cols * TILE, rows * TILE), (128, 128, 128))
    for r in range(rows):
        for c in range(cols):
            tx, ty = tx0 + c, ty0 + r
            img = fetch_tile(tx, ty, ZOOM)
            if img:
                canvas.paste(img, (c * TILE, r * TILE))
    # crop the sub-region
    off_x = x0 - tx0 * TILE
    off_y = y0 - ty0 * TILE
    canvas = canvas.crop((off_x, off_y, off_x + EXTENT_PX, off_y + EXTENT_PX))

    # red marker at exact center
    draw = ImageDraw.Draw(canvas)
    cp = EXTENT_PX // 2
    rr = 9
    draw.ellipse((cp - rr, cp - rr, cp + rr, cp + rr), fill=(255, 0, 0), outline=(255, 255, 255), width=3)

    safe = ''.join(ch if ch.isalnum() or ch in ' -_()' else '_' for ch in name).strip().replace(' ', '_')
    fn = f"{OUT}/{i:02d}_{safe}_{lon:.5f}_{lat:.5f}.png"
    canvas.save(fn)
    return fn

os.makedirs(OUT, exist_ok=True)
sites = json.load(open("overflights_by_site.json"))
if "--limit" in sys.argv:
    sites = sites[:int(sys.argv[sys.argv.index("--limit") + 1])]
print(f"downloading {len(sites)} sites -> {OUT}/")
for i, s in enumerate(sites, 1):
    fn = make_map(s["lng"], s["lat"], s["name"], i, len(sites))
    print(f"[{i}/{len(sites)}] {s['name']!r} ({s['type']}) -> {fn}")
print("done")
