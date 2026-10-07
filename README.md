# RECUP-DZ
## Système de Gestion des Récupérateurs de Déchets — Algérie
**Conforme à : Loi n°01-19 | Décret exécutif n°06-104**

---

> **Déploiement en production (serveur client) : utiliser Docker.**
> - Serveur Windows → [`GUIDE_INSTALLATION_WINDOWS.md`](GUIDE_INSTALLATION_WINDOWS.md) (double-clic sur `install.bat`)
> - Serveur Linux → [`GUIDE_INSTALLATION.md`](GUIDE_INSTALLATION.md)
>
> Les instructions ci-dessous (venv Python, `npm run dev`...) décrivent un
> environnement de **développement local uniquement** — ne pas les suivre
> pour un déploiement client.

---

## 🚀 Installation et lancement (développement local uniquement)

### Prérequis
- Python 3.10+
- Node.js 18+
- Windows / VS Code

---

### BACKEND

```powershell
# 1. Ouvrir PowerShell dans le dossier backend
cd recup_dz\backend

# 2. Créer l'environnement virtuel
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Créer les tables de la base de données
python manage.py makemigrations
python manage.py migrate

# 5. Créer le superuser + importer la nomenclature
python setup.py

# 6. Lancer le serveur backend
python manage.py runserver
```

Le backend sera disponible sur : **http://localhost:8000**
- Admin Django : http://localhost:8000/admin
- API : http://localhost:8000/api/

---

### FRONTEND

```powershell
# Ouvrir un NOUVEAU PowerShell dans le dossier frontend
cd recup_dz\frontend

# Installer les dépendances
npm install

# Lancer le serveur frontend
npm run dev
```

Le frontend sera disponible sur : **http://localhost:5173**

---

## 🔑 Compte superuser

| Champ      | Valeur         |
|------------|----------------|
| Username   | `admin`        |
| Password   | `Admin2024!`   |
| Role       | ADMIN          |
| URL Admin  | http://localhost:8000/admin |
| URL App    | http://localhost:5173 |

### Compte inspecteur de test
| Username      | Password        |
|---------------|-----------------|
| `inspecteur1` | `Inspect2024!`  |

---

## 📁 Structure du projet

```
recup_dz/
├── backend/
│   ├── config/          ← Settings, URLs Django
│   ├── apps/
│   │   ├── accounts/    ← Utilisateurs et authentification
│   │   ├── recuperateurs/ ← Fiches récupérateurs
│   │   ├── nomenclature/  ← Nomenclature nationale des déchets
│   │   ├── operations/    ← Opérations de récupération
│   │   ├── bsd/           ← Bordereaux de Suivi des Déchets
│   │   ├── declarations/  ← Déclarations réglementaires
│   │   └── inspections/   ← Contrôles et inspections
│   ├── manage.py
│   ├── setup.py         ← Script de configuration initiale
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── pages/       ← Pages de l'application
    │   ├── components/  ← Composants réutilisables
    │   ├── api.js       ← Appels API
    │   ├── store.js     ← État global (Zustand)
    │   └── App.jsx      ← Routes principales
    └── package.json
```

---

## 📋 Modules disponibles

| Module          | URL                    | Description                          |
|-----------------|------------------------|--------------------------------------|
| Dashboard       | `/dashboard`           | Tableau de bord avec statistiques    |
| Récupérateurs   | `/recuperateurs`       | Gestion des fiches récupérateurs     |
| Nomenclature    | `/nomenclature`        | Codes déchets (Décret 06-104)        |
| Opérations      | `/operations`          | Suivi des opérations de récupération |
| BSD             | `/bsd`                 | Bordereaux de Suivi des Déchets      |
| Déclarations    | `/declarations`        | Déclarations mensuelles/trimestrielles |
| Inspections     | `/inspections`         | PV de contrôle et d'inspection       |
| Statistiques    | `/stats`               | Rapports et analyses                 |

---

## 🔌 API Endpoints

```
POST /api/auth/token/         → Connexion (JWT)
POST /api/auth/token/refresh/ → Refresh token
GET  /api/accounts/me/        → Utilisateur connecté

GET/POST   /api/recuperateurs/       → Liste/Création
GET/PATCH  /api/recuperateurs/{id}/  → Détail/Modification
GET        /api/recuperateurs/stats/ → Statistiques
GET        /api/recuperateurs/alerts/ → Alertes

GET /api/nomenclature/        → Nomenclature des déchets
GET /api/operations/          → Opérations
GET /api/bsd/                 → BSD
POST /api/bsd/{id}/signer/    → Signature BSD
GET /api/declarations/        → Déclarations
GET /api/inspections/         → Inspections
```

---

## 🏗️ Catégories de récupérateurs

| Catégorie | Description                    | Agrément requis |
|-----------|--------------------------------|-----------------|
| CAT1      | Déchets non dangereux (MA/I)   | Non             |
| CAT2      | Déchets Spéciaux               | Oui — Wilaya    |
| CAT3      | Déchets Spéciaux Dangereux     | Oui — Ministère |
| CAT4      | Carte professionnelle          | Carte pro       |

---

## ⚖️ Conformité réglementaire

- **Loi n°01-19** du 12 décembre 2001 relative à la gestion, au contrôle et à l'élimination des déchets
- **Décret exécutif n°06-104** fixant la nomenclature des déchets
- **Décret exécutif n°05-315** fixant les modalités de déclaration des déchets spéciaux dangereux
