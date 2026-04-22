@echo off
cd /d "%~dp0"
echo Building KumuRemote.exe ...
pyinstaller --onefile --console --icon=logo.ico --name=KumuRemote --add-data "static;static" server.py
echo.
echo Done! Find KumuRemote.exe in the dist\ folder.
pause
