from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from PIL import Image

from .geo import Extent, WEB_MERCATOR_LIMIT, clamp_web_mercator_extent


TILE_SIZE = 256
MAX_TILE_COUNT = 24
MIN_ZOOM = 1
MAX_ZOOM = 19
ESRI_WORLD_IMAGERY_URL = (
    "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
ESRI_WORLD_IMAGERY_ATTRIBUTION = (
    "Sources: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
)
USER_AGENT = "BoreholeToSurfer/1.0"


@dataclass(frozen=True)
class TileRange:
    zoom: int
    x_min: int
    x_max: int
    y_min: int
    y_max: int

    @property
    def width(self) -> int:
        return self.x_max - self.x_min + 1

    @property
    def height(self) -> int:
        return self.y_max - self.y_min + 1

    @property
    def tile_count(self) -> int:
        return self.width * self.height


@dataclass(frozen=True)
class BasemapImage:
    image: Image.Image
    attribution: str
    zoom: int


def _default_opener(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        return response.read()


def _mercator_to_world_pixel(x: float, y: float, zoom: int) -> tuple[float, float]:
    world_px = TILE_SIZE * (2**zoom)
    scale = world_px / (2.0 * WEB_MERCATOR_LIMIT)
    px = (x + WEB_MERCATOR_LIMIT) * scale
    py = (WEB_MERCATOR_LIMIT - y) * scale
    return px, py


def tile_range_for_extent(extent: Extent, zoom: int) -> TileRange:
    min_x, max_x, min_y, max_y = clamp_web_mercator_extent(extent)
    left_px, top_px = _mercator_to_world_pixel(min_x, max_y, zoom)
    right_px, bottom_px = _mercator_to_world_pixel(max_x, min_y, zoom)
    world_px = TILE_SIZE * (2**zoom)
    right_px = min(world_px - 1e-6, max(0.0, right_px - 1e-6))
    bottom_px = min(world_px - 1e-6, max(0.0, bottom_px - 1e-6))
    x_min = max(0, min((2**zoom) - 1, int(math.floor(left_px / TILE_SIZE))))
    x_max = max(0, min((2**zoom) - 1, int(math.floor(right_px / TILE_SIZE))))
    y_min = max(0, min((2**zoom) - 1, int(math.floor(top_px / TILE_SIZE))))
    y_max = max(0, min((2**zoom) - 1, int(math.floor(bottom_px / TILE_SIZE))))
    return TileRange(zoom=zoom, x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)


def choose_zoom_for_extent(
    extent: Extent,
    max_tile_count: int = MAX_TILE_COUNT,
    min_zoom: int = MIN_ZOOM,
    max_zoom: int = MAX_ZOOM,
) -> int:
    for zoom in range(max_zoom, min_zoom - 1, -1):
        if tile_range_for_extent(extent, zoom).tile_count <= max_tile_count:
            return zoom
    return min_zoom


def _cache_path(cache_dir: Path, zoom: int, x: int, y: int) -> Path:
    return cache_dir / str(zoom) / str(x) / f"{y}.jpg"


def _load_cached_tile(path: Path) -> Image.Image | None:
    if not path.exists():
        return None
    try:
        with Image.open(path) as image:
            loaded = image.convert("RGB")
            loaded.load()
            return loaded
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        return None


def _load_tile(
    cache_dir: Path,
    zoom: int,
    x: int,
    y: int,
    opener: Callable[[str], bytes],
) -> Image.Image:
    path = _cache_path(cache_dir, zoom, x, y)
    if cached := _load_cached_tile(path):
        return cached

    tile_url = ESRI_WORLD_IMAGERY_URL.format(z=zoom, x=x, y=y)
    data = opener(tile_url)
    with Image.open(BytesIO(data)) as opened:
        image = opened.convert("RGB")
        image.load()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return image


def load_world_imagery(
    extent: Extent,
    pixel_w: int,
    pixel_h: int,
    cache_dir: Path,
    opener: Callable[[str], bytes] | None = None,
) -> BasemapImage:
    extent = clamp_web_mercator_extent(extent)
    zoom = choose_zoom_for_extent(extent)
    tile_range = tile_range_for_extent(extent, zoom)
    opener = opener or _default_opener

    mosaic = Image.new(
        "RGB",
        (tile_range.width * TILE_SIZE, tile_range.height * TILE_SIZE),
    )
    for x in range(tile_range.x_min, tile_range.x_max + 1):
        for y in range(tile_range.y_min, tile_range.y_max + 1):
            tile = _load_tile(cache_dir=cache_dir, zoom=zoom, x=x, y=y, opener=opener)
            mosaic.paste(tile, ((x - tile_range.x_min) * TILE_SIZE, (y - tile_range.y_min) * TILE_SIZE))

    left_px, top_px = _mercator_to_world_pixel(extent[0], extent[3], zoom)
    right_px, bottom_px = _mercator_to_world_pixel(extent[1], extent[2], zoom)
    origin_x = tile_range.x_min * TILE_SIZE
    origin_y = tile_range.y_min * TILE_SIZE
    crop_left = max(0, int(math.floor(left_px - origin_x)))
    crop_top = max(0, int(math.floor(top_px - origin_y)))
    crop_right = min(mosaic.width, int(math.ceil(right_px - origin_x)))
    crop_bottom = min(mosaic.height, int(math.ceil(bottom_px - origin_y)))
    crop_right = max(crop_left + 1, crop_right)
    crop_bottom = max(crop_top + 1, crop_bottom)

    cropped = mosaic.crop((crop_left, crop_top, crop_right, crop_bottom))
    resized = cropped.resize((max(1, pixel_w), max(1, pixel_h)), Image.Resampling.LANCZOS)
    return BasemapImage(
        image=resized,
        attribution=ESRI_WORLD_IMAGERY_ATTRIBUTION,
        zoom=zoom,
    )
