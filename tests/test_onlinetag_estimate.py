"""
Unit tests for the online tagging time estimate.

Mirrors the launcher dialog's algorithm: per-comic API calls (counted per
source — first-match-wins bills the costliest source, merge sums them) over
the slowest enabled source's per-minute rate.
"""

from __future__ import annotations

from typing import Final

import pytest

from codex.librarian.onlinetag.estimate import estimate_seconds

_AUTO_METRON_SECONDS: Final = 60.0
_SLOWEST_SOURCE_SECONDS: Final = 600.0
_COMICVINE_CAREFUL_SECONDS: Final = 1000.0
_COMICVINE_EAGER_SECONDS: Final = 400.0
_UNKNOWN_DEFAULTS_SECONDS: Final = 180.0
_MERGE_TWO_SOURCES_SECONDS: Final = 1000.0


def test_zero_remaining_is_zero() -> None:
    """No remaining comics means no time."""
    assert estimate_seconds(0, "auto", ("metron",)) == 0.0


def test_no_sources_is_zero() -> None:
    """No enabled sources means no time."""
    assert estimate_seconds(10, "auto", ()) == 0.0


def test_auto_mode_metron() -> None:
    """Metron's flat two-step search: 10 comics x 2 calls / 20 per-minute = 60s."""
    assert estimate_seconds(10, "auto", ("metron",)) == _AUTO_METRON_SECONDS


def test_metron_calls_are_mode_independent() -> None:
    """Match mode does not change Metron's fixed two-step request count."""
    auto = estimate_seconds(10, "auto", ("metron",))
    careful = estimate_seconds(10, "careful", ("metron",))
    eager = estimate_seconds(10, "eager", ("metron",))
    assert auto == careful == eager == _AUTO_METRON_SECONDS


def test_slowest_source_binds() -> None:
    """
    Comicvine (3/min) is slower than metron (20/min) and binds the rate.

    First-match-wins bills the costliest source: max(metron 2, comicvine 3) = 3.
    10 x 3 / 3 = 10 min = 600s.
    """
    assert (
        estimate_seconds(10, "auto", ("metron", "comicvine")) == _SLOWEST_SOURCE_SECONDS
    )


def test_comicvine_match_mode_scales_calls() -> None:
    """Comic Vine's per-comic calls scale with match mode (careful 5, eager 2)."""
    careful = estimate_seconds(10, "careful", ("comicvine",))
    eager = estimate_seconds(10, "eager", ("comicvine",))
    assert careful == pytest.approx(_COMICVINE_CAREFUL_SECONDS)
    assert eager == pytest.approx(_COMICVINE_EAGER_SECONDS)


def test_unknown_mode_and_source_use_defaults() -> None:
    """
    Unknown mode -> 3 calls/comic; unknown source -> 10/min default.

    10 x 3 / 10 = 3 min = 180s.
    """
    assert estimate_seconds(10, "bogus", ("unknown",)) == _UNKNOWN_DEFAULTS_SECONDS


def test_merge_all_sources_sums_per_source_calls() -> None:
    """
    Merge mode queries every source per comic, so per-comic calls are summed.

    metron 2 + comicvine 3 = 5 calls/comic over 3 per-minute (slowest).
    10 x 5 / 3 = 1000s — more than the 600s first-match-wins estimate but not
    double it, since the two sources cost different amounts.
    """
    assert estimate_seconds(
        10, "auto", ("metron", "comicvine"), merge_all_sources=True
    ) == pytest.approx(_MERGE_TWO_SOURCES_SECONDS)


def test_merge_all_sources_single_source_is_noop() -> None:
    """With one source there's nothing to merge, so the estimate is unchanged."""
    assert (
        estimate_seconds(10, "auto", ("metron",), merge_all_sources=True)
        == _AUTO_METRON_SECONDS
    )
