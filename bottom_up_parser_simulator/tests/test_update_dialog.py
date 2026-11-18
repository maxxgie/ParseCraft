"""Tests for the update dialogs (view layer)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication

from core.preferences import UpdateHistoryEntry
from core.update.manifest import ReleaseManifest
from gui.update_dialog import (
    INSTALL_NOW,
    INSTALL_ON_RESTART,
    REMIND_LATER,
    UpdateDialog,
    UpdateHistoryDialog,
    UpdateProgressDialog,
    _format_size,
)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def _manifest(**overrides) -> ReleaseManifest:
    data = dict(
        version="1.2.0",
        release_date="2026-11-18",
        release_notes="# Release\n- Added automatic updates\n- Fixed export",
        download_url="https://example.com/app.zip",
        sha256="a" * 64,
        size=2_500_000,
        min_version="1.0.0",
        package_type="zip",
    )
    data.update(overrides)
    return ReleaseManifest(**data)


def test_update_dialog_shows_versions(app):
    dialog = UpdateDialog(_manifest(), "1.0.0")
    assert dialog.manifest.version == "1.2.0"
    assert dialog.current_version == "1.0.0"
    assert dialog.windowTitle() == "Update Available"


def test_update_dialog_install_now_choice(app):
    dialog = UpdateDialog(_manifest(), "1.0.0")
    dialog._on_install_now()
    assert dialog.choice == INSTALL_NOW


def test_update_dialog_restart_choice(app):
    dialog = UpdateDialog(_manifest(), "1.0.0")
    dialog._on_install_on_restart()
    assert dialog.choice == INSTALL_ON_RESTART


def test_update_dialog_remind_later_choice(app):
    dialog = UpdateDialog(_manifest(), "1.0.0")
    dialog._on_remind_later()
    assert dialog.choice == REMIND_LATER


def test_update_dialog_close_defaults_to_remind(app):
    dialog = UpdateDialog(_manifest(), "1.0.0")
    dialog.done(0)
    assert dialog.choice == REMIND_LATER


def test_update_progress_set_progress(app):
    dialog = UpdateProgressDialog()
    dialog.set_progress(50, 200)
    assert dialog._bar.value() == 25


def test_update_progress_indeterminate(app):
    dialog = UpdateProgressDialog()
    dialog.set_progress(10, 0)
    assert dialog._bar.minimum() == 0 and dialog._bar.maximum() == 0


def test_update_progress_complete_and_error(app):
    dialog = UpdateProgressDialog()
    dialog.set_complete("Done")
    assert dialog._bar.value() == 100
    dialog.set_error("Boom")
    assert dialog._cancel_button.text() == "Close"


def test_update_progress_cancel(app):
    dialog = UpdateProgressDialog()
    fired = []
    dialog.cancelled.connect(lambda: fired.append(True))
    dialog._on_cancel()
    assert dialog.was_cancelled is True
    assert fired == [True]


def test_update_history_dialog_with_entries(app):
    entries = [
        UpdateHistoryEntry(timestamp="2026-11-18T10:00:00+00:00", event="install", version="1.1.0"),
        UpdateHistoryEntry(timestamp="2026-11-17T09:00:00+00:00", event="check", detail="up to date"),
    ]
    dialog = UpdateHistoryDialog(entries)
    assert dialog.windowTitle() == "Update History"
    # The table should have a row per entry.
    from PyQt6.QtWidgets import QTableWidget

    table = dialog.findChild(QTableWidget)
    assert table is not None
    assert table.rowCount() == 2


def test_update_history_dialog_empty(app):
    dialog = UpdateHistoryDialog([])
    assert dialog.windowTitle() == "Update History"


def test_format_size():
    assert _format_size(0) == "Unknown size"
    assert _format_size(512) == "512 B"
    assert _format_size(2_500_000).endswith("MB")