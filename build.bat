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
  --exclude-module=PyQt5 ^
  --exclude-module=PyQt6 ^
  --exclude-module=PySide2 ^
  --exclude-module=PySide6 ^
  --exclude-module=cv2 ^
  --exclude-module=numpy ^
  --exclude-module=matplotlib ^
  --exclude-module=IPython ^
  --exclude-module=pytest ^
  --exclude-module=_pytest ^
  --exclude-module=Cython ^
  --exclude-module=lxml ^
  --exclude-module=pygments ^
  --exclude-module=prompt_toolkit ^
  --exclude-module=setuptools ^
  server.py
echo.
echo Done! Find KumuRemote.exe in the dist\ folder.
pause
