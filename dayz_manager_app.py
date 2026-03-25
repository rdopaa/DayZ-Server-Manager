"""BTZ DayZ Manager

Modern DayZ server control panel for Windows.
Features:
- Dashboard with live console, status, CPU, uptime
- Server start/stop/restart and command console
- Mods manager with manual client/server separation
- SteamCMD workshop updater
- Backups and config export
- Scheduler with restart notifications export
- XML validator
- Logs with filters
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import traceback
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import re

from PySide6.QtCore import Qt, QProcess, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    import psutil
except Exception:
    psutil = None

APP_NAME = "BTZ DayZ Manager"
APP_ORG = "BrutalZ"
DISCORD_URL = "https://discord.gg/uaH3k8WRUN"
DAYZ_APP_ID = 221100
SETTINGS_FILE = (
    Path(os.getenv("APPDATA", str(Path.home()))) / "BTZDayZManager" / "settings.json"
)


@dataclass
class XmlError:
    file: str
    line: int
    column: int
    error: str


class ConsoleBox(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.document().setMaximumBlockCount(10000)

    def append_line(self, text: str) -> None:
        self.appendPlainText(text.rstrip("\n"))
        self.moveCursor(QTextCursor.End)


class GroupCard(QGroupBox):
    def __init__(self, title: str, widget: QWidget) -> None:
        super().__init__(title)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 18, 10, 10)
        lay.addWidget(widget)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1760, 1040)
        self.setMinimumSize(1100, 700)

        self.process: Optional[QProcess] = None
        self.start_timestamp: Optional[datetime] = None
        self.logs_raw: list[str] = []
        self.xml_errors: list[XmlError] = []
        self.next_restart: Optional[datetime] = None
        self.notified_marks: set[int] = set()

        self._types_tree: Optional[ET.ElementTree] = None
        self._types_elems: list[ET.Element] = []
        self._types_path: str = ""
        self._types_loading: bool = False

        self.scheduler_enabled = False
        self.settings = self._load_settings()

        self._build_ui()
        self._apply_style()
        self._wire_events()
        self._restore_settings()
        self._set_status("off")
        self.log("Ready.")

        self.runtime_timer = QTimer(self)
        self.runtime_timer.setInterval(1000)
        self.runtime_timer.timeout.connect(self._refresh_runtime)

        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.setInterval(1000)
        self.scheduler_timer.timeout.connect(self._tick_scheduler)

    # ──────────────────────────── UI BUILD ────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(14, 10, 14, 10)
        main.setSpacing(0)

        # ── Header: transparent background, just floating text ──
        header = QWidget()
        header.setObjectName("HeaderArea")
        h = QHBoxLayout(header)
        h.setContentsMargins(10, 10, 10, 10)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel("BTZ DayZ Manager")
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label = QLabel(
            "Everything you need to manage your DayZ server in one place."
        )
        self.subtitle_label.setObjectName("SubtitleLabel")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)

        self.status_chip = QLabel("○ OFFLINE")
        self.status_chip.setObjectName("StatusChip")
        self.status_chip.setAlignment(Qt.AlignCenter)
        self.status_chip.setFixedWidth(160)
        self.status_chip.setFixedHeight(34)

        # Invisible spacer widget (same width as chip) to keep title truly centered
        spacer_left = QWidget()
        spacer_left.setFixedWidth(160)
        spacer_left.setAttribute(Qt.WA_TransparentForMouseEvents)

        h.addWidget(spacer_left)
        h.addStretch(1)
        h.addLayout(title_col)
        h.addStretch(1)
        h.addWidget(self.status_chip)
        main.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(False)
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.addTab(self._dashboard_tab(), "⚡  Dashboard")
        self.tabs.addTab(self._server_tab(), "⚙️  Server")
        self.tabs.addTab(self._mods_tab(), "🧩  Mods")
        self.tabs.addTab(self._backups_tab(), "💾  Backups")
        self.tabs.addTab(self._xml_tab(), "🔍  XML")
        self.tabs.addTab(self._scheduler_tab(), "🕒  Scheduler")
        self.tabs.addTab(self._logs_tab(), "📋  Logs")
        main.addWidget(self.tabs, 1)

        footer = QFrame()
        footer.setObjectName("FooterCard")
        f = QHBoxLayout(footer)
        f.setContentsMargins(12, 8, 12, 8)
        f.addStretch(1)
        self.discord_btn = QPushButton("💬  Join Official Discord")
        self.discord_btn.setObjectName("DiscordButton")
        f.addWidget(self.discord_btn)
        f.addStretch(1)
        main.addWidget(footer)

    def _dashboard_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        # Status bar
        status_bar = QFrame()
        status_bar.setObjectName("StatusBar")
        top = QHBoxLayout(status_bar)
        top.setContentsMargins(12, 8, 12, 8)
        top.setSpacing(20)
        self.dashboard_status = QLabel("Status: OFF")
        self.dashboard_status.setObjectName("Badge")
        self.dashboard_cpu = QLabel("CPU: 0%")
        self.dashboard_cpu.setObjectName("Badge")
        self.dashboard_uptime = QLabel("Uptime: 00:00:00")
        self.dashboard_uptime.setObjectName("Badge")
        self.dashboard_pid = QLabel("PID: -")
        self.dashboard_pid.setObjectName("Badge")
        self.dashboard_root = QLabel("Root: not selected")
        self.dashboard_root.setObjectName("RootLabel")
        for lab in (
            self.dashboard_status,
            self.dashboard_cpu,
            self.dashboard_uptime,
            self.dashboard_pid,
        ):
            top.addWidget(lab)
        top.addWidget(self.dashboard_root, 1)
        layout.addWidget(status_bar)

        # Action buttons
        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.btn_start = QPushButton("▶  Start")
        self.btn_stop = QPushButton("⏹  Stop")
        self.btn_restart = QPushButton("🔄  Restart")
        self.btn_force = QPushButton("⚡  Force Restart")
        self.btn_detect_mods = QPushButton("🧩  Detect Mods")
        self.btn_preview_restart = QPushButton("🕒  Preview Schedule")
        self.btn_start.setObjectName("BtnStart")
        self.btn_stop.setObjectName("BtnStop")
        self.btn_restart.setObjectName("BtnAction")
        self.btn_force.setObjectName("BtnDanger")
        for b in (
            self.btn_start,
            self.btn_stop,
            self.btn_restart,
            self.btn_force,
            self.btn_detect_mods,
            self.btn_preview_restart,
        ):
            actions.addWidget(b)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.live_console = ConsoleBox()
        layout.addWidget(GroupCard("Live console", self.live_console), 1)

        cmd_row = QHBoxLayout()
        self.console_cmd = QLineEdit()
        self.console_cmd.setPlaceholderText(
            "Type command: restart / clear / stop / start / help"
        )
        self.console_cmd_button = QPushButton("Send")
        cmd_row.addWidget(self.console_cmd, 1)
        cmd_row.addWidget(self.console_cmd_button)
        layout.addLayout(cmd_row)

        return w

    def _server_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        paths = QGroupBox("Server paths")
        grid = QGridLayout(paths)
        grid.setSpacing(8)
        grid.setContentsMargins(14, 20, 14, 14)

        # Fixed label column so fields never overlap
        LABEL_W = 160

        self.server_root = QLineEdit()
        self.exe_path = QLineEdit()
        self.battleye_path = QLineEdit()
        self.mission_path = QLineEdit()
        self.profiles_path = QLineEdit("profiles")
        self.config_path = QLineEdit("serverDZ.cfg")
        self.port = QLineEdit("2302")
        self.server_name = QLineEdit("BTZ Server")
        self.restart_timeout = QSpinBox()
        self.restart_timeout.setRange(0, 86400)
        self.restart_timeout.setValue(21600)

        self.btn_root = QPushButton("Browse")
        self.btn_exe = QPushButton("Browse")
        self.btn_battleye = QPushButton("Browse")
        self.btn_mission = QPushButton("Browse")
        for btn in (self.btn_root, self.btn_exe, self.btn_battleye, self.btn_mission):
            btn.setFixedWidth(80)
            btn.setMinimumHeight(32)

        def _lbl(text):
            lbl = QLabel(text)
            lbl.setFixedWidth(LABEL_W)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return lbl

        grid.addWidget(_lbl("Server root:"),        0, 0)
        grid.addWidget(self.server_root,             0, 1)
        grid.addWidget(self.btn_root,                0, 2)

        grid.addWidget(_lbl("Executable:"),          1, 0)
        grid.addWidget(self.exe_path,                1, 1)
        grid.addWidget(self.btn_exe,                 1, 2)

        grid.addWidget(_lbl("BattlEye:"),            2, 0)
        grid.addWidget(self.battleye_path,           2, 1)
        grid.addWidget(self.btn_battleye,            2, 2)

        grid.addWidget(_lbl("Mission:"),             3, 0)
        grid.addWidget(self.mission_path,            3, 1)
        grid.addWidget(self.btn_mission,             3, 2)

        grid.addWidget(_lbl("Profiles:"),            4, 0)
        grid.addWidget(self.profiles_path,           4, 1, 1, 2)

        grid.addWidget(_lbl("Config file:"),         5, 0)
        grid.addWidget(self.config_path,             5, 1, 1, 2)

        grid.addWidget(_lbl("Port:"),                6, 0)
        grid.addWidget(self.port,                    6, 1, 1, 2)

        grid.addWidget(_lbl("Server name:"),         7, 0)
        grid.addWidget(self.server_name,             7, 1, 1, 2)

        grid.addWidget(_lbl("Restart timeout (s):"), 8, 0)
        grid.addWidget(self.restart_timeout,         8, 1, 1, 2)

        grid.setColumnStretch(1, 1)
        layout.addWidget(paths)

        opts = QGroupBox("Launch options")
        opt_l = QHBoxLayout(opts)
        self.opt_dologs = QCheckBox("-dologs")
        self.opt_adminlog = QCheckBox("-adminlog")
        self.opt_netlog = QCheckBox("-netlog")
        self.opt_freeze = QCheckBox("-freezecheck")
        for c in (self.opt_dologs, self.opt_adminlog, self.opt_netlog, self.opt_freeze):
            c.setChecked(True)
            opt_l.addWidget(c)
        opt_l.addStretch(1)
        layout.addWidget(opts)

        btns = QHBoxLayout()
        self.btn_generate_bat = QPushButton("📄  Generate start.bat")
        self.btn_export_cfg = QPushButton("📦  Export configs")
        self.btn_open_root = QPushButton("📂  Open root folder")
        for b in (self.btn_generate_bat, self.btn_export_cfg, self.btn_open_root):
            btns.addWidget(b)
        btns.addStretch(1)
        layout.addLayout(btns)

        self.cmd_preview = QPlainTextEdit()
        self.cmd_preview.setReadOnly(True)
        self.cmd_preview.setMinimumHeight(220)
        layout.addWidget(GroupCard("BAT preview", self.cmd_preview), 1)

        return w

    def _mods_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.btn_mod_scan = QPushButton("🔍  Scan @mods")
        self.btn_to_client = QPushButton("→ Client")
        self.btn_to_server = QPushButton("→ Server")
        self.btn_remove_client = QPushButton("← Remove Client")
        self.btn_remove_server = QPushButton("← Remove Server")
        self.btn_auto_server = QPushButton("💡  Suggest server mods")
        self.btn_clear_mods = QPushButton("🗑  Clear all")
        for b in (
            self.btn_mod_scan,
            self.btn_to_client,
            self.btn_to_server,
            self.btn_remove_client,
            self.btn_remove_server,
            self.btn_auto_server,
            self.btn_clear_mods,
        ):
            top.addWidget(b)
        top.addStretch(1)
        layout.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        self.available_mods = QListWidget()
        self.client_mods = QListWidget()
        self.server_mods = QListWidget()
        for lst in (self.available_mods, self.client_mods, self.server_mods):
            lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
        split.addWidget(GroupCard("Available", self.available_mods))
        split.addWidget(GroupCard("Client mods", self.client_mods))
        split.addWidget(GroupCard("Server mods", self.server_mods))
        layout.addWidget(split, 1)

        workshop = QGroupBox("Workshop updater (SteamCMD)")
        wf = QFormLayout(workshop)
        wf.setSpacing(8)
        self.steamcmd_path = QLineEdit()
        self.steamcmd_browse = QPushButton("Browse")
        self.steamcmd_install = QPushButton("Install")
        self.steam_login_mode = QComboBox()
        self.steam_login_mode.addItems(["Anonymous", "User / Password"])
        self.steam_user = QLineEdit()
        self.steam_pass = QLineEdit()
        self.steam_pass.setEchoMode(QLineEdit.Password)
        self.workshop_table = QTableWidget(0, 3)
        self.workshop_table.setHorizontalHeaderLabels(
            ["Folder", "Workshop ID", "Target Path"]
        )
        self.workshop_table.horizontalHeader().setStretchLastSection(True)
        self.workshop_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.workshop_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.workshop_table.setMinimumHeight(160)

        row_btns = QHBoxLayout()
        self.btn_workshop_add = QPushButton("+ Add row")
        self.btn_workshop_del = QPushButton("- Remove row")
        self.btn_workshop_update = QPushButton("⬆  Update selected")
        self.btn_workshop_update_all = QPushButton("⬆  Update all")
        for b in (
            self.btn_workshop_add,
            self.btn_workshop_del,
            self.btn_workshop_update,
            self.btn_workshop_update_all,
        ):
            row_btns.addWidget(b)
        row_btns.addStretch(1)

        wf.addRow(
            "SteamCMD:",
            self._row3(self.steamcmd_path, self.steamcmd_browse, self.steamcmd_install),
        )
        wf.addRow("Login mode:", self.steam_login_mode)
        wf.addRow("Steam user:", self.steam_user)
        wf.addRow("Steam password:", self.steam_pass)
        wf.addRow("Workshop table:", self.workshop_table)
        wf.addRow(row_btns)
        layout.addWidget(workshop)

        return w

    def _backups_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        box = QGroupBox("Backups & export")
        form = QFormLayout(box)
        form.setSpacing(8)
        self.backup_dest = QLineEdit()
        self.storage1_path = QLineEdit()
        self.mpmissions_path = QLineEdit()
        self.btn_backup_dest = QPushButton("Browse")
        self.btn_storage1 = QPushButton("Browse")
        self.btn_mpmissions = QPushButton("Browse")
        self.include_storage1 = QCheckBox("Include storage_1")
        self.include_storage1.setChecked(True)
        self.include_mpmissions = QCheckBox("Include mpmissions")
        self.include_mpmissions.setChecked(True)
        self.include_configs = QCheckBox("Include configs")
        self.include_configs.setChecked(True)
        self.btn_backup_now = QPushButton("💾  Backup now")
        self.btn_export_all = QPushButton("📦  Export all configs")

        form.addRow(
            "Backup destination:", self._row(self.backup_dest, self.btn_backup_dest)
        )
        form.addRow("storage_1:", self._row(self.storage1_path, self.btn_storage1))
        form.addRow("mpmissions:", self._row(self.mpmissions_path, self.btn_mpmissions))
        form.addRow(self.include_storage1)
        form.addRow(self.include_mpmissions)
        form.addRow(self.include_configs)
        form.addRow(self._two_buttons_row(self.btn_backup_now, self.btn_export_all))
        layout.addWidget(box)

        self.backup_log = ConsoleBox()
        layout.addWidget(GroupCard("Backup log", self.backup_log), 1)
        return w

    def _xml_tab(self) -> QWidget:
        w = QWidget()
        main = QVBoxLayout(w)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        sub = QTabWidget()
        sub.setObjectName("XmlSubTabs")
        sub.addTab(self._types_xml_sub_tab(),       "📝  Types.xml")
        sub.addTab(self._weather_placeholder_tab(),  "🌤  Weather")
        sub.addTab(self._daynight_placeholder_tab(), "🌙  Day/Night")
        sub.addTab(self._json_editor_sub_tab(),      "{ }  JSON")
        sub.addTab(self._spawn_placeholder_tab(),    "🎯  Spawn")
        sub.addTab(self._raw_xml_sub_tab(),          "🔧  Raw XML")
        sub.addTab(self._xml_validator_sub_tab(),    "✅  Validator")
        main.addWidget(sub, 1)
        return w

    # ── Types.xml editor ──────────────────────────────────────────────────

    def _types_xml_sub_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Toolbar row ──
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.types_path = QLineEdit()
        self.types_path.setPlaceholderText("Path to types.xml…")
        self.types_path.setReadOnly(True)
        self.btn_types_open = QPushButton("📂  Open types.xml")
        self.btn_types_load = QPushButton("⬇  Load")
        self.btn_types_save = QPushButton("💾  Save")
        self.btn_types_split = QPushButton("✂  Split by category")
        self.btn_types_dupes = QPushButton("🔎  Check duplicates")
        self.btn_types_open.setObjectName("BtnAction")
        self.btn_types_save.setObjectName("BtnStart")
        bar.addWidget(self.types_path, 1)
        bar.addWidget(self.btn_types_open)
        bar.addWidget(self.btn_types_load)
        bar.addWidget(self.btn_types_save)
        bar.addWidget(self.btn_types_split)
        bar.addWidget(self.btn_types_dupes)
        layout.addLayout(bar)

        # ── Filter row ──
        frow = QHBoxLayout()
        frow.setSpacing(6)
        self.types_search = QLineEdit()
        self.types_search.setPlaceholderText("🔍  Filter by name…")
        self.types_cat_filter = QComboBox()
        self.types_cat_filter.addItem("All categories")
        self.types_cat_filter.setMinimumWidth(180)
        self.types_usage_filter = QComboBox()
        self.types_usage_filter.addItem("All usages")
        self.types_usage_filter.setMinimumWidth(150)
        self.types_count_label = QLabel("No file loaded.")
        self.types_count_label.setObjectName("RootLabel")
        frow.addWidget(self.types_search, 2)
        frow.addWidget(self.types_cat_filter)
        frow.addWidget(self.types_usage_filter)
        frow.addStretch(1)
        frow.addWidget(self.types_count_label)
        layout.addLayout(frow)

        # ── Table ──
        self.types_table = QTableWidget(0, 8)
        self.types_table.setHorizontalHeaderLabels(
            ["Name", "Nominal", "Lifetime", "Restock", "Min", "Category", "Usage / Value", "Raw XML"]
        )
        hdr = self.types_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QHeaderView.Stretch)
        self.types_table.setAlternatingRowColors(True)
        self.types_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.types_table.setSortingEnabled(True)
        self.types_table.verticalHeader().setDefaultSectionSize(24)
        self.types_table.verticalHeader().setVisible(True)
        layout.addWidget(self.types_table, 1)

        return w

    # ── XML Validator sub-tab (extracted from old _xml_tab) ───────────────

    def _xml_validator_sub_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        top = QHBoxLayout()
        self.xml_root = QLineEdit()
        self.xml_root.setPlaceholderText("Folder to scan for XML errors…")
        self.btn_xml_browse = QPushButton("Choose folder")
        self.btn_xml_scan = QPushButton("🔍  Scan XML")
        self.btn_xml_export = QPushButton("📄  Export CSV")
        top.addWidget(QLabel("Scan root:"))
        top.addWidget(self.xml_root, 1)
        top.addWidget(self.btn_xml_browse)
        top.addWidget(self.btn_xml_scan)
        top.addWidget(self.btn_xml_export)
        layout.addLayout(top)

        self.xml_table = QTableWidget(0, 4)
        self.xml_table.setHorizontalHeaderLabels(["File", "Line", "Column", "Error"])
        self.xml_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.xml_table, 1)
        self.xml_summary = QLabel("No scan yet.")
        self.xml_summary.setWordWrap(True)
        layout.addWidget(self.xml_summary)
        return w

    # ── Raw XML viewer/editor ─────────────────────────────────────────────

    def _raw_xml_sub_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        bar = QHBoxLayout()
        self.raw_xml_path_label = QLabel("No file loaded.")
        self.raw_xml_path_label.setObjectName("RootLabel")
        self.btn_raw_xml_save = QPushButton("💾  Save changes")
        self.btn_raw_xml_save.setObjectName("BtnStart")
        self.btn_raw_xml_reload = QPushButton("🔄  Reload from disk")
        bar.addWidget(self.raw_xml_path_label, 1)
        bar.addWidget(self.btn_raw_xml_reload)
        bar.addWidget(self.btn_raw_xml_save)
        layout.addLayout(bar)
        self.raw_xml_editor = QPlainTextEdit()
        self.raw_xml_editor.setFont(QFont("Consolas", 10))
        self.raw_xml_editor.setPlaceholderText(
            "Load a types.xml file in the Types.xml tab to edit its raw content here…"
        )
        layout.addWidget(self.raw_xml_editor, 1)
        return w

    # ── JSON editor ───────────────────────────────────────────────────────

    def _json_editor_sub_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        bar = QHBoxLayout()
        self.json_path_edit = QLineEdit()
        self.json_path_edit.setPlaceholderText("Path to JSON file…")
        self.json_path_edit.setReadOnly(True)
        self.btn_json_open = QPushButton("📂  Open")
        self.btn_json_save_file = QPushButton("💾  Save")
        self.btn_json_save_file.setObjectName("BtnStart")
        self.btn_json_format = QPushButton("{ }  Format")
        bar.addWidget(self.json_path_edit, 1)
        bar.addWidget(self.btn_json_open)
        bar.addWidget(self.btn_json_format)
        bar.addWidget(self.btn_json_save_file)
        layout.addLayout(bar)
        self.json_editor = QPlainTextEdit()
        self.json_editor.setFont(QFont("Consolas", 10))
        self.json_editor.setPlaceholderText(
            "Open any DayZ JSON file (cfgeconomycore.json, types.json, etc.)…"
        )
        layout.addWidget(self.json_editor, 1)
        return w

    # ── Placeholder sub-tabs ──────────────────────────────────────────────

    def _placeholder_sub_tab(self, icon: str, title: str, note: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lbl = QLabel(f"{icon}\n{title}\n\n{note}")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color:#3a5575; font-size:15px; font-weight:600;")
        lay.addWidget(lbl)
        return w

    def _weather_placeholder_tab(self) -> QWidget:
        return self._placeholder_sub_tab(
            "🌤", "Weather Editor",
            "Edit cfggameplay.json weather parameters.\nComing in a future update."
        )

    def _daynight_placeholder_tab(self) -> QWidget:
        return self._placeholder_sub_tab(
            "🌙", "Day/Night Cycle Editor",
            "Adjust server day/night cycle settings.\nComing in a future update."
        )

    def _spawn_placeholder_tab(self) -> QWidget:
        return self._placeholder_sub_tab(
            "🎯", "Spawn Editor",
            "Edit cfgspawnabletypes.xml spawn tables.\nComing in a future update."
        )

    def _scheduler_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        mode = QGroupBox("Restart mode")
        grid = QGridLayout(mode)
        grid.setSpacing(8)
        self.r_hours = QRadioButton("Every N hours")
        self.r_days = QRadioButton("Every N days")
        self.r_fixed = QRadioButton("Fixed times")
        self.r_hours.setChecked(True)
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(1, 72)
        self.hours_spin.setValue(6)
        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 30)
        self.days_spin.setValue(1)
        self.fixed_times = QLineEdit("00:00, 06:00, 12:00, 18:00")
        grid.addWidget(self.r_hours, 0, 0)
        grid.addWidget(self.hours_spin, 0, 1)
        grid.addWidget(QLabel("hours"), 0, 2)
        grid.addWidget(self.r_days, 1, 0)
        grid.addWidget(self.days_spin, 1, 1)
        grid.addWidget(QLabel("days"), 1, 2)
        grid.addWidget(self.r_fixed, 2, 0)
        grid.addWidget(self.fixed_times, 2, 1, 1, 2)
        layout.addWidget(mode)

        notif = QGroupBox("Notification offsets")
        notif_l = QHBoxLayout(notif)
        self.cb_15 = QCheckBox("15m")
        self.cb_10 = QCheckBox("10m")
        self.cb_5 = QCheckBox("5m")
        self.cb_1 = QCheckBox("1m")
        for c in (self.cb_15, self.cb_10, self.cb_5, self.cb_1):
            c.setChecked(True)
            notif_l.addWidget(c)
        notif_l.addStretch(1)
        layout.addWidget(notif)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_sched_preview = QPushButton("👁  Preview")
        self.btn_sched_export = QPushButton("📤  Export messages.json")
        self.btn_sched_arm = QPushButton("✅  Arm")
        self.btn_sched_disarm = QPushButton("⛔  Disarm")
        for b in (
            self.btn_sched_preview,
            self.btn_sched_export,
            self.btn_sched_arm,
            self.btn_sched_disarm,
        ):
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)

        self.schedule_table = QTableWidget(0, 3)
        self.schedule_table.setHorizontalHeaderLabels(["Restart", "Notify", "Text"])
        self.schedule_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.schedule_table, 1)
        return w

    def _logs_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.log_search = QLineEdit()
        self.log_search.setPlaceholderText("Search logs…")
        self.chk_info = QCheckBox("INFO")
        self.chk_info.setChecked(True)
        self.chk_warn = QCheckBox("WARN")
        self.chk_warn.setChecked(True)
        self.chk_error = QCheckBox("ERROR")
        self.chk_error.setChecked(True)
        self.chk_be = QCheckBox("BE")
        self.chk_be.setChecked(True)
        self.chk_pause = QCheckBox("Pause")
        self.btn_log_tail = QPushButton("Tail 200")
        self.btn_log_export = QPushButton("📄  Export")
        self.btn_log_clear = QPushButton("🗑  Clear")
        for x in (
            self.log_search,
            self.chk_info,
            self.chk_warn,
            self.chk_error,
            self.chk_be,
            self.chk_pause,
            self.btn_log_tail,
            self.btn_log_export,
            self.btn_log_clear,
        ):
            row.addWidget(x)
        row.addStretch(1)
        layout.addLayout(row)
        self.log_view = ConsoleBox()
        layout.addWidget(self.log_view, 1)
        return w

    # ──────────────────────────── STYLE ────────────────────────────

    def _apply_style(self) -> None:
        app = QApplication.instance()
        if app:
            app.setStyle("Fusion")
            app.setFont(QFont("Segoe UI", 10))

        self.setStyleSheet(
            """
            /* ── Base ────────────────────────────────────────────── */
            QWidget {
                background: #0d1117;
                color: #e6edf3;
                font-family: "Segoe UI", Arial, sans-serif;
            }

            /* ── Header area — fully transparent ─────────────────── */
            QWidget#HeaderArea {
                background: transparent;
                border: none;
            }
            QFrame#FooterCard {
                background: #0e1520;
                border: 1px solid #1a2a3a;
                border-radius: 12px;
            }
            QFrame#StatusBar {
                background: #0b1220;
                border: 1px solid #1e2d40;
                border-radius: 10px;
            }

            /* ── Title (white, glow effect via text-shadow workaround) ── */
            QLabel#TitleLabel {
                font-size: 28px;
                font-weight: 800;
                color: #ffffff;
                letter-spacing: 2px;
                background: transparent;
                border: none;
            }
            QLabel#SubtitleLabel {
                color: #6a85a8;
                font-size: 11px;
                letter-spacing: 1px;
                background: transparent;
                border: none;
            }
            QLabel#RootLabel {
                color: #9aaabb;
                font-size: 11px;
            }

            /* ── Status / Badge chips ─────────────────────────────── */
            QLabel#StatusChip, QLabel#Badge {
                background: #141d2b;
                border: 1px solid #2b3d55;
                border-radius: 10px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }

            /* ── Buttons ──────────────────────────────────────────── */
            QPushButton {
                background: #151e2d;
                border: 1px solid #253040;
                border-radius: 8px;
                padding: 6px 14px;
                min-height: 30px;
                font-size: 12px;
                color: #c9d4e0;
            }
            QPushButton:hover {
                background: #1c2940;
                border-color: #3a5070;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #0e1925;
            }
            QPushButton#BtnStart {
                background: #0d3320;
                border-color: #1a6640;
                color: #3ddc82;
                font-weight: 700;
            }
            QPushButton#BtnStart:hover {
                background: #0f4028;
                border-color: #25994f;
            }
            QPushButton#BtnStop {
                background: #2d1010;
                border-color: #601818;
                color: #ff6b6b;
                font-weight: 700;
            }
            QPushButton#BtnStop:hover {
                background: #3d1515;
            }
            QPushButton#BtnDanger {
                background: #2a1a00;
                border-color: #5a3800;
                color: #ffaa40;
            }
            QPushButton#BtnDanger:hover {
                background: #352000;
            }
            QPushButton#BtnAction {
                background: #0d1f3a;
                border-color: #1a3a6a;
                color: #60aaff;
            }
            QPushButton#DiscordButton {
                background: #1a1f5e;
                border: 1px solid #5865F2;
                color: #8fa5ff;
                font-weight: 700;
                padding: 8px 24px;
                min-height: 34px;
            }
            QPushButton#DiscordButton:hover {
                background: #252b80;
                color: #ffffff;
            }

            /* ── GroupBox ─────────────────────────────────────────── */
            QGroupBox {
                border: 1px solid #1e2d42;
                border-radius: 12px;
                margin-top: 14px;
                padding: 14px 10px 10px 10px;
                background: #0b1220;
                font-weight: 600;
                font-size: 12px;
                color: #7aadda;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #5090cc;
            }

            /* ── Inputs ───────────────────────────────────────────── */
            QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background: #080f18;
                border: 1px solid #1e2d42;
                border-radius: 8px;
                padding: 6px 10px;
                selection-background-color: #2255aa;
                color: #d0dce8;
            }
            QLineEdit { min-height: 32px; font-size: 12px; }
            QLineEdit:focus, QPlainTextEdit:focus,
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #3a70c0;
                background: #090f1c;
            }
            QComboBox { min-height: 32px; }

            /* ── Lists / Tables ───────────────────────────────────── */
            QListWidget, QTableWidget {
                background: #080f18;
                border: 1px solid #1e2d42;
                border-radius: 8px;
                padding: 4px;
                alternate-background-color: #0b1420;
                gridline-color: #1a2535;
            }
            QListWidget::item:selected, QTableWidget::item:selected {
                background: #1a3a6a;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #0d1a2a;
                border: none;
                border-bottom: 1px solid #1e2d42;
                padding: 6px 10px;
                font-weight: 600;
                color: #6090bb;
            }

            /* ── Tabs ─────────────────────────────────────────────── */
            QTabWidget {
                background: transparent;
            }
            QTabWidget::pane {
                border: 1px solid #1a2d40;
                border-top: none;
                border-radius: 0 0 10px 10px;
                padding: 8px;
                background: #08101a;
                margin-top: 0px;
            }
            QTabBar {
                background: transparent;
                border: none;
            }
            QTabBar::tab {
                background: #0a1522;
                border: 1px solid #1a2535;
                border-bottom: none;
                padding: 5px 10px;
                margin-right: 3px;
                margin-bottom: 0px;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                min-width: 80px;
                max-width: 120px;
                min-height: 26px;
                font-weight: 600;
                font-size: 12px;
                color: #5a7a9a;
            }
            QTabBar::tab:selected {
                background: #08101a;
                border-color: #1a2d40;
                border-bottom: none;
                color: #60aaff;
                padding-bottom: 6px;
            }
            QTabBar::tab:hover:!selected {
                background: #0e1c2e;
                color: #90b8d8;
            }
            QTabBar::scroller {
                width: 0;
            }

            /* ── XML sub-tabs (inner tab widget) ─────────────────── */
            QTabWidget#XmlSubTabs::pane {
                border: 1px solid #1a2d40;
                border-top: none;
                border-radius: 0 0 8px 8px;
                padding: 6px;
                background: #070e17;
                margin-top: 0px;
            }
            QTabWidget#XmlSubTabs QTabBar::tab {
                min-width: 70px;
                max-width: 140px;
                min-height: 22px;
                padding: 4px 10px;
                font-size: 11px;
                background: #091220;
                color: #4a6a8a;
            }
            QTabWidget#XmlSubTabs QTabBar::tab:selected {
                background: #070e17;
                color: #50a0f0;
                padding-bottom: 5px;
            }
            QTabWidget#XmlSubTabs QTabBar::tab:hover:!selected {
                background: #0d1a2a;
                color: #80b0d0;
            }

            /* ── Progress bar ─────────────────────────────────────── */
            QProgressBar {
                border: 1px solid #1e2d42;
                border-radius: 6px;
                background: #080f18;
                text-align: center;
                color: #7aadda;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1a5090, stop:1 #3090dd);
                border-radius: 5px;
            }

            /* ── CheckBox / RadioButton ───────────────────────────── */
            QCheckBox, QRadioButton { color: #c0d0e0; spacing: 6px; }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 16px; height: 16px;
                border: 1px solid #2a4060;
                border-radius: 4px;
                background: #0a1525;
            }
            QCheckBox::indicator:checked {
                background: #2255aa;
                border-color: #4080dd;
                image: url('');
            }
            QRadioButton::indicator { border-radius: 8px; }
            QRadioButton::indicator:checked {
                background: #2255aa;
                border-color: #4080dd;
            }

            /* ── ScrollBar ────────────────────────────────────────── */
            QScrollBar:vertical {
                background: #080f18;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #253550;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background: #080f18;
                height: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #253550;
                border-radius: 5px;
                min-width: 20px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
            """
        )

    # ──────────────────────────── WIRING ────────────────────────────

    def _wire_events(self) -> None:
        self.discord_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(DISCORD_URL))
        )

        self.btn_root.clicked.connect(lambda: self._browse_dir(self.server_root))
        self.btn_exe.clicked.connect(
            lambda: self._browse_file(self.exe_path, "Executables (*.exe)")
        )
        self.btn_battleye.clicked.connect(lambda: self._browse_dir(self.battleye_path))
        self.btn_mission.clicked.connect(lambda: self._browse_dir(self.mission_path))
        self.btn_open_root.clicked.connect(self.open_root)
        self.btn_generate_bat.clicked.connect(self.generate_bat)
        self.btn_export_cfg.clicked.connect(self.export_all_configs)

        self.btn_start.clicked.connect(self.start_server)
        self.btn_stop.clicked.connect(self.stop_server)
        self.btn_restart.clicked.connect(self.restart_server)
        self.btn_force.clicked.connect(self.force_restart)
        self.btn_detect_mods.clicked.connect(self.detect_mods)
        self.btn_preview_restart.clicked.connect(self.preview_restart_schedule)
        self.console_cmd_button.clicked.connect(self.handle_console_command)
        self.console_cmd.returnPressed.connect(self.handle_console_command)

        self.btn_mod_scan.clicked.connect(self.detect_mods)
        self.btn_to_client.clicked.connect(
            lambda: self._move_selected(self.available_mods, self.client_mods)
        )
        self.btn_to_server.clicked.connect(
            lambda: self._move_selected(self.available_mods, self.server_mods)
        )
        self.btn_remove_client.clicked.connect(
            lambda: self._move_selected(self.client_mods, self.available_mods)
        )
        self.btn_remove_server.clicked.connect(
            lambda: self._move_selected(self.server_mods, self.available_mods)
        )
        self.btn_auto_server.clicked.connect(self.suggest_server_mods)
        self.btn_clear_mods.clicked.connect(self.clear_mods)
        self.steamcmd_browse.clicked.connect(
            lambda: self._browse_file(self.steamcmd_path, "steamcmd.exe (steamcmd.exe)")
        )
        self.steamcmd_install.clicked.connect(self.install_steamcmd)
        self.btn_workshop_add.clicked.connect(self.add_workshop_row)
        self.btn_workshop_del.clicked.connect(self.remove_workshop_row)
        self.btn_workshop_update.clicked.connect(self.update_selected_workshop_mods)
        self.btn_workshop_update_all.clicked.connect(self.update_all_workshop_mods)

        self.btn_backup_dest.clicked.connect(lambda: self._browse_dir(self.backup_dest))
        self.btn_storage1.clicked.connect(lambda: self._browse_dir(self.storage1_path))
        self.btn_mpmissions.clicked.connect(
            lambda: self._browse_dir(self.mpmissions_path)
        )
        self.btn_backup_now.clicked.connect(self.create_backup_now)
        self.btn_export_all.clicked.connect(self.export_all_configs)

        self.btn_xml_browse.clicked.connect(lambda: self._browse_dir(self.xml_root))
        self.btn_xml_scan.clicked.connect(self.scan_xml)
        self.btn_xml_export.clicked.connect(self.export_xml_csv)

        self.btn_sched_preview.clicked.connect(self.preview_restart_schedule)
        self.btn_sched_export.clicked.connect(self.export_messages_json)
        self.btn_sched_arm.clicked.connect(self.arm_scheduler)
        self.btn_sched_disarm.clicked.connect(self.disarm_scheduler)

        self.btn_log_tail.clicked.connect(lambda: self.tail_logs(200))
        self.btn_log_export.clicked.connect(self.export_logs)
        self.btn_log_clear.clicked.connect(self.clear_logs)
        self.log_search.textChanged.connect(self.refresh_logs_view)
        for cb in (self.chk_info, self.chk_warn, self.chk_error, self.chk_be, self.chk_pause):
            cb.toggled.connect(self.refresh_logs_view)

        for edit in (
            self.server_root,
            self.exe_path,
            self.battleye_path,
            self.mission_path,
            self.profiles_path,
            self.config_path,
            self.port,
            self.server_name,
            self.steamcmd_path,
            self.steam_user,
            self.steam_pass,
            self.backup_dest,
            self.storage1_path,
            self.mpmissions_path,
            self.xml_root,
        ):
            try:
                edit.textChanged.connect(self.save_settings)
            except Exception:
                pass
        self.restart_timeout.valueChanged.connect(self.save_settings)
        for cb in (
            self.opt_dologs,
            self.opt_adminlog,
            self.opt_netlog,
            self.opt_freeze,
            self.include_storage1,
            self.include_mpmissions,
            self.include_configs,
            self.r_hours,
            self.r_days,
            self.r_fixed,
            self.cb_15,
            self.cb_10,
            self.cb_5,
            self.cb_1,
        ):
            cb.toggled.connect(self.save_settings)

        self.server_root.textChanged.connect(
            lambda: self.dashboard_root.setText(
                f"Root: {self.server_root.text().strip() or 'not selected'}"
            )
        )
        self.server_root.textChanged.connect(self.auto_detect_paths)
        self.server_root.textChanged.connect(self.update_bat_preview)
        self.exe_path.textChanged.connect(self.update_bat_preview)
        self.port.textChanged.connect(self.update_bat_preview)
        self.config_path.textChanged.connect(self.update_bat_preview)
        self.profiles_path.textChanged.connect(self.update_bat_preview)
        self.server_name.textChanged.connect(self.update_bat_preview)
        self.restart_timeout.valueChanged.connect(self.update_bat_preview)

    # ──────────────────────────── HELPERS ────────────────────────────

    def _row(self, edit: QLineEdit, button: QPushButton) -> QWidget:
        edit.setMinimumHeight(32)
        button.setMinimumHeight(32)
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(edit, 1)
        lay.addWidget(button)
        return w

    def _row3(
        self, edit: QLineEdit, b1: QPushButton, b2: QPushButton
    ) -> QWidget:
        edit.setMinimumHeight(32)
        b1.setMinimumHeight(32)
        b2.setMinimumHeight(32)
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(edit, 1)
        lay.addWidget(b1)
        lay.addWidget(b2)
        return w

    def _two_buttons_row(self, left: QPushButton, right: QPushButton) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(left)
        lay.addWidget(right)
        lay.addStretch(1)
        return w

    def auto_detect_paths(self) -> None:
        try:
            root = Path(self.server_root.text().strip())
            if not root.exists():
                return

            exe = root / "DayZServer_x64.exe"
            battleye = root / "battleye"
            missions = root / "mpmissions"
            profiles = root / "profiles"

            if exe.exists():
                self.exe_path.setText(str(exe))
            if battleye.exists():
                self.battleye_path.setText(str(battleye))
            if missions.exists():
                self.mission_path.setText(str(missions))
            if profiles.exists():
                self.profiles_path.setText("profiles")

            self.log("Auto-detected server structure.")
        except Exception:
            pass

    def install_steamcmd(self) -> None:
        try:
            root = Path(self.server_root.text().strip())
            if not root.exists():
                QMessageBox.warning(self, "Error", "Select server root first.")
                return

            steam_dir = root / "steamcmd"
            steam_dir.mkdir(parents=True, exist_ok=True)
            zip_path = steam_dir / "steamcmd.zip"

            self.log("Downloading SteamCMD…")
            urllib.request.urlretrieve(
                "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip",
                zip_path,
            )

            self.log("Extracting SteamCMD…")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(steam_dir)

            exe = steam_dir / "steamcmd.exe"
            if exe.exists():
                self.steamcmd_path.setText(str(exe))
                self.log("SteamCMD installed successfully.")
            else:
                self.log("SteamCMD install failed — exe not found after extraction.")

        except Exception as e:
            self.log(f"SteamCMD error: {e}")

    def _browse_dir(self, edit: QLineEdit) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose folder", edit.text().strip() or str(Path.home())
        )
        if folder:
            edit.setText(folder)

    def _browse_file(self, edit: QLineEdit, filter_text: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose file", edit.text().strip() or str(Path.home()), filter_text
        )
        if path:
            edit.setText(path)

    def list_items(self, widget: QListWidget) -> list[str]:
        return [widget.item(i).text() for i in range(widget.count())]

    def _set_status(self, state: str) -> None:
        if state == "starting":
            self.status_chip.setText("STARTING…")
            self.dashboard_status.setText("Status: STARTING")
            self.status_chip.setStyleSheet("color:#f5c542; border-color:#7a6010;")
        elif state == "running":
            self.status_chip.setText("● RUNNING")
            self.dashboard_status.setText("Status: RUNNING")
            self.status_chip.setStyleSheet("color:#3ddc82; border-color:#0d5930;")
        else:
            self.status_chip.setText("○ OFFLINE")
            self.dashboard_status.setText("Status: OFFLINE")
            self.status_chip.setStyleSheet("color:#ff6b6b; border-color:#601818;")

    def log(self, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {text}"
        self.logs_raw.append(line)
        if hasattr(self, "live_console"):
            self.live_console.append_line(line)
        if hasattr(self, "log_view"):
            self.refresh_logs_view()

    def clear_logs(self) -> None:
        self.logs_raw.clear()
        if hasattr(self, "live_console"):
            self.live_console.clear()
        if hasattr(self, "log_view"):
            self.log_view.clear()

    def _load_settings(self) -> dict:
        try:
            if SETTINGS_FILE.exists():
                return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def save_settings(self) -> None:
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(self._collect_settings(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            self.log(f"Settings save failed: {e}")

    def _collect_settings(self) -> dict:
        return {
            "server_root": self.server_root.text().strip(),
            "exe_path": self.exe_path.text().strip(),
            "battleye_path": self.battleye_path.text().strip(),
            "mission_path": self.mission_path.text().strip(),
            "profiles_path": self.profiles_path.text().strip(),
            "config_path": self.config_path.text().strip(),
            "port": self.port.text().strip(),
            "server_name": self.server_name.text().strip(),
            "restart_timeout": self.restart_timeout.value(),
            "steamcmd_path": self.steamcmd_path.text().strip(),
            "steam_login_mode": self.steam_login_mode.currentIndex(),
            "steam_user": self.steam_user.text().strip(),
            "steam_pass": self.steam_pass.text(),
            "backup_dest": self.backup_dest.text().strip(),
            "storage1_path": self.storage1_path.text().strip(),
            "mpmissions_path": self.mpmissions_path.text().strip(),
            "xml_root": self.xml_root.text().strip(),
            "include_storage1": self.include_storage1.isChecked(),
            "include_mpmissions": self.include_mpmissions.isChecked(),
            "include_configs": self.include_configs.isChecked(),
            "opt_dologs": self.opt_dologs.isChecked(),
            "opt_adminlog": self.opt_adminlog.isChecked(),
            "opt_netlog": self.opt_netlog.isChecked(),
            "opt_freeze": self.opt_freeze.isChecked(),
            "client_mods": self.list_items(self.client_mods),
            "server_mods": self.list_items(self.server_mods),
            "workshop_rows": self.workshop_rows(),
            "json_scheduler": {
                "mode": self.restart_mode(),
                "hours": self.hours_spin.value(),
                "days": self.days_spin.value(),
                "fixed_times": self.fixed_times.text().strip(),
                "marks": {
                    "15": self.cb_15.isChecked(),
                    "10": self.cb_10.isChecked(),
                    "5": self.cb_5.isChecked(),
                    "1": self.cb_1.isChecked(),
                },
            },
        }

    def _restore_settings(self) -> None:
        s = self.settings
        self.server_root.setText(s.get("server_root", ""))
        self.exe_path.setText(s.get("exe_path", ""))
        self.battleye_path.setText(s.get("battleye_path", ""))
        self.mission_path.setText(s.get("mission_path", ""))
        self.profiles_path.setText(s.get("profiles_path", "profiles"))
        self.config_path.setText(s.get("config_path", "serverDZ.cfg"))
        self.port.setText(s.get("port", "2302"))
        self.server_name.setText(s.get("server_name", "BTZ Server"))
        self.restart_timeout.setValue(int(s.get("restart_timeout", 21600)))
        self.steamcmd_path.setText(s.get("steamcmd_path", ""))
        self.steam_login_mode.setCurrentIndex(int(s.get("steam_login_mode", 0)))
        self.steam_user.setText(s.get("steam_user", ""))
        self.steam_pass.setText(s.get("steam_pass", ""))
        self.backup_dest.setText(s.get("backup_dest", ""))
        self.storage1_path.setText(s.get("storage1_path", ""))
        self.mpmissions_path.setText(s.get("mpmissions_path", ""))
        self.xml_root.setText(s.get("xml_root", ""))
        self.include_storage1.setChecked(bool(s.get("include_storage1", True)))
        self.include_mpmissions.setChecked(bool(s.get("include_mpmissions", True)))
        self.include_configs.setChecked(bool(s.get("include_configs", True)))
        self.opt_dologs.setChecked(bool(s.get("opt_dologs", True)))
        self.opt_adminlog.setChecked(bool(s.get("opt_adminlog", True)))
        self.opt_netlog.setChecked(bool(s.get("opt_netlog", True)))
        self.opt_freeze.setChecked(bool(s.get("opt_freeze", True)))
        self.client_mods.clear()
        self.server_mods.clear()
        for mod in s.get("client_mods", []):
            self.client_mods.addItem(mod)
        for mod in s.get("server_mods", []):
            self.server_mods.addItem(mod)
        for row in s.get("workshop_rows", []):
            self.add_workshop_row(
                row.get("folder", ""),
                row.get("workshop_id", ""),
                row.get("target", ""),
            )
        self.update_bat_preview()

    # ──────────────────────────── SERVER PROCESS ────────────────────────────

    def build_launch_args(self) -> tuple[str, list[str], str]:
        root = (
            Path(self.server_root.text().strip())
            if self.server_root.text().strip()
            else Path.cwd()
        )
        exe = (
            Path(self.exe_path.text().strip())
            if self.exe_path.text().strip()
            else root / "DayZServer_x64.exe"
        )
        work = str(root)
        args = [
            f'-config="{self.config_path.text().strip()}"',
            f'-port={self.port.text().strip()}',
            f'-profiles="{self.profiles_path.text().strip()}"',
        ]
        if self.opt_dologs.isChecked():
            args.append("-dologs")
        if self.opt_adminlog.isChecked():
            args.append("-adminlog")
        if self.opt_netlog.isChecked():
            args.append("-netlog")
        if self.opt_freeze.isChecked():
            args.append("-freezecheck")
        client = self.list_items(self.client_mods)
        server = self.list_items(self.server_mods)
        if client:
            args.append(f'-mod={";".join(client)}')
        if server:
            args.append(f'-serverMod={";".join(server)}')
        return str(exe), args, work

    def update_bat_preview(self) -> None:
        try:
            exe, _args, work = self.build_launch_args()
            client = ";".join(self.list_items(self.client_mods))
            server = ";".join(self.list_items(self.server_mods))
            params = []
            if self.opt_dologs.isChecked():
                params.append("-doLogs")
            if self.opt_adminlog.isChecked():
                params.append("-adminLog")
            if self.opt_netlog.isChecked():
                params.append("-netLog")
            if self.opt_freeze.isChecked():
                params.append("-freezeCheck")
            additional = " ".join(params) if params else "-doLogs -adminLog -netLog -freezeCheck"
            bat = (
                f"@echo off\n"
                f"setlocal EnableExtensions\n\n"
                f"title {self.server_name.text().strip() or 'BTZ Server'}\n"
                f"color 0A\n\n"
                f"set S_NAME={self.server_name.text().strip() or 'BTZ Server'}\n"
                f"set EXE_PATH={work}\n"
                f"set EXE={Path(exe).name}\n"
                f"set CPU_CORES=%NUMBER_OF_PROCESSORS%\n"
                f"set MODLIST=-mod={client}\n"
                f"set SERVERMODLIST=-serverMod={server}\n"
                f"set PORT={self.port.text().strip()}\n"
                f"set CONFIG={self.config_path.text().strip()}\n"
                f"set PROFILE={self.profiles_path.text().strip()}\n"
                f"set RESTART_TIMEOUT={self.restart_timeout.value()}\n"
                f"set SERVER_FPS_LIMIT=200\n"
                f"set ADDITIONAL_PARAMETERS={additional}\n\n"
                f":LOOP\n"
                f'CD /D "%EXE_PATH%"\n'
                f"ECHO MESSAGE: Starting %S_NAME% at %DATE% %TIME%\n"
                f'START "" /MIN "%EXE_PATH%\\%EXE%" -profiles=%PROFILE% '
                f"-config=%CONFIG% -port=%PORT% -cpuCount=%CPU_CORES% "
                f"-limitFPS=%SERVER_FPS_LIMIT% %MODLIST% %SERVERMODLIST% "
                f"%ADDITIONAL_PARAMETERS%\n"
                f"IF %RESTART_TIMEOUT% == 0 GOTO WAIT_ONLY\n"
                f"TIMEOUT /T %RESTART_TIMEOUT% /NOBREAK >NUL\n"
                f"TASKKILL /IM %EXE% /F\n"
                f"TIMEOUT /T 10 /NOBREAK >NUL\n"
                f"GOTO LOOP\n\n"
                f":WAIT_ONLY\n"
                f"TIMEOUT /T 10 /NOBREAK >NUL\n"
                f"GOTO WAIT_ONLY\n"
            )
            self.cmd_preview.setPlainText(bat)
        except Exception as e:
            self.cmd_preview.setPlainText(f"Preview error: {e}")

    def generate_bat(self) -> None:
        default = Path(self.server_root.text().strip() or Path.cwd()) / "start.bat"
        out, _ = QFileDialog.getSaveFileName(
            self, "Save start.bat", str(default), "Batch files (*.bat)"
        )
        if not out:
            return
        self.update_bat_preview()
        Path(out).write_text(
            self.cmd_preview.toPlainText().replace("\n", "\r\n") + "\r\n",
            encoding="utf-8",
        )
        self.log(f"Generated BAT: {out}")
        QMessageBox.information(self, "BAT generated", f"Saved to:\n{out}")

    def start_server(self) -> None:
        try:
            exe, args, work = self.build_launch_args()
            if not Path(exe).exists():
                raise FileNotFoundError(f"Executable not found: {exe}")
            if self.process and self.process.state() != QProcess.NotRunning:
                QMessageBox.information(
                    self, "Server running", "The server is already running."
                )
                return
            self.process = QProcess(self)
            self.process.setWorkingDirectory(work)
            self.process.readyReadStandardOutput.connect(self._read_stdout)
            self.process.readyReadStandardError.connect(self._read_stderr)
            self.process.started.connect(lambda: self._set_status("starting"))
            self.process.finished.connect(self._on_process_finished)
            self.process.errorOccurred.connect(self._on_process_error)
            self.process.setProgram(exe)
            self.process.setArguments(args)
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.start()
            if not self.process.waitForStarted(5000):
                raise RuntimeError(
                    "DayZ server did not start. Check exe path, config, and working directory."
                )
            self.start_timestamp = datetime.now()
            self.runtime_timer.start()
            try:
                self.set_process_affinity()
            except Exception:
                pass
            self.log("Server start requested.")
            self._set_status("starting")
        except Exception as e:
            self.log(f"Start failed: {e}")
            QMessageBox.critical(self, "Start failed", str(e))

    def stop_server(self) -> None:
        if not self.process or self.process.state() == QProcess.NotRunning:
            self._set_status("off")
            return
        self.log("Stopping server…")
        self.process.terminate()
        if not self.process.waitForFinished(5000):
            self.process.kill()
            self.process.waitForFinished(5000)
        self.start_timestamp = None
        self.runtime_timer.stop()
        self._set_status("off")

    def restart_server(self) -> None:
        self.log("Restart requested.")
        self.stop_server()
        QTimer.singleShot(1500, self.start_server)

    def force_restart(self) -> None:
        self.log("Force restart requested.")
        self.stop_server()
        QTimer.singleShot(500, self.start_server)

    def _on_process_finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self.log(f"Server exited — code={code}, status={status.name}")
        self.start_timestamp = None
        self.runtime_timer.stop()
        self._set_status("off")

    def _on_process_error(self, error) -> None:
        self.log(f"Process error: {error}")

    def _read_stdout(self) -> None:
        if not self.process:
            return
        text = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        for line in text.splitlines():
            self.log(line)

    def _read_stderr(self) -> None:
        if not self.process:
            return
        text = bytes(self.process.readAllStandardError()).decode(errors="replace")
        for line in text.splitlines():
            self.log(f"[ERR] {line}")

    def _refresh_runtime(self) -> None:
        if not self.process or self.process.state() == QProcess.NotRunning:
            self.dashboard_pid.setText("PID: -")
            self.dashboard_uptime.setText("Uptime: 00:00:00")
            self.dashboard_cpu.setText("CPU: 0%")
            self._set_status("off")
            return

        pid = int(self.process.processId()) if hasattr(self.process, "processId") else 0
        self.dashboard_pid.setText(f"PID: {pid if pid else '-'}")

        if self.start_timestamp:
            delta = datetime.now() - self.start_timestamp
            h, rem = divmod(int(delta.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            self.dashboard_uptime.setText(f"Uptime: {h:02d}:{m:02d}:{s:02d}")
        else:
            self.dashboard_uptime.setText("Uptime: running")

        if psutil and pid:
            try:
                p = psutil.Process(pid)
                p.cpu_percent()
                cpu = p.cpu_percent(interval=0.5)
                self.dashboard_cpu.setText(f"CPU: {cpu:.1f}%")
            except Exception:
                self.dashboard_cpu.setText("CPU: n/a")
        else:
            self.dashboard_cpu.setText("CPU: n/a")

        self._set_status("running")

    def set_process_affinity(self, pid: Optional[int] = None) -> None:
        try:
            if pid is None:
                if not self.process:
                    return
                try:
                    pid = (
                        int(self.process.processId())
                        if hasattr(self.process, "processId")
                        else None
                    )
                except Exception:
                    pid = None
            if not pid:
                return

            if psutil:
                try:
                    cpu_count = psutil.cpu_count(logical=True) or os.cpu_count() or 1
                    p = psutil.Process(pid)
                    p.cpu_affinity(list(range(cpu_count)))
                    self.log(f"Set CPU affinity to all {cpu_count} cores (psutil).")
                    return
                except Exception as e:
                    self.log(f"psutil affinity failed: {e}")

            if os.name == "nt":
                try:
                    import ctypes

                    PROCESS_SET_INFORMATION = 0x0200
                    PROCESS_QUERY_INFORMATION = 0x0400
                    handle = ctypes.windll.kernel32.OpenProcess(
                        PROCESS_SET_INFORMATION | PROCESS_QUERY_INFORMATION,
                        False,
                        int(pid),
                    )
                    if not handle:
                        self.log("Failed to open process handle for affinity.")
                        return
                    try:
                        n = os.cpu_count() or 1
                        mask = (1 << n) - 1
                        res = ctypes.windll.kernel32.SetProcessAffinityMask(
                            handle, ctypes.c_size_t(mask)
                        )
                        if res == 0:
                            self.log("SetProcessAffinityMask failed.")
                        else:
                            self.log(f"Set CPU affinity to all {n} cores (WinAPI).")
                    finally:
                        ctypes.windll.kernel32.CloseHandle(handle)
                    return
                except Exception as e:
                    self.log(f"WinAPI affinity failed: {e}")

            if os.name != "nt" and hasattr(os, "sched_setaffinity"):
                try:
                    n = os.cpu_count() or 1
                    cpus = list(range(n))
                    p_int = int(pid) if pid else 0
                    os.sched_setaffinity(p_int, cpus)
                    self.log(f"Set CPU affinity to all {n} cores (sched_setaffinity).")
                except PermissionError as e:
                    self.log(f"sched_setaffinity permission denied: {e}")
                except Exception as e:
                    self.log(f"sched_setaffinity failed: {e}")

        except Exception as e:
            self.log(f"Affinity error: {e}")

    # ──────────────────────────── CONSOLE COMMANDS ────────────────────────────

    def handle_console_command(self) -> None:
        cmd = self.console_cmd.text().strip().lower()
        self.console_cmd.clear()
        if not cmd:
            return
        if cmd == "restart":
            self.restart_server()
        elif cmd == "clear":
            self.live_console.clear()
        elif cmd == "stop":
            self.stop_server()
        elif cmd == "start":
            self.start_server()
        elif cmd == "help":
            self.log("Commands: restart, clear, stop, start, help")
        else:
            self.log(f"Unknown command: {cmd!r}")

    # ──────────────────────────── MODS ────────────────────────────

    def detect_mods(self) -> None:
        root = self.server_root.text().strip()
        if not root:
            QMessageBox.warning(self, "Missing root", "Choose the server root first.")
            return
        base = Path(root)
        if not base.exists():
            QMessageBox.warning(self, "Invalid path", "Server root does not exist.")
            return

        bat_candidates: list[Path] = []
        preferred = ["start.bat", "start_server.bat", "run.bat", "server.bat"]
        for name in preferred:
            p = base / name
            if p.exists():
                bat_candidates.append(p)
        for p in sorted(base.glob("*.bat")):
            if p not in bat_candidates:
                bat_candidates.append(p)

        mods_ordered: list[str] = []
        used = set(self.list_items(self.client_mods)) | set(
            self.list_items(self.server_mods)
        )

        def extract_mods_from_token(token: str) -> list[str]:
            token = token.strip().strip('"').replace(",", ";")
            if token.lower().startswith("-mod="):
                token = token[5:]
            token = token.strip('"')
            return [x.strip() for x in token.split(";") if x.strip()]

        found_source: Optional[Path] = None
        for bat in bat_candidates:
            try:
                text = bat.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            m = re.search(r"(?mi)^\s*set\s+(mod(?:list|s)?)\s*=\s*(.*)$", text)
            if m:
                rhs = m.group(2).strip()
                token_match = re.search(r"-mod=([^\s\"]+)", rhs)
                if token_match:
                    mods_ordered = extract_mods_from_token("-mod=" + token_match.group(1))
                else:
                    mods_ordered = extract_mods_from_token(rhs)
                found_source = bat
                break

            all_mods = re.findall(r"-mod=([^\s\"]+)", text, flags=re.IGNORECASE)
            if all_mods:
                mods_ordered = extract_mods_from_token("-mod=" + all_mods[0])
                found_source = bat
                break

        if not mods_ordered:
            mods_ordered = [
                p.name
                for p in sorted(base.iterdir(), key=lambda x: x.name.lower())
                if p.is_dir() and p.name.startswith("@")
            ]

        self.available_mods.clear()
        count = 0
        for mod in mods_ordered:
            if mod in used:
                continue
            self.available_mods.addItem(mod)
            count += 1

        if found_source:
            self.log(f"Detected {count} mods from {found_source.name} (order preserved).")
        else:
            self.log(f"Detected {count} local @mods (folder scan fallback).")

        self.update_bat_preview()

    def suggest_server_mods(self) -> None:
        root = self.server_root.text().strip()
        if not root:
            return
        base = Path(root)
        source = self.list_items(self.client_mods) + self.list_items(self.available_mods)
        suggestions = []
        for mod in source:
            mod_dir = base / mod
            if not mod_dir.exists():
                continue
            low = mod.lower()
            has_keys = (mod_dir / "keys").exists() or any(
                mod_dir.rglob("*.bikey")
            )
            looks_server = any(
                token in low
                for token in ["server", "battleye", "admin", "tool", "storage", "economy"]
            )
            if has_keys or looks_server:
                suggestions.append(mod)
        if suggestions:
            QMessageBox.information(
                self,
                "Server mod suggestions",
                "Possible server-side mods:\n" + "\n".join(suggestions),
            )
        else:
            QMessageBox.information(
                self, "Server mod suggestions", "No obvious server-side mods found."
            )

    def clear_mods(self) -> None:
        self.available_mods.clear()
        self.client_mods.clear()
        self.server_mods.clear()
        self.update_bat_preview()

    def _move_selected(self, src: QListWidget, dst: QListWidget) -> None:
        for item in list(src.selectedItems()):
            text = item.text()
            if not dst.findItems(text, Qt.MatchExactly):
                dst.addItem(text)
            src.takeItem(src.row(item))
        self.update_bat_preview()
        self.save_settings()

    # ──────────────────────────── WORKSHOP ────────────────────────────

    def add_workshop_row(
        self, folder: str = "", workshop_id: str = "", target: str = ""
    ) -> None:
        row = self.workshop_table.rowCount()
        self.workshop_table.insertRow(row)
        self.workshop_table.setItem(row, 0, QTableWidgetItem(folder))
        self.workshop_table.setItem(row, 1, QTableWidgetItem(workshop_id))
        self.workshop_table.setItem(row, 2, QTableWidgetItem(target))

    def remove_workshop_row(self) -> None:
        row = self.workshop_table.currentRow()
        if row >= 0:
            self.workshop_table.removeRow(row)

    def workshop_rows(self) -> list[dict]:
        rows = []
        for r in range(self.workshop_table.rowCount()):
            rows.append(
                {
                    "folder": (
                        self.workshop_table.item(r, 0).text()
                        if self.workshop_table.item(r, 0)
                        else ""
                    ),
                    "workshop_id": (
                        self.workshop_table.item(r, 1).text()
                        if self.workshop_table.item(r, 1)
                        else ""
                    ),
                    "target": (
                        self.workshop_table.item(r, 2).text()
                        if self.workshop_table.item(r, 2)
                        else ""
                    ),
                }
            )
        return rows

    def update_selected_workshop_mods(self) -> None:
        rows = sorted({i.row() for i in self.workshop_table.selectedItems()})
        if not rows:
            QMessageBox.information(self, "Workshop", "Select at least one row.")
            return
        self._update_workshop_rows(rows)

    def update_all_workshop_mods(self) -> None:
        self._update_workshop_rows(list(range(self.workshop_table.rowCount())))

    def _steamcmd_prefix(self) -> list[str]:
        if (
            self.steam_login_mode.currentIndex() == 1
            and self.steam_user.text().strip()
        ):
            return [
                "+login",
                self.steam_user.text().strip(),
                self.steam_pass.text().strip(),
            ]
        return ["+login", "anonymous"]

    def _run_steamcmd(self, args: list[str]) -> tuple[int, str]:
        steamcmd = self.steamcmd_path.text().strip()
        if not steamcmd or not Path(steamcmd).exists():
            raise FileNotFoundError("SteamCMD executable not found.")
        cmd = [steamcmd] + args
        self.log("SteamCMD: " + " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        for line in out.splitlines():
            if line.strip():
                self.log(f"[SteamCMD] {line}")
        return proc.returncode, out

    def _update_workshop_rows(self, rows: list[int]) -> None:
        if not rows:
            return
        root = self.server_root.text().strip()
        for r in rows:
            folder = (
                self.workshop_table.item(r, 0).text().strip()
                if self.workshop_table.item(r, 0)
                else ""
            )
            workshop_id = (
                self.workshop_table.item(r, 1).text().strip()
                if self.workshop_table.item(r, 1)
                else ""
            )
            target = (
                self.workshop_table.item(r, 2).text().strip()
                if self.workshop_table.item(r, 2)
                else ""
            )

            if not workshop_id and folder:
                candidate = (
                    Path(target)
                    if target
                    else (Path(root) / folder if root else Path(folder))
                )
                try:
                    detected = self._detect_workshop_id_for_folder(candidate)
                    if detected:
                        workshop_id = detected
                        self.workshop_table.setItem(r, 1, QTableWidgetItem(workshop_id))
                        self.log(
                            f"Auto-detected workshop id {workshop_id} for folder {folder}"
                        )
                except Exception as e:
                    self.log(f"Workshop id auto-detect failed for {folder}: {e}")

            if not workshop_id:
                self.log(f"Skipping workshop row {r}: no workshop id.")
                continue

            if not target and root and folder:
                target = str(Path(root) / folder)
            if not target:
                self.log(f"Skipping workshop row {r}: no target folder.")
                continue

            rc, _ = self._run_steamcmd(
                self._steamcmd_prefix()
                + [
                    "+force_install_dir",
                    target,
                    "+workshop_download_item",
                    str(DAYZ_APP_ID),
                    workshop_id,
                    "validate",
                    "+quit",
                ]
            )
            self.log(
                f"Workshop update {workshop_id}: {'OK' if rc == 0 else 'FAILED'}"
            )

    def _detect_workshop_id_for_folder(self, folder: Path) -> Optional[str]:
        """Try to detect a Steam Workshop ID for a mod folder."""
        try:
            if not folder:
                return None
            p = Path(folder)
            if not p.exists():
                root_text = self.server_root.text().strip()
                root = Path(root_text) if root_text else None
                if root:
                    p = root / folder
            if not p.exists():
                return None

            if p.name.isdigit():
                return p.name

            nums = [child.name for child in p.iterdir() if child.name.isdigit()]
            if nums:
                nums.sort(key=lambda x: (-len(x), -int(x)))
                return nums[0]

            pattern = re.compile(r"\b(\d{6,10})\b")
            counts: dict[str, int] = {}
            search_files = (
                list(p.rglob("meta.cpp"))
                + list(p.rglob("*.txt"))
                + list(p.rglob("*.cpp"))
                + list(p.rglob("*.hpp"))
            )
            for fp in search_files:
                try:
                    txt = fp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for mid in pattern.findall(txt):
                    counts[mid] = counts.get(mid, 0) + 1

            if counts:
                sorted_ids = sorted(
                    counts.items(), key=lambda kv: (-kv[1], -len(kv[0]), -int(kv[0]))
                )
                return sorted_ids[0][0]

        except Exception as e:
            self.log(f"Error detecting workshop id: {e}")
        return None

    # ──────────────────────────── BACKUPS ────────────────────────────

    def _zip_folder(self, zf, src: Path, arc_prefix: str) -> None:
        if not src.exists():
            self.backup_log.append_line(f"Missing: {src}")
            return
        if src.is_file():
            zf.write(src, arcname=f"{arc_prefix}/{src.name}")
            return
        for p in src.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=f"{arc_prefix}/{p.relative_to(src)}")

    def _zip_configs(self, zf) -> None:
        root = Path(self.server_root.text().strip())
        if not root.exists():
            return
        for pattern in ("*.cfg", "*.json", "*.xml", "*.txt", "*.ini", "*.bat"):
            for path in root.rglob(pattern):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(root)))

    def create_backup_now(self) -> None:
        dest = self.backup_dest.text().strip()
        if not dest:
            QMessageBox.warning(self, "Missing destination", "Choose a backup destination.")
            return
        dest_path = Path(dest)
        dest_path.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        zip_path = dest_path / f"BTZ_Backup_{stamp}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if self.include_storage1.isChecked() and self.storage1_path.text().strip():
                self._zip_folder(
                    zf, Path(self.storage1_path.text().strip()), "storage_1"
                )
            if self.include_mpmissions.isChecked() and self.mpmissions_path.text().strip():
                self._zip_folder(
                    zf, Path(self.mpmissions_path.text().strip()), "mpmissions"
                )
            if self.include_configs.isChecked():
                self._zip_configs(zf)
        self.backup_log.append_line(f"Backup created: {zip_path}")
        QMessageBox.information(self, "Backup", f"Backup created:\n{zip_path}")

    def export_all_configs(self) -> None:
        root = Path(self.server_root.text().strip())
        if not root.exists():
            QMessageBox.warning(self, "Missing root", "Choose the server root first.")
            return
        out, _ = QFileDialog.getSaveFileName(
            self,
            "Export configs",
            str(Path.home() / "dayz_configs.zip"),
            "Zip (*.zip)",
        )
        if not out:
            return
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            self._zip_configs(zf)
        QMessageBox.information(self, "Exported", f"Configs exported to:\n{out}")

    # ──────────────────────────── XML VALIDATOR ────────────────────────────

    def scan_xml(self) -> None:
        root = (
            self.xml_root.text().strip()
            or self.mission_path.text().strip()
            or self.server_root.text().strip()
        )
        if not root:
            QMessageBox.warning(self, "Missing path", "Choose a scan root first.")
            return
        base = Path(root)
        if not base.exists():
            QMessageBox.warning(self, "Invalid path", "Folder does not exist.")
            return
        self.xml_errors.clear()
        xml_files = list(base.rglob("*.xml"))
        ok = 0
        for file in xml_files:
            try:
                ET.parse(file)
                ok += 1
            except ET.ParseError as e:
                line, col = getattr(e, "position", (0, 0))
                self.xml_errors.append(XmlError(str(file), line, col, str(e)))
            except Exception as e:
                self.xml_errors.append(XmlError(str(file), 0, 0, str(e)))
        self.xml_table.setRowCount(len(self.xml_errors))
        for r, err in enumerate(self.xml_errors):
            self.xml_table.setItem(r, 0, QTableWidgetItem(err.file))
            self.xml_table.setItem(r, 1, QTableWidgetItem(str(err.line)))
            self.xml_table.setItem(r, 2, QTableWidgetItem(str(err.column)))
            self.xml_table.setItem(r, 3, QTableWidgetItem(err.error))
        summary = f"Scanned {len(xml_files)} XML files — Valid: {ok}, Errors: {len(self.xml_errors)}."
        self.xml_summary.setText(summary)
        self.log(summary)

    def export_xml_csv(self) -> None:
        out, _ = QFileDialog.getSaveFileName(
            self,
            "Export XML report",
            str(Path.home() / "xml_report.csv"),
            "CSV (*.csv)",
        )
        if not out:
            return
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file", "line", "column", "error"])
            for err in self.xml_errors:
                writer.writerow([err.file, err.line, err.column, err.error])
        QMessageBox.information(self, "Exported", f"XML report saved to:\n{out}")

    # ──────────────────────────── TYPES.XML EDITOR ────────────────────────────

    def types_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open types.xml", str(Path.home()), "XML Files (*.xml);;All Files (*)"
        )
        if path:
            self.types_path.setText(path)
            self.load_types_xml()

    def load_types_xml(self) -> None:
        path = self.types_path.text().strip()
        if not path:
            QMessageBox.warning(self, "No file", "Please open a types.xml file first.")
            return
        p = Path(path)
        if not p.exists():
            QMessageBox.warning(self, "File not found", f"File not found:\n{path}")
            return
        try:
            self._types_tree = ET.parse(str(p))
            self._types_path = str(p)
        except ET.ParseError as e:
            QMessageBox.critical(self, "Parse error", f"Could not parse XML:\n{e}")
            return

        root_el = self._types_tree.getroot()
        if root_el.tag == "types":
            self._types_elems = [el for el in root_el if el.tag == "type"]
        elif root_el.tag == "type":
            self._types_elems = [root_el]
        else:
            self._types_elems = [el for el in root_el.iter("type")]

        self._populate_types_table()

        raw = p.read_text(encoding="utf-8", errors="replace")
        self.raw_xml_editor.setPlainText(raw)
        self.raw_xml_path_label.setText(str(p))
        self.log(f"[XML Editor] Loaded {len(self._types_elems)} types from {p.name}")

    def _get_text(self, el: ET.Element, tag: str, default: str = "0") -> str:
        child = el.find(tag)
        return child.text.strip() if child is not None and child.text else default

    def _get_attr(self, el: ET.Element, tag: str, attr: str, default: str = "") -> str:
        child = el.find(tag)
        return child.get(attr, default) if child is not None else default

    def _populate_types_table(self) -> None:
        self._types_loading = True
        self.types_table.setSortingEnabled(False)
        self.types_table.setRowCount(0)

        cats: set[str] = set()
        usages: set[str] = set()

        for el in self._types_elems:
            name = el.get("name", "")
            nominal = self._get_text(el, "nominal")
            lifetime = self._get_text(el, "lifetime")
            restock = self._get_text(el, "restock")
            min_val = self._get_text(el, "min")
            cat = self._get_attr(el, "category", "name")
            if cat:
                cats.add(cat)

            usage_parts = [u.get("name", "") for u in el.findall("usage") if u.get("name")]
            value_parts = [v.get("name", "") for v in el.findall("value") if v.get("name")]
            for u in usage_parts:
                usages.add(u)
            usage_val = ", ".join(filter(None, usage_parts + value_parts))

            # Raw XML snippet (shortened)
            raw_snip = f'<type name="{name}">…'

            row = self.types_table.rowCount()
            self.types_table.insertRow(row)

            items = [name, nominal, lifetime, restock, min_val, cat, usage_val, raw_snip]
            for col, val in enumerate(items):
                item = QTableWidgetItem(val)
                if col == 7:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setForeground(QColor("#3a6090"))
                self.types_table.setItem(row, col, item)

        # Update filter dropdowns
        self.types_cat_filter.blockSignals(True)
        self.types_usage_filter.blockSignals(True)
        current_cat = self.types_cat_filter.currentText()
        current_usage = self.types_usage_filter.currentText()
        self.types_cat_filter.clear()
        self.types_cat_filter.addItem("All categories")
        for c in sorted(cats):
            self.types_cat_filter.addItem(c)
        self.types_usage_filter.clear()
        self.types_usage_filter.addItem("All usages")
        for u in sorted(usages):
            self.types_usage_filter.addItem(u)
        self.types_cat_filter.blockSignals(False)
        self.types_usage_filter.blockSignals(False)
        idx = self.types_cat_filter.findText(current_cat)
        if idx >= 0:
            self.types_cat_filter.setCurrentIndex(idx)
        idx = self.types_usage_filter.findText(current_usage)
        if idx >= 0:
            self.types_usage_filter.setCurrentIndex(idx)

        self.types_table.setSortingEnabled(True)
        self._types_loading = False
        self.types_count_label.setText(f"Loaded {len(self._types_elems)} types.")
        self.filter_types_table()

    def _on_types_cell_changed(self, row: int, col: int) -> None:
        if self._types_loading:
            return
        if col not in (0, 1, 2, 3, 4, 5):
            return
        item = self.types_table.item(row, col)
        if item is None:
            return
        val = item.text().strip()

        visible_row = 0
        actual_idx = -1
        for r in range(self.types_table.rowCount()):
            if not self.types_table.isRowHidden(r):
                if visible_row == row:
                    actual_idx = r
                    break
                visible_row += 1

        if actual_idx < 0:
            actual_idx = row

        # Map visible row to _types_elems index via name column
        name_item = self.types_table.item(row, 0)
        if name_item is None:
            return
        name = name_item.text()
        el = next((e for e in self._types_elems if e.get("name") == name), None)
        if el is None:
            return

        col_map = {0: "name_attr", 1: "nominal", 2: "lifetime", 3: "restock", 4: "min", 5: "category"}
        field = col_map[col]

        if field == "name_attr":
            el.set("name", val)
        elif field == "category":
            cat_el = el.find("category")
            if cat_el is not None:
                cat_el.set("name", val)
            else:
                new_cat = ET.SubElement(el, "category")
                new_cat.set("name", val)
        else:
            child = el.find(field)
            if child is not None:
                child.text = val
            else:
                new_child = ET.SubElement(el, field)
                new_child.text = val

    def filter_types_table(self) -> None:
        search = self.types_search.text().strip().lower()
        cat_filter = self.types_cat_filter.currentText()
        usage_filter = self.types_usage_filter.currentText()
        visible = 0
        for row in range(self.types_table.rowCount()):
            name_item = self.types_table.item(row, 0)
            cat_item = self.types_table.item(row, 5)
            usage_item = self.types_table.item(row, 6)
            name = name_item.text().lower() if name_item else ""
            cat = cat_item.text() if cat_item else ""
            usage = usage_item.text() if usage_item else ""

            show = True
            if search and search not in name:
                show = False
            if cat_filter != "All categories" and cat != cat_filter:
                show = False
            if usage_filter != "All usages" and usage_filter not in usage:
                show = False

            self.types_table.setRowHidden(row, not show)
            if show:
                visible += 1

        total = self.types_table.rowCount()
        if search or cat_filter != "All categories" or usage_filter != "All usages":
            self.types_count_label.setText(f"Showing {visible} of {total} types.")
        else:
            self.types_count_label.setText(f"Loaded {total} types.")

    def save_types_xml(self) -> None:
        if not self._types_tree or not self._types_path:
            QMessageBox.warning(self, "Nothing to save", "No types.xml is loaded.")
            return
        try:
            ET.indent(self._types_tree.getroot(), space="    ")
        except AttributeError:
            pass
        try:
            self._types_tree.write(
                self._types_path,
                encoding="utf-8",
                xml_declaration=True,
            )
            self.raw_xml_editor.setPlainText(
                Path(self._types_path).read_text(encoding="utf-8", errors="replace")
            )
            self.log(f"[XML Editor] Saved types.xml → {self._types_path}")
            QMessageBox.information(self, "Saved", f"types.xml saved successfully:\n{self._types_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save error", f"Could not save:\n{e}")

    def split_types_by_category(self) -> None:
        if not self._types_elems:
            QMessageBox.warning(self, "Nothing loaded", "Load a types.xml file first.")
            return
        dest_dir = QFileDialog.getExistingDirectory(
            self, "Choose output folder", str(Path(self._types_path).parent) if self._types_path else str(Path.home())
        )
        if not dest_dir:
            return

        cat_map: dict[str, list[ET.Element]] = {}
        for el in self._types_elems:
            cat_el = el.find("category")
            cat = cat_el.get("name", "Uncategorized") if cat_el is not None else "Uncategorized"
            if not cat:
                cat = "Uncategorized"
            cat_map.setdefault(cat, []).append(el)

        dest = Path(dest_dir)
        created = 0
        for cat, elems in cat_map.items():
            root_el = ET.Element("types")
            for e in elems:
                root_el.append(e)
            try:
                ET.indent(root_el, space="    ")
            except AttributeError:
                pass
            tree = ET.ElementTree(root_el)
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in cat)
            out_path = dest / f"types_{safe_name}.xml"
            tree.write(str(out_path), encoding="utf-8", xml_declaration=True)
            created += 1

        self.log(f"[XML Editor] Split types.xml into {created} category files in {dest_dir}")
        QMessageBox.information(
            self, "Split complete",
            f"Created {created} category files in:\n{dest_dir}"
        )

    def check_types_duplicates(self) -> None:
        if not self._types_elems:
            QMessageBox.warning(self, "Nothing loaded", "Load a types.xml file first.")
            return
        seen: dict[str, list[int]] = {}
        for idx, el in enumerate(self._types_elems):
            name = el.get("name", "")
            seen.setdefault(name.lower(), []).append(idx + 1)

        dupes = {n: lines for n, lines in seen.items() if len(lines) > 1}
        if not dupes:
            QMessageBox.information(self, "No duplicates", f"No duplicate type names found in {len(self._types_elems)} types.")
            return

        msg = f"Found {len(dupes)} duplicate type name(s):\n\n"
        for name, lines in sorted(dupes.items())[:30]:
            msg += f"  • {name}  (rows {', '.join(str(l) for l in lines)})\n"
        if len(dupes) > 30:
            msg += f"\n  … and {len(dupes) - 30} more."
        QMessageBox.warning(self, f"Duplicates found ({len(dupes)})", msg)

    # ── Raw XML editor ─────────────────────────────────────────────────────

    def save_raw_xml(self) -> None:
        path = self._types_path
        if not path:
            QMessageBox.warning(self, "No file", "Load a types.xml file in the Types.xml tab first.")
            return
        content = self.raw_xml_editor.toPlainText()
        try:
            ET.fromstring(content)
        except ET.ParseError as e:
            if QMessageBox.question(
                self, "XML error",
                f"The XML has parse errors:\n{e}\n\nSave anyway?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.No:
                return
        try:
            Path(path).write_text(content, encoding="utf-8")
            self.log(f"[XML Editor] Raw XML saved → {path}")
            QMessageBox.information(self, "Saved", f"File saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))

    def _reload_raw_xml_from_disk(self) -> None:
        path = self._types_path
        if not path or not Path(path).exists():
            QMessageBox.warning(self, "No file", "Load a types.xml file first.")
            return
        self.raw_xml_editor.setPlainText(
            Path(path).read_text(encoding="utf-8", errors="replace")
        )

    # ── JSON editor ────────────────────────────────────────────────────────

    def open_json_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open JSON file", str(Path.home()),
            "JSON Files (*.json);;All Files (*)"
        )
        if path:
            self.json_path_edit.setText(path)
            try:
                content = Path(path).read_text(encoding="utf-8", errors="replace")
                self.json_editor.setPlainText(content)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def save_json_file(self) -> None:
        path = self.json_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "No file", "Open a JSON file first.")
            return
        content = self.json_editor.toPlainText()
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            if QMessageBox.question(
                self, "JSON error",
                f"Invalid JSON:\n{e}\n\nSave anyway?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.No:
                return
        try:
            Path(path).write_text(content, encoding="utf-8")
            QMessageBox.information(self, "Saved", f"JSON saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))

    def format_json(self) -> None:
        content = self.json_editor.toPlainText()
        try:
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=4, ensure_ascii=False)
            self.json_editor.setPlainText(formatted)
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Invalid JSON", f"Cannot format:\n{e}")

    # ──────────────────────────── SCHEDULER ────────────────────────────

    def restart_mode(self) -> str:
        if self.r_days.isChecked():
            return "days"
        if self.r_fixed.isChecked():
            return "fixed"
        return "hours"

    def _next_restart_after(self, now: datetime) -> Optional[datetime]:
        if self.r_days.isChecked():
            return (now + timedelta(days=max(1, self.days_spin.value()))).replace(
                microsecond=0
            )
        if self.r_hours.isChecked():
            step = max(1, self.hours_spin.value())
            if 24 % step == 0:
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
                for h in range(0, 24, step):
                    cand = midnight + timedelta(hours=h)
                    if cand > now:
                        return cand
                return midnight + timedelta(days=1)
            return (now + timedelta(hours=step)).replace(microsecond=0)
        times = []
        for token in [x.strip() for x in self.fixed_times.text().split(",") if x.strip()]:
            try:
                hh, mm = token.split(":", 1)
                times.append((int(hh), int(mm)))
            except Exception:
                pass
        for offset in range(0, 8):
            day = now.date() + timedelta(days=offset)
            for hh, mm in times:
                cand = datetime(day.year, day.month, day.day, hh, mm, 0)
                if cand > now:
                    return cand
        return None

    def preview_restart_schedule(self) -> None:
        now = datetime.now().replace(microsecond=0)
        self.next_restart = self._next_restart_after(now - timedelta(seconds=1))
        self.refresh_restart_preview()
        QMessageBox.information(self, "Restart preview", "Restart table updated.")

    def refresh_restart_preview(self) -> None:
        now = datetime.now().replace(microsecond=0)
        next_restart = self.next_restart or self._next_restart_after(now)
        self.next_restart = next_restart
        rows = []
        if next_restart:
            for mins in (15, 10, 5, 1):
                notify = next_restart - timedelta(minutes=mins)
                if notify > now:
                    rows.append(
                        (
                            next_restart,
                            notify,
                            f"Server restart in {mins} minute{'s' if mins != 1 else ''}.",
                        )
                    )
        self.schedule_table.setRowCount(len(rows))
        for r, (restart_dt, notify_dt, text) in enumerate(rows):
            self.schedule_table.setItem(
                r, 0, QTableWidgetItem(restart_dt.strftime("%Y-%m-%d %H:%M:%S"))
            )
            self.schedule_table.setItem(
                r, 1, QTableWidgetItem(notify_dt.strftime("%Y-%m-%d %H:%M:%S"))
            )
            self.schedule_table.setItem(r, 2, QTableWidgetItem(text))

    def export_messages_json(self) -> None:
        self.preview_restart_schedule()
        if not self.next_restart:
            QMessageBox.warning(self, "Schedule", "No schedule available.")
            return
        out, _ = QFileDialog.getSaveFileName(
            self,
            "Save messages.json",
            str(Path.home() / "messages.json"),
            "JSON (*.json)",
        )
        if not out:
            return
        now = datetime.now().astimezone()
        utc_offset = int(
            (now.utcoffset().total_seconds() if now.utcoffset() else 0) // 3600
        )
        payload = {
            "m_Version": 2,
            "Enabled": 1,
            "UTC": utc_offset,
            "UseMissionTime": 0,
            "Notifications": [],
        }
        next_restart = self.next_restart
        for mins in (15, 10, 5, 1):
            notify = next_restart - timedelta(minutes=mins)
            payload["Notifications"].append(
                {
                    "Hour": notify.hour,
                    "Minute": notify.minute,
                    "Second": notify.second,
                    "Title": "RESTART",
                    "Text": f"Server restart in {mins} minute{'s' if mins != 1 else ''}.",
                    "Icon": "Info",
                    "Color": "#FF0000",
                }
            )
        Path(out).write_text(
            json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8"
        )
        QMessageBox.information(self, "Exported", f"Saved to:\n{out}")

    def arm_scheduler(self) -> None:
        self.scheduler_enabled = True
        self.notified_marks.clear()
        self.preview_restart_schedule()
        self.scheduler_timer.start()
        self.log("Scheduler armed.")

    def disarm_scheduler(self) -> None:
        self.scheduler_enabled = False
        self.scheduler_timer.stop()
        self.notified_marks.clear()
        self.log("Scheduler disarmed.")

    def _tick_scheduler(self) -> None:
        if not self.scheduler_enabled:
            return
        if not self.next_restart:
            self.next_restart = self._next_restart_after(
                datetime.now().replace(microsecond=0)
            )
        if not self.next_restart:
            return
        now = datetime.now().replace(microsecond=0)
        remaining = max(0, int((self.next_restart - now).total_seconds()))
        for mins in (15, 10, 5, 1):
            if mins not in self.notified_marks and remaining <= mins * 60:
                self.notified_marks.add(mins)
                self.log(f"Restart warning: {mins} minute(s) left.")
        if remaining == 0:
            self.log("Scheduled restart triggered.")
            self.restart_server()
            self.notified_marks.clear()
            self.next_restart = self._next_restart_after(
                datetime.now().replace(microsecond=0) + timedelta(seconds=1)
            )

    # ──────────────────────────── LOGS ────────────────────────────

    def refresh_logs_view(self) -> None:
        if not hasattr(self, "log_view") or self.chk_pause.isChecked():
            return
        q = self.log_search.text().lower().strip()
        out = []
        for line in self.logs_raw:
            low = line.lower()
            if q and q not in low:
                continue
            is_error = "error" in low or "[err]" in low
            is_warn = "warn" in low
            is_be = "battleye" in low or "battley" in low
            if (
                (is_error and self.chk_error.isChecked())
                or (is_warn and self.chk_warn.isChecked())
                or (is_be and self.chk_be.isChecked())
                or (
                    not is_error
                    and not is_warn
                    and not is_be
                    and self.chk_info.isChecked()
                )
            ):
                out.append(line)
        self.log_view.blockSignals(True)
        self.log_view.setPlainText("\n".join(out))
        self.log_view.blockSignals(False)

    def tail_logs(self, count: int) -> None:
        self.logs_raw = self.logs_raw[-count:]
        self.refresh_logs_view()

    def export_logs(self) -> None:
        out, _ = QFileDialog.getSaveFileName(
            self,
            "Export logs",
            str(Path.home() / "btz_logs.txt"),
            "Text (*.txt)",
        )
        if not out:
            return
        Path(out).write_text("\n".join(self.logs_raw) + "\n", encoding="utf-8")
        QMessageBox.information(self, "Exported", f"Logs exported to:\n{out}")

    # ──────────────────────────── MISC ────────────────────────────

    def open_root(self) -> None:
        root = self.server_root.text().strip()
        if root and Path(root).exists():
            if os.name == "nt":
                os.startfile(root)
            else:
                subprocess.Popen(["xdg-open", root])

    def closeEvent(self, event) -> None:
        self.save_settings()
        try:
            if self.process and self.process.state() != QProcess.NotRunning:
                self.process.terminate()
                self.process.waitForFinished(2000)
                if self.process.state() != QProcess.NotRunning:
                    self.process.kill()
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
