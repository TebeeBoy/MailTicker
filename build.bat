@echo off
rem MailTicker.exe és telepítő készítése (dist\MailTicker.exe, dist\MailTicker-Setup-<verzió>.exe)
rem A telepítőhöz Inno Setup 6 kell: https://jrsoftware.org/isdl.php
python -m pip install --upgrade pyinstaller || goto :error
python make_version_info.py build\version_info.txt || goto :error
python -m PyInstaller --noconfirm --onefile --noconsole --name MailTicker --icon assets\mailticker.ico --version-file build\version_info.txt mail_ticker.py || goto :error
for /f %%v in (python -c "from version import VERSION; print(VERSION)") do set VERSION=%%v
set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (echo Inno Setup nem talalhato, telepito nem keszult.& goto :done)
"%ISCC%" /Q /DAppVersion=%VERSION% installer\MailTicker.iss || goto :error
:done
echo.
echo Kesz: dist\
goto :eof
:error
echo Hiba tortent a build soran.
exit /b 1
