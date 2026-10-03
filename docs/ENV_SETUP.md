# ENV_SETUP.md : Variables d'environnement et installation

Document de référence n°8 sur 13.
**Aucune valeur réelle dans ce document ni dans le dépôt.** Les fichiers `.env.example` contiennent les noms et des valeurs factices explicites (`change-me`, `http://localhost:...`).

Tous les composants tournent dans des conteneurs Docker (voir `ARCHITECTURE.md` 1.1). Les variables ci-dessous sont donc toutes des variables de conteneurs.

---

## 1. Où vivent les valeurs

| Environnement | Stockage des valeurs |
|---|---|
| local | `.env` à la racine et `deploy/supabase/.env` (ignorés par Git), générés par `make env-local` : `.env.example` complétés et clés générées localement par `deploy/supabase/generate_keys.py`. Depuis la phase 1, `make env-local` crée aussi `deploy/supabase/.env` (copie de son `.env.example`) puis lance `generate_keys.py --env local`, qui remplace les `change-me` par des secrets générés et recopie `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` et `POSTGRES_PASSWORD` dans le `.env` racine (sans toucher au reste du fichier ; section 7.5). La source unique des secrets de la pile reste `deploy/supabase/.env` |
| staging, production : conteneurs de l'application | AWS Secrets Manager, secret JSON `soronua-predict/<env>/app`, injecté dans les tâches ECS |
| staging, production : construction de l'image web | AWS Secrets Manager, secret JSON `soronua-predict/<env>/web-build`, lu par CodeBuild |
| staging, production : pile Supabase | AWS Secrets Manager, secret JSON `soronua-predict/<env>/data`, lu sur l'hôte de données au moment du déploiement pour produire son `.env` (permissions 600, jamais copié ailleurs) |
| CI/CD (pipelines) | AWS Secrets Manager, secret JSON `soronua-predict/cicd`, lu par CodeBuild |
| Infrastructure (CDK) | `infra/cdk.json` (valeurs non secrètes uniquement : région, domaine, e-mails de notification, tailles) |

## 2. Variables : conteneurs api et worker (`apps/api`)

Règles de lecture (module `app/config.py`, seul autorisé à lire l'environnement) :
- `APP_ENV` et `SERVICE_NAME` sont **obligatoires** et sans valeur par défaut : s'ils manquent ou sont invalides, le conteneur refuse de démarrer avec un message qui liste les noms des variables fautives, jamais leurs valeurs ;
- une variable présente mais **vide** (`VAR=`) est ignorée, comme si elle était absente : la valeur par défaut s'applique ;
- les autres variables ont une valeur par défaut (`APP_RELEASE=local`, `LOG_LEVEL=INFO`, `SENTRY_DSN` vide, `SENTRY_TRACES_SAMPLE_RATE=0`, `MAX_UPLOAD_BYTES=10485760`) ;
- depuis la phase 1, `SUPABASE_URL` vaut par défaut `http://supabase-kong:8000` (elle doit commencer par `http://` ou `https://` et ne pas finir par `/`), et `SUPABASE_ANON_KEY` et `SUPABASE_SERVICE_ROLE_KEY` sont vides par défaut. Ces deux clés sont lues comme secrets (jamais affichées dans un `repr`, un journal ou un message d'erreur). Clé publique vide : `/api/ready` répond 503 (échec fermé) au lieu d'empêcher le démarrage ; un client Supabase refuse de se construire avec une clé vide ;
- une variable n'est ajoutée à `config.py` que par la phase qui l'utilise pour la première fois (voir la table de la section 7.5).

| Nom | Rôle | Où l'obtenir |
|---|---|---|
| `APP_ENV` | `local`, `staging` ou `production` ; active les comportements propres à l'environnement (OpenAPI désactivé en production, commandes de test refusées en production). | Fixé par environnement. |
| `APP_RELEASE` | Identifiant de version (SHA Git court) affiché dans `/api/health` et envoyé à Sentry. | Injecté par le pipeline ; `local` en local. |
| `LOG_LEVEL` | Niveau de journalisation (`INFO` par défaut, `DEBUG` en local). | Fixé par environnement. |
| `SERVICE_NAME` | `api` ou `worker`, balise Sentry et journaux. | Fixé dans la définition de tâche et `docker-compose.yml`. |
| `SUPABASE_URL` | Adresse **interne** de la passerelle Kong. | Local : `http://supabase-kong:8000` (réseau Compose). AWS : `http://data.<env>.internal:8000`. |
| `SUPABASE_ANON_KEY` | Clé publique (jeton `anon`), utilisée avec le jeton de l'utilisateur. | Générée par `generate_keys.py`, identique à `ANON_KEY` du secret `data`. |
| `SUPABASE_SERVICE_ROLE_KEY` | Clé de service, réservée aux modules listés dans `ARCHITECTURE.md` 2.5. **Jamais dans l'image web.** | Générée par `generate_keys.py`, identique à `SERVICE_ROLE_KEY` du secret `data`. |
| `SUPABASE_JWT_SECRET` | Secret HS256 servant à vérifier les jetons des utilisateurs (phase 2). Vide : toute vérification de jeton échoue en erreur de configuration (500), jamais en 401. Reçu par `api` seulement (garde G5). | Identique à `JWT_SECRET` du secret `data`. Local : recopié par `make env-local` depuis `deploy/supabase/.env`. |
| `SUPABASE_JWT_ISSUER` | Émetteur attendu dans les jetons (phase 2). | `<SUPABASE_PUBLIC_URL>/auth/v1`, identique à `GOTRUE_JWT_ISSUER` de la pile (local : `http://localhost:54321/auth/v1` ; un test unitaire vérifie l'égalité des deux exemples). |
| `REDIS_URL` | Connexion Redis (`redis://` en local, `rediss://` Upstash ailleurs) ; contient un mot de passe sur Upstash (`SecretStr`, jamais journalisée). | Local : `redis://redis:6379/0`. Distant : console Upstash, base, "Connect", URL TLS. |
| `SENTRY_DSN` | DSN du projet Sentry `soronua-predict-api` (api) ou `soronua-predict-worker` (worker). Lue par `config.py` dès la phase 0 ; sans effet avant la phase 16. | Sentry, Settings, Projects, Client Keys. Vide en local (Sentry désactivé). |
| `SENTRY_TRACES_SAMPLE_RATE` | Part des requêtes tracées (0.1 en production, 1.0 en staging, 0 en local). Lue par `config.py` dès la phase 0 ; sans effet avant la phase 16. | Fixé par environnement. |
| `WEB_APP_URL` | URL publique de l'interface, sans barre finale ; redirection des e-mails d'invitation et origine du lien affiché par `bootstrap_admin --print-link`. Doit être égale à `SITE_URL` de la pile (testé). | Local : `http://localhost:3000`. Distant : `https://staging-predict.<DOMAIN_NAME>` ou `https://predict.<DOMAIN_NAME>`. |
| `STORAGE_BUCKET_UPLOADS` | `dataset-uploads`. | Fixe. |
| `STORAGE_BUCKET_ARTIFACTS` | `model-artifacts`. | Fixe. |
| `MAX_UPLOAD_BYTES` | 10485760. Lue par `config.py` dès la phase 0 : le garde-fou de taille des requêtes (413) en dérive (fichier multipart : cette valeur plus 64 Kio ; JSON : 64 Kio). | Fixe. |
| `MODEL_POINTER_REFRESH_SECONDS` | 30. | Fixe. |
| `WORKER_HEARTBEAT_PATH` | `/tmp/worker-heartbeat`. | Fixe. |
| `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_FULL_NAME` | Premier administrateur (commande `bootstrap_admin`). Déclarées dans `Settings` mais livrées au seul service `cli` (pas à `api` ni au worker, D-072). | Fourni par l'utilisateur une fois par environnement (en local : `make bootstrap-admin FIRST_ADMIN_EMAIL=... FIRST_ADMIN_FULL_NAME="..."`). |
| `SEED_CSV_PATH` | `/app/data/seed/digital_marketing_campaign_dataset.csv` (dans l'image). | Fixe. |

## 3. Variables : conteneur web (`apps/web`)

Les variables `NEXT_PUBLIC_*` sont incluses dans le code envoyé au navigateur : elles ne contiennent **jamais** de secret. Elles sont fixées à la construction de l'image (une image web par environnement).

Lecture par `src/lib/env.ts` (validation Zod ; une variable vide est traitée comme absente). En phase 0, seules `NEXT_PUBLIC_APP_ENV` et `NEXT_PUBLIC_APP_RELEASE` sont obligatoires : sans elles, la construction de l'image de production échoue avec un message qui liste les noms des variables, jamais leurs valeurs. Les variables Supabase et Sentry sont facultatives jusqu'aux phases 2 et 16, où elles deviennent obligatoires. `API_PROXY_TARGET` est lue par `next.config.ts` (les réécritures sont évaluées avant l'application).

| Nom | Rôle | Où l'obtenir |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Adresse de base de l'authentification **vue par le serveur web** (middleware, `/auth/confirm`). Le navigateur, lui, utilise toujours sa propre origine (`/auth/v1/*`, D-069). | Local : `http://supabase-kong:8000`. Distant : l'URL du site elle-même (l'ALB transmet `/auth/v1/*` à Kong). |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Clé publique (seule valeur Supabase que `web` reçoit). | Comme `SUPABASE_ANON_KEY` (Compose la recopie). |
| `AUTH_PROXY_TARGET` | **Local uniquement** (D-069) : cible du relais Next `/auth/v1/*`, comme `API_PROXY_TARGET`. Sur AWS, l'ALB route `/auth/v1/*`. | Local : `http://supabase-kong:8000`. |
| `NEXT_PUBLIC_APP_ENV` | `local`, `staging`, `production`. | Fixé par environnement. |
| `NEXT_PUBLIC_APP_RELEASE` | SHA Git court, affiché en pied de page. | Injecté par le pipeline. |
| `NEXT_PUBLIC_SENTRY_DSN` | DSN du projet Sentry `soronua-predict-web`. | Sentry. Vide en local. |
| `SENTRY_AUTH_TOKEN` | Envoi des source maps à la construction (jamais dans l'image finale). | Sentry, Settings, Auth Tokens (`project:releases`, `org:read`). |
| `SENTRY_ORG` / `SENTRY_PROJECT` | Organisation Sentry / `soronua-predict-web`. | Sentry. |
| `API_PROXY_TARGET` | **Local uniquement** : cible des réécritures `/api/*` du serveur Next.js (`http://api:8000`). Absente sur AWS (l'ALB route `/api/*`). | Fixe. |

## 4. Variables : pile Supabase (`deploy/supabase/.env`, secret `soronua-predict/<env>/data`)

En phase 1, cette section est lue par `deploy/supabase/docker-compose.yml` (directive `include` avec `env_file: deploy/supabase/.env`, voir 7.5). Les variables `GOTRUE_*`, `PGRST_*`, `KONG_*` et les autres réglages fixes des services sont écrits en clair dans ce fichier Compose : seules les variables ci-dessous changent d'un environnement à l'autre. Un secret vide fait échouer `docker compose` avec un message qui renvoie à `make env-local` (`${VAR:?...}`).

| Nom | Rôle | Où l'obtenir |
|---|---|---|
| `POSTGRES_PASSWORD` | Mot de passe du superutilisateur Postgres et des rôles internes. Uniquement des lettres et des chiffres (il est intégré dans une URL de connexion). | Généré (40 caractères aléatoires) par `generate_keys.py` ; recopié dans le `.env` racine (services `toolbox` et `pgtap`). |
| `JWT_SECRET` | Secret de signature des jetons (64 caractères aléatoires minimum). | Généré par `generate_keys.py`. |
| `ANON_KEY` / `SERVICE_ROLE_KEY` | Jetons `anon` et `service_role` signés avec `JWT_SECRET`, sans expiration courte (10 ans). | Générés par `generate_keys.py`. |
| `PG_META_CRYPTO_KEY` | Clé de chiffrement de `supabase-meta` et de Studio (32 caractères). Local seulement (profil `local`). | Générée par `generate_keys.py`. |
| `S3_PROTOCOL_ACCESS_KEY_ID` / `S3_PROTOCOL_ACCESS_KEY_SECRET` | Identifiants exigés par l'image `supabase-storage` (protocole S3 interne, jamais publié). | Générés par `generate_keys.py`. |
| `SUPABASE_PUBLIC_URL` | URL publique de la pile. | Local : `http://localhost:54321`. Distant : URL du site. |
| `API_EXTERNAL_URL` | Base des liens produits par l'authentification. | Comme `SUPABASE_PUBLIC_URL`. |
| `SITE_URL` | URL de l'interface. | Comme `WEB_APP_URL`. |
| `ADDITIONAL_REDIRECT_URLS` | `<SITE_URL>/auth/confirm`. | Dérivé. |
| `GOTRUE_DISABLE_SIGNUP` | `true` : pas d'inscription libre. | Fixe. |
| `GOTRUE_JWT_EXP` | `3600`. | Fixe. |
| `GOTRUE_JWT_DEFAULT_GROUP_NAME` | `authenticated` : valeur du `role` des jetons des utilisateurs (D-066). | Fixe. |
| `GOTRUE_JWT_ISSUER` | `<SUPABASE_PUBLIC_URL>/auth/v1`. | Dérivé. |
| `GOTRUE_MAILER_TEMPLATES_INVITE` / `GOTRUE_MAILER_TEMPLATES_RECOVERY` | **Phase 2** (D-053, D-068). URL des gabarits d'e-mails servis par `web` (obligatoires depuis la phase 2 ; `web` doit être démarré à l'envoi). Les objets sont fixés dans Compose : « You have been invited to Soro Nua Campaign Predictor » et « Reset your Soro Nua Campaign Predictor password ». | `<SITE_URL>/auth-templates/invite.html` et `recovery.html` (en local : `http://web:3000/...`). |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_ADMIN_EMAIL` / `SMTP_SENDER_NAME` | Envoi des e-mails. | Local : `mailpit`, port 1025, sans identifiants. Distant : Amazon SES (section 7.4), expéditeur `no-reply@<DOMAIN_NAME>`, nom "Soro Nua Campaign Predictor". |
| `STORAGE_FILE_SIZE_LIMIT` | 10485760. | Fixe. |
| `KONG_HTTP_PORT` | Port exposé par Kong (`54321` en local, `8000` sur AWS). | Fixe. |
| `KONG_BIND_ADDRESS` | Adresse sur laquelle Kong publie son port (`127.0.0.1` en local, `0.0.0.0` sur AWS où le groupe de sécurité limite l'accès à l'ALB). | Fixe. |
| `STUDIO_HOST_PORT` | Port de Studio sur la machine (`54323`), local uniquement (profil `local`), publié sur `127.0.0.1`. | Fixe. |
| `POSTGRES_PORT` | Port **interne** de Postgres (`5432`) dans le conteneur. Postgres n'est **jamais publié** sur la machine (D-051) ; `make db-shell` ouvre `psql` dans le conteneur. | Fixe. |
| `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD` | **Supprimées en phase 1** (D-052) : Studio est local, joignable seulement depuis `127.0.0.1` et sans authentification ; il n'est pas déployé ailleurs. | n/a |
| `BACKUP_BUCKET` | Phase 17. Compartiment S3 des sauvegardes (`soronua-predict-<env>-backups`). Absent en local. | Sortie CDK. |
| `BACKUP_SCHEDULE` | Phase 17. Heure de la sauvegarde nocturne (`0 2 * * *`, UTC). | Fixe. |

## 5. Variables : tests de bout en bout (conteneur Playwright)

| Nom | Rôle | Où l'obtenir |
|---|---|---|
| `E2E_BASE_URL` | URL testée. | `http://web:3000` (local, réseau Compose) ou URL staging / production. |
| `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` | Administrateur de test. | Créé par `python -m app.cli.create_test_users` (local et staging uniquement), valeurs dans `soronua-predict/cicd`. |
| `E2E_ADMIN2_EMAIL` / `E2E_ADMIN2_PASSWORD` | Second administrateur (tests de concurrence). | Idem. |
| `E2E_MARKETER_A_EMAIL` / `E2E_MARKETER_A_PASSWORD` | Utilisateur A (isolation). | Idem. |
| `E2E_MARKETER_B_EMAIL` / `E2E_MARKETER_B_PASSWORD` | Utilisateur B (isolation). | Idem. |
| `E2E_SMOKE_EMAIL` / `E2E_SMOKE_PASSWORD` | Compte `marketer` dédié aux tests de fumée en production (lecture et simulation uniquement). | Invité une fois en production ; valeurs dans `soronua-predict/cicd`. |
| `E2E_RESET_EMAIL` / `E2E_RESET_PASSWORD` | Compte dédié au scénario de réinitialisation du mot de passe (phase 2, D-074). | Idem. |
| `E2E_INVITEE_EMAIL` | Adresse invitée par `create_test_users` pour le scénario d'invitation (phase 2). | `e2e-invitee@example.test` en local. |
| `E2E_MAILPIT_URL` | Lecture des e-mails de test, **local uniquement**. | `http://mailpit:8025`. |
| ~~`E2E_SUPABASE_SERVICE_ROLE_KEY`~~ | **Supprimée en phase 2** (SECURITY_NOTES section 5, CLAUDE 4.2) : aucune clé de service dans le conteneur Playwright. Les comptes sont préparés par le service `cli` (`make test-users`) avant les tests. | n/a |

En local, les mots de passe `E2E_*_PASSWORD` sont **générés** par `make env-local` dans `.env` (24 caractères alphanumériques, jamais dans un fichier versionné) ; les adresses ont des valeurs par défaut en `@example.test`. Le service `cli` (profil `tools`, sans port) les reçoit pour `create_test_users` ; `e2e` les reçoit pour se connecter.

## 6. Variables : CI/CD et infrastructure

| Nom | Rôle | Où l'obtenir |
|---|---|---|
| `AWS_ACCOUNT_ID` | Compte AWS cible. | Console AWS. |
| `AWS_REGION` | `eu-west-3`. | Fixe. |
| `DOMAIN_NAME` | Domaine racine sous lequel sont créés `staging-predict.` et `predict.`. | Fourni par Soro Nua (section 8.2). |
| `HOSTED_ZONE_ID` | Zone Route 53 publique du domaine ou du sous-domaine délégué. | Route 53. |
| `GITHUB_CONNECTION_ARN` | Connexion CodeConnections vers le dépôt. | Console Developer Tools, Connections. |
| `GITHUB_REPOSITORY` | `<propriétaire>/soronua-campaign-predictor`. | GitHub. |
| `DATA_HOST_INSTANCE_ID_STAGING` / `DATA_HOST_INSTANCE_ID_PROD` | Cible des commandes SSM de mise à jour de la pile Supabase. | Sorties CDK (lues automatiquement par le pipeline). |
| `DATABASE_URL_STAGING` / `DATABASE_URL_PROD` | Connexion Postgres privée utilisée par `supabase db push --db-url` depuis CodeBuild (dans le VPC). | Construite à partir de `POSTGRES_PASSWORD` et de `data.<env>.internal:5432`, stockée dans `soronua-predict/cicd`. |
| `APPROVAL_NOTIFICATION_EMAIL` | Destinataire des demandes d'approbation de mise en production (l'utilisateur). | Fourni par l'utilisateur. |
| `ALARM_NOTIFICATION_EMAIL` | Destinataire des alarmes. | Fourni par l'utilisateur. |
| `SENTRY_AUTH_TOKEN` / `SENTRY_ORG` | Versions Sentry dans le pipeline. | Sentry. |

## 7. Installation locale (exécutée par Claude Code)

### 7.1 Prérequis
- Git 2.40 ou plus.
- Docker Desktop (ou Docker Engine) avec Docker Compose 2.20 ou plus (directive `include`, utilisée à partir de la phase 1), 8 Go de mémoire alloués au minimum.
- GNU Make (la version 3.81 livrée avec macOS suffit : le `Makefile` y est compatible).
- GitHub CLI (`gh`), pour les pull requests.
- Rien d'autre n'est installé sur la machine : Python, Node.js, la Supabase CLI, Playwright et les outils de contrôle s'exécutent dans des conteneurs, appelés par le `Makefile` :
  - les contrôles Python (formatage, lint, types, tests, audit, cohérence du verrou `uv`) dans l'image de développement `api`, ceux du web (formatage, lint, types, tests, audit) dans l'image de développement `web`, Playwright dans le service `e2e` ;
  - l'image `soronua-predict-toolbox` (construite depuis `tools/Dockerfile`) porte le reste : `uv lock`, `gitleaks`, `pre-commit`, Supabase CLI, AWS CLI, CDK, `make toolbox-versions`.

### 7.2 Étapes

```bash
git clone git@github.com:<propriétaire>/soronua-campaign-predictor.git
cd soronua-campaign-predictor
git checkout dev

make env-local       # crée .env et deploy/supabase/.env, génère les clés locales
make build           # construit toutes les images (web, api, db-backup, toolbox) et tire les images figées de la pile
make up              # démarre toute la pile : Supabase, redis, mailpit, api, worker, web, puis applique les migrations
make db-reset        # recrée les volumes de la base locale et du stockage et applique toutes les migrations
make seed            # charge le jeu de départ (8 000 lignes)
make bootstrap-admin FIRST_ADMIN_EMAIL=admin@example.test FIRST_ADMIN_FULL_NAME="Local Admin"
make test-users      # crée ou réinitialise les comptes de test Playwright (service cli ; refusé en production)
```

Puis :
- interface : `http://localhost:3000` ;
- API : `http://localhost:8000/api/health` ;
- passerelle Supabase : `http://localhost:54321` ;
- Postgres : **aucun port publié** (D-051) ; `make db-shell` ouvre `psql` dans le conteneur `supabase-db` ;
- Supabase Studio : `http://localhost:54323` (local seulement, joignable depuis `127.0.0.1` uniquement, sans identifiants, D-052) ;
- e-mails locaux : `http://localhost:54324` (Mailpit).

Le premier administrateur définit son mot de passe via le lien reçu dans Mailpit.

**Ce que démarrent `make build` et `make up` selon la phase.** Les commentaires du bloc ci-dessus décrivent la pile complète (état final). Tant que les phases suivantes ne sont pas livrées, les commandes font moins :

| Phase | `make env-local` | `make build` | `make up` | Commandes disponibles |
|---|---|---|---|---|
| 0 | crée `.env` depuis `.env.example` | images `api` (cible `dev`), `web` (cible `dev`), `e2e` et `toolbox` | `redis`, `api`, `web`, attend leur état sain ; adresses `http://localhost:3000` (web) et `http://localhost:8000/api/health` (API) | `make help` les liste ; `make db-reset`, `seed`, `bootstrap-admin`, `test-users` n'existent pas encore |
| 1 (actuelle) | crée aussi `deploy/supabase/.env`, génère les clés locales et les recopie dans `.env` | + tire les images figées de la pile Supabase, de `mailpit` et de `pg_prove` | + pile Supabase (`include`) et `mailpit`, attend leur état sain, puis applique les migrations (`make db-migrate`) ; ports `54321` (Kong), `54323` (Studio) et `54324` (Mailpit), tous sur `127.0.0.1`, aucun port Postgres | `make db-reset`, `make db-migrate`, `make db-new-migration`, `make db-shell`, `make pull`, `make test-db` (pgTAP réel) |
| 2 | ajoute `SUPABASE_JWT_SECRET` et génère les cinq `E2E_*_PASSWORD` dans `.env` ; ajoute à `deploy/supabase/.env` les variables nouvelles de l'exemple (`GOTRUE_MAILER_TEMPLATES_*`) | + service `cli` (même image que `api`) | + `web` sert `/auth-templates/*` et relaie `/auth/v1/*` ; gotrue lit les gabarits depuis `web` | `make bootstrap-admin`, `make test-users` ; `make test-e2e` réinitialise la base locale |
| 4 | inchangé | l'image `api` embarque le jeu de départ | inchangé | `make seed` |
| 6 | inchangé | inchangé | + `worker` | n/a |
| 17 | inchangé | + image `db-backup` | inchangé | n/a |

Le conteneur `toolbox` (profil `tools`) et le service `e2e` (profil `e2e`) ne sont jamais lancés par `make up` : le `Makefile` les appelle à la demande.

### 7.3 Composition locale
- Cette liste décrit l'état final. **Phase 0** : `docker-compose.yml` ne contenait que `redis`, `api` et `web` ainsi que `toolbox` (profil `tools`) et `e2e` (profil `e2e`). **Phase 1** : il inclut `deploy/supabase/docker-compose.yml` et ajoute `mailpit` et le service `pgtap` (profil `tools`, image `pg_prove` figée, D-048) ; il n'y a pas de `worker` avant la phase 6. Le nom du projet Compose est fixé à `soronua-predict` et aucun conteneur n'a de nom imposé (les conteneurs d'autres projets de la machine ne sont jamais touchés).
- `docker-compose.yml` à la racine inclut `deploy/supabase/docker-compose.yml` (directive `include`, phase 1) et ajoute :
  - `redis` ;
  - `mailpit` ;
  - `api` : cible `dev`, `uvicorn --reload`, code monté en volume ;
  - `worker` ;
  - `web` : cible `dev`, `next dev`.
- Un seul réseau Compose : les conteneurs se joignent par leur nom (`supabase-kong`, `redis`, `api`, `web`).
- Les données locales vivent dans des volumes nommés (`supabase-db-data`, `supabase-db-config`, `supabase-storage-data`), supprimés par `make db-reset` (filtrés par l'étiquette du projet Compose `soronua-predict`, jamais par nom global ni par `docker volume prune`) et par `make clean`.
- `supabase-meta` et `supabase-studio` sont rattachés au profil Compose `local` : ils ne sont jamais lancés sur AWS. `make up` les démarre (`--profile local`) ; `PROFILES` du `Makefile` contient aussi `local` pour que `build`, `pull` et `clean` les voient.
- Deux fichiers d'interpolation : le `docker-compose.yml` racine lit le `.env` racine, le fichier inclus lit `deploy/supabase/.env`. Si `deploy/supabase/.env` manque, **toute** commande `docker compose` échoue : `make env-local` doit donc précéder tout autre appel sur un clone neuf (`build`, `up`, `lint`, `pre-commit` et `db-reset` en dépendent).

### 7.4 Commandes courantes

| Commande | Effet |
|---|---|
| `make env-local` | Crée `.env` depuis `.env.example` et `deploy/supabase/.env` depuis son `.env.example` (jamais d'écrasement ; les variables ajoutées plus tard à l'exemple sont ajoutées au fichier existant), puis exécute `generate_keys.py --env local` dans le `toolbox` : seules les valeurs vides ou `change-me` sont générées (idempotent), les secrets ne sont jamais affichés. Depuis la phase 2 il recopie aussi `JWT_SECRET` en `SUPABASE_JWT_SECRET` dans `.env` et génère les cinq `E2E_*_PASSWORD`. |
| `make bootstrap-admin FIRST_ADMIN_EMAIL=... FIRST_ADMIN_FULL_NAME="..." [PRINT_LINK=1]` | Crée (ou ré-invite) le premier administrateur dans le service `cli` (`python -m app.cli.bootstrap_admin`). `PRINT_LINK=1` affiche le lien à usage unique au lieu d'envoyer l'e-mail. Les variables passent par l'environnement, jamais en argument. |
| `make test-users` | Crée ou réinitialise les comptes de test Playwright dans le service `cli` (`python -m app.cli.create_test_users`) ; refusé si `APP_ENV=production`. |
| `make check` | Tous les contrôles (voir `CONVENTIONS.md` section 2), dans des conteneurs. |
| `make test-unit` / `make test-integration` / `make test-db` / `make test-e2e` | Tests par niveau. **`make test-e2e` réinitialise la base locale** de ce projet (`up`, `db-reset`, `test-users`, puis Playwright, D-074). `make test-unit` lance aussi les tests de `generate_keys.py` et des fichiers de la pile (`python -m unittest discover -s deploy/supabase/tests`). `make test-db` applique les migrations, crée l'extension pgTAP dans la base **locale** (jamais par une migration), puis lance `pg_prove` (service `pgtap`) sur `supabase/tests/database/*.test.sql` ; il échoue s'il n'y a aucun test (`PGPROVE_FLAGS=--verbose` pour le détail). `make test-integration` suppose la pile démarrée (`make up`) et échoue franchement si elle ne répond pas. |
| `make guards` | En plus des contrôles de phase 0, lit la configuration Compose résolue (sans l'afficher, elle contient des secrets) et vérifie : images figées par digest, aucun secret Supabase dans `web`, aucun port publié hors `127.0.0.1`, aucun port publié par `supabase-db`, `-rest`, `-storage`, `-meta`, `-auth`. |
| `make hooks` | Installe les crochets Git (`pre-commit`, `commit-msg`) ; rien n'est installé sur la machine. |
| `make audit` / `make secrets` | Audit des dépendances / analyse `gitleaks` de l'historique. |
| `make api-types` | Régénère `apps/web/src/lib/api/types.gen.ts`. |
| `make db-new-migration name=<description>` | Crée un fichier de migration vide horodaté (phase 1). |
| `make db-migrate` | Applique les migrations en attente à la base en marche (`supabase migration up --db-url "$DATABASE_URL"` dans le `toolbox`) ; idempotent. `make up` l'appelle après le démarrage. |
| `make db-reset` | Supprime les volumes de la base et du stockage de ce projet, redémarre la pile et rejoue toutes les migrations. Ne touche à aucun conteneur ni volume d'un autre projet. Après `generate_keys.py --rotate`, `make db-reset` est obligatoire (le mot de passe est figé dans le volume de données). |
| `make db-shell` | `psql` dans le conteneur `supabase-db` (aucun port Postgres n'est publié). |
| `make pull` | Tire les images figées qui ne sont pas construites ici (pile Supabase, Mailpit, `pg_prove`). |
| `make logs` | Journaux des conteneurs. |
| `make down` / `make clean` | Arrête la pile / l'arrête et supprime ses volumes. |

### 7.5 Variables de composition (locales)

Ces variables ne sont lues ni par l'API ni par l'interface : elles servent uniquement à `docker-compose.yml` et au `Makefile`, en local. Elles n'existent ni sur AWS, ni dans les secrets Secrets Manager.

| Nom | Rôle | Valeur par défaut |
|---|---|---|
| `WEB_HOST_PORT` | Port de la machine sur lequel l'interface est publiée (`127.0.0.1:<port>`). À modifier seulement si le port est déjà pris par un autre programme (par exemple `3001`) ; les tests Playwright, eux, joignent toujours `http://web:3000` dans le réseau Compose. | `3000` |
| `API_HOST_PORT` | Port de la machine sur lequel l'API est publiée (`127.0.0.1:<port>`). | `8000` |
| `NOTEBOOKS_HOST_PORT` | Port de la machine sur lequel JupyterLab est publié (`127.0.0.1:<port>`), seulement avec `make notebooks-lab` (D-044). Facultatif : valeur par défaut dans `docker-compose.yml`, absent de `.env.example`. | `8888` |
| `MAILPIT_HOST_PORT` | Port de la machine de l'interface Mailpit (`127.0.0.1:<port>`) ; le port SMTP 1025 reste interne. Lue dans le `.env` **racine** (service racine `mailpit`). | `54324` |
| `KONG_HTTP_PORT` | Port de la machine de la passerelle Kong. Lue dans `deploy/supabase/.env`. En le changeant, `SUPABASE_PUBLIC_URL` et `API_EXTERNAL_URL` (donc l'émetteur des jetons) doivent suivre. | `54321` |
| `KONG_BIND_ADDRESS` | Adresse de publication de Kong. Lue dans `deploy/supabase/.env`. | `127.0.0.1` |
| `STUDIO_HOST_PORT` | Port de la machine de Studio (`127.0.0.1:<port>`). Lue dans `deploy/supabase/.env`. | `54323` |
| `POSTGRES_PASSWORD` | Lue par les services racine `toolbox` (`DATABASE_URL` pour `supabase migration up --db-url`, sans mot de passe dans la ligne de commande visible) et `pgtap` ; synchronisée par `generate_keys.py` depuis `deploy/supabase/.env`. | généré |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Reçues par le seul service `api` (liste `environment:`). Les deux clés sont synchronisées par `generate_keys.py` depuis `ANON_KEY` et `SERVICE_ROLE_KEY`. Jamais dans `web` ni `e2e`. | `http://supabase-kong:8000` ; clés générées |

Règles :
- **`.env.example` à la racine** est la source de la composition locale. `make env-local` le copie en `.env` (ignoré par Git) et ne l'écrase jamais ; `make up` l'appelle d'abord. Il contient `WEB_HOST_PORT`, `API_HOST_PORT`, `MAILPIT_HOST_PORT`, `APP_ENV`, `APP_RELEASE`, `LOG_LEVEL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `POSTGRES_PASSWORD`, `NEXT_PUBLIC_APP_ENV`, `NEXT_PUBLIC_APP_RELEASE` et `API_PROXY_TARGET`, avec des valeurs factices ou locales (`change-me` pour les trois clés et le mot de passe, remplacés par `make env-local`), jamais de secret.
- **`deploy/supabase/.env.example`** est la source de la pile Supabase locale : `make env-local` le copie en `deploy/supabase/.env` (ignoré par Git, droits 600) puis `generate_keys.py` y remplace les `change-me`. Chaque variable n'a qu'une source : les ports de Kong et de Studio sont dans ce fichier, pas dans le `.env` racine. Le hook de commit refuse tout `.env` réel.
- **`apps/api/.env.example` et `apps/web/.env.example`** sont une documentation par composant (sous-ensembles des variables des sections 2 et 3). Ils ne servent pas à la composition. Ne jamais créer `apps/web/.env` : le dossier est monté dans le conteneur et Next.js le lirait.
- **Listes explicites, jamais `env_file`** : chaque service de `docker-compose.yml` reçoit uniquement les variables nommées dans sa section `environment:`. Le `.env` complet n'est jamais transmis en bloc, afin que la clé de service Supabase (à partir de la phase 1) n'atteigne jamais le conteneur `web`. Tout ce qui n'est pas listé prend sa valeur par défaut dans `config.py` (en phase 0 : `SENTRY_DSN` vide, `SENTRY_TRACES_SAMPLE_RATE=0`, `MAX_UPLOAD_BYTES=10485760`).
- **Valeurs vides ignorées** : `VAR=` équivaut à une variable absente (API : `env_ignore_empty` ; web : `env.ts`). Compose substitue `${VAR:-défaut}` de la même façon.
- **`APP_ENV` et `SERVICE_NAME` obligatoires** pour l'API (section 2). Compose fixe `SERVICE_NAME=api` ; `APP_ENV` vaut `local` par défaut.
- Si `WEB_HOST_PORT` est modifié, utiliser ce port dans le navigateur (`http://localhost:<port>`) ; l'adresse `http://localhost:3000` citée par `ROADMAP.md` suppose le port par défaut libre.

**Phase d'introduction des variables.** Une variable est ajoutée, dans le même commit, à `config.py` ou `env.ts`, au `.env.example` concerné et à ce document, par la première phase qui l'utilise ; avant cela, elle n'est pas lue (et un nom inconnu présent dans l'environnement est ignoré).

| Phase | Variables introduites |
|---|---|
| 0 | API : `APP_ENV`, `SERVICE_NAME`, `APP_RELEASE`, `LOG_LEVEL`, `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `MAX_UPLOAD_BYTES`. Web : `NEXT_PUBLIC_APP_ENV`, `NEXT_PUBLIC_APP_RELEASE` (obligatoires), `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_SENTRY_DSN` (facultatives), `API_PROXY_TARGET`. Composition : `WEB_HOST_PORT`, `API_HOST_PORT`. Tests : `E2E_BASE_URL`. |
| 1 | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (api uniquement, jamais web) ; la section 4 **sauf** `GOTRUE_MAILER_TEMPLATES_*` (phase 2, D-053), `BACKUP_*` (phase 17) et `DASHBOARD_*` (supprimées, D-052) : pile Supabase, dont `SMTP_*` vers Mailpit, `KONG_BIND_ADDRESS`, `STUDIO_HOST_PORT`, `PG_META_CRYPTO_KEY`, `S3_PROTOCOL_ACCESS_KEY_*` ; `deploy/supabase/.env` ; composition : `MAILPIT_HOST_PORT`, `POSTGRES_PASSWORD`. |
| 2 | `SUPABASE_JWT_SECRET`, `SUPABASE_JWT_ISSUER`, `REDIS_URL` (cache de profil), `WEB_APP_URL`, `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_FULL_NAME`, `GOTRUE_MAILER_TEMPLATES_INVITE` et `_RECOVERY` ; `NEXT_PUBLIC_SUPABASE_URL` et `NEXT_PUBLIC_SUPABASE_ANON_KEY` deviennent obligatoires ; `AUTH_PROXY_TARGET` ; `E2E_ADMIN_*`, `E2E_ADMIN2_*`, `E2E_MARKETER_A_*`, `E2E_MARKETER_B_*`, `E2E_RESET_*`, `E2E_INVITEE_EMAIL`, `E2E_MAILPIT_URL` (pas de clé de service dans `e2e`). |
| 4 | `STORAGE_BUCKET_UPLOADS`, `SEED_CSV_PATH`. |
| 6 | `STORAGE_BUCKET_ARTIFACTS`, `WORKER_HEARTBEAT_PATH` ; `SERVICE_NAME=worker` est utilisé. |
| 8 | `MODEL_POINTER_REFRESH_SECONDS`. |
| 16 | `NEXT_PUBLIC_SENTRY_DSN` et `SENTRY_DSN` deviennent utilisées ; `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`. |
| 17 | Section 6 (`AWS_ACCOUNT_ID`, `AWS_REGION`, `DOMAIN_NAME`, `HOSTED_ZONE_ID`, `GITHUB_*`, `DATA_HOST_INSTANCE_ID_*`, `DATABASE_URL_*`, `ALARM_NOTIFICATION_EMAIL`), `BACKUP_*`, secrets Secrets Manager et base Upstash (`REDIS_URL` en `rediss://`). |
| 18 | `APPROVAL_NOTIFICATION_EMAIL`. |
| 19 | `SMTP_*` d'Amazon SES dans le secret `data` de staging. |
| 20 | `E2E_SMOKE_EMAIL`, `E2E_SMOKE_PASSWORD`. |

Cette table suit `ROADMAP.md` ; si une phase déplace l'usage d'une variable, la table est corrigée dans le même commit et la décision consignée dans `docs/decisions.md`.

## 8. Préparation des services externes (une fois, par Claude Code avec les accès fournis par l'utilisateur)

L'utilisateur fournit seulement les accès (comptes, facturation, domaine, e-mails). Tout le reste est fait et documenté par Claude Code.

### 8.1 Pile Supabase (staging et production)
Aucune console en ligne à configurer : la pile est créée par CDK (hôte de données) et le pipeline (`CI_CD.md`).
1. Générer les clés de l'environnement : `python deploy/supabase/generate_keys.py --env <env>`. Le script écrit directement dans le secret `soronua-predict/<env>/data` et n'affiche aucune valeur.
2. Recopier les valeurs communes dans `soronua-predict/<env>/app` et `.../web-build`, avec le même script (option `--sync-app-secrets`).
3. Premier déploiement de la pile : voir `ROADMAP.md` phase 17.

### 8.2 Domaine
- Soro Nua fournit un domaine. S'il est géré hors d'AWS, déléguer un sous-domaine (par exemple `app.<domaine>`) vers une zone Route 53 créée par Claude Code. `DOMAIN_NAME` est alors ce sous-domaine.
- Certificats ACM et enregistrements DNS créés par CDK.

### 8.3 Upstash
- Deux bases Redis `soronua-predict-staging` et `soronua-predict-prod`, région AWS `eu-west-3` si proposée, sinon `eu-central-1`.
- TLS activé.
- Éviction désactivée, pour que la file ne perde jamais d'élément.

### 8.4 Amazon SES
1. Vérifier le domaine d'envoi (enregistrements DKIM ajoutés par CDK).
2. Adresse d'expédition : `no-reply@<DOMAIN_NAME>`.
3. Demander la sortie du "sandbox" SES pour la production.
4. Créer des identifiants SMTP SES et les placer dans le secret `soronua-predict/<env>/data` (`SMTP_*`, hôte `email-smtp.eu-west-3.amazonaws.com`, port 587).

### 8.5 Sentry
- Organisation Sentry ; projets `soronua-predict-web`, `soronua-predict-api`, `soronua-predict-worker` ; environnements `staging` et `production`.
- Alerte e-mail sur toute nouvelle erreur vers `ALARM_NOTIFICATION_EMAIL`.

### 8.6 AWS
1. Amorçage CDK : `cdk bootstrap aws://<AWS_ACCOUNT_ID>/eu-west-3` (exécuté depuis le conteneur `toolbox`).
2. Créer la connexion GitHub (CodeConnections) et l'autoriser sur le dépôt.
3. Remplir les secrets. La saisie est faite par Claude Code via la CLI AWS, à partir de valeurs fournies par l'utilisateur de façon sécurisée, jamais dans le dépôt ni dans une conversation enregistrée. Seuls les noms des clés sont documentés.

## 9. Dépendances et versions
Voir `CONVENTIONS.md` section 1. Toute nouvelle variable d'environnement est ajoutée, dans le même commit :
- dans ce document ;
- dans le `.env.example` concerné ;
- dans `config.py`, `lib/env.ts` ou `deploy/supabase/.env.example` ;
- dans le secret AWS correspondant.
