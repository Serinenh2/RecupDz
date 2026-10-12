@echo off
REM Restaure les donnees existantes de SARL Indurex (voir restore-data.ps1 / GUIDE_INSTALLATION_WINDOWS.md)
REM A lancer UNE SEULE FOIS, juste apres install.bat.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore-data.ps1" %*
echo.
pause
