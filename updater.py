"""Önfrissítés GitHub Releases-ből.

Két eset van:
- Telepített program (a telepítő tette fel, mellette van az unins000.exe): a kiadás
  telepítőjét (MailTicker-Setup-x.y.z.exe) tölti le, és csendben lefuttatja; a telepítő
  frissíti a „Programok és szolgáltatások” bejegyzést is, majd újraindítja a programot.
- Hordozható exe: a kiadáshoz csatolt MailTicker.exe-t tölti le az exe mellé (.new),
  és kicseréli a futót. A futó exe Windowson nem írható felül, de átnevezhető: a régi
  .old néven marad, és az új példány induláskor törli.
Letöltés után a méretet és az SHA-256 ellenőrzőösszeget is ellenőrzi.
"""
from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.request import Request, urlopen

import winutil
from version import UPDATE_REPO, VERSION

EXE_ASSET = "MailTicker.exe"
SETUP_PREFIX = "MailTicker-Setup-"
UNINSTALLER = "unins000.exe"  # az Inno Setup eltávolítója – ebből tudjuk, hogy telepítve vagyunk
# tesztelésnél egy helyi szerverre irányítható
API_URL = os.environ.get("MAILTICKER_UPDATE_URL") or f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{UPDATE_REPO}/releases/latest"

log = logging.getLogger("mail_ticker")


@dataclass
class Asset:
    name: str
    url: str
    size: int
    sha256: Optional[str]


@dataclass
class Release:
    version: str
    asset: Asset  # amit ez a példány letölt: telepítő vagy exe
    page_url: str
    notes: str


def parse_version(text: str) -> tuple[int, ...]:
    parts = []
    for piece in text.strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def is_installed() -> bool:
    return getattr(sys, "frozen", False) and os.path.exists(
        os.path.join(os.path.dirname(sys.executable), UNINSTALLER)
    )


def _request(url: str, accept: str) -> Request:
    return Request(url, headers={"Accept": accept, "User-Agent": f"MailTicker/{VERSION}"})


def _asset(data: dict) -> Asset:
    digest = data.get("digest") or ""
    return Asset(
        name=data["name"],
        url=data["browser_download_url"],
        size=int(data.get("size") or 0),
        sha256=digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else None,
    )


def check_latest() -> Optional[Release]:
    """Az újabb kiadás adatai, vagy None, ha a mostani a legfrissebb."""
    with urlopen(_request(API_URL, "application/vnd.github+json"), timeout=20) as resp:
        data = json.load(resp)
    tag = data.get("tag_name", "")
    if data.get("draft") or data.get("prerelease") or parse_version(tag) <= parse_version(VERSION):
        return None
    assets = data.get("assets", [])
    if is_installed():
        found = next((a for a in assets if a.get("name", "").startswith(SETUP_PREFIX)), None)
    else:
        found = next((a for a in assets if a.get("name") == EXE_ASSET), None)
    if found is None:
        log.warning("A %s kiadásban nincs %s", tag, "telepítő" if is_installed() else EXE_ASSET)
        return None
    return Release(
        version=tag.lstrip("vV"),
        asset=_asset(found),
        page_url=data.get("html_url") or RELEASES_PAGE,
        notes=(data.get("body") or "").strip(),
    )


def can_self_update() -> bool:
    """Csak a kész exe tudja frissíteni magát (forrásból futtatva nincs mit cserélni)."""
    return winutil.IS_WINDOWS and getattr(sys, "frozen", False)


def download(release: Release, progress: Callable[[int, int], None] | None = None) -> str:
    """Letölti és ellenőrzi a frissítést. Visszaadja a letöltött fájl útvonalát."""
    asset = release.asset
    if is_installed():
        target = os.path.join(tempfile.gettempdir(), asset.name)
    else:
        target = sys.executable + ".new"
    sha = hashlib.sha256()
    done = 0
    try:
        with urlopen(_request(asset.url, "application/octet-stream"), timeout=60) as resp, open(target, "wb") as out:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, asset.size)
        if asset.size and done != asset.size:
            raise IOError(f"Hiányos letöltés ({done} / {asset.size} bájt)")
        if asset.sha256 and sha.hexdigest() != asset.sha256:
            raise IOError("A letöltött fájl ellenőrzőösszege nem egyezik")
    except Exception:
        _remove_quietly(target)
        raise
    return target


def _spawn(args: list[str]) -> None:
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"  # az indított exe saját környezettel induljon, ne a miénkkel
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, env=env, close_fds=True, creationflags=flags)


def install_and_restart(downloaded: str) -> None:
    """Telepíti a letöltött frissítést és gondoskodik az újraindításról. A hívónak ezután ki kell lépnie."""
    winutil.release_single_instance()
    if is_installed():
        # a telepítő leállítja a még futó példányt, frissít, majd elindítja az újat
        _spawn([downloaded, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
        return
    exe = sys.executable
    old = exe + ".old"
    _remove_quietly(old)
    os.replace(exe, old)  # a futó exe átnevezhető, felülírni nem lehet
    try:
        os.replace(downloaded, exe)
    except Exception:
        os.replace(old, exe)
        raise
    _spawn([exe, "--after-update"])


def cleanup_after_update() -> None:
    """A frissítés maradékainak törlése (a régi folyamat még épp kiléphet)."""
    if not getattr(sys, "frozen", False):
        return
    import time

    for setup in glob.glob(os.path.join(tempfile.gettempdir(), SETUP_PREFIX + "*.exe")):
        _remove_quietly(setup)
    for _ in range(20):
        old = sys.executable + ".old"
        if not os.path.exists(old) or _remove_quietly(old):
            return
        time.sleep(1)


def _remove_quietly(path: str) -> bool:
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False
