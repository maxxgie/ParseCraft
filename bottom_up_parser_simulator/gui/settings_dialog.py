"""Application settings dialog with a dedicated Updates section.

The dialog is a thin editor over :class:`~core.preferences.Preferences`. The
Updates tab exposes every option required by the update system (automatic
checks, automatic download/install, notify-only, channel, manual check, and a
link to the update history). Changes are persisted when the user confirms.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.paths import get_app_data_dir, get_install_dir
from core.update.manager import UpdateManager
from core.version import APP_NAME, APP_VERSION, BUILD_NUMBER, RELEASE_DATE


class SettingsDialog(QDialog):
    """Modal settings editor.

    Signals:
        check_requested: Emitted when the user clicks "Check for Updates Now".
        history_requested: Emitted when the user clicks "View Update History".
    """

    check_requested = pyqtSignal()
    history_requested = pyqtSignal()

    def __init__(self, manager: UpdateManager, parent: Optional[QWidget] = None) -> None:
        """Initialize the dialog.

        Args:
            manager: The :class:`UpdateManager` providing settings and actions.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self._build_ui()
        self._load_values()

    # -- UI --------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_updates_tab(), "Updates")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setContentsMargins(8, 12, 8, 8)
        form.setSpacing(10)

        form.addRow("Application:", QLabel(APP_NAME))
        form.addRow("Version:", QLabel(f"{APP_VERSION} (build {BUILD_NUMBER})"))
        if RELEASE_DATE:
            form.addRow("Release date:", QLabel(RELEASE_DATE))
        form.addRow("Install location:", QLabel(str(get_install_dir())))
        form.addRow("User data location:", QLabel(str(get_app_data_dir())))

        note = QLabel(
            "User data (projects, saved grammars, preferences, themes, recent "
            "files, and logs) is stored separately from the application "
            "binaries, so updates never remove your data."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748B;")
        form.addRow(note)
        return tab

    def _build_updates_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(8, 12, 8, 8)
        outer.setSpacing(12)

        group = QGroupBox("Automatic updates")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        self._auto_check = QCheckBox("Automatically check for updates at startup")
        self._check_on_startup = QCheckBox("Check for updates when the application launches")
        self._auto_download = QCheckBox("Automatically download updates")
        self._auto_install = QCheckBox("Automatically install downloaded updates")
        self._notify_only = QCheckBox("Notify only (do not download or install automatically)")

        for box in (
            self._auto_check,
            self._check_on_startup,
            self._auto_download,
            self._auto_install,
            self._notify_only,
        ):
            group_layout.addWidget(box)

        outer.addWidget(group)

        channel_group = QGroupBox("Advanced")
        form = QFormLayout(channel_group)
        self._channel = QComboBox()
        self._channel.addItems(["stable", "beta"])
        form.addRow("Update channel:", self._channel)

        self._manifest_url = QLineEdit()
        self._manifest_url.setPlaceholderText("Leave blank to use the default update server")
        form.addRow("Update manifest URL:", self._manifest_url)
        outer.addWidget(channel_group)

        last_check = QLabel("")
        last_check.setStyleSheet("color: #64748B;")
        self._last_check_label = last_check
        outer.addWidget(last_check)

        actions = QHBoxLayout()
        check_button = QPushButton("Check for Updates Now")
        check_button.setObjectName("checkNowButton")
        check_button.clicked.connect(self.check_requested.emit)
        actions.addWidget(check_button)

        history_button = QPushButton("View Update History")
        history_button.setObjectName("historyButton")
        history_button.clicked.connect(self.history_requested.emit)
        actions.addWidget(history_button)
        actions.addStretch(1)
        outer.addLayout(actions)

        outer.addStretch(1)
        return tab

    # -- data binding ----------------------------------------------------
    def _load_values(self) -> None:
        settings = self.manager.get_settings()
        self._auto_check.setChecked(bool(settings.get("auto_check", True)))
        self._check_on_startup.setChecked(bool(settings.get("check_on_startup", True)))
        self._auto_download.setChecked(bool(settings.get("auto_download", False)))
        self._auto_install.setChecked(bool(settings.get("auto_install", False)))
        self._notify_only.setChecked(bool(settings.get("notify_only", True)))

        channel = settings.get("channel", "stable")
        index = self._channel.findText(channel)
        self._channel.setCurrentIndex(index if index >= 0 else 0)

        self._manifest_url.setText(str(settings.get("manifest_url", "")))

        last_check = settings.get("last_check")
        if last_check:
            self._last_check_label.setText(f"Last checked: {str(last_check)[:19].replace('T', ' ')}")
        else:
            self._last_check_label.setText("Last checked: never")

    def _on_accept(self) -> None:
        """Persist settings and close."""
        self.manager.update_settings(
            {
                "auto_check": self._auto_check.isChecked(),
                "check_on_startup": self._check_on_startup.isChecked(),
                "auto_download": self._auto_download.isChecked(),
                "auto_install": self._auto_install.isChecked(),
                "notify_only": self._notify_only.isChecked(),
                "channel": self._channel.currentText(),
                "manifest_url": self._manifest_url.text().strip(),
            }
        )
        self.accept()