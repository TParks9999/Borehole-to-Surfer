from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class LinePoint:
    easting: float
    northing: float
    chainage: float


@dataclass(frozen=True)
class LineDefinition:
    p1: LinePoint
    p2: LinePoint


@dataclass(frozen=True)
class CollarRecord:
    hole_id: str
    easting: float
    northing: float
    rl: float


@dataclass(frozen=True)
class LithRecord:
    hole_id: str
    from_depth: float
    to_depth: float
    category: str


@dataclass(frozen=True)
class ProjectedHole:
    hole_id: str
    easting: float
    northing: float
    collar_rl: float
    chainage: float
    offset_m: float
    included: bool
    reason: str


@dataclass(frozen=True)
class StickPolygon:
    hole_id: str
    category: str
    color_hex: str
    y_top: float
    y_base: float
    x_left: float
    x_right: float
    points: List[Tuple[float, float]]


PaletteMap = Dict[str, str]

