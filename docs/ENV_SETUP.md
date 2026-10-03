# ENV_SETUP.md : Variables d'environnement et installation

Document de référence n°8 sur 13.
**Aucune valeur réelle dans ce document ni dans le dépôt.** Les fichiers `.env.example` contiennent les noms et des valeurs factices explicites (`change-me`, `http://localhost:...`).

Tous les composants tournent dans des conteneurs Docker (voir `ARCHITECTURE.md` 1.1). Les variables ci-dessous sont donc toutes des variables de conteneurs.

---

## 1. Où vivent les valeurs

| Environnement | Stockage des valeurs |
|---|---|
| local | `.env` à la racine et `deploy/supabase/.env` (ignorés par Git), générés par `make env-local` : `.env.example` complétés et clés générées localement par `deploy/supabase/generate_keys.py` |
| staging, production : conteneurs de l'application | AWS Secrets Manager, secret JSON `soronua-predict/<env>/app`, injecté dans les tâches ECS |
| staging, production : construction de l'image web | AWS Secrets Manager, secret JSON `soronua-predict/<env>/web-build`, lu par CodeBuild |
| staging, production : pile Supabase | AWS Secrets Manager, secret JSON `soronua-predict/<env>/data`, lu sur l'hôte de données au moment du déploiement pour produire son `.env` (permissions 600, jamais copié ailleurs) |
| CI/CD (pipelines) | AWS Secrets Manager, secret JSON `soronua-predict/cicd`, lu par CodeBuild |
| Infrastructure (CDK) | `infra/cdk.json` (valeurs non secrètes uniquement : région, domaine, e-mails de notification, tailles) |

## 2. Variables : conteneurs api et worker (`apps/api`)

| Nom | Rôle | Où l'obtenir |
|---|---|---|
| `APP_ENV` | `local`, `staging` ou `production` ; active les comportements propres à l'environnement (OpenAPI désactivé en production, commandes de test refusées en production). | Fixé par environnement. |
| `APP_RELEASE` | Identifiant de version (SHA Git court) affiché dans `/api/health` et envoyé à Sentry. | Injecté par le pipeline ; `local` en local. |
| `LOG_LEVEL` | Niveau de journalisation (`INFO` par défaut, `DEBUG` en local). | Fixé par environnement. |
| `SERVICE_NAME` | `api` ou `worker`, balise Sentry et journaux. | Fixé dans la définition de tâche et `docker-compose.yml`. |
| `SUPABASE_URL` | Adresse **interne** de la passerelle Kong. | Local : `http://supabase-kong:8000` (réseau Compose). AWS : `http://data.<env>.internal:8000`. |
| `SUPABASE_ANON_KEY` | Clé publique (jeton `anon`), utilisée avec le jeton de l'utilisateur. | Générée par `generate_keys.py`, identique à `ANON_KEY` du secret `data`. |
| `SUPABASE_SERVICE_ROLE_KEY` | Clé de service, réservée aux modules listés dans `ARCHITECTURE.md` 2.5. **Jamais dans l'image web.** | Générée par `generate_keys.py`, identique à `SERVICE_ROLE_KEY` du secret `data`. |
| `SUPABASE_JWT_SECRET` | Secret HS256 servant à vérifier les jetons des utilisateurs. | Identique à `JWT_SECRET` du secret `data`. |
| `SUPABASE_JWT_ISSUER` | Émetteur attendu dans les jetons. | `<SUPABASE_PUBLIC_URL>/auth/v1`, identique à `GOTRUE_JWT_ISSUER` de la pile. |
| `REDIS_URL` | Connexion Redis (`redis://` en local, `rediss://` Upstash ailleurs). | Local : `redis://redis:6379/0`. Distant : console Upstash, base, "Connect", URL TLS. |
| `SENTRY_DSN` | DSN du projet Sentry `soronua-predict-api` (api) ou `soronua-predict-worker` (worker). | Sentry, Settings, Projects, Client Keys. Vide en local (Sentry désactivé). |
| `SENTRY_TRACES_SAMPLE_RATE` | Part des requêtes tracées (0.1 en production, 1.0 en staging, 0 en local). | Fixé par environnement. |
| `WEB_APP_URL` | URL publique de l'interface ; redirection des e-mails d'invitation. | Local : `http://localhost:3000`. Distant : `https://staging-predict.<DOMAIN_NAME>` ou `https://predict.<DOMAIN_NAME>`. |
| `STORAGE_BUCKET_UPLOADS` | `dataset-uploads`. | Fixe. |
| `STORAGE_BUCKET_ARTIFACTS` | `model-artifacts`. | Fixe. |
| `MAX_UPLOAD_BYTES` | 10485760. | Fixe. |
| `MODEL_POINTER_REFRESH_SECONDS` | 30. | Fixe. |
| `WORKER_HEARTBEAT_PATH` | `/tmp/worker-heartbeat`. | Fixe. |
| `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_FULL_NAME` | Premier administrateur (commande `bootstrap_admin`). | Fourni par l'utilisateur une fois par environnement. |
| `SEED_CSV_PATH` | `/app/data/seed/digital_marketing_campaign_dataset.csv` (dans l'image). | Fixe. |

## 3. Variables : conteneur web (`apps/web`)

Les variables `NEXT_PUBLIC_*` sont incluses dans le code envoyé au navigateur : elles ne contiennent **jamais** de secret. Elles sont fixées à la construction de l'image (une image web par environnement).

| Nom | Rôle | Où l'obtenir |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Adresse **publique** de l'authentification. | Local : `http://localhost:54321`. Distant : l'URL du site elle-même (l'ALB transmet `/auth/v1/*` à Kong). |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Clé publique. | Comme `SUPABASE_ANON_KEY`. |
| `NEXT_PUBLIC_APP_ENV` | `local`, `staging`, `production`. | Fixé par environnement. |
| `NEXT_PUBLIC_APP_RELEASE` | SHA Git court, affiché en pied de page. | Injecté par le pipeline. |
| `NEXT_PUBLIC_SENTRY_DSN` | DSN du projet Sentry `soronua-predict-web`. | Sentry. Vide en local. |
| `SENTRY_AUTH_TOKEN` | Envoi des source maps à la construction (jamais dans l'image finale). | Sentry, Settings, Auth Tokens (`project:releases`, `org:read`). |
| `SENTRY_ORG` / `SENTRY_PROJECT` | Organisation Sentry / `soronua-predict-web`. | Sentry. |
| `API_PROXY_TARGET` | **Local uniquement** : cible des réécritures `/api/*` du serveur Next.js (`http://api:8000`). Absente sur AWS (l'ALB route `/api/*`). | Fixe. |

## 4. Variables : pile Supabase (`deploy/supabase/.env`, secret `soronua-predict/<env>/data`)

| Nom | Rôle | Où l'obtenir |
|---|---|---|
| `POSTGRES_PASSWORD` | Mot de passe du superutilisateur Postgres et des rôles internes. | Généré (40 caractères aléatoires) par `generate_keys.py`. |
| `JWT_SECRET` | Secret de signature des jetons (64 caractères aléatoires minimum). | Généré par `generate_keys.py`. |
| `ANON_KEY` / `SERVICE_ROLE_KEY` | Jetons `anon` et `service_role` signés avec `JWT_SECRET`, sans expiration courte. | Générés par `generate_keys.py`. |
| `SUPABASE_PUBLIC_URL` | URL publique de la pile. | Local : `http://localhost:54321`. Distant : URL du site. |
| `API_EXTERNAL_URL` | Base des liens produits par l'authentification. | Comme `SUPABASE_PUBLIC_URL`. |
| `SITE_URL` | URL de l'interface. | Comme `WEB_APP_URL`. |
| `ADDITIONAL_REDIRECT_URLS` | `<SITE_URL>/auth/confirm`. | Dérivé. |
| `GOTRUE_DISABLE_SIGNUP` | `true` : pas d'inscription libre. | Fixe. |
| `GOTRUE_JWT_EXP` | `3600`. | Fixe. |
| `GOTRUE_JWT_ISSUER` | `<SUPABASE_PUBLIC_URL>/auth/v1`. | Dérivé. |
| `GOTRUE_MAILER_TEMPLATES_INVITE` / `GOTRUE_MAILER_TEMPLATES_RECOVERY` | URL des gabarits d'e-mails servis par `web`. | `<SITE_URL>/auth-templates/invite.html` et `recovery.html` (en local : `http://web:3000/...`). |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_ADMIN_EMAIL` / `SMTP_SENDER_NAME` | Envoi des e-mails. | Local : `mailpit`, port 1025, sans identifiants. Distant : Amazon SES (section 7.4), expéditeur `no-reply@<DOMAIN_NAME>`, nom "Soro Nua Campaign Predictor". |
| `STORAGE_FILE_SIZE_LIMIT` | 10485760. | Fixe. |
| `KONG_HTTP_PORT` | Port exposé par Kong (`54321` en local, `8000` sur AWS). | Fixe. |
| `POSTGRES_PORT` | Port Postgres publié (`54322` en local, `5432` sur AWS, réseau privé seulement). | Fixe. |
| `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD` | Accès à Studio, **local uniquement** (Studio n'est pas déployé ailleurs). | Générés localement. |
| `BACKUP_BUCKET` | Compartiment S3 des sauvegardes (`soronua-predict-<env>-backups`). Absent en local. | Sortie CDK. |
| `BACKUP_SCHEDULE` | Heure de la sauvegarde nocturne (`0 2 * * *`, UTC). | Fixe. |

## 5. Variables : tests de bout en bout (conteneur Playwright)

| Nom | Rôle | Où l'obtenir |
|---|---|---|
| `E2E_BASE_URL` | URL testée. | `http://web:3000` (local, réseau Compose) ou URL staging / production. |
| `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` | Administrateur de test. | Créé par `python -m app.cli.create_test_users` (local et staging uniquement), valeurs dans `soronua-predict/cicd`. |
| `E2E_ADMIN2_EMAIL` / `E2E_ADMIN2_PASSWORD` | Second administrateur (tests de concurrence). | Idem. |
| `E2E_MARKETER_A_EMAIL` / `E2E_MARKETER_A_PASSWORD` | Utilisateur A (isolation). | Idem. |
| `E2E_MARKETER_B_EMAIL` / `E2E_MARKETER_B_PASSWORD` | Utilisateur B (isolation). | Idem. |
| `E2E_SMOKE_EMAIL` / `E2E_SMOKE_PASSWORD` | Compte `marketer` dédié aux tests de fumée en production (lecture et simulation uniquement). | Invité une fois en production ; valeurs dans `soronua-predict/cicd`. |
| `E2E_MAILPIT_URL` | Lecture des e-mails de test, **local uniquement**. | `http://mailpit:8025`. |
| `E2E_SUPABASE_SERVICE_ROLE_KEY` | Local et staging uniquement : préparation des données de test. **Jamais pour la production.** | Comme `SUPABASE_SERVICE_ROLE_KEY` du même environnement. |

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
- Docker Desktop (ou Docker Engine) avec Docker Compose v2, 8 Go de mémoire alloués au minimum.
- GNU Make.
- Rien d'autre n'est installé sur la machine : Python, Node.js, la Supabase CLI, Playwright et les outils de contrôle s'exécutent dans des conteneurs (image `soronua-predict-toolbox` construite depuis `tools/Dockerfile`), appelés par le `Makefile`.

### 7.2 Étapes

```bash
git clone git@github.com:<propriétaire>/soronua-campaign-predictor.git
cd soronua-campaign-predictor
git checkout dev

make env-local       # crée .env et deploy/supabase/.env, génère les clés locales
make build           # construit toutes les images (web, api, db-backup, toolbox)
make up              # démarre toute la pile : Supabase, redis, mailpit, api, worker, web
make db-reset        # recrée le volume de la base locale et applique toutes les migrations
make seed            # charge le jeu de départ (8 000 lignes)
make bootstrap-admin FIRST_ADMIN_EMAIL=admin@example.test FIRST_ADMIN_FULL_NAME="Local Admin"
make test-users      # crée les comptes de test Playwright
```

Puis :
- interface : `http://localhost:3000` ;
- API : `http://localhost:8000/api/health` ;
- passerelle Supabase : `http://localhost:54321` ;
- Postgres : `localhost:54322` ;
- Supabase Studio : `http://localhost:54323` (identifiants `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`) ;
- e-mails locaux : `http://localhost:54324` (Mailpit).

Le premier administrateur définit son mot de passe via le lien reçu dans Mailpit.

### 7.3 Composition locale
- `docker-compose.yml` à la racine inclut `deploy/supabase/docker-compose.yml` (directive `include`) et ajoute :
  - `redis` ;
  - `mailpit` ;
  - `api` : cible `dev`, `uvicorn --reload`, code monté en volume ;
  - `worker` ;
  - `web` : cible `dev`, `next dev`.
- Un seul réseau Compose : les conteneurs se joignent par leur nom (`supabase-kong`, `redis`, `api`, `web`).
- Les données locales vivent dans des volumes nommés (`supabase-db-data`, `supabase-storage-data`), supprimés par `make db-reset` et `make clean`.
- `supabase-meta` et `supabase-studio` sont rattachés au profil Compose `local` : ils ne sont jamais lancés sur AWS.

### 7.4 Commandes courantes

| Commande | Effet |
|---|---|
| `make check` | Tous les contrôles (voir `CONVENTIONS.md` section 2), dans des conteneurs. |
| `make test-unit` / `make test-integration` / `make test-db` / `make test-e2e` | Tests par niveau. |
| `make api-types` | Régénère `apps/web/src/lib/api/types.gen.ts`. |
| `make db-new-migration name=<description>` | Crée un fichier de migration vide horodaté. |
| `make logs` | Journaux des conteneurs. |
| `make down` / `make clean` | Arrête la pile / l'arrête et supprime ses volumes. |

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
