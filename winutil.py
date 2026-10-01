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
    _mutex_handles.append(handle)
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


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
