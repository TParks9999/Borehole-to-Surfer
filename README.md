# Borehole to Surfer

Desktop Python GUI app for generating borehole stick outputs for Surfer workflows.

## What It Does

- Loads collar and lithology CSV files.
- Projects boreholes onto a user-defined section line.
- Builds borehole stick polygons.
- Exports:
  - `*.shp` shapefile
  - `*.bln` polygons
  - `*_postmap.csv` (full labels source)
  - `*_postmap_labels.csv` (smart-filtered labels)
  - `*_palette.csv`
  - `*_qa.csv`
  - Surfer auto-load Python script and BAT launcher

## Requirements (Source Run)

- Windows
- Python 3.10+ (tested with Python 3.13)

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Run From Source

```powershell
python borehole_stick_gui.py
```

Alternative:

```powershell
python -m src.borehole_stick_gui
```

## Using the App

1. Load `Collar CSV` and `Lithology CSV` (Survey CSV is optional and currently ignored).
2. Define section line coordinates and chainages (`P1`, `P2`).
3. Set:
   - `Max Off-Line Distance (m)`
   - `Stick Width (m)`
   - `Classification Column`
4. Configure labels:
   - `Smart label filter` ON/OFF
   - `Label Density` (`Light`, `Medium`, `Strong`)
   - Optional advanced controls:
     - Thin-unit suppression
     - Thin minimum absolute thickness
     - Thin relative factor (hole median based)
     - Merge adjacent same-category units
     - Adjacent gap tolerance
5. Choose output folder and base name.
6. Click `Generate Outputs`.

## Smart Label Filtering

When enabled, label filtering applies to `*_postmap_labels.csv`:

- Hybrid thin-unit suppression can remove very thin intervals.
- Adjacent same-category intervals can be consolidated.
- Major-category selection and spacing controls still apply.
- Full `*_postmap.csv` remains unfiltered (all valid included intervals).

## Build Standalone EXE

PyInstaller build command used:

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name BoreholeToSurfer --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 --exclude-module PySide6 borehole_stick_gui.py
```

Output executable:

- `dist\BoreholeToSurfer.exe`

You can distribute this `.exe` to other Windows users without requiring Python/pip setup.

## Project Structure

- `borehole_stick_gui.py` - main launcher
- `src\borehole_stick_gui\` - application source
- `tests\` - pytest tests
- `examples\` - sample data
- `Outputs\` - generated output examples

## Testing

Run all tests:

```powershell
python -m pytest -q
```

## Troubleshooting

- If Surfer does not auto-open, run the generated `*_run_surfer_autoload.bat` manually.
- If mapping errors occur, verify column mappings in the app before generating outputs.
- If no labels appear, check:
  - Smart filter settings
  - Density preset
  - Thin/merge thresholds
  - Hole inclusion by offset filter
