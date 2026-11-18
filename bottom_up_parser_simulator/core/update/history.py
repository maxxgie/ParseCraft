"""Persistent update history backed by ``update_history.json``.

The update system keeps a durable, human-readable history of everything it does
(checks, downloads, installs, rollbacks) in a dedicated JSON file inside the
per-user data directory. Each entry records the installed version, the date it
was installed, and the changes (release notes) that came with it, satisfying the
"Update History" requirement while remaining trivially inspectable.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.paths import get_app_data_dir
from core.preferences import UpdateHistoryEntry


HISTORY_FILENAME = "update_history.json"

# Maximum number of entries to retain.
MAX_HISTORY_ENTRIES = 200


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class UpdateHistoryStore:
    """JSON-backed update history store.

    Attributes:
        path: Path to the backing ``update_history.json`` file.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """Initialize the store.

        Args:
            path: Optional explicit path. Defaults to
                ``<app_data_dir>/update_history.json``.
        """
        self.path = Path(path) if path is not None else get_app_data_dir() / HISTORY_FILENAME
        self._entries: List[UpdateHistoryEntry] = []
        self._loaded = False

    # -- persistence -----------------------------------------------------
    def load(self) -> "UpdateHistoryStore":
        """Load entries from disk, tolerating a missing or corrupt file.

        Returns:
            ``self`` to allow chaining.
        """
        if self._loaded:
            return self
        self._entries = []
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            self._entries.append(UpdateHistoryEntry.from_dict(item))
            except (OSError, json.JSONDecodeError):
                self._entries = []
        self._loaded = True
        return self

    def save(self) -> None:
        """Atomically persist entries to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.stem + ".", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump([e.to_dict() for e in self._entries], handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    # -- access ----------------------------------------------------------
    def entries(self) -> List[UpdateHistoryEntry]:
        """Return all entries, newest first.

        Returns:
            A list of :class:`UpdateHistoryEntry` objects.
        """
        self._ensure_loaded()
        return list(reversed(self._entries))

    def record(
        self,
        event: str,
        version: str = "",
        detail: str = "",
        changes: Optional[List[str]] = None,
    ) -> UpdateHistoryEntry:
        """Append an entry to the history.

        Args:
            event: Event type (``check``, ``download``, ``install``,
                ``rollback``, ``error``).
            version: Associated version string.
            detail: Human-readable detail.
            changes: Optional list of change descriptions (release notes).

        Returns:
            The recorded :class:`UpdateHistoryEntry`.
        """
        self._ensure_loaded()
        entry = UpdateHistoryEntry(
            timestamp=_utc_now_iso(),
            event=event,
            version=version,
            detail=detail,
            changes=list(changes or []),
        )
        self._entries.append(entry)
        if len(self._entries) > MAX_HISTORY_ENTRIES:
            self._entries = self._entries[-MAX_HISTORY_ENTRIES:]
        self.save()
        return entry

    def clear(self) -> None:
        """Remove all history entries."""
        self._ensure_loaded()
        self._entries = []
        self.save()


def get_history_path() -> Path:
    """Return the default path to ``update_history.json``.

    Returns:
        The path inside the per-user data directory.
    """
    return get_app_data_dir() / HISTORY_FILENAME