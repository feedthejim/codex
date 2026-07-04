"""
The codex estimate seam delegates to comicbox.online_estimate.

The request/rate model and its full test matrix live in comicbox (4.1.0); these
just guard that codex's thin adapter forwards correctly and re-exports the rate
map the session snapshot reads.
"""

from __future__ import annotations

from typing import Final

import pytest

from codex.librarian.onlinetag.estimate import SOURCE_RATE_PER_MINUTE, estimate_seconds

_METRON_AUTO_SECONDS: Final = 60.0
_MERGE_SECONDS: Final = 1000.0
_METRON_RATE: Final = 20
_COMICVINE_RATE: Final = 3


def test_estimate_seconds_delegates_to_comicbox() -> None:
    """Metron's flat two-step: 10 comics x 2 requests / 20 per-minute = 60s."""
    assert estimate_seconds(10, "auto", ("metron",)) == _METRON_AUTO_SECONDS


def test_estimate_seconds_passes_merge_flag() -> None:
    """merge_all_sources reaches comicbox: (metron 2 + comicvine 3) x 10 / 3."""
    assert estimate_seconds(
        10, "auto", ("metron", "comicvine"), merge_all_sources=True
    ) == pytest.approx(_MERGE_SECONDS)


def test_source_rate_per_minute_reexported() -> None:
    """The snapshot reads the per-source rate map through this seam."""
    assert SOURCE_RATE_PER_MINUTE["metron"] == _METRON_RATE
    assert SOURCE_RATE_PER_MINUTE["comicvine"] == _COMICVINE_RATE
