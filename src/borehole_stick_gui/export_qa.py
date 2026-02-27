from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable

from .models import ProjectedHole


def write_qa_csv(
    path: str | Path,
    projected_holes: Iterable[ProjectedHole],
    exported_counts_by_hole: Dict[str, int],
) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "hole_id",
                "easting",
                "northing",
                "collar_rl",
                "chainage",
                "offset_m",
                "included",
                "reason",
                "n_intervals_exported",
            ],
        )
        writer.writeheader()
        for hole in sorted(projected_holes, key=lambda x: x.hole_id):
            writer.writerow(
                {
                    "hole_id": hole.hole_id,
                    "easting": f"{hole.easting:.3f}",
                    "northing": f"{hole.northing:.3f}",
                    "collar_rl": f"{hole.collar_rl:.3f}",
                    "chainage": f"{hole.chainage:.3f}",
                    "offset_m": f"{hole.offset_m:.3f}",
                    "included": str(hole.included),
                    "reason": hole.reason,
                    "n_intervals_exported": exported_counts_by_hole.get(hole.hole_id, 0),
                }
            )

