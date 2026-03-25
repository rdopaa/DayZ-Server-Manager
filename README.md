# BrutalZ Control Center 🩸

**BrutalZ Control Center** is a modern desktop app for managing a DayZ server from one place.  
It combines server start/stop controls, mod detection, restart scheduling, XML validation, `types.xml` tools, weather helpers, banlist editing, JSON tools, and a live log console in a dark Steam-style interface.

---

## Features

- **Server Dashboard**
  - Live server status indicator:
    - 🟢 Started
    - 🟡 Starting
    - 🔴 Off
  - Start / Stop / Restart / Force Restart
  - Command preview for the generated `.bat`
  - Integrated console/log output

- **Mods Manager**
  - Detects `@` folders from the DayZ server root
  - Moves mods between:
    - Client mods
    - Server-side mods
  - Auto-suggests possible server-side mods
  - Generates a ready-to-use `start.bat`

- **Banlist Manager**
  - Load, edit, reorder, and save `banlist.txt`
  - Raw text editor + list view

- **Restart Scheduler**
  - Restart every N hours
  - Restart every N days
  - Fixed restart times
  - Notification previews and `messages.json` export

- **XML Validator**
  - Recursively scans `.xml` files
  - Reports line / column / parsing errors
  - Exports reports to CSV

- **Config Tools**
  - `types.xml` loader and editor
  - Duplicate checker
  - Split `types.xml` by category
  - Weather config helper
  - Day / night calculator
  - JSON validator / formatter
  - Spawn point helper
  - Raw XML editor

- **Modern UI**
  - Dark Steam-inspired design
  - Clean layout
  - Sidebar navigation
  - Footer support link

---

## Screenshots

> Add your own screenshots here after packaging the app.

Example:

```md
![Dashboard](docs/screenshots/dashboard.png)
![Mods](docs/screenshots/mods.png)
```

---

## Requirements

- Windows 10 / 11
- Python 3.10+
- [PySide6](https://pypi.org/project/PySide6/)

---

## Installation

```bash
pip install PySide6
```

---

## Run from source

```bash
python dayz_manager_app.py
```

---

## Build an EXE

Using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name BrutalZControlCenter dayz_manager_app.py
```

The final executable will be created inside the `dist` folder.

---

## Recommended folder setup

Example:

```text
DayZServer/
├── DayZServer_x64.exe
├── serverDZ.cfg
├── profiles/
├── BattlEye/
├── mpmissions/
└── @YourMod/
```

---

## Discord Support

Join the official support Discord:

[Support from Oficial Discord](https://discord.gg/uaH3k8WRUN)

---

## Notes

- The app is designed to work as an administration panel for your DayZ server.
- Restart scheduling and messages are meant to match your configured restart plan.
- XML validation checks that files are well-formed and reports readable errors.

---

## License

Add your preferred license here before publishing on GitHub.
