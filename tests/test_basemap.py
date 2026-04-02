from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from borehole_stick_gui.basemap import choose_zoom_for_extent, load_world_imagery, tile_range_for_extent
from borehole_stick_gui.geo import WEB_MERCATOR_LIMIT


def _tile_bytes(color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (256, 256), color=color).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_tile_range_for_world_extent_at_zoom_two_covers_all_tiles():
    extent = (-WEB_MERCATOR_LIMIT, WEB_MERCATOR_LIMIT, -WEB_MERCATOR_LIMIT, WEB_MERCATOR_LIMIT)
    tile_range = tile_range_for_extent(extent, zoom=2)

    assert tile_range.x_min == 0
    assert tile_range.x_max == 3
    assert tile_range.y_min == 0
    assert tile_range.y_max == 3
    assert tile_range.tile_count == 16


def test_choose_zoom_for_extent_respects_max_tile_count():
    extent = (-WEB_MERCATOR_LIMIT, WEB_MERCATOR_LIMIT, -WEB_MERCATOR_LIMIT, WEB_MERCATOR_LIMIT)

    assert choose_zoom_for_extent(extent, max_tile_count=4) == 1


def test_load_world_imagery_uses_disk_cache():
    calls = {"count": 0}

    def opener(_url: str) -> bytes:
        calls["count"] += 1
        return _tile_bytes("#336699")

    extent = (-1000.0, 1000.0, -1000.0, 1000.0)
    with TemporaryDirectory() as tmp_dir:
        cache_dir = Path(tmp_dir)
        first = load_world_imagery(extent, pixel_w=320, pixel_h=240, cache_dir=cache_dir, opener=opener)
        first_call_count = calls["count"]
        second = load_world_imagery(extent, pixel_w=320, pixel_h=240, cache_dir=cache_dir, opener=opener)

        assert first.image.size == (320, 240)
        assert second.image.size == (320, 240)
        assert first.attribution == second.attribution
        assert first_call_count > 0
        assert calls["count"] == first_call_count
