# Guide d'installation — Windows Server

Installation de RecupIndurex sur un serveur Windows (Windows Server 2022/2019
ou Windows 10/11). L'application tourne dans des conteneurs Docker **Linux**
(PostgreSQL, Django, nginx) — Windows exécute ces conteneurs via Docker
Desktop + son moteur WSL2, pas nativement.

---

## 1. Prérequis (une seule fois)

### 1.1 Activer WSL2

Ouvrir **PowerShell en administrateur** et exécuter :

```powershell
wsl --install
```

Redémarrer le serveur si demandé. Si `wsl --install` n'est pas disponible
(Windows Server plus ancien), activer manuellement :

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
Restart-Computer
```

Puis installer le noyau WSL2 (lien officiel Microsoft "WSL2 Linux kernel
update package") et définir la version par défaut :

```powershell
wsl --set-default-version 2
```

### 1.2 Installer Docker Desktop

1. Télécharger Docker Desktop depuis [docker.com](https://www.docker.com/products/docker-desktop)
2. Installer avec l'option **"Use WSL 2 instead of Hyper-V"** cochée
3. Lancer Docker Desktop, attendre l'icône verte "Running" dans la barre système
4. Vérifier dans un terminal :
   ```powershell
   docker version
   ```
   Doit afficher une version Client **et** Server sans erreur.

### 1.3 Ouvrir le port dans le pare-feu Windows (accès depuis le réseau local)

```powershell
New-NetFirewallRule -DisplayName "RecupIndurex HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
```

---

## 2. Transférer le projet sur le serveur

Copier l'intégralité du dossier du projet sur le serveur (clé USB, partage
réseau, ou `git clone` si le dépôt est accessible depuis le serveur). Ne pas
oublier : le dossier doit contenir `docker-compose.yml`, `backend/`,
`frontend/`, `install.ps1`, `install.bat`.

Destination conseillée : `C:\RecupIndurex\`

**Ne pas copier** un éventuel fichier `.env` d'un autre environnement — le
script d'installation en génère un nouveau avec des identifiants uniques et
sécurisés pour ce serveur.

---

## 3. Installer

Dans l'explorateur de fichiers, double-cliquer sur **`install.bat`**.

(Équivalent en ligne de commande : `powershell -ExecutionPolicy Bypass -File install.ps1`)

Le script :
1. Vérifie que Docker fonctionne
2. Génère `.env` avec une clé secrète, un mot de passe de base de données et
   un mot de passe administrateur générés aléatoirement (si `.env` n'existe
   pas déjà)
3. Construit les images (quelques minutes la première fois)
4. Démarre la base de données et attend qu'elle soit prête
5. Applique les migrations, crée le compte administrateur, configure les
   permissions (RBAC)
6. Démarre le backend et le site
7. Vérifie que le site répond bien

**À la fin, le script affiche l'URL et les identifiants administrateur —
notez-les, le mot de passe n'est affiché qu'une seule fois** (il reste
cependant consultable dans le fichier `.env`, à conserver précieusement et
à ne jamais partager).

Le script est **sans risque à relancer** (idempotent) : si une étape échoue
(coupure réseau pendant le build, etc.), corrigez le problème et relancez
`install.bat` — il reprendra sans dupliquer de données.

---

## 4. Vérifier l'installation

- Depuis le serveur : http://localhost/
- Depuis un autre poste du réseau : `http://<IP-du-serveur>/`
  (trouver l'IP avec `ipconfig` sur le serveur)

Se connecter avec le compte administrateur affiché à la fin de
l'installation.

`status.bat` (à la racine du projet) affiche l'état des conteneurs et teste
l'accès au site en une commande.

---

## 5. Première configuration (après installation)

L'application démarre avec une base de données vide — aucune donnée métier
pré-remplie. Pour configurer le compte de l'entreprise elle-même :

1. Se connecter avec le compte administrateur (`admin`)
2. Aller dans **Utilisateurs → Nouvel utilisateur**
3. Créer un compte avec le rôle **Récupérateur** pour l'entreprise cliente
   (ex. nom d'utilisateur `recuperateur1`) — une fiche entreprise vide est
   créée automatiquement et liée à ce compte
4. Se déconnecter, se reconnecter avec ce nouveau compte
5. Aller dans **Profil** pour renseigner les informations de l'entreprise
   (raison sociale, RC/NIF/NIS, adresse, coordonnées bancaires) et importer
   le logo, le cachet électronique et les badges ISO 9001/14001/45001 — ces
   éléments apparaîtront automatiquement sur tous les documents PDF/Word
   générés (Proforma, BC, Facture, BL)

Depuis le compte `admin` (superadmin), créer ensuite les autres comptes
utilisateurs nécessaires (Responsable Collecte, Agent de Collecte,
Observateur…) avec les permissions adaptées à chacun.

---

## 6. Opérations courantes

| Besoin | Commande |
|---|---|
| Démarrer l'application | double-clic sur `start.bat` |
| Arrêter l'application (données conservées) | double-clic sur `stop.bat` |
| Voir l'état / tester l'accès | double-clic sur `status.bat` |
| Voir les journaux du backend | `docker compose logs backend --tail 100` |
| Voir les journaux de tous les services | `docker compose logs -f` |
| Redémarrer un service après une modification | `docker compose restart backend` |

L'application démarre **automatiquement avec Docker Desktop** si celui-ci
est configuré pour démarrer avec Windows (option par défaut) — les
conteneurs ont `restart: unless-stopped` dans `docker-compose.yml`, donc ils
redémarrent avec Docker après un redémarrage du serveur sans action
manuelle. Vérifier avec `status.bat` après tout redémarrage du serveur.

---

## 7. Sauvegardes

Une sauvegarde automatique quotidienne de la base de données peut être
activée :

```powershell
docker compose --profile backup up -d db-backup
```

Les sauvegardes sont stockées dans le volume Docker `db_backups` (rétention
30 jours par défaut, réglable via `BACKUP_RETENTION_DAYS` dans `.env`).

Sauvegarde manuelle immédiate :

```powershell
docker compose exec db pg_dump -U recup_user recup_indurex | Out-File -Encoding utf8 backup_manuel.sql
```

---

## 8. Mise à jour vers une nouvelle version

1. Arrêter l'application : `stop.bat`
2. Remplacer les fichiers du projet par la nouvelle version (en conservant
   le fichier `.env` existant — ne pas l'écraser)
3. Reconstruire et relancer :
   ```powershell
   docker compose build
   docker compose run --rm migrate
   docker compose up -d
   ```

---

## 9. Dépannage

**`docker version` échoue ou Docker Desktop ne démarre pas**
→ Vérifier que la virtualisation est activée dans le BIOS/UEFI du serveur
(Intel VT-x / AMD-V) et que WSL2 est bien installé (`wsl --status`).

**Le site ne répond pas après installation (`status.bat` montre une erreur)**
→ `docker compose logs backend --tail 100` et `docker compose logs nginx --tail 50`
pour voir l'erreur précise. Cause fréquente : le port 80 est déjà utilisé par
IIS ou un autre service — l'arrêter, ou changer le port dans
`docker-compose.yml` (section `nginx` → `ports:`, ex. `8080:80`) puis
relancer `install.bat`.

**Un collègue sur le réseau local n'arrive pas à accéder au site**
→ Vérifier la règle de pare-feu (section 1.3) et que l'IP utilisée est bien
celle du serveur (`ipconfig`), pas `localhost`.

**Mot de passe administrateur perdu**
→ `docker compose exec backend python manage.py changepassword admin`

**Recommencer une installation propre (⚠️ supprime toutes les données)**
```powershell
docker compose down -v
del .env
install.bat
```

---

## 10. Sécurité — à faire avant mise en production réelle

- Changer le mot de passe administrateur généré automatiquement dès la
  première connexion
- Si le serveur est exposé au-delà du réseau local (accès internet), mettre
  en place HTTPS (certificat réel + nom de domaine) — voir
  `GUIDE_INSTALLATION.md` section Certbot pour la configuration SSL, ou
  placer un reverse proxy (IIS, Nginx, Cloudflare Tunnel) devant le port 80
- Ne jamais partager ou committer le fichier `.env`
