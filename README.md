# 🩸 BrutalZ Control Center

Modern all-in-one DayZ Server Manager with a clean UI, advanced tools and automation.

---

## 🚀 Features

- 🖥️ Server control (Start / Stop / Restart / Force Restart)
- 📜 Live console & log viewer (with filters)
- 🔧 Automatic `start.bat` generator (pro optimized)
- 📦 Mod manager (client / server separation)
- 🔒 Banlist editor (BattlEye compatible)
- ⏱️ Advanced restart scheduler (hours / days / fixed times)
- 🔔 Auto `messages.xml` generator (restart warnings synced)
- 🌦️ Weather editor (cfgweather.xml visual builder)
- 🧠 XML Validator (scan full mission folder)
- 🧾 Types.xml tools (edit, split, duplicate check)
- 📊 JSON tools (validate, pretty, minify)
- 📍 Spawn editor (export CSV)
- 📂 Raw XML editor
- 🎮 Dashboard with uptime, status and stats
- 💬 Integrated Discord support button

---

## 🧩 Installation

1. Download the installer or `.exe`
2. Run it
3. Select your DayZ Server folder
4. Done ✅

---

## 🛠️ Build from source (optional)

```bash
pyinstaller --noconfirm --onefile --windowed --collect-all PySide6 dayz_manager_app.py
