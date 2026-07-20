"""Regression tests for the resilient file-based cache backend."""

from pathlib import Path
from unittest.mock import patch

from codex.cache import ResilientFileBasedCache


def _cache_with_entry(tmp_path: Path) -> tuple[ResilientFileBasedCache, Path]:
    cache = ResilientFileBasedCache(str(tmp_path), {})
    cache.set("key", "value")
    cache_path = Path(cache._key_to_file("key"))  # noqa: SLF001  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
    assert cache_path.exists()
    return cache, cache_path


def test_get_discards_unreadable_entry(tmp_path: Path) -> None:
    """A mixed-owner entry must behave as a miss instead of crashing a view."""
    cache, cache_path = _cache_with_entry(tmp_path)

    with patch("builtins.open", side_effect=PermissionError(13, "Permission denied")):
        assert cache.get("key", default="miss") == "miss"

    assert not cache_path.exists()


def test_touch_discards_unreadable_entry(tmp_path: Path) -> None:
    """Touch must apply the same recovery contract as get."""
    cache, cache_path = _cache_with_entry(tmp_path)

    with patch("builtins.open", side_effect=PermissionError(13, "Permission denied")):
        assert cache.touch("key") is False

    assert not cache_path.exists()


def test_get_still_returns_readable_entry(tmp_path: Path) -> None:
    """The recovery path must not affect ordinary cache hits."""
    cache, _cache_path = _cache_with_entry(tmp_path)

    assert cache.get("key", default="miss") == "value"
