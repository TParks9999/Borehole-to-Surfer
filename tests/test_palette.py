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
