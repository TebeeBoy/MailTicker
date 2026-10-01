"""Windows-specifikus segédfüggvények (más rendszeren ártalmatlan no-op-ok)."""
from __future__ import annotations

import os
import sys

IS_WINDOWS = sys.platform == "win32"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "MailTicker"

_mutex_handles = []

if IS_WINDOWS:
    import ctypes
    import winreg
    from ctypes import wintypes


def enable_dpi_awareness() -> None:
    """Éles betűk nagy DPI-s kijelzőn (a Tk ablak létrehozása előtt kell hívni)."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def acquire_single_instance(name: str = "Local\\MailTicker_SingleInstance") -> bool:
    """False, ha a program már fut."""
    if not IS_WINDOWS:
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)  # különben mi magunk tartanánk életben, és újrapróbálkozáskor sem indulnánk el
        return False
    _mutex_handles.append(handle)
    return True


def release_single_instance() -> None:
    """Frissítés után az új példány indulhasson el, mielőtt ez kilép."""
    if not IS_WINDOWS:
        return
    while _mutex_handles:
        ctypes.windll.kernel32.CloseHandle(_mutex_handles.pop())


def work_area(root) -> tuple[int, int, int, int]:
    """A képernyő tálca nélküli része: (bal, felső, jobb, alsó)."""
    if IS_WINDOWS:
        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
            return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def is_visible(x: int, y: int, width: int, height: int, root) -> bool:
    """Látszik-e a sáv eleje valamelyik monitoron (pl. lecsatolt második monitor esetén nem)."""
    probe = min(width, 80)
    if IS_WINDOWS:
        rect = wintypes.RECT(x, y, x + probe, y + height)
        user32 = ctypes.windll.user32
        user32.MonitorFromRect.restype = wintypes.HMONITOR
        return bool(user32.MonitorFromRect(ctypes.byref(rect), 0))  # MONITOR_DEFAULTTONULL
    return 0 <= x <= root.winfo_screenwidth() - probe and 0 <= y <= root.winfo_screenheight() - height


# ---------- már megnyitott Gmail-lap újrahasználata ----------
#
# Egy külső program nem tud egy böngészőlapot közvetlenül irányítani, ezért:
# megkeressük azt a böngészőablakot, amelynek címsorában (= az aktív lap címe)
# „Gmail” és a fiók címe szerepel, előtérbe hozzuk, és a címsorba beírjuk a
# levél linkjét (vágólapon át – a karakterenkénti gépelést a billentyűzetkiosztás és
# a böngésző automatikus kiegészítése is elronthatja). Mivel csak a # utáni rész
# változik, a Gmail újratöltés nélkül vált. A vágólap korábbi szövegét visszaállítjuk.

BROWSER_CLASSES = ("Chrome_WidgetWin_1", "MozillaWindowClass")  # Chrome/Edge/Brave/Opera, Firefox

if IS_WINDOWS:
    _ULONG_PTR = ctypes.c_size_t

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ULONG_PTR),
        ]

    class _MOUSEINPUT(ctypes.Structure):  # csak az unió helyes méretéhez kell
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", _ULONG_PTR),
        ]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    # saját példányok, hogy az argtypes beállítás ne hasson a program többi ctypes-hívására
    _clip_user32 = ctypes.WinDLL("user32", use_last_error=True)
    _clip_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _clip_user32.OpenClipboard.argtypes = [wintypes.HWND]
    _clip_user32.GetClipboardData.argtypes = [wintypes.UINT]
    _clip_user32.GetClipboardData.restype = ctypes.c_void_p
    _clip_user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    _clip_user32.SetClipboardData.restype = ctypes.c_void_p
    _clip_kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _clip_kernel32.GlobalAlloc.restype = ctypes.c_void_p
    _clip_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    _clip_kernel32.GlobalLock.restype = ctypes.c_void_p
    _clip_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    _clip_kernel32.GlobalFree.argtypes = [ctypes.c_void_p]

_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x2
_KEYEVENTF_UNICODE = 0x4
_VK_CONTROL, _VK_L, _VK_V, _VK_RETURN = 0x11, 0x4C, 0x56, 0x0D
_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x2


def _open_clipboard() -> bool:
    import time

    for _ in range(10):  # más program épp foghatja
        if _clip_user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def get_clipboard_text():
    if not IS_WINDOWS or not _open_clipboard():
        return None
    try:
        handle = _clip_user32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return None
        ptr = _clip_kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(ptr) if ptr else None
        finally:
            _clip_kernel32.GlobalUnlock(handle)
    finally:
        _clip_user32.CloseClipboard()


def set_clipboard_text(text: str) -> bool:
    if not IS_WINDOWS:
        return False
    data = (text + "\0").encode("utf-16-le")
    handle = _clip_kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(data))
    if not handle:
        return False
    ptr = _clip_kernel32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    _clip_kernel32.GlobalUnlock(handle)
    if not _open_clipboard():
        _clip_kernel32.GlobalFree(handle)
        return False
    try:
        _clip_user32.EmptyClipboard()
        if not _clip_user32.SetClipboardData(_CF_UNICODETEXT, handle):
            _clip_kernel32.GlobalFree(handle)
            return False
        return True  # a vágólap átvette a memóriát
    finally:
        _clip_user32.CloseClipboard()


def _window_text(hwnd) -> str:
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def find_gmail_window(address: str):
    """Az a látható böngészőablak, amelynek aktív lapja ennek a fióknak a Gmailje."""
    if not IS_WINDOWS or not address:
        return None
    user32 = ctypes.windll.user32
    address = address.lower()
    found = []

    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd) and _class_name(hwnd) in BROWSER_CLASSES:
            title = _window_text(hwnd)
            if "Gmail" in title and address in title.lower():
                found.append(hwnd)
        return True

    user32.EnumWindows(_WNDENUMPROC(callback), 0)
    return found[0] if found else None  # az EnumWindows a legfelső ablakkal kezd


def _key(vk: int, up: bool = False):
    ki = _KEYBDINPUT(wVk=vk, wScan=0, dwFlags=_KEYEVENTF_KEYUP if up else 0, time=0, dwExtraInfo=0)
    return _INPUT(type=_INPUT_KEYBOARD, u=_INPUTUNION(ki=ki))


def _ctrl(vk: int) -> list:
    return [_key(_VK_CONTROL), _key(vk), _key(vk, up=True), _key(_VK_CONTROL, up=True)]


def _send(inputs) -> None:
    array = (_INPUT * len(inputs))(*inputs)
    ctypes.windll.user32.SendInput(len(inputs), array, ctypes.sizeof(_INPUT))


def navigate_existing_gmail(url: str, address: str, expect_title_change: bool = True) -> bool:
    """True, ha a meglévő Gmail-lapon biztosan megnyílt a link; különben a hívó nyisson új lapot.

    Blokkol (néhány tized mp-től pár mp-ig), ezért háttérszálból kell hívni.
    """
    import threading
    import time

    hwnd = find_gmail_window(address)
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    title_before = _window_text(hwnd)
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    for _ in range(40):
        if user32.GetForegroundWindow() == hwnd:
            break
        time.sleep(0.05)
    else:
        return False  # nem kaptuk meg a fókuszt – nehogy máshová illesszünk be
    # Aktiváláskor a böngésző visszaadja a fókuszt az oldal utoljára használt mezőjének
    # (pl. a Gmail keresőjének); ha ez a Ctrl+L után történik, oda menne a link.
    time.sleep(0.3)

    previous = get_clipboard_text()
    if not set_clipboard_text(url):
        return False

    def still_ours() -> bool:
        return user32.GetForegroundWindow() == hwnd

    try:
        _send(_ctrl(_VK_L))  # címsor kijelölése
        time.sleep(0.2)
        if not still_ours():
            return False
        _send(_ctrl(_VK_V))
        time.sleep(0.15)
        if not still_ours():
            return False
        _send([_key(_VK_RETURN), _key(_VK_RETURN, up=True)])

        if not expect_title_change:
            return True
        # siker: a Gmail a megnyitott levél tárgyára írja át az ablak (aktív lap) címét
        for _ in range(40):
            time.sleep(0.1)
            if _window_text(hwnd) != title_before:
                return True
        return False
    finally:
        def restore() -> None:
            # csak akkor, ha közben a felhasználó nem másolt mást a vágólapra
            if previous is not None and get_clipboard_text() == url:
                set_clipboard_text(previous)

        threading.Timer(1.0, restore).start()


def _autostart_command() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller exe
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mail_ticker.py")
    return f'"{exe}" "{script}"'


def autostart_enabled() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
            return True
    except OSError:
        return False


def set_autostart(enabled: bool) -> None:
    if not IS_WINDOWS:
        return
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass
