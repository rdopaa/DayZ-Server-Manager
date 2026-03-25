# 🩸 BrutalZ Control Center

Modern all-in-one DayZ Server Manager with a clean UI, advanced tools and automation.

---
<img width="1919" height="1012" alt="image" src="https://github.com/user-attachments/assets/32e25300-ab60-4d25-9a8c-c0d5cf2d1865" />
<img width="1920" height="1014" alt="image" src="https://github.com/user-attachments/assets/953d6121-9dc0-4979-b0be-b63de1aaba23" />

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
