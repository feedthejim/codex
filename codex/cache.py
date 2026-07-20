"""
Cache backends.

Django's ``FileBasedCache`` treats an unusable cache file as fatal: a
truncated zlib stream or a partial pickle bubbles up as ``zlib.error``
or ``pickle.UnpicklingError``, while a file written by a management
process running under another UID raises ``PermissionError``. Any of
these can crash whatever query happened to fall on that key. The right
behaviour for an expendable cache entry is just "treat it as a miss".

``ResilientFileBasedCache`` catches those errors, tries to delete the
bad file, and reports a miss so the caller continues with the underlying
query instead of returning a 500 to the user.

It also no-ops ``validate_key``: the base class checks every key for
memcached compatibility (no spaces / control chars / length > 250)
and emits a ``CacheKeyWarning`` for violators. Codex hashes-and-pickles
to disk; the FS layer accepts arbitrary keys, so the memcached
portability warnings are noise. Cachalot in particular composes keys
from query plans that include tuples (``(127, 128)``) which trip the
warning on every browse / cover request.
"""

import zlib
from pickle import UnpicklingError
from typing import override

from django.core.cache import caches
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.filebased import FileBasedCache
from django.utils.connection import ConnectionProxy
from loguru import logger

_UNUSABLE_CACHE_ERRORS: tuple[type[BaseException], ...] = (
    zlib.error,
    UnpicklingError,
    EOFError,
    PermissionError,
)


class ResilientFileBasedCache(FileBasedCache):
    """Cache backend that tolerates corrupt or unreadable cache entries."""

    def _discard_unusable(self, fname: str, exc: BaseException) -> None:
        try:
            deleted = self._delete(fname)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
        except OSError as delete_exc:
            logger.debug(f"Could not discard unusable cache file {fname}: {delete_exc}")
        else:
            action = "Discarded" if deleted else "Ignored"
            logger.debug(f"{action} unusable cache file {fname}: {exc}")

    @override
    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default=default, version=version)
        except _UNUSABLE_CACHE_ERRORS as exc:
            fname = self._key_to_file(key, version)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            self._discard_unusable(fname, exc)
            return default

    @override
    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().touch(key, timeout=timeout, version=version)
        except _UNUSABLE_CACHE_ERRORS as exc:
            fname = self._key_to_file(key, version)  # pyright: ignore[reportAttributeAccessIssue], # ty: ignore[unresolved-attribute]
            self._discard_unusable(fname, exc)
            return False

    @override
    def validate_key(self, key):
        """No-op key validation — see module docstring."""


# Per-thread connection to the dedicated "tagging" cache, mirroring
# ``django.core.cache.cache``. Durable tagging state (pending online-tag
# prompts, tag-write errors) lives here because the default cache is
# ``cache.clear()``-ed broadly (import finish, Library/Group CRUD,
# startup) and Django's file-based clear ignores key prefixes.
# django-stubs omits CacheHandler's BaseConnectionHandler base.
tagging_cache = ConnectionProxy(caches, "tagging")  # pyright: ignore[reportArgumentType], # ty: ignore[invalid-argument-type]
