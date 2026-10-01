"""Beállítások betöltése és mentése (%APPDATA%\\MailTicker\\config.ini).

A Gmail-alkalmazásjelszót Windows alatt DPAPI-val titkosítva tároljuk,
így csak ugyanaz a Windows-felhasználó tudja visszafejteni.
"""
from __future__ import annotations

import base64
import configparser
import os
import sys

APP_DIR = os.path.join(
    os.environ.get("APPDATA") or os.path.expanduser("~/.config"), "MailTicker"
)
CONFIG_PATH = os.path.join(APP_DIR, "config.ini")
SECTION = "ticker"

DEFAULTS = {
    "email": "",
    "password": "",
    "poll_seconds": "60",
    "x": "",  # üres = alaphelyzet (bal felső sarok)
    "y": "",
    "width": "0",  # 0 = teljes képernyőszélesség
    "speed": "1.5",  # képpont / képkocka (kb. 50 képkocka/mp)
    "font_family": "Segoe UI",
    "font_size": "10",
    "bg": "#1d2b3a",
    "hover_bg": "#2f4660",
    "badge_bg": "#2b6cb0",
    "error_bg": "#c53030",
    "sender_fg": "#ffd36b",
    "subject_fg": "#ffffff",
    "date_fg": "#9fb3c8",
    "update_fg": "#68d391",
    "alpha": "0.95",
    "hide_when_empty": "no",
    "mark_as_read": "yes",
    "update_check": "yes",  # új verzió keresése indításkor és naponta
}


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _dpapi(data: bytes, protect: bool) -> bytes:
        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob_out = _DataBlob()
        crypt32 = ctypes.windll.crypt32
        func = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        if not func(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _encode_secret(secret: str) -> str:
    if not secret:
        return ""
    data = secret.encode("utf-8")
    if sys.platform == "win32":
        return "dpapi:" + base64.b64encode(_dpapi(data, protect=True)).decode("ascii")
    return "plain:" + base64.b64encode(data).decode("ascii")


def _decode_secret(stored: str) -> str:
    if not stored:
        return ""
    kind, _, payload = stored.partition(":")
    try:
        data = base64.b64decode(payload)
        if kind == "dpapi" and sys.platform == "win32":
            return _dpapi(data, protect=False).decode("utf-8")
        if kind == "plain":
            return data.decode("utf-8")
    except Exception:
        pass
    return ""


class Settings:
    def __init__(self, values: dict[str, str]):
        self._values = values

    def __getitem__(self, key: str) -> str:
        return self._values.get(key, DEFAULTS.get(key, ""))

    def set(self, key: str, value) -> None:
        self._values[key] = str(value)

    def get_int(self, key: str) -> int:
        try:
            return int(self[key])
        except ValueError:
            return int(DEFAULTS[key])

    def get_optional_int(self, key: str) -> int | None:
        try:
            return int(self[key])
        except ValueError:
            return None

    def get_float(self, key: str) -> float:
        try:
            return float(self[key])
        except ValueError:
            return float(DEFAULTS[key])

    def get_bool(self, key: str) -> bool:
        return self[key].strip().lower() in ("1", "yes", "true", "on", "igen")

    @property
    def password(self) -> str:
        return _decode_secret(self["password"])

    @password.setter
    def password(self, value: str) -> None:
        self._values["password"] = _encode_secret(value)

    def as_dict(self) -> dict[str, str]:
        return dict(self._values)


def load() -> Settings:
    parser = configparser.ConfigParser(interpolation=None)
    values = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        parser.read(CONFIG_PATH, encoding="utf-8")
        if parser.has_section(SECTION):
            values.update(parser[SECTION])
    return Settings(values)


def save(settings: Settings) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    parser = configparser.ConfigParser(interpolation=None)
    parser[SECTION] = settings.as_dict()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        parser.write(f)
