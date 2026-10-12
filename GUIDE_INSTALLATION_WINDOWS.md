# Guide d'installation — Windows Server

Installation de RecupIndurex sur un serveur Windows (Windows Server 2022/2019
ou Windows 10/11). L'application tourne dans des conteneurs Docker **Linux**
(PostgreSQL, Django, nginx) — Windows exécute ces conteneurs via Docker
Desktop + son moteur WSL2, pas nativement.

---

## 1. Prérequis

**Aucune installation manuelle n'est nécessaire** — `install.bat` installe
tout seul ce qui manque (WSL2, Docker Desktop, règle de pare-feu). Il suffit
d'avoir :

- Windows 10/11 ou Windows Server 2019+
- Une connexion internet (pour télécharger Docker Desktop la première fois,
  si besoin)
- Un compte Windows avec droits administrateur sur ce PC (une invite de
  sécurité Windows apparaîtra si une installation est nécessaire — cliquer
  sur **Oui**)
- La virtualisation (Intel VT-x / AMD-V) activée dans le BIOS/UEFI — c'est le
  cas par défaut sur la quasi-totalité des PC récents ; voir section 10
  (Dépannage) si l'installation signale un problème à ce sujet, seul point
  qu'un script ne peut pas activer à la place de l'utilisateur.

Si WSL2 n'était pas déjà actif sur ce PC, Windows exigera **un redémarrage,
une seule fois**, en cours d'installation — `install.bat` le signale
clairement, attend une touche avant de redémarrer, et reprend tout seul à la
reconnexion (double-cliquer à nouveau sur `install.bat` n'est pas
nécessaire).

---

## 2. Transférer le projet sur le serveur

Copier l'intégralité du dossier du projet sur le serveur (clé USB, partage
réseau, ou `git clone` si le dépôt est accessible depuis le serveur). Ne pas
oublier : le dossier doit contenir `docker-compose.yml`, `backend/`,
`frontend/`, `install.ps1`, `install.bat`.

Si ce package inclut un dossier **`backup\`** (fichiers
`recup_indurex_data.sql.gz` et `media_backup.tar.gz`), le copier aussi — il
contient les données déjà saisies pour SARL Indurex (compte, fiche
entreprise, logo, cachet, badges ISO) et permet de ne pas repartir de zéro
(voir section 4).

Destination conseillée : `C:\RecupIndurex\`

**Ne pas copier** un éventuel fichier `.env` d'un autre environnement — le
script d'installation en génère un nouveau avec des identifiants uniques et
sécurisés pour ce serveur.

---

## 3. Installer

Dans l'explorateur de fichiers, double-cliquer sur **`install.bat`**. C'est
la seule action manuelle de toute l'installation — tout le reste est
automatique.

(Équivalent en ligne de commande : `powershell -ExecutionPolicy Bypass -File install.ps1`)

Le script :
1. Vérifie WSL2 — l'active automatiquement s'il ne l'est pas encore
   (redémarrage Windows requis dans ce cas précis, voir section 1)
2. Vérifie Docker Desktop — le télécharge et l'installe automatiquement s'il
   est absent (quelques minutes)
3. Démarre Docker et attend qu'il soit prêt
4. Ajoute la règle de pare-feu (accès depuis le réseau local)
5. Génère `.env` avec une clé secrète, un mot de passe de base de données et
   un mot de passe administrateur générés aléatoirement (si `.env` n'existe
   pas déjà)
6. Construit les images (quelques minutes la première fois)
7. Démarre la base de données et attend qu'elle soit prête
8. Applique les migrations, crée le compte administrateur, configure les
   permissions (RBAC)
9. Démarre le backend et le site
10. Vérifie que le site répond bien

Une invite de sécurité Windows ("Voulez-vous autoriser cette application...")
peut apparaître une fois au début si WSL2 ou Docker Desktop doivent être
installés — cliquer sur **Oui**. Si tout est déjà installé sur ce PC, aucune
invite n'apparaît.

**À la fin, le script affiche l'URL et les identifiants administrateur —
notez-les, le mot de passe n'est affiché qu'une seule fois** (il reste
cependant consultable dans le fichier `.env`, à conserver précieusement et
à ne jamais partager). **Si vous restaurez les données existantes de SARL
Indurex (section 4 ci-dessous), ces identifiants générés seront remplacés —
ce n'est pas un problème, passez directement à la section 4.**

Le script est **sans risque à relancer** (idempotent) : si une étape échoue
(coupure réseau pendant le build, etc.), corrigez le problème et relancez
`install.bat` — il reprendra sans dupliquer de données.

---

## 4. Restaurer les données existantes de SARL Indurex (optionnel, une seule fois)

À faire **juste après `install.bat`**, uniquement si le dossier `backup\`
est présent (voir section 2). Cette étape charge les données déjà saisies —
compte `admin_indurex`, fiche entreprise complète, logo, cachet électronique
et badges ISO 9001/14001/45001 — à la place d'une base vide.

Double-cliquer sur **`restore-data.bat`**.

(Équivalent en ligne de commande : `powershell -ExecutionPolicy Bypass -File restore-data.ps1`)

Le script :
1. Vérifie que `backup\recup_indurex_data.sql.gz` et `backup\media_backup.tar.gz` sont présents
2. Restaure la base de données (comptes, fiche entreprise, nomenclature...)
3. Vérifie que tout est à jour (migrations, permissions)
4. Redémarre le backend et le site
5. Restaure les fichiers (logo, cachet, badges ISO)
6. Vérifie que le site répond bien

**Important : après cette restauration, les identifiants générés par
`install.bat` ne sont plus valables.** Utilisez les identifiants fournis
avec ce package (voir `GUIDE_UTILISATION.md`) :
- Administrateur : `admin`
- Récupérateur (SARL Indurex) : `admin_indurex`

Le script est **sans risque à relancer** — il remplace les comptes et
données à chaque exécution par celles du dossier `backup\`, sans dupliquer
quoi que ce soit.

Si le dossier `backup\` n'est pas fourni avec ce package, ignorez cette
section et passez directement à la section 6 (« Première configuration »)
pour créer le compte de l'entreprise depuis zéro.

---

## 5. Vérifier l'installation

- Depuis le serveur : http://localhost/
- Depuis un autre poste du réseau : `http://<IP-du-serveur>/`
  (trouver l'IP avec `ipconfig` sur le serveur)

Se connecter avec le compte administrateur (celui affiché à la fin de
l'installation, ou `admin` si les données existantes ont été restaurées —
section 4).

`status.bat` (à la racine du projet) affiche l'état des conteneurs et teste
l'accès au site en une commande.

---

## 6. Première configuration (si vous n'avez pas restauré de données existantes)

Si la section 4 a été utilisée, le compte `admin_indurex` et sa fiche
entreprise (logo, ISO, cachet...) sont déjà prêts — cette section ne vous
concerne pas.

Sinon, l'application démarre avec une base de données vide — aucune donnée
métier pré-remplie. Pour configurer le compte de l'entreprise elle-même :

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

## 7. Opérations courantes

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

## 8. Sauvegardes

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

## 9. Mise à jour vers une nouvelle version

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

## 10. Dépannage

**`install.bat` affiche une erreur de virtualisation, ou Docker ne démarre
jamais après son installation**
→ C'est le seul point que le script ne peut pas activer à la place de
l'utilisateur : la virtualisation (Intel VT-x / AMD-V) doit être activée
dans le BIOS/UEFI du PC. Redémarrer, entrer dans le BIOS (touche Suppr/F2/F10
selon le fabricant, affichée au tout début du démarrage), chercher une
option "Virtualization Technology", "Intel VT-x" ou "SVM Mode" et l'activer,
puis enregistrer et relancer `install.bat`.

**L'invite de sécurité Windows a été refusée ou fermée par erreur**
→ Relancer simplement `install.bat` et accepter l'invite cette fois.

**Après le redémarrage automatique, l'installation ne reprend pas toute
seule**
→ Se reconnecter sur le compte Windows utilisé pour l'installation (la
reprise automatique est propre à ce compte), ou double-cliquer à nouveau sur
`install.bat` — il reprendra exactement là où il s'était arrêté.

**Le téléchargement de Docker Desktop échoue ("Echec du telechargement")**
→ Ce PC n'a pas accès à internet, ou un pare-feu/proxy d'entreprise bloque
le téléchargement. Télécharger Docker Desktop manuellement depuis
[docker.com](https://www.docker.com/products/docker-desktop) sur un PC qui a
accès à internet, le transférer sur ce PC (clé USB), l'installer normalement
(cocher "Use WSL 2 instead of Hyper-V"), puis relancer `install.bat` — il
détectera que Docker est déjà installé et passera directement à la suite.

**Le site ne répond pas après installation (`status.bat` montre une erreur)**
→ `docker compose logs backend --tail 100` et `docker compose logs nginx --tail 50`
pour voir l'erreur précise. Cause fréquente : le port 80 est déjà utilisé par
IIS ou un autre service — l'arrêter, ou changer le port dans
`docker-compose.yml` (section `nginx` → `ports:`, ex. `8080:80`) puis
relancer `install.bat`.

**Un collègue sur le réseau local n'arrive pas à accéder au site**
→ Vérifier que la règle de pare-feu a bien été créée (`install.bat` l'ajoute
automatiquement — sinon, voir le message affiché à l'étape "Verification du
pare-feu" lors de l'installation) et que l'IP utilisée est bien celle du
serveur (`ipconfig`), pas `localhost`.

**Mot de passe administrateur perdu**
→ `docker compose exec backend python manage.py changepassword admin`

**`restore-data.bat` échoue avec "Fichiers de sauvegarde introuvables"**
→ Vérifier que le dossier `backup\` (avec `recup_indurex_data.sql.gz` et
`media_backup.tar.gz`) a bien été copié à la racine du projet, au même
niveau que `restore-data.bat` (voir section 2).

**Recommencer une installation propre (⚠️ supprime toutes les données)**
```powershell
docker compose down -v
del .env
install.bat
```
Pour repartir avec les données de SARL Indurex après une réinstallation
propre, relancer ensuite `restore-data.bat` (section 4).

---

## 11. Sécurité — à faire avant mise en production réelle

- Si vous êtes parti d'une base vide (section 6), changer le mot de passe
  administrateur généré automatiquement dès la première connexion
- Si le serveur est exposé au-delà du réseau local (accès internet), mettre
  en place HTTPS (certificat réel + nom de domaine) — voir
  `GUIDE_INSTALLATION.md` section Certbot pour la configuration SSL, ou
  placer un reverse proxy (IIS, Nginx, Cloudflare Tunnel) devant le port 80
- Ne jamais partager ou committer le fichier `.env` ni le dossier `backup\`
  (il contient des mots de passe et des documents de l'entreprise)
