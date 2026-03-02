from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import pandas as pd

from .models import CollarRecord, ProjectedHole


DEFAULT_MIN_LABEL_LENGTH_M = 1.0
DEFAULT_THIN_MIN_ABS_M = 0.3
DEFAULT_THIN_RELATIVE_TO_MEDIAN = 0.2
DEFAULT_ADJACENT_GAP_TOLERANCE_M = 0.05


def _safe_computed_name(base: str, existing_cols: set[str]) -> str:
    if base not in existing_cols:
        existing_cols.add(base)
        return base
    name = f"calc_{base}"
    while name in existing_cols:
        name = f"calc_{name}"
    existing_cols.add(name)
    return name


def build_category_class_map(categories: Iterable[str]) -> Dict[str, int]:
    unique = sorted({str(c).strip() for c in categories if str(c).strip() != ""})
    return {category: idx + 1 for idx, category in enumerate(unique)}


def _build_base_postmap_df(
    lith_df: pd.DataFrame,
    lith_mapping: Dict[str, str],
    classification_field: str,
    projected_holes: Iterable[ProjectedHole],
    collars: Iterable[CollarRecord],
) -> pd.DataFrame:
    if classification_field not in lith_df.columns:
        raise ValueError(f"Classification column '{classification_field}' not found in lithology table.")

    hole_col = lith_mapping["hole_id"]
    from_col = lith_mapping["from_depth"]
    to_col = lith_mapping["to_depth"]
    for col in [hole_col, from_col, to_col]:
        if col not in lith_df.columns:
            raise ValueError(f"Mapped lithology column '{col}' not found in lithology table.")

    df = lith_df.copy()
    df["_hole_id"] = df[hole_col].astype(str).str.strip()
    df = df[df["_hole_id"] != ""].copy()
    df["_from_depth"] = pd.to_numeric(df[from_col], errors="coerce")
    df["_to_depth"] = pd.to_numeric(df[to_col], errors="coerce")
    df["_category"] = df[classification_field].fillna("").astype(str).str.strip()
    df["_thickness"] = df["_to_depth"] - df["_from_depth"]

    valid_interval = df["_to_depth"] > df["_from_depth"]
    df = df[valid_interval].copy()

    projected_df = pd.DataFrame(
        [
            {
                "hole_id": item.hole_id,
                "chainage": item.chainage,
                "offset_m": item.offset_m,
                "included": item.included,
            }
            for item in projected_holes
        ]
    )
    collar_df = pd.DataFrame([{"hole_id": item.hole_id, "collar_rl": item.rl} for item in collars])

    df = df.merge(projected_df, how="left", left_on="_hole_id", right_on="hole_id")
    df = df.merge(collar_df, how="left", left_on="_hole_id", right_on="hole_id", suffixes=("", "_collar"))
    df = df[df["included"] == True].copy()  # noqa: E712
    df = df[df["chainage"].notna() & df["collar_rl"].notna()].copy()

    df["elevation_top"] = df["collar_rl"] - df["_from_depth"]
    df["elevation_base"] = df["collar_rl"] - df["_to_depth"]
    df["elevation_mid"] = (df["elevation_top"] + df["elevation_base"]) / 2.0
    return df


def _add_computed_columns(
    df: pd.DataFrame,
    lith_df: pd.DataFrame,
    class_map: Dict[str, int] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    resolved_map = dict(class_map or {})
    if not resolved_map:
        resolved_map = build_category_class_map(out["_category"].tolist())
    else:
        # Keep provided IDs stable; append any missing categories deterministically.
        next_id = max(resolved_map.values(), default=0) + 1
        for category in sorted(out["_category"].astype(str).str.strip().unique().tolist()):
            if category and category not in resolved_map:
                resolved_map[category] = next_id
                next_id += 1
    out["class_id"] = out["_category"].map(resolved_map).astype("int64")

    existing = set(lith_df.columns.tolist())
    hole_out = _safe_computed_name("hole_id", existing)
    chain_out = _safe_computed_name("chainage", existing)
    elev_mid_out = _safe_computed_name("elevation_mid", existing)
    elev_top_out = _safe_computed_name("elevation_top", existing)
    elev_base_out = _safe_computed_name("elevation_base", existing)
    class_out = _safe_computed_name("class_id", existing)
    category_out = _safe_computed_name("category", existing)
    offset_out = _safe_computed_name("offset_m", existing)
    incl_out = _safe_computed_name("included", existing)

    out[hole_out] = out["_hole_id"]
    out[chain_out] = out["chainage"]
    out[elev_mid_out] = out["elevation_mid"]
    out[elev_top_out] = out["elevation_top"]
    out[elev_base_out] = out["elevation_base"]
    out[class_out] = out["class_id"]
    out[category_out] = out["_category"]
    out[offset_out] = out["offset_m"]
    out[incl_out] = out["included"]

    computed_order = [
        hole_out,
        chain_out,
        elev_mid_out,
        elev_top_out,
        elev_base_out,
        class_out,
        category_out,
        offset_out,
        incl_out,
    ]
    original_order = list(lith_df.columns)
    return out[computed_order + original_order].copy()


def _apply_thin_filter(
    df: pd.DataFrame, thin_min_abs_m: float, thin_relative_to_median: float
) -> pd.DataFrame:
    work = df.copy()
    if work.empty:
        return work

    kept: list[pd.DataFrame] = []
    for _hole_id, hole_rows in work.groupby("_hole_id", sort=False):
        hole = hole_rows.copy()
        median_thickness = float(hole["_thickness"].median()) if not hole.empty else 0.0
        threshold = max(float(thin_min_abs_m), float(thin_relative_to_median) * median_thickness)
        kept.append(hole[hole["_thickness"] >= threshold].copy())

    out = pd.concat(kept, ignore_index=True) if kept else work.iloc[0:0].copy()
    return out


def _consolidate_adjacent_intervals(df: pd.DataFrame, gap_tolerance_m: float) -> pd.DataFrame:
    work = df.copy()
    if work.empty:
        return work

    merged_rows: list[pd.Series] = []
    tol = float(gap_tolerance_m)

    for _hole_id, hole_rows in work.groupby("_hole_id", sort=False):
        ordered = hole_rows.sort_values(by=["_from_depth", "_to_depth"], ascending=[True, True]).copy()
        if ordered.empty:
            continue

        current = ordered.iloc[0].copy()
        current_from = float(current["_from_depth"])
        current_to = float(current["_to_depth"])
        current_thickness = float(current["_thickness"])
        current_count = 1

        for _, row in ordered.iloc[1:].iterrows():
            row_from = float(row["_from_depth"])
            row_to = float(row["_to_depth"])
            row_thickness = float(row["_thickness"])
            same_category = str(row["_category"]) == str(current["_category"])
            gap = row_from - current_to
            is_adjacent = gap <= tol

            if same_category and is_adjacent:
                current_to = max(current_to, row_to)
                current_thickness += row_thickness
                current_count += 1
                continue

            current["_from_depth"] = current_from
            current["_to_depth"] = current_to
            current["_thickness"] = current_thickness
            current["elevation_top"] = float(current["collar_rl"]) - current_from
            current["elevation_base"] = float(current["collar_rl"]) - current_to
            current["elevation_mid"] = (float(current["elevation_top"]) + float(current["elevation_base"])) / 2.0
            current["_merged_count"] = current_count
            merged_rows.append(current.copy())

            current = row.copy()
            current_from = row_from
            current_to = row_to
            current_thickness = row_thickness
            current_count = 1

        current["_from_depth"] = current_from
        current["_to_depth"] = current_to
        current["_thickness"] = current_thickness
        current["elevation_top"] = float(current["collar_rl"]) - current_from
        current["elevation_base"] = float(current["collar_rl"]) - current_to
        current["elevation_mid"] = (float(current["elevation_top"]) + float(current["elevation_base"])) / 2.0
        current["_merged_count"] = current_count
        merged_rows.append(current.copy())

    out = pd.DataFrame(merged_rows, columns=list(work.columns) + ["_merged_count"])
    return out


def _apply_min_label_length_filter(df: pd.DataFrame, min_label_length_m: float) -> pd.DataFrame:
    work = df.copy()
    if work.empty:
        return work
    return work[work["_thickness"] >= float(min_label_length_m)].copy()


def build_postmap_dataframes(
    lith_df: pd.DataFrame,
    lith_mapping: Dict[str, str],
    classification_field: str,
    projected_holes: Iterable[ProjectedHole],
    collars: Iterable[CollarRecord],
    smart_filter_enabled: bool = True,
    min_label_length_m: float = DEFAULT_MIN_LABEL_LENGTH_M,
    thin_filter_enabled: bool = True,
    thin_min_abs_m: float = DEFAULT_THIN_MIN_ABS_M,
    thin_relative_to_median: float = DEFAULT_THIN_RELATIVE_TO_MEDIAN,
    merge_adjacent_enabled: bool = True,
    adjacent_gap_tolerance_m: float = DEFAULT_ADJACENT_GAP_TOLERANCE_M,
    class_map: Dict[str, int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_df = _build_base_postmap_df(
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field=classification_field,
        projected_holes=projected_holes,
        collars=collars,
    )
    full_df = _add_computed_columns(base_df, lith_df, class_map=class_map)

    if not smart_filter_enabled:
        return full_df, full_df.copy()

    label_candidates = base_df.copy()
    if thin_filter_enabled:
        label_candidates = _apply_thin_filter(
            label_candidates,
            thin_min_abs_m=float(thin_min_abs_m),
            thin_relative_to_median=float(thin_relative_to_median),
        )
    if merge_adjacent_enabled:
        label_candidates = _consolidate_adjacent_intervals(
            label_candidates, gap_tolerance_m=float(adjacent_gap_tolerance_m)
        )

    labels_raw = _apply_min_label_length_filter(
        label_candidates, min_label_length_m=float(min_label_length_m)
    )

    # Ensure each included hole keeps at least one label row.
    by_hole_labels = set(labels_raw["_hole_id"].astype(str).tolist()) if not labels_raw.empty else set()
    for hole_id, hole_rows in label_candidates.groupby("_hole_id", sort=False):
        if str(hole_id) not in by_hole_labels:
            idx = hole_rows["_thickness"].idxmax()
            labels_raw = pd.concat([labels_raw, label_candidates.loc[[idx]]], ignore_index=True)

    labels_df = _add_computed_columns(labels_raw, lith_df, class_map=class_map)
    return full_df, labels_df


def write_postmap_csvs(
    full_path: str | Path,
    labels_path: str | Path,
    lith_df: pd.DataFrame,
    lith_mapping: Dict[str, str],
    classification_field: str,
    projected_holes: Iterable[ProjectedHole],
    collars: Iterable[CollarRecord],
    smart_filter_enabled: bool = True,
    min_label_length_m: float = DEFAULT_MIN_LABEL_LENGTH_M,
    thin_filter_enabled: bool = True,
    thin_min_abs_m: float = DEFAULT_THIN_MIN_ABS_M,
    thin_relative_to_median: float = DEFAULT_THIN_RELATIVE_TO_MEDIAN,
    merge_adjacent_enabled: bool = True,
    adjacent_gap_tolerance_m: float = DEFAULT_ADJACENT_GAP_TOLERANCE_M,
    class_map: Dict[str, int] | None = None,
) -> Tuple[Path, int, Path, int]:
    full_df, labels_df = build_postmap_dataframes(
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field=classification_field,
        projected_holes=projected_holes,
        collars=collars,
        smart_filter_enabled=smart_filter_enabled,
        min_label_length_m=min_label_length_m,
        thin_filter_enabled=thin_filter_enabled,
        thin_min_abs_m=thin_min_abs_m,
        thin_relative_to_median=thin_relative_to_median,
        merge_adjacent_enabled=merge_adjacent_enabled,
        adjacent_gap_tolerance_m=adjacent_gap_tolerance_m,
        class_map=class_map,
    )

    full_out = Path(full_path)
    labels_out = Path(labels_path)
    full_out.parent.mkdir(parents=True, exist_ok=True)
    labels_out.parent.mkdir(parents=True, exist_ok=True)
    full_df.to_csv(full_out, index=False)
    labels_df.to_csv(labels_out, index=False)
    return full_out, len(full_df), labels_out, len(labels_df)
