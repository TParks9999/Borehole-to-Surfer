from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable


def normalize_hex(color: str) -> str:
    c = str(color).strip()
    if not c:
        return "#808080"
    if not c.startswith("#"):
        c = f"#{c}"
    c = c.upper()
    if len(c) == 4:
        c = f"#{c[1]*2}{c[2]*2}{c[3]*2}"
    if len(c) != 7:
        return "#808080"
    if not all(ch in "0123456789ABCDEF#" for ch in c):
        return "#808080"
    return c


RAINBOW_PRESET = [
    "#FF0000",  # red
    "#FF7F00",  # orange
    "#FFFF00",  # yellow
    "#00FF00",  # green
    "#0000FF",  # blue
    "#4B0082",  # indigo
    "#8F00FF",  # violet
]


def ensure_palette(categories: Iterable[str], base: Dict[str, str]) -> Dict[str, str]:
    out = {k: normalize_hex(v) for k, v in base.items()}
    missing = [cat for cat in sorted({str(c) for c in categories}) if cat not in out]
    for idx, cat in enumerate(missing):
        out[cat] = RAINBOW_PRESET[idx % len(RAINBOW_PRESET)]
    return out


def save_palette_csv(path: str | Path, classification_column: str, palette: Dict[str, str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["classification_column", "category", "color_hex"]
        )
        writer.writeheader()
        for category in sorted(palette.keys()):
            writer.writerow(
                {
                    "classification_column": classification_column,
                    "category": category,
                    "color_hex": normalize_hex(palette[category]),
                }
            )


def load_palette_csv(path: str | Path, classification_column: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("classification_column", "") != classification_column:
                continue
            category = str(row.get("category", "")).strip()
            if not category:
                continue
            color = normalize_hex(str(row.get("color_hex", "")))
            out[category] = color
    return out
