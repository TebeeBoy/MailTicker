@echo off
rem Egyetlen MailTicker.exe készítése (dist\MailTicker.exe)
python -m pip install --upgrade pyinstaller || goto :error
python make_version_info.py build\version_info.txt || goto :error
python -m PyInstaller --noconfirm --onefile --noconsole --name MailTicker --version-file build\version_info.txt mail_ticker.py || goto :error
echo.
echo Kesz: dist\MailTicker.exe
goto :eof
:error
echo Hiba tortent a build soran.
exit /b 1
