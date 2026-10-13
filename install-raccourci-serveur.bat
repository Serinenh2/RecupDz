@echo off
REM Cree le raccourci RecupIndurex sur le Bureau DE CE SERVEUR (pointe vers localhost)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-raccourci.ps1" -ServerUrl "http://localhost/"
