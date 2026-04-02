from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk

import pandas as pd
import pytest

import borehole_stick_gui.app as app_module
from borehole_stick_gui.app import BoreholeStickApp
from borehole_stick_gui.map_view import expand_extent


class FakeCanvas:
    def __init__(self, width: int = 640, height: int = 480) -> None:
        self.width = width
        self.height = height
        self._next_id = 1
        self.lines: list[dict[str, object]] = []
        self.polygons: list[dict[str, object]] = []
        self.rectangles: list[dict[str, object]] = []
        self.texts: list[dict[str, object]] = []
        self._items: dict[int, dict[str, object]] = {}

    def delete(self, *_args) -> None:
        pass

    def winfo_width(self) -> int:
        return self.width

    def winfo_height(self) -> int:
        return self.height

    def _allocate_id(self, item: dict[str, object]) -> int:
        item_id = self._next_id
        self._next_id += 1
        self._items[item_id] = item
        return item_id

    def create_text(self, *args, **kwargs) -> int:
        item = {
            "type": "text",
            "x": float(args[0]),
            "y": float(args[1]),
            "kwargs": kwargs,
        }
        self.texts.append(item)
        return self._allocate_id(item)

    def create_image(self, *_args, **_kwargs) -> int:
        return 1

    def create_polygon(self, coords, **kwargs) -> int:
        self.polygons.append({"coords": coords, "kwargs": kwargs})
        return 1

    def create_rectangle(self, *args, **kwargs) -> int:
        item = {
            "type": "rectangle",
            "coords": args,
            "kwargs": kwargs,
        }
        self.rectangles.append(item)
        return self._allocate_id(item)

    def create_line(self, *args, **kwargs) -> int:
        item = {
            "type": "line",
            "coords": args,
            "kwargs": kwargs,
        }
        self.lines.append(item)
        return self._allocate_id(item)

    def create_oval(self, *_args, **_kwargs) -> int:
        return 1

    def bbox(self, item_id: int) -> tuple[int, int, int, int] | None:
        item = self._items.get(item_id)
        if item is None or item.get("type") != "text":
            return None
        kwargs = item["kwargs"]
        text = str(kwargs.get("text", ""))
        x = float(item["x"])
        y = float(item["y"])
        width = max(8, len(text) * 6)
        height = 12
        anchor = str(kwargs.get("anchor", "center"))
        if anchor == "w":
            left = x
            right = x + width
            top = y - height / 2
            bottom = y + height / 2
        else:
            left = x - width / 2
            right = x + width / 2
            top = y - height / 2
            bottom = y + height / 2
        return (int(left), int(top), int(right), int(bottom))

    def tag_lower(self, *_args) -> None:
        pass


def _build_app(monkeypatch) -> tuple[tk.Tk, BoreholeStickApp]:
    tmp_dir = TemporaryDirectory()
    tmp_path = Path(tmp_dir.name)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(BoreholeStickApp, "_autoload_recent_files", lambda self: None)

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        tmp_dir.cleanup()
        pytest.skip(f"Tk is unavailable in this environment: {exc}")
    root.withdraw()
    app = BoreholeStickApp(root)
    app._tmp_dir = tmp_dir
    return root, app


def _configure_map_inputs(app: BoreholeStickApp) -> None:
    app.collar_df = pd.DataFrame(
        [
            {"hole_id": "BH1", "easting": 100.0, "northing": 100.0, "rl": 50.0},
            {"hole_id": "BH2", "easting": 200.0, "northing": 250.0, "rl": 55.0},
        ]
    )
    app.collar_map_vars["hole_id"].set("hole_id")
    app.collar_map_vars["easting"].set("easting")
    app.collar_map_vars["northing"].set("northing")
    app.collar_map_vars["rl"].set("rl")
    app.p1_e.set("100")
    app.p1_n.set("100")
    app.p1_ch.set("0")
    app.p2_e.set("200")
    app.p2_n.set("250")
    app.p2_ch.set("100")
    app.max_offset.set("25")
    app.map_canvas = FakeCanvas()


def test_map_corridor_is_drawn_without_fill(monkeypatch):
    root, app = _build_app(monkeypatch)
    try:
        _configure_map_inputs(app)
        app.show_satellite_basemap.set(False)

        app._redraw_map()

        assert app.map_canvas.polygons
        polygon = app.map_canvas.polygons[0]["kwargs"]
        assert polygon["fill"] == ""
        assert polygon["outline"] == "#ffd54f"
        assert polygon["width"] == 2
    finally:
        root.destroy()
        app._tmp_dir.cleanup()


def test_map_borehole_labels_have_white_backdrop(monkeypatch):
    root, app = _build_app(monkeypatch)
    try:
        _configure_map_inputs(app)
        app.show_satellite_basemap.set(False)

        app._redraw_map()

        assert app.map_canvas.rectangles
        backdrop = app.map_canvas.rectangles[0]["kwargs"]
        assert backdrop["fill"] == "white"
        assert "stipple" not in backdrop
        assert backdrop["outline"] == ""
        borehole_texts = [item for item in app.map_canvas.texts if item["kwargs"].get("text") in {"BH1", "BH2"}]
        assert len(borehole_texts) == 2
    finally:
        root.destroy()
        app._tmp_dir.cleanup()


def test_map_line_endpoints_use_cross_markers_with_requested_colours(monkeypatch):
    root, app = _build_app(monkeypatch)
    try:
        _configure_map_inputs(app)
        app.show_satellite_basemap.set(False)

        app._redraw_map()

        cross_lines = [item for item in app.map_canvas.lines if item["kwargs"].get("width") == 2]
        pink_crosses = [item for item in cross_lines if item["kwargs"].get("fill") == "#FF69B4"]
        purple_crosses = [item for item in cross_lines if item["kwargs"].get("fill") == "#800080"]
        assert len(pink_crosses) == 2
        assert len(purple_crosses) == 2

        endpoint_texts = {
            item["kwargs"].get("text"): item["kwargs"].get("fill")
            for item in app.map_canvas.texts
            if item["kwargs"].get("text") in {"P1", "P2"}
        }
        assert endpoint_texts == {"P1": "#FF69B4", "P2": "#800080"}
    finally:
        root.destroy()
        app._tmp_dir.cleanup()


def test_satellite_map_uses_larger_padded_extent(monkeypatch):
    root, app = _build_app(monkeypatch)
    try:
        _configure_map_inputs(app)
        app.show_satellite_basemap.set(True)
        app.utm_zone.set("56")
        app.utm_hemisphere.set("S")

        captured: dict[str, tuple[float, float, float, float]] = {}

        monkeypatch.setattr(app_module, "transform_points", lambda points, **_kwargs: points)

        def fake_draw_satellite_basemap(*, canvas, extent, transform):
            captured["extent"] = extent
            return None, None

        app._draw_satellite_basemap = fake_draw_satellite_basemap

        app._redraw_map()

        assert captured["extent"] == expand_extent(
            (100.0, 200.0, 100.0, 250.0),
            buffer_ratio=0.20,
            min_abs=1.0,
        )
    finally:
        root.destroy()
        app._tmp_dir.cleanup()
