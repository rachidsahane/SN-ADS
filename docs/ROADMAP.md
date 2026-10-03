# ROADMAP.md : Plan de construction

Document de référence n°12 sur 13.

Ordre imposé : socle technique et authentification, puis données, puis fonctionnalités, puis intégrations externes.
Chaque phase tient dans une session de travail de Claude Code et produit un résultat visible à l'écran.
Le déroulé d'une phase et sa définition de terminé générale sont dans `CLAUDE.md`. Les critères ci-dessous s'ajoutent à cette définition générale.

Tout est conteneurisé dès la phase 0 : interface, API, modèle, base de données, authentification et stockage tournent dans des conteneurs Docker, en local comme sur AWS (voir `ARCHITECTURE.md` 1.1).

Avant la phase 16, Sentry n'est pas branché : les erreurs passent par `infra/observability.py` et `lib/observability.ts`, qui journalisent localement. La phase 16 y branche Sentry sans toucher au reste du code.

## Suivi

Tenu à jour par Claude Code à la fin de chaque phase.

| Phase | Titre | Statut | Pull request | Date |
|---|---|---|---|---|
| 0 | Socle du dépôt | en cours (construit et vérifié en local ; pull request en attente de la décision GitHub) | en attente (dépôt GitHub à créer) | |
| 1 | Base locale et profils | en cours (construit en local) | en attente (dépôt GitHub à créer, comme la phase 0) | |
| 2 | Authentification | à faire | | |
| 3 | Gestion des utilisateurs et audit | à faire | | |
| 4 | Stockage des données et jeu de départ | à faire | | |
| 5 | Import des données de l'agence | à faire | | |
| 6 | File d'attente et worker | à faire | | |
| 7 | Apprentissage des trois modèles | à faire | | |
| 8 | Comparaison, activation et page Model | à faire | | |
| 9 | Formulaire et prédiction des trois chiffres | à faire | | |
| 10 | Niveau de performance | à faire | | |
| 11 | Facteurs de la campagne | à faire | | |
| 12 | Recommandations | à faire | | |
| 13 | Simulation en direct et brouillon | à faire | | |
| 14 | Enregistrement, historique et isolation | à faire | | |
| 15 | Robustesse et suite de bout en bout complète | à faire | | |
| 16 | Sentry | à faire | | |
| 17 | Infrastructure AWS de staging | à faire | | |
| 18 | Pipelines CI/CD | à faire | | |
| 19 | E-mails réels (Amazon SES) | à faire | | |
| 20 | Mise en production | à faire | | |

Piste annexe (accord de l'utilisateur, D-044) : **préparation de la phase 7**, trois notebooks d'analyse et d'entraînement dans `notebooks/` (Docker uniquement), sans changer le périmètre ni l'ordre des phases. Branche `phase/07-notebooks-prep`, statut : en cours.

---

## Socle technique et authentification

### Phase 0 : Socle du dépôt
**Objectif** : un dépôt propre qui démarre en local avec une commande.
**Périmètre** :
- dépôt GitHub `soronua-campaign-predictor`, branches `dev`, `staging`, `main`, protections (`CONVENTIONS.md` 4.4) ;
- arborescence de `LLD.md` (dossiers et fichiers de configuration) ;
- versions figées et tableau de `CONVENTIONS.md` 1 complété ;
- `Makefile`, `docker-compose.yml`, image `toolbox` (`tools/Dockerfile`) qui porte tous les outils, `pre-commit` (dont `gitleaks`), `.env.example` ; aucun outil installé directement sur la machine ;
- API FastAPI avec `/api/health` ;
- Next.js avec une page d'accueil provisoire affichant l'état de l'API ;
- configuration des outils de test (pytest, Vitest, Playwright) avec un premier test chacun ;
- documents copiés dans `docs/`, `docs/decisions.md` créé ;
- jeu de départ dans `data/seed/` avec `SOURCE.md` (origine Kaggle et licence).

**Définition de terminé (à l'écran)** :
- sur `http://localhost:3000`, le titre "Soro Nua Campaign Predictor" et la ligne "API: healthy" en vert ;
- en arrêtant le conteneur `api`, la ligne devient "API: unreachable" en rouge ;
- sur GitHub, les trois branches existent et une poussée directe sur `main` est refusée.

### Phase 1 : Base locale et profils
**Objectif** : la pile Supabase auto-hébergée tourne en conteneurs en local, avec les profils, l'audit et leurs règles d'isolation.
**Périmètre** : `deploy/supabase/` (composition réduite, images figées par digest, `kong.yml`, `generate_keys.py`), Mailpit, inclusion dans `docker-compose.yml`, `make db-reset` ; migrations 1 et 2 de `DATA_MODEL.md` 7 (types, `profiles`, `is_admin`, `is_active_user`, déclencheurs, `audit_log`, `log_audit`), tests pgTAP, `/api/ready` avec vérification de la base et version du schéma.
**Définition de terminé** :
- la page d'accueil affiche aussi "Database: connected (schema <numéro>)" ;
- Supabase Studio local (`http://localhost:54323`) montre les tables `profiles` et `audit_log` avec "RLS enabled".

### Phase 2 : Authentification
**Objectif** : se connecter, se déconnecter, accepter une invitation, réinitialiser son mot de passe.
**Périmètre** :
- écrans "Sign in", "Forgot password", "Set your password" ;
- route `/auth/confirm` ;
- middleware de session ;
- gabarits d'e-mails ;
- vérification des jetons côté API et `GET /api/v1/me` ;
- cache de profil (Redis local) ;
- commande `bootstrap_admin` ;
- en-tête avec nom et bouton "Sign out" ;
- page `/predict` vide protégée ;
- scénarios E2E-AUTH-01 à 04, 06 et 07.

**Définition de terminé** :
- le premier administrateur reçoit l'invitation dans la boîte mail locale (`http://localhost:54324`), définit son mot de passe et arrive sur une page "Predict" vide avec son nom en haut à droite ;
- un mauvais mot de passe affiche "Invalid email or password." ;
- après "Sign out", l'adresse `/predict` renvoie vers "Sign in".

### Phase 3 : Gestion des utilisateurs et audit
**Objectif** : l'administrateur gère l'équipe.
**Périmètre** :
- routes `/api/v1/admin/users*` et `/api/v1/admin/audit-log` ;
- pages "Users" et "Audit log" ;
- invitation, changement de rôle, désactivation (avec bannissement Auth), réactivation ;
- garde du dernier administrateur et interdiction d'agir sur soi-même ;
- navigation selon le rôle et garde des pages d'administration ;
- scénarios E2E-USR, E2E-AUTH-05 et 08, E2E-ISO-06 et 07, E2E-SESS-03.

**Définition de terminé** :
- l'administrateur invite un collègue, qui apparaît "Invited" puis "Active" après avoir défini son mot de passe ;
- le collègue connecté (`marketer`) ne voit pas les menus d'administration et, en tapant `/admin/users`, revient sur "Predict" avec "You do not have access to this page." ;
- une désactivation empêche le collègue de continuer (message de désactivation) ;
- la page "Audit log" liste toutes ces actions.

## Données

### Phase 4 : Stockage des données et jeu de départ
**Objectif** : les 8 000 lignes du jeu de départ sont en base, avec les lignes de test désignées.
**Périmètre** :
- migration 3 (`dataset_uploads`, `dataset_rows`, espace `dataset-uploads`) et tests pgTAP ;
- `domain/dataset_schema.py`, `domain/csv_validation.py`, `domain/holdout.py` ;
- commande `seed_dataset` ;
- `GET /api/v1/admin/dataset/summary` et `GET /api/v1/admin/uploads` ;
- page "Data" (résumé et liste des imports).

**Définition de terminé** :
- la page "Data" affiche "Seed rows: 8,000", "Agency rows: 0", un nombre de lignes de test proche de 1 600, et une ligne d'import "seed" au statut "Ready" ;
- relancer la commande de chargement ne change rien à l'écran.

### Phase 5 : Import des données de l'agence
**Objectif** : l'administrateur ajoute des données au bon format, et seulement au bon format.
**Périmètre** :
- `POST /api/v1/admin/uploads` et `upload_service` (validation complète, empreinte, doublons, stockage, lots, nettoyage en cas d'échec, audit) ;
- formulaire d'import avec case d'anonymisation et rappels ;
- tableau des erreurs ;
- fichiers de test valides et invalides ;
- scénarios E2E-DATA et E2E-INV-05 à 08.

**Définition de terminé** :
- un fichier valide de 300 lignes apparaît "Ready" et le résumé passe à "Agency rows: 300" ;
- un fichier contenant un taux à 5 affiche un tableau d'erreurs (ligne, colonne, message) et le résumé ne change pas ;
- réimporter le premier fichier affiche "This file has already been imported."

### Phase 6 : File d'attente et worker
**Objectif** : la mécanique d'apprentissage en arrière-plan fonctionne de bout en bout.
**Périmètre** :
- migration 4 (`model_versions`, espace `model-artifacts`, `activate_model_version`) et tests pgTAP ;
- `infra/queue.py` ;
- `worker.py` (boucle, battement, reprise des travaux orphelins, versions bloquées) ;
- `training_request_service` ;
- `training_job` provisoire (compte les lignes du périmètre, attend 5 secondes, réussit) ;
- routes `POST/GET /api/v1/admin/model-versions` ;
- page "Models" avec bouton "Train a new version", choix du périmètre et statut rafraîchi toutes les 3 s ;
- scénario E2E-CONC-01.

**Définition de terminé** :
- un clic sur "Train a new version" fait apparaître "v1" en "Queued", puis "Running", puis "Succeeded" sans recharger la page ;
- un second clic pendant l'exécution affiche "A training run is already in progress." ;
- en arrêtant le worker pendant "Running" puis en le relançant plus tard, la version finit en "Failed" avec "Training was interrupted." (test avec délai réduit).

### Phase 7 : Apprentissage des trois modèles
**Objectif** : de vrais modèles XGBoost, évalués honnêtement.
**Périmètre** :
- `domain/features.py`, `derived_metrics.py`, `scoring.py` (construction des références et seuils), `engagement_defaults.py`, `explanations.py` (importance globale) ;
- `ml/*` ;
- `training_job` réel (`LLD.md` 5.7) avec dépôt des artefacts ;
- détail d'une version : métriques par chiffre, fiabilité, nombre de lignes, variables utilisées ;
- tests dorés sur `small_dataset.csv`.

**Définition de terminé** :
- sur la page d'une version réussie : un tableau avec, pour "Click-through rate", "Conversion rate" et "Website visits", l'erreur moyenne, l'erreur d'une prédiction constante et la fiabilité ("Low" pour le jeu de départ) ;
- une version entraînée sur les données de test fortes (`small_dataset.csv` importé) affiche une fiabilité "Moderate" ou "Good" ;
- un apprentissage "Agency data only" avec moins de 250 lignes est refusé avec le message prévu.

### Phase 8 : Comparaison, activation et page Model
**Objectif** : choisir en connaissance de cause la version utilisée par l'équipe.
**Périmètre** :
- `domain/comparison.py` intégré au travail ;
- `activation_service` et pointeur Upstash ;
- `model_registry` (chargement et rechargement toutes les 30 s) ;
- `GET /api/v1/model/active` ;
- tableau de comparaison, verdict, bouton "Activate this version" ;
- page "Model" pour tous (fiabilité, importance globale en graphique, bandeau de fiabilité faible) ;
- commande `activate_model_version` ;
- scénarios E2E-MOD et E2E-CONC-02.

**Définition de terminé** :
- la première version s'active en un clic ;
- la page "Model", vue par un `marketer`, affiche "v1", sa date, sa fiabilité et un graphique des éléments qui comptent le plus ;
- une seconde version affiche le tableau avant/après et le verdict, et le bouton n'est actif que si le verdict est favorable ;
- deux administrateurs qui activent en même temps : l'un voit "The active version changed since you opened this page..."

## Fonctionnalités

### Phase 9 : Formulaire et prédiction des trois chiffres
**Objectif** : décrire une campagne et voir les trois chiffres.
**Périmètre** :
- `GET /api/v1/reference/options`, `GET /api/v1/reference/engagement-defaults` ;
- `POST /api/v1/predictions/simulate` (trois chiffres, dérivés, avertissements hors plage et fiabilité) ;
- formulaire en trois blocs avec pré-remplissage et validation Zod ;
- cartes des trois chiffres et des deux chiffres dérivés ;
- bandeau "No active model yet..." ;
- limite de débit `simulate` ;
- scénarios E2E-PRED-01, 02, 06, 07, 08 et E2E-INV-01 à 04.

**Définition de terminé** :
- sur "Predict", choisir "Email" et "Conversion" remplit automatiquement les cinq champs d'engagement ;
- après avoir complété le formulaire et cliqué "Predict", cinq cartes apparaissent : "Click-through rate", "Conversion rate", "Website visits", "Estimated leads", "Estimated cost per result" ;
- un budget négatif affiche un message sous le champ.

### Phase 10 : Niveau de performance
**Objectif** : savoir si la campagne est faible, moyenne ou forte.
**Périmètre** : notes, score, seuils et niveau à la prédiction (`LLD.md` 6.3 et 6.4), avertissement de repli de référence, composant `PerformanceLevel` (badge, score sur 100, trois notes).
**Définition de terminé** :
- sous les cartes, un badge "Low", "Medium" ou "High" de couleur distincte, le score "48.2 / 100" et les trois notes ;
- une campagne dont les prospects estimés valent zéro affiche "n/a" pour le coût par résultat et une note de coût à 0.

### Phase 11 : Facteurs de la campagne
**Objectif** : comprendre ce qui pèse sur chaque chiffre.
**Périmètre** : contributions par variable, regroupement par champ, 5 principaux facteurs par chiffre, graphique à barres horizontales (vers la droite = fait monter, vers la gauche = fait baisser), onglets par chiffre.
**Définition de terminé** :
- une section "What drives these predictions" avec trois onglets ;
- chaque onglet montre 5 barres étiquetées avec les libellés anglais du glossaire et leur valeur saisie.

### Phase 12 : Recommandations
**Objectif** : savoir quoi changer.
**Périmètre** :
- `domain/recommendations.py` (variantes, calcul en un lot, meilleure par levier, seuil de 5 points, top 3) ;
- composant `RecommendationsList` avec avant/après et bouton "Apply" ;
- message "No tested change improves the result significantly." ;
- scénario E2E-PRED-05.

**Définition de terminé** :
- avec le modèle entraîné sur les données de test fortes, jusqu'à trois cartes "Change channel from Email to PPC: +6.1 points (Medium → High)" apparaissent, chacune avec "Apply" ;
- avec le modèle du jeu de départ, le message "No tested change improves the result significantly." s'affiche le plus souvent.

### Phase 13 : Simulation en direct et brouillon
**Objectif** : essayer des variantes sans cliquer, sans rien perdre.
**Périmètre** :
- `use-simulation` (anti-rebond 400 ms, annulation, affichage des résultats précédents pendant le calcul) ;
- suppression du bouton "Predict" au profit du calcul automatique ;
- `use-form-draft` ;
- "Apply" déclenche le recalcul ;
- scénario E2E-PRED-04.

**Définition de terminé** :
- modifier le budget met à jour les résultats environ une demi-seconde après la dernière frappe, avec un indicateur de recalcul ;
- recharger la page restaure le formulaire tel qu'il était.

### Phase 14 : Enregistrement, historique et isolation
**Objectif** : retrouver ses prédictions, et seulement les siennes.
**Périmètre** :
- migration 5 (`predictions`) et tests pgTAP ;
- `POST/GET/DELETE /api/v1/predictions*` ;
- pagination par curseur ;
- dialogue "Save prediction" ;
- pages "History" et détail figé ;
- limite de débit `save` ;
- scénarios E2E-HIST, E2E-ISO-01 à 05 et 08, E2E-CONC-05.

**Définition de terminé** :
- "Save prediction" avec un nom fait apparaître la ligne en tête de "History" ;
- l'ouvrir affiche exactement les mêmes résultats et le numéro de version ;
- un autre utilisateur qui colle la même adresse voit "Prediction not found." ;
- un administrateur non plus ne la voit pas.

### Phase 15 : Robustesse et suite de bout en bout complète
**Objectif** : les cas difficiles se comportent comme prévu.
**Périmètre** :
- toutes les limites de débit ;
- gestion de session expirée (rafraîchissement unique, redirection avec motif, restauration du brouillon) ;
- mode dégradé si Redis est indisponible ;
- messages 503 ;
- en-têtes de sécurité ;
- revue d'accessibilité (clavier, libellés, contraste) ;
- tous les scénarios de `TESTING.md` section 3 présents et verts en local ;
- couverture aux seuils.

**Définition de terminé** :
- `make test-e2e` affiche tous les scénarios en vert ;
- en local, révoquer la session d'un utilisateur en pleine saisie puis modifier un champ affiche "Your session has expired. Please sign in again." et, après reconnexion, le formulaire revient rempli ;
- arrêter Redis affiche "The service is temporarily unavailable..." uniquement au lancement d'un apprentissage, le reste fonctionne.

## Intégrations externes

### Phase 16 : Sentry
**Objectif** : toute erreur est visible et diagnosticable sans lire le code.
**Périmètre** :
- `sentry-sdk` (api, worker) et `@sentry/nextjs` (web) branchés dans les modules d'observabilité ;
- balises `service`, `environment`, `release`, `request_id`, `user.id`, identifiants métier ;
- filtrage des données personnelles ;
- source maps ;
- page d'erreur affichant "Reference: <request_id>" ;
- route de test d'erreur disponible hors production uniquement.

**Définition de terminé** :
- depuis l'environnement local configuré avec un DSN de test, déclencher l'erreur de test fait apparaître dans Sentry un événement avec la route, l'identifiant de requête (le même que celui affiché à l'écran), l'identifiant utilisateur et la version ;
- une erreur provoquée dans le worker apparaît avec l'identifiant de la version du modèle.

### Phase 17 : Infrastructure AWS de staging
**Objectif** : l'application tourne sur AWS avec HTTPS.
**Périmètre** :
- piles CDK `SoroNuaPredict-shared` (ECR) et `SoroNuaPredict-staging` (réseau, ECS, ALB, DNS, certificat, secrets, journaux, alarmes) ;
- pile `SoroNuaPredict-staging-data` (`data_stack.py`) : hôte de données, volume chiffré, DNS privé, sauvegardes (conteneur `db-backup` et AWS Backup), règle d'ALB `/auth/v1/*` ;
- clés de la pile générées dans Secrets Manager (`ENV_SETUP.md` 8.1) ;
- `apply.sh`, `backup.sh`, `restore.sh` ;
- base Upstash staging ;
- premier déploiement manuel documenté (publication des images depuis `dev`, migrations, `cdk deploy`, chargement du jeu de départ, premier administrateur) ;
- tests d'infrastructure.

**Définition de terminé** :
- `https://staging-predict.<DOMAIN_NAME>` affiche l'écran "Sign in" avec un cadenas HTTPS valide ;
- l'administrateur de staging ouvre le lien d'invitation que Claude Code lui transmet (`bootstrap_admin --print-link`, pas encore d'e-mail réel avant la phase 19), définit son mot de passe, se connecte, entraîne et active une version, obtient une prédiction ;
- la console AWS montre, le lendemain matin, une sauvegarde nocturne dans le compartiment de sauvegarde ;
- le pied de page affiche le numéro de version.

### Phase 18 : Pipelines CI/CD
**Objectif** : plus aucune mise en ligne manuelle.
**Périmètre** :
- pile `SoroNuaPredict-cicd` ;
- buildspecs ;
- contrôle `checks` sur les pull requests et `dev` ;
- pipeline staging complet avec Playwright sur staging ;
- pipeline de production créé mais sans environnement cible (phase 20) ;
- statut `checks` rendu obligatoire dans les protections GitHub ;
- notifications ;
- promotion `dev` vers `staging` par pull request.

**Définition de terminé** :
- sur GitHub, chaque pull request affiche un contrôle "checks" vert ou rouge, et le bouton de fusion est bloqué tant qu'il n'est pas vert ;
- une fusion dans `staging` fait changer, quelques minutes plus tard, le numéro de version en pied de page du site de staging ;
- la console CodePipeline montre toutes les étapes vertes, "E2E" compris.

### Phase 19 : E-mails réels (Amazon SES)
**Objectif** : les invitations et réinitialisations arrivent dans de vraies boîtes.
**Périmètre** : vérification du domaine dans SES (DKIM par CDK), adresse `no-reply@<DOMAIN_NAME>`, identifiants SMTP, variables `SMTP_*` du secret `data` de staging puis relance de l'étape Data du pipeline, demande de sortie du "sandbox" SES.
**Définition de terminé** :
- une invitation envoyée depuis staging arrive dans la boîte de réception réelle de l'utilisateur, expéditeur `no-reply@<DOMAIN_NAME>`, et le lien ouvre "Set your password" sur le site de staging.

### Phase 20 : Mise en production
**Objectif** : l'équipe utilise l'outil.
**Périmètre** :
- pile `SoroNuaPredict-prod` ;
- pile `SoroNuaPredict-prod-data` (hôte de données de production, sauvegardes) et base Upstash de production ;
- SMTP SES en production ;
- secrets de production ;
- compte de fumée ;
- première mise en production par le chemin complet (`staging` vers `main`, approbation par e-mail, déploiement, tests de fumée) ;
- chargement du jeu de départ, premier administrateur ;
- exercice de retour arrière applicatif (`CI_CD.md` 6.1) réalisé une fois puis annulé ;
- exercice de restauration complète de la base de staging depuis la sauvegarde de la nuit (`CI_CD.md` 6.2), avec vérification des nombres de lignes ;
- README final.

**Définition de terminé** :
- l'utilisateur reçoit l'e-mail d'approbation, clique pour approuver, puis voit `https://predict.<DOMAIN_NAME>` afficher "Sign in" ;
- il reçoit son invitation d'administrateur, se connecte, entraîne et active une version, invite un collègue ;
- le collègue obtient une prédiction complète ;
- la page "Model" affiche la version active.
