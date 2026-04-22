@echo off
cd /d "%~dp0"

echo Opening firewall for port 5000...
netsh advfirewall firewall add rule name="PC Remote Control" dir=in action=allow protocol=TCP localport=5000 >nul 2>&1

python server.py
pause