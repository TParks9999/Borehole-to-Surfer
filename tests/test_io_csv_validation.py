import pandas as pd

from borehole_stick_gui.io_csv import find_duplicate_hole_ids, find_missing_category_rows


def test_find_duplicate_hole_ids_returns_sorted_duplicates():
    df = pd.DataFrame(
        {
            "hole_id": ["BH2", "BH1", "BH2", " ", None, "BH1", "BH3"],
        }
    )
    assert find_duplicate_hole_ids(df, "hole_id") == ["BH1", "BH2"]


def test_find_missing_category_rows_reports_csv_like_row_numbers():
    df = pd.DataFrame(
        {
            "lithology": ["SAND", "", None, "  ", "CLAY"],
        }
    )
    assert find_missing_category_rows(df, "lithology") == [3, 4, 5]

