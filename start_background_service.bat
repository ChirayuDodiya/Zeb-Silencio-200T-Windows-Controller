@echo off
start "" pythonw "%~dp0background_service.py"
echo ZEB-Silencio 200T Background Auto-Tuner started silently.
echo It will automatically set your headphones to OnePlus Buds 3 upon Bluetooth connection.
timeout /t 3 >nul
