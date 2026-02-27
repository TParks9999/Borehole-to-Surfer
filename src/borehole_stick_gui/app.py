from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import subprocess
from tkinter import BooleanVar, END, StringVar, Tk, colorchooser, filedialog, messagebox
from tkinter import ttk
from typing import Any

import pandas as pd

from .export_bln import write_bln
from .export_postmap_csv import write_postmap_csvs
from .export_qa import write_qa_csv
from .export_shp import write_sticks_shapefile
from .export_surfer_autoload import write_surfer_autoload_bat, write_surfer_autoload_script
from .geometry import project_collar_records
from .io_csv import detect_mapping, parse_collar, parse_lith, read_csv, split_lith_validity
from .models import LineDefinition, LinePoint
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


class BoreholeStickApp(ttk.Frame):
    def __init__(self, root: Tk) -> None:
        super().__init__(root, padding=10)
        self.root = root
        self.root.title("Borehole Stick Generator")
        self.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

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
        self.smart_label_filter_enabled = BooleanVar(value=True)
        self.label_density_preset = StringVar(value="Medium")
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

        self.settings_path = Path.home() / ".borehole_stick_gui_settings.json"
        self._saved_collar_mapping: dict[str, str] = {}
        self._saved_lith_mapping: dict[str, str] = {}
        self._load_settings()

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._autoload_recent_files()

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
            ("label_density_preset", self.label_density_preset),
            ("thin_min_abs_m", self.thin_min_abs_m),
            ("thin_relative_to_median", self.thin_relative_to_median),
            ("adjacent_gap_tolerance_m", self.adjacent_gap_tolerance_m),
        ]:
            value = data.get(key)
            if isinstance(value, str):
                var.set(value)
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
            "smart_label_filter_enabled": bool(self.smart_label_filter_enabled.get()),
            "label_density_preset": self.label_density_preset.get(),
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
        self.smart_label_filter_enabled.set(True)
        self.label_density_preset.set("Medium")
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
        self._log("Settings reset to defaults.")

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

    def _build_ui(self) -> None:
        files_frame = ttk.LabelFrame(self, text="Input Files")
        files_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        files_frame.columnconfigure(1, weight=1)

        self._file_row(files_frame, 0, "Collar CSV", self.collar_path, self._load_collar)
        self._file_row(files_frame, 1, "Lithology CSV", self.lith_path, self._load_lith)
        self._file_row(files_frame, 2, "Survey CSV (optional)", self.survey_path, self._load_survey)

        line_frame = ttk.LabelFrame(self, text="Survey Line Definition")
        line_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        for idx in range(6):
            line_frame.columnconfigure(idx, weight=1)
        labels = ["P1 Easting", "P1 Northing", "P1 Chainage", "P2 Easting", "P2 Northing", "P2 Chainage"]
        vars_ = [self.p1_e, self.p1_n, self.p1_ch, self.p2_e, self.p2_n, self.p2_ch]
        for col, (label, var) in enumerate(zip(labels, vars_)):
            ttk.Label(line_frame, text=label).grid(row=0, column=col, sticky="w")
            ttk.Entry(line_frame, textvariable=var, width=14).grid(row=1, column=col, sticky="ew", padx=1)

        options_frame = ttk.LabelFrame(self, text="Options")
        options_frame.grid(row=2, column=0, sticky="ew", padx=2, pady=2)
        for idx in range(6):
            options_frame.columnconfigure(idx, weight=1)
        ttk.Label(options_frame, text="Max Off-Line Distance (m)").grid(row=0, column=0, sticky="w")
        ttk.Entry(options_frame, textvariable=self.max_offset, width=12).grid(row=1, column=0, sticky="w")
        ttk.Label(options_frame, text="Stick Width (m)").grid(row=0, column=1, sticky="w")
        ttk.Entry(options_frame, textvariable=self.rect_width, width=12).grid(row=1, column=1, sticky="w")
        ttk.Label(options_frame, text="Classification Column").grid(row=0, column=2, sticky="w")
        self.category_combo = ttk.Combobox(
            options_frame, textvariable=self.category_field, state="readonly", width=28
        )
        self.category_combo.grid(row=1, column=2, sticky="ew", padx=2)
        self.category_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_palette_view())
        ttk.Checkbutton(
            options_frame,
            text="Smart label filter (major units + spacing)",
            variable=self.smart_label_filter_enabled,
            command=self._save_settings,
        ).grid(row=0, column=3, columnspan=2, sticky="w")
        ttk.Label(options_frame, text="Label Density").grid(row=0, column=5, sticky="w")
        density_combo = ttk.Combobox(
            options_frame,
            textvariable=self.label_density_preset,
            state="readonly",
            values=["Light", "Medium", "Strong"],
            width=10,
        )
        density_combo.grid(row=1, column=5, sticky="w")
        density_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_settings())

        ttk.Checkbutton(
            options_frame,
            text="Thin-unit suppression",
            variable=self.thin_filter_enabled,
            command=self._save_settings,
        ).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(options_frame, text="Thin min abs (m)").grid(row=2, column=2, sticky="w")
        thin_abs_entry = ttk.Entry(options_frame, textvariable=self.thin_min_abs_m, width=12)
        thin_abs_entry.grid(row=3, column=2, sticky="w")
        thin_abs_entry.bind("<FocusOut>", lambda _e: self._save_settings())

        ttk.Label(options_frame, text="Thin relative factor").grid(row=2, column=3, sticky="w")
        thin_rel_entry = ttk.Entry(options_frame, textvariable=self.thin_relative_to_median, width=12)
        thin_rel_entry.grid(row=3, column=3, sticky="w")
        thin_rel_entry.bind("<FocusOut>", lambda _e: self._save_settings())

        ttk.Checkbutton(
            options_frame,
            text="Merge adjacent same-category units",
            variable=self.merge_adjacent_enabled,
            command=self._save_settings,
        ).grid(row=2, column=4, sticky="w")
        ttk.Label(options_frame, text="Adj. gap tolerance (m)").grid(row=2, column=5, sticky="w")
        adj_gap_entry = ttk.Entry(options_frame, textvariable=self.adjacent_gap_tolerance_m, width=12)
        adj_gap_entry.grid(row=3, column=5, sticky="w")
        adj_gap_entry.bind("<FocusOut>", lambda _e: self._save_settings())

        output_frame = ttk.LabelFrame(self, text="Output")
        output_frame.grid(row=3, column=0, sticky="ew", padx=2, pady=2)
        output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="Output Folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(output_frame, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew")
        ttk.Button(output_frame, text="Browse", command=self._pick_output_dir).grid(row=0, column=2, padx=2)
        ttk.Label(output_frame, text="File Base Name").grid(row=1, column=0, sticky="w")
        ttk.Entry(output_frame, textvariable=self.output_base).grid(row=1, column=1, sticky="ew")

        mapping_frame = ttk.LabelFrame(self, text="Column Mapping")
        mapping_frame.grid(row=4, column=0, sticky="ew", padx=2, pady=2)
        mapping_frame.columnconfigure(1, weight=1)
        mapping_frame.columnconfigure(3, weight=1)
        self._mapping_controls(mapping_frame)

        palette_frame = ttk.LabelFrame(self, text="Palette")
        palette_frame.grid(row=5, column=0, sticky="nsew", padx=2, pady=2)
        palette_frame.columnconfigure(0, weight=1)
        palette_frame.rowconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)

        self.category_list = ttk.Treeview(
            palette_frame, columns=("category", "color", "swatch"), show="headings", height=10
        )
        self.category_list.heading("category", text="Category")
        self.category_list.heading("color", text="Color")
        self.category_list.heading("swatch", text="Swatch")
        self.category_list.column("category", width=260)
        self.category_list.column("color", width=120)
        self.category_list.column("swatch", width=90, anchor="center")
        self.category_list.grid(row=0, column=0, sticky="nsew")
        palette_btns = ttk.Frame(palette_frame)
        palette_btns.grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Button(palette_btns, text="Set Color", command=self._set_selected_color).pack(side="left", padx=2)
        ttk.Button(palette_btns, text="Load Palette CSV", command=self._load_palette).pack(side="left", padx=2)
        ttk.Button(palette_btns, text="Save Palette CSV", command=self._save_palette).pack(side="left", padx=2)

        run_frame = ttk.Frame(self)
        run_frame.grid(row=6, column=0, sticky="ew", padx=2, pady=6)
        ttk.Button(run_frame, text="Generate Outputs", command=self._run).pack(side="left")
        ttk.Button(run_frame, text="Reset Settings", command=self._reset_settings).pack(side="left", padx=6)

        log_frame = ttk.LabelFrame(self, text="Messages")
        log_frame.grid(row=7, column=0, sticky="nsew", padx=2, pady=2)
        self.rowconfigure(7, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_box = ttk.Treeview(log_frame, columns=("message",), show="headings", height=6)
        self.log_box.heading("message", text="Message")
        self.log_box.column("message", width=800)
        self.log_box.grid(row=0, column=0, sticky="nsew")

    def _mapping_controls(self, parent: ttk.LabelFrame) -> None:
        ttk.Label(parent, text="Collar fields").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text="Lith fields").grid(row=0, column=2, sticky="w")

        collar_fields = ["hole_id", "easting", "northing", "rl"]
        lith_fields = ["hole_id", "from_depth", "to_depth"]
        for idx, field in enumerate(collar_fields, start=1):
            ttk.Label(parent, text=field).grid(row=idx, column=0, sticky="w")
            var = StringVar()
            self.collar_map_vars[field] = var
            ttk.Combobox(parent, textvariable=var, state="readonly").grid(row=idx, column=1, sticky="ew")
        for idx, field in enumerate(lith_fields, start=1):
            ttk.Label(parent, text=field).grid(row=idx, column=2, sticky="w")
            var = StringVar()
            self.lith_map_vars[field] = var
            ttk.Combobox(parent, textvariable=var, state="readonly").grid(row=idx, column=3, sticky="ew")

    def _file_row(self, parent: ttk.Frame, row: int, label: str, var: StringVar, cb) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew")
        ttk.Button(parent, text="Load", command=cb).grid(row=row, column=2, padx=2)

    def _pick_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)
            self._save_settings()

    def _load_collar_path(self, path: str | Path) -> None:
        self.collar_df = read_csv(path)
        self.collar_path.set(str(path))
        self._bind_mapping_options(self.collar_map_vars, list(self.collar_df.columns))
        result = detect_mapping(self.collar_df.columns, self.collar_map_vars.keys())
        for field, column in result.mapping.items():
            self.collar_map_vars[field].set(column)
        for field, column in self._saved_collar_mapping.items():
            if field in self.collar_map_vars and column in self.collar_df.columns:
                self.collar_map_vars[field].set(column)
        self._log(f"Loaded collar CSV with {len(self.collar_df)} rows.")

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
        self._log(f"Loaded survey CSV with {len(self.survey_df)} rows (optional; ignored in processing).")

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
        categories = (
            self.lith_df[cat_col].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
        )
        self.palette = ensure_palette(categories, self.palette)
        for cat in sorted(categories):
            color = self.palette.get(cat, "#808080")
            tag = f"swatch_{color.replace('#', '')}"
            try:
                self.category_list.tag_configure(tag, background=color)
            except Exception:
                pass
            self.category_list.insert("", END, values=(cat, color, "      "), tags=(tag,))

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
        _, chosen = colorchooser.askcolor(color=initial, title=f"Pick color for {category}")
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
            if thin_min_abs_m < 0:
                raise ValueError("Thin min abs (m) must be >= 0.")
            if thin_relative_to_median < 0:
                raise ValueError("Thin relative factor must be >= 0.")
            if adjacent_gap_tolerance_m < 0:
                raise ValueError("Adjacent gap tolerance (m) must be >= 0.")

            collar_mapping = self._get_mapping(
                self.collar_map_vars, ["hole_id", "easting", "northing", "rl"]
            )
            lith_mapping = self._get_mapping(self.lith_map_vars, ["hole_id", "from_depth", "to_depth"])
            lith_mapping[category_field] = category_field

            collars = parse_collar(self.collar_df, collar_mapping)
            all_lith = parse_lith(self.lith_df, lith_mapping, category_field)
            valid_lith, invalid_lith = split_lith_validity(all_lith)

            line = self._line_definition()
            projected = project_collar_records(collars, line, float(self.max_offset.get()))

            category_values = [item.category for item in valid_lith]
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
            shp_path = write_sticks_shapefile(shp_path, polygons)
            postmap_path, postmap_rows, postmap_labels_path, postmap_labels_rows = write_postmap_csvs(
                full_path=postmap_path,
                labels_path=postmap_labels_path,
                lith_df=self.lith_df,
                lith_mapping=lith_mapping,
                classification_field=category_field,
                projected_holes=projected,
                collars=collars,
                smart_filter_enabled=bool(self.smart_label_filter_enabled.get()),
                density_preset=self.label_density_preset.get(),
                thin_filter_enabled=bool(self.thin_filter_enabled.get()),
                thin_min_abs_m=thin_min_abs_m,
                thin_relative_to_median=thin_relative_to_median,
                merge_adjacent_enabled=bool(self.merge_adjacent_enabled.get()),
                adjacent_gap_tolerance_m=adjacent_gap_tolerance_m,
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
            )
            surfer_bat_path = write_surfer_autoload_bat(
                path=surfer_bat_path,
                script_path=surfer_script_path,
                shp_path=shp_path,
                palette_csv_path=pal_path,
                postmap_csv_path=postmap_labels_path,
                label_field=category_field,
                out_srf_path=out_srf_path,
            )

            if self.survey_df is not None:
                warnings.append("Survey file supplied and ignored (vertical borehole assumption).")
            if invalid_lith:
                warnings.append(f"Skipped {len(invalid_lith)} invalid intervals where to_depth <= from_depth.")

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
                "Label filter: "
                f"{'ON' if self.smart_label_filter_enabled.get() else 'OFF'}, "
                f"preset={self.label_density_preset.get()}"
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
