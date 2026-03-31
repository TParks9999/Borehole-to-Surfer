from pathlib import Path
import tkinter as tk

import pandas as pd

import borehole_stick_gui.app as app_module
from borehole_stick_gui.app import BoreholeStickApp, save_settings_file


def test_settings_payload_and_load_include_reverse_chainage(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(BoreholeStickApp, "_autoload_recent_files", lambda self: None)

    settings_path = tmp_path / ".borehole_stick_gui_settings.json"
    save_settings_file(settings_path, {"reverse_chainage": True})

    root = tk.Tk()
    root.withdraw()
    try:
        app = BoreholeStickApp(root)
        assert app.reverse_chainage.get() is True

        app.reverse_chainage.set(False)
        payload = app._settings_payload()
        assert payload["reverse_chainage"] is False
    finally:
        root.destroy()


def test_run_passes_reverse_chainage_flag_to_surfer_writers(tmp_path: Path, monkeypatch):
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

    def fake_write_qa_csv(path, projected, counts):
        Path(path).write_text("hole_id,chainage\n", encoding="ascii")

    def fake_save_palette_csv(path, category_field, palette):
        Path(path).write_text("category,color_hex\n", encoding="ascii")

    def fake_write_surfer_autoload_script(**kwargs):
        captured["script"] = bool(kwargs["reverse_chainage"])
        path = Path(kwargs["path"])
        path.write_text("# script\n", encoding="utf-8")
        return path

    def fake_write_surfer_autoload_bat(**kwargs):
        captured["bat"] = bool(kwargs["reverse_chainage"])
        path = Path(kwargs["path"])
        path.write_text("@echo off\n", encoding="ascii")
        return path

    monkeypatch.setattr(app_module, "write_bln", fake_write_bln)
    monkeypatch.setattr(app_module, "write_sticks_shapefile", fake_write_sticks_shapefile)
    monkeypatch.setattr(app_module, "write_postmap_csvs", fake_write_postmap_csvs)
    monkeypatch.setattr(app_module, "write_qa_csv", fake_write_qa_csv)
    monkeypatch.setattr(app_module, "save_palette_csv", fake_save_palette_csv)
    monkeypatch.setattr(app_module, "write_surfer_autoload_script", fake_write_surfer_autoload_script)
    monkeypatch.setattr(app_module, "write_surfer_autoload_bat", fake_write_surfer_autoload_bat)
    monkeypatch.setattr(app_module.subprocess, "Popen", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module.messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module.messagebox, "showerror", lambda *args, **kwargs: None)

    root = tk.Tk()
    root.withdraw()
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

        app.collar_map_vars["hole_id"].set("hole_id")
        app.collar_map_vars["easting"].set("easting")
        app.collar_map_vars["northing"].set("northing")
        app.collar_map_vars["rl"].set("rl")
        app.lith_map_vars["hole_id"].set("hole_id")
        app.lith_map_vars["from_depth"].set("from_depth")
        app.lith_map_vars["to_depth"].set("to_depth")

        app._run()

        assert captured == {"script": True, "bat": True}
    finally:
        root.destroy()
