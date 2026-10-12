# ===============================================================================
# RecupIndurex - Restauration des donnees existantes (SARL Indurex)
#
# A lancer UNE SEULE FOIS, juste apres install.bat / install.ps1, pour charger
# les donnees deja saisies (compte admin_indurex, logo, badges ISO, cachet...)
# au lieu de repartir d'une base vide.
#
# Prerequis :
#   - install.bat / install.ps1 a deja tourne (images construites, .env present)
#   - Le dossier backup\ contient recup_indurex_data.sql.gz et media_backup.tar.gz
#     (fournis avec ce package de deploiement)
#
# Usage :
#   .\restore-data.bat                   (double-clic)
#   .\restore-data.ps1
#
# IMPORTANT : ce script REMPLACE les comptes et donnees actuellement dans la
# base par ceux du backup (admin et admin_indurex, avec leurs mots de passe
# d'origine). Les identifiants affiches a la fin de install.ps1 ne seront
# plus valables ensuite - utilisez ceux fournis avec ce package.
# ===============================================================================

Set-Location -Path $PSScriptRoot

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "    OK : $msg" -ForegroundColor Green }
function Write-Err  { param($msg) Write-Host "    ERREUR : $msg" -ForegroundColor Red }

function Wait-ServiceHealthy {
    param([string]$Service, [int]$TimeoutSec = 180)
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        $id = (docker compose ps -q $Service 2>$null)
        if ($id) {
            $status = docker inspect --format='{{.State.Health.Status}}' $id 2>$null
            if ($status -eq "healthy") { return $true }
        }
        Start-Sleep -Seconds 3
        $elapsed += 3
    }
    return $false
}

Write-Host "========================================" -ForegroundColor Yellow
Write-Host " RecupIndurex - Restauration des donnees" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# --- 0. Verifications prealables -------------------------------------------------
$dbBackup    = Join-Path $PSScriptRoot "backup\recup_indurex_data.sql.gz"
$mediaBackup = Join-Path $PSScriptRoot "backup\media_backup.tar.gz"
$envPath     = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $dbBackup) -or -not (Test-Path $mediaBackup)) {
    Write-Err "Fichiers de sauvegarde introuvables dans le dossier backup\"
    Write-Host "    Attendu : backup\recup_indurex_data.sql.gz et backup\media_backup.tar.gz"
    exit 1
}
if (-not (Test-Path $envPath)) {
    Write-Err "Fichier .env introuvable - lancez d'abord install.bat (install.ps1)"
    exit 1
}

$envLines = Get-Content $envPath
$dbName = ($envLines | Where-Object { $_ -match '^DB_NAME=' }) -replace 'DB_NAME=', ''
$dbUser = ($envLines | Where-Object { $_ -match '^DB_USER=' }) -replace 'DB_USER=', ''
if (-not $dbName) { $dbName = "recup_indurex" }
if (-not $dbUser) { $dbUser = "recup_user" }

Write-Ok "Fichiers de sauvegarde trouves"

# --- 1. Base de donnees prete -----------------------------------------------------
Write-Step "Verification de la base de donnees"
docker compose up -d db *> $null
if (-not (Wait-ServiceHealthy "db" 90)) {
    Write-Err "La base de donnees n'est pas devenue saine a temps"
    exit 1
}
Write-Ok "Base de donnees prete"

# --- 2. Restauration de la base ----------------------------------------------------
Write-Step "Restauration des donnees (comptes, fiche entreprise...)"
docker compose cp "$dbBackup" "db:/tmp/restore.sql.gz"
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la copie du fichier de sauvegarde vers le conteneur"; exit 1 }

docker compose exec db sh -c "gunzip -c /tmp/restore.sql.gz | psql -U $dbUser -d $dbName -v ON_ERROR_STOP=0 -q && rm -f /tmp/restore.sql.gz"
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la restauration de la base de donnees"; exit 1 }
Write-Ok "Base de donnees restauree"

# --- 3. Migrations (sans effet si deja a jour) + verifications -------------------
Write-Step "Verification des migrations et des permissions"
docker compose run --rm migrate
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la verification post-restauration"; exit 1 }
Write-Ok "Base de donnees a jour"

# --- 4. Backend + Frontend ----------------------------------------------------------
Write-Step "Demarrage du backend et du frontend"
docker compose up -d backend nginx *> $null
if (-not (Wait-ServiceHealthy "backend" 180)) {
    Write-Err "Le backend n'est pas devenu sain a temps"
    exit 1
}
if (-not (Wait-ServiceHealthy "nginx" 60)) {
    Write-Err "Nginx n'est pas devenu sain a temps"
    exit 1
}
Write-Ok "Backend et frontend demarres"

# --- 5. Restauration des fichiers (logo, cachet, badges ISO...) ------------------
Write-Step "Restauration des fichiers (logo, cachet, badges ISO...)"
docker compose cp "$mediaBackup" "backend:/tmp/media_backup.tar.gz"
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la copie des fichiers vers le conteneur"; exit 1 }

docker compose exec backend sh -c "tar xzf /tmp/media_backup.tar.gz -C /app/media && rm -f /tmp/media_backup.tar.gz"
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de l'extraction des fichiers"; exit 1 }
Write-Ok "Fichiers restaures"

# --- 6. Verification finale -------------------------------------------------------
Write-Step "Verification finale"
$ok = $false
try {
    $resp = Invoke-WebRequest -Uri "http://localhost/" -UseBasicParsing -TimeoutSec 10
    if ($resp.StatusCode -eq 200) { Write-Ok "Le site repond correctement (HTTP 200)"; $ok = $true }
    else { Write-Err "Reponse inattendue : HTTP $($resp.StatusCode)" }
} catch {
    Write-Err "Impossible de joindre http://localhost/ : $($_.Exception.Message)"
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " RESTAURATION TERMINEE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host " URL (depuis ce serveur)     : http://localhost/"
Write-Host " URL (depuis le reseau local): http://<IP-de-ce-serveur>/"
Write-Host ""
Write-Host " Utilisez les identifiants fournis avec ce package (PAS ceux affiches"
Write-Host " par install.ps1 - ils ne sont plus valables apres restauration) :"
Write-Host "   Administrateur : admin"
Write-Host "   Recuperateur   : admin_indurex"
Write-Host "========================================`n" -ForegroundColor Green

if (-not $ok) {
    Write-Host "Attention : la verification finale a echoue - relisez les erreurs ci-dessus" -ForegroundColor Yellow
    exit 1
}
