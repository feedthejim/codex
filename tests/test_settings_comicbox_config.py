"""
COMICBOX_CONFIG overlay regression tests.

comicbox's confuse template nests ``loglevel`` and ``delete_keys`` under the
``general`` section; a flat overlay is *silently ignored*. That regression
made renames carry comicfn2dict remainder junk from the old filename into
the new one (e.g. ``Wolverine (0000) #023.cbz`` →
``… Power Grab[(0000)].cbz``) because ``remainders`` was never deleted from
the merged metadata.
"""

from codex.settings import COMICBOX_CONFIG, LOGLEVEL


def test_delete_keys_overlay_reaches_comicbox() -> None:
    """The unused-field delete list must survive the config overlay."""
    keys = COMICBOX_CONFIG.general.delete_keys
    # Non-empty proves the nested overlay applied at all.
    assert keys
    # Filename junk must not leak into rename targets.
    assert "remainders" in keys
    # A field codex consumes must never be deleted.
    assert "series" not in keys


def test_loglevel_overlay_reaches_comicbox() -> None:
    """Comicbox logs at codex's configured level, not its own default."""
    assert COMICBOX_CONFIG.general.loglevel == LOGLEVEL
