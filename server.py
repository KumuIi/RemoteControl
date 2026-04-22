from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import pyautogui
import pyperclip
import socket
import shutil
import subprocess
import sys
import io
import os
import logging
import qrcode

logging.getLogger("werkzeug").setLevel(logging.ERROR)

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# PyInstaller bundles files into sys._MEIPASS at runtime
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))
app.config["SECRET_KEY"] = "rc-local"
socketio = SocketIO(app, cors_allowed_origins="*")

INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "KumuRemote")
INSTALL_EXE = os.path.join(INSTALL_DIR, "KumuRemote.exe")


@app.route("/")
def index():
    return send_from_directory(os.path.join(BASE_DIR, "static"), "index.html")


@socketio.on("mouse_move")
def on_mouse_move(data):
    pyautogui.moveRel(data["dx"], data["dy"])


@socketio.on("click")
def on_click(data):
    pyautogui.click(button=data.get("button", "left"))


@socketio.on("double_click")
def on_double_click(_):
    pyautogui.doubleClick()


@socketio.on("scroll")
def on_scroll(data):
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


def install_and_shortcut():
    """
    If running as a bundled exe from outside the install folder, copy the exe
    to AppData\\Local\\KumuRemote\\ so it survives the original download being deleted.
    Always (re)creates the desktop shortcut pointing to the installed path.
    """
    if not getattr(sys, "frozen", False):
        # Raw Python — nothing to install
        _create_shortcut(sys.executable)
        return

    current = os.path.abspath(sys.executable)
    target  = os.path.abspath(INSTALL_EXE)

    if current.lower() != target.lower():
        os.makedirs(INSTALL_DIR, exist_ok=True)
        shutil.copy2(current, target)
        print(f"  Installed to {target}")

    _create_shortcut(target)


def _create_shortcut(exe_path):
    try:
        work_dir = os.path.dirname(exe_path)
        desktop = subprocess.check_output(
            ["powershell", "-Command", "[Environment]::GetFolderPath('Desktop')"],
            text=True
        ).strip()
        shortcut_path = os.path.join(desktop, "KumuRemote.lnk")
        ps = (
            f"$ws = New-Object -ComObject WScript.Shell;"
            f"$sc = $ws.CreateShortcut('{shortcut_path}');"
            f"$sc.TargetPath = '{exe_path}';"
            f"$sc.WorkingDirectory = '{work_dir}';"
            f"$sc.IconLocation = '{exe_path},0';"
            f"$sc.Description = 'KumuRemote - PC Remote Control';"
            f"$sc.Save()"
        )
        subprocess.run(["powershell", "-Command", ps], capture_output=True)
        print("  Desktop shortcut created.")
    except Exception as e:
        print(f"  (Shortcut skipped: {e})")


if __name__ == "__main__":
    install_and_shortcut()

    ip = get_local_ip()
    url = f"http://{ip}:5000"
    print()
    print("  KumuRemote")
    print("  ──────────────────────────────")
    print(f"  {url}")
    print("  ──────────────────────────────")
    print_qr(url)
    print("  Scan the QR code or open the URL above on your phone (same WiFi)")
    print("  Ctrl+C to stop")
    print()
    socketio.run(app, host="0.0.0.0", port=5000, debug=False,
                 log_output=False, use_reloader=False, allow_unsafe_werkzeug=True)
