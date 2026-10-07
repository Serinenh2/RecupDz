@echo off
REM Lance l'installation complete (voir install.ps1 / GUIDE_INSTALLATION_WINDOWS.md)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
