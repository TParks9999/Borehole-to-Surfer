# Borehole to Surfer

Borehole to Surfer is a Windows desktop application for converting borehole CSV data into section outputs that can be loaded directly into Golden Software Surfer.

It is designed for a practical geology and engineering workflow:

- load collar and lithology tables
- define a section line with chainage
- review borehole inclusion in an in-app map
- export Surfer-ready files with minimal manual cleanup

## Status

This repository is intended for public source control and active development. Generated outputs, local settings, virtual environments, and build artifacts are intentionally excluded from version control.

## Screenshots

### Application
![Borehole to Surfer window](docs/images/app-window.png)

### Surfer Output
![Surfer output example](docs/images/surfer-output-example.png)

## Key Features

- Single-window workflow for borehole section preparation
- Flexible collar and lithology column mapping
- Section line entry by coordinates or CSV import
- Map preview showing collars, section line, corridor, and included or excluded holes
- Optional satellite basemap preview
- Reverse-chainage support for sections that need to read right-to-left in Surfer
- Smart label filtering for cleaner interval labels
- Optional borehole name label export
- Automatic export of Surfer support files, including a runner batch file

## Outputs

For a base name such as `borehole_sticks`, the application generates:

- `borehole_sticks.shp` with companion `.shx`, `.dbf`, and `.prj`
- `borehole_sticks.bln`
- `borehole_sticks_postmap.csv`
- `borehole_sticks_postmap_labels.csv`
- `borehole_sticks_postmap_borehole_names.csv`
- `borehole_sticks_palette.csv`
- `borehole_sticks_qa.csv`
- `borehole_sticks_surfer_autoload.py`
- `borehole_sticks_run_surfer_autoload.bat`

## Requirements

- Windows
- Python 3.10 or later
- Golden Software Surfer for the generated auto-load workflow

## Installation

Install runtime dependencies:

```powershell
python -m pip install -r requirements.txt
```

Install development and test dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Editable install for local development:

```powershell
python -m pip install -e .
```

## Running the Application

Run the application directly:

```powershell
python borehole_stick_gui.py
```

Or use the included Windows launcher:

```powershell
run_borehole_stick_gui.bat
```

The launcher prefers a local `.venv`, creates one if needed, and installs runtime dependencies automatically.

## Typical Workflow

1. Load the collar CSV and lithology CSV.
2. Define the section line using the `P1` and `P2` fields or import a line CSV.
3. Select the classification column in `Column Mapping`.
4. Set section parameters such as maximum off-line distance, stick width, and label sizing.
5. Review the map panel to confirm the correct holes are included.
6. Choose an output folder and base name.
7. Generate outputs and open the Surfer runner if required.

## Input Data

### Required files

- Collar CSV
- Lithology CSV

### Optional line CSV

If you prefer to load the section line from a file, use the following columns:

```csv
point,easting,northing,chainage
P1,499980.0,6999990.0,0.0
P2,500420.0,7000152.0,468.9
```

For reversed profiles, keep the `P1` and `P2` coordinates and chainages true to the section direction, then enable `Reverse profile chainage in Surfer` in the application.

## Example Files

The `examples/` folder includes:

- `collar_template.csv`
- `lithology_template.csv`
- `palette_template.csv`
- `collar_example_comprehensive.csv`
- `lithology_example_comprehensive.csv`
- `palette_example_comprehensive.csv`
- `line_example_comprehensive.csv`

## Development

Run the test suite:

```powershell
python -m pytest -q
```

Build the standalone executable:

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name BoreholeToSurfer --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 --exclude-module PySide6 borehole_stick_gui.py
```

The executable is written to `dist/BoreholeToSurfer.exe`.

## Repository Layout

- `borehole_stick_gui.py` - root launcher
- `src/borehole_stick_gui/` - application source
- `tests/` - automated tests
- `examples/` - sample and template CSV files
- `docs/images/` - screenshots used in documentation

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) for setup, testing, and pull request expectations.

## Security

If you find a vulnerability, follow the reporting guidance in [SECURITY.md](SECURITY.md) instead of opening a public issue first.

## License

No license file has been added yet. Choose and add a license before publishing if you want others to have explicit rights to use, modify, or redistribute this code.

## Troubleshooting

- If Surfer does not open automatically, run `*_run_surfer_autoload.bat` manually.
- If no holes appear in the map or exports, recheck collar column mapping for `hole_id`, `easting`, `northing`, and `rl`.
- If the section orientation is backwards in Surfer, enable `Reverse profile chainage in Surfer` before export.
- If interval labels are too dense or too sparse, adjust the label filtering settings.
