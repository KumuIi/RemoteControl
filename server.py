from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import pyautogui
import pyperclip
import socket
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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


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
        # clipboard paste handles unicode; typewrite only handles ASCII
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
    # Write encoded bytes directly — avoids closing sys.stdout.buffer
    sys.stdout.buffer.write(buf.getvalue().encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    ip = get_local_ip()
    url = f"http://{ip}:5000"
    print()
    print("  PC Remote Control")
    print("  ──────────────────────────────")
    print(f"  {url}")
    print("  ──────────────────────────────")
    print_qr(url)
    print("  Scan the QR code or open the URL above on your phone (same WiFi)")
    print("  Ctrl+C to stop")
    print()
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
