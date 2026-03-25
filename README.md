# 🎮 BTZ DayZ Manager

> A professional all-in-one control panel for DayZ server administrators.

---

## What is it?

**BTZ DayZ Manager** is a Windows desktop application that lets you manage your DayZ server without touching the command line, editing config files by hand, or babysitting the machine waiting for something to crash. Everything from a single modern dark-themed interface full control over every aspect of your server.
<img width="1565" height="980" alt="image" src="https://github.com/user-attachments/assets/69962baa-3c38-4cb1-9280-e3c510857de6" />
<img width="1560" height="983" alt="image" src="https://github.com/user-attachments/assets/03c74b01-4a29-4f1f-b3b9-96c1c64bc49b" />
<img width="1545" height="842" alt="image" src="https://github.com/user-attachments/assets/5dedb7de-b08e-4659-bada-7419a1e9e6a2" />

---

## ✨ Features

### ⚡ Dashboard
- Real-time server status: **ONLINE / STARTING / OFFLINE**
- Live process PID, uptime, CPU and RAM usage
- **Live console** with built-in **Ctrl+F search** — highlight matches, navigate next/previous, wrap-around, Escape to close
- Send RCON commands directly from the dashboard
- Start, Stop, Restart and Force Restart buttons

### ⚙️ Server Configuration
- Set paths for executable, server root, BattlEye folder, mission and profiles
- Port, server name, config file
- Launch options: `-dologs`, `-adminlog`, `-netlog`, `-freezecheck`
- Process priority and CPU affinity (Normal / Above Normal / High)
- **Real-time `.bat` preview** — see the exact launch command before saving it
- **start.bat generator** using the clean standard template format (`set mods=`, `set servermods=`, `^` line continuations)

### 🧩 Mods
- Separate lists for **Client Mods** and **Server Mods**
- Manual mod entry — no folder scanning required
- Auto-detection from the server directory
- SteamCMD workshop updater — update one mod or all at once
- Workshop ID integration for automated downloads

### 📁 Profiles
- Full file explorer for the server profiles folder
- Built-in text editor supporting: `.cfg`, `.json`, `.xml`, `.ini`, `.txt`, `.log`, `.bat`, `.hpp`, `.rpt`, `.adm`, `.sqf`, `.sqm`
- Auto pretty-print for JSON files on open
- Save, Reload, and Open in Explorer — all from within the app

### 🔌 RCON
- Native BattlEye RCON over UDP with correct protocol implementation
- Command console with quick-action buttons: `players`, `say`, `#shutdown`, `#lock`, `#unlock`
- Built-in setup guide for `BEServer_x64.cfg` configuration

### 👥 Players
- Live connected player list via RCON
- Kick and ban directly from the list
- Auto-refresh every 10 seconds

### 📊 Performance
- Real-time CPU, RAM and player count charts
- Up to 120 data points of history
- Timestamped data table

### 🔍 XML / Config Tools
- XML validator for types, events and spawn files
- `types.xml` editor with search, filters and inline value editing
- Config diff viewer — compare two versions of any config file
- Spawnpoints editor

### 💾 Backups
- Manual and automatic scheduled backups
- One-click restore from backup
- Configurable interval and destination folder

### 🚫 Bans
- Ban list management by GUID / SteamID
- Add, remove and export bans
- Ban reason support

### 🕒 Scheduler
- Automated scheduled restarts by time of day
- Discord notifications before each scheduled restart
- Schedule export for external use

### 💬 Discord Webhooks
- Notifications for: server start, stop, crash, restart and player events
- Independent webhook URL per event type
- Custom server name for all messages

### 🔄 Crash Recovery
- Automatic crash detection (unexpected process exit)
- **Configurable auto-restart** with custom delay
- Discord notification on crash detection

---

## ⚙️ Easy Installation
- Install .EXE from Release

> **Tip:** On first launch, right-click → "Run as administrator" so that auto-restart and firewall rule management work without interruption.

---

## 📋 RCON Setup

To use RCON, your `<ServerRoot>\battleye\BEServer_x64.cfg` must contain:

```
RConPassword YourPasswordHere
RConPort 2305
```

The default RCON port is **game port + 3** (e.g. 2302 → 2306).

---

## 🎯 Generated start.bat format

The app generates a clean, readable one-shot launcher:

```batch
@echo off
title DayZ Server MyServer

set mods=@CF;@DabsFramework;@DayZ-Expansion-Core
set servermods=@AutoStack;@DynamicAI

echo =====================================
echo  Starting DayZ Server: MyServer
echo =====================================
echo.

start "" "C:\dayzserver\DayZServer_x64.exe" ^
    -config=serverDZ.cfg ^
    -port=2302 ^
    -profiles=profiles ^
    -name=MyServer ^
    -mod=%mods% ^
    -servermod=%servermods% ^
    -dologs ^
    -adminlog ^
    -netlog ^
    -freezecheck ^
    -BEPath="C:\dayzserver\battleye"
```

No restart loop — restarts are managed by the app. The `.bat` is a clean one-shot launcher.

---

## 🤝 Official Support

If you need support, go to our official discord and open a ticket:
https://discord.gg/uaH3k8WRUN

---

## 🤝 Contributing

Pull requests are welcome. If you find a bug or want a new feature, open an Issue.

---

## 📄 License

MIT — use, modify and distribute freely.

---

<div align="center">
  <b>Built for the DayZ server community 🌍</b>
</div>
