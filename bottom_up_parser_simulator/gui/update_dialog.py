"""Dialogs for the update user experience.

These dialogs are intentionally thin views: they render information and collect
a user decision. All network, download, verification, and install work is done
by :class:`~core.update.manager.UpdateManager` and the worker threads in
:mod:`gui.update_worker`; the owning window orchestrates the flow.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.preferences import UpdateHistoryEntry


# User choices returned by :class:`UpdateDialog`.
INSTALL_NOW = "install_now"
INSTALL_ON_RESTART = "install_on_restart"
REMIND_LATER = "remind_later"


def _format_size(size: int) -> str:
    """Return a human-readable size string.

    Args:
        size: Size in bytes.

    Returns:
        A string such as ``"14.2 MB"``.
    """
    if size <= 0:
        return "Unknown size"
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{size} B"


class UpdateDialog(QDialog):
    """Prompt the user about an available update.

    The dialog shows the new version, release date, size, and release notes,
    and offers three choices: install now, install on next restart, or remind
    later.

    Attributes:
        choice: The selected choice (one of the module-level constants), or
            ``None`` if the dialog was closed without choosing.
    """

    def __init__(
        self,
        manifest,
        current_version: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the dialog.

        Args:
            manifest: The :class:`~core.update.manifest.ReleaseManifest`.
            current_version: The installed version string.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.manifest = manifest
        self.current_version = current_version
        self.choice: Optional[str] = None

        self.setWindowTitle("Update Available")
        self.setMinimumWidth(520)
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the dialog widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("A new version of the application is available")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #1E293B;")
        layout.addWidget(title)

        version_line = QLabel(
            f"Current version: <b>{self.current_version}</b>"
            f"  &nbsp;&rarr;&nbsp;  New version: <b>{self.manifest.version}</b>"
        )
        version_line.setTextFormat(Qt.TextFormat.RichText)
        version_line.setStyleSheet("color: #334155;")
        layout.addWidget(version_line)

        meta_bits = []
        if self.manifest.release_date:
            meta_bits.append(f"Released: {self.manifest.release_date}")
        if self.manifest.size:
            meta_bits.append(f"Size: {_format_size(self.manifest.size)}")
        if self.manifest.mandatory:
            meta_bits.append("This update is mandatory")
        if meta_bits:
            meta = QLabel(" &nbsp;•&nbsp; ".join(meta_bits))
            meta.setStyleSheet("color: #64748B;")
            layout.addWidget(meta)

        notes_label = QLabel("Release notes:")
        notes_label.setStyleSheet("color: #334155; font-weight: bold;")
        layout.addWidget(notes_label)

        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setMinimumHeight(180)
        notes.setStyleSheet(
            "QTextBrowser { background: #F8FAFC; border: 1px solid #CBD5E1;"
            " border-radius: 6px; padding: 8px; color: #1F2937; }"
        )
        notes_text = self.manifest.release_notes or "No release notes provided."
        try:
            notes.setMarkdown(notes_text)
        except Exception:
            notes.setPlainText(notes_text)
        layout.addWidget(notes)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        remind_button = QPushButton("Remind Me Later")
        remind_button.setObjectName("remindButton")
        remind_button.clicked.connect(self._on_remind_later)
        buttons.addWidget(remind_button)

        restart_button = QPushButton("Install on Next Restart")
        restart_button.setObjectName("restartButton")
        restart_button.clicked.connect(self._on_install_on_restart)
        buttons.addWidget(restart_button)

        install_button = QPushButton("Install Now")
        install_button.setObjectName("installButton")
        install_button.setDefault(True)
        install_button.setStyleSheet(
            "QPushButton#installButton { background-color: #2563EB; color: white;"
            " font-weight: bold; padding: 6px 16px; border-radius: 6px; border: none; }"
            "QPushButton#installButton:hover { background-color: #1D4ED8; }"
        )
        install_button.clicked.connect(self._on_install_now)
        buttons.addWidget(install_button)

        layout.addLayout(buttons)

    # -- button handlers -------------------------------------------------
    def _finish(self, choice: str) -> None:
        self.choice = choice
        self.accept()

    def _on_install_now(self) -> None:
        self._finish(INSTALL_NOW)

    def _on_install_on_restart(self) -> None:
        self._finish(INSTALL_ON_RESTART)

    def _on_remind_later(self) -> None:
        self.choice = REMIND_LATER
        self.reject()

    def done(self, result: int) -> None:  # noqa: N802 (Qt naming)
        """Ensure closing the dialog records a "remind later" choice."""
        if self.choice is None:
            self.choice = REMIND_LATER
        super().done(result)


class UpdateProgressDialog(QDialog):
    """Show download progress with a cancel option.

    Signals:
        cancelled: Emitted when the user clicks "Cancel".
    """

    cancelled = pyqtSignal()

    def __init__(self, title: str = "Downloading Update", parent: Optional[QWidget] = None) -> None:
        """Initialize the progress dialog.

        Args:
            title: Window title.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self._cancelled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._status = QLabel("Preparing download...")
        self._status.setStyleSheet("color: #334155;")
        layout.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setStyleSheet(
            "QProgressBar { border: 1px solid #CBD5E1; border-radius: 6px;"
            " text-align: center; color: #1F2937; background: #F8FAFC; }"
            "QProgressBar::chunk { background-color: #2563EB; border-radius: 5px; }"
        )
        layout.addWidget(self._bar)

        self._detail = QLabel("")
        self._detail.setStyleSheet("color: #64748B;")
        layout.addWidget(self._detail)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("cancelButton")
        self._cancel_button.clicked.connect(self._on_cancel)
        buttons.addWidget(self._cancel_button)
        layout.addLayout(buttons)

    @property
    def was_cancelled(self) -> bool:
        """Return ``True`` if the user cancelled."""
        return self._cancelled

    def set_status(self, text: str) -> None:
        """Update the status line.

        Args:
            text: Status text.
        """
        self._status.setText(text)

    def set_detail(self, text: str) -> None:
        """Update the detail line.

        Args:
            text: Detail text.
        """
        self._detail.setText(text)

    def set_busy(self) -> None:
        """Switch the progress bar to an indeterminate (busy) animation."""
        self._bar.setRange(0, 0)

    def set_progress(self, downloaded: int, total: int) -> None:
        """Update the progress bar.

        Args:
            downloaded: Bytes downloaded so far.
            total: Total bytes (0 if unknown).
        """
        if total > 0:
            self._bar.setRange(0, 100)
            percent = int(downloaded * 100 / total)
            self._bar.setValue(min(100, max(0, percent)))
            self.set_detail(f"{_format_size(downloaded)} of {_format_size(total)}")
        else:
            self.set_busy()
            self.set_detail(f"{_format_size(downloaded)} downloaded")

    def set_complete(self, message: str = "Download complete") -> None:
        """Mark the progress as complete.

        Args:
            message: Status message to display.
        """
        self._bar.setRange(0, 100)
        self._bar.setValue(100)
        self.set_status(message)
        self._cancel_button.setEnabled(False)

    def set_error(self, message: str) -> None:
        """Display an error state.

        Args:
            message: Error message.
        """
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self.set_status(message)
        self._cancel_button.setText("Close")

    def _on_cancel(self) -> None:
        self._cancelled = True
        self.cancelled.emit()


class UpdateHistoryDialog(QDialog):
    """Display the update history (checks, downloads, installs, rollbacks)."""

    def __init__(
        self, history: List[UpdateHistoryEntry], parent: Optional[QWidget] = None
    ) -> None:
        """Initialize the history dialog.

        Args:
            history: List of history entries (newest first).
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Update History")
        self.setMinimumSize(640, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QLabel("Recent update activity")
        header.setStyleSheet("color: #1E293B; font-weight: bold;")
        layout.addWidget(header)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Timestamp", "Event", "Version", "Detail"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header_view = table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.setStyleSheet(
            "QTableWidget { background: #FFFFFF; grid-color: #E2E8F0;"
            " selection-background-color: #DBEAFE; selection-color: #0F172A; }"
            "QHeaderView::section { background-color: #1E293B; color: #F8FAFC;"
            " font-weight: bold; padding: 4px; border: 0px; border-right: 1px solid #334155; }"
        )
        for entry in history:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(_format_timestamp(entry.timestamp)))
            table.setItem(row, 1, QTableWidgetItem(entry.event))
            table.setItem(row, 2, QTableWidgetItem(entry.version or "—"))
            table.setItem(row, 3, QTableWidgetItem(entry.detail or ""))
        layout.addWidget(table)

        if not history:
            empty = QLabel("No update activity recorded yet.")
            empty.setStyleSheet("color: #64748B;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close_button)
        layout.addLayout(row)


def _format_timestamp(iso: str) -> str:
    """Format an ISO timestamp for display.

    Args:
        iso: ISO-8601 timestamp string.

    Returns:
        A trimmed display string (date + time) or the original text.
    """
    if not iso:
        return ""
    try:
        # Show the date and time portion without timezone noise.
        return iso.replace("T", " ")[:19]
    except Exception:  # pragma: no cover - defensive
        return iso