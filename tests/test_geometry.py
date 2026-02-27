from borehole_stick_gui.geometry import build_unit_line, project_collar_records
from borehole_stick_gui.models import CollarRecord, LineDefinition, LinePoint


def test_projection_chainage_and_offset():
    line = LineDefinition(
        p1=LinePoint(1000.0, 2000.0, 10.0),
        p2=LinePoint(1100.0, 2000.0, 110.0),
    )
    collars = [
        CollarRecord("BH1", 1020.0, 2000.0, 50.0),
        CollarRecord("BH2", 1020.0, 2010.0, 50.0),
    ]
    out = project_collar_records(collars, line, max_offset_m=10.0)
    assert out[0].chainage == 30.0
    assert out[0].offset_m == 0.0
    assert out[0].included is True
    assert out[1].chainage == 30.0
    assert out[1].offset_m == 10.0
    assert out[1].included is True


def test_identical_line_points_raises():
    line = LineDefinition(
        p1=LinePoint(1.0, 1.0, 0.0),
        p2=LinePoint(1.0, 1.0, 10.0),
    )
    try:
        build_unit_line(line)
        assert False, "Expected ValueError"
    except ValueError:
        pass

