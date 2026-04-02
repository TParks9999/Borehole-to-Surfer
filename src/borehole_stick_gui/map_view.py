from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Tuple


Extent = Tuple[float, float, float, float]  # min_x, max_x, min_y, max_y
Point = Tuple[float, float]


@dataclass(frozen=True)
class MapTransform:
    min_x: float
    max_y: float
    scale: float
    offset_x: float
    offset_y: float
    draw_w: float
    draw_h: float


def compute_extent(points: Iterable[Point]) -> Extent:
    pts = list(points)
    if not pts:
        raise ValueError("Cannot compute extent for empty points.")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def _inflate_degenerate_extent(extent: Extent, min_abs: float = 1.0) -> Extent:
    min_x, max_x, min_y, max_y = extent
    if max_x - min_x <= 0:
        cx = (min_x + max_x) / 2.0
        min_x, max_x = cx - min_abs / 2.0, cx + min_abs / 2.0
    if max_y - min_y <= 0:
        cy = (min_y + max_y) / 2.0
        min_y, max_y = cy - min_abs / 2.0, cy + min_abs / 2.0
    return min_x, max_x, min_y, max_y


def expand_extent(extent: Extent, buffer_ratio: float = 0.05, min_abs: float = 1.0) -> Extent:
    min_x, max_x, min_y, max_y = _inflate_degenerate_extent(extent, min_abs=min_abs)
    width = max_x - min_x
    height = max_y - min_y
    pad_x = max(width * float(buffer_ratio), float(min_abs))
    pad_y = max(height * float(buffer_ratio), float(min_abs))
    return min_x - pad_x, max_x + pad_x, min_y - pad_y, max_y + pad_y


def fit_transform(extent: Extent, canvas_w: int, canvas_h: int, padding_px: int = 20) -> MapTransform:
    min_x, max_x, min_y, max_y = _inflate_degenerate_extent(extent, min_abs=1.0)
    width = max_x - min_x
    height = max_y - min_y

    avail_w = max(1.0, float(canvas_w - 2 * padding_px))
    avail_h = max(1.0, float(canvas_h - 2 * padding_px))
    scale = min(avail_w / width, avail_h / height)

    draw_w = width * scale
    draw_h = height * scale
    offset_x = float(padding_px) + (avail_w - draw_w) / 2.0
    offset_y = float(padding_px) + (avail_h - draw_h) / 2.0
    return MapTransform(
        min_x=min_x,
        max_y=max_y,
        scale=scale,
        offset_x=offset_x,
        offset_y=offset_y,
        draw_w=draw_w,
        draw_h=draw_h,
    )


def world_to_screen(x: float, y: float, transform: MapTransform) -> Point:
    sx = transform.offset_x + (x - transform.min_x) * transform.scale
    sy = transform.offset_y + (transform.max_y - y) * transform.scale
    return sx, sy


def transform_screen_rect(transform: MapTransform) -> tuple[int, int, int, int]:
    left = int(math.floor(transform.offset_x))
    top = int(math.floor(transform.offset_y))
    right = int(math.ceil(transform.offset_x + transform.draw_w))
    bottom = int(math.ceil(transform.offset_y + transform.draw_h))
    return left, top, right, bottom


def corridor_polygon_for_extent(
    p1: Point,
    p2: Point,
    max_offset: float,
    extent: Extent,
) -> list[Point]:
    if max_offset <= 0:
        return []

    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length <= 0:
        return []

    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux

    min_x, max_x, min_y, max_y = extent
    corners = [
        (min_x, min_y),
        (min_x, max_y),
        (max_x, min_y),
        (max_x, max_y),
    ]
    t_vals = [((cx - x1) * ux + (cy - y1) * uy) for cx, cy in corners]
    t_min = min(t_vals)
    t_max = max(t_vals)

    c1x, c1y = x1 + ux * t_min, y1 + uy * t_min
    c2x, c2y = x1 + ux * t_max, y1 + uy * t_max
    d = float(max_offset)
    return [
        (c1x + nx * d, c1y + ny * d),
        (c2x + nx * d, c2y + ny * d),
        (c2x - nx * d, c2y - ny * d),
        (c1x - nx * d, c1y - ny * d),
    ]
