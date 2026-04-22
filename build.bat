@echo off
cd /d "%~dp0"
echo Building KumuRemote.exe ...
python -m PyInstaller ^
  --onefile ^
  --console ^
  --icon=logo.ico ^
  --name=KumuRemote ^
  --add-data "static;static" ^
  --hidden-import=engineio.async_drivers.threading ^
  --hidden-import=engineio.async_drivers.aiohttp ^
  --collect-all=engineio ^
  --collect-all=socketio ^
  --collect-all=flask_socketio ^
  server.py
echo.
echo Done! Find KumuRemote.exe in the dist\ folder.
pause
