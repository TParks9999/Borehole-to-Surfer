from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

import shapefile

from .models import StickPolygon


def write_sticks_shapefile(
    path: str | Path,
    polygons: Iterable[StickPolygon],
    class_map: Dict[str, int] | None = None,
) -> Path:
    polygons = list(polygons)
    base_path = Path(path)
    if base_path.suffix.lower() == ".shp":
        base_path = base_path.with_suffix("")
    base_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_class_map = dict(class_map or {})
    if not resolved_class_map:
        categories = sorted({poly.category for poly in polygons})
        resolved_class_map = {category: idx + 1 for idx, category in enumerate(categories)}

    with shapefile.Writer(str(base_path), shapeType=shapefile.POLYGON) as writer:
        writer.autoBalance = 1
        writer.field("HOLE_ID", "C", size=64)
        writer.field("CLASS_ID", "N", size=8, decimal=0)
        writer.field("CATEGORY", "C", size=80)
        writer.field("X_LEFT", "F", size=18, decimal=3)
        writer.field("X_RIGHT", "F", size=18, decimal=3)
        writer.field("Y_TOP", "F", size=18, decimal=3)
        writer.field("Y_BASE", "F", size=18, decimal=3)

        for poly in polygons:
            writer.poly([poly.points])
            writer.record(
                poly.hole_id,
                int(resolved_class_map[poly.category]),
                poly.category[:80],
                float(poly.x_left),
                float(poly.x_right),
                float(poly.y_top),
                float(poly.y_base),
            )

    shp_path = base_path.with_suffix(".shp")
    prj_path = base_path.with_suffix(".prj")
    prj_path.write_text('LOCAL_CS["Undefined"]\n', encoding="ascii")
    return shp_path
