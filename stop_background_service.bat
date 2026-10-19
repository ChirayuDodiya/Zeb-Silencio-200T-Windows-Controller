@echo off
taskkill /F /IM ZEB-Silencio-200T.exe 2>nul
wmic process where "commandline like '%%background_service.py%%'" delete 2>nul
echo ZEB-Silencio 200T background processes stopped.
timeout /t 2 >nul
