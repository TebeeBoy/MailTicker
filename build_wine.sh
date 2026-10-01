#!/usr/bin/env bash
# MailTicker.exe és telepítő (MailTicker-Setup-<verzió>.exe) készítése Linuxon, Wine alatt
# futó 32 bites Windows-os Pythonnal és Inno Setuppal. A 32 bites exe 64 bites Windowson is fut.
#
# Első futáskor felépíti a build-környezetet (~/.cache/mail_ticker_wine):
# letölti a Python MSI-csomagjait, msitools-szal kibontja (a Python telepítője
# régi Wine alatt nem fut), majd telepíti a PyInstallert.
# Kell hozzá: wine (32 bites), apt-get download, dpkg, curl.
set -euo pipefail

PY_VERSION=3.11.9
INNO_TAG=is-6_7_3
INNO_EXE=innosetup-6.7.3.exe
CACHE="${MAIL_TICKER_BUILD_CACHE:-$HOME/.cache/mail_ticker_wine}"
WINE="${WINE:-$(command -v wine || echo /usr/lib/wine/wine)}"
export WINEPREFIX="$CACHE/prefix" WINEARCH=win32 WINEDEBUG=-all
PYDIR="$WINEPREFIX/drive_c/Python311"
SRC="$(cd "$(dirname "$0")" && pwd)"

# A régi Wine alatt a Python nem indul, ha a kimenete fájlba van irányítva – csővezetéken át működik.
wpy() { "$WINE" 'C:\Python311\python.exe' "$@" 2>&1 | cat; }

if [ ! -f "$CACHE/.ready" ]; then
    echo ">> Build-környezet felépítése: $CACHE"
    rm -rf "$PYDIR"
    mkdir -p "$CACHE/dl" "$CACHE/msitools"
    "$WINE" wineboot -i
    "$WINE" reg add 'HKCU\Software\Wine' /v Version /d win10 /f

    (cd "$CACHE/msitools" && apt-get download msitools libmsi0 && for d in *.deb; do dpkg -x "$d" root; done)
    MSIEXTRACT="$CACHE/msitools/root/usr/bin/msiextract"
    export LD_LIBRARY_PATH="$CACHE/msitools/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

    mkdir -p "$PYDIR"
    for m in core exe lib tcltk; do
        curl -sSfL -o "$CACHE/dl/$m.msi" "https://www.python.org/ftp/python/$PY_VERSION/win32/$m.msi"
        (cd "$PYDIR" && "$MSIEXTRACT" "$CACHE/dl/$m.msi" >/dev/null)
    done
    wpy -m ensurepip
    wpy -m pip install --disable-pip-version-check --no-warn-script-location pyinstaller
    touch "$CACHE/.ready"
fi

ISCC_DIR="$WINEPREFIX/drive_c/InnoSetup6"
if [ ! -f "$ISCC_DIR/ISCC.exe" ]; then
    echo ">> Inno Setup telepítése"
    mkdir -p "$CACHE/dl"
    curl -sSfL -o "$CACHE/dl/$INNO_EXE" "https://github.com/jrsoftware/issrc/releases/download/$INNO_TAG/$INNO_EXE"
    "$WINE" "$CACHE/dl/$INNO_EXE" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER '/DIR=C:\InnoSetup6' /NOICONS 2>&1 | cat
fi

cd "$SRC"
VERSION="$(python3 -c 'from version import VERSION; print(VERSION)')"
wpy make_version_info.py 'build\version_info.txt'
wpy -m PyInstaller --noconfirm --onefile --noconsole --name MailTicker \
    --icon 'assets\mailticker.ico' --version-file 'build\version_info.txt' mail_ticker.py
test -f dist/MailTicker.exe
"$WINE" 'C:\InnoSetup6\ISCC.exe' /Q "/DAppVersion=$VERSION" 'installer\MailTicker.iss' 2>&1 | cat
test -f "dist/MailTicker-Setup-$VERSION.exe"
echo
echo ">> Kész: $SRC/dist/MailTicker.exe"
echo ">> Kész: $SRC/dist/MailTicker-Setup-$VERSION.exe"
