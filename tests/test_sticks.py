from borehole_stick_gui.models import LithRecord, ProjectedHole
from borehole_stick_gui.sticks import build_stick_polygons


def test_build_rectangles_and_fallback_color():
    holes = [
        ProjectedHole("BH1", 0.0, 0.0, 100.0, 50.0, 0.0, True, "ok"),
        ProjectedHole("BH2", 0.0, 0.0, 100.0, 60.0, 20.0, False, "offset>10"),
    ]
    lith = [
        LithRecord("BH1", 0.0, 2.0, "SANDSTONE"),
        LithRecord("BH1", 2.0, 4.0, "UNKNOWN"),
    ]
    polygons, warnings = build_stick_polygons(holes, lith, 2.0, {"SANDSTONE": "#FFFF00"})
    assert len(polygons) == 2
    assert polygons[0].x_left == 49.0
    assert polygons[0].x_right == 51.0
    assert polygons[0].y_top == 100.0
    assert polygons[0].y_base == 98.0
    assert polygons[1].color_hex == "#808080"
    assert any("missing in palette" in w for w in warnings)

