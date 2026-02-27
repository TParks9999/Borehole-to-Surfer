from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import StickPolygon


def write_bln(path: str | Path, polygons: Iterable[StickPolygon]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for poly in polygons:
            # Surfer-compatible BLN header: "num_points,boundary_flag"
            # Using 1 as a standard boundary flag for closed polygons.
            f.write(f"{len(poly.points)},1\n")
            for x, y in poly.points:
                f.write(f"{x:.3f},{y:.3f}\n")
