from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from .models import CollarRecord, LineDefinition, LinePoint, LithRecord


def normalize_header(text: str) -> str:
    return "".join(ch for ch in str(text).strip().lower() if ch.isalnum())


STANDARD_CANDIDATES = {
    "hole_id": ["holeid", "hole_id", "bhid", "id", "hole"],
    "easting": ["easting", "x", "utm_e", "utmeasting"],
    "northing": ["northing", "y", "utm_n", "utmnorthing"],
    "rl": ["rl", "elevation", "collarrl", "z", "collarelevation"],
    "from_depth": ["from", "fromdepth", "depthfrom", "startdepth"],
    "to_depth": ["to", "todepth", "depthto", "enddepth"],
}


@dataclass(frozen=True)
class MappingResult:
    mapping: Dict[str, str]
    missing: List[str]


def detect_mapping(columns: Iterable[str], required_fields: Iterable[str]) -> MappingResult:
    col_list = list(columns)
    norm_lookup = {normalize_header(c): c for c in col_list}
    mapping: Dict[str, str] = {}
    missing: List[str] = []

    for field in required_fields:
        candidates = STANDARD_CANDIDATES.get(field, [field])
        found = None
        for candidate in candidates:
            key = normalize_header(candidate)
            if key in norm_lookup:
                found = norm_lookup[key]
                break
        if found is None:
            missing.append(field)
        else:
            mapping[field] = found
    return MappingResult(mapping=mapping, missing=missing)


def read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, mapping: Dict[str, str], required: Iterable[str]) -> None:
    missing_keys = [key for key in required if key not in mapping]
    if missing_keys:
        raise ValueError(f"Missing mapped fields: {', '.join(missing_keys)}")
    missing_cols = [mapping[key] for key in required if mapping[key] not in df.columns]
    if missing_cols:
        raise ValueError(f"Mapped columns not found in CSV: {', '.join(missing_cols)}")


def _to_numeric(series: pd.Series, field: str) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce")
    if out.isna().any():
        sample = series[out.isna()].head(5).astype(str).tolist()
        raise ValueError(f"Non-numeric values in {field}: {sample}")
    return out


def parse_collar(df: pd.DataFrame, mapping: Dict[str, str]) -> List[CollarRecord]:
    required = ["hole_id", "easting", "northing", "rl"]
    _require_columns(df, mapping, required)
    part = df[[mapping[key] for key in required]].copy()
    part.columns = required
    part["easting"] = _to_numeric(part["easting"], "easting")
    part["northing"] = _to_numeric(part["northing"], "northing")
    part["rl"] = _to_numeric(part["rl"], "rl")
    part["hole_id"] = part["hole_id"].astype(str).str.strip()
    part = part[part["hole_id"] != ""]
    return [
        CollarRecord(
            hole_id=row.hole_id,
            easting=float(row.easting),
            northing=float(row.northing),
            rl=float(row.rl),
        )
        for row in part.itertuples(index=False)
    ]


def parse_lith(df: pd.DataFrame, mapping: Dict[str, str], category_field: str) -> List[LithRecord]:
    required = ["hole_id", "from_depth", "to_depth", category_field]
    _require_columns(df, mapping, required)
    part = df[[mapping[key] for key in required]].copy()
    part.columns = required
    part["hole_id"] = part["hole_id"].astype(str).str.strip()
    part = part[part["hole_id"] != ""]
    part["from_depth"] = _to_numeric(part["from_depth"], "from_depth")
    part["to_depth"] = _to_numeric(part["to_depth"], "to_depth")
    # Keep nulls as empty strings here. Missing categories are validated earlier in app flow.
    part[category_field] = part[category_field].fillna("").astype(str).str.strip()

    return [
        LithRecord(
            hole_id=row.hole_id,
            from_depth=float(row.from_depth),
            to_depth=float(row.to_depth),
            category=str(getattr(row, category_field)),
        )
        for row in part.itertuples(index=False)
    ]


def split_lith_validity(records: List[LithRecord]) -> Tuple[List[LithRecord], List[LithRecord]]:
    valid: List[LithRecord] = []
    invalid: List[LithRecord] = []
    for item in records:
        if item.to_depth > item.from_depth:
            valid.append(item)
        else:
            invalid.append(item)
    return valid, invalid


def find_duplicate_hole_ids(df: pd.DataFrame, hole_id_col: str) -> List[str]:
    if hole_id_col not in df.columns:
        return []
    hole_ids = df[hole_id_col].fillna("").astype(str).str.strip()
    hole_ids = hole_ids[hole_ids != ""]
    if hole_ids.empty:
        return []
    counts = hole_ids.value_counts()
    return sorted(counts[counts > 1].index.tolist())


def find_missing_category_rows(df: pd.DataFrame, category_col: str) -> List[int]:
    if category_col not in df.columns:
        return []
    vals = df[category_col].fillna("").astype(str).str.strip()
    bad = vals == ""
    # Return 1-based CSV-like row numbers (excluding header offset awareness).
    return [int(idx) + 2 for idx in df.index[bad].tolist()]


def parse_line_definition_df(df: pd.DataFrame) -> LineDefinition:
    norm_lookup = {normalize_header(col): col for col in df.columns}
    required = ["point", "easting", "northing", "chainage"]
    missing = [col for col in required if col not in norm_lookup]
    if missing:
        raise ValueError(f"Line CSV missing required columns: {', '.join(missing)}")

    part = df[
        [
            norm_lookup["point"],
            norm_lookup["easting"],
            norm_lookup["northing"],
            norm_lookup["chainage"],
        ]
    ].copy()
    part.columns = required
    part["point"] = part["point"].fillna("").astype(str).str.strip().str.upper()
    part = part[part["point"] != ""].copy()
    if len(part) != 2:
        raise ValueError("Line CSV must contain exactly two rows: one for P1 and one for P2.")

    allowed = {"P1", "P2"}
    points = set(part["point"].tolist())
    if points != allowed:
        raise ValueError("Line CSV point values must be exactly 'P1' and 'P2'.")

    if part["point"].duplicated().any():
        raise ValueError("Line CSV contains duplicate point labels.")

    part["easting"] = _to_numeric(part["easting"], "easting")
    part["northing"] = _to_numeric(part["northing"], "northing")
    part["chainage"] = _to_numeric(part["chainage"], "chainage")

    rows = {row.point: row for row in part.itertuples(index=False)}
    return LineDefinition(
        p1=LinePoint(
            easting=float(rows["P1"].easting),
            northing=float(rows["P1"].northing),
            chainage=float(rows["P1"].chainage),
        ),
        p2=LinePoint(
            easting=float(rows["P2"].easting),
            northing=float(rows["P2"].northing),
            chainage=float(rows["P2"].chainage),
        ),
    )


def read_line_definition_csv(path: str | Path) -> LineDefinition:
    df = read_csv(path)
    return parse_line_definition_df(df)
