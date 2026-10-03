# LLD.md : Conception détaillée

Document de référence n°6 sur 13.

---

## 1. Arborescence exacte

```
soronua-campaign-predictor/
├── CLAUDE.md
├── README.md
├── Makefile
├── docker-compose.yml
├── .gitignore
├── .gitattributes                    # le CSV de départ n'est jamais converti (fins de ligne, `-text`)
├── .dockerignore                     # contexte de construction unique : la racine du dépôt
├── .env.example                      # source des variables de `docker-compose.yml` (valeurs locales, aucun secret)
├── .npmrc                            # outils racine : versions exactes (`save-exact=true`)
├── .pre-commit-config.yaml           # contrôles locaux exécutés dans le conteneur toolbox (fichiers interdits, gitleaks)
├── .editorconfig
├── package.json                      # outils racine uniquement (Supabase CLI figée, exécutée dans le conteneur toolbox)
├── package-lock.json
├── docs/
│   ├── PROJECT_BRIEF.md
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── API_SPEC.md
│   ├── LLD.md
│   ├── CONVENTIONS.md
│   ├── ENV_SETUP.md
│   ├── TESTING.md
│   ├── SECURITY_NOTES.md
│   ├── CI_CD.md
│   ├── ROADMAP.md
│   └── decisions.md                  # décisions prises en cours de construction
├── ui_prototype/                     # maquette de référence fournie par l'utilisateur : lecture seule, jamais construite ni copiée dans une image (exclue par `.dockerignore`)
├── notebooks/                        # préparation de la phase 7 (D-044) : analyse et entraînement exploratoires, jamais construits dans l'image de production
│   ├── README.md
│   ├── common.py                     # règles du LLD 5.x (holdout, variables, paramètres, métriques) partagées par les notebooks
│   ├── 01_data_profile.ipynb
│   ├── 02_train_three_models.ipynb
│   ├── 03_evaluation_and_scoring.ipynb
│   └── _out/                         # sorties (figures, métriques, modèles), ignoré par git
├── data/
│   └── seed/
│       ├── digital_marketing_campaign_dataset.csv
│       └── SOURCE.md                 # origine et licence du jeu de départ
├── tools/
│   └── Dockerfile                    # image toolbox : Python/uv, Node, Supabase CLI, AWS CLI, CDK, outils de contrôle
├── deploy/
│   └── supabase/
│       ├── docker-compose.yml        # pile Supabase auto-hébergée (local, staging, production) ; incluse par le docker-compose.yml racine
│       ├── .env.example              # valeurs locales et `change-me` ; `deploy/supabase/.env` (ignoré par Git) est généré par `make env-local`
│       ├── kong.yml                  # routes de la passerelle (auth, rest, storage, /kong-health) ; gabarit : seuls `$SUPABASE_ANON_KEY`, `$SUPABASE_SERVICE_KEY` et `$SITE_URL` y sont permis
│       ├── generate_keys.py          # génère JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY, POSTGRES_PASSWORD (et PG_META_CRYPTO_KEY, S3_PROTOCOL_*), les recopie dans le `.env` racine ; bibliothèque standard seulement
│       ├── db/
│       │   ├── roles.sql             # phase 1 : aligne les mots de passe des rôles internes sur POSTGRES_PASSWORD (initialisation de supabase-db)
│       │   └── jwt.sql               # phase 1 : durée des jetons visible de la base (`app.settings.jwt_exp`)
│       ├── tests/                    # phase 1 : tests `unittest` de la pile, lancés dans le toolbox par `make test-unit`
│       │   ├── __init__.py
│       │   ├── _helpers.py
│       │   ├── compose_guards.py     # contrôles sur la configuration Compose résolue (`make guards`) ; n'est pas un test collecté
│       │   ├── test_compose_guards.py
│       │   ├── test_compose_stack.py
│       │   ├── test_db_init_scripts.py
│       │   ├── test_generate_keys.py
│       │   ├── test_kong_config.py
│       │   ├── test_makefile.py
│       │   └── test_migrations_static.py
│       ├── apply.sh                  # exécuté par SSM sur l'hôte de données : .env depuis Secrets Manager, pull, up, santé
│       ├── supabase-stack.service    # unité systemd qui lance la pile au démarrage de l'hôte
│       └── backup/
│           ├── Dockerfile            # image soronua-predict-db-backup
│           ├── backup.sh             # pg_dump + copie des fichiers de stockage vers S3
│           └── restore.sh            # restauration documentée dans CI_CD.md 6.2
├── apps/
│   ├── api/
│   │   ├── Dockerfile                    # cibles : `dev` (outils de contrôle, utilisée par `make check`) et `prod`
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── .env.example
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── worker.py
│   │   │   ├── config.py
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py
│   │   │   │   ├── deps.py
│   │   │   │   ├── errors.py
│   │   │   │   ├── middleware.py
│   │   │   │   ├── routes_health.py
│   │   │   │   ├── routes_me.py
│   │   │   │   ├── routes_reference.py
│   │   │   │   ├── routes_predictions.py
│   │   │   │   ├── routes_model.py
│   │   │   │   └── admin/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── routes_users.py
│   │   │   │       ├── routes_dataset.py
│   │   │   │       ├── routes_model_versions.py
│   │   │   │       └── routes_audit.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── common.py
│   │   │   │   ├── campaign.py
│   │   │   │   ├── prediction.py
│   │   │   │   ├── reference.py
│   │   │   │   ├── user.py
│   │   │   │   ├── dataset.py
│   │   │   │   ├── model_version.py
│   │   │   │   └── audit.py
│   │   │   ├── domain/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── dataset_schema.py
│   │   │   │   ├── csv_validation.py
│   │   │   │   ├── holdout.py
│   │   │   │   ├── features.py
│   │   │   │   ├── derived_metrics.py
│   │   │   │   ├── scoring.py
│   │   │   │   ├── engagement_defaults.py
│   │   │   │   ├── explanations.py
│   │   │   │   ├── recommendations.py
│   │   │   │   ├── warnings.py
│   │   │   │   ├── comparison.py
│   │   │   │   └── errors.py
│   │   │   ├── ml/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── params.py
│   │   │   │   ├── training.py
│   │   │   │   ├── evaluation.py
│   │   │   │   ├── bundle.py
│   │   │   │   └── predictor.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── prediction_service.py
│   │   │   │   ├── readiness_service.py       # phase 1 : sonde de la base pour /api/ready
│   │   │   │   ├── reference_service.py
│   │   │   │   ├── upload_service.py
│   │   │   │   ├── training_request_service.py
│   │   │   │   ├── training_job.py
│   │   │   │   ├── activation_service.py
│   │   │   │   ├── model_registry.py
│   │   │   │   ├── user_admin_service.py
│   │   │   │   └── audit_service.py
│   │   │   ├── repositories/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── profiles_repo.py
│   │   │   │   ├── dataset_repo.py
│   │   │   │   ├── model_versions_repo.py
│   │   │   │   ├── predictions_repo.py
│   │   │   │   ├── audit_repo.py
│   │   │   │   └── storage_repo.py
│   │   │   ├── infra/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── supabase_clients.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── redis_client.py
│   │   │   │   ├── queue.py
│   │   │   │   ├── rate_limit.py
│   │   │   │   ├── profile_cache.py
│   │   │   │   ├── observability.py
│   │   │   │   ├── request_context.py
│   │   │   │   └── pagination.py
│   │   │   └── cli/
│   │   │       ├── __init__.py
│   │   │       ├── bootstrap_admin.py
│   │   │       ├── seed_dataset.py
│   │   │       ├── create_test_users.py
│   │   │       └── activate_model_version.py
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── fixtures/
│   │       │   ├── small_dataset.csv          # 300 lignes déterministes
│   │       │   ├── invalid_*.csv              # un fichier par type d'erreur
│   │       │   └── golden/                    # résultats attendus figés
│   │       ├── factories.py
│   │       ├── unit/                          # miroir de app/domain et app/ml
│   │       │   ├── test_config.py             # phase 0 : Settings, variables manquantes ou invalides
│   │       │   ├── test_errors.py             # phase 0 : codes, statuts, traduction des erreurs de validation
│   │       │   ├── test_observability.py      # phase 0 : journaux JSON, aucune donnée personnelle
│   │       │   ├── test_request_context.py    # phase 0 : identifiant de requête, contexte
│   │       │   ├── test_supabase_clients.py   # phase 1 : client anon, client utilisateur (nouveau à chaque appel), client de service (instance unique)
│   │       │   ├── test_readiness_service.py  # phase 1 : sonde de la base (transport httpx simulé, aucune pile)
│   │       │   └── test_architecture.py       # phase 0 : règles de dépendance, lecture de l'environnement réservée à config.py ; phase 1 : `get_service_client` importé seulement par les modules autorisés
│   │       └── integration/                   # api + Supabase locale + Redis ; en phase 0, `test_health.py` (TestClient, sans pile)
│   │           ├── conftest.py                # phase 1 : `require_stack` (échec franc si la pile ne répond pas, jamais `skip`)
│   │           ├── test_ready.py              # phase 1 : /api/ready (TestClient, sans pile, dépendance surchargée)
│   │           └── test_stack_wiring.py       # phase 1 : pile réelle (Kong, authentification, déclencheur de profil, Mailpit, /api/ready)
│   └── web/
│       ├── Dockerfile                         # cibles : `dev`, `prod` (build Next.js standalone) et `e2e` (image Playwright)
│       ├── package.json
│       ├── package-lock.json
│       ├── .env.example
│       ├── next.config.ts
│       ├── tsconfig.json
│       ├── tailwind.config.ts
│       ├── postcss.config.mjs
│       ├── eslint.config.mjs
│       ├── .prettierrc.json
│       ├── .prettierignore
│       ├── .npmrc                             # versions exactes (`save-exact=true`)
│       ├── components.json                    # configuration shadcn/ui
│       ├── vitest.config.ts
│       ├── playwright.config.ts
│       ├── instrumentation.ts                 # Sentry serveur
│       ├── instrumentation-client.ts          # Sentry navigateur
│       ├── sentry.server.config.ts
│       ├── sentry.edge.config.ts
│       ├── public/
│       │   └── auth-templates/ (invite.html, recovery.html)   # gabarits d'e-mails lus par supabase-auth
│       ├── src/
│       │   ├── middleware.ts
│       │   ├── app/
│       │   │   ├── layout.tsx
│       │   │   ├── page.tsx                    # provisoire (phases 0 et 1) : état de l'API et de la base ; supprimée en phase 2 quand `(app)/page.tsx` arrive
│       │   │   ├── icon.svg
│       │   │   ├── fonts/                      # Barlow et Barlow Condensed (licence OFL), servies localement
│       │   │   ├── globals.css
│       │   │   ├── global-error.tsx
│       │   │   ├── not-found.tsx
│       │   │   ├── healthz/route.ts
│       │   │   ├── (public)/
│       │   │   │   ├── login/page.tsx
│       │   │   │   └── forgot-password/page.tsx
│       │   │   ├── auth/
│       │   │   │   ├── confirm/route.ts
│       │   │   │   └── set-password/page.tsx
│       │   │   └── (app)/
│       │   │       ├── layout.tsx
│       │   │       ├── page.tsx                # redirige vers /predict
│       │   │       ├── predict/page.tsx
│       │   │       ├── history/page.tsx
│       │   │       ├── history/[id]/page.tsx
│       │   │       ├── model/page.tsx
│       │   │       └── admin/
│       │   │           ├── layout.tsx          # garde de rôle
│       │   │           ├── users/page.tsx
│       │   │           ├── data/page.tsx
│       │   │           ├── models/page.tsx
│       │   │           ├── models/[id]/page.tsx
│       │   │           └── audit/page.tsx
│       │   ├── components/
│       │   │   ├── ui/                         # composants shadcn/ui générés
│       │   │   ├── layout/ (app-header.tsx, app-nav.tsx, app-footer.tsx, page-title.tsx)
│       │   │   ├── feedback/ (api-status.tsx [phase 0], database-status.tsx [phase 1], error-state.tsx, empty-state.tsx, warning-banner.tsx, loading-state.tsx)
│       │   │   ├── prediction/ (campaign-form.tsx, campaign-plan-fields.tsx, audience-fields.tsx,
│       │   │   │               engagement-fields.tsx, results-panel.tsx, metric-cards.tsx,
│       │   │   │               performance-level.tsx, drivers-chart.tsx, recommendations-list.tsx,
│       │   │   │               save-prediction-dialog.tsx)
│       │   │   ├── history/ (history-table.tsx)
│       │   │   ├── model/ (reliability-table.tsx, global-importance-chart.tsx)
│       │   │   └── admin/ (users-table.tsx, invite-user-dialog.tsx, upload-form.tsx,
│       │   │              upload-errors-table.tsx, uploads-table.tsx, dataset-summary.tsx,
│       │   │              train-dialog.tsx, model-versions-table.tsx, version-comparison.tsx,
│       │   │              audit-table.tsx)
│       │   ├── hooks/
│       │   │   ├── use-api-health.ts           # phase 0 : interroge /api/health
│       │   │   ├── use-api-ready.ts            # phase 1 : interroge /api/ready (état de la base et numéro de schéma)
│       │   │   ├── use-session.ts
│       │   │   ├── use-me.ts
│       │   │   ├── use-reference.ts
│       │   │   ├── use-simulation.ts
│       │   │   ├── use-predictions.ts
│       │   │   ├── use-model.ts
│       │   │   ├── use-admin-users.ts
│       │   │   ├── use-admin-dataset.ts
│       │   │   ├── use-admin-model-versions.ts
│       │   │   └── use-form-draft.ts
│       │   ├── lib/
│       │   │   ├── api/
│       │   │   │   ├── client.ts
│       │   │   │   ├── errors.ts
│       │   │   │   ├── types.gen.ts            # généré depuis OpenAPI, jamais édité à la main
│       │   │   │   └── query-keys.ts
│       │   │   ├── supabase/
│       │   │   │   ├── browser.ts
│       │   │   │   ├── server.ts
│       │   │   │   └── middleware.ts
│       │   │   ├── schemas/campaign.ts         # schéma Zod du formulaire
│       │   │   ├── format.ts
│       │   │   ├── utils.ts                    # `cn()` (shadcn/ui)
│       │   │   ├── labels.ts                   # libellés anglais (glossaire PRD 8)
│       │   │   ├── env.ts
│       │   │   └── observability.ts
│       │   └── providers/
│       │       ├── query-provider.tsx
│       │       └── session-provider.tsx
│       ├── tests/                              # tests unitaires Vitest
│       │   ├── setup.ts                        # configuration commune (nettoyage du DOM, serveur MSW)
│       │   ├── msw/server.ts                   # faux serveur d'API pour les tests
│       │   ├── lib/                            # miroir de src/lib
│       │   └── components/                     # miroir de src/components (phase 1 : `database-status.test.tsx`)
│       └── e2e/
│           ├── health.spec.ts                  # phases 0 et 1 : parcours de l'état de l'API et de la base
│           ├── fixtures/ (auth.ts, data.ts, files/)
│           ├── auth.spec.ts
│           ├── predict.spec.ts
│           ├── history.spec.ts
│           ├── isolation.spec.ts
│           ├── admin-users.spec.ts
│           ├── admin-data.spec.ts
│           ├── admin-models.spec.ts
│           ├── concurrency.spec.ts
│           ├── session.spec.ts
│           └── smoke.spec.ts                   # réservé au parcours de fumée de production (phase 18) ; ne pas l'utiliser pour les tests de la phase 0
├── supabase/
│   ├── config.toml                   # utilisé seulement par la CLI pour gérer les migrations
│   ├── migrations/                   # phase 1 : migrations 1 et 2 (`..._init_enums_profiles.sql`, `..._audit_log.sql`)
│   └── tests/database/               # phase 1 : tests pgTAP (`NNN_*.test.sql`) et `_helpers.psql`
├── infra/
│   ├── app.py
│   ├── cdk.json
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── stacks/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── network_stack.py
│   │   ├── data_stack.py
│   │   ├── app_stack.py
│   │   ├── monitoring_stack.py
│   │   └── pipeline_stack.py
│   └── tests/
├── buildspecs/
│   ├── checks.yml
│   ├── build.yml
│   ├── data_host.yml
│   ├── migrate.yml
│   ├── deploy.yml
│   ├── e2e.yml
│   ├── smoke.yml
│   └── sentry_release.yml
└── .github/
    ├── pull_request_template.md
    ├── CODEOWNERS
    └── dependabot.yml
```

Aucun fichier ne doit être créé hors de cette arborescence sans être ajouté ici (voir `CLAUDE.md`).

---

## 2. Responsabilités des modules : api (Python)

Règle de dépendance : `api` → `services` → (`domain`, `ml`, `repositories`, `infra`). `domain` n'importe rien d'autre que la bibliothèque standard, `numpy` et `pandas`. `ml` importe `domain`. `repositories` n'importe que `infra` et `schemas`. Aucun cycle.

**`main.py`** : fabrique l'application FastAPI (`create_app()`). Branche le middleware de requête, les gestionnaires d'erreurs, le routeur, Sentry, et le chargement du modèle au démarrage. Aucune logique métier.

**`worker.py`** : point d'entrée du worker (`python -m app.worker`). Initialise la configuration et Sentry, remet en file les travaux orphelins, marque en échec les versions bloquées, puis tourne la boucle `run_forever()`. Option `--healthcheck` : vérifie l'âge du fichier de battement.

**`config.py`** : lit et valide toutes les variables d'environnement avec `pydantic-settings`. Un démarrage avec une variable manquante ou invalide échoue immédiatement avec un message listant les variables en cause (jamais leurs valeurs). Aucune autre partie du code ne lit `os.environ` (un test d'architecture le vérifie). Une variable à valeur vide est traitée comme absente (`env_ignore_empty`). Étendue en phase 0 : `Settings` ne contient que `APP_ENV` et `SERVICE_NAME` (obligatoires, sans valeur par défaut), `APP_RELEASE`, `LOG_LEVEL`, `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE` et `MAX_UPLOAD_BYTES` ; la phase 1 ajoute `SUPABASE_URL` (défaut `http://supabase-kong:8000`, motif `http(s)://hôte`, sans barre finale) et `SUPABASE_ANON_KEY` et `SUPABASE_SERVICE_ROLE_KEY` (`SecretStr`, vides par défaut, jamais dans un `repr` ni un journal, D-058) ; chaque phase ajoute les variables dont elle a besoin (`REDIS_URL`, etc.), avec `config.py`, les `.env.example` et `ENV_SETUP.md` dans le même commit.

**`infra/` (deux sens)** : `apps/api/app/infra/` est le module de l'API (`observability.py`, `request_context.py`, puis clients Supabase, Redis, etc.). Le dossier `infra/` à la racine du dépôt est le paquet AWS CDK (phase 17) ; il n'existe pas avant. Ne pas les confondre dans les imports ni dans les commandes : `mypy --strict` porte sur `apps/api/app`.

**`api/router.py`** : assemble tous les routeurs sous `/api` et `/api/v1`.

**`api/deps.py`** : dépendances FastAPI :
- `get_settings` ;
- `get_database_check` (phase 1 : appelle `check_database(settings)` de `services/readiness_service.py`) ;
- `get_current_user` (jeton vérifié + profil) ;
- `require_admin` ;
- `get_user_db` (client Supabase portant le jeton de l'utilisateur) ;
- `rate_limit(scope)`.

**`api/errors.py`** : énumération `ErrorCode` et table `ERROR_STATUS` (les 23 codes de `API_SPEC.md` 3, gardées synchrones par un test unitaire), classe `AppError(code, status, message, details, headers)` et gestionnaires qui convertissent `AppError`, erreurs de validation Pydantic, erreurs HTTP de Starlette (404, 405, 413) et, plus tard, erreurs PostgREST (`P0001` avec code métier) au format standard. La traduction des erreurs de validation (`translate_validation_errors`) ne recopie jamais la valeur refusée. Les exceptions inattendues sont envoyées à Sentry avant la réponse 500 (gérées par `RequestContextMiddleware`, pas par un gestionnaire FastAPI). `PayloadTooLargeError` dérive de `fastapi.HTTPException` : FastAPI transformerait toute autre exception levée pendant la lecture du corps en 400.

**`schemas/common.py`** : schémas communs à toutes les routes : `HealthResponse`, `ReadyChecks` et `ReadyResponse` (phase 1 : `status`, `checks`, `schema_version`, `release` ; les champs `cache` et `model` de `checks` sont optionnels et omis tant que non vérifiés), `ErrorDetail`, `ErrorBody`, `ErrorResponse` (`extra="forbid"`).

**`api/routes_health.py`** : `GET /health` (asynchrone, ne dépend d'aucun service) et, depuis la phase 1, `GET /ready` : route **synchrone** (`def`, exécutée dans le pool de threads, car la sonde fait un appel réseau bloquant) qui renvoie 200 ou 503 avec le même schéma `ReadyResponse` (`response_model_exclude_none=True`, pas le format d'erreur standard ; `responses={503: {"model": ReadyResponse}}` pour OpenAPI). Elle dépend de `get_database_check` (`api/deps.py`), surchargeable en test par `app.dependency_overrides`.

**`api/middleware.py`** : deux middlewares ASGI purs (pas de `BaseHTTPMiddleware`, pour que le contexte et les en-têtes restent identiques sur toutes les réponses, y compris une 500) :
- `RequestContextMiddleware` (le plus externe) : génère ou reprend `X-Request-ID` (UUID, sinon un nouvel UUID est généré), le place dans le contexte (`request_context`) et dans la portée Sentry, journalise chaque requête en JSON (méthode, chemin, route, statut, durée ; `user_id` quand il est connu), ajoute les en-têtes de sécurité (`API_SPEC.md` 3.2) et transforme toute exception inattendue en 500 `INTERNAL_ERROR` après l'avoir remontée ;
- `RequestGuardMiddleware` : refuse les corps de type non accepté (415) et trop gros (413) avant toute lecture : 64 Ko pour le JSON, `MAX_UPLOAD_BYTES` plus 64 Ko de marge pour un envoi `multipart/form-data` ; compte aussi les octets reçus en flux, car `Content-Length` peut manquer ou être faux.

`/api/health` et `/api/ready` sont journalisés au niveau DEBUG tant qu'ils réussissent, pour ne pas noyer les journaux ; un 503 de `/api/ready` est journalisé comme toute réponse 5xx (niveau `error` par le middleware, `QUIET_PATHS` ne fait taire que les succès).

**`api/routes_*.py`** : une route = une fonction courte qui valide via les schémas, appelle un service, renvoie un schéma. Aucune requête base de données directe.

**`schemas/*`** : modèles Pydantic des entrées et sorties, conformes à `API_SPEC.md`, avec `model_config = ConfigDict(extra="forbid")` sur toutes les entrées.

**`domain/dataset_schema.py`** : source unique des colonnes du jeu de données, de leur correspondance avec les noms internes, des énumérations, des bornes de validation et des groupes de champs (plan, audience, engagement, cibles, ignorés).

**`domain/csv_validation.py`** : vérifie un fichier CSV brut (encodage, en-tête, types, bornes, doublons, injection de formules) et renvoie soit un tableau propre, soit la liste des erreurs. Fonction pure, sans accès réseau.

**`domain/holdout.py`** : décide de façon déterministe si une ligne est mise de côté pour les tests.

**`domain/features.py`** : définit les variables d'entrée actives, transforme des lignes ou une saisie en matrice numérique (codage des catégories) et calcule les plages observées.

**`domain/derived_metrics.py`** : calcule prospects estimés et coût par résultat.

**`domain/scoring.py`** : construit les distributions de référence par type, calcule les notes, le score global, les seuils et le niveau.

**`domain/engagement_defaults.py`** : calcule et restitue les valeurs de pré-remplissage de l'engagement attendu.

**`domain/explanations.py`** : regroupe les contributions par champ d'origine, produit les 5 principaux facteurs et l'importance globale.

**`domain/recommendations.py`** : génère les variantes par levier, les classe et applique le seuil de 5 points.

**`domain/warnings.py`** : produit les avertissements (`LOW_MODEL_RELIABILITY`, `OUT_OF_TRAINING_RANGE`, `REFERENCE_FALLBACK`).

**`domain/comparison.py`** : compare deux jeux de métriques et rend le verdict.

**`domain/errors.py`** : exceptions métier (`CsvInvalid`, `NotEnoughData`, etc.) converties par `api/errors.py`.

**`ml/params.py`** : hyperparamètres figés de XGBoost et constantes d'apprentissage.

**`ml/training.py`** : à partir d'un tableau de lignes, découpe apprentissage et test selon `is_holdout`, entraîne les trois modèles et renvoie un `TrainedBundle`.

**`ml/evaluation.py`** : calcule MAE, RMSE, R² et erreur de référence (moyenne) pour chaque chiffre, et évalue n'importe quel `Predictor` sur un tableau de test.

**`ml/bundle.py`** : définit `ModelBundle` (modèles + métadonnées) et sa sérialisation en fichiers (trois modèles XGBoost au format JSON + `bundle.json`) et désérialisation. Vérifie `bundle_schema_version`.

**`ml/predictor.py`** : `Predictor` enveloppe un `ModelBundle` chargé ; prédit les trois chiffres pour un lot de saisies et fournit les contributions par variable (`pred_contribs=True`). Borne les sorties (taux dans [0, 1], visites ≥ 0).

**`services/prediction_service.py`** : orchestre une simulation ou un enregistrement : modèle actif, validation, prédiction, dérivés, score, facteurs, recommandations, avertissements, puis insertion en base pour un enregistrement.

**`services/readiness_service.py`** (phase 1) : `check_database(settings, *, transport=None) -> DatabaseCheck` et `DatabaseCheck(ok, schema_version, reason)` (dataclass figée ; `reason` vaut `missing_key`, `timeout`, `connection_error`, `http_<statut>` ou `bad_payload`). Appelle `POST {SUPABASE_URL}/rest/v1/rpc/schema_version` (corps `{}`, en-têtes `apikey` et `Authorization: Bearer` avec la clé **anon**, jamais la clé de service) avec un `httpx.Client` synchrone fermé par `with` (délai de 2 s) et attend une chaîne de 14 chiffres. Clé anon vide : échec fermé sans requête réseau. Journalise un `warning` structuré `readiness_failed` (`check`, `reason`), jamais la clé, l'URL complète ni le corps ; ne remonte rien à Sentry (panne attendue). Le paramètre `transport` ne sert qu'aux tests (`httpx.MockTransport`).

**`services/reference_service.py`** : sert les options du formulaire et les valeurs de pré-remplissage à partir du modèle actif.

**`services/upload_service.py`** : orchestre un import : taille, empreinte, validation, contrôle des doublons d'identifiants, stockage du fichier, insertion par lots, passage à `ready`, nettoyage en cas d'échec, journal d'audit.

**`services/training_request_service.py`** : crée la version en `queued`, pousse le travail dans la file, gère l'indisponibilité de la file.

**`services/training_job.py`** : exécute un travail d'apprentissage dans le worker, de bout en bout (voir section 5.7).

**`services/activation_service.py`** : appelle la fonction `activate_model_version`, met à jour le pointeur Upstash, traduit les erreurs.

**`services/model_registry.py`** : garde le `Predictor` actif en mémoire, vérifie le pointeur toutes les 30 secondes, recharge depuis Storage de façon atomique (le nouvel objet remplace l'ancien en une affectation ; les requêtes en cours gardent leur référence).

**`services/user_admin_service.py`** : invitation, changement de rôle, désactivation (avec bannissement Supabase Auth), réactivation, liste des utilisateurs avec statut, invalidation du cache de profil.

**`services/audit_service.py`** : écrit les entrées d'audit (via `log_audit` avec le jeton de l'administrateur, ou directement en clé de service depuis le worker) et les lit.

**`repositories/*`** : un fichier par table ou espace de stockage, uniquement des accès aux données, traduction des lignes en objets typés. Chaque fonction reçoit explicitement le client à utiliser (utilisateur ou service).

**`infra/supabase_clients.py`** : crée le client "anonyme" (clé publique, sans jeton), le client "utilisateur" (clé publique + jeton de l'utilisateur, nouveau par requête) et le client "service" (clé de service, instance unique, `lru_cache`). Aucun client ne conserve de session ni ne lance de minuteur de rafraîchissement. Une clé vide ou un jeton vide lève une erreur explicite sans écho de valeur. Le client "service" n'est défini que dans ce module et n'est importable que par les modules autorisés (liste fermée de `ARCHITECTURE.md` 2.5), vérifié par un test d'architecture (voir `TESTING.md`) ; aucun consommateur n'existe avant les phases suivantes. Signatures (phase 1) :
```python
def get_anon_client(settings: Settings | None = None) -> Client: ...
def get_user_client(access_token: str, settings: Settings | None = None) -> Client: ...
def get_service_client(settings: Settings | None = None) -> Client: ...
```
Les paramètres `settings` valent `get_settings()` par défaut (`app/config.py`, variables `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, voir `ENV_SETUP.md` 2 et D-058).

**`infra/auth.py`** : vérification des JWT (HS256 avec le secret de la pile Supabase de l'environnement, émetteur et audience contrôlés).

**`infra/redis_client.py`** : connexion Redis unique (TLS en staging et production), délais courts (connexion 2 s, lecture 5 s).

**`infra/queue.py`** : `enqueue`, `dequeue_blocking` (`BLMOVE` 20 s vers la liste de traitement), `ack` (`LREM`), `requeue_orphans`.

**`infra/rate_limit.py`** : fenêtre fixe avec `INCR` + `EXPIRE` ; en cas d'indisponibilité de Redis, laisse passer et signale à Sentry (une fois par minute au maximum).

**`infra/profile_cache.py`** : lecture et écriture du profil en cache, invalidation.

**`infra/observability.py`** : initialisation de Sentry (`send_default_pii=False`, balises `service`, `environment`, `release`), journalisation JSON (`structlog`), fonction `capture(exc, **context)`.

**`infra/request_context.py`** : variables de contexte (`request_id`, `user_id`) lues par les journaux et Sentry.

**`infra/pagination.py`** : encodage et décodage des curseurs (`created_at` + `id`, base64 URL).

**`cli/*`** : commandes d'exploitation, idempotentes, avec clé de service :
- `bootstrap_admin` : crée ou invite le premier administrateur ; option `--print-link` qui génère le lien d'invitation (API d'administration de `supabase-auth`) et l'affiche à l'opérateur seulement, pour les environnements sans SMTP réel ;
- `seed_dataset` : charge le jeu de départ, ne fait rien s'il est déjà présent ;
- `create_test_users` : crée les comptes de test pour Playwright, refusé en production ;
- `activate_model_version` : réactive une version réussie donnée, pour le retour arrière.

## 3. Responsabilités des modules : web (TypeScript)

**`middleware.ts`** : rafraîchit la session Supabase à chaque requête (`lib/supabase/middleware.ts`) et redirige vers `/login?next=<chemin>` toute route du groupe `(app)` sans session.

**`app/(public)/*`** : écrans de connexion et de mot de passe oublié. Utilisent `supabase.auth.signInWithPassword` et `resetPasswordForEmail`.

**`app/auth/confirm/route.ts`** : reçoit `token_hash`, `type` (`invite` ou `recovery`) et `next`, appelle `verifyOtp`, redirige vers `next` (limité aux chemins internes commençant par `/`) ou vers `/login?reason=invalid_link`.

**`app/auth/set-password/page.tsx`** : saisie et confirmation du mot de passe (`updateUser`).

**`app/(app)/layout.tsx`** : en-tête, navigation selon le rôle (`use-me`), pied de page avec la version, fournisseurs.

**`app/(app)/admin/layout.tsx`** : garde de rôle ; un `marketer` est redirigé vers `/predict?notice=forbidden`.

**`app/(app)/predict/page.tsx`** : assemble `CampaignForm` et `ResultsPanel` ; gère le bandeau "aucun modèle actif".

**`app/(app)/history/*`** : liste paginée et détail en lecture seule (le détail réutilise `ResultsPanel` en mode figé).

**`app/(app)/model/page.tsx`** : fiabilité et importance globale.

**`app/(app)/admin/*`** : utilisateurs, données, versions (avec interrogation toutes les 3 s pendant un apprentissage), audit.

**`components/prediction/campaign-form.tsx`** : formulaire React Hook Form + Zod en trois blocs ; déclenche le pré-remplissage quand canal et type changent (sans écraser un champ déjà modifié par l'utilisateur) ; expose les valeurs validées à `use-simulation`.

**`components/prediction/results-panel.tsx`** : affiche un `PredictionResult` (cartes, niveau, facteurs, recommandations, avertissements) ; bouton "Apply" qui remonte la nouvelle valeur au formulaire ; mode "figé" pour l'historique.

**`hooks/use-api-ready.ts`** et **`components/feedback/database-status.tsx`** (phase 1, provisoires comme la page d'accueil) : le hook interroge `/api/ready` toutes les 5 s (délai de 3 s, sans nouvel essai) et renvoie `{ state: "checking" | "connected" | "unreachable", schemaVersion }` ; `connected` seulement si `status === "ready"`, `checks.database === "ok"` et `schema_version` non vide, toute autre issue (erreur réseau, 503, corps inattendu) donne `unreachable`. Le composant porte `data-testid="database-status"` et `data-state`, les classes `text-success` / `text-danger` / `text-neutral-700` et les libellés de `labels.status.database` (D-055). Il est indépendant de `api-status.tsx` : les deux sondes échouent séparément.

**`hooks/use-simulation.ts`** : anti-rebond de 400 ms sur les valeurs valides du formulaire, appel `simulate` via TanStack Query (`keepPreviousData`), annulation de la requête précédente.

**`hooks/use-form-draft.ts`** : sauvegarde le brouillon du formulaire dans `sessionStorage` (clé `predict-draft:v1`) à chaque changement ; restauration au chargement de `/predict` ; effacement après enregistrement réussi ou à la déconnexion volontaire.

**`lib/api/client.ts`** : fonction `apiFetch` unique :
- ajoute le jeton et `X-Request-ID` ;
- sur `TOKEN_EXPIRED`, tente un seul `refreshSession()` puis rejoue ;
- sur nouvel échec 401, redirige vers `/login?reason=session_expired&next=...` ;
- sur `ACCOUNT_DISABLED`, déconnecte et redirige vers `/login?reason=disabled` ;
- transforme toute erreur en `ApiError` typée.

**`lib/api/types.gen.ts`** : types générés par `openapi-typescript` depuis `/api/openapi.json`. Régénéré par `make api-types` ; un contrôle CI vérifie qu'il est à jour.

**`lib/labels.ts`** : tous les textes affichés (glossaire du PRD section 8 et messages), au même endroit.

**`lib/observability.ts`** : `reportError(error, context)` vers Sentry, avec `request_id` et nom de page ; jamais d'e-mail ni de valeur saisie dans le contexte.

## 4. Responsabilités : infrastructure et exploitation

**`infra/stacks/config.py`** : paramètres par environnement (`staging`, `prod`) : région, domaine, tailles de tâches, nombres d'instances.

**`infra/stacks/network_stack.py`** : VPC, sous-réseaux, passerelle NAT, groupes de sécurité.

**`infra/stacks/app_stack.py`** (reçoit les étiquettes d'images en paramètres de contexte `apiImageTag` et `webImageTag` ; le déploiement d'une nouvelle version de l'application est un `cdk deploy` de cette pile) :
- dépôts ECR (dans une pile partagée `SoroNuaPredict-shared` pour être créés une seule fois) ;
- cluster ECS et services `api`, `web`, `worker` avec contrôles de santé, disjoncteur de déploiement et mise à l'échelle ;
- ALB avec règles `/api/*` vers `api` et `/auth/v1/*` vers le groupe cible de l'hôte de données (créé par `data_stack.py`) ;
- certificat ACM, enregistrement DNS Route 53 ;
- secret Secrets Manager (créé vide, rempli à la main une fois, voir `ENV_SETUP.md`) ;
- groupes de journaux CloudWatch (rétention 30 jours).

**`infra/stacks/monitoring_stack.py`** : alarmes CloudWatch et sujet SNS.

**`infra/stacks/pipeline_stack.py` (pile `SoroNuaPredict-cicd`, déployée une fois dans le compte)** :
- connexion GitHub ;
- projets CodeBuild et pipelines décrits dans `CI_CD.md` ;
- sujets SNS d'approbation.

**`buildspecs/*.yml`** : étapes exécutées par CodeBuild, décrites dans `CI_CD.md`.

**`infra/stacks/data_stack.py`** : hôte de données de l'environnement :
- instance EC2 en sous-réseau privé, profil IAM limité (SSM, lecture du secret `data`, écriture dans le compartiment de sauvegarde, lecture du compartiment de déploiement) ;
- volume EBS chiffré, plan AWS Backup ;
- compartiments S3 de sauvegarde et de déploiement ;
- enregistrement DNS privé `data.<env>.internal` ;
- groupe de sécurité (`ARCHITECTURE.md` 5) ;
- groupe cible de l'ALB pour `/auth/v1/*` ;
- script de démarrage installant Docker, Docker Compose, l'agent CloudWatch et l'unité `supabase-stack.service`.

**`deploy/supabase/docker-compose.yml`** :
- pile officielle Supabase réduite à `supabase-db`, `supabase-auth`, `supabase-rest`, `supabase-storage`, `supabase-kong`, plus `supabase-meta` et `supabase-studio` sous le profil `local`, et `db-backup` sous le profil `aws` ;
- images figées par digest (`CONVENTIONS.md` 1.2) ;
- ni `name:` ni `container_name` : le nom du projet (`soronua-predict`) vient du fichier racine qui l'inclut, et aucun nom de conteneur imposé n'évite les collisions avec les autres projets de la machine (D-008) ;
- chaque service reçoit une liste explicite de variables (`environment:`), jamais `env_file` ; un secret vide fait échouer la composition (`${VAR:?...}`) ;
- ports publiés : seulement Kong (`${KONG_BIND_ADDRESS:-127.0.0.1}:${KONG_HTTP_PORT:-54321}:8000`, la même ligne sert sur AWS avec `0.0.0.0` et `8000`) et Studio (`127.0.0.1:${STUDIO_HOST_PORT:-54323}:3000`, profil `local`) ; Postgres, PostgREST, Storage, Auth et `postgres-meta` n'en publient aucun (D-051) ;
- `supabase-kong` : entrypoint qui développe le gabarit `kong.yml` (`eval "echo ..."`), plugins limités à `cors,key-auth,acl,request-termination` ;
- `supabase-db` : scripts d'initialisation `db/roles.sql` et `db/jwt.sql` montés en lecture seule ;
- volumes nommés pour la base (`supabase-db-data`, `supabase-db-config`) et les fichiers (`supabase-storage-data`) ;
- contrôles de santé sur chaque service ;
- pilote de journaux `awslogs` sur AWS ;
- réglages de l'authentification : inscription désactivée (valeur fixe, pas une variable), jetons d'une heure, rotation des jetons de rafraîchissement, mot de passe de 10 caractères au moins (`SECURITY_NOTES.md` 4.4), SMTP par variables (`ENV_SETUP.md` 4) ; les gabarits d'e-mails servis par `web` s'ajoutent en phase 2 (D-053).

**`deploy/supabase/apply.sh`** : idempotent ; échoue si un service n'est pas sain après 5 minutes (le pipeline s'arrête alors avant les migrations).

**`tools/Dockerfile`** : image `soronua-predict-toolbox` qui contient les outils transverses aux versions figées (Python/uv, Node, Supabase CLI, AWS CLI, CDK, gitleaks, pre-commit) ; le `Makefile` et les buildspecs exécutent dedans `uv lock`, gitleaks, pre-commit, la Supabase CLI, l'AWS CLI et CDK. Les contrôles propres à un composant tournent dans les images du projet : Python (ruff, mypy, pytest, pip-audit) dans l'image `api` cible `dev`, contrôles web dans l'image `web` cible `dev`, Playwright dans le service `e2e`. Rien n'est installé directement sur la machine de développement ni sur l'environnement CodeBuild : l'hôte n'a besoin que de `make`, Docker, git et `gh`.

**`docker-compose.yml`** (phase 1) : inclut `deploy/supabase/docker-compose.yml` (directive `include` avec `env_file: deploy/supabase/.env`) ; services `redis`, `api`, `web` et `mailpit` (lancés par `make up`, avec la pile Supabase et le profil `local`), plus `toolbox` (profil `tools`, reçoit `DATABASE_URL` pour la Supabase CLI), `pgtap` (profil `tools`, `pg_prove` figé par digest, monte `supabase/tests/database` en lecture seule) et `e2e` (profil `e2e`). `api` reçoit `SUPABASE_URL`, `SUPABASE_ANON_KEY` et `SUPABASE_SERVICE_ROLE_KEY` ; `web` ne reçoit aucune variable Supabase avant la phase 2 et jamais de clé de service. Le worker (phase 6) et `db-backup` (phase 17) arrivent avec leurs phases. Tous les contextes de construction sont la racine du dépôt (`context: .`) ; chaque service reçoit une liste explicite de variables (`environment:`), jamais `env_file: .env`, afin que la clé de service ne puisse pas atteindre `web`.

**`supabase/config.toml`** : présent uniquement parce que la Supabase CLI l'exige pour gérer les migrations ; la pile locale n'est **pas** lancée par la CLI mais par `deploy/supabase/docker-compose.yml`. Contenu minimal : `project_id`, `[db] major_version = 17`, `[db.migrations] enabled = true`.

**`supabase/migrations/`** (phase 1) : `20261003135336_init_enums_profiles.sql` et `20261003135339_audit_log.sql` (migrations 1 et 2 de `DATA_MODEL.md` 7, jamais modifiées une fois appliquées). **`supabase/tests/database/`** : tests pgTAP `001_types` à `090_global_rls_and_privileges` (`*.test.sql`, un fichier = une session) et `_helpers.psql` (inclus par `\ir`, extension `.psql` pour que `pg_prove --ext .sql` ne l'exécute pas comme un test ; tout ce qu'il crée vit dans la transaction du test).

**`Makefile`** (phase 1) : nouvelles cibles `db-migrate`, `db-new-migration name=...`, `db-reset`, `db-shell`, `pull` ; `env-local` génère aussi `deploy/supabase/.env` et les clés ; `up` démarre toute la pile puis migre ; `test-db` lance pgTAP via `pg_prove` ; `guards` contrôle la configuration Compose résolue (`ENV_SETUP.md` 7.4).

---

## 5. Données et apprentissage

### 5.1 Correspondance des colonnes

| Colonne CSV | Nom interne | Groupe |
|---|---|---|
| CustomerID | `external_id` | identifiant (ignoré par le modèle) |
| Age | `age` | audience |
| Gender | `gender` | audience |
| Income | `income` | audience |
| CampaignChannel | `campaign_channel` | plan |
| CampaignType | `campaign_type` | plan |
| AdSpend | `ad_spend` | plan |
| ClickThroughRate | `click_through_rate` | cible |
| ConversionRate | `conversion_rate` | cible |
| WebsiteVisits | `website_visits` | cible |
| PagesPerVisit | `pages_per_visit` | engagement |
| TimeOnSite | `time_on_site` | engagement |
| SocialShares | `social_shares` | engagement |
| EmailOpens | `email_opens` | engagement |
| EmailClicks | `email_clicks` | engagement |
| PreviousPurchases | `previous_purchases` | audience |
| LoyaltyPoints | `loyalty_points` | audience |
| AdvertisingPlatform | `advertising_platform` | optionnel |
| AdvertisingTool | `advertising_tool` | optionnel |
| Conversion | `conversion` | ignoré (résultat individuel) |

Les 20 colonnes sont obligatoires dans tout fichier importé, avec ces noms exacts (sensibles à la casse), dans n'importe quel ordre.

### 5.2 Variables d'entrée des modèles

- Numériques (10) : `ad_spend`, `age`, `income`, `previous_purchases`, `loyalty_points`, `pages_per_visit`, `time_on_site`, `social_shares`, `email_opens`, `email_clicks`.
- Catégorielles (3) : `campaign_channel`, `campaign_type`, `gender`, codées en indicateurs 0/1 (une colonne par valeur de l'énumération, toutes les valeurs de l'énumération présentes même si absentes des données).
- Optionnelles (2) : `advertising_platform`, `advertising_tool`. Incluses **si et seulement si** elles ont au moins 2 valeurs distinctes dans les lignes d'apprentissage du périmètre. Leurs catégories sont alors celles observées au moins 5 fois, les autres sont regroupées sous `__other__`. Une valeur saisie inconnue est codée `__other__`.
- Ordre des colonnes : figé dans `bundle.json` (`feature_columns`) et réutilisé tel quel à la prédiction.

### 5.3 Lignes de test (holdout)

`is_holdout = int(sha256(f"{source}:{external_id}").hexdigest()[:8], 16) % 5 == 0` : environ 20 % des lignes, calculé à l'insertion, jamais modifié. Une même ligne est donc toujours de test, quelle que soit la version.

### 5.4 Apprentissage

- Périmètre `all` : lignes de tous les imports `ready` dont `ready_at <= data_cutoff_at`. Périmètre `agency_only` : même règle avec `source = 'agency'`.
- Minimums : 200 lignes d'apprentissage et 50 lignes de test, sinon échec `NOT_ENOUGH_DATA` avec le message du PRD US-08.
- Trois modèles `XGBRegressor` indépendants, un par cible, mêmes paramètres (`ml/params.py`) :
  `n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=1, reg_lambda=1.0, objective="reg:squarederror", tree_method="hist", random_state=42, n_jobs=2`.
- Pas de recherche d'hyperparamètres en première version (résultat reproductible et rapide).

### 5.5 Évaluation et comparaison

- Sur les lignes de test du périmètre : MAE, RMSE, R², et `baseline_mae` (erreur d'une prédiction constante égale à la moyenne d'apprentissage).
- Comparaison : la version active (si elle existe) est évaluée **sur les mêmes lignes de test**. `mean_mae_ratio = moyenne(new_mae / previous_mae)` sur les trois cibles ; `is_activatable = (pas de version active) ou (mean_mae_ratio <= 1.0)`.

### 5.6 Paquet d'artefacts

Chemin Storage : `model-artifacts/versions/<model_version_id>/`.
- `click_through_rate.json`, `conversion_rate.json`, `website_visits.json` : modèles XGBoost (`save_model`, format JSON).
- `bundle.json` :

```json
{
  "bundle_schema_version": 1,
  "model_version_id": "uuid",
  "trained_at": "2026-09-23T10:00:00Z",
  "data_scope": "all",
  "feature_columns": ["ad_spend", "age", "...", "campaign_channel=Email", "..."],
  "features_used": ["ad_spend", "age", "..."],
  "optional_categories": {"advertising_platform": [], "advertising_tool": []},
  "training_ranges": {"ad_spend": {"min": 100.05, "max": 9997.91}},
  "engagement_defaults": {
    "by_channel_type": {"Email|Conversion": {"pages_per_visit": 5.6, "time_on_site": 7.8, "social_shares": 50, "email_opens": 9, "email_clicks": 4, "n": 390}},
    "by_channel": {"Email": {"...": 0, "n": 1557}},
    "all": {"...": 0, "n": 8000}
  },
  "scoring_reference": {
    "by_type": {"Conversion": {"click_through_rate": [0.01, "..."], "estimated_leads": [0.0, "..."], "estimated_cost_per_result": [12.5, "..."], "n": 2077}},
    "all_types": {"...": []},
    "thresholds": {"low_below": 41.2, "high_from": 58.9}
  },
  "metrics": {"...": "DATA_MODEL.md 4.7"},
  "global_importance": {"...": "DATA_MODEL.md 4.7"}
}
```

Les tableaux de référence contiennent les valeurs **réelles** des lignes du périmètre (apprentissage + test), triées par ordre croissant ; un coût par résultat infini (prospects nuls) est stocké comme `null` et placé en fin de tableau.

### 5.7 Déroulé d'un travail (worker)

1. `dequeue_blocking()` renvoie `{"model_version_id": ...}` ou rien (nouvelle boucle).
2. Mise à jour conditionnelle `status = 'running', started_at = now()` **seulement si** `status = 'queued'` ; sinon `ack` et abandon (travail déjà traité).
3. Lecture des lignes du périmètre par pages de 1 000.
4. `ml.training.train()`, puis `ml.evaluation.evaluate()`, puis évaluation de la version active sur les mêmes lignes de test, puis `domain.comparison.compare()`.
5. Construction des références de score, des valeurs de pré-remplissage, de l'importance globale.
6. Dépôt des 4 fichiers dans Storage.
7. Mise à jour `status = 'succeeded'` avec métriques, comparaison, importance, `is_activatable`, `features_used`, comptes, `artifact_prefix`, `finished_at`. Audit `model.training_succeeded`.
8. `ack`.
9. En cas d'exception : `status = 'failed'`, `error_message` lisible (message métier ou "Training failed unexpectedly. Reference: <event_id>"), audit `model.training_failed`, capture Sentry avec `model_version_id`, `ack`.
10. Au démarrage : `requeue_orphans()` remet en file les éléments de la liste de traitement ; toute version `running` depuis plus de 60 minutes passe en `failed` ("Training was interrupted.").
11. Délai maximal d'un travail : 30 minutes, au-delà échec "Training took too long."

---

## 6. Calculs de prédiction

### 6.1 Prédiction
`Predictor.predict(inputs)` renvoie pour chaque saisie les trois chiffres, bornés : `click_through_rate` et `conversion_rate` dans [0, 1], `website_visits` ≥ 0.

### 6.2 Dérivés
- `estimated_leads = website_visits × conversion_rate`, arrondi à 2 décimales pour l'affichage uniquement (les calculs utilisent la valeur complète).
- `estimated_cost_per_result = ad_spend / estimated_leads` si `estimated_leads > 0`, sinon `None`.

### 6.3 Notes (0 à 100)
Référence = `scoring_reference.by_type[campaign_type]` si `n >= 30`, sinon `all_types` (avec l'avertissement `REFERENCE_FALLBACK`).

`percentile_rank(x, sorted_ref) = 100 × (nb(ref < x) + 0,5 × nb(ref == x)) / n` (recherche dichotomique).
- Note du taux de clic = `percentile_rank(ctr, ref.click_through_rate)`.
- Note des prospects = `percentile_rank(leads, ref.estimated_leads)`.
- Note du coût par résultat = `100 − percentile_rank(cpr, ref.estimated_cost_per_result)` où les valeurs `null` de la référence comptent comme plus grandes que tout nombre ; si `cpr is None`, note = 0.

### 6.4 Score et niveau
- `score = (note_ctr + note_leads + note_cpr) / 3`, arrondi à 1 décimale.
- Seuils : au moment de l'apprentissage, le score de chaque ligne du périmètre est calculé avec ses valeurs réelles contre la référence de son type ; `low_below` = 1er tercile, `high_from` = 2e tercile de ces scores (`numpy.quantile`, méthode linéaire).
- Niveau : `low` si `score < low_below`, `high` si `score >= high_from`, sinon `medium`.

### 6.5 Valeurs de pré-remplissage
Moyennes des 5 champs d'engagement sur les lignes du périmètre, dans cet ordre de repli :
1. même canal et même type si `n >= 30` (`basis = channel_and_type`) ;
2. sinon même canal si `n >= 30` (`basis = channel`) ;
3. sinon toutes les lignes (`basis = all`).

Arrondis :
- `pages_per_visit` et `time_on_site` : 1 décimale ;
- les trois autres : entier le plus proche.

### 6.6 Facteurs
`Predictor.contributions(input)` renvoie pour chaque cible les contributions par colonne (sans le biais). Les colonnes codées d'un même champ sont additionnées. Les 5 plus fortes en valeur absolue sont gardées ; `direction = "up"` si contribution > 0, sinon `"down"`. Importance globale : moyenne des valeurs absolues sur les lignes de test, regroupée par champ, normalisée à 1.

### 6.7 Recommandations
Leviers et valeurs candidates (un levier modifié à la fois, les autres champs inchangés, engagement attendu inchangé) :

| Levier | Candidates |
|---|---|
| `ad_spend` | valeur actuelle × {0,5 ; 0,6 ; 0,7 ; 0,8 ; 0,9 ; 1,1 ; 1,2 ; 1,3 ; 1,4 ; 1,5}, arrondie à 2 décimales, dans les bornes |
| `campaign_channel` | les 4 autres valeurs |
| `campaign_type` | les 3 autres valeurs |
| `age` | milieux des tranches 18-24, 25-34, 35-44, 45-54, 55+ : {21, 30, 40, 50, 62}, sauf la tranche actuelle |
| `income` | milieux des tranches <45k, 45-70k, 70-95k, 95-120k, 120k+ : {32500, 57500, 82500, 107500, 135000}, sauf la tranche actuelle |
| `gender` | l'autre valeur |
| `previous_purchases` | {0, 3, 6, 9}, sauf la valeur actuelle |
| `loyalty_points` | {0, 1250, 2500, 3750, 4999}, sauf la valeur actuelle |
| `advertising_platform`, `advertising_tool` | si utilisés par le modèle : les autres catégories connues |

Algorithme :
1. Construire toutes les variantes (environ 40) et les prédire en **un seul lot**.
2. Calculer le score de chaque variante selon 6.2 à 6.4 (avec le type de la variante pour la référence).
3. Pour chaque levier, garder la meilleure variante.
4. Éliminer celles dont `score_gain < 5.0`.
5. Trier par gain décroissant (à égalité, dans l'ordre du tableau ci-dessus) et garder les 3 premières.
6. `status = "found"` si au moins une, sinon `"none_significant"`.

### 6.8 Avertissements
- `LOW_MODEL_RELIABILITY` : si `overall_reliability == "low"`.
- `OUT_OF_TRAINING_RANGE` : pour chaque champ numérique hors de `training_ranges[champ]`.
- `REFERENCE_FALLBACK` : voir 6.3.

---

## 7. Signatures des fonctions non triviales

```python
# domain/csv_validation.py
@dataclass(frozen=True)
class CsvIssue:
    row: int | None          # numéro de ligne du fichier, en-tête = 1 ; None pour une erreur de fichier
    column: str | None
    issue: str               # code court : "missing_column", "out_of_range", "formula_injection", ...
    message: str             # phrase anglaise

@dataclass(frozen=True)
class CsvValidationResult:
    frame: pd.DataFrame | None       # colonnes internes, types stricts ; None si erreurs
    issues: list[CsvIssue]
    total_issue_count: int

def validate_dataset_csv(content: bytes, *, max_rows: int = 50_000, max_reported: int = 100) -> CsvValidationResult: ...

# domain/holdout.py
def is_holdout(source: str, external_id: int) -> bool: ...

# domain/features.py
@dataclass(frozen=True)
class FeatureSpec:
    numeric: tuple[str, ...]
    categorical: dict[str, tuple[str, ...]]
    optional_categories: dict[str, tuple[str, ...]]
    columns: tuple[str, ...]

def build_feature_spec(train_frame: pd.DataFrame) -> FeatureSpec: ...
def encode(frame: pd.DataFrame, spec: FeatureSpec) -> np.ndarray: ...
def training_ranges(frame: pd.DataFrame, spec: FeatureSpec) -> dict[str, dict[str, float]]: ...

# domain/derived_metrics.py
def estimated_leads(website_visits: float, conversion_rate: float) -> float: ...
def estimated_cost_per_result(ad_spend: float, leads: float) -> float | None: ...

# domain/scoring.py
@dataclass(frozen=True)
class ScoringReference:
    by_type: dict[str, ReferenceArrays]
    all_types: ReferenceArrays
    low_below: float
    high_from: float

def build_scoring_reference(frame: pd.DataFrame) -> ScoringReference: ...
def percentile_rank(value: float, sorted_values: np.ndarray) -> float: ...
def score_campaign(ctr: float, leads: float, cpr: float | None, campaign_type: str,
                   reference: ScoringReference) -> PerformanceScore: ...
def level_for(score: float, reference: ScoringReference) -> Literal["low", "medium", "high"]: ...

# domain/engagement_defaults.py
def build_engagement_defaults(frame: pd.DataFrame) -> EngagementDefaults: ...
def defaults_for(defaults: EngagementDefaults, channel: str, campaign_type: str) -> EngagementValues: ...

# domain/explanations.py
def aggregate_contributions(contribs: np.ndarray, spec: FeatureSpec) -> dict[str, float]: ...
def top_drivers(aggregated: dict[str, float], values: Mapping[str, object], k: int = 5) -> list[Driver]: ...
def global_importance(contribs_by_target: dict[str, np.ndarray], spec: FeatureSpec) -> dict[str, list[ImportanceShare]]: ...

# domain/recommendations.py
def candidate_variants(base: CampaignValues, spec: FeatureSpec) -> list[Variant]: ...
def select_recommendations(base_score: float, scored: Sequence[ScoredVariant],
                           min_gain: float = 5.0, max_items: int = 3) -> RecommendationResult: ...

# domain/comparison.py
def compare(new: Metrics, previous: Metrics | None) -> Comparison | None: ...
def is_activatable(comparison: Comparison | None) -> bool: ...

# ml/training.py
def train(frame: pd.DataFrame, *, data_scope: str, model_version_id: UUID) -> TrainedBundle: ...

# ml/evaluation.py
def evaluate(predictor: Predictor, holdout: pd.DataFrame) -> Metrics: ...

# ml/bundle.py
def save_bundle(bundle: ModelBundle, directory: Path) -> list[Path]: ...
def load_bundle(directory: Path) -> ModelBundle: ...

# ml/predictor.py
class Predictor:
    def __init__(self, bundle: ModelBundle) -> None: ...
    @property
    def version_id(self) -> UUID: ...
    def predict(self, inputs: Sequence[CampaignValues]) -> list[TargetValues]: ...
    def contributions(self, value: CampaignValues) -> dict[str, np.ndarray]: ...

# services/model_registry.py
class ModelRegistry:
    def current(self) -> Predictor | None: ...          # vérifie le pointeur au plus toutes les 30 s
    def refresh(self, *, force: bool = False) -> None: ...

# services/prediction_service.py
def simulate(user: CurrentUser, payload: CampaignInput, *, registry: ModelRegistry) -> PredictionResult: ...
def save(user: CurrentUser, db: UserClient, payload: SavePredictionRequest, *, registry: ModelRegistry) -> PredictionResult: ...

# services/upload_service.py
def import_agency_file(user: CurrentUser, db: UserClient, *, file_name: str, content: bytes,
                       anonymization_confirmed: bool) -> UploadRecord: ...

# services/training_request_service.py
def request_training(user: CurrentUser, db: UserClient, data_scope: DataScope) -> ModelVersionRecord: ...

# services/training_job.py
def run_training_job(model_version_id: UUID, *, service_db: ServiceClient, storage: StorageRepo) -> None: ...

# services/activation_service.py
def activate(user: CurrentUser, db: UserClient, version_id: UUID, expected_active_id: UUID | None) -> ModelVersionRecord: ...

# infra/queue.py
def enqueue(job: TrainingJob) -> None: ...
def dequeue_blocking(timeout_seconds: int = 20) -> TrainingJob | None: ...
def ack(job: TrainingJob) -> None: ...
def requeue_orphans() -> int: ...

# infra/rate_limit.py
def check(scope: str, user_id: UUID, *, limit: int, window_seconds: int) -> None: ...   # lève AppError RATE_LIMITED

# infra/supabase_clients.py (phase 1)
def get_anon_client(settings: Settings | None = None) -> Client: ...                       # clé publique, sans jeton
def get_user_client(access_token: str, settings: Settings | None = None) -> Client: ...    # nouveau client par requête
def get_service_client(settings: Settings | None = None) -> Client: ...                    # instance unique ; liste fermée d'appelants

# services/readiness_service.py (phase 1)
def check_database(settings: Settings, *, transport: httpx.BaseTransport | None = None) -> DatabaseCheck: ...

# infra/auth.py
def verify_access_token(token: str) -> TokenClaims: ...   # lève AppError UNAUTHENTICATED ou TOKEN_EXPIRED
```

```typescript
// lib/api/client.ts
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string,
              public details: ApiErrorDetail[], public requestId: string | null) { super(message); }
}
export async function apiFetch<T>(path: string, init?: { method?: string; body?: unknown; formData?: FormData; signal?: AbortSignal }): Promise<T>;

// hooks/use-simulation.ts
export function useSimulation(input: CampaignInput | null): {
  data: PredictionResult | undefined; isFetching: boolean; error: ApiError | null;
};

// hooks/use-form-draft.ts
export function useFormDraft(form: UseFormReturn<CampaignFormValues>): { clearDraft: () => void };

// lib/format.ts
export function formatRate(value: number): string;        // 0.1542 -> "15.42%"
export function formatCount(value: number, decimals?: number): string;
export function formatUsd(value: number | null): string;  // null -> "n/a"
```

## 8. Gestion d'état côté interface

| Type d'état | Outil | Règle |
|---|---|---|
| Données serveur | TanStack Query v5 | Toute donnée venant de l'API passe par un hook de `hooks/`. Clés centralisées dans `lib/api/query-keys.ts`. `staleTime` 30 s par défaut, 0 pour les versions en cours d'apprentissage (interrogation 3 s). Invalidation explicite après chaque écriture. |
| Formulaire | React Hook Form + résolveur Zod | Un seul formulaire `CampaignForm`. Validation Zod identique aux bornes de `API_SPEC.md` 5.1. |
| Session | `@supabase/ssr` + `SessionProvider` | La session n'est jamais copiée ailleurs. |
| Brouillon | `sessionStorage` via `useFormDraft` | Uniquement les valeurs du formulaire, jamais de jeton. |
| État d'affichage local | `useState` | Dialogues, onglets, sélection. |
| État global | aucun magasin global (pas de Redux, Zustand ni Context de données) | Le cache TanStack Query suffit. |

## 9. Conventions de nommage

| Élément | Convention | Exemple |
|---|---|---|
| Fichiers Python | `snake_case.py` | `prediction_service.py` |
| Fonctions et variables Python | `snake_case` | `score_campaign` |
| Classes Python | `PascalCase` | `ModelRegistry` |
| Constantes | `UPPER_SNAKE_CASE` | `MIN_SCORE_GAIN` |
| Fichiers TypeScript et React | `kebab-case.ts(x)` | `results-panel.tsx` |
| Composants React | `PascalCase` | `ResultsPanel` |
| Hooks | `useCamelCase`, fichier `use-kebab.ts` | `useSimulation` |
| Types TypeScript | `PascalCase` | `PredictionResult` |
| Tables, colonnes, types SQL | `snake_case`, tables au pluriel | `model_versions.data_scope` |
| Index SQL | `<table>_<colonnes>_idx`, unicité `_unique` | `predictions_user_created_idx` |
| Politiques RLS | `<table>_<action>_<qui>` | `predictions_select_own` |
| Routes API | `kebab-case`, noms au pluriel | `/api/v1/admin/model-versions` |
| Champs JSON | `snake_case` | `estimated_cost_per_result` |
| Codes d'erreur | `UPPER_SNAKE_CASE` | `NO_ACTIVE_MODEL` |
| Clés Redis | `domaine:sous-domaine:id` | `auth:profile:<uuid>` |
| Variables d'environnement | `UPPER_SNAKE_CASE` | `SUPABASE_URL` |
| Tests Python | `test_<comportement_attendu>` | `test_cost_note_is_zero_when_no_leads` |
| Tests Playwright | `<zone>.spec.ts`, titres en phrases anglaises | `marketer cannot open another user's prediction` |
| Branches | voir `CONVENTIONS.md` | `phase/09-prediction-form` |
