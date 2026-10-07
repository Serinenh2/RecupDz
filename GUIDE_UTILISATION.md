# Guide d'utilisation — RecupIndurex

Guide pas-à-pas pour utiliser l'application au quotidien. Aucune connaissance
technique n'est nécessaire.

---

## Accès à l'application

**Adresse (URL)** : http://localhost/
*(depuis un autre poste du réseau : `http://<adresse-IP-du-serveur>/`)*

**Comptes de connexion :**

| Compte | Utilisateur | Mot de passe | À utiliser pour |
|---|---|---|---|
| Administrateur | `admin` | `Indurex2026` | Créer/gérer les comptes utilisateurs, administration générale |
| Récupérateur (SARL Indurex) | `admin_indurex` | `Indurex2026` | Le travail quotidien : créer des documents, suivre les déchets |

> **Important** : changez ces deux mots de passe dès la première connexion
> (voir section 13, *Changer le mot de passe d'un compte*). Ne les
> partagez pas par écrit ou par message non sécurisé.

Pour le travail de tous les jours (créer un Bon de Commande, suivre une
récupération de déchets, etc.), connectez-vous avec **`admin_indurex`**.
Le compte **`admin`** sert uniquement à gérer qui a accès à l'application.

---

## Sommaire

1. [Se connecter](#1-se-connecter)
2. [Découvrir l'écran principal](#2-découvrir-lécran-principal)
3. [Remplir les informations de l'entreprise (Mon Profil)](#3-remplir-les-informations-de-lentreprise-mon-profil)
4. [Gérer les partenaires (Opérateurs)](#4-gérer-les-partenaires-opérateurs)
5. [Suivre une récupération de déchets (Traçabilité)](#5-suivre-une-récupération-de-déchets-traçabilité)
6. [Créer les documents commerciaux (Documents)](#6-créer-les-documents-commerciaux-documents)
7. [Les inspections (PV)](#7-les-inspections-pv)
8. [Les alertes](#8-les-alertes)
9. [Archiver un document](#9-archiver-un-document)
10. [Consulter la nomenclature](#10-consulter-la-nomenclature)
11. [Consulter les statistiques](#11-consulter-les-statistiques)
12. [Le glossaire](#12-le-glossaire)
13. [Gérer les utilisateurs (compte administrateur)](#13-gérer-les-utilisateurs-compte-administrateur)
14. [Questions fréquentes](#14-questions-fréquentes)

---

## 1. Se connecter

1. Ouvrir un navigateur internet (Chrome, Edge...)
2. Aller sur **http://localhost/**
3. Saisir le nom d'utilisateur et le mot de passe (voir tableau ci-dessus)
4. Cliquer sur **Se connecter**

Vous arrivez sur le **Tableau de bord**.

---

## 2. Découvrir l'écran principal

Un menu est affiché sur le côté gauche de l'écran. Chaque ligne du menu ouvre
une page différente :

| Menu | À quoi ça sert |
|---|---|
| **Tableau de bord** | Vue d'ensemble de l'activité |
| **Opérateurs** | Liste de vos partenaires (transporteurs, éliminateurs...) |
| **Traçabilité** | Suivi de chaque déchet récupéré |
| **Documents** | Proforma, Bon de Commande, Bon de Livraison, Facture, BSD, DSD |
| **Statistiques** | Chiffres et totaux de l'activité |
| **Nomenclature** | Catalogue de vos articles + codes déchets officiels |
| **Glossaire** | Définitions des termes utilisés dans l'application |
| **Archive** | Stockage de documents (contrats, agréments scannés...) |
| **Alertes** | Avertissements (ex : agrément qui expire bientôt) |

En bas du menu : **Mon Profil** (vos informations et celles de l'entreprise)
et **Déconnexion**.

---

## 3. Remplir les informations de l'entreprise (Mon Profil)

**À faire en premier**, une seule fois (sauf si les informations changent).

1. Cliquer sur **Mon Profil** en bas du menu
2. Dans la section *Fiche récupérateur*, remplir :
   - Raison sociale, responsable, statut juridique
   - RC, NIF, NIS, numéro d'article
   - Adresse, téléphone, email, compte bancaire
   - *Slogan* et *Capital social* (optionnel — apparaissent sur les
     documents PDF si renseignés)
3. Cliquer sur **Choisir un fichier** sous chaque image pour ajouter :
   - le **logo** de l'entreprise
   - le **cachet électronique**
   - les **badges ISO 9001 / 14001 / 45001** (si l'entreprise les possède)
4. Cliquer sur **Mettre à jour la fiche** (en bas de la section *Fiche
   récupérateur*)

➡️ Le logo, le cachet et les badges ISO apparaîtront automatiquement sur
**tous** les documents générés ensuite (Proforma, BC, BL, Facture).

---

## 4. Gérer les partenaires (Opérateurs)

Un **Opérateur** est une entreprise avec qui vous travaillez : celle qui
produit le déchet (**Générateur**), celle qui le transporte
(**Transporteur**), celle qui le traite (**Éliminateur**,
**Valorisateur**) ou le **Centre d'Enfouissement Technique (CET)**.

**Ajouter un opérateur :**

1. Cliquer sur **Opérateurs** dans le menu
2. Cliquer sur **Nouvel opérateur**
3. Choisir son type (Générateur / Transporteur / Éliminateur / Valorisateur / CET...)
4. Remplir ses informations (raison sociale, adresse, agrément si applicable)
5. Cliquer sur **Créer l'opérateur**

Ces fiches seront ensuite proposées automatiquement dans les listes
déroulantes lors de la création des documents — pas besoin de les
ressaisir à chaque fois.

---

## 5. Suivre une récupération de déchets (Traçabilité)

C'est l'opération **la plus fréquente** : chaque fois que vous récupérez
un déchet chez un client, vous créez un **dossier de traçabilité**.

1. Cliquer sur **Traçabilité** dans le menu
2. Cliquer sur **Nouveau dossier**
3. Remplir le formulaire en 4 étapes (utilisez **Étape suivante** pour
   avancer, **Retour** pour revenir en arrière) :

   | Étape | Contenu |
   |---|---|
   | 1. Générateur & Déchet | Qui a produit le déchet, quel type de déchet, quelle quantité |
   | 2. Enlèvement & Transport | Quand et où le déchet a été enlevé, quel transporteur |
   | 3. Destination finale | Où va le déchet : valorisation, élimination, CET, ou mis en stock |
   | 4. Statut & Clôture | Prix, frais de transport, statut du dossier |

4. Sur la dernière étape, cliquer sur **Créer le dossier de traçabilité**

Chaque dossier créé peut ensuite être retrouvé, modifié ou consulté depuis
la liste de la page Traçabilité. Les quantités en stock, valorisées ou
éliminées apparaissent automatiquement dans les **Statistiques**.

---

## 6. Créer les documents commerciaux (Documents)

La page **Documents** regroupe tous les documents que vous émettez. En haut
de la page, des onglets permettent de choisir le type de document :
**Proforma**, **BC**, **BL**, **Facture**, **DSD**, **BSD**.

### Proforma → Bon de Commande → Bon de Livraison → Facture

Ces quatre documents s'enchaînent naturellement dans une vente :

1. **Proforma** : devis envoyé au client avant la commande
2. **BC (Bon de Commande)** : confirmation de la commande
3. **BL (Bon de Livraison)** : accompagne la marchandise livrée
4. **Facture** : document de facturation final

**Pour créer un document :**

1. Cliquer sur l'onglet correspondant (ex : **Proforma**)
2. Cliquer sur le bouton **Nouveau...** en haut à droite (son nom change
   selon l'onglet : *Nouveau Proforma*, *Nouveau BC*, *Nouveau BL*,
   *Nouvelle Facture*)
3. Choisir le **Récupérateur** émetteur (si plusieurs comptes existent)
4. Remplir les informations du client et les lignes d'articles (désignation,
   quantité, prix)
5. Cliquer sur le bouton de création en bas du formulaire (*Créer le
   Proforma*, *Créer le BC*, *Créer le BL* ou *Créer la Facture*)

**Pour transformer un document en document suivant** (ex : une Proforma
acceptée devient un Bon de Commande) : ouvrir le document concerné et
utiliser le bouton de génération automatique proposé sur sa fiche — les
informations sont reprises automatiquement, pas besoin de tout ressaisir.

**Pour télécharger un document** (PDF ou Word) : cliquer sur l'icône de
téléchargement à côté du document dans la liste.

### BSD (Bordereau de Suivi des Déchets) et DSD (Déclaration)

Ce sont des documents **réglementaires obligatoires** pour certains types
de déchets (spéciaux / dangereux). Même principe de création que ci-dessus,
via leurs onglets respectifs (boutons *Nouveau BSD* / *Nouvelle DSD*, puis
*Créer le BSD* / *Enregistrer la DSD*).

---

## 7. Les inspections (PV)

Pour enregistrer un contrôle ou une inspection (procès-verbal) :

1. Cliquer sur **Inspections** (menu latéral, section hors "Documents")
2. Cliquer sur **Nouveau PV**
3. Choisir le type de contrôle, la date, le résultat, les observations
4. Cliquer sur **Créer le PV**

Le PV peut ensuite être téléchargé en PDF ou Word depuis sa fiche.

---

## 8. Les alertes

La page **Alertes** affiche automatiquement les avertissements importants,
par exemple : un agrément qui a expiré ou qui arrive bientôt à expiration.

- Les alertes **rouges** sont critiques (agrément expiré)
- Les alertes **orange** sont des avertissements (expiration proche)

Si une alerte concerne votre propre entreprise, un bouton permet d'aller
directement sur **Mon Profil** pour la corriger (ex : renouveler
l'agrément).

---

## 9. Archiver un document

Pour conserver un document qui n'est pas généré par l'application (ex : un
contrat signé, un agrément scanné) :

1. Cliquer sur **Archive** dans le menu
2. Cliquer sur **Importer un document**
3. Glisser le fichier (ou cliquer pour le choisir) — formats acceptés :
   PDF, Word, Excel, images, archives zip — 50 Mo maximum
4. Donner un titre et choisir une catégorie
5. Cliquer sur **Importer le document**

---

## 10. Consulter la nomenclature

La page **Nomenclature** a deux onglets :

- **Mon catalogue** : la liste de vos articles habituels (ex : Palette de
  PEHD, BigBag, Cartons déchets...) avec leur référence et le code déchet
  officiel correspondant
- **Codes déchets** : la liste complète des codes déchets officiels
  (Décret exécutif n° 06-104), avec leur classe (Ménagers et Assimilés,
  Inertes, Spéciaux, Spéciaux Dangereux) et leur dangerosité

Utilisez la barre de recherche en haut de chaque onglet pour retrouver
rapidement un article ou un code.

---

## 11. Consulter les statistiques

La page **Statistiques** permet de choisir quels chiffres afficher plutôt
que de tout montrer en même temps :

1. Cliquer sur **Statistiques** dans le menu
2. Choisir une période (Quotidienne, Date précise, Intervalle, Mensuelle, Annuelle)
3. Dans la ligne **Statistiques à afficher**, cliquer sur chaque bouton pour
   l'activer ou le désactiver :
   - Déchets spéciaux et spéciaux dangereux
   - Déchets ménagers et assimilés
   - Déchets envoyés au CET
   - Stock actuel par type de déchets
   - Évolution des prix
   - Évolution des quantités

Chaque section affichée peut être exportée en fichier CSV (bouton
**Exporter CSV**) pour l'ouvrir dans Excel.

---

## 12. Le glossaire

La page **Glossaire** liste les définitions des termes techniques et
réglementaires utilisés dans l'application (BSD, DSD, CET, agrément...).
Utile en cas de doute sur un terme.

---

## 13. Gérer les utilisateurs (compte administrateur)

**Réservé au compte `admin`.** Pour donner accès à l'application à une
nouvelle personne :

1. Se connecter avec le compte **`admin`**
2. Dans le menu, section *Administration*, cliquer sur **Utilisateurs**
3. Cliquer sur **Nouvel utilisateur**
4. Renseigner un nom d'utilisateur, un mot de passe, et choisir un **rôle** :

   | Rôle | Pour qui |
   |---|---|
   | Super Administrateur | Accès complet (à réserver, usage rare) |
   | Administrateur | Gestion quasi complète |
   | Récupérateur | Usage quotidien : créer des documents, suivre les déchets |
   | Responsable Collecte | Suivi des opérations de collecte |
   | Agent de Collecte | Saisie terrain |
   | Responsable Décharge | Suivi des opérations de décharge/CET |
   | Observateur | Consultation uniquement, aucune modification |

5. Cliquer sur **Créer**

> Si le rôle choisi est **Récupérateur**, une fiche entreprise vide est
> créée automatiquement pour ce compte — la personne pourra se connecter
> et remplir ses propres informations via **Mon Profil** (voir section 3).

Depuis cette même page, un administrateur peut aussi **désactiver** un
compte (icône correspondante) sans le supprimer, ou le supprimer
définitivement.

**Changer le mot de passe d'un compte :** il n'existe pas de bouton
"changer mon mot de passe" accessible à l'utilisateur lui-même — seul le
compte `admin` peut le faire :

1. Se connecter avec le compte **`admin`**
2. Aller dans **Utilisateurs**, cliquer sur le compte concerné
3. Cliquer sur l'icône **clé** (🔑) **Réinitialiser le mot de passe**
4. Saisir le nouveau mot de passe (8 caractères minimum) et confirmer

---

## 14. Questions fréquentes

**Je ne vois pas certains menus (Opérateurs, Documents...).**
→ Cela dépend du rôle de votre compte. Un compte "Observateur" par exemple
ne peut pas créer de documents. Demandez à l'administrateur de vérifier
votre rôle (section 13).

**Je ne peux pas créer de Proforma / Bon de Commande.**
→ Vérifiez qu'un **Récupérateur** est bien sélectionné dans le formulaire.
Si aucun n'apparaît dans la liste, contactez l'administrateur : un compte
Récupérateur doit d'abord exister (voir section 13).

**J'ai oublié mon mot de passe / je veux le changer.**
→ Contactez la personne qui a le compte `admin` : elle peut le réinitialiser
depuis **Utilisateurs** (icône clé — voir section 13). Il n'y a pas
d'option pour le changer soi-même.

**Le logo / les badges ISO n'apparaissent pas sur mes documents PDF.**
→ Ils doivent d'abord être importés dans **Mon Profil** (section 3). Une
fois importés, ils s'affichent automatiquement sur tous les nouveaux
documents.

**Un document a disparu / je ne le retrouve pas.**
→ Vérifiez que vous êtes sur le bon onglet (Proforma / BC / BL / Facture /
DSD / BSD) dans la page Documents, et utilisez la barre de recherche.

**Je ne sais pas quel code déchet utiliser pour un article.**
→ Consultez l'onglet **Mon catalogue** de la page Nomenclature (section
10) : le code déchet officiel y est indiqué à côté de chaque article
habituel de l'entreprise.
