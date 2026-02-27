from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from .models import LithRecord, ProjectedHole, StickPolygon


def build_stick_polygons(
    projected_holes: Iterable[ProjectedHole],
    lith_records: Iterable[LithRecord],
    width_m: float,
    category_to_color: Dict[str, str],
) -> Tuple[List[StickPolygon], List[str]]:
    if width_m <= 0:
        raise ValueError("Rectangle width must be greater than zero.")

    holes = {h.hole_id: h for h in projected_holes if h.included}
    lith_by_hole: Dict[str, List[LithRecord]] = defaultdict(list)
    for lith in lith_records:
        lith_by_hole[lith.hole_id].append(lith)

    half_w = width_m / 2.0
    polygons: List[StickPolygon] = []
    warnings: List[str] = []

    for hole_id, hole in holes.items():
        intervals = lith_by_hole.get(hole_id, [])
        if not intervals:
            warnings.append(f"No lithology intervals for included hole {hole_id}.")
            continue

        intervals = sorted(intervals, key=lambda x: (x.from_depth, x.to_depth))
        for interval in intervals:
            y_top = hole.collar_rl - interval.from_depth
            y_base = hole.collar_rl - interval.to_depth
            x_left = hole.chainage - half_w
            x_right = hole.chainage + half_w
            color_hex = category_to_color.get(interval.category, "#808080")
            if interval.category not in category_to_color:
                warnings.append(
                    f"Category '{interval.category}' missing in palette; using fallback #808080."
                )
            points = [
                (x_left, y_top),
                (x_right, y_top),
                (x_right, y_base),
                (x_left, y_base),
                (x_left, y_top),
            ]
            polygons.append(
                StickPolygon(
                    hole_id=hole.hole_id,
                    category=interval.category,
                    color_hex=color_hex,
                    y_top=y_top,
                    y_base=y_base,
                    x_left=x_left,
                    x_right=x_right,
                    points=points,
                )
            )

    polygons.sort(key=lambda p: (p.x_left + p.x_right) / 2.0)
    return polygons, warnings

