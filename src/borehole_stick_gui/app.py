from __future__ import annotations

from collections import Counter
import ctypes
import json
from pathlib import Path
import subprocess
import sys
from tkinter import BooleanVar, Canvas, END, Label, StringVar, Tk, Toplevel, colorchooser, filedialog, messagebox
from tkinter import ttk
from typing import Any

import pandas as pd

from .export_bln import write_bln
from .export_postmap_csv import build_category_class_map, write_postmap_csvs
from .export_qa import write_qa_csv
from .export_shp import write_sticks_shapefile
from .export_surfer_autoload import write_surfer_autoload_bat, write_surfer_autoload_script
from .geometry import project_collar_records
from .io_csv import (
    detect_mapping,
    find_duplicate_hole_ids,
    find_missing_category_rows,
    parse_collar,
    read_line_definition_csv,
    parse_lith,
    read_csv,
    split_lith_validity,
)
from .models import LineDefinition, LinePoint
from .map_view import (
    compute_extent,
    corridor_polygon_for_extent,
    expand_extent,
    fit_transform,
    world_to_screen,
)
from .palette import ensure_palette, load_palette_csv, normalize_hex, save_palette_csv
from .sticks import build_stick_polygons


def load_settings_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def validate_run_inputs(
    collar_df: pd.DataFrame,
    lith_df: pd.DataFrame,
    collar_hole_col: str,
    lith_hole_col: str,
    classification_col: str,
    max_offset_m: float,
) -> None:
    if max_offset_m < 0:
        raise ValueError("Max Off-Line Distance (m) must be >= 0.")

    duplicates = find_duplicate_hole_ids(collar_df, collar_hole_col)
    if duplicates:
        sample = ", ".join(duplicates[:8])
        extra = f" (+{len(duplicates) - 8} more)" if len(duplicates) > 8 else ""
        raise ValueError(f"Duplicate collar hole IDs found: {sample}{extra}")

    missing_rows = find_missing_category_rows(lith_df, classification_col)
    if missing_rows:
        sample_rows = ", ".join(str(v) for v in missing_rows[:10])
        extra = f" (+{len(missing_rows) - 10} more)" if len(missing_rows) > 10 else ""
        raise ValueError(
            f"Missing values in classification column '{classification_col}' at CSV rows: {sample_rows}{extra}"
        )

    if lith_hole_col not in lith_df.columns:
        raise ValueError(f"Lithology hole ID column not found in CSV: {lith_hole_col}")

    collar_hole_ids = {
        str(value).strip()
        for value in collar_df[collar_hole_col].fillna("").astype(str).tolist()
        if str(value).strip()
    }
    lith_hole_ids = {
        str(value).strip()
        for value in lith_df[lith_hole_col].fillna("").astype(str).tolist()
        if str(value).strip()
    }
    if collar_hole_ids and lith_hole_ids and not (collar_hole_ids & lith_hole_ids):
        raise ValueError(
            "No matching hole IDs were found between the collar CSV and lithology CSV. "
            "Check the lithology hole_id mapping; it should be the borehole ID column "
            "(for example 'Location ID'), not the classification column."
        )


def count_lith_overlaps(records: list[Any]) -> int:
    by_hole: dict[str, list[Any]] = {}
    for rec in records:
        by_hole.setdefault(rec.hole_id, []).append(rec)

    overlaps = 0
    for hole_records in by_hole.values():
        ordered = sorted(hole_records, key=lambda r: (r.from_depth, r.to_depth))
        prev_to = None
        for item in ordered:
            if prev_to is not None and item.from_depth < prev_to:
                overlaps += 1
            prev_to = item.to_depth if prev_to is None else max(prev_to, item.to_depth)
    return overlaps


class BoreholeStickApp(ttk.Frame):
    def __init__(self, root: Tk) -> None:
        super().__init__(root, padding=10)
        self.root = root
        self.root.title("Borehole Stick Generator")
        self.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._canvas: Canvas | None = None
        self._vscroll: ttk.Scrollbar | None = None
        self._content: ttk.Frame | None = None
        self._canvas_window_id = -1
        self._main_split: ttk.Frame | None = None
        self.map_canvas: Canvas | None = None
        self._map_after_id: str | None = None
        self._map_padding_px = 20
        self._map_buffer_ratio = 0.05
        self._line_entries: list[ttk.Entry] = []
        self._max_offset_entry: ttk.Entry | None = None

        self.collar_df: pd.DataFrame | None = None
        self.lith_df: pd.DataFrame | None = None
        self.survey_df: pd.DataFrame | None = None

        self.collar_path = StringVar()
        self.lith_path = StringVar()
        self.survey_path = StringVar()
        self.output_dir = StringVar(value=str(Path.cwd()))
        self.output_base = StringVar(value="borehole_sticks")

        self.p1_e = StringVar(value="0")
        self.p1_n = StringVar(value="0")
        self.p1_ch = StringVar(value="0")
        self.p2_e = StringVar(value="100")
        self.p2_n = StringVar(value="0")
        self.p2_ch = StringVar(value="100")

        self.max_offset = StringVar(value="25")
        self.rect_width = StringVar(value="2")
        self.reverse_chainage = BooleanVar(value=False)
        self.smart_label_filter_enabled = BooleanVar(value=True)
        self.min_label_length_m = StringVar(value="1.0")
        self.thin_filter_enabled = BooleanVar(value=True)
        self.merge_adjacent_enabled = BooleanVar(value=True)
        self.thin_min_abs_m = StringVar(value="0.3")
        self.thin_relative_to_median = StringVar(value="0.2")
        self.adjacent_gap_tolerance_m = StringVar(value="0.05")

        self.category_field = StringVar()
        self.palette: dict[str, str] = {}

        self.collar_map_vars: dict[str, StringVar] = {}
        self.lith_map_vars: dict[str, StringVar] = {}
        self.category_list: ttk.Treeview | None = None
        self.log_box: ttk.Treeview | None = None
        self._label_filter_widgets: list[ttk.Widget] = []

        self.settings_path = Path.home() / ".borehole_stick_gui_settings.json"
        self._saved_collar_mapping: dict[str, str] = {}
        self._saved_lith_mapping: dict[str, str] = {}
        self._load_settings()

        self._init_scroll_container()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._autoload_recent_files()

    def _init_scroll_container(self) -> None:
        self._main_split = ttk.Frame(self)
        self._main_split.grid(row=0, column=0, sticky="nsew")
        self._main_split.columnconfigure(0, weight=3)
        self._main_split.columnconfigure(1, weight=2)
        self._main_split.rowconfigure(0, weight=1)

        left_host = ttk.Frame(self._main_split)
        left_host.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_host.columnconfigure(0, weight=1)
        left_host.rowconfigure(0, weight=1)

        self._canvas = Canvas(left_host, highlightthickness=0)
        self._vscroll = ttk.Scrollbar(left_host, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vscroll.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vscroll.grid(row=0, column=1, sticky="ns")

        self._content = ttk.Frame(self._canvas)
        self._canvas_window_id = self._canvas.create_window((0, 0), window=self._content, anchor="nw")
        self._content.columnconfigure(0, weight=1)

        self._content.bind("<Configure>", self._on_content_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._content.bind("<Enter>", self._bind_mousewheel)
        self._content.bind("<Leave>", self._unbind_mousewheel)

        map_frame = ttk.LabelFrame(self._main_split, text="Map View")
        map_frame.grid(row=0, column=1, sticky="nsew")
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        self.map_canvas = Canvas(map_frame, bg="white", highlightthickness=1)
        self.map_canvas.grid(row=0, column=0, sticky="nsew")
        self.map_canvas.bind("<Configure>", self._on_map_canvas_configure)

    def _on_content_configure(self, _event=None) -> None:
        if self._canvas is None:
            return
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        if self._canvas is None:
            return
        self._canvas.itemconfigure(self._canvas_window_id, width=event.width)

    def _on_map_canvas_configure(self, _event=None) -> None:
        self._schedule_map_redraw()

    def _bind_mousewheel(self, _event=None) -> None:
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None) -> None:
        self.root.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event) -> None:
        if self._canvas is None:
            return
        delta = int(-1 * (event.delta / 120))
        if delta != 0:
            self._canvas.yview_scroll(delta, "units")

    def _load_settings(self) -> None:
        data = load_settings_file(self.settings_path)
        if not data:
            return
        for key, var in [
            ("collar_path", self.collar_path),
            ("lith_path", self.lith_path),
            ("survey_path", self.survey_path),
            ("output_dir", self.output_dir),
            ("output_base", self.output_base),
            ("p1_e", self.p1_e),
            ("p1_n", self.p1_n),
            ("p1_ch", self.p1_ch),
            ("p2_e", self.p2_e),
            ("p2_n", self.p2_n),
            ("p2_ch", self.p2_ch),
            ("max_offset", self.max_offset),
            ("rect_width", self.rect_width),
            ("category_field", self.category_field),
            ("min_label_length_m", self.min_label_length_m),
            ("thin_min_abs_m", self.thin_min_abs_m),
            ("thin_relative_to_median", self.thin_relative_to_median),
            ("adjacent_gap_tolerance_m", self.adjacent_gap_tolerance_m),
        ]:
            value = data.get(key)
            if isinstance(value, str):
                var.set(value)
        self.reverse_chainage.set(bool(data.get("reverse_chainage", False)))
        self.smart_label_filter_enabled.set(bool(data.get("smart_label_filter_enabled", True)))
        self.thin_filter_enabled.set(bool(data.get("thin_filter_enabled", True)))
        self.merge_adjacent_enabled.set(bool(data.get("merge_adjacent_enabled", True)))

        palette = data.get("palette")
        if isinstance(palette, dict):
            self.palette = {str(k): normalize_hex(str(v)) for k, v in palette.items()}
        self._saved_collar_mapping = {
            str(k): str(v) for k, v in data.get("collar_mapping", {}).items()
        }
        self._saved_lith_mapping = {str(k): str(v) for k, v in data.get("lith_mapping", {}).items()}

    def _settings_payload(self) -> dict[str, Any]:
        return {
            "collar_path": self.collar_path.get(),
            "lith_path": self.lith_path.get(),
            "survey_path": self.survey_path.get(),
            "output_dir": self.output_dir.get(),
            "output_base": self.output_base.get(),
            "p1_e": self.p1_e.get(),
            "p1_n": self.p1_n.get(),
            "p1_ch": self.p1_ch.get(),
            "p2_e": self.p2_e.get(),
            "p2_n": self.p2_n.get(),
            "p2_ch": self.p2_ch.get(),
            "max_offset": self.max_offset.get(),
            "rect_width": self.rect_width.get(),
            "category_field": self.category_field.get(),
            "reverse_chainage": bool(self.reverse_chainage.get()),
            "smart_label_filter_enabled": bool(self.smart_label_filter_enabled.get()),
            "min_label_length_m": self.min_label_length_m.get(),
            "thin_filter_enabled": bool(self.thin_filter_enabled.get()),
            "merge_adjacent_enabled": bool(self.merge_adjacent_enabled.get()),
            "thin_min_abs_m": self.thin_min_abs_m.get(),
            "thin_relative_to_median": self.thin_relative_to_median.get(),
            "adjacent_gap_tolerance_m": self.adjacent_gap_tolerance_m.get(),
            "palette": self.palette,
            "collar_mapping": {key: var.get() for key, var in self.collar_map_vars.items()},
            "lith_mapping": {key: var.get() for key, var in self.lith_map_vars.items()},
        }

    def _save_settings(self) -> None:
        try:
            save_settings_file(self.settings_path, self._settings_payload())
        except Exception as exc:
            self._log(f"Warning: Could not save settings: {exc}")

    def _on_close(self) -> None:
        self._save_settings()
        self.root.destroy()

    def _reset_settings(self) -> None:
        confirm = messagebox.askyesno(
            "Reset Settings",
            "Clear saved settings and reset fields to defaults?",
        )
        if not confirm:
            return

        self.collar_df = None
        self.lith_df = None
        self.survey_df = None
        self.collar_path.set("")
        self.lith_path.set("")
        self.survey_path.set("")
        self.output_dir.set(str(Path.cwd()))
        self.output_base.set("borehole_sticks")
        self.p1_e.set("0")
        self.p1_n.set("0")
        self.p1_ch.set("0")
        self.p2_e.set("100")
        self.p2_n.set("0")
        self.p2_ch.set("100")
        self.max_offset.set("25")
        self.rect_width.set("2")
        self.reverse_chainage.set(False)
        self.smart_label_filter_enabled.set(True)
        self.min_label_length_m.set("1.0")
        self.thin_filter_enabled.set(True)
        self.merge_adjacent_enabled.set(True)
        self.thin_min_abs_m.set("0.3")
        self.thin_relative_to_median.set("0.2")
        self.adjacent_gap_tolerance_m.set("0.05")
        self.category_field.set("")
        self.palette = {}
        self._saved_collar_mapping = {}
        self._saved_lith_mapping = {}

        for var in self.collar_map_vars.values():
            var.set("")
        for var in self.lith_map_vars.values():
            var.set("")
        self.category_combo["values"] = []
        if self.category_list is not None:
            self.category_list.delete(*self.category_list.get_children())
        if self.log_box is not None:
            self.log_box.delete(*self.log_box.get_children())

        if self.settings_path.exists():
            try:
                self.settings_path.unlink()
            except Exception as exc:
                messagebox.showwarning("Reset Settings", f"Could not remove settings file: {exc}")
                return
        self._apply_label_filter_widget_state()
        self._log("Settings reset to defaults.")
        self._schedule_map_redraw()

    def _autoload_recent_files(self) -> None:
        if self.collar_path.get().strip():
            path = Path(self.collar_path.get().strip())
            if path.exists():
                self._load_collar_path(path)
        if self.lith_path.get().strip():
            path = Path(self.lith_path.get().strip())
            if path.exists():
                self._load_lith_path(path)
        if self.survey_path.get().strip():
            path = Path(self.survey_path.get().strip())
            if path.exists():
                self._load_survey_path(path)
        self._schedule_map_redraw()

    def _build_ui(self) -> None:
        if self._content is None:
            raise RuntimeError("Scroll content frame is not initialized.")
        container = self._content

        files_frame = ttk.LabelFrame(container, text="Input Files")
        files_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        files_frame.columnconfigure(1, weight=1)

        self._file_row(files_frame, 0, "Collar CSV", self.collar_path, self._load_collar)
        self._file_row(files_frame, 1, "Lithology CSV", self.lith_path, self._load_lith)
        self._file_row(
            files_frame,
            2,
            "Survey CSV (reserved, currently unused)",
            self.survey_path,
            self._load_survey,
        )

        line_frame = ttk.LabelFrame(container, text="Survey Line Definition")
        line_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        for idx in range(6):
            line_frame.columnconfigure(idx, weight=1)
        labels = ["P1 Easting", "P1 Northing", "P1 Chainage", "P2 Easting", "P2 Northing", "P2 Chainage"]
        vars_ = [self.p1_e, self.p1_n, self.p1_ch, self.p2_e, self.p2_n, self.p2_ch]
        for col, (label, var) in enumerate(zip(labels, vars_)):
            ttk.Label(line_frame, text=label).grid(row=0, column=col, sticky="w")
            entry = ttk.Entry(line_frame, textvariable=var, width=14)
            entry.grid(row=1, column=col, sticky="ew", padx=1)
            entry.bind("<FocusOut>", lambda _e: self._schedule_map_redraw())
            entry.bind("<Return>", lambda _e: self._schedule_map_redraw())
            self._line_entries.append(entry)
        ttk.Button(line_frame, text="Load Line CSV", command=self._load_line_csv).grid(
            row=2, column=0, columnspan=6, sticky="e", pady=(4, 0)
        )
        reverse_chainage_check = ttk.Checkbutton(
            line_frame,
            text="Reverse profile chainage in Surfer",
            variable=self.reverse_chainage,
            command=self._save_settings,
        )
        reverse_chainage_check.grid(row=3, column=0, columnspan=6, sticky="w", pady=(6, 0))
        ttk.Label(
            line_frame,
            text="Use for sections that should read right-to-left on the Surfer profile.",
        ).grid(row=4, column=0, columnspan=6, sticky="w", pady=(2, 0))

        options_frame = ttk.LabelFrame(container, text="Options")
        options_frame.grid(row=2, column=0, sticky="ew", padx=2, pady=2)
        options_frame.columnconfigure(0, weight=1)
        options_frame.columnconfigure(1, weight=1)

        basic_frame = ttk.LabelFrame(options_frame, text="Basic")
        basic_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        basic_frame.columnconfigure(1, weight=1)
        ttk.Label(basic_frame, text="Max Off-Line Distance (m)").grid(row=0, column=0, sticky="w")
        self._max_offset_entry = ttk.Entry(basic_frame, textvariable=self.max_offset, width=14)
        self._max_offset_entry.grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )
        self._max_offset_entry.bind("<FocusOut>", lambda _e: self._schedule_map_redraw())
        self._max_offset_entry.bind("<Return>", lambda _e: self._schedule_map_redraw())
        ttk.Label(basic_frame, text="Stick Width (m)").grid(row=1, column=0, sticky="w")
        ttk.Entry(basic_frame, textvariable=self.rect_width, width=14).grid(
            row=1, column=1, sticky="w", padx=(8, 0)
        )
        ttk.Label(basic_frame, text="Classification Column").grid(row=2, column=0, sticky="w")
        self.category_combo = ttk.Combobox(
            basic_frame, textvariable=self.category_field, state="readonly", width=28
        )
        self.category_combo.grid(row=2, column=1, sticky="ew", padx=(8, 0))
        self.category_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_palette_view())

        filter_frame = ttk.LabelFrame(options_frame, text="Label Filtering")
        filter_frame.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        filter_frame.columnconfigure(0, weight=1)
        filter_frame.columnconfigure(1, weight=1)

        smart_filter_check = ttk.Checkbutton(
            filter_frame,
            text="Smart label filter (major units + spacing)",
            variable=self.smart_label_filter_enabled,
            command=self._on_smart_filter_toggle,
        )
        smart_filter_check.grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(filter_frame, text="Minimum label length (m)").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        min_label_len_entry = ttk.Entry(filter_frame, textvariable=self.min_label_length_m, width=12)
        min_label_len_entry.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(4, 0))
        min_label_len_entry.bind("<FocusOut>", lambda _e: self._save_settings())

        thin_filter_check = ttk.Checkbutton(
            filter_frame,
            text="Thin-unit suppression",
            variable=self.thin_filter_enabled,
            command=self._save_settings,
        )
        thin_filter_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(filter_frame, text="Thin min abs (m)").grid(row=3, column=0, sticky="w")
        thin_abs_entry = ttk.Entry(filter_frame, textvariable=self.thin_min_abs_m, width=12)
        thin_abs_entry.grid(row=3, column=1, sticky="w", padx=(8, 0))
        thin_abs_entry.bind("<FocusOut>", lambda _e: self._save_settings())

        ttk.Label(filter_frame, text="Thin relative factor").grid(row=4, column=0, sticky="w")
        thin_rel_entry = ttk.Entry(filter_frame, textvariable=self.thin_relative_to_median, width=12)
        thin_rel_entry.grid(row=4, column=1, sticky="w", padx=(8, 0))
        thin_rel_entry.bind("<FocusOut>", lambda _e: self._save_settings())

        merge_adjacent_check = ttk.Checkbutton(
            filter_frame,
            text="Merge adjacent same-category units",
            variable=self.merge_adjacent_enabled,
            command=self._save_settings,
        )
        merge_adjacent_check.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(filter_frame, text="Adj. gap tolerance (m)").grid(row=6, column=0, sticky="w")
        adj_gap_entry = ttk.Entry(filter_frame, textvariable=self.adjacent_gap_tolerance_m, width=12)
        adj_gap_entry.grid(row=6, column=1, sticky="w", padx=(8, 0))
        adj_gap_entry.bind("<FocusOut>", lambda _e: self._save_settings())
        self._label_filter_widgets = [
            min_label_len_entry,
            thin_filter_check,
            thin_abs_entry,
            thin_rel_entry,
            merge_adjacent_check,
            adj_gap_entry,
        ]
        self._apply_label_filter_widget_state()

        output_frame = ttk.LabelFrame(container, text="Output")
        output_frame.grid(row=3, column=0, sticky="ew", padx=2, pady=2)
        output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="Output Folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(output_frame, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew")
        ttk.Button(output_frame, text="Browse", command=self._pick_output_dir).grid(row=0, column=2, padx=2)
        ttk.Label(output_frame, text="File Base Name").grid(row=1, column=0, sticky="w")
        ttk.Entry(output_frame, textvariable=self.output_base).grid(row=1, column=1, sticky="ew")

        mapping_frame = ttk.LabelFrame(container, text="Column Mapping")
        mapping_frame.grid(row=4, column=0, sticky="ew", padx=2, pady=2)
        mapping_frame.columnconfigure(1, weight=1)
        mapping_frame.columnconfigure(3, weight=1)
        self._mapping_controls(mapping_frame)

        palette_frame = ttk.LabelFrame(container, text="Palette")
        palette_frame.grid(row=5, column=0, sticky="nsew", padx=2, pady=2)
        palette_frame.columnconfigure(0, weight=1)
        palette_frame.rowconfigure(0, weight=1)
        container.rowconfigure(5, weight=1)

        self.category_list = ttk.Treeview(palette_frame, columns=("category", "color"), show="headings", height=10)
        self.category_list.heading("category", text="Category")
        self.category_list.heading("color", text="Color")
        self.category_list.column("category", width=320)
        self.category_list.column("color", width=180)
        self.category_list.grid(row=0, column=0, sticky="nsew")
        palette_btns = ttk.Frame(palette_frame)
        palette_btns.grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Button(palette_btns, text="Set Color", command=self._set_selected_color).pack(side="left", padx=2)
        ttk.Button(palette_btns, text="Load Palette CSV", command=self._load_palette).pack(side="left", padx=2)
        ttk.Button(palette_btns, text="Save Palette CSV", command=self._save_palette).pack(side="left", padx=2)

        run_frame = ttk.Frame(container)
        run_frame.grid(row=6, column=0, sticky="ew", padx=2, pady=6)
        ttk.Button(run_frame, text="Generate Outputs", command=self._run).pack(side="left")
        ttk.Button(run_frame, text="Reset Settings", command=self._reset_settings).pack(side="left", padx=6)

        log_frame = ttk.LabelFrame(container, text="Messages")
        log_frame.grid(row=7, column=0, sticky="nsew", padx=2, pady=2)
        container.rowconfigure(7, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_box = ttk.Treeview(log_frame, columns=("message",), show="headings", height=6)
        self.log_box.heading("message", text="Message")
        self.log_box.column("message", width=800)
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self._schedule_map_redraw()

    def _mapping_controls(self, parent: ttk.LabelFrame) -> None:
        ttk.Label(parent, text="Collar fields").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text="Lith fields").grid(row=0, column=2, sticky="w")

        collar_fields = ["hole_id", "easting", "northing", "rl"]
        lith_fields = ["hole_id", "from_depth", "to_depth"]
        for idx, field in enumerate(collar_fields, start=1):
            ttk.Label(parent, text=field).grid(row=idx, column=0, sticky="w")
            var = StringVar()
            self.collar_map_vars[field] = var
            combo = ttk.Combobox(parent, textvariable=var, state="readonly")
            combo.grid(row=idx, column=1, sticky="ew")
            combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_map_redraw())
        for idx, field in enumerate(lith_fields, start=1):
            ttk.Label(parent, text=field).grid(row=idx, column=2, sticky="w")
            var = StringVar()
            self.lith_map_vars[field] = var
            combo = ttk.Combobox(parent, textvariable=var, state="readonly")
            combo.grid(row=idx, column=3, sticky="ew")
            combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_map_redraw())

    def _file_row(self, parent: ttk.Frame, row: int, label: str, var: StringVar, cb) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew")
        ttk.Button(parent, text="Load", command=cb).grid(row=row, column=2, padx=2)

    def _pick_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)
            self._save_settings()

    def _on_smart_filter_toggle(self) -> None:
        self._apply_label_filter_widget_state()
        self._save_settings()

    def _apply_label_filter_widget_state(self) -> None:
        state = "normal" if self.smart_label_filter_enabled.get() else "disabled"
        for widget in self._label_filter_widgets:
            try:
                widget.configure(state=state)
            except Exception:
                continue

    def _load_collar_path(self, path: str | Path) -> None:
        self.collar_df = read_csv(path)
        self.collar_path.set(str(path))
        self._bind_mapping_options(self.collar_map_vars, list(self.collar_df.columns))
        result = detect_mapping(self.collar_df.columns, self.collar_map_vars.keys())
        for field, column in result.mapping.items():
            self.collar_map_vars[field].set(column)
        applied_saved = False
        for field, column in self._saved_collar_mapping.items():
            if field in self.collar_map_vars and column in self.collar_df.columns:
                self.collar_map_vars[field].set(column)
                applied_saved = True
        if applied_saved:
            try:
                parse_collar(
                    self.collar_df,
                    {
                        "hole_id": self.collar_map_vars["hole_id"].get(),
                        "easting": self.collar_map_vars["easting"].get(),
                        "northing": self.collar_map_vars["northing"].get(),
                        "rl": self.collar_map_vars["rl"].get(),
                    },
                )
            except Exception:
                # Saved mapping may come from a different collar schema; revert to detected mapping.
                for field, column in result.mapping.items():
                    self.collar_map_vars[field].set(column)
                self._log("Saved collar mapping was invalid for this file; reverted to auto-detected mapping.")
        self._log(f"Loaded collar CSV with {len(self.collar_df)} rows.")
        self._schedule_map_redraw()

    def _load_lith_path(self, path: str | Path) -> None:
        self.lith_df = read_csv(path)
        self.lith_path.set(str(path))
        self._bind_mapping_options(self.lith_map_vars, list(self.lith_df.columns))
        result = detect_mapping(self.lith_df.columns, self.lith_map_vars.keys())
        for field, column in result.mapping.items():
            self.lith_map_vars[field].set(column)
        for field, column in self._saved_lith_mapping.items():
            if field in self.lith_map_vars and column in self.lith_df.columns:
                self.lith_map_vars[field].set(column)
        self.category_combo["values"] = list(self.lith_df.columns)
        if self.category_field.get() and self.category_field.get() in self.lith_df.columns:
            self.category_field.set(self.category_field.get())
        elif self.lith_df.columns.size > 0:
            self.category_field.set(str(self.lith_df.columns[0]))
        self._refresh_palette_view()
        self._log(f"Loaded lithology CSV with {len(self.lith_df)} rows.")

    def _load_survey_path(self, path: str | Path) -> None:
        self.survey_df = read_csv(path)
        self.survey_path.set(str(path))
        self._log(
            f"Loaded survey CSV with {len(self.survey_df)} rows (reserved; currently ignored in processing)."
        )

    def _load_collar(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        self._load_collar_path(path)
        self._save_settings()

    def _load_lith(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        self._load_lith_path(path)
        self._save_settings()

    def _load_survey(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        self._load_survey_path(path)
        self._save_settings()

    def _load_line_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            line = read_line_definition_csv(path)
            self.p1_e.set(f"{line.p1.easting:g}")
            self.p1_n.set(f"{line.p1.northing:g}")
            self.p1_ch.set(f"{line.p1.chainage:g}")
            self.p2_e.set(f"{line.p2.easting:g}")
            self.p2_n.set(f"{line.p2.northing:g}")
            self.p2_ch.set(f"{line.p2.chainage:g}")
            self._log(f"Loaded line definition from {path}.")
            self._save_settings()
            self._schedule_map_redraw()
        except Exception as exc:
            messagebox.showerror("Line CSV error", str(exc))

    def _bind_mapping_options(self, map_vars: dict[str, StringVar], columns: list[str]) -> None:
        combos = [w for w in self.winfo_children_recursive() if isinstance(w, ttk.Combobox)]
        for combo in combos:
            linked = combo.cget("textvariable")
            for var in map_vars.values():
                if str(var) == linked:
                    combo["values"] = columns

    def winfo_children_recursive(self):
        stack = list(self.winfo_children())
        while stack:
            node = stack.pop()
            yield node
            stack.extend(node.winfo_children())

    def _get_mapping(self, map_vars: dict[str, StringVar], required: list[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        missing = []
        for field in required:
            val = map_vars[field].get().strip()
            if not val:
                missing.append(field)
            else:
                mapping[field] = val
        if missing:
            raise ValueError(f"Missing mapping selection for: {', '.join(missing)}")
        return mapping

    def _line_definition(self) -> LineDefinition:
        return LineDefinition(
            p1=LinePoint(float(self.p1_e.get()), float(self.p1_n.get()), float(self.p1_ch.get())),
            p2=LinePoint(float(self.p2_e.get()), float(self.p2_n.get()), float(self.p2_ch.get())),
        )

    def _refresh_palette_view(self) -> None:
        if self.category_list is None:
            return
        self.category_list.delete(*self.category_list.get_children())
        if self.lith_df is None or not self.category_field.get():
            return
        cat_col = self.category_field.get()
        if cat_col not in self.lith_df.columns:
            return
        categories = self.lith_df[cat_col].fillna("").astype(str).str.strip()
        categories = categories[categories != ""].unique().tolist()
        self.palette = ensure_palette(categories, self.palette)
        for cat in sorted(categories):
            color = self.palette.get(cat, "#808080")
            tag = f"swatch_{color.replace('#', '')}"
            try:
                self.category_list.tag_configure(tag, background=color)
            except Exception:
                pass
            self.category_list.insert("", END, values=(cat, color), tags=(tag,))

    def _validate_hex_color(self, value: str) -> str | None:
        text = str(value).strip()
        if text.startswith("#"):
            text = text[1:]
        if len(text) not in (3, 6):
            return None
        if not all(ch in "0123456789abcdefABCDEF" for ch in text):
            return None
        return normalize_hex(text)

    def _sample_screen_color_windows(self, x: int, y: int) -> str | None:
        if not sys.platform.startswith("win"):
            return None
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            hdc = user32.GetDC(0)
            if hdc == 0:
                return None
            pixel = gdi32.GetPixel(hdc, int(x), int(y))
            user32.ReleaseDC(0, hdc)
            if pixel == -1:
                return None
            red = pixel & 0xFF
            green = (pixel >> 8) & 0xFF
            blue = (pixel >> 16) & 0xFF
            return f"#{red:02X}{green:02X}{blue:02X}"
        except Exception:
            return None

    def _pick_color_from_screen(self) -> str | None:
        if not sys.platform.startswith("win"):
            messagebox.showinfo(
                "Screen Picker Unavailable",
                "Screen color sampling is currently available on Windows only.",
            )
            return None

        result: dict[str, str | None] = {"hex": None}
        overlay: Toplevel | None = None
        try:
            overlay = Toplevel(self.root)
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            overlay.geometry(f"{screen_w}x{screen_h}+0+0")
            overlay.overrideredirect(True)
            overlay.attributes("-alpha", 0.01)
            overlay.attributes("-topmost", True)
            overlay.configure(cursor="crosshair", bg="black")

            def on_click(event) -> None:
                overlay.withdraw()
                overlay.update_idletasks()
                sampled = self._sample_screen_color_windows(event.x_root, event.y_root)
                result["hex"] = sampled
                overlay.destroy()

            def on_cancel(_event=None) -> None:
                overlay.destroy()

            overlay.bind("<Button-1>", on_click)
            overlay.bind("<Escape>", on_cancel)
            overlay.focus_force()
            overlay.grab_set()
            overlay.wait_window()
        except Exception as exc:
            messagebox.showwarning("Screen Picker", f"Could not pick screen color: {exc}")
        finally:
            try:
                if overlay is not None and overlay.winfo_exists():
                    overlay.destroy()
            except Exception:
                pass
        return result["hex"]

    def _open_color_editor_dialog(self, category: str, initial_hex: str) -> str | None:
        dialog = Toplevel(self.root)
        dialog.title(f"Edit Color: {category}")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.columnconfigure(1, weight=1)

        color_var = StringVar(value=normalize_hex(initial_hex))
        result: dict[str, str | None] = {"hex": None}

        ttk.Label(dialog, text="Color code (#RRGGBB)").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        entry = ttk.Entry(dialog, textvariable=color_var, width=18)
        entry.grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 4))

        ttk.Label(dialog, text="Preview").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        preview = Label(dialog, text="        ")
        preview.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        def update_preview() -> None:
            parsed = self._validate_hex_color(color_var.get())
            try:
                preview.configure(background=parsed or "#808080")
            except Exception:
                pass

        def on_native_picker() -> None:
            parsed = self._validate_hex_color(color_var.get()) or "#808080"
            _, chosen = colorchooser.askcolor(color=parsed, title=f"Pick color for {category}")
            if chosen:
                color_var.set(chosen.upper())
                update_preview()

        def on_screen_pick() -> None:
            dialog.withdraw()
            self.root.withdraw()
            self.root.update_idletasks()
            chosen = self._pick_color_from_screen()
            self.root.deiconify()
            dialog.deiconify()
            dialog.lift()
            dialog.focus_force()
            if chosen:
                color_var.set(chosen)
                update_preview()

        def on_apply() -> None:
            parsed = self._validate_hex_color(color_var.get())
            if not parsed:
                messagebox.showerror("Invalid Color", "Enter a valid hex color like #FF8800.", parent=dialog)
                return
            result["hex"] = parsed
            dialog.destroy()

        def on_cancel() -> None:
            dialog.destroy()

        button_row = ttk.Frame(dialog)
        button_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 8))
        ttk.Button(button_row, text="Pick from Screen", command=on_screen_pick).pack(side="left", padx=(0, 4))
        ttk.Button(button_row, text="Native Picker...", command=on_native_picker).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Apply", command=on_apply).pack(side="right", padx=(4, 0))
        ttk.Button(button_row, text="Cancel", command=on_cancel).pack(side="right")

        entry.bind("<KeyRelease>", lambda _e: update_preview())
        entry.bind("<Return>", lambda _e: on_apply())
        dialog.bind("<Escape>", lambda _e: on_cancel())
        update_preview()
        entry.focus_set()
        dialog.wait_window()
        return result["hex"]

    def _set_selected_color(self) -> None:
        if self.category_list is None:
            return
        selected = self.category_list.selection()
        if not selected:
            messagebox.showinfo("No selection", "Select a category row first.")
            return
        item = self.category_list.item(selected[0])
        category = str(item["values"][0])
        initial = self.palette.get(category, "#808080")
        chosen = self._open_color_editor_dialog(category=category, initial_hex=initial)
        if not chosen:
            return
        self.palette[category] = normalize_hex(chosen)
        self._refresh_palette_view()
        self._save_settings()

    def _load_palette(self) -> None:
        if not self.category_field.get():
            messagebox.showerror("Missing classification", "Select a classification column first.")
            return
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        loaded = load_palette_csv(path, self.category_field.get())
        self.palette.update(loaded)
        self._refresh_palette_view()
        self._log(f"Loaded {len(loaded)} palette entries from {path}.")
        self._save_settings()

    def _save_palette(self) -> None:
        if not self.category_field.get():
            messagebox.showerror("Missing classification", "Select a classification column first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{self.output_base.get()}_palette.csv",
        )
        if not path:
            return
        save_palette_csv(path, self.category_field.get(), self.palette)
        self._log(f"Saved palette to {path}.")
        self._save_settings()

    def _log(self, message: str) -> None:
        if self.log_box is not None:
            self.log_box.insert("", END, values=(message,))
            self.log_box.see(self.log_box.get_children()[-1])

    def _schedule_map_redraw(self) -> None:
        if self.map_canvas is None:
            return
        if self._map_after_id is not None:
            try:
                self.root.after_cancel(self._map_after_id)
            except Exception:
                pass
        self._map_after_id = self.root.after(60, self._redraw_map)

    def _collect_map_features(self) -> tuple[list[Any], LineDefinition | None, float | None, str | None]:
        collars: list[Any] = []
        line: LineDefinition | None = None
        max_offset: float | None = None
        status: str | None = None

        if self.collar_df is not None:
            try:
                collar_mapping = self._get_mapping(self.collar_map_vars, ["hole_id", "easting", "northing", "rl"])
                collars = parse_collar(self.collar_df, collar_mapping)
            except Exception as exc:
                status = f"Collar mapping/data issue: {exc}"

        try:
            line = self._line_definition()
        except Exception:
            status = status or "Enter valid numeric P1/P2 values to show the line."

        try:
            max_offset = float(self.max_offset.get())
            if max_offset < 0:
                status = status or "Max Off-Line Distance must be >= 0."
                max_offset = None
        except Exception:
            status = status or "Enter a valid numeric Max Off-Line Distance."

        if not collars and status is None:
            status = "Load collar CSV to view boreholes."
        return collars, line, max_offset, status

    def _redraw_map(self) -> None:
        self._map_after_id = None
        if self.map_canvas is None:
            return

        canvas = self.map_canvas
        canvas.delete("all")
        w = max(1, int(canvas.winfo_width()))
        h = max(1, int(canvas.winfo_height()))
        if w < 40 or h < 40:
            return

        collars, line, max_offset, status = self._collect_map_features()
        points: list[tuple[float, float]] = []
        points.extend((float(c.easting), float(c.northing)) for c in collars)
        if line is not None:
            points.append((line.p1.easting, line.p1.northing))
            points.append((line.p2.easting, line.p2.northing))

        if not points:
            canvas.create_text(
                w / 2,
                h / 2,
                text=status or "No map data available.",
                fill="#444444",
                anchor="center",
            )
            return

        extent = expand_extent(
            compute_extent(points),
            buffer_ratio=self._map_buffer_ratio,
            min_abs=1.0,
        )
        transform = fit_transform(extent, w, h, padding_px=self._map_padding_px)

        projected = []
        included_ids: set[str] = set()
        excluded_ids: set[str] = set()
        if collars and line is not None and max_offset is not None:
            try:
                projected = project_collar_records(collars, line, max_offset)
                included_ids = {p.hole_id for p in projected if p.included}
                excluded_ids = {p.hole_id for p in projected if not p.included}
            except Exception:
                pass

        if line is not None and max_offset is not None and max_offset > 0:
            corridor = corridor_polygon_for_extent(
                (line.p1.easting, line.p1.northing),
                (line.p2.easting, line.p2.northing),
                max_offset=max_offset,
                extent=extent,
            )
            if corridor:
                coords: list[float] = []
                for x, y in corridor:
                    sx, sy = world_to_screen(x, y, transform)
                    coords.extend([sx, sy])
                canvas.create_polygon(
                    coords,
                    fill="#9ecae1",
                    outline="#4292c6",
                    stipple="gray25",
                    width=1,
                )

        if line is not None:
            p1s = world_to_screen(line.p1.easting, line.p1.northing, transform)
            p2s = world_to_screen(line.p2.easting, line.p2.northing, transform)
            canvas.create_line(*p1s, *p2s, fill="#1f77b4", width=2)

            for label, pt, color in [
                ("P1", line.p1, "#d62728"),
                ("P2", line.p2, "#2ca02c"),
            ]:
                sx, sy = world_to_screen(pt.easting, pt.northing, transform)
                canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=color, outline=color)
                canvas.create_text(sx + 8, sy - 8, text=label, anchor="w", fill=color, font=("Segoe UI", 9, "bold"))

        for collar in collars:
            sx, sy = world_to_screen(float(collar.easting), float(collar.northing), transform)
            if collar.hole_id in included_ids:
                pt_fill, pt_outline = "#2ca02c", "#1b7f3a"
            elif collar.hole_id in excluded_ids:
                pt_fill, pt_outline = "#d95f5f", "#b22222"
            else:
                pt_fill, pt_outline = "#2b2b2b", "#2b2b2b"
            canvas.create_oval(sx - 3, sy - 3, sx + 3, sy + 3, fill=pt_fill, outline=pt_outline)
            canvas.create_text(
                sx + 6,
                sy - 6,
                text=str(collar.hole_id),
                anchor="w",
                fill="#222222",
                font=("Segoe UI", 8),
            )

        legend = f"Collars: {len(collars)}"
        if projected:
            legend += f"  Included: {len(included_ids)}  Excluded: {len(excluded_ids)}"
        if max_offset is not None:
            legend += f"  Max offset: {max_offset:g} m"
        canvas.create_text(8, 8, text=legend, anchor="nw", fill="#1f1f1f", font=("Segoe UI", 9, "bold"))

        if status:
            canvas.create_text(8, h - 8, text=status, anchor="sw", fill="#555555", font=("Segoe UI", 8))

    def _run(self) -> None:
        try:
            if self.collar_df is None or self.lith_df is None:
                raise ValueError("Load collar and lithology CSV files.")
            category_field = self.category_field.get().strip()
            if not category_field:
                raise ValueError("Select a classification column.")
            if category_field not in self.lith_df.columns:
                raise ValueError("Selected classification column is not in lithology CSV.")
            thin_min_abs_m = float(self.thin_min_abs_m.get())
            thin_relative_to_median = float(self.thin_relative_to_median.get())
            adjacent_gap_tolerance_m = float(self.adjacent_gap_tolerance_m.get())
            min_label_length_m = float(self.min_label_length_m.get())
            max_offset_m = float(self.max_offset.get())
            if thin_min_abs_m < 0:
                raise ValueError("Thin min abs (m) must be >= 0.")
            if thin_relative_to_median < 0:
                raise ValueError("Thin relative factor must be >= 0.")
            if adjacent_gap_tolerance_m < 0:
                raise ValueError("Adjacent gap tolerance (m) must be >= 0.")
            if min_label_length_m < 0:
                raise ValueError("Minimum label length (m) must be >= 0.")

            collar_mapping = self._get_mapping(
                self.collar_map_vars, ["hole_id", "easting", "northing", "rl"]
            )
            lith_mapping = self._get_mapping(self.lith_map_vars, ["hole_id", "from_depth", "to_depth"])
            lith_mapping[category_field] = category_field
            validate_run_inputs(
                collar_df=self.collar_df,
                lith_df=self.lith_df,
                collar_hole_col=collar_mapping["hole_id"],
                lith_hole_col=lith_mapping["hole_id"],
                classification_col=category_field,
                max_offset_m=max_offset_m,
            )

            collars = parse_collar(self.collar_df, collar_mapping)
            all_lith = parse_lith(self.lith_df, lith_mapping, category_field)
            valid_lith, invalid_lith = split_lith_validity(all_lith)

            line = self._line_definition()
            projected = project_collar_records(collars, line, max_offset_m)
            included_holes = {hole.hole_id for hole in projected if hole.included}
            matched_included_holes = {item.hole_id for item in valid_lith if item.hole_id in included_holes}
            if included_holes and not matched_included_holes:
                raise ValueError(
                    "No lithology intervals match the included holes. "
                    "Check the lithology hole_id mapping and confirm the section line / max offset include the intended boreholes."
                )

            category_values = [item.category for item in valid_lith if item.hole_id in included_holes]
            if not category_values:
                category_values = [item.category for item in valid_lith]
            class_map = build_category_class_map(category_values)
            self.palette = ensure_palette(category_values, self.palette)
            polygons, warnings = build_stick_polygons(
                projected_holes=projected,
                lith_records=valid_lith,
                width_m=float(self.rect_width.get()),
                category_to_color=self.palette,
            )

            out_dir = Path(self.output_dir.get()).resolve()
            out_dir.mkdir(parents=True, exist_ok=True)
            base = self.output_base.get().strip() or "borehole_sticks"
            bln_path = out_dir / f"{base}.bln"
            shp_path = out_dir / f"{base}.shp"
            postmap_path = out_dir / f"{base}_postmap.csv"
            postmap_labels_path = out_dir / f"{base}_postmap_labels.csv"
            qa_path = out_dir / f"{base}_qa.csv"
            pal_path = out_dir / f"{base}_palette.csv"
            surfer_script_path = out_dir / f"{base}_surfer_autoload.py"
            surfer_bat_path = out_dir / f"{base}_run_surfer_autoload.bat"
            out_srf_path = out_dir / f"{base}.srf"

            write_bln(bln_path, polygons)
            shp_path = write_sticks_shapefile(shp_path, polygons, class_map=class_map)
            postmap_path, postmap_rows, postmap_labels_path, postmap_labels_rows = write_postmap_csvs(
                full_path=postmap_path,
                labels_path=postmap_labels_path,
                lith_df=self.lith_df,
                lith_mapping=lith_mapping,
                classification_field=category_field,
                projected_holes=projected,
                collars=collars,
                smart_filter_enabled=bool(self.smart_label_filter_enabled.get()),
                min_label_length_m=min_label_length_m,
                thin_filter_enabled=bool(self.thin_filter_enabled.get()),
                thin_min_abs_m=thin_min_abs_m,
                thin_relative_to_median=thin_relative_to_median,
                merge_adjacent_enabled=bool(self.merge_adjacent_enabled.get()),
                adjacent_gap_tolerance_m=adjacent_gap_tolerance_m,
                class_map=class_map,
            )
            counts = Counter(poly.hole_id for poly in polygons)
            write_qa_csv(qa_path, projected, counts)
            save_palette_csv(pal_path, category_field, self.palette)
            surfer_script_path = write_surfer_autoload_script(
                path=surfer_script_path,
                shp_path=shp_path,
                palette_csv_path=pal_path,
                postmap_csv_path=postmap_labels_path,
                label_field=category_field,
                out_srf_path=out_srf_path,
                reverse_chainage=bool(self.reverse_chainage.get()),
            )
            surfer_bat_path = write_surfer_autoload_bat(
                path=surfer_bat_path,
                script_path=surfer_script_path,
                shp_path=shp_path,
                palette_csv_path=pal_path,
                postmap_csv_path=postmap_labels_path,
                label_field=category_field,
                out_srf_path=out_srf_path,
                reverse_chainage=bool(self.reverse_chainage.get()),
            )

            if self.survey_df is not None:
                warnings.append("Survey file supplied but currently ignored (vertical borehole assumption).")
            if invalid_lith:
                warnings.append(f"Skipped {len(invalid_lith)} invalid intervals where to_depth <= from_depth.")
            overlap_count = count_lith_overlaps(valid_lith)
            if overlap_count > 0:
                warnings.append(
                    f"Detected {overlap_count} overlapping lithology interval pair(s); review input intervals."
                )

            included = sum(1 for h in projected if h.included)
            excluded = len(projected) - included
            self._log(f"Exported BLN polygons: {len(polygons)}")
            self._log(f"Included holes: {included}; excluded by offset: {excluded}")
            self._log(f"BLN: {bln_path}")
            self._log(f"SHP: {shp_path}")
            self._log("SHP includes numeric CLASS_ID field for Surfer Classed Colors.")
            self._log(f"PostMap CSV (full): {postmap_path}")
            self._log(f"PostMap CSV (labels): {postmap_labels_path}")
            self._log(
                "Profile chainage orientation: "
                f"{'reversed in Surfer output' if self.reverse_chainage.get() else 'standard left-to-right'}"
            )
            if self.reverse_chainage.get():
                self._log(
                    "Note: Manual SHP/PostMap imports outside the generated runner still need the Surfer X axis reversed."
                )
            self._log(
                "Label filter: "
                f"{'ON' if self.smart_label_filter_enabled.get() else 'OFF'}, "
                f"min_length_m={min_label_length_m}"
            )
            self._log(
                "Label advanced: "
                f"thin={'ON' if self.thin_filter_enabled.get() else 'OFF'} "
                f"(abs={thin_min_abs_m}, rel={thin_relative_to_median}), "
                f"merge={'ON' if self.merge_adjacent_enabled.get() else 'OFF'} "
                f"(gap_tol={adjacent_gap_tolerance_m})"
            )
            self._log(f"Rows full -> labels: {postmap_rows} -> {postmap_labels_rows}")
            self._log(f"QA CSV: {qa_path}")
            self._log(f"Palette CSV: {pal_path}")
            self._log(f"Surfer script: {surfer_script_path}")
            self._log(f"Surfer runner BAT: {surfer_bat_path}")
            try:
                subprocess.Popen(
                    ["cmd", "/c", str(surfer_bat_path)],
                    cwd=str(out_dir),
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
                self._log("Launched Surfer runner BAT automatically.")
            except Exception as launch_exc:
                self._log(f"Warning: Could not auto-launch Surfer runner: {launch_exc}")
            for warning in warnings:
                self._log(f"Warning: {warning}")
            self._save_settings()
            messagebox.showinfo("Complete", "Export complete. See Messages panel for details.")
        except Exception as exc:
            messagebox.showerror("Processing error", str(exc))


def run() -> None:
    root = Tk()
    app = BoreholeStickApp(root)
    app.mainloop()
