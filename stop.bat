@echo off
REM Arrete l'application (les donnees sont conservees).
cd /d "%~dp0"
docker compose stop
echo.
echo Application arretee. Pour redemarrer : start.bat
pause
