@echo off
REM Lance l'installation complete (voir install.ps1 / GUIDE_INSTALLATION_WINDOWS.md)
REM Droits administrateur requis (active WSL2 / installe Docker Desktop si besoin)
REM -> elevation automatique (une seule invite de securite Windows).
net session >nul 2>&1
if %errorLevel% == 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
    echo.
    pause
) else (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
)
