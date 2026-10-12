@echo off
REM Sauvegarde l'etat actuel des donnees dans backup\ (voir backup-data.ps1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-data.ps1" %*
echo.
pause
