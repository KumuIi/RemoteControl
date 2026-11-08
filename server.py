from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import pyautogui
import pyperclip
import socket
import shutil
import ctypes
import subprocess
import sys
import io
import os
import logging
import mimetypes
import qrcode
from cursor_overlay import CursorOverlay

logging.getLogger("werkzeug").setLevel(logging.ERROR)

# Windows' registry often maps .js to text/plain; serve the bundled
# socket.io.min.js with the proper type so Safari (iPhone) runs it.
mimetypes.add_type("text/javascript", ".js")

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# PyInstaller bundles files into sys._MEIPASS at runtime
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))
app.config["SECRET_KEY"] = "rc-local"
socketio = SocketIO(app, cors_allowed_origins="*")

INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "KumuRemote")
INSTALL_EXE = os.path.join(INSTALL_DIR, "KumuRemote.exe")
PORT = 5000
FIREWALL_RULE = "KumuRemote"
ELEVATED_FLAG = "--elevated"

# Draws the pointer ourselves when Windows hides it (no mouse attached)
cursor_overlay = CursorOverlay()


@app.route("/")
def index():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "index.html")


@socketio.on("mouse_move")
def on_mouse_move(data):
    pyautogui.moveRel(data["dx"], data["dy"])
    cursor_overlay.poke()


@socketio.on("click")
def on_click(data):
    pyautogui.click(button=data.get("button", "left"))
    cursor_overlay.poke()


@socketio.on("double_click")
def on_double_click(_):
    pyautogui.doubleClick()
    cursor_overlay.poke()


@socketio.on("scroll")
def on_scroll(data):
    # dy is in raw Windows wheel units (120 = one notch); the phone applies
    # the scroll-speed multiplier and only ever sends whole units.
    pyautogui.scroll(int(data["dy"]))


@socketio.on("key")
def on_key(data):
    keys = data["keys"]
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)


@socketio.on("type_text")
def on_type(data):
    text = data.get("text", "")
    if not text:
        return
    try:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    except Exception:
        pyautogui.typewrite(text, interval=0.02)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def print_qr(url):
    buf = io.StringIO()
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(out=buf, invert=True)
    sys.stdout.buffer.write(buf.getvalue().encode("utf-8"))
    sys.stdout.buffer.flush()


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_admin():
    """
    Ask for admin rights exactly once, right at startup.
    - Already elevated (e.g. Task Scheduler "Run with highest privileges",
      or our own relaunch) -> no prompt at all, just continue.
    - Not elevated -> relaunch this program via UAC ("runas") and exit.
    - UAC declined -> keep running without admin (works, but can't control
      windows of programs that themselves run as admin).
    """
    if is_admin():
        return
    if ELEVATED_FLAG in sys.argv:
        # We already tried once — never loop.
        print("  (Running without admin rights)")
        return

    if getattr(sys, "frozen", False):
        args = sys.argv[1:]
    else:
        args = [os.path.abspath(sys.argv[0])] + sys.argv[1:]
    params = subprocess.list2cmdline(args + [ELEVATED_FLAG])

    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, os.getcwd(), 1
    )
    if rc > 32:
        sys.exit(0)  # the elevated copy takes over
    print("  (Admin rights declined — running without them)")


def ensure_firewall_rule():
    """
    While elevated, allow inbound TCP on our port for this exe ourselves, so
    Windows never pops its own firewall dialog (which would be a 2nd prompt).
    Recreated each start so it always matches the current exe path.
    """
    if not is_admin():
        return
    flags = subprocess.CREATE_NO_WINDOW
    subprocess.run(
        ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={FIREWALL_RULE}"],
        capture_output=True, creationflags=flags,
    )
    subprocess.run(
        ["netsh", "advfirewall", "firewall", "add", "rule", f"name={FIREWALL_RULE}",
         "dir=in", "action=allow", "protocol=TCP", f"localport={PORT}",
         f"program={os.path.abspath(sys.executable)}", "profile=any"],
        capture_output=True, creationflags=flags,
    )


def install_and_shortcut():
    """
    If running as a bundled exe from outside the install folder, copy the exe
    to AppData\\Local\\KumuRemote\\ so it survives the original download being deleted.
    Creates the desktop shortcut only if it is missing or points elsewhere, so
    settings you make on the shortcut are kept.
    """
    if not getattr(sys, "frozen", False):
        # Raw Python — nothing to install
        _create_shortcut(sys.executable)
        return

    current = os.path.abspath(sys.executable)
    target  = os.path.abspath(INSTALL_EXE)

    if current.lower() != target.lower():
        try:
            os.makedirs(INSTALL_DIR, exist_ok=True)
            shutil.copy2(current, target)
            print(f"  Installed to {target}")
        except OSError as e:
            # e.g. the installed copy is currently running (autostart task)
            print(f"  (Install skipped: {e})")

    _create_shortcut(target)


def _create_shortcut(exe_path):
    try:
        work_dir = os.path.dirname(exe_path)
        ps = (
            "$ws = New-Object -ComObject WScript.Shell;"
            "$p = Join-Path ([Environment]::GetFolderPath('Desktop')) 'KumuRemote.lnk';"
            f"if ((Test-Path $p) -and ($ws.CreateShortcut($p).TargetPath -eq '{exe_path}')) {{ 'exists'; exit }};"
            "$sc = $ws.CreateShortcut($p);"
            f"$sc.TargetPath = '{exe_path}';"
            f"$sc.WorkingDirectory = '{work_dir}';"
            f"$sc.IconLocation = '{exe_path},0';"
            "$sc.Description = 'KumuRemote - PC Remote Control';"
            "$sc.Save(); 'created'"
        )
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout.strip()
        if out == "created":
            print("  Desktop shortcut created.")
    except Exception as e:
        print(f"  (Shortcut skipped: {e})")


if __name__ == "__main__":
    ensure_admin()          # the one and only UAC prompt (none if already admin)
    ensure_firewall_rule()  # prevents the Windows firewall dialog
    install_and_shortcut()
    cursor_overlay.start()  # --cursor=auto|always|off

    ip = get_local_ip()
    url = f"http://{ip}:{PORT}"
    print()
    print("  KumuRemote")
    print("  ──────────────────────────────")
    print(f"  {url}")
    print("  ──────────────────────────────")
    print_qr(url)
    print("  Scan the QR code or open the URL above on your phone (same WiFi)")
    print("  Ctrl+C to stop")
    print()
    socketio.run(app, host="0.0.0.0", port=PORT, debug=False,
                 log_output=False, use_reloader=False, allow_unsafe_werkzeug=True)
