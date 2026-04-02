from pathlib import Path

import pytest

from borehole_stick_gui.export_surfer_autoload import (
    AUTO_FIT_SCALE_MODE,
    MANUAL_SCALE_MODE,
    compute_a1_auto_map_scale,
    write_surfer_autoload_bat,
    write_surfer_autoload_script,
)


def test_write_surfer_autoload_script_supports_reverse_chainage(tmp_path: Path):
    script_path = write_surfer_autoload_script(
        path=tmp_path / "autoload.py",
        shp_path=tmp_path / "sticks.shp",
        palette_csv_path=tmp_path / "palette.csv",
        interval_postmap_csv_path=tmp_path / "labels.csv",
        interval_label_field="lithology",
        class_map={"SAND": 1, "CLAY": 2},
        out_srf_path=tmp_path / "out.srf",
        reverse_chainage=True,
        borehole_postmap_csv_path=tmp_path / "boreholes.csv",
        interval_label_size=7.5,
        borehole_label_size=10.5,
        scale_mode=MANUAL_SCALE_MODE,
        manual_scale=250.0,
    )

    content = script_path.read_text(encoding="utf-8")
    assert "--reverse-chainage" in content
    assert "axis.Reverse = True" in content
    assert 'default=True' in content
    assert "_set_bottom_axis_reverse(map_frame, bool(args.reverse_chainage))" in content
    assert "--interval-postmap" in content
    assert "--borehole-postmap" in content
    assert 'default=7.5' in content
    assert 'default=10.5' in content
    assert "--scale-mode" in content
    assert "--manual-scale" in content
    assert "A1_LANDSCAPE_WIDTH_CM = 84.1" in content
    assert "A1_LANDSCAPE_HEIGHT_CM = 59.4" in content
    assert "A1_MARGIN_FRACTION = 0.2" in content
    assert "_configure_a1_landscape_page(plot)" in content
    assert "_compute_auto_map_scale(" in content
    assert '_add_post_label_map(' in content
    assert 'label_position_names=("srfPostPosLeft",)' in content
    assert 'label_position_names=("srfPostPosAbove",)' in content
    assert "_CATEGORY_CLASS_MAP = {'SAND': 1, 'CLAY': 2}" in content
    assert 'query = f\'type="Polygon" and [CLASS_ID] = {int(class_id)}\'' in content
    assert 'query = f\'type="Polygon" and [CATEGORY] = "{_query_escape(category)}"\'' in content
    assert "default='manual'" in content
    assert "default=250.0" in content
    assert "applied manual scale" in content


def test_write_surfer_autoload_bat_includes_reverse_chainage_flag(tmp_path: Path):
    bat_path = write_surfer_autoload_bat(
        path=tmp_path / "run.bat",
        script_path=tmp_path / "autoload.py",
        shp_path=tmp_path / "sticks.shp",
        palette_csv_path=tmp_path / "palette.csv",
        interval_postmap_csv_path=tmp_path / "labels.csv",
        interval_label_field="lithology",
        out_srf_path=tmp_path / "out.srf",
        reverse_chainage=True,
        borehole_postmap_csv_path=tmp_path / "boreholes.csv",
        scale_mode=MANUAL_SCALE_MODE,
        manual_scale=125.0,
    )

    content = bat_path.read_text(encoding="ascii")
    assert "--reverse-chainage" in content
    assert "--interval-postmap" in content
    assert "--borehole-postmap" in content
    assert "--scale-mode" in content
    assert "--manual-scale" in content
    assert "set SCALE_MODE=manual" in content
    assert '--manual-scale "125.0"' in content


def test_write_surfer_autoload_bat_omits_reverse_chainage_flag_by_default(tmp_path: Path):
    bat_path = write_surfer_autoload_bat(
        path=tmp_path / "run.bat",
        script_path=tmp_path / "autoload.py",
        shp_path=tmp_path / "sticks.shp",
        palette_csv_path=tmp_path / "palette.csv",
        interval_postmap_csv_path=tmp_path / "labels.csv",
        interval_label_field="lithology",
        out_srf_path=tmp_path / "out.srf",
    )

    content = bat_path.read_text(encoding="ascii")
    assert "--reverse-chainage" not in content
    assert '--scale-mode "%SCALE_MODE%"' in content
    assert "--manual-scale" not in content
    assert f"set SCALE_MODE={AUTO_FIT_SCALE_MODE}" in content


def test_compute_a1_auto_map_scale_prefers_wider_extent() -> None:
    scale = compute_a1_auto_map_scale(x_extent=4000.0, y_extent=600.0)
    expected = 4000.0 / (84.1 * 0.8)
    assert scale == pytest.approx(expected)


def test_compute_a1_auto_map_scale_prefers_taller_extent() -> None:
    scale = compute_a1_auto_map_scale(x_extent=600.0, y_extent=4000.0)
    expected = 4000.0 / (59.4 * 0.8)
    assert scale == pytest.approx(expected)
