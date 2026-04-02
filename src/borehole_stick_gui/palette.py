from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable


def _normalize_text(value: str) -> str:
    return str(value).strip().casefold()


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
    normalized_categories = sorted(
        {str(category).strip() for category in categories if str(category).strip() != ""}
    )
    normalized_base = {
        str(category).strip(): normalize_hex(color)
        for category, color in base.items()
        if str(category).strip() != ""
    }
    out = {category: normalized_base[category] for category in normalized_categories if category in normalized_base}
    missing = [category for category in normalized_categories if category not in out]
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
    exact_matches: Dict[str, str] = {}
    fallback_matches: Dict[str, str] = {}
    seen_classifications: set[str] = set()
    target = _normalize_text(classification_column)

    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = str(row.get("category", "")).strip()
            if not category:
                continue
            classification_value = str(row.get("classification_column", "")).strip()
            normalized_classification = _normalize_text(classification_value)
            if normalized_classification:
                seen_classifications.add(normalized_classification)
            color = normalize_hex(str(row.get("color_hex", "")))
            if normalized_classification == target:
                exact_matches[category] = color
            fallback_matches[category] = color

    if exact_matches:
        return exact_matches
    if len(seen_classifications) <= 1:
        return fallback_matches
    return {}
