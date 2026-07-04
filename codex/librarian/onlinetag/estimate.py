"""
Adapt comicbox's online-tag run estimator to codex's callers.

The request/rate model that used to live here now lives in
``comicbox.online_estimate`` (comicbox 4.1.0), next to the search flow it
describes and the rate limits it divides by. This module is the thin
codex-facing seam over it: callers keep importing ``estimate_seconds`` /
``SOURCE_RATE_PER_MINUTE`` from here, and the live status countdown and the
launcher dialog stay in agreement with comicbox because they read the same
source of truth instead of a hand-synced copy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from comicbox.online_session import SOURCE_RATE_PER_MINUTE, estimate_run

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ("SOURCE_RATE_PER_MINUTE", "estimate_seconds")


def estimate_seconds(
    remaining_comics: int,
    mode: str,
    sources: Sequence[str],
    *,
    merge_all_sources: bool = False,
) -> float:
    """Estimated seconds to look up ``remaining_comics`` more comics."""
    return estimate_run(
        remaining_comics, mode, sources, merge_all_sources=merge_all_sources
    ).seconds
