from pathlib import Path

from borehole_stick_gui.export_surfer_autoload import (
    write_surfer_autoload_bat,
    write_surfer_autoload_script,
)


def test_write_surfer_autoload_script_supports_reverse_chainage(tmp_path: Path):
    script_path = write_surfer_autoload_script(
        path=tmp_path / "autoload.py",
        shp_path=tmp_path / "sticks.shp",
        palette_csv_path=tmp_path / "palette.csv",
        postmap_csv_path=tmp_path / "labels.csv",
        label_field="lithology",
        out_srf_path=tmp_path / "out.srf",
        reverse_chainage=True,
    )

    content = script_path.read_text(encoding="utf-8")
    assert "--reverse-chainage" in content
    assert "axis.Reverse = True" in content
    assert 'default=True' in content
    assert "_set_bottom_axis_reverse(map_frame, bool(args.reverse_chainage))" in content


def test_write_surfer_autoload_bat_includes_reverse_chainage_flag(tmp_path: Path):
    bat_path = write_surfer_autoload_bat(
        path=tmp_path / "run.bat",
        script_path=tmp_path / "autoload.py",
        shp_path=tmp_path / "sticks.shp",
        palette_csv_path=tmp_path / "palette.csv",
        postmap_csv_path=tmp_path / "labels.csv",
        label_field="lithology",
        out_srf_path=tmp_path / "out.srf",
        reverse_chainage=True,
    )

    content = bat_path.read_text(encoding="ascii")
    assert "--reverse-chainage" in content


def test_write_surfer_autoload_bat_omits_reverse_chainage_flag_by_default(tmp_path: Path):
    bat_path = write_surfer_autoload_bat(
        path=tmp_path / "run.bat",
        script_path=tmp_path / "autoload.py",
        shp_path=tmp_path / "sticks.shp",
        palette_csv_path=tmp_path / "palette.csv",
        postmap_csv_path=tmp_path / "labels.csv",
        label_field="lithology",
        out_srf_path=tmp_path / "out.srf",
    )

    content = bat_path.read_text(encoding="ascii")
    assert "--reverse-chainage" not in content
