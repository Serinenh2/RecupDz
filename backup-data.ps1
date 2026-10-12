# ===============================================================================
# RecupIndurex - Sauvegarde des donnees actuelles (pour deploiement client)
#
# Capture l'etat actuel de la base de donnees et des fichiers (logo, ISO,
# cachet...) dans le dossier backup\, pour les livrer avec le package de
# deploiement (voir restore-data.ps1 / GUIDE_INSTALLATION_WINDOWS.md).
#
# A relancer avant chaque deploiement si les donnees ont change depuis la
# derniere sauvegarde (ex: logo ou fiche entreprise mis a jour).
#
# Usage :
#   .\backup-data.bat                    (double-clic)
#   .\backup-data.ps1
# ===============================================================================

Set-Location -Path $PSScriptRoot

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "    OK : $msg" -ForegroundColor Green }
function Write-Err  { param($msg) Write-Host "    ERREUR : $msg" -ForegroundColor Red }

Write-Host "========================================" -ForegroundColor Yellow
Write-Host " RecupIndurex - Sauvegarde des donnees" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Err "Fichier .env introuvable - l'application doit etre installee et demarree"
    exit 1
}
$envLines = Get-Content $envPath
$dbName = ($envLines | Where-Object { $_ -match '^DB_NAME=' }) -replace 'DB_NAME=', ''
$dbUser = ($envLines | Where-Object { $_ -match '^DB_USER=' }) -replace 'DB_USER=', ''
if (-not $dbName) { $dbName = "recup_indurex" }
if (-not $dbUser) { $dbUser = "recup_user" }

$backupDir = Join-Path $PSScriptRoot "backup"
if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir | Out-Null }

# --- 1. Base de donnees -----------------------------------------------------------
Write-Step "Sauvegarde de la base de donnees"
$dbId = (docker compose ps -q db 2>$null)
if (-not $dbId) {
    Write-Err "Le conteneur de base de donnees n'est pas demarre (lancez start.bat d'abord)"
    exit 1
}
# Le dump est cree et compresse DANS le conteneur, puis recupere via
# "docker compose cp" - ne jamais faire transiter un flux binaire (gzip)
# par une redirection PowerShell (">"), qui le reinterprete comme du texte
# et le corrompt.
docker compose exec db sh -c "pg_dump -U $dbUser -d $dbName --no-owner --no-acl --clean --if-exists | gzip > /tmp/backup.sql.gz"
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la sauvegarde de la base de donnees"; exit 1 }
docker compose cp "db:/tmp/backup.sql.gz" (Join-Path $backupDir "recup_indurex_data.sql.gz")
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la copie de la sauvegarde"; exit 1 }
docker compose exec db sh -c "rm -f /tmp/backup.sql.gz"
Write-Ok "Base de donnees sauvegardee -> backup\recup_indurex_data.sql.gz"

# --- 2. Fichiers (logo, cachet, badges ISO...) -------------------------------------
Write-Step "Sauvegarde des fichiers (logo, cachet, badges ISO...)"
$backendId = (docker compose ps -q backend 2>$null)
if (-not $backendId) {
    Write-Err "Le conteneur backend n'est pas demarre (lancez start.bat d'abord)"
    exit 1
}
docker compose exec backend sh -c "cd /app/media && tar czf /tmp/media_backup.tar.gz ."
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la creation de l'archive des fichiers"; exit 1 }
docker compose cp "backend:/tmp/media_backup.tar.gz" (Join-Path $backupDir "media_backup.tar.gz")
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la copie de l'archive des fichiers"; exit 1 }
docker compose exec backend sh -c "rm -f /tmp/media_backup.tar.gz"
Write-Ok "Fichiers sauvegardes -> backup\media_backup.tar.gz"

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " SAUVEGARDE TERMINEE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host " Le dossier backup\ est pret a etre inclus dans le package de"
Write-Host " deploiement, avec restore-data.ps1 / restore-data.bat."
Write-Host "========================================`n" -ForegroundColor Green
