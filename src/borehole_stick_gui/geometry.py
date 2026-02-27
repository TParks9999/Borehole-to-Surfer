from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List

from .models import CollarRecord, LineDefinition, ProjectedHole


@dataclass(frozen=True)
class UnitLine:
    ux: float
    uy: float
    length: float


def build_unit_line(line: LineDefinition) -> UnitLine:
    dx = line.p2.easting - line.p1.easting
    dy = line.p2.northing - line.p1.northing
    length = math.hypot(dx, dy)
    if length <= 0.0:
        raise ValueError("Line points must not be identical.")
    return UnitLine(ux=dx / length, uy=dy / length, length=length)


def project_collar_records(
    collars: Iterable[CollarRecord],
    line: LineDefinition,
    max_offset_m: float,
) -> List[ProjectedHole]:
    unit = build_unit_line(line)
    out: List[ProjectedHole] = []

    for collar in collars:
        vx = collar.easting - line.p1.easting
        vy = collar.northing - line.p1.northing
        along = vx * unit.ux + vy * unit.uy
        chainage = line.p1.chainage + along
        cross_signed = vx * unit.uy - vy * unit.ux
        offset_m = abs(cross_signed)
        included = offset_m <= max_offset_m
        reason = "ok" if included else f"offset>{max_offset_m}"

        out.append(
            ProjectedHole(
                hole_id=collar.hole_id,
                easting=collar.easting,
                northing=collar.northing,
                collar_rl=collar.rl,
                chainage=chainage,
                offset_m=offset_m,
                included=included,
                reason=reason,
            )
        )
    return out

