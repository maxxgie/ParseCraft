"""Tests for the settings dialog with the Updates section."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication

from core.preferences import Preferences
from core.update.manager import UpdateManager
from gui.settings_dialog import SettingsDialog


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def _manager(tmp_path) -> UpdateManager:
    return UpdateManager(Preferences(tmp_path / "preferences.json"))


def test_settings_dialog_loads_defaults(app, tmp_path):
    dialog = SettingsDialog(_manager(tmp_path))
    assert dialog._auto_check.isChecked() is True
    assert dialog._auto_download.isChecked() is False


def test_settings_dialog_saves_changes(app, tmp_path):
    manager = _manager(tmp_path)
    dialog = SettingsDialog(manager)
    dialog._auto_download.setChecked(True)
    dialog._auto_install.setChecked(True)
    dialog._channel.setCurrentText("beta")
    dialog._on_accept()

    settings = manager.get_settings()
    assert settings["auto_download"] is True
    assert settings["auto_install"] is True
    assert settings["channel"] == "beta"


def test_settings_dialog_emits_check_requested(app, tmp_path):
    manager = _manager(tmp_path)
    dialog = SettingsDialog(manager)
    fired = []
    dialog.check_requested.connect(lambda: fired.append(True))
    button = dialog.findChild(type(dialog), "checkNowButton")
    # findChild by object name:
    from PyQt6.QtWidgets import QPushButton

    check_button = dialog.findChild(QPushButton, "checkNowButton")
    assert check_button is not None
    check_button.click()
    assert fired == [True]


def test_settings_dialog_emits_history_requested(app, tmp_path):
    from PyQt6.QtWidgets import QPushButton

    manager = _manager(tmp_path)
    dialog = SettingsDialog(manager)
    fired = []
    dialog.history_requested.connect(lambda: fired.append(True))
    history_button = dialog.findChild(QPushButton, "historyButton")
    assert history_button is not None
    history_button.click()
    assert fired == [True]


def test_settings_dialog_shows_version(app, tmp_path):
    from core.version import APP_VERSION, BUILD_NUMBER
    from PyQt6.QtWidgets import QLabel

    dialog = SettingsDialog(_manager(tmp_path))
    labels = [lbl.text() for lbl in dialog.findChildren(QLabel)]
    assert any(f"{APP_VERSION} (build {BUILD_NUMBER})" == text for text in labels)


def test_settings_dialog_reflects_saved_values(app, tmp_path):
    manager = _manager(tmp_path)
    manager.update_settings({"auto_download": True, "channel": "beta"})
    dialog = SettingsDialog(manager)
    assert dialog._auto_download.isChecked() is True
    assert dialog._channel.currentText() == "beta"