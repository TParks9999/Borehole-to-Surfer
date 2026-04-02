from __future__ import annotations

import math
from functools import lru_cache

from pyproj import CRS, Transformer


Extent = tuple[float, float, float, float]
Point = tuple[float, float]
WEB_MERCATOR_LIMIT = 20037508.342789244


def validate_utm_zone(zone: int) -> int:
    if zone < 1 or zone > 60:
        raise ValueError("UTM zone must be an integer from 1 to 60.")
    return zone


def validate_hemisphere(hemisphere: str) -> str:
    hemi = str(hemisphere).strip().upper()
    if hemi not in {"N", "S"}:
        raise ValueError("Hemisphere must be 'N' or 'S'.")
    return hemi


def build_wgs84_utm_crs(zone: int, hemisphere: str) -> CRS:
    zone = validate_utm_zone(int(zone))
    hemi = validate_hemisphere(hemisphere)
    epsg = 32600 + zone if hemi == "N" else 32700 + zone
    return CRS.from_epsg(epsg)


@lru_cache(maxsize=16)
def _build_transformer(zone: int, hemisphere: str, target: str) -> Transformer:
    source = build_wgs84_utm_crs(zone, hemisphere)
    return Transformer.from_crs(source, CRS.from_user_input(target), always_xy=True)


def transform_points(points: list[Point], zone: int, hemisphere: str, target: str) -> list[Point]:
    if not points:
        return []
    transformer = _build_transformer(int(zone), validate_hemisphere(hemisphere), target)
    return [(float(x2), float(y2)) for x2, y2 in transformer.itransform(points)]


def transform_extent(extent: Extent, zone: int, hemisphere: str, target: str) -> Extent:
    min_x, max_x, min_y, max_y = extent
    corners = [
        (min_x, min_y),
        (min_x, max_y),
        (max_x, min_y),
        (max_x, max_y),
    ]
    transformed = transform_points(corners, zone=zone, hemisphere=hemisphere, target=target)
    xs = [pt[0] for pt in transformed]
    ys = [pt[1] for pt in transformed]
    return min(xs), max(xs), min(ys), max(ys)


def clamp_web_mercator_extent(extent: Extent) -> Extent:
    min_x, max_x, min_y, max_y = extent
    return (
        max(-WEB_MERCATOR_LIMIT, min_x),
        min(WEB_MERCATOR_LIMIT, max_x),
        max(-WEB_MERCATOR_LIMIT, min_y),
        min(WEB_MERCATOR_LIMIT, max_y),
    )


def mercator_span(extent: Extent) -> tuple[float, float]:
    min_x, max_x, min_y, max_y = clamp_web_mercator_extent(extent)
    return max(0.0, max_x - min_x), max(0.0, max_y - min_y)


def mercator_diagonal(extent: Extent) -> float:
    width, height = mercator_span(extent)
    return math.hypot(width, height)
