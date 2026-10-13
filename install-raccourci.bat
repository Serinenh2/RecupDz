@echo off
REM Cree le raccourci RecupIndurex sur le Bureau de ce PC (poste client, pas le serveur)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-raccourci.ps1" %*
