@echo off
REM Redemarre l'application (sans reconstruire les images) — a utiliser apres
REM un redemarrage du serveur ou un arret manuel.
cd /d "%~dp0"
docker compose up -d db
docker compose up -d backend nginx
echo.
echo Application demarree : http://localhost/
pause
