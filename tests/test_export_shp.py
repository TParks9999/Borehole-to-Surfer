from pathlib import Path

import shapefile

from borehole_stick_gui.export_shp import write_sticks_shapefile
from borehole_stick_gui.models import StickPolygon


def test_write_sticks_shapefile(tmp_path: Path):
    polygons = [
        StickPolygon(
            hole_id="BH1",
            category="SAND",
            color_hex="#FFFF00",
            y_top=100.0,
            y_base=98.0,
            x_left=10.0,
            x_right=12.0,
            points=[(10.0, 100.0), (12.0, 100.0), (12.0, 98.0), (10.0, 98.0), (10.0, 100.0)],
        )
    ]
    shp_path = write_sticks_shapefile(tmp_path / "sticks.shp", polygons)
    assert shp_path.exists()
    assert shp_path.with_suffix(".dbf").exists()
    assert shp_path.with_suffix(".shx").exists()
    assert shp_path.with_suffix(".prj").exists()
    assert 'LOCAL_CS["Undefined"]' in shp_path.with_suffix(".prj").read_text(encoding="ascii")

    reader = shapefile.Reader(str(shp_path))
    assert len(reader.records()) == 1
    record = reader.records()[0]
    assert record["HOLE_ID"] == "BH1"
    assert record["CLASS_ID"] == 1
    assert record["CATEGORY"] == "SAND"
