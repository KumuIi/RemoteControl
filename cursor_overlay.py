"""
On-screen cursor for PCs without a physical mouse.

Windows does not draw the mouse pointer when no mouse is attached: each
thread's cursor "show count" starts at -1 if no mouse is installed, and touch
input additionally suppresses the pointer. Moving the pointer with
SetCursorPos (what pyautogui does) or with injected SendInput events does not
change that, so on such a PC the pointer moved from the phone is invisible.

KumuRemote therefore draws the pointer itself: a tiny topmost layered window
that copies the current cursor shape and follows the real cursor position
while the phone is moving it, then fades out after a few idle seconds.
The window is click-through (WS_EX_TRANSPARENT), never activated
(WS_EX_NOACTIVATE) and kept out of the taskbar and Alt-Tab (WS_EX_TOOLWINDOW),
so clicks land on whatever is underneath and focus never moves.

Mode, chosen with the command line option --cursor=MODE:
  auto    draw only while Windows itself is not showing the pointer (default)
  always  draw on every phone mouse action, even when Windows shows a pointer
  off     never draw

Only ctypes is used (no Qt/numpy/tkinter), so the exe build stays small.
"""
import ctypes
import ctypes.wintypes as wt
import sys
import threading
import time

MODES = ("auto", "always", "off")
HOLD_SECONDS = 4.0    # fully visible this long after the last phone action
FADE_SECONDS = 0.4    # then fade out over this long
FRAME_MS = 15         # follow/fade timer while visible

# Own DLL instances: setting argtypes on ctypes.windll.user32 would change the
# signatures pyautogui uses through that shared object.
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
OVERLAY_EX_STYLE = (WS_EX_TOPMOST | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
                    | WS_EX_LAYERED | WS_EX_NOACTIVATE)

HWND_TOPMOST = wt.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x1, 0x2, 0x10, 0x40
SW_HIDE = 0
WM_NCHITTEST, WM_MOUSEACTIVATE, WM_TIMER, WM_DPICHANGED = 0x84, 0x21, 0x113, 0x2E0
WM_APP_POKE = 0x8000 + 1
HTTRANSPARENT, MA_NOACTIVATE = -1, 3
ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA = 0x2, 0x0, 0x1
CURSOR_SHOWING = 0x1
DI_NORMAL = 0x3
IDC_ARROW = 32512
DIB_RGB_COLORS = 0
MONITOR_DEFAULTTONEAREST = 2
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
TIMER_ID = 1

LRESULT = wt.LPARAM
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON), ("hCursor", wt.HANDLE),
                ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD),
                ("hCursor", wt.HANDLE), ("ptScreenPos", wt.POINT)]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wt.BOOL), ("xHotspot", wt.DWORD), ("yHotspot", wt.DWORD),
                ("hbmMask", wt.HBITMAP), ("hbmColor", wt.HBITMAP)]


class BITMAP(ctypes.Structure):
    _fields_ = [("bmType", wt.LONG), ("bmWidth", wt.LONG), ("bmHeight", wt.LONG),
                ("bmWidthBytes", wt.LONG), ("bmPlanes", wt.WORD),
                ("bmBitsPixel", wt.WORD), ("bmBits", wt.LPVOID)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


def _sig(dll, name, restype, *argtypes):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = restype, list(argtypes)


_sig(kernel32, "GetModuleHandleW", wt.HMODULE, wt.LPCWSTR)
_sig(user32, "RegisterClassExW", wt.ATOM, ctypes.POINTER(WNDCLASSEXW))
_sig(user32, "CreateWindowExW", wt.HWND, wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
     wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID)
_sig(user32, "DefWindowProcW", LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
_sig(user32, "GetMessageW", wt.BOOL, ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT)
_sig(user32, "TranslateMessage", wt.BOOL, ctypes.POINTER(wt.MSG))
_sig(user32, "DispatchMessageW", LRESULT, ctypes.POINTER(wt.MSG))
_sig(user32, "PostMessageW", wt.BOOL, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
_sig(user32, "SetTimer", ctypes.c_size_t, wt.HWND, ctypes.c_size_t, wt.UINT, wt.LPVOID)
_sig(user32, "KillTimer", wt.BOOL, wt.HWND, ctypes.c_size_t)
_sig(user32, "ShowWindow", wt.BOOL, wt.HWND, ctypes.c_int)
_sig(user32, "SetWindowPos", wt.BOOL, wt.HWND, wt.HWND,
     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT)
_sig(user32, "UpdateLayeredWindow", wt.BOOL, wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT),
     ctypes.POINTER(wt.SIZE), wt.HDC, ctypes.POINTER(wt.POINT), wt.COLORREF,
     ctypes.POINTER(BLENDFUNCTION), wt.DWORD)
_sig(user32, "GetCursorPos", wt.BOOL, ctypes.POINTER(wt.POINT))
_sig(user32, "GetCursorInfo", wt.BOOL, ctypes.POINTER(CURSORINFO))
_sig(user32, "LoadCursorW", wt.HANDLE, wt.HINSTANCE, wt.LPVOID)
_sig(user32, "GetIconInfo", wt.BOOL, wt.HANDLE, ctypes.POINTER(ICONINFO))
_sig(user32, "DrawIconEx", wt.BOOL, wt.HDC, ctypes.c_int, ctypes.c_int, wt.HANDLE,
     ctypes.c_int, ctypes.c_int, wt.UINT, wt.HBRUSH, wt.UINT)
_sig(user32, "MonitorFromPoint", wt.HMONITOR, wt.POINT, wt.DWORD)
_sig(gdi32, "CreateCompatibleDC", wt.HDC, wt.HDC)
_sig(gdi32, "CreateDIBSection", wt.HBITMAP, wt.HDC, ctypes.POINTER(BITMAPINFOHEADER),
     wt.UINT, ctypes.POINTER(wt.LPVOID), wt.HANDLE, wt.DWORD)
_sig(gdi32, "SelectObject", wt.HGDIOBJ, wt.HDC, wt.HGDIOBJ)
_sig(gdi32, "DeleteObject", wt.BOOL, wt.HGDIOBJ)
_sig(gdi32, "GetObjectW", ctypes.c_int, wt.HANDLE, ctypes.c_int, wt.LPVOID)
_sig(gdi32, "GdiFlush", wt.BOOL)


def mode_from_argv(argv):
    """--cursor=auto|always|off from the command line (default: auto)."""
    for arg in argv[1:]:
        if arg.startswith("--cursor="):
            mode = arg.split("=", 1)[1].strip().lower()
            if mode in MODES:
                return mode
            print(f"  (Unknown --cursor mode '{mode}', using auto)")
    return "auto"


class _Image:
    __slots__ = ("bitmap", "w", "h", "hot_x", "hot_y")

    def __init__(self, bitmap, w, h, hot_x, hot_y):
        self.bitmap, self.w, self.h, self.hot_x, self.hot_y = bitmap, w, h, hot_x, hot_y


class CursorOverlay:
    def __init__(self):
        self.mode = "off"
        self.hwnd = None
        self._last_poke = 0.0
        self._pending = False
        self._visible = False
        self._drawn = None
        self._raised_at = 0.0
        self._images = {}
        self._failed = False

    # -- called from the Socket.IO handler threads ---------------------------

    def start(self, mode=None):
        """Create the overlay window on its own thread (no-op for mode 'off')."""
        mode = mode_from_argv(sys.argv) if mode is None else mode
        if sys.platform != "win32" or mode not in ("auto", "always") or self.hwnd:
            return
        self.mode = mode
        ready = threading.Event()
        threading.Thread(target=self._run, args=(ready,), name="cursor-overlay",
                         daemon=True).start()
        ready.wait(2)

    def poke(self):
        """Show the cursor (again) after a phone mouse action. Never blocks."""
        self._last_poke = time.monotonic()
        if self.hwnd and not self._pending:
            self._pending = True  # coalesce: one wake-up message at a time
            if not user32.PostMessageW(self.hwnd, WM_APP_POKE, 0, 0):
                self._pending = False

    # -- everything below runs on the overlay thread -------------------------

    def _run(self, ready):
        try:
            self._create_window()
        except Exception as e:
            print(f"  (Cursor overlay disabled: {e})")
            return
        finally:
            ready.set()
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _create_window(self):
        # Physical pixels on every monitor, so position and size match the
        # real pointer even with mixed DPI scaling. Only affects this thread.
        try:
            set_ctx = user32.SetThreadDpiAwarenessContext
            set_ctx.restype, set_ctx.argtypes = wt.LPVOID, [wt.LPVOID]
            set_ctx(wt.LPVOID(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
        except AttributeError:
            pass  # older than Windows 10 1607: process-wide DPI mode applies
        try:
            self._system_dpi = user32.GetDpiForSystem() or 96
        except AttributeError:
            self._system_dpi = 96
        try:
            dpi_for_monitor = ctypes.WinDLL("shcore").GetDpiForMonitor
            dpi_for_monitor.restype = ctypes.c_long
            dpi_for_monitor.argtypes = [wt.HMONITOR, ctypes.c_int,
                                        ctypes.POINTER(wt.UINT), ctypes.POINTER(wt.UINT)]
            self._dpi_for_monitor = dpi_for_monitor
        except (OSError, AttributeError):
            self._dpi_for_monitor = None

        self._dc = gdi32.CreateCompatibleDC(None)
        self._arrow = user32.LoadCursorW(None, IDC_ARROW)
        hinst = kernel32.GetModuleHandleW(None)
        self._wndproc_ref = WNDPROC(self._wndproc)  # keep alive
        class_name = f"KumuRemoteCursor{id(self):x}"
        wc = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=self._wndproc_ref,
                         hInstance=hinst, lpszClassName=class_name)
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            raise ctypes.WinError(ctypes.get_last_error())
        hwnd = user32.CreateWindowExW(OVERLAY_EX_STYLE, class_name, "KumuRemote cursor",
                                      WS_POPUP, 0, 0, 1, 1, None, None, hinst, None)
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self.hwnd = hwnd

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_APP_POKE or (msg == WM_TIMER and wparam == TIMER_ID):
            self._pending = False
            if not self._failed:
                try:
                    self._tick()
                except Exception as e:
                    self._failed = True  # never take the server down
                    print(f"  (Cursor overlay stopped: {e})")
                    self._hide()
            return 0
        if msg == WM_NCHITTEST:
            return HTTRANSPARENT
        if msg == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if msg == WM_DPICHANGED:
            return 0  # size is recomputed per frame from the monitor's DPI
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _tick(self):
        now = time.monotonic()
        idle = now - self._last_poke
        if idle >= HOLD_SECONDS + FADE_SECONDS:
            return self._hide()

        info = CURSORINFO(cbSize=ctypes.sizeof(CURSORINFO))
        if not user32.GetCursorInfo(ctypes.byref(info)):
            return self._hide()  # e.g. secure desktop (UAC, lock screen)
        system_draws_it = bool(info.flags & CURSOR_SHOWING) and bool(info.hCursor)
        if self.mode == "auto" and system_draws_it:
            return self._hide()

        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        scale = self._dpi_at(pt) / self._system_dpi
        img = (info.hCursor and self._image(info.hCursor, scale)) or self._image(self._arrow, scale)
        if img is None:
            return self._hide()

        alpha = 255
        if idle > HOLD_SECONDS:
            alpha = max(0, round(255 * (1 - (idle - HOLD_SECONDS) / FADE_SECONDS)))
        x, y = pt.x - img.hot_x, pt.y - img.hot_y
        state = (x, y, img, alpha)
        if state != self._drawn:
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, alpha, AC_SRC_ALPHA)
            old = gdi32.SelectObject(self._dc, img.bitmap)
            user32.UpdateLayeredWindow(self.hwnd, None, ctypes.byref(wt.POINT(x, y)),
                                       ctypes.byref(wt.SIZE(img.w, img.h)), self._dc,
                                       ctypes.byref(wt.POINT(0, 0)), 0,
                                       ctypes.byref(blend), ULW_ALPHA)
            gdi32.SelectObject(self._dc, old)
            self._drawn = state

        # Show without activating; re-assert topmost now and then so windows
        # that became topmost later (taskbar, players) don't cover us.
        if not self._visible or now - self._raised_at > 0.5:
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            if not self._visible:
                flags |= SWP_SHOWWINDOW
                user32.SetTimer(self.hwnd, TIMER_ID, FRAME_MS, None)
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            self._visible = True
            self._raised_at = now

    def _hide(self):
        if self._visible:
            user32.KillTimer(self.hwnd, TIMER_ID)
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self._visible = False
            self._drawn = None

    def _dpi_at(self, pt):
        if self._dpi_for_monitor is None:
            return self._system_dpi
        monitor = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        dpi_x, dpi_y = wt.UINT(), wt.UINT()
        if self._dpi_for_monitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) != 0:
            return self._system_dpi
        return dpi_x.value or self._system_dpi

    # -- turning a cursor handle into a premultiplied-alpha bitmap -----------

    def _image(self, hcursor, scale):
        key = (hcursor, round(scale * 100))
        img = self._images.get(key)
        if img is None:
            img = self._render(hcursor, scale)
            if img is None:
                return None
            if len(self._images) >= 32:  # drop the oldest
                old_key = next(iter(self._images))
                gdi32.DeleteObject(self._images.pop(old_key).bitmap)
            self._images[key] = img
        return img

    def _render(self, hcursor, scale):
        info = ICONINFO()
        if not user32.GetIconInfo(hcursor, ctypes.byref(info)):
            return None
        try:
            bm = BITMAP()
            gdi32.GetObjectW(info.hbmColor or info.hbmMask, ctypes.sizeof(BITMAP), ctypes.byref(bm))
            native_w = bm.bmWidth
            # monochrome cursors stack the AND and XOR masks in one bitmap
            native_h = bm.bmHeight if info.hbmColor else bm.bmHeight // 2
        finally:
            for bmp in (info.hbmMask, info.hbmColor):
                if bmp:
                    gdi32.DeleteObject(bmp)
        if native_w <= 0 or native_h <= 0:
            return None
        w, h = max(1, round(native_w * scale)), max(1, round(native_h * scale))

        # Drawing on black gives the premultiplied colour, drawing on white
        # additionally reveals the alpha. Works for alpha, colour and
        # monochrome (AND/XOR) cursors alike.
        on_black = self._draw(hcursor, w, h, 0x00)
        on_white = self._draw(hcursor, w, h, 0xFF)
        pixels = _combine(on_black, on_white, w, h)

        bits = wt.LPVOID()
        bitmap = gdi32.CreateDIBSection(None, ctypes.byref(_bitmap_header(w, h)),
                                        DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        if not bitmap:
            return None
        ctypes.memmove(bits, pixels, len(pixels))
        return _Image(bitmap, w, h, round(info.xHotspot * w / native_w),
                      round(info.yHotspot * h / native_h))

    def _draw(self, hcursor, w, h, background):
        bits = wt.LPVOID()
        bitmap = gdi32.CreateDIBSection(None, ctypes.byref(_bitmap_header(w, h)),
                                        DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        if not bitmap:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ctypes.memset(bits, background, w * h * 4)
            old = gdi32.SelectObject(self._dc, bitmap)
            user32.DrawIconEx(self._dc, 0, 0, hcursor, w, h, 0, None, DI_NORMAL)
            gdi32.GdiFlush()
            gdi32.SelectObject(self._dc, old)
            return ctypes.string_at(bits, w * h * 4)
        finally:
            gdi32.DeleteObject(bitmap)


def _bitmap_header(w, h):
    # 32-bit top-down DIB
    return BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w,
                            biHeight=-h, biPlanes=1, biBitCount=32)


def _combine(on_black, on_white, w, h):
    """Premultiplied BGRA from the cursor drawn on black and on white."""
    out = bytearray(w * h * 4)
    inverted = []
    for i in range(w * h):
        o = i * 4
        b0, g0, r0 = on_black[o], on_black[o + 1], on_black[o + 2]
        b1, g1, r1 = on_white[o], on_white[o + 1], on_white[o + 2]
        if b1 < b0 or g1 < g0 or r1 < r0:
            # XOR pixel (e.g. the text I-beam): it inverts the screen, which a
            # layered window can't do, so draw it opaque black ...
            out[o + 3] = 255
            inverted.append(i)
            continue
        alpha = 255 - ((b1 - b0) + (g1 - g0) + (r1 - r0)) // 3
        if alpha > 0:
            out[o], out[o + 1], out[o + 2] = min(b0, alpha), min(g0, alpha), min(r0, alpha)
            out[o + 3] = alpha
    # ... with a white outline so it stays visible on dark backgrounds too
    for i in inverted:
        x, y = i % w, i // w
        for nx in (x - 1, x, x + 1):
            for ny in (y - 1, y, y + 1):
                if 0 <= nx < w and 0 <= ny < h:
                    o = (ny * w + nx) * 4
                    if out[o + 3] == 0:
                        out[o:o + 4] = b"\xff\xff\xff\xff"
    return bytes(out)
