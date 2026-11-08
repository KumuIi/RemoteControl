<div align="center">
  <img src="logo.png" width="120" alt="KumuRemote logo">
  <h1>KumuRemote</h1>
  <p>Control your Windows PC from your phone browser — no app install needed.</p>
</div>

---

## What it does

Run the server on your PC, scan a QR code with your phone, and instantly get:

- **Trackpad** — drag to move the mouse, tap to click, hold for right-click, two fingers to scroll
- **Media controls** — play/pause, seek, volume, YouTube shortcuts (J/K/L, F, T), browser navigation
- **Keyboard** — send any text (including emoji/unicode), shortcuts (Ctrl+C/V/Z/A, Alt+F4…), arrow keys

Both devices must be on the **same WiFi network**. The phone opens a webpage — no app install required.

---

## Download & Install

### Option 1 — Standalone .exe (recommended, no Python needed)

1. Go to [Releases](../../releases/latest)
2. Download `KumuRemote.exe`
3. Double-click it and accept the **one** admin prompt (UAC)
4. Scan the QR code shown in the terminal with your phone camera
5. Done — the remote opens in your phone's browser

On first run the exe copies itself to `%LOCALAPPDATA%\KumuRemote\` and puts a shortcut on your desktop.

#### Autostart at login (no prompt at all)
Open **Task Scheduler → Create Task**:
- **General:** tick **Run with highest privileges**
- **Triggers:** *At log on*
- **Actions:** start `%LOCALAPPDATA%\KumuRemote\KumuRemote.exe`
- **Conditions:** untick *Start only if on AC power* (laptops)

Because the task already runs elevated, KumuRemote detects that and skips the UAC prompt.

### Option 2 — Raw Python

**Requirements:** Python 3.10+

1. Download or clone this repo
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. **Right-click `start.bat` → Run as administrator**
4. Scan the QR code or type the URL shown into your phone browser

---

## Usage

### Trackpad tab
| Gesture | Action |
|---------|--------|
| Drag (1 finger) | Move mouse |
| Tap | Left click |
| Hold (~0.6s) | Right click |
| 2 fingers drag | Scroll |
| Speed slider | Adjust mouse sensitivity |
| Left / Double / Right buttons | Explicit clicks |

### Media tab
| Button | Action |
|--------|--------|
| ⏪ / ⏩ | Seek −10s / +10s |
| ⏯ | Play / Pause (Space) |
| Vol − / Mute / Vol + | System volume |
| Fullscreen (F) | Toggle fullscreen |
| Theater (T) | YouTube theater mode |
| YT Mute (M) | Mute YouTube |
| J / K / L | YouTube −10s / play / +10s |
| Back / Reload / Forward | Browser navigation |

### Keys tab
| Control | Action |
|---------|--------|
| Text field + ➤ | Type text into focused PC app (supports unicode & emoji) |
| Esc / Tab / Enter / ⌫ | Special keys |
| Copy / Paste / Undo / Sel All | Ctrl shortcuts |
| New Tab / Close Tab | Browser tabs |
| Arrow keys | Navigate |
| Alt+F4 | Close active window |

---

## Notes

- **Admin rights** — the exe asks once at startup (or not at all when already elevated, e.g. via Task Scheduler). Admin is needed to add the firewall rule and to control windows of programs that themselves run as administrator (many games).
- The exe creates a firewall rule named `KumuRemote` that only allows TCP port 5000 for KumuRemote itself, so Windows never shows its own firewall dialog. (`start.bat` uses a rule named `PC Remote Control`.)
- To remove the rule later: open Windows Firewall → Inbound Rules → delete `KumuRemote` / `PC Remote Control`.

---

<div align="center">
  Made by <a href="https://github.com/KumuIi">KumuIi</a>
</div>
