from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk

import pandas as pd
import pytest

import borehole_stick_gui.app as app_module
from borehole_stick_gui.app import BoreholeStickApp, save_settings_file


def _make_root_or_skip() -> tk.Tk:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk is unavailable in this environment: {exc}")
    root.withdraw()
    return root


def test_settings_payload_and_load_include_reverse_chainage(monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(BoreholeStickApp, "_autoload_recent_files", lambda self: None)

        settings_path = tmp_path / ".borehole_stick_gui_settings.json"
        save_settings_file(
            settings_path,
            {
                "reverse_chainage": True,
                "show_satellite_basemap": False,
                "show_borehole_names": False,
                "utm_zone": "56",
                "utm_hemisphere": "S",
                "interval_label_size": "9",
                "borehole_name_label_size": "11",
            },
        )

        root = _make_root_or_skip()
        try:
            app = BoreholeStickApp(root)
            assert app.reverse_chainage.get() is True
            assert app.show_satellite_basemap.get() is False
            assert app.show_borehole_names.get() is False
            assert app.utm_zone.get() == "56"
            assert app.utm_hemisphere.get() == "S"
            assert app.interval_label_size.get() == "9"
            assert app.borehole_name_label_size.get() == "11"

            app.reverse_chainage.set(False)
            app.show_satellite_basemap.set(True)
            app.show_borehole_names.set(True)
            payload = app._settings_payload()
            assert payload["reverse_chainage"] is False
            assert payload["show_satellite_basemap"] is True
            assert payload["show_borehole_names"] is True
            assert "survey_path" not in payload
        finally:
            root.destroy()


def test_run_passes_reverse_chainage_flag_to_surfer_writers(monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(BoreholeStickApp, "_autoload_recent_files", lambda self: None)

        captured: dict[str, bool] = {}

        def fake_write_bln(path, polygons):
            Path(path).write_text("", encoding="ascii")

        def fake_write_sticks_shapefile(path, polygons, class_map=None):
            return Path(path)

        def fake_write_postmap_csvs(**kwargs):
            full_path = Path(kwargs["full_path"])
            labels_path = Path(kwargs["labels_path"])
            full_path.write_text("chainage,elevation_mid,lithology\n", encoding="ascii")
            labels_path.write_text("chainage,elevation_mid,lithology\n", encoding="ascii")
            return full_path, 1, labels_path, 1

        def fake_write_borehole_name_postmap_csv(**kwargs):
            path = Path(kwargs["path"])
            path.write_text("hole_id,chainage,elevation_label\n", encoding="ascii")
            return path, 1

        def fake_write_qa_csv(path, projected, counts):
            Path(path).write_text("hole_id,chainage\n", encoding="ascii")

        def fake_save_palette_csv(path, category_field, palette):
            Path(path).write_text("category,color_hex\n", encoding="ascii")

        def fake_write_surfer_autoload_script(**kwargs):
            captured["script"] = bool(kwargs["reverse_chainage"])
            captured["script_interval_size"] = float(kwargs["interval_label_size"])
            captured["script_borehole_size"] = float(kwargs["borehole_label_size"])
            captured["script_has_boreholes"] = kwargs["borehole_postmap_csv_path"] is not None
            path = Path(kwargs["path"])
            path.write_text("# script\n", encoding="utf-8")
            return path

        def fake_write_surfer_autoload_bat(**kwargs):
            captured["bat"] = bool(kwargs["reverse_chainage"])
            captured["bat_interval_size"] = float(kwargs["interval_label_size"])
            captured["bat_borehole_size"] = float(kwargs["borehole_label_size"])
            captured["bat_has_boreholes"] = kwargs["borehole_postmap_csv_path"] is not None
            path = Path(kwargs["path"])
            path.write_text("@echo off\n", encoding="ascii")
            return path

        monkeypatch.setattr(app_module, "write_bln", fake_write_bln)
        monkeypatch.setattr(app_module, "write_sticks_shapefile", fake_write_sticks_shapefile)
        monkeypatch.setattr(app_module, "write_postmap_csvs", fake_write_postmap_csvs)
        monkeypatch.setattr(app_module, "write_borehole_name_postmap_csv", fake_write_borehole_name_postmap_csv)
        monkeypatch.setattr(app_module, "write_qa_csv", fake_write_qa_csv)
        monkeypatch.setattr(app_module, "save_palette_csv", fake_save_palette_csv)
        monkeypatch.setattr(app_module, "write_surfer_autoload_script", fake_write_surfer_autoload_script)
        monkeypatch.setattr(app_module, "write_surfer_autoload_bat", fake_write_surfer_autoload_bat)
        monkeypatch.setattr(app_module.subprocess, "Popen", lambda *args, **kwargs: None)
        monkeypatch.setattr(app_module.messagebox, "showinfo", lambda *args, **kwargs: None)
        monkeypatch.setattr(app_module.messagebox, "showerror", lambda *args, **kwargs: None)

        root = _make_root_or_skip()
        try:
            app = BoreholeStickApp(root)
            app.settings_path = tmp_path / ".borehole_stick_gui_settings.json"
            app.collar_df = pd.DataFrame(
                [{"hole_id": "BH1", "easting": 10.0, "northing": 0.0, "rl": 100.0}]
            )
            app.lith_df = pd.DataFrame(
                [{"hole_id": "BH1", "from_depth": 0.0, "to_depth": 2.0, "lithology": "SAND"}]
            )
            app.output_dir.set(str(tmp_path))
            app.output_base.set("reverse_chainage_case")
            app.category_field.set("lithology")
            app.reverse_chainage.set(True)
            app.interval_label_size.set("7")
            app.borehole_name_label_size.set("10")
            app.show_borehole_names.set(True)

            app.collar_map_vars["hole_id"].set("hole_id")
            app.collar_map_vars["easting"].set("easting")
            app.collar_map_vars["northing"].set("northing")
            app.collar_map_vars["rl"].set("rl")
            app.lith_map_vars["hole_id"].set("hole_id")
            app.lith_map_vars["from_depth"].set("from_depth")
            app.lith_map_vars["to_depth"].set("to_depth")

            app._run()

            assert captured == {
                "script": True,
                "script_interval_size": 7.0,
                "script_borehole_size": 10.0,
                "script_has_boreholes": True,
                "bat": True,
                "bat_interval_size": 7.0,
                "bat_borehole_size": 10.0,
                "bat_has_boreholes": True,
            }
        finally:
            root.destroy()
