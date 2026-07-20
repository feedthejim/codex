"""Cover thumbnail sizing and cache-version regression tests."""

from io import BytesIO

from PIL import Image

from codex.librarian.covers.create import (
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    _render_cover_thumb,
)
from codex.librarian.covers.path import CoverPathMixin


def test_cover_cache_path_is_versioned_by_width() -> None:
    """A size change must not silently reuse thumbnails from the old cache."""
    path = CoverPathMixin.get_cover_path(1234, custom=False)
    assert path.name.endswith(f".w{THUMBNAIL_WIDTH}.webp")


def test_render_custom_cover_uses_configured_dimensions(tmp_path) -> None:
    """The renderer should produce the configured Retina-friendly dimensions."""
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "cover.webp"
    Image.new("RGB", (1000, 1537), "red").save(source_path)

    pk, rendered_path, error = _render_cover_thumb(
        (1, str(source_path), str(output_path), True)
    )

    assert (pk, rendered_path, error) == (1, str(output_path), None)
    with output_path.open("rb") as output_file, Image.open(
        BytesIO(output_file.read())
    ) as image:
        assert image.width == THUMBNAIL_WIDTH
        assert image.height <= THUMBNAIL_HEIGHT
