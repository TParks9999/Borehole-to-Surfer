from borehole_stick_gui.map_view import (
    compute_extent,
    corridor_polygon_for_extent,
    expand_extent,
    fit_transform,
    world_to_screen,
)


def test_compute_extent():
    extent = compute_extent([(0.0, 0.0), (10.0, 5.0), (-2.0, 4.0)])
    assert extent == (-2.0, 10.0, 0.0, 5.0)


def test_expand_extent_adds_padding():
    out = expand_extent((0.0, 100.0, 0.0, 50.0), buffer_ratio=0.1, min_abs=1.0)
    assert out == (-10.0, 110.0, -5.0, 55.0)


def test_fit_transform_and_world_to_screen():
    t = fit_transform((0.0, 100.0, 0.0, 100.0), canvas_w=220, canvas_h=220, padding_px=10)
    sx, sy = world_to_screen(0.0, 100.0, t)
    assert round(sx, 6) == 10.0
    assert round(sy, 6) == 10.0
    sx2, sy2 = world_to_screen(100.0, 0.0, t)
    assert round(sx2, 6) == 210.0
    assert round(sy2, 6) == 210.0


def test_corridor_polygon_for_extent_returns_quad():
    poly = corridor_polygon_for_extent(
        p1=(0.0, 0.0),
        p2=(10.0, 0.0),
        max_offset=2.0,
        extent=(-5.0, 5.0, -5.0, 5.0),
    )
    assert len(poly) == 4
    ys = [p[1] for p in poly]
    assert max(ys) == 2.0
    assert min(ys) == -2.0

