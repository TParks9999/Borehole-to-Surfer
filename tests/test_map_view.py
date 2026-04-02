from borehole_stick_gui.map_view import (
    compute_extent,
    corridor_polygon_for_extent,
    expand_extent,
    fit_transform,
    transform_screen_rect,
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
    assert round(t.draw_w, 6) == 200.0
    assert round(t.draw_h, 6) == 200.0


def test_fit_transform_exposes_letterboxed_draw_box():
    t = fit_transform((0.0, 200.0, 0.0, 100.0), canvas_w=300, canvas_h=300, padding_px=20)

    assert round(t.draw_w, 6) == 260.0
    assert round(t.draw_h, 6) == 130.0
    assert round(t.offset_x, 6) == 20.0
    assert round(t.offset_y, 6) == 85.0


def test_transform_screen_rect_rounds_outward_to_avoid_clipping():
    t = fit_transform((0.0, 3.0, 0.0, 1.0), canvas_w=301, canvas_h=301, padding_px=20)

    left, top, right, bottom = transform_screen_rect(t)

    assert left <= t.offset_x
    assert top <= t.offset_y
    assert right >= t.offset_x + t.draw_w
    assert bottom >= t.offset_y + t.draw_h
    assert (right - left) >= round(t.draw_w)
    assert (bottom - top) >= round(t.draw_h)


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
