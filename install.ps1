# ===============================================================================
# RecupIndurex - Installation automatique (Windows Server / Windows 10+)
#
# Entierement automatique : installe WSL2 et Docker Desktop si necessaire
# (aucun prerequis manuel), puis installe l'application. Un redemarrage
# Windows peut etre necessaire une seule fois si WSL2 n'etait pas deja
# active - le script reprend alors tout seul apres la reconnexion.
#
# Usage :
#   .\install.bat                        (double-clic, domaine = localhost)
#   .\install.ps1 -Domain mon-serveur.local
# ===============================================================================
param(
    [string]$Domain = "localhost"
)

# Pas de $ErrorActionPreference = "Stop" ici : sous Windows PowerShell 5.1,
# rediriger le stderr d'un programme natif (ex: docker ... 2>$null) alors que
# ErrorActionPreference = Stop est actif transforme tout texte stderr - meme
# un simple avertissement - en erreur fatale qui arrete le script. On verifie
# explicitement $LASTEXITCODE apres chaque commande docker importante a la place.
Set-Location -Path $PSScriptRoot

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "    OK : $msg" -ForegroundColor Green }
function Write-Err  { param($msg) Write-Host "    ERREUR : $msg" -ForegroundColor Red }
function Write-Warn { param($msg) Write-Host "    ATTENTION : $msg" -ForegroundColor Yellow }

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

function Test-IsAdmin {
    $identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

function Register-ResumeAfterReboot {
    # Relance automatiquement ce script a la prochaine connexion Windows
    # (une seule fois) - necessaire quand on doit redemarrer pour activer WSL2.
    $runOnceKey = "HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce"
    $command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Domain `"$Domain`""
    Set-ItemProperty -Path $runOnceKey -Name "RecupIndurexInstall" -Value $command -ErrorAction SilentlyContinue
}

Write-Host "========================================" -ForegroundColor Yellow
Write-Host " RecupIndurex - Installation" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

# --- 0. Elevation a la demande ------------------------------------------------------
# On ne demande les droits administrateur QUE si une action qui en a reellement
# besoin doit etre effectuee (activer WSL2, installer Docker Desktop) - pas a
# chaque lancement. Si tout est deja installe, aucune invite Windows n'apparait.
function Request-Elevation {
    if (Test-IsAdmin) { return }
    Write-Step "Droits administrateur requis pour cette etape - relancement avec elevation"
    Write-Host "    (Windows va demander une confirmation - cliquez sur Oui)"
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Domain `"$Domain`""
    try {
        Start-Process powershell.exe -Verb RunAs -ArgumentList $argList
    } catch {
        Write-Err "Elevation refusee ou impossible. Relancez install.bat et acceptez l'invite Windows."
        exit 1
    }
    exit
}

# --- 1. WSL2 -----------------------------------------------------------------------
# "wsl --status" ne necessite pas de droits administrateur et renvoie un code de
# sortie 0 si WSL2 est deja pret - on ne verifie via DISM (qui exige l'elevation)
# que si cette premiere verification echoue.
Write-Step "Verification de WSL2"
wsl --status *> $null
$wslNeedsEnable = $LASTEXITCODE -ne 0

if ($wslNeedsEnable) {
    Request-Elevation
    $wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -ErrorAction SilentlyContinue
    $vmFeature  = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -ErrorAction SilentlyContinue
    $wslNeedsEnable = ($null -eq $wslFeature) -or ($wslFeature.State -ne "Enabled") -or
                      ($null -eq $vmFeature)  -or ($vmFeature.State  -ne "Enabled")
}

if ($wslNeedsEnable) {
    Write-Host "    WSL2 n'est pas encore active sur ce PC - activation..."
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null

    Register-ResumeAfterReboot

    Write-Host "`n========================================" -ForegroundColor Yellow
    Write-Host " REDEMARRAGE NECESSAIRE (une seule fois)" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host " WSL2 vient d'etre active - Windows exige un redemarrage"
    Write-Host " pour terminer cette etape. L'installation reprendra"
    Write-Host " automatiquement apres votre prochaine connexion."
    Write-Host " (Si une invite de securite Windows apparait a ce moment-la,"
    Write-Host "  acceptez-la pour laisser l'installation continuer.)"
    Write-Host ""
    Write-Host " Fermez vos autres programmes, puis appuyez sur une touche"
    Write-Host " pour redemarrer maintenant..."
    [System.Console]::ReadKey($true) | Out-Null
    Restart-Computer -Force
    exit
}
Write-Ok "WSL2 est actif"

try { wsl --set-default-version 2 *> $null } catch {}

# --- 2. Docker Desktop ---------------------------------------------------------------
Write-Step "Verification de Docker Desktop"
$dockerCmd = Get-Command docker.exe -ErrorAction SilentlyContinue
$dockerExePath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$dockerInstalled = ($null -ne $dockerCmd) -or (Test-Path $dockerExePath)

if (-not $dockerInstalled) {
    Request-Elevation
    Write-Host "    Docker Desktop n'est pas installe - telechargement..."
    $installerPath = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
    try {
        Invoke-WebRequest -Uri "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" `
            -OutFile $installerPath -UseBasicParsing
    } catch {
        Write-Err "Echec du telechargement de Docker Desktop : $($_.Exception.Message)"
        Write-Host "    Verifiez la connexion internet de ce PC, ou installez Docker Desktop"
        Write-Host "    manuellement depuis https://www.docker.com/products/docker-desktop puis relancez."
        exit 1
    }
    Write-Ok "Docker Desktop telecharge"

    Write-Step "Installation de Docker Desktop (silencieuse, quelques minutes)"
    $proc = Start-Process -FilePath $installerPath `
        -ArgumentList "install", "--quiet", "--accept-license", "--backend=wsl-2" `
        -Wait -PassThru
    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue

    if ($proc.ExitCode -eq 3010) {
        # Code standard Windows "redemarrage requis"
        Register-ResumeAfterReboot
        Write-Host "`n========================================" -ForegroundColor Yellow
        Write-Host " REDEMARRAGE NECESSAIRE (une seule fois)" -ForegroundColor Yellow
        Write-Host "========================================" -ForegroundColor Yellow
        Write-Host " Docker Desktop a ete installe - Windows exige un redemarrage"
        Write-Host " pour terminer cette etape. L'installation reprendra"
        Write-Host " automatiquement apres votre prochaine connexion."
        Write-Host ""
        Write-Host " Fermez vos autres programmes, puis appuyez sur une touche"
        Write-Host " pour redemarrer maintenant..."
        [System.Console]::ReadKey($true) | Out-Null
        Restart-Computer -Force
        exit
    }
    if ($proc.ExitCode -ne 0) {
        Write-Err "L'installation de Docker Desktop a echoue (code $($proc.ExitCode))"
        Write-Host "    Installez-le manuellement depuis https://www.docker.com/products/docker-desktop puis relancez."
        exit 1
    }
    Write-Ok "Docker Desktop installe"
} else {
    Write-Ok "Docker Desktop est deja installe"
}

# --- 3. Docker pret (demarre Docker Desktop si besoin, attend le moteur) -----------
Write-Step "Demarrage de Docker"
docker version *> $null
if ($LASTEXITCODE -ne 0) {
    if (Test-Path $dockerExePath) {
        Start-Process $dockerExePath
    }
    Write-Host "    Attente du demarrage de Docker Desktop (peut prendre 1 a 2 minutes la premiere fois)..."
    $elapsed = 0
    while ($elapsed -lt 180) {
        docker version *> $null
        if ($LASTEXITCODE -eq 0) { break }
        Start-Sleep -Seconds 5
        $elapsed += 5
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Docker n'a pas demarre a temps."
        Write-Host "    Ouvrez Docker Desktop manuellement (icone sur le Bureau), attendez"
        Write-Host "    l'icone verte 'Running', puis relancez install.bat."
        exit 1
    }
}
Write-Ok "Docker est disponible"

# --- 3b. Pare-feu (acces depuis le reseau local) ------------------------------------
Write-Step "Verification du pare-feu"
$fwRule = Get-NetFirewallRule -DisplayName "RecupIndurex HTTP" -ErrorAction SilentlyContinue
if (-not $fwRule) {
    try {
        if (Test-IsAdmin) {
            New-NetFirewallRule -DisplayName "RecupIndurex HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow -ErrorAction Stop | Out-Null
            Write-Ok "Regle de pare-feu ajoutee (port 80)"
        } else {
            Write-Warn "Regle de pare-feu non ajoutee (droits insuffisants) - l'application"
            Write-Host "    ne sera accessible que depuis ce PC (http://localhost/). Pour l'ouvrir"
            Write-Host "    au reseau local, executez en administrateur :"
            Write-Host '    New-NetFirewallRule -DisplayName "RecupIndurex HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow'
        }
    } catch {
        Write-Warn "Impossible d'ajouter la regle de pare-feu automatiquement - voir GUIDE_INSTALLATION_WINDOWS.md > Depannage"
    }
} else {
    Write-Ok "Regle de pare-feu deja presente"
}

# --- 4. Fichier .env ------------------------------------------------------------
$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Step "Generation du fichier .env (identifiants securises generes automatiquement)"

    $secretKey     = New-RandomSecret 50
    $dbPassword    = New-RandomSecret 20
    $adminPassword = New-RandomSecret 14

    $envContent = @"
# Genere automatiquement par install.ps1 - NE PAS COMMITER DANS GIT
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
    Write-Ok ".env existe deja - conserve tel quel (identifiants inchanges)"
}

$envLines  = Get-Content $envPath
$adminUser = ($envLines | Where-Object { $_ -match '^DJANGO_SUPERUSER_USERNAME=' })  -replace 'DJANGO_SUPERUSER_USERNAME=', ''
$adminPass = ($envLines | Where-Object { $_ -match '^DJANGO_SUPERUSER_PASSWORD=' })  -replace 'DJANGO_SUPERUSER_PASSWORD=', ''

# --- 5. Construction des images -------------------------------------------------
Write-Step "Construction des images Docker (plusieurs minutes la premiere fois)"
docker compose build
if ($LASTEXITCODE -ne 0) { Write-Err "Echec de la construction des images"; exit 1 }
Write-Ok "Images construites"

# --- 6. Base de donnees ----------------------------------------------------------
Write-Step "Demarrage de la base de donnees"
docker compose up -d db
if (-not (Wait-ServiceHealthy "db" 90)) {
    Write-Err "La base de donnees n'est pas devenue saine a temps"
    docker compose logs db --tail 50
    exit 1
}
Write-Ok "Base de donnees prete"

# --- 7. Migrations + compte admin + RBAC -----------------------------------------
Write-Step "Migrations de la base de donnees et configuration initiale"
docker compose run --rm migrate
if ($LASTEXITCODE -ne 0) { Write-Err "Echec des migrations"; exit 1 }
Write-Ok "Base de donnees migree, compte admin et permissions configures"

# --- 8. Backend + Frontend --------------------------------------------------------
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

# --- 9. Verification finale -------------------------------------------------------
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
    Write-Host "Attention : la verification finale a echoue - relisez les erreurs ci-dessus" -ForegroundColor Yellow
    Write-Host "avant de considerer l'installation comme terminee. Voir GUIDE_INSTALLATION_WINDOWS.md > Depannage." -ForegroundColor Yellow
    exit 1
}
