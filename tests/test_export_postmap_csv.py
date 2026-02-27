from pathlib import Path

import pandas as pd

from borehole_stick_gui.export_postmap_csv import write_postmap_csvs
from borehole_stick_gui.models import CollarRecord, ProjectedHole


def test_write_postmap_csv_included_valid_only(tmp_path: Path):
    lith_df = pd.DataFrame(
        [
            {"hole_id": "BH1", "from": 0, "to": 2, "lithology": "SAND", "unit": "A"},
            {"hole_id": "BH1", "from": 2, "to": 1, "lithology": "CLAY", "unit": "B"},
            {"hole_id": "BH2", "from": 0, "to": 3, "lithology": "SILT", "unit": "C"},
        ]
    )
    lith_mapping = {"hole_id": "hole_id", "from_depth": "from", "to_depth": "to", "lithology": "lithology"}
    projected = [
        ProjectedHole("BH1", 500000.0, 7000000.0, 100.0, 250.0, 3.0, True, "ok"),
        ProjectedHole("BH2", 500050.0, 7000005.0, 98.0, 300.0, 30.0, False, "offset>25"),
    ]
    collars = [
        CollarRecord("BH1", 500000.0, 7000000.0, 100.0),
        CollarRecord("BH2", 500050.0, 7000005.0, 98.0),
    ]

    out_path, n_rows, label_path, label_rows = write_postmap_csvs(
        full_path=tmp_path / "postmap.csv",
        labels_path=tmp_path / "postmap_labels.csv",
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field="lithology",
        projected_holes=projected,
        collars=collars,
    )

    assert out_path.exists()
    assert label_path.exists()
    assert n_rows == 1
    assert label_rows == 1
    out_df = pd.read_csv(out_path)
    assert len(out_df) == 1
    assert float(out_df.loc[0, "chainage"]) == 250.0
    assert float(out_df.loc[0, "elevation_top"]) == 100.0
    assert float(out_df.loc[0, "elevation_base"]) == 98.0
    assert float(out_df.loc[0, "elevation_mid"]) == 99.0
    assert int(out_df.loc[0, "class_id"]) == 1
    assert out_df.loc[0, "unit"] == "A"


def test_label_filter_reduces_crowded_rows(tmp_path: Path):
    lith_df = pd.DataFrame(
        [
            {"hole_id": "BH1", "from": 0.0, "to": 0.4, "lithology": "A", "unit": "U1"},
            {"hole_id": "BH1", "from": 0.4, "to": 0.8, "lithology": "A", "unit": "U2"},
            {"hole_id": "BH1", "from": 0.8, "to": 1.2, "lithology": "A", "unit": "U3"},
            {"hole_id": "BH1", "from": 1.2, "to": 1.6, "lithology": "B", "unit": "U4"},
            {"hole_id": "BH1", "from": 1.6, "to": 2.0, "lithology": "B", "unit": "U5"},
            {"hole_id": "BH1", "from": 2.0, "to": 2.4, "lithology": "B", "unit": "U6"},
            {"hole_id": "BH2", "from": 0.0, "to": 0.4, "lithology": "A", "unit": "U7"},
            {"hole_id": "BH2", "from": 0.4, "to": 0.8, "lithology": "A", "unit": "U8"},
            {"hole_id": "BH2", "from": 0.8, "to": 1.2, "lithology": "B", "unit": "U9"},
            {"hole_id": "BH2", "from": 1.2, "to": 1.6, "lithology": "B", "unit": "U10"},
        ]
    )
    lith_mapping = {"hole_id": "hole_id", "from_depth": "from", "to_depth": "to", "lithology": "lithology"}
    projected = [
        ProjectedHole("BH1", 0.0, 0.0, 100.0, 100.0, 0.0, True, "ok"),
        ProjectedHole("BH2", 0.0, 0.0, 100.0, 108.0, 0.0, True, "ok"),
    ]
    collars = [
        CollarRecord("BH1", 0.0, 0.0, 100.0),
        CollarRecord("BH2", 0.0, 0.0, 100.0),
    ]

    _, full_rows, _, label_rows = write_postmap_csvs(
        full_path=tmp_path / "full.csv",
        labels_path=tmp_path / "labels.csv",
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field="lithology",
        projected_holes=projected,
        collars=collars,
        smart_filter_enabled=True,
        density_preset="Strong",
    )
    assert full_rows == 10
    assert label_rows < full_rows


def test_label_filter_presets_are_monotonic(tmp_path: Path):
    rows = []
    depth = 0.0
    for i in range(30):
        rows.append(
            {
                "hole_id": "BH1",
                "from": depth,
                "to": depth + 0.5,
                "lithology": "A" if i % 3 == 0 else ("B" if i % 3 == 1 else "C"),
                "unit": f"U{i}",
            }
        )
        depth += 0.5
    lith_df = pd.DataFrame(rows)
    lith_mapping = {"hole_id": "hole_id", "from_depth": "from", "to_depth": "to", "lithology": "lithology"}
    projected = [ProjectedHole("BH1", 0.0, 0.0, 100.0, 100.0, 0.0, True, "ok")]
    collars = [CollarRecord("BH1", 0.0, 0.0, 100.0)]

    _, _, _, n_light = write_postmap_csvs(
        full_path=tmp_path / "full_light.csv",
        labels_path=tmp_path / "labels_light.csv",
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field="lithology",
        projected_holes=projected,
        collars=collars,
        smart_filter_enabled=True,
        density_preset="Light",
    )
    _, _, _, n_medium = write_postmap_csvs(
        full_path=tmp_path / "full_medium.csv",
        labels_path=tmp_path / "labels_medium.csv",
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field="lithology",
        projected_holes=projected,
        collars=collars,
        smart_filter_enabled=True,
        density_preset="Medium",
    )
    _, _, _, n_strong = write_postmap_csvs(
        full_path=tmp_path / "full_strong.csv",
        labels_path=tmp_path / "labels_strong.csv",
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field="lithology",
        projected_holes=projected,
        collars=collars,
        smart_filter_enabled=True,
        density_preset="Strong",
    )

    assert n_light >= n_medium >= n_strong
    assert n_strong >= 1


def test_hybrid_thin_filter_suppresses_thin_units(tmp_path: Path):
    lith_df = pd.DataFrame(
        [
            {"hole_id": "BH1", "from": 0.0, "to": 0.1, "lithology": "A", "unit": "U1"},
            {"hole_id": "BH1", "from": 1.0, "to": 1.4, "lithology": "A", "unit": "U2"},
            {"hole_id": "BH1", "from": 2.0, "to": 2.4, "lithology": "A", "unit": "U3"},
        ]
    )
    lith_mapping = {"hole_id": "hole_id", "from_depth": "from", "to_depth": "to", "lithology": "lithology"}
    projected = [ProjectedHole("BH1", 0.0, 0.0, 100.0, 100.0, 0.0, True, "ok")]
    collars = [CollarRecord("BH1", 0.0, 0.0, 100.0)]

    _, _, labels_off_path, labels_off_rows = write_postmap_csvs(
        full_path=tmp_path / "full_off.csv",
        labels_path=tmp_path / "labels_off.csv",
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field="lithology",
        projected_holes=projected,
        collars=collars,
        smart_filter_enabled=True,
        density_preset="Light",
        thin_filter_enabled=False,
        merge_adjacent_enabled=False,
    )
    _, _, labels_on_path, labels_on_rows = write_postmap_csvs(
        full_path=tmp_path / "full_on.csv",
        labels_path=tmp_path / "labels_on.csv",
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field="lithology",
        projected_holes=projected,
        collars=collars,
        smart_filter_enabled=True,
        density_preset="Light",
        thin_filter_enabled=True,
        thin_min_abs_m=0.3,
        thin_relative_to_median=0.2,
        merge_adjacent_enabled=False,
    )

    assert labels_off_rows == 3
    assert labels_on_rows == 2
    labels_on_df = pd.read_csv(labels_on_path)
    assert labels_on_df["unit"].tolist() == ["U2", "U3"]
    labels_off_df = pd.read_csv(labels_off_path)
    assert sorted(labels_off_df["unit"].tolist()) == ["U1", "U2", "U3"]


def test_adjacent_same_category_near_gap_consolidates_to_one_label(tmp_path: Path):
    lith_df = pd.DataFrame(
        [
            {"hole_id": "BH1", "from": 0.0, "to": 1.0, "lithology": "A", "unit": "U1"},
            {"hole_id": "BH1", "from": 1.02, "to": 3.0, "lithology": "A", "unit": "U2"},
        ]
    )
    lith_mapping = {"hole_id": "hole_id", "from_depth": "from", "to_depth": "to", "lithology": "lithology"}
    projected = [ProjectedHole("BH1", 0.0, 0.0, 100.0, 100.0, 0.0, True, "ok")]
    collars = [CollarRecord("BH1", 0.0, 0.0, 100.0)]

    _, _, labels_path, label_rows = write_postmap_csvs(
        full_path=tmp_path / "full.csv",
        labels_path=tmp_path / "labels.csv",
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field="lithology",
        projected_holes=projected,
        collars=collars,
        smart_filter_enabled=True,
        density_preset="Light",
        thin_filter_enabled=False,
        merge_adjacent_enabled=True,
        adjacent_gap_tolerance_m=0.05,
    )

    assert label_rows == 1
    labels_df = pd.read_csv(labels_path)
    assert float(labels_df.loc[0, "elevation_top"]) == 100.0
    assert float(labels_df.loc[0, "elevation_base"]) == 97.0
    assert float(labels_df.loc[0, "elevation_mid"]) == 98.5
    assert labels_df.loc[0, "category"] == "A"


def test_adjacent_same_category_gap_above_tolerance_not_consolidated(tmp_path: Path):
    lith_df = pd.DataFrame(
        [
            {"hole_id": "BH1", "from": 0.0, "to": 1.0, "lithology": "A", "unit": "U1"},
            {"hole_id": "BH1", "from": 1.2, "to": 3.0, "lithology": "A", "unit": "U2"},
        ]
    )
    lith_mapping = {"hole_id": "hole_id", "from_depth": "from", "to_depth": "to", "lithology": "lithology"}
    projected = [ProjectedHole("BH1", 0.0, 0.0, 100.0, 100.0, 0.0, True, "ok")]
    collars = [CollarRecord("BH1", 0.0, 0.0, 100.0)]

    _, _, _, label_rows = write_postmap_csvs(
        full_path=tmp_path / "full.csv",
        labels_path=tmp_path / "labels.csv",
        lith_df=lith_df,
        lith_mapping=lith_mapping,
        classification_field="lithology",
        projected_holes=projected,
        collars=collars,
        smart_filter_enabled=True,
        density_preset="Light",
        thin_filter_enabled=False,
        merge_adjacent_enabled=True,
        adjacent_gap_tolerance_m=0.05,
    )

    assert label_rows == 2
