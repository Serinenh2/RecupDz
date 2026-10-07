# ═══════════════════════════════════════════════════════════════════════════
# RecupIndurex — Installation automatique (Windows Server / Windows 10+)
#
# Prérequis (voir GUIDE_INSTALLATION_WINDOWS.md) :
#   - Docker Desktop installé, démarré, backend WSL2 actif
#
# Usage :
#   .\install.bat                        (double-clic, domaine = localhost)
#   .\install.ps1 -Domain mon-serveur.local
# ═══════════════════════════════════════════════════════════════════════════
param(
    [string]$Domain = "localhost"
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "    OK : $msg" -ForegroundColor Green }
function Write-Err  { param($msg) Write-Host "    ERREUR : $msg" -ForegroundColor Red }

function New-RandomSecret {
    param([int]$Length = 32)
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return ([Convert]::ToBase64String($bytes) -replace '[^a-zA-Z0-9]', '').Substring(0, $Length)
}

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
Write-Host " RecupIndurex — Installation" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# ── 1. Docker disponible ? ───────────────────────────────────────────────────
Write-Step "Verification de Docker"
try {
    docker version *> $null
    if ($LASTEXITCODE -ne 0) { throw "docker non disponible" }
} catch {
    Write-Err "Docker n'est pas installe ou n'est pas demarre."
    Write-Host "    Installez Docker Desktop (backend WSL2) puis relancez ce script."
    Write-Host "    Voir GUIDE_INSTALLATION_WINDOWS.md, section Prerequis."
    exit 1
}
Write-Ok "Docker est disponible"

# ── 2. Fichier .env ───────────────────────────────────────────────────────────
$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Step "Generation du fichier .env (identifiants securises generes automatiquement)"

    $secretKey     = New-RandomSecret 50
    $dbPassword    = New-RandomSecret 20
    $adminPassword = New-RandomSecret 14

    $envContent = @"
# Genere automatiquement par install.ps1 — NE PAS COMMITER DANS GIT
DJANGO_SECRET_KEY=$secretKey
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,$Domain
DJANGO_LOG_LEVEL=WARNING

DB_ENGINE=django.db.backends.postgresql
DB_NAME=recup_indurex
DB_USER=recup_user
DB_PASSWORD=$dbPassword
DB_HOST=db
DB_PORT=5432
DB_CONN_MAX_AGE=60

DJANGO_CORS_ALLOWED_ORIGINS=http://localhost,http://127.0.0.1,http://$Domain

DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_HSTS_SECONDS=0
DJANGO_NUM_PROXIES=1

DOMAIN=$Domain
SSL_EMAIL=admin@example.com

BACKUP_RETENTION_DAYS=30

DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=$adminPassword
"@
    Set-Content -Path $envPath -Value $envContent -Encoding utf8
    Write-Ok ".env genere"
} else {
    Write-Ok ".env existe deja — conserve tel quel (identifiants inchanges)"
}

$envLines  = Get-Content $envPath
$adminUser = ($envLines | Where-Object { $_ -match '^DJANGO_SUPERUSER_USERNAME=' })  -replace 'DJANGO_SUPERUSER_USERNAME=', ''
$adminPass = ($envLines | Where-Object { $_ -match '^DJANGO_SUPERUSER_PASSWORD=' })  -replace 'DJANGO_SUPERUSER_PASSWORD=', ''

# ── 3. Construction des images ────────────────────────────────────────────────
Write-Step "Construction des images Docker (plusieurs minutes la premiere fois)"
docker compose build
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la construction des images"; exit 1 }
Write-Ok "Images construites"

# ── 4. Base de donnees ────────────────────────────────────────────────────────
Write-Step "Demarrage de la base de donnees"
docker compose up -d db
if (-not (Wait-ServiceHealthy "db" 90)) {
    Write-Err "La base de donnees n'est pas devenue saine a temps"
    docker compose logs db --tail 50
    exit 1
}
Write-Ok "Base de donnees prete"

# ── 5. Migrations + compte admin + RBAC ───────────────────────────────────────
Write-Step "Migrations de la base de donnees et configuration initiale"
docker compose run --rm migrate
if ($LASTEXITCODE -ne 0) { Write-Err "Echec des migrations"; exit 1 }
Write-Ok "Base de donnees migree, compte admin et permissions configures"

# ── 6. Backend + Frontend ─────────────────────────────────────────────────────
Write-Step "Demarrage du backend et du frontend"
docker compose up -d backend nginx
if (-not (Wait-ServiceHealthy "backend" 180)) {
    Write-Err "Le backend n'est pas devenu sain a temps"
    docker compose logs backend --tail 50
    exit 1
}
if (-not (Wait-ServiceHealthy "nginx" 60)) {
    Write-Err "Nginx n'est pas devenu sain a temps"
    docker compose logs nginx --tail 50
    exit 1
}
Write-Ok "Backend et frontend demarres"

# ── 7. Verification finale ────────────────────────────────────────────────────
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
Write-Host " INSTALLATION TERMINEE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host " URL (depuis ce serveur)     : http://localhost/"
Write-Host " URL (depuis le reseau local): http://<IP-de-ce-serveur>/"
Write-Host ""
Write-Host " Compte administrateur :"
Write-Host "   Utilisateur : $adminUser"
Write-Host "   Mot de passe: $adminPass"
Write-Host ""
Write-Host " Ces identifiants sont aussi dans le fichier .env (ne pas supprimer)."
Write-Host " Changez ce mot de passe apres la premiere connexion (page Profil)."
Write-Host "========================================`n" -ForegroundColor Green

if (-not $ok) {
    Write-Host "Attention : la verification finale a echoue — relisez les erreurs ci-dessus" -ForegroundColor Yellow
    Write-Host "avant de considerer l'installation comme terminee. Voir GUIDE_INSTALLATION_WINDOWS.md > Depannage." -ForegroundColor Yellow
    exit 1
}
