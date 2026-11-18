"""Persistent user preferences, backed by a JSON file.

Preferences are stored per-user (see :mod:`core.paths`) so they survive
application upgrades. This module covers two areas:

* **Update preferences** — whether to check automatically at startup, whether
  to download/install automatically, the update channel, and a manual check
  timestamp.
* **Update history** — an append-only log of update checks/downloads/installs
  that the user can review from the settings dialog.

The store is intentionally dependency-free (standard library only) so it can be
tested without Qt and works in every packaged build.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.paths import get_app_data_dir
from core.version import UPDATE_CHANNEL


PREFERENCES_FILENAME = "preferences.json"

# Default update preferences.
DEFAULT_UPDATE_PREFERENCES: Dict[str, Any] = {
    "auto_check": True,          # check for updates at startup
    "auto_download": False,      # download updates automatically when found
    "auto_install": False,       # install downloaded updates automatically
    "notify_only": True,         # only notify, never auto-download/install
    "check_on_startup": True,    # perform the startup check
    "channel": UPDATE_CHANNEL,   # update channel (stable/beta)
    "last_check": None,          # ISO-8601 timestamp of last check
    "manifest_url": "",          # optional per-user override of manifest URL
}

# Maximum number of history entries to retain.
MAX_HISTORY_ENTRIES = 100


@dataclass
class UpdateHistoryEntry:
    """A single entry in the update history log.

    Attributes:
        timestamp: ISO-8601 timestamp of the event (also the install date).
        event: Event type (``check``, ``download``, ``install``, ``rollback``,
            ``error``).
        version: Version associated with the event, if any.
        detail: Human-readable detail message.
        changes: Optional list of change descriptions (release notes) for an
            installed version.
    """

    timestamp: str
    event: str
    version: str = ""
    detail: str = ""
    changes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict for this entry."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UpdateHistoryEntry":
        """Build an entry from a dict, tolerating missing fields."""
        changes = data.get("changes", [])
        if not isinstance(changes, list):
            changes = [str(changes)]
        return cls(
            timestamp=str(data.get("timestamp", "")),
            event=str(data.get("event", "")),
            version=str(data.get("version", "")),
            detail=str(data.get("detail", "")),
            changes=[str(item) for item in changes],
        )


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class Preferences:
    """JSON-backed preference store.

    The store is loaded lazily and written atomically (write to a temporary
    file, then replace) so a crash mid-write cannot corrupt the file.

    Attributes:
        path: Path to the backing JSON file.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """Initialize the store.

        Args:
            path: Optional explicit path. Defaults to
                ``<app_data_dir>/preferences.json``.
        """
        self.path = Path(path) if path is not None else get_app_data_dir() / PREFERENCES_FILENAME
        self._data: Dict[str, Any] = {}
        self._loaded = False

    # -- persistence -----------------------------------------------------
    def load(self) -> "Preferences":
        """Load preferences from disk, creating defaults if absent.

        Returns:
            ``self`` to allow chaining.
        """
        if self._loaded:
            return self
        self._data = {}
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    self._data = loaded
            except (OSError, json.JSONDecodeError):
                # Corrupt file: start fresh rather than crash the app.
                self._data = {}
        self._loaded = True
        return self

    def save(self) -> None:
        """Atomically persist preferences to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.stem + ".", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=2, sort_keys=True)
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

    # -- update preferences ---------------------------------------------
    def get_update_preferences(self) -> Dict[str, Any]:
        """Return the update preferences merged with defaults.

        Returns:
            A dict containing every update preference key.
        """
        self._ensure_loaded()
        stored = self._data.get("updates")
        prefs = dict(DEFAULT_UPDATE_PREFERENCES)
        if isinstance(stored, dict):
            prefs.update({k: stored[k] for k in DEFAULT_UPDATE_PREFERENCES if k in stored})
        return prefs

    def set_update_preferences(self, values: Dict[str, Any]) -> None:
        """Merge and persist update preferences.

        Only keys present in :data:`DEFAULT_UPDATE_PREFERENCES` are stored.

        Args:
            values: Mapping of preference keys to values.
        """
        self._ensure_loaded()
        current = self.get_update_preferences()
        for key in DEFAULT_UPDATE_PREFERENCES:
            if key in values:
                current[key] = values[key]
        self._data["updates"] = current
        self.save()

    def get(self, key: str, default: Any = None) -> Any:
        """Return a top-level preference value.

        Args:
            key: Preference key.
            default: Value to return when the key is missing.

        Returns:
            The stored value or ``default``.
        """
        self._ensure_loaded()
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a top-level preference value.

        Args:
            key: Preference key.
            value: Value to store.
        """
        self._ensure_loaded()
        self._data[key] = value
        self.save()

    # -- update history --------------------------------------------------
    def get_update_history(self) -> List[UpdateHistoryEntry]:
        """Return the update history, newest first.

        Returns:
            A list of :class:`UpdateHistoryEntry` objects.
        """
        self._ensure_loaded()
        raw = self._data.get("update_history", [])
        entries: List[UpdateHistoryEntry] = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    entries.append(UpdateHistoryEntry.from_dict(item))
        return list(reversed(entries))

    def record_update_event(
        self, event: str, version: str = "", detail: str = ""
    ) -> UpdateHistoryEntry:
        """Append an entry to the update history.

        Args:
            event: Event type (``check``, ``download``, ``install``,
                ``rollback``, ``error``).
            version: Associated version string.
            detail: Human-readable detail.

        Returns:
            The recorded :class:`UpdateHistoryEntry`.
        """
        self._ensure_loaded()
        entry = UpdateHistoryEntry(
            timestamp=_utc_now_iso(), event=event, version=version, detail=detail
        )
        history = self._data.get("update_history")
        if not isinstance(history, list):
            history = []
        history.append(entry.to_dict())
        # Trim oldest entries.
        if len(history) > MAX_HISTORY_ENTRIES:
            history = history[-MAX_HISTORY_ENTRIES:]
        self._data["update_history"] = history
        self.save()
        return entry

    # -- module-level convenience ---------------------------------------
    _default: Optional["Preferences"] = None


def get_preferences() -> Preferences:
    """Return a shared :class:`Preferences` instance.

    Returns:
        The process-wide preferences singleton.
    """
    if Preferences._default is None:
        Preferences._default = Preferences().load()
    return Preferences._default


def reset_preferences() -> None:
    """Reset the shared preferences singleton (mainly for tests)."""
    Preferences._default = None