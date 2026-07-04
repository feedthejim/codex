"""
Estimate how long an online tagging run will take.

This mirrors the "tag online" launcher dialog's estimate
(frontend/src/components/online-tag/launcher-dialog.vue) so the number the
admin saw before starting carries forward into the live "Look Up Online
Tags" status countdown. Keep the constants and the math in sync with that
component — the whole point is that the two agree.

The model is deliberately simple: a run's wall-clock is bound by the
slowest enabled source's per-minute throughput (first-match-wins means a
comic isn't done until the binding source answers), times the number of API
calls each comic needs, over the comics left.

API calls per comic are counted per source. Metron (comicbox 4.0.5+) is a
fixed two-step search — one series_list discovery call plus one issues_list
lookup — that no longer scales with match mode, so it is a flat count. Comic
Vine's fuzzy volume→issue path does more verification the tighter the match
mode, so it keeps a per-mode count.

Under first-match-wins a comic stops at the first source that answers, so we
conservatively bill the costliest single selected source. When merging all
sources (comicbox first_wins=False) every enabled source is queried for
every comic, so the per-comic calls are summed instead.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

# Per-minute request budgets per source. Matches launcher-dialog SOURCE_RATES.
# Public because the live session snapshot reports each source's budget; the
# leading underscore is gone but the values are still the single source of
# truth shared with the estimate math below.
SOURCE_RATE_PER_MINUTE: Final = MappingProxyType({"metron": 20, "comicvine": 3})

# API calls per comic, per source. Matches the launcher-dialog's
# METRON_CALLS_PER_COMIC / COMICVINE_CALLS_BY_MODE. Metron's two-step search
# (series_list + issues_list) is a flat count that match mode does not change;
# Comic Vine's count scales with match mode.
_METRON_CALLS_PER_COMIC: Final = 2
_COMICVINE_CALLS_BY_MODE: Final = MappingProxyType(
    {"eager": 2, "auto": 3, "careful": 5}
)

# Fallbacks for an unknown mode / unrecognized source, mirroring the dialog.
_DEFAULT_CALLS_PER_COMIC: Final = 3
_DEFAULT_RATE_PER_MINUTE: Final = 10


def _calls_per_comic(source: str, mode: str) -> int:
    """Return the API calls one comic costs against a single source under ``mode``."""
    if source == "metron":
        return _METRON_CALLS_PER_COMIC
    if source == "comicvine":
        return _COMICVINE_CALLS_BY_MODE.get(mode, _DEFAULT_CALLS_PER_COMIC)
    return _DEFAULT_CALLS_PER_COMIC


def _slowest_rate_per_minute(sources: tuple[str, ...]) -> int:
    rates = [SOURCE_RATE_PER_MINUTE[s] for s in sources if s in SOURCE_RATE_PER_MINUTE]
    return min(rates) if rates else _DEFAULT_RATE_PER_MINUTE


def estimate_seconds(
    remaining_comics: int,
    mode: str,
    sources: tuple[str, ...],
    *,
    merge_all_sources: bool = False,
) -> float:
    """Estimated seconds to look up ``remaining_comics`` more comics."""
    if remaining_comics <= 0 or not sources:
        return 0.0
    per_source_calls = [_calls_per_comic(source, mode) for source in sources]
    # Merge queries every source per comic (sum); first-match-wins stops at
    # the first source that answers, so bill the costliest single source.
    calls_per_comic = (
        sum(per_source_calls) if merge_all_sources else max(per_source_calls)
    )
    total_calls = remaining_comics * calls_per_comic
    minutes = total_calls / _slowest_rate_per_minute(sources)
    return minutes * 60.0
