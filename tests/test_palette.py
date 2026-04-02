from pathlib import Path

from borehole_stick_gui.palette import ensure_palette, load_palette_csv, save_palette_csv


def test_palette_round_trip(tmp_path: Path):
    palette = ensure_palette(["A", "B"], {"A": "#112233"})
    out = tmp_path / "palette.csv"
    save_palette_csv(out, "lithology", palette)
    loaded = load_palette_csv(out, "lithology")
    assert loaded["A"] == "#112233"
    assert "B" in loaded


def test_rainbow_defaults_for_new_categories_preserve_existing():
    palette = ensure_palette(["SAND", "CLAY", "SILT"], {"SAND": "#123456"})
    assert palette["SAND"] == "#123456"
    assert palette["CLAY"] == "#FF0000"
    assert palette["SILT"] == "#FF7F00"


def test_palette_save_drops_categories_not_in_current_run(tmp_path: Path):
    prior_run_palette = {"SAND": "#123456", "CLAY": "#654321"}
    current_run_palette = ensure_palette(["SAND"], prior_run_palette)
    out = tmp_path / "palette.csv"

    save_palette_csv(out, "lithology", current_run_palette)
    loaded = load_palette_csv(out, "lithology")

    assert loaded == {"SAND": "#123456"}


def test_palette_load_falls_back_when_file_has_single_classification_group(tmp_path: Path):
    out = tmp_path / "palette.csv"
    out.write_text(
        "classification_column,category,color_hex\n"
        "Category,CLAY,#8C564B\n"
        "Category,SAND,#F6D55C\n",
        encoding="utf-8",
    )

    loaded = load_palette_csv(out, "lithology")

    assert loaded == {"CLAY": "#8C564B", "SAND": "#F6D55C"}


def test_palette_load_does_not_fall_back_when_file_has_multiple_classification_groups(tmp_path: Path):
    out = tmp_path / "palette.csv"
    out.write_text(
        "classification_column,category,color_hex\n"
        "Category,CLAY,#8C564B\n"
        "Unit,SAND,#F6D55C\n",
        encoding="utf-8",
    )

    loaded = load_palette_csv(out, "lithology")

    assert loaded == {}
