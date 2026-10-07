@echo off
REM Affiche l'etat des conteneurs et teste l'acces au site.
cd /d "%~dp0"
docker compose ps
echo.
curl -s -o NUL -w "Site web : HTTP %%{http_code} (200 = OK)\n" http://localhost/
pause
