from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import pyautogui
import pyperclip
import socket
import subprocess
import sys
import io
import os
import qrcode

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# PyInstaller bundles files into sys._MEIPASS at runtime
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))
app.config["SECRET_KEY"] = "rc-local"
# No async_mode specified — lets python-socketio auto-detect the threading driver.
# Explicit async_mode="threading" causes PyInstaller to fail because the driver
# module is loaded dynamically and not picked up by the bundler.
socketio = SocketIO(app, cors_allowed_origins="*")


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


def create_desktop_shortcut():
    """Creates a desktop shortcut pointing to this exe using PowerShell COM."""
    try:
        exe_path = sys.executable
        work_dir = os.path.dirname(exe_path)
        # Resolve the real Desktop folder (handles OneDrive-redirected desktops)
        desktop = subprocess.check_output(
            ["powershell", "-Command",
             "[Environment]::GetFolderPath('Desktop')"],
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
    create_desktop_shortcut()

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
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
