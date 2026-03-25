"""DayZ Server Manager

Requires:
    pip install PySide6

Optional packaging:
    pip install pyinstaller
    Inno Setup for installer creation

Features:
- Select DayZ server root and related paths
- Detect @mods from the server directory
- Organize client mods and server-side mods
- Build a start.bat command line automatically
- Edit banlist.txt from BattlEye
- Schedule restarts and generate restart notification JSON
- Scan and validate XML files recursively
- Launch/stop/restart the DayZ server process from the app

Notes:
- The restart notification export uses the JSON structure shown in the chat.
- XML validation here means well-formedness validation (parse errors with line/column).
- Auto-detection of which mod must also be loaded server-side is not reliable in general,
  so the app gives explicit client/server lists and drag-and-drop between them.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QProcess, QTimer, QUrl
from PySide6.QtGui import QFont, QTextCursor, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


APP_NAME = "BrutalZ Control Center 🩸"
APP_ORG = "BrutalZ"
SETTINGS_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "DayZServerManager"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
DEFAULT_FIXED_TIMES = ["00:00", "06:00", "12:00", "18:00"]

DISCORD_ICON_B64 = """iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAGpUlEQVR4nM2Xf4hcVxXHP+fe9+a9mdmd2dntbrdJq60//jCCINia2CST1lIEKxjsbEuKBpNtSyqKWG1EkHHsPxWEVlCKupGKorijTZCWCvkj2VRtRKz4axEULcGYsE2Tzf6YX++9e/zjzczuJrtJ2gp64MHMvffc+z3nfO8558L/WOSNq6qgq3cRvcLi/45Uq2rKVfWqVTWXwVGVjeauJN61HgxQq4kD3Aywd6+GDbM4GATL0s6OL4pIE4hnLl9/RblqCCoVtfW6JAD37z//HnxvNxqVVd3bcRQVFUQWxMg/RO2LxsrhHz099LtLdd8QgN4GlU/+e4sJcjVRdnv+gHUuwiUdVNO9xViM8THGJ46WAHmu3V6uHn5m88tXA7EhgJ7ixP65SeMHT3leNt9pXwTVGEFURURUAFRFRVRRFMH6maIkSbvj4tbB6amxp64EYl3ClMvHvHpdksrk6S8F2dJ31cX5dms+TiGLB2JFMCACIt3ftjsnUXs+cUnHD7IjT048OPdEvS5JuXxsXb5d5oG+2/ed2RfmRg+12/OxamJFjKTHpUrukktnBBRQTT9UFUwc5Ib91vLc5+qHxp9czxNrAFSramo19KOTp98Z2PwfBHyXRIKIEYE4hnZHcU7JhgbpaivQajpEhCAQPK8LAlURLzHGStJaum36mc0vVyrTtl6f6INYE4LZ2bqAaEbsE56XD10Sae/wTgcKg0p5m8/De/OMj0Imo4QhDA/BQ5/Iced2n6ECdDraBSeiLhJjA6vW+zrAli2VNb7reyC1Xtz9k2ferSb4o6oD1BgDyw3l/e/1+PRkgcKgBeDiQoJzaUgUKBXT8aXlhG9/f5HjL0UM5AXnQFWd9bLGxcvbpqfGT672Qt8Dx7u/E7wJP1MwqHMASQK5LOx7YIDCoCVO0rFiwVIasgwVLaWiJemOD+Qt+x4YoFQQ4rjPGed5ISpmD8Dclkrf8D6AXdDNWp1dzkUgiDXQaCo7twbcMOaTJGANWEvXsvRzLh0zJgVRKnp8cGdAo6k9chqXdBDYASozNS7lgEqtJm7v3n+GiP825zqgIk4h4ym7tgcovUuX0s6Ylf/GpGMr81D+QEg+C0kaJklcB1V9654Dp4bSwpXmENOnMbCQDQsoBXUJYlSiCMavt7zjZj81w8Bvf9/iwBfOc3Sm0SfSiycbPPjoOWZONjAm9chNmz1u3OStEFIdRiQfRZmhlHOsAtCTpRVqikAUK5s3CRnf4LoBOvJCk7/8zXH4+eX0qgPPPt/kr39XDj/X7NtjjXDTjUIUg4j0coQErBXTOxDAG40WBRZFUkY7ByOlNIF1z2Lr+zKUio5ttwZI19/bt2YoFZRtt/rp2i7YkWHbyweIGBBdluDCAkCtlvq9mx5FqVZNvfaW5n2Tc68Y42/WpONU1QZB1/ouyI/cnWfH1pBiwabxBT724UHu3J7rX8Ue+DDoO1iN8SV28akffPNd5/mWSq+B6a8o8xUD4JATxmRQUBFYWowxBjybJpg/z7YIMoKQ3gjT3SGfFf4026TVcnheOr64mPRI6awNVNBfI6LlKn2k/QKxq9togJuOo6UvOofJ54Rf/iYik1ng3ntyjAx7DBYMBx8/z8iw5fpRiwDnXlNOn4347EMDhKFh/mLCkV8sc3SmTT4nJIkaYzpCwo8Bxmb7zdx6tUDcxOTZF/yg9KGoPZ8gxi43lOEhuGtnSC4n/PCnTZxL3YymOUAV7tsdIsDR423mLjjyoUFEE88ftFFn4aX61Njt1SqyulNap0SqqLnwWBw37xLji2qshQGRRgumf97CCORyBhHto+9VwZ8caeGcEoSGYt6QOFXBqmqMk+jzIDo7u7Zn3Lgc7z/9mTB3wzfa7fMRznlipEf6/pW8VHp8SDOkqqrE2dx1fnP5TLV+aNNXr1qOe1IuH/NmZu6IK5Nnvxbmxh5rN19T1DnE2PXWr+PFBESC8DrTbr769PTU2CPdw7tBWwV6PfWZmTviSkVtfWr8YKdx7lFrgsQPilbVKaqxqq6qBH17XW/O8wettYHptF6tTk+NPVKtqqnXuezwDT3Qk5VwnLnN8/KPq8jdnhfikg6J66xkHDEY42NtgEvaOBef6ESNLz/7vU0nek3ORg+X19WWTzy8cLvg7kXdDtTdrLjBdBOzhMgphF+pup9Nf2f02KW6b0qqVTWorgG758B8qTL5yi2VyTO3fPxT/xpZq6Hyel9I1ySVyrQtV3XD11S5esyrVPQaiZrKm3qc9krqlWL8fy//Aee1QOm5apSCAAAAAElFTkSuQmCC"""
DISCORD_SUPPORT_URL = "https://discord.gg/uaH3k8WRUN"


@dataclass
class RestartConfig:
    mode: str  # "hours", "days", "fixed"
    interval_value: int
    fixed_times: List[str]


class LogBox(QTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setMinimumHeight(160)
        self.setLineWrapMode(QTextEdit.NoWrap)

    def write(self, text: str) -> None:
        self.append(text.rstrip("\n"))
        self.moveCursor(QTextCursor.End)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1500, 940)

        self.server_process: Optional[QProcess] = None
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.setInterval(1000)
        self.scheduler_timer.timeout.connect(self._tick_scheduler)
        self.scheduler_armed = False
        self.next_restart_dt: Optional[datetime] = None
        self.notified_marks: set[int] = set()

        self.settings = self._load_settings()

        self._build_ui()
        self._apply_theme()
        self._wire_actions()
        self._restore_settings_to_ui()
        self._initial_scan_if_possible()
        self._log("App ready.")

    # ------------------------------ UI ------------------------------
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("HeaderCard")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 14)

        title_col = QVBoxLayout()
        title = QLabel("BrutalZ Control Center 🩸")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Server path, mods, banlist, restart scheduler and XML validator in one place. Powered by BrutalZ.")
        subtitle.setObjectName("SubtitleLabel")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setObjectName("StatusPill")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumWidth(260)

        header_layout.addLayout(title_col)
        header_layout.addStretch(1)
        header_layout.addWidget(self.status_label)
        main_layout.addWidget(header)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        self.server_tab = QWidget()
        self.mods_tab = QWidget()
        self.banlist_tab = QWidget()
        self.schedule_tab = QWidget()
        self.validator_tab = QWidget()
        self.logs_tab = QWidget()

        self.tabs.addTab(self.server_tab, "Server")
        self.tabs.addTab(self.mods_tab, "Mods")
        self.tabs.addTab(self.banlist_tab, "Banlist")
        self.tabs.addTab(self.schedule_tab, "Schedule Restart")
        self.tabs.addTab(self.validator_tab, "XML Validator")
        self.tabs.addTab(self.logs_tab, "Logs")

        self._build_server_tab()
        self._build_mods_tab()
        self._build_banlist_tab()
        self._build_schedule_tab()
        self._build_validator_tab()
        self._build_logs_tab()

        footer = QFrame()
        footer.setObjectName("FooterCard")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 10, 14, 10)
        footer_layout.setSpacing(10)
        footer_layout.addStretch(1)
        self.discord_button = QPushButton("Support from Official Discord")
        self.discord_button.setObjectName("DiscordSupport")
        self.discord_button.setCursor(Qt.PointingHandCursor)
        self.discord_button.setIcon(QIcon(self._discord_icon()))
        self.discord_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DISCORD_SUPPORT_URL)))
        footer_layout.addWidget(self.discord_button)
        footer_layout.addStretch(1)
        main_layout.addWidget(footer)

    def _discord_icon(self) -> QPixmap:
        if not hasattr(self, "_discord_icon_cache"):
            pix = QPixmap()
            pix.loadFromData(base64.b64decode(DISCORD_ICON_B64), "PNG")
            self._discord_icon_cache = pix
        return self._discord_icon_cache

    def _build_server_tab(self) -> None:
        layout = QVBoxLayout(self.server_tab)
        layout.setSpacing(10)

        paths_box = QGroupBox("Paths")
        form = QFormLayout(paths_box)
        form.setLabelAlignment(Qt.AlignRight)

        self.server_root_edit = QLineEdit()
        self.exe_edit = QLineEdit()
        self.battleye_edit = QLineEdit()
        self.mission_edit = QLineEdit()
        self.profiles_edit = QLineEdit("profiles")
        self.config_edit = QLineEdit("serverDZ.cfg")
        self.port_edit = QLineEdit("2302")

        self.root_btn = QPushButton("Browse")
        self.exe_btn = QPushButton("Browse")
        self.battleye_btn = QPushButton("Browse")
        self.mission_btn = QPushButton("Browse")

        form.addRow(QLabel("Server root"), self._row_with_button(self.server_root_edit, self.root_btn))
        form.addRow(QLabel("DayZ executable"), self._row_with_button(self.exe_edit, self.exe_btn))
        form.addRow(QLabel("BattlEye folder"), self._row_with_button(self.battleye_edit, self.battleye_btn))
        form.addRow(QLabel("Mission folder"), self._row_with_button(self.mission_edit, self.mission_btn))
        form.addRow(QLabel("Profiles folder"), self.profiles_edit)
        form.addRow(QLabel("Config file"), self.config_edit)
        form.addRow(QLabel("Port"), self.port_edit)

        layout.addWidget(paths_box)

        options_box = QGroupBox("Launch options")
        options_layout = QGridLayout(options_box)
        self.use_dologs = QCheckBox("-dologs")
        self.use_adminlog = QCheckBox("-adminlog")
        self.use_netlog = QCheckBox("-netlog")
        self.use_freezecheck = QCheckBox("-freezecheck")
        self.use_dologs.setChecked(True)
        self.use_adminlog.setChecked(True)
        self.use_netlog.setChecked(True)
        self.use_freezecheck.setChecked(True)

        options_layout.addWidget(self.use_dologs, 0, 0)
        options_layout.addWidget(self.use_adminlog, 0, 1)
        options_layout.addWidget(self.use_netlog, 0, 2)
        options_layout.addWidget(self.use_freezecheck, 0, 3)

        layout.addWidget(options_box)

        btn_row = QHBoxLayout()
        self.detect_mods_btn = QPushButton("Detect Mods")
        self.generate_bat_btn = QPushButton("Generate start.bat")
        self.start_server_btn = QPushButton("Start Server")
        self.stop_server_btn = QPushButton("Stop Server")
        self.restart_server_btn = QPushButton("Restart Server")
        self.open_root_btn = QPushButton("Open Root")
        btn_row.addWidget(self.detect_mods_btn)
        btn_row.addWidget(self.generate_bat_btn)
        btn_row.addWidget(self.start_server_btn)
        btn_row.addWidget(self.stop_server_btn)
        btn_row.addWidget(self.restart_server_btn)
        btn_row.addWidget(self.open_root_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        preview_box = QGroupBox("Generated command preview")
        preview_layout = QVBoxLayout(preview_box)
        self.command_preview = QTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMinimumHeight(170)
        preview_layout.addWidget(self.command_preview)
        layout.addWidget(preview_box, 1)

    def _build_mods_tab(self) -> None:
        layout = QVBoxLayout(self.mods_tab)

        info = QLabel(
            "Drag mods between lists or use the buttons. Available mods are detected from folders that start with @ in the server root."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        splitter = QSplitter(Qt.Horizontal)

        self.available_mods, self.available_hint, available_box = self._list_group("Available mods")
        self.client_mods, self.client_hint, client_box = self._list_group("Client mods")
        self.server_mods, self.server_hint, server_box = self._list_group("Server-side mods")

        splitter.addWidget(available_box)
        splitter.addWidget(client_box)
        splitter.addWidget(server_box)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        layout.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        self.to_client_btn = QPushButton("→ Client")
        self.to_server_btn = QPushButton("→ Server")
        self.remove_client_btn = QPushButton("Remove from Client")
        self.remove_server_btn = QPushButton("Remove from Server")
        self.auto_classify_btn = QPushButton("Auto-suggest server mods")
        self.clear_mods_btn = QPushButton("Clear selections")
        buttons.addWidget(self.to_client_btn)
        buttons.addWidget(self.to_server_btn)
        buttons.addWidget(self.remove_client_btn)
        buttons.addWidget(self.remove_server_btn)
        buttons.addWidget(self.auto_classify_btn)
        buttons.addWidget(self.clear_mods_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        foot = QLabel(
            "There is no perfect automatic detection for server-side only mods. Use the Server Mods column for any mod that must load on the server."
        )
        foot.setWordWrap(True)
        layout.addWidget(foot)

    def _build_banlist_tab(self) -> None:
        layout = QVBoxLayout(self.banlist_tab)
        top = QHBoxLayout()
        self.banlist_path_edit = QLineEdit()
        self.banlist_browse_btn = QPushButton("Browse banlist.txt")
        self.load_banlist_btn = QPushButton("Load")
        self.save_banlist_btn = QPushButton("Save")
        top.addWidget(QLabel("Banlist file"))
        top.addWidget(self.banlist_path_edit, 1)
        top.addWidget(self.banlist_browse_btn)
        top.addWidget(self.load_banlist_btn)
        top.addWidget(self.save_banlist_btn)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.banlist_entries = QListWidget()
        self.banlist_entries.setSelectionMode(QAbstractItemView.ExtendedSelection)
        left_layout.addWidget(self.banlist_entries, 1)

        actions = QHBoxLayout()
        self.add_ban_btn = QPushButton("Add")
        self.edit_ban_btn = QPushButton("Edit")
        self.del_ban_btn = QPushButton("Delete")
        self.up_ban_btn = QPushButton("Up")
        self.down_ban_btn = QPushButton("Down")
        actions.addWidget(self.add_ban_btn)
        actions.addWidget(self.edit_ban_btn)
        actions.addWidget(self.del_ban_btn)
        actions.addWidget(self.up_ban_btn)
        actions.addWidget(self.down_ban_btn)
        actions.addStretch(1)
        left_layout.addLayout(actions)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.ban_raw = QTextEdit()
        self.ban_raw.setPlaceholderText("Raw banlist preview / edit area")
        self.ban_raw.setMinimumWidth(420)
        right_layout.addWidget(self.ban_raw, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.ban_note = QLabel("Load from BattlEye\\banlist.txt, edit entries, then save back.")
        self.ban_note.setWordWrap(True)
        layout.addWidget(self.ban_note)

    def _build_schedule_tab(self) -> None:
        layout = QVBoxLayout(self.schedule_tab)

        mode_box = QGroupBox("Restart plan")
        mode_layout = QGridLayout(mode_box)
        self.hours_radio = QRadioButton("Every N hours")
        self.days_radio = QRadioButton("Every N days")
        self.fixed_radio = QRadioButton("Fixed daily times")
        self.hours_radio.setChecked(True)

        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(1, 72)
        self.hours_spin.setValue(6)
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 30)
        self.days_spin.setValue(1)
        self.fixed_times_edit = QLineEdit(", ".join(DEFAULT_FIXED_TIMES))
        self.fixed_times_edit.setPlaceholderText("00:00, 06:00, 12:00, 18:00")

        mode_layout.addWidget(self.hours_radio, 0, 0)
        mode_layout.addWidget(self.hours_spin, 0, 1)
        mode_layout.addWidget(QLabel("hours"), 0, 2)
        mode_layout.addWidget(self.days_radio, 1, 0)
        mode_layout.addWidget(self.days_spin, 1, 1)
        mode_layout.addWidget(QLabel("days"), 1, 2)
        mode_layout.addWidget(self.fixed_radio, 2, 0)
        mode_layout.addWidget(self.fixed_times_edit, 2, 1, 1, 2)

        layout.addWidget(mode_box)

        notif_box = QGroupBox("Notification offsets")
        notif_layout = QHBoxLayout(notif_box)
        self.mark_15 = QCheckBox("15 min")
        self.mark_10 = QCheckBox("10 min")
        self.mark_5 = QCheckBox("5 min")
        self.mark_1 = QCheckBox("1 min")
        for cb in (self.mark_15, self.mark_10, self.mark_5, self.mark_1):
            cb.setChecked(True)
            notif_layout.addWidget(cb)
        notif_layout.addStretch(1)
        layout.addWidget(notif_box)

        controls = QHBoxLayout()
        self.preview_schedule_btn = QPushButton("Preview next restarts")
        self.export_messages_btn = QPushButton("Export messages.json / messages.xml")
        self.arm_scheduler_btn = QPushButton("Arm scheduler")
        self.disarm_scheduler_btn = QPushButton("Disarm scheduler")
        controls.addWidget(self.preview_schedule_btn)
        controls.addWidget(self.export_messages_btn)
        controls.addWidget(self.arm_scheduler_btn)
        controls.addWidget(self.disarm_scheduler_btn)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.schedule_preview = QTableWidget(0, 3)
        self.schedule_preview.setHorizontalHeaderLabels(["Restart time", "Notification", "Text"])
        self.schedule_preview.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.schedule_preview, 1)

        help_text = QLabel(
            "If you choose 6 hours, the app aligns restarts to clock times (00:00 / 06:00 / 12:00 / 18:00) when possible so they match your message schedule."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

    def _build_validator_tab(self) -> None:
        layout = QVBoxLayout(self.validator_tab)

        top = QHBoxLayout()
        self.xml_root_edit = QLineEdit()
        self.xml_root_btn = QPushButton("Choose mpmissions folder")
        self.scan_xml_btn = QPushButton("Scan XML")
        self.export_xml_report_btn = QPushButton("Export report")
        top.addWidget(QLabel("Scan root"))
        top.addWidget(self.xml_root_edit, 1)
        top.addWidget(self.xml_root_btn)
        top.addWidget(self.scan_xml_btn)
        top.addWidget(self.export_xml_report_btn)
        layout.addLayout(top)

        self.xml_table = QTableWidget(0, 4)
        self.xml_table.setHorizontalHeaderLabels(["File", "Line", "Column", "Error"])
        self.xml_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.xml_table, 1)

        self.xml_summary = QLabel("No scan run yet.")
        self.xml_summary.setWordWrap(True)
        layout.addWidget(self.xml_summary)

    def _build_logs_tab(self) -> None:
        layout = QVBoxLayout(self.logs_tab)
        row = QHBoxLayout()
        self.clear_logs_btn = QPushButton("Clear logs")
        row.addWidget(self.clear_logs_btn)
        row.addStretch(1)
        layout.addLayout(row)
        self.logs = LogBox()
        layout.addWidget(self.logs, 1)

    def _list_group(self, title: str) -> Tuple[QListWidget, QLabel, QWidget]:
        box = QGroupBox(title)
        v = QVBoxLayout(box)
        hint = QLabel("Drag items here")
        hint.setWordWrap(True)
        hint.setObjectName("SmallHint")
        lst = QListWidget()
        lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lst.setDragEnabled(True)
        lst.setAcceptDrops(True)
        lst.setDropIndicatorShown(True)
        lst.setDragDropMode(QAbstractItemView.DragDrop)
        lst.setDefaultDropAction(Qt.MoveAction)
        v.addWidget(hint)
        v.addWidget(lst, 1)
        return lst, hint, box

    def _row_with_button(self, edit: QLineEdit, button: QPushButton) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit, 1)
        layout.addWidget(button)
        return widget

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")
            app.setFont(QFont("Segoe UI", 10))

        self.setStyleSheet(
            """
            QWidget {
                background: #0d1117;
                color: #e6edf3;
            }
            QFrame#HeaderCard, QFrame#FooterCard {
                background: #111822;
                border: 1px solid #1f2a3a;
                border-radius: 16px;
            }
            QGroupBox {
                border: 1px solid #30363d;
                border-radius: 14px;
                margin-top: 14px;
                padding-top: 14px;
                background: #111822;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            QTabWidget::pane {
                border: 1px solid #30363d;
                border-radius: 14px;
                background: #111822;
            }
            QTabBar::tab {
                background: #161b22;
                padding: 10px 16px;
                margin-right: 4px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                border: 1px solid #30363d;
            }
            QTabBar::tab:selected {
                background: #233044;
            }
            QLineEdit, QTextEdit, QListWidget, QTableWidget, QSpinBox {
                background: #0b1016;
                border: 1px solid #30363d;
                border-radius: 10px;
                padding: 8px;
                selection-background-color: #4f8cff;
                selection-color: white;
            }
            QPushButton {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 10px;
                padding: 9px 12px;
            }
            QPushButton:hover {
                background: #1f2630;
            }
            QPushButton:pressed {
                background: #2a3240;
            }
            QLabel#TitleLabel {
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#SubtitleLabel {
                color: #8b949e;
            }
            QLabel#StatusPill {
                background: #1b2230;
                border: 1px solid #30363d;
                border-radius: 14px;
                padding: 10px 14px;
                font-weight: 700;
            }
            QLabel#SmallHint {
                color: #8b949e;
            }
            QPushButton#DiscordSupport {
                border-radius: 999px;
                padding: 10px 16px;
            }
            """
        )

    def _wire_actions(self) -> None:
        self.root_btn.clicked.connect(lambda: self._browse_dir(self.server_root_edit))
        self.exe_btn.clicked.connect(lambda: self._browse_file(self.exe_edit, "DayZServer_x64.exe (*.exe)"))
        self.battleye_btn.clicked.connect(lambda: self._browse_dir(self.battleye_edit))
        self.mission_btn.clicked.connect(lambda: self._browse_dir(self.mission_edit))
        self.detect_mods_btn.clicked.connect(self.detect_mods)
        self.generate_bat_btn.clicked.connect(self.generate_bat)
        self.start_server_btn.clicked.connect(self.start_server)
        self.stop_server_btn.clicked.connect(self.stop_server)
        self.restart_server_btn.clicked.connect(self.restart_server)
        self.open_root_btn.clicked.connect(self.open_root_folder)

        self.to_client_btn.clicked.connect(lambda: self._move_selected(self.available_mods, self.client_mods))
        self.to_server_btn.clicked.connect(lambda: self._move_selected(self.available_mods, self.server_mods))
        self.remove_client_btn.clicked.connect(lambda: self._move_selected(self.client_mods, self.available_mods))
        self.remove_server_btn.clicked.connect(lambda: self._move_selected(self.server_mods, self.available_mods))
        self.auto_classify_btn.clicked.connect(self.auto_suggest_server_mods)
        self.clear_mods_btn.clicked.connect(self.clear_mods)

        self.banlist_browse_btn.clicked.connect(lambda: self._browse_file(self.banlist_path_edit, "Text files (*.txt);;All files (*.*)"))
        self.load_banlist_btn.clicked.connect(self.load_banlist)
        self.save_banlist_btn.clicked.connect(self.save_banlist)
        self.add_ban_btn.clicked.connect(self.add_ban_entry)
        self.edit_ban_btn.clicked.connect(self.edit_ban_entry)
        self.del_ban_btn.clicked.connect(self.delete_ban_entry)
        self.up_ban_btn.clicked.connect(lambda: self.move_ban_entry(-1))
        self.down_ban_btn.clicked.connect(lambda: self.move_ban_entry(1))

        self.preview_schedule_btn.clicked.connect(self.refresh_schedule_preview)
        self.export_messages_btn.clicked.connect(self.export_messages_file)
        self.arm_scheduler_btn.clicked.connect(self.arm_scheduler)
        self.disarm_scheduler_btn.clicked.connect(self.disarm_scheduler)

        self.xml_root_btn.clicked.connect(lambda: self._browse_dir(self.xml_root_edit))
        self.scan_xml_btn.clicked.connect(self.scan_xml_files)
        self.export_xml_report_btn.clicked.connect(self.export_xml_report)

        self.clear_logs_btn.clicked.connect(self.logs.clear)

        # Persist on edits
        for w in (
            self.server_root_edit,
            self.exe_edit,
            self.battleye_edit,
            self.mission_edit,
            self.profiles_edit,
            self.config_edit,
            self.port_edit,
            self.banlist_path_edit,
            self.xml_root_edit,
            self.fixed_times_edit,
        ):
            w.textChanged.connect(self._persist_ui_state)

        for w in (
            self.use_dologs,
            self.use_adminlog,
            self.use_netlog,
            self.use_freezecheck,
            self.hours_radio,
            self.days_radio,
            self.fixed_radio,
            self.mark_15,
            self.mark_10,
            self.mark_5,
            self.mark_1,
        ):
            w.toggled.connect(self._persist_ui_state)

        self.hours_spin.valueChanged.connect(self._persist_ui_state)
        self.days_spin.valueChanged.connect(self._persist_ui_state)

        # Drag/drop between lists still persists when selection changes manually
        self.available_mods.itemDoubleClicked.connect(lambda item: self._move_item_between(item, self.available_mods, self.client_mods))
        self.client_mods.itemDoubleClicked.connect(lambda item: self._move_item_between(item, self.client_mods, self.available_mods))
        self.server_mods.itemDoubleClicked.connect(lambda item: self._move_item_between(item, self.server_mods, self.available_mods))

    def _initial_scan_if_possible(self) -> None:
        if self.server_root_edit.text().strip():
            self.detect_mods(silent=True)
        if self.battleye_edit.text().strip():
            self.load_banlist(silent=True)
        self.refresh_schedule_preview()

    # ------------------------------ Settings ------------------------------
    def _load_settings(self) -> dict:
        try:
            if SETTINGS_FILE.exists():
                return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_settings(self) -> None:
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps(self._collect_settings(), indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            self._log(f"Settings save failed: {exc}")

    def _collect_settings(self) -> dict:
        return {
            "server_root": self.server_root_edit.text().strip(),
            "exe_path": self.exe_edit.text().strip(),
            "battleye_path": self.battleye_edit.text().strip(),
            "mission_path": self.mission_edit.text().strip(),
            "profiles": self.profiles_edit.text().strip(),
            "config": self.config_edit.text().strip(),
            "port": self.port_edit.text().strip(),
            "banlist_path": self.banlist_path_edit.text().strip(),
            "xml_root": self.xml_root_edit.text().strip(),
            "use_dologs": self.use_dologs.isChecked(),
            "use_adminlog": self.use_adminlog.isChecked(),
            "use_netlog": self.use_netlog.isChecked(),
            "use_freezecheck": self.use_freezecheck.isChecked(),
            "restart_mode": self._restart_mode(),
            "hours": self.hours_spin.value(),
            "days": self.days_spin.value(),
            "fixed_times": self.fixed_times_edit.text().strip(),
            "marks": {
                "15": self.mark_15.isChecked(),
                "10": self.mark_10.isChecked(),
                "5": self.mark_5.isChecked(),
                "1": self.mark_1.isChecked(),
            },
            "client_mods": self._list_items(self.client_mods),
            "server_mods": self._list_items(self.server_mods),
            "banlist_entries": self._list_items(self.banlist_entries),
        }

    def _restore_settings_to_ui(self) -> None:
        s = self.settings
        self.server_root_edit.setText(s.get("server_root", ""))
        self.exe_edit.setText(s.get("exe_path", ""))
        self.battleye_edit.setText(s.get("battleye_path", ""))
        self.mission_edit.setText(s.get("mission_path", ""))
        self.profiles_edit.setText(s.get("profiles", "profiles"))
        self.config_edit.setText(s.get("config", "serverDZ.cfg"))
        self.port_edit.setText(str(s.get("port", "2302")))
        self.banlist_path_edit.setText(s.get("banlist_path", ""))
        self.xml_root_edit.setText(s.get("xml_root", ""))
        self.use_dologs.setChecked(bool(s.get("use_dologs", True)))
        self.use_adminlog.setChecked(bool(s.get("use_adminlog", True)))
        self.use_netlog.setChecked(bool(s.get("use_netlog", True)))
        self.use_freezecheck.setChecked(bool(s.get("use_freezecheck", True)))

        mode = s.get("restart_mode", "hours")
        if mode == "days":
            self.days_radio.setChecked(True)
        elif mode == "fixed":
            self.fixed_radio.setChecked(True)
        else:
            self.hours_radio.setChecked(True)
        self.hours_spin.setValue(int(s.get("hours", 6)))
        self.days_spin.setValue(int(s.get("days", 1)))
        self.fixed_times_edit.setText(s.get("fixed_times", ", ".join(DEFAULT_FIXED_TIMES)))

        marks = s.get("marks", {})
        self.mark_15.setChecked(bool(marks.get("15", True)))
        self.mark_10.setChecked(bool(marks.get("10", True)))
        self.mark_5.setChecked(bool(marks.get("5", True)))
        self.mark_1.setChecked(bool(marks.get("1", True)))

        self.client_mods.clear()
        for item in s.get("client_mods", []):
            self.client_mods.addItem(item)
        self.server_mods.clear()
        for item in s.get("server_mods", []):
            self.server_mods.addItem(item)
        self.banlist_entries.clear()
        for item in s.get("banlist_entries", []):
            self.banlist_entries.addItem(item)
        self._sync_ban_raw_from_list()
        self._update_command_preview()

    def _persist_ui_state(self) -> None:
        self._save_settings()
        self._update_command_preview()

    # ------------------------------ Helpers ------------------------------
    def _log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.logs.write(f"[{stamp}] {message}")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        low = text.lower()
        if any(token in low for token in ("starting", "launching", "booting")):
            self.status_label.setStyleSheet("background:#3a3206;color:#ffd966;border:1px solid #8f7a19;border-radius:14px;padding:10px 14px;font-weight:700;")
        elif any(token in low for token in ("running", "started", "online", "up")):
            self.status_label.setStyleSheet("background:#12351f;color:#8fff9d;border:1px solid #1e6b39;border-radius:14px;padding:10px 14px;font-weight:700;")
        elif any(token in low for token in ("idle", "stopped", "off")):
            self.status_label.setStyleSheet("background:#4a1717;color:#ffb0b0;border:1px solid #7f2525;border-radius:14px;padding:10px 14px;font-weight:700;")
        else:
            self.status_label.setStyleSheet("background:#1b2230;color:#e6edf3;border:1px solid #30363d;border-radius:14px;padding:10px 14px;font-weight:700;")

    def _browse_dir(self, target: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose folder", target.text().strip() or str(Path.home()))
        if path:
            target.setText(path)

    def _browse_file(self, target: QLineEdit, filter_text: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose file", target.text().strip() or str(Path.home()), filter_text)
        if path:
            target.setText(path)

    def _list_items(self, widget: QListWidget) -> List[str]:
        return [widget.item(i).text() for i in range(widget.count())]

    def _list_has_text(self, widget: QListWidget, text: str) -> bool:
        return bool(widget.findItems(text, Qt.MatchExactly))

    def _remove_duplicates(self, widget: QListWidget) -> None:
        seen = set()
        keep = []
        for i in range(widget.count()):
            t = widget.item(i).text()
            if t not in seen:
                seen.add(t)
                keep.append(t)
        widget.clear()
        for t in keep:
            widget.addItem(t)

    def _move_selected(self, source: QListWidget, destination: QListWidget) -> None:
        texts = [item.text() for item in source.selectedItems()]
        for text in texts:
            if not self._list_has_text(destination, text):
                destination.addItem(text)
            matches = source.findItems(text, Qt.MatchExactly)
            for item in matches:
                if source.row(item) >= 0:
                    source.takeItem(source.row(item))
                    break
        self._persist_ui_state()

    def _move_item_between(self, item: QListWidgetItem, source: QListWidget, destination: QListWidget) -> None:
        text = item.text()
        if not self._list_has_text(destination, text):
            destination.addItem(text)
        row = source.row(item)
        if row >= 0:
            source.takeItem(row)
        self._persist_ui_state()

    def _restart_mode(self) -> str:
        if self.days_radio.isChecked():
            return "days"
        if self.fixed_radio.isChecked():
            return "fixed"
        return "hours"

    def _restart_timeout_seconds(self) -> int:
        mode = self._restart_mode()
        if mode == "days":
            return max(1, self.days_spin.value()) * 24 * 3600
        if mode == "fixed":
            return 0
        return max(1, self.hours_spin.value()) * 3600

    # ------------------------------ Mod detection ------------------------------
    def detect_mods(self, silent: bool = False) -> None:
        root = self.server_root_edit.text().strip()
        if not root:
            if not silent:
                QMessageBox.warning(self, "Missing server root", "Choose the DayZ server root folder first.")
            return

        base = Path(root)
        if not base.exists():
            if not silent:
                QMessageBox.warning(self, "Invalid path", "The selected server root does not exist.")
            return

        detected = []
        for child in sorted(base.iterdir(), key=lambda p: p.name.lower()):
            if child.is_dir() and child.name.startswith("@"):
                detected.append(child.name)

        current = set(self._list_items(self.client_mods)) | set(self._list_items(self.server_mods))
        self.available_mods.clear()
        for mod in detected:
            if mod not in current:
                self.available_mods.addItem(mod)

        self._remove_duplicates(self.client_mods)
        self._remove_duplicates(self.server_mods)
        self._update_mod_hints(len(detected), self.client_mods.count(), self.server_mods.count())
        self._update_command_preview()
        self._persist_ui_state()

        msg = f"Detected {len(detected)} @mods."
        if not silent:
            QMessageBox.information(self, "Mod scan complete", msg)
        self._log(msg)

    def auto_suggest_server_mods(self) -> None:
        root = self.server_root_edit.text().strip()
        if not root:
            QMessageBox.warning(self, "Missing server root", "Choose the DayZ server root folder first.")
            return
        base = Path(root)
        if not base.exists():
            QMessageBox.warning(self, "Invalid path", "The selected server root does not exist.")
            return

        suggestions = []
        source = self._list_items(self.client_mods) + self._list_items(self.available_mods)
        for mod in source:
            mod_dir = base / mod
            if not mod_dir.exists():
                continue
            lower = mod.lower()
            has_keys = (mod_dir / "keys").exists() or any(p.suffix.lower() == ".bikey" for p in mod_dir.rglob("*.bikey"))
            looks_serverish = any(token in lower for token in ["server", "battleye", "admin", "storage", "economy", "tool"])
            if has_keys or looks_serverish:
                suggestions.append(mod)

        if not suggestions:
            QMessageBox.information(self, "No suggestions", "No obvious server-side mods were found by heuristic.")
            return

        for mod in suggestions:
            if not self._list_has_text(self.server_mods, mod):
                self.server_mods.addItem(mod)
            for widget in (self.available_mods, self.client_mods):
                matches = widget.findItems(mod, Qt.MatchExactly)
                for item in matches:
                    widget.takeItem(widget.row(item))

        self._remove_duplicates(self.server_mods)
        self._update_command_preview()
        self._persist_ui_state()
        self._log(f"Suggested {len(suggestions)} server-side mods.")

    def clear_mods(self) -> None:
        self.available_mods.clear()
        self.client_mods.clear()
        self.server_mods.clear()
        self._persist_ui_state()
        self._update_mod_hints(0, 0, 0)

    def _update_mod_hints(self, total: int, client: int, server: int) -> None:
        self.available_hint.setText(f"Detected: {total}")
        self.client_hint.setText(f"Client selected: {client}")
        self.server_hint.setText(f"Server selected: {server}")

    # ------------------------------ Command / BAT generation ------------------------------
    def _compose_professional_bat(self, exe: str, args: List[str], working_dir: str) -> str:
        client_mods = ";".join(self._list_items(self.client_mods))
        server_mods = ";".join(self._list_items(self.server_mods))
        restart_timeout = max(0, self._restart_timeout_seconds())
        server_fps = 200
        profile_name = self.profiles_edit.text().strip() or "DayZServer"
        config_name = self.config_edit.text().strip() or "serverDZ.cfg"
        port = self.port_edit.text().strip() or "2302"
        exe_name = Path(exe).name or "DayZServer_x64.exe"
        work_dir = str(Path(working_dir))
        be_dir = self.battleye_edit.text().strip()
        bec_exe = "bec.exe"
        additional_params = "-doLogs -adminLog -netLog -freezeCheck -filePatching"

        return f"""@echo off
:: ============================================================================
:: BrutalZ Server Start Script
:: Generated by BrutalZ Control Center 🩸
:: ============================================================================
setlocal EnableExtensions EnableDelayedExpansion
color 0A
TITLE BrutalZ Server 🩸

echo MESSAGE: Pre startup initialised

:: Command window name, does not affect anything else
SET S_NAME=BrutalZ Server

:: Path to the DayZ server executable
SET EXE_PATH="{work_dir}"
:: Name of executable
SET EXE="{exe_name}"

:: Logical CPU cores
SET CPU_CORES=%NUMBER_OF_PROCESSORS%

:: List of client side mods
SET MODLIST=-mod={client_mods}

:: List of server side mods
SET SERVERMODLIST=-serverMod={server_mods}

:: Set the port number of the DayZ server
SET PORT={port}

:: Set the DayZ config file
SET CONFIG={config_name}

:: Profile name
SET PROFILE={profile_name}

:: Restart timeout in seconds (6 hours by default if you selected that mode)
SET RESTART_TIMEOUT={restart_timeout}

:: FPS limit for the server
SET SERVER_FPS_LIMIT={server_fps}

:: Enables BEC
SET USE_BEC={'true' if be_dir else 'false'}
:: Path of the BattleEye Client (BEC)
SET BEC_EXE_PATH="{be_dir or 'changeme'}"
:: Name of BEC executable
SET BEC_EXE="{bec_exe}"

:: Extra launch parameters
SET ADDITIONAL_PARAMETERS={additional_params}

:: ============================================================================
:: DO NOT CHANGE ANYTHING BELOW THIS POINT UNLESS YOU KNOW WHAT YOU ARE DOING
:: ============================================================================

TITLE %S_NAME%
SET ERROR=

ECHO.
ECHO MESSAGE: Starting vars checks

IF %PORT% ==0 (
	SET ERROR=PORT
	GOTO CONFIG_ERROR
)
IF %SERVER_FPS_LIMIT% GTR 200 (
	SET ERROR=SERVER_FPS_LIMIT
	GOTO CONFIG_ERROR
)
IF %SERVER_FPS_LIMIT% LEQ 1 (
	SET ERROR=SERVER_FPS_LIMIT
	GOTO CONFIG_ERROR
)
IF %USE_BEC% ==false (
	GOTO NO_BEC
)
IF %BEC_EXE_PATH% =="changeme" (
	SET ERROR=BEC_EXE_PATH
	GOTO CONFIG_ERROR
)
:NO_BEC

ECHO.
ECHO MESSAGE: Variable checks completed
SET LOOPS=0

:LOOP
TASKLIST /FI IMAGENAME eq %EXE% 2>NUL | find /I /N %EXE% >NUL
IF %ERRORLEVEL% == 0 GOTO LOOP

ECHO MESSAGE: Starting server at: %DATE%, %TIME%
IF %LOOPS% NEQ 0 (
	ECHO MESSAGE: Restarts: %LOOPS%
)

CD /D %EXE_PATH%
START "%S_NAME%" /MIN /D %EXE_PATH% %EXE% -profiles=%PROFILE% -config=%CONFIG% -port=%PORT% -cpuCount=%CPU_CORES% -limitFPS=%SERVER_FPS_LIMIT% %MODLIST% %SERVERMODLIST% %ADDITIONAL_PARAMETERS%
ECHO MESSAGE: To stop the server, close this window then the server process

IF %USE_BEC% ==true (
	ECHO MESSAGE: Starting BEC
	START "%S_NAME%" /MIN %BEC_EXE_PATH%\%BEC_EXE%
)

IF %RESTART_TIMEOUT% ==0 (
	GOTO RESTART_SKIP
)
TIMEOUT /T %RESTART_TIMEOUT% /NOBREAK >NUL
TASKKILL /IM %EXE% /F
IF %USE_BEC% ==true (
	TASKKILL /IM %BEC_EXE% /F
)

:RESTART_SKIP
TIMEOUT /T 30 /NOBREAK >NUL
ECHO.

:LOOPING
SET /A LOOPS+=1
TIMEOUT /T 5 /NOBREAK >NUL
TASKLIST /FI IMAGENAME eq %EXE% 2>NUL | find /I /N %EXE% >NUL
IF %ERRORLEVEL%==0 GOTO LOOPING
GOTO LOOP

:CONFIG_ERROR
COLOR C
ECHO ERROR: %ERROR% not set correctly, please check the config
PAUSE
COLOR F
endlocal
"""

    def build_launch_command(self) -> Tuple[str, List[str], str]:
        exe = self.exe_edit.text().strip()
        root = self.server_root_edit.text().strip()
        if not exe:
            exe = str(Path(root) / "DayZServer_x64.exe") if root else "DayZServer_x64.exe"

        client_mods = self._list_items(self.client_mods)
        server_mods = self._list_items(self.server_mods)

        args = []
        cfg = self.config_edit.text().strip()
        profiles = self.profiles_edit.text().strip() or "profiles"
        port = self.port_edit.text().strip() or "2302"

        args.append(f'-config="{cfg}"')
        args.append(f'-port={port}')
        args.append(f'-profiles="{profiles}"')

        if self.use_dologs.isChecked():
            args.append("-dologs")
        if self.use_adminlog.isChecked():
            args.append("-adminlog")
        if self.use_netlog.isChecked():
            args.append("-netlog")
        if self.use_freezecheck.isChecked():
            args.append("-freezecheck")

        if client_mods:
            args.append(f'-mod={";".join(client_mods)}')
        if server_mods:
            args.append(f'-serverMod={";".join(server_mods)}')

        working_dir = root if root else str(Path(exe).resolve().parent)
        return exe, args, working_dir

    def _update_command_preview(self) -> None:
        try:
            exe, args, working_dir = self.build_launch_command()
            lines = [
                "# Launch preview",
                f"Working dir: {working_dir}",
                f"Executable: {exe}",
                "Arguments: " + " ".join(args),
            ]
            self.command_preview.setPlainText("\n".join(lines))
        except Exception:
            self.command_preview.setPlainText("Unable to build command preview yet.")

    def generate_bat(self) -> None:
        exe, args, working_dir = self.build_launch_command()
        default_name = Path(self.server_root_edit.text().strip() or working_dir) / "start.bat"
        path, _ = QFileDialog.getSaveFileName(self, "Save start.bat", str(default_name), "Batch files (*.bat)")
        if not path:
            return

        bat_text = self._compose_professional_bat(exe, args, working_dir)
        with open(path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(bat_text)
        self._log(f"start.bat written to {path}")
        QMessageBox.information(self, "BAT generated", f"Saved to:\n{path}")

    # ------------------------------ Server process control ------------------------------
    def start_server(self) -> None:
        try:
            exe, args, working_dir = self.build_launch_command()
            exe_path = Path(exe)
            if not exe_path.exists():
                raise FileNotFoundError(f"Executable not found: {exe}")

            if self.server_process and self.server_process.state() != QProcess.NotRunning:
                QMessageBox.information(self, "Server already running", "The server process is already running from this app.")
                return

            self.server_process = QProcess(self)
            self.server_process.setProgram(str(exe_path))
            self.server_process.setArguments(args)
            self.server_process.setWorkingDirectory(working_dir)
            self.server_process.readyReadStandardOutput.connect(self._read_server_stdout)
            self.server_process.readyReadStandardError.connect(self._read_server_stderr)
            self.server_process.started.connect(lambda: self._on_server_started(exe_path, args))
            self.server_process.finished.connect(self._on_server_finished)
            self.server_process.start()

            self._set_status("Status: Starting server...")
            self._log("Server start requested.")
        except Exception as exc:
            QMessageBox.critical(self, "Start failed", str(exc))
            self._log(f"Start failed: {exc}")

    def stop_server(self) -> None:
        proc = self.server_process
        if not proc or proc.state() == QProcess.NotRunning:
            self._log("No server process to stop.")
            self._set_status("Status: Idle")
            return
        self._log("Stopping server process...")
        proc.terminate()
        if not proc.waitForFinished(5000):
            self._log("Terminate timeout; killing process.")
            proc.kill()
            proc.waitForFinished(5000)
        self._set_status("Status: Stopped")

    def restart_server(self) -> None:
        self._log("Restart requested.")
        self.stop_server()
        QTimer.singleShot(1500, self.start_server)

    def _on_server_started(self, exe_path: Path, args: List[str]) -> None:
        self._set_status("Status: Running")
        self._log(f"Server started: {exe_path.name}")
        self._log("Arguments: " + " ".join(args))

    def _on_server_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._log(f"Server finished. exit_code={exit_code}, exit_status={exit_status.name}")
        if self.scheduler_armed:
            self._set_status("Status: Restarting by scheduler")
        else:
            self._set_status("Status: Idle")

    def _read_server_stdout(self) -> None:
        if not self.server_process:
            return
        data = bytes(self.server_process.readAllStandardOutput()).decode(errors="replace")
        if data.strip():
            for line in data.splitlines():
                self._log(f"[SERVER] {line}")

    def _read_server_stderr(self) -> None:
        if not self.server_process:
            return
        data = bytes(self.server_process.readAllStandardError()).decode(errors="replace")
        if data.strip():
            for line in data.splitlines():
                self._log(f"[SERVER-ERR] {line}")

    def open_root_folder(self) -> None:
        root = self.server_root_edit.text().strip()
        if not root:
            QMessageBox.warning(self, "Missing server root", "Choose the DayZ server root folder first.")
            return
        path = Path(root)
        if not path.exists():
            QMessageBox.warning(self, "Invalid path", "The selected server root does not exist.")
            return
        os.startfile(str(path))

    # ------------------------------ Banlist ------------------------------
    def load_banlist(self, silent: bool = False) -> None:
        path = self.banlist_path_edit.text().strip()
        if not path:
            if not silent:
                QMessageBox.warning(self, "Missing banlist path", "Choose BattlEye\\banlist.txt first.")
            return
        p = Path(path)
        if not p.exists():
            if not silent:
                QMessageBox.warning(self, "File not found", "banlist.txt was not found.")
            return
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
            self.ban_raw.setPlainText(raw)
            self.banlist_entries.clear()
            for line in raw.splitlines():
                if line.strip():
                    self.banlist_entries.addItem(line.rstrip("\r\n"))
            self._persist_ui_state()
            self._log(f"Loaded banlist from {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", str(exc))

    def save_banlist(self) -> None:
        path = self.banlist_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Missing banlist path", "Choose BattlEye\\banlist.txt first.")
            return
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            lines = self._list_items(self.banlist_entries)
            text = "\n".join(lines) + ("\n" if lines else "")
            p.write_text(text, encoding="utf-8")
            self.ban_raw.setPlainText(text)
            self._persist_ui_state()
            self._log(f"Saved banlist to {path}")
            QMessageBox.information(self, "Saved", "banlist.txt was saved successfully.")
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def add_ban_entry(self) -> None:
        text, ok = self._prompt_text("Add ban entry", "Paste the new ban line:")
        if ok and text.strip():
            self.banlist_entries.addItem(text.strip())
            self._sync_ban_raw_from_list()
            self._persist_ui_state()

    def edit_ban_entry(self) -> None:
        item = self.banlist_entries.currentItem()
        if not item:
            return
        text, ok = self._prompt_text("Edit ban entry", "Edit the ban line:", item.text())
        if ok and text.strip():
            item.setText(text.strip())
            self._sync_ban_raw_from_list()
            self._persist_ui_state()

    def delete_ban_entry(self) -> None:
        row = self.banlist_entries.currentRow()
        if row >= 0:
            self.banlist_entries.takeItem(row)
            self._sync_ban_raw_from_list()
            self._persist_ui_state()

    def move_ban_entry(self, delta: int) -> None:
        row = self.banlist_entries.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self.banlist_entries.count():
            return
        item = self.banlist_entries.takeItem(row)
        self.banlist_entries.insertItem(new_row, item)
        self.banlist_entries.setCurrentRow(new_row)
        self._sync_ban_raw_from_list()
        self._persist_ui_state()

    def _sync_ban_raw_from_list(self) -> None:
        text = "\n".join(self._list_items(self.banlist_entries))
        if text:
            text += "\n"
        self.ban_raw.setPlainText(text)

    def _prompt_text(self, title: str, label: str, default: str = "") -> Tuple[str, bool]:
        from PySide6.QtWidgets import QInputDialog

        return QInputDialog.getText(self, title, label, text=default)

    # ------------------------------ Scheduler ------------------------------
    def _restart_config(self) -> RestartConfig:
        return RestartConfig(
            mode=self._restart_mode(),
            interval_value=self.hours_spin.value() if self.hours_radio.isChecked() else self.days_spin.value(),
            fixed_times=[x.strip() for x in self.fixed_times_edit.text().split(",") if x.strip()],
        )

    def _parse_fixed_times(self, raw: List[str]) -> List[dtime]:
        parsed: List[dtime] = []
        for token in raw:
            try:
                hh, mm = token.split(":", 1)
                parsed.append(dtime(int(hh), int(mm), 0))
            except Exception:
                continue
        return sorted(parsed)

    def _next_restart_after(self, now: datetime, cfg: RestartConfig) -> Optional[datetime]:
        if cfg.mode == "days":
            return (now + timedelta(days=max(1, cfg.interval_value))).replace(microsecond=0)

        if cfg.mode == "hours":
            step = max(1, cfg.interval_value)
            if 24 % step == 0:
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
                hours = list(range(0, 24, step))
                candidates = [midnight + timedelta(hours=h) for h in hours]
                for c in candidates:
                    if c > now:
                        return c
                return midnight + timedelta(days=1)
            return (now + timedelta(hours=step)).replace(microsecond=0)

        times = self._parse_fixed_times(cfg.fixed_times)
        if not times:
            return None
        today = now.date()
        for offset in range(0, 8):
            day = today + timedelta(days=offset)
            for t in times:
                candidate = datetime.combine(day, t)
                if candidate > now:
                    return candidate
        return None

    def _notification_marks(self) -> List[int]:
        marks = []
        if self.mark_15.isChecked():
            marks.append(15)
        if self.mark_10.isChecked():
            marks.append(10)
        if self.mark_5.isChecked():
            marks.append(5)
        if self.mark_1.isChecked():
            marks.append(1)
        return marks

    def _utc_offset_hours(self) -> int:
        offset = datetime.now().astimezone().utcoffset()
        if offset is None:
            return 0
        return int(offset.total_seconds() // 3600)

    def _build_notification_rows(self, horizon_count: int = 8) -> List[dict]:
        now = datetime.now().replace(microsecond=0)
        cfg = self._restart_config()
        marks = self._notification_marks()
        rows = []
        restart = self._next_restart_after(now - timedelta(seconds=1), cfg)
        seen = 0
        while restart and seen < horizon_count:
            seen += 1
            for m in sorted(marks, reverse=True):
                t = restart - timedelta(minutes=m)
                if t <= now:
                    continue
                rows.append(
                    {
                        "restart": restart,
                        "notify": t,
                        "minutes": m,
                        "title": "RESTART",
                        "text": f"Server restart in {m} minute{'s' if m != 1 else ''}.",
                        "icon": "Info",
                        "color": "#FF0000",
                    }
                )
            restart = self._next_restart_after(restart + timedelta(seconds=1), cfg)
        rows.sort(key=lambda x: x["notify"])
        return rows

    def refresh_schedule_preview(self) -> None:
        try:
            rows = self._build_notification_rows()
            self.schedule_preview.setRowCount(len(rows))
            for r, row in enumerate(rows):
                self.schedule_preview.setItem(r, 0, QTableWidgetItem(row["restart"].strftime("%Y-%m-%d %H:%M:%S")))
                self.schedule_preview.setItem(r, 1, QTableWidgetItem(row["notify"].strftime("%H:%M:%S") + f" (-{row['minutes']}m)"))
                self.schedule_preview.setItem(r, 2, QTableWidgetItem(row["text"]))
            self.next_restart_dt = rows[0]["restart"] if rows else None
            self._log(f"Preview generated: {len(rows)} notification rows.")
            self._update_scheduler_status_label()
        except Exception as exc:
            self._log(f"Schedule preview failed: {exc}")
            self.schedule_preview.setRowCount(0)

    def export_messages_file(self) -> None:
        rows = self._build_notification_rows()
        if not rows:
            QMessageBox.warning(self, "No schedule", "Could not build notifications. Check the schedule settings.")
            return

        default_name = Path(self.server_root_edit.text().strip() or str(Path.home())) / "messages.xml"
        path, _ = QFileDialog.getSaveFileName(self, "Save restart messages file", str(default_name), "JSON files (*.json *.xml);;All files (*.*)")
        if not path:
            return

        payload = {
            "m_Version": 2,
            "Enabled": 1,
            "UTC": self._utc_offset_hours(),
            "UseMissionTime": 0,
            "Notifications": [],
        }

        for row in rows:
            payload["Notifications"].append(
                {
                    "Hour": row["notify"].hour,
                    "Minute": row["notify"].minute,
                    "Second": row["notify"].second,
                    "Title": row["title"],
                    "Text": row["text"],
                    "Icon": row["icon"],
                    "Color": row["color"],
                }
            )

        try:
            Path(path).write_text(json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8")
            self._log(f"Exported restart messages to {path}")
            QMessageBox.information(self, "Exported", f"Messages file saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def arm_scheduler(self) -> None:
        self.scheduler_armed = True
        self.notified_marks.clear()
        self.refresh_schedule_preview()
        if not self.scheduler_timer.isActive():
            self.scheduler_timer.start()
        self._set_status("Status: Scheduler armed")
        self._log("Scheduler armed.")

    def disarm_scheduler(self) -> None:
        self.scheduler_armed = False
        self.scheduler_timer.stop()
        self.notified_marks.clear()
        self._set_status("Status: Idle")
        self._log("Scheduler disarmed.")

    def _tick_scheduler(self) -> None:
        if not self.scheduler_armed:
            return

        now = datetime.now().replace(microsecond=0)
        cfg = self._restart_config()
        if self.next_restart_dt is None:
            self.next_restart_dt = self._next_restart_after(now, cfg)
            self.notified_marks.clear()

        if self.next_restart_dt is None:
            self._set_status("Status: Scheduler armed, but no valid next restart")
            return

        seconds_left = max(0, int((self.next_restart_dt - now).total_seconds()))
        for m in self._notification_marks():
            if m in self.notified_marks:
                continue
            if seconds_left <= m * 60:
                self.notified_marks.add(m)
                self._log(f"Restart notification threshold reached: {m} minutes remaining.")

        self._update_scheduler_status_label(seconds_left)

        if seconds_left <= 0:
            self._log("Scheduled restart triggered.")
            self.restart_server()
            self.notified_marks.clear()
            self.next_restart_dt = self._next_restart_after(datetime.now().replace(microsecond=0) + timedelta(seconds=1), cfg)

    def _update_scheduler_status_label(self, seconds_left: Optional[int] = None) -> None:
        if not self.scheduler_armed:
            return
        if self.next_restart_dt is None:
            self.status_label.setText("Status: Scheduler armed")
            return
        if seconds_left is None:
            seconds_left = max(0, int((self.next_restart_dt - datetime.now()).total_seconds()))
        hh = seconds_left // 3600
        mm = (seconds_left % 3600) // 60
        ss = seconds_left % 60
        self.status_label.setText(f"Next restart in {hh:02d}:{mm:02d}:{ss:02d}")

    # ------------------------------ XML validation ------------------------------
    def scan_xml_files(self) -> None:
        root = self.xml_root_edit.text().strip() or self.mission_edit.text().strip() or self.server_root_edit.text().strip()
        if not root:
            QMessageBox.warning(self, "Missing root", "Choose the mpmissions folder or mission folder first.")
            return
        base = Path(root)
        if not base.exists():
            QMessageBox.warning(self, "Invalid path", "The selected scan root does not exist.")
            return

        files = list(base.rglob("*.xml"))
        errors = []
        valid = 0
        import xml.etree.ElementTree as ET

        for file in files:
            try:
                ET.parse(file)
                valid += 1
            except ET.ParseError as e:
                line, col = getattr(e, "position", (0, 0))
                errors.append((str(file), line, col, str(e)))
            except Exception as e:
                errors.append((str(file), 0, 0, str(e)))

        self.xml_table.setRowCount(len(errors))
        for r, (file, line, col, err) in enumerate(errors):
            self.xml_table.setItem(r, 0, QTableWidgetItem(file))
            self.xml_table.setItem(r, 1, QTableWidgetItem(str(line)))
            self.xml_table.setItem(r, 2, QTableWidgetItem(str(col)))
            self.xml_table.setItem(r, 3, QTableWidgetItem(err))

        self.xml_summary.setText(f"Scanned {len(files)} XML files. Valid: {valid}. Errors: {len(errors)}.")
        self._log(self.xml_summary.text())
        QMessageBox.information(self, "XML scan complete", self.xml_summary.text())

    def export_xml_report(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save XML report", str(Path.home() / "dayz_xml_report.csv"), "CSV files (*.csv)")
        if not path:
            return
        try:
            lines = ["file,line,column,error"]
            for r in range(self.xml_table.rowCount()):
                row = []
                for c in range(self.xml_table.columnCount()):
                    item = self.xml_table.item(r, c)
                    value = item.text() if item else ""
                    value = value.replace('"', '""')
                    row.append(f'"{value}"')
                lines.append(",".join(row))
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            self._log(f"XML report exported to {path}")
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    # ------------------------------ Lifecycle ------------------------------
    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_settings()
        try:
            if self.server_process and self.server_process.state() != QProcess.NotRunning:
                self.server_process.terminate()
                self.server_process.waitForFinished(2000)
                if self.server_process.state() != QProcess.NotRunning:
                    self.server_process.kill()
        except Exception:
            pass
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
