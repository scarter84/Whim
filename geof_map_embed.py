"""
GeoF Map Embed — Offline tile-based map renderer for Whim Terminal.
Downloads and caches OSM tiles, renders them on a tkinter Canvas.
Replaces the old X11 window-swallowing approach for OrganicMaps.
"""

import math
import os
import threading
import urllib.request

from PIL import Image, ImageTk

TILE_SIZE = 256
_DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
_DEFAULT_CACHE_DIR = os.path.expanduser("~/.openclaw/map_tiles")
_USER_AGENT = "WhimTerminal/3.4 (local-first geofence monitor)"


def _lat_lon_to_tile(lat, lon, zoom):
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad))
             / math.pi) / 2.0 * n)
    return x, y


class TileMapRenderer:
    """Renders OSM tiles on a tkinter Canvas with geofence/collar overlay."""

    def __init__(self, tile_url=None, cache_dir=None):
        self._tile_url = tile_url or _DEFAULT_TILE_URL
        self._cache_dir = cache_dir or _DEFAULT_CACHE_DIR
        os.makedirs(self._cache_dir, exist_ok=True)
        self._tk_images = {}
        self._active = False
        self._fetching = False
        self._redraw_cb = None

    @property
    def is_active(self):
        return self._active

    def activate(self):
        self._active = True

    def deactivate(self):
        self._active = False
        self._tk_images.clear()

    def set_redraw_callback(self, cb):
        self._redraw_cb = cb

    def draw_tiles(self, canvas, lats, lons, cw, ch,
                   center_lat=None, center_lon=None, zoom=None):
        """Draw tile images on canvas background.

        When *center_lat*, *center_lon* and *zoom* are all provided the
        renderer uses them directly (manual pan/zoom).  Otherwise it
        auto-fits to the data bounding box.

        Returns a ``to_px(lat, lon)`` callable that maps geographic
        coordinates to canvas pixel positions, or *None* when there is
        no data to display.
        """
        if not lats or not lons:
            return None

        if center_lat is not None and center_lon is not None and zoom is not None:
            pass
        else:
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            center_lat = (min_lat + max_lat) / 2.0
            center_lon = (min_lon + max_lon) / 2.0
            zoom = self._fit_zoom(min_lat, max_lat, min_lon, max_lon, cw, ch)

        zoom = max(1, min(18, zoom))
        n = 2 ** zoom

        cx_frac = (center_lon + 180.0) / 360.0 * n
        clat_rad = math.radians(center_lat)
        cy_frac = ((1.0 - math.log(math.tan(clat_rad) + 1.0 / math.cos(clat_rad))
                     / math.pi) / 2.0 * n)

        ox = cw / 2.0 - cx_frac * TILE_SIZE
        oy = ch / 2.0 - cy_frac * TILE_SIZE

        tx_start = max(0, int(-ox / TILE_SIZE))
        tx_end = min(n - 1, int((cw - ox) / TILE_SIZE))
        ty_start = max(0, int(-oy / TILE_SIZE))
        ty_end = min(n - 1, int((ch - oy) / TILE_SIZE))

        self._tk_images.clear()
        missing = []

        for tx in range(tx_start, tx_end + 1):
            for ty in range(ty_start, ty_end + 1):
                cp = self._cache_path(zoom, tx, ty)
                if os.path.isfile(cp):
                    try:
                        pil = Image.open(cp).convert("RGB")
                        tk_img = ImageTk.PhotoImage(pil)
                        key = f"{zoom}_{tx}_{ty}"
                        self._tk_images[key] = tk_img
                        px = int(tx * TILE_SIZE + ox)
                        py = int(ty * TILE_SIZE + oy)
                        canvas.create_image(px, py, anchor="nw", image=tk_img)
                    except Exception:
                        missing.append((tx, ty))
                else:
                    missing.append((tx, ty))

        if missing and not self._fetching:
            self._fetch_bg(zoom, missing, canvas)

        def to_px(lat, lon):
            x_frac = (lon + 180.0) / 360.0 * n
            lr = math.radians(lat)
            y_frac = ((1.0 - math.log(math.tan(lr) + 1.0 / math.cos(lr))
                        / math.pi) / 2.0 * n)
            return x_frac * TILE_SIZE + ox, y_frac * TILE_SIZE + oy

        return to_px

    def fit_zoom(self, lats, lons, cw, ch):
        """Return the auto-fit zoom level for the given data bounds."""
        if not lats or not lons:
            return 10
        return self._fit_zoom(min(lats), max(lats), min(lons), max(lons), cw, ch)

    # ------------------------------------------------------------------
    def _fit_zoom(self, min_lat, max_lat, min_lon, max_lon, cw, ch):
        for z in range(17, 0, -1):
            n = 2 ** z
            x1 = (min_lon + 180.0) / 360.0 * n * TILE_SIZE
            x2 = (max_lon + 180.0) / 360.0 * n * TILE_SIZE
            lr1 = math.radians(max_lat)
            y1 = ((1.0 - math.log(math.tan(lr1) + 1.0 / math.cos(lr1))
                    / math.pi) / 2.0 * n * TILE_SIZE)
            lr2 = math.radians(min_lat)
            y2 = ((1.0 - math.log(math.tan(lr2) + 1.0 / math.cos(lr2))
                    / math.pi) / 2.0 * n * TILE_SIZE)
            if abs(x2 - x1) < cw * 0.7 and abs(y2 - y1) < ch * 0.7:
                return z
        return 1

    def _cache_path(self, z, x, y):
        return os.path.join(self._cache_dir, str(z), str(x), f"{y}.png")

    def _fetch_bg(self, zoom, tiles, canvas):
        self._fetching = True

        def _worker():
            for tx, ty in tiles:
                if not self._active:
                    break
                url = self._tile_url.format(z=zoom, x=tx, y=ty)
                cp = self._cache_path(zoom, tx, ty)
                try:
                    req = urllib.request.Request(
                        url, headers={"User-Agent": _USER_AGENT})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = resp.read()
                    os.makedirs(os.path.dirname(cp), exist_ok=True)
                    with open(cp, "wb") as f:
                        f.write(data)
                except Exception:
                    pass
            self._fetching = False
            if self._active and self._redraw_cb:
                try:
                    canvas.after(0, self._redraw_cb)
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()
