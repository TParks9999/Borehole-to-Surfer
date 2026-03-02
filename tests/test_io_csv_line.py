from pathlib import Path

import pandas as pd
import pytest

from borehole_stick_gui.io_csv import parse_line_definition_df, read_line_definition_csv


def test_parse_line_definition_df_valid():
    df = pd.DataFrame(
        [
            {"point": "P2", "easting": 110.0, "northing": 220.0, "chainage": 50.0},
            {"point": "P1", "easting": 100.0, "northing": 200.0, "chainage": 0.0},
        ]
    )
    line = parse_line_definition_df(df)
    assert line.p1.easting == 100.0
    assert line.p1.northing == 200.0
    assert line.p1.chainage == 0.0
    assert line.p2.easting == 110.0
    assert line.p2.northing == 220.0
    assert line.p2.chainage == 50.0


def test_parse_line_definition_df_rejects_missing_points():
    df = pd.DataFrame(
        [
            {"point": "P1", "easting": 100.0, "northing": 200.0, "chainage": 0.0},
            {"point": "P3", "easting": 110.0, "northing": 220.0, "chainage": 50.0},
        ]
    )
    with pytest.raises(ValueError, match="must be exactly 'P1' and 'P2'"):
        parse_line_definition_df(df)


def test_parse_line_definition_df_rejects_wrong_row_count():
    df = pd.DataFrame(
        [
            {"point": "P1", "easting": 100.0, "northing": 200.0, "chainage": 0.0},
        ]
    )
    with pytest.raises(ValueError, match="exactly two rows"):
        parse_line_definition_df(df)


def test_read_line_definition_csv(tmp_path: Path):
    path = tmp_path / "line.csv"
    path.write_text(
        "point,easting,northing,chainage\n"
        "P1,10,20,0\n"
        "P2,30,40,100\n",
        encoding="ascii",
    )
    line = read_line_definition_csv(path)
    assert line.p1.easting == 10.0
    assert line.p2.chainage == 100.0

