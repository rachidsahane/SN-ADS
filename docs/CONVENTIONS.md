# CONVENTIONS.md : Règles de code et de collaboration

Document de référence n°7 sur 13.

---

## 1. Versions figées

### 1.1 Règle de figement
- Les versions ci-dessous sont des **séries**. À la phase 0, Claude Code installe la dernière version corrective disponible de chaque série et la fige :
  - Python : `==` exact dans `pyproject.toml`, `uv.lock` versionné ;
  - Node : version exacte sans `^` ni `~` dans `package.json`, `package-lock.json` versionné, `save-exact=true` dans `.npmrc`.
- Claude Code remplace ensuite, **dans ce document**, chaque série par la version exacte installée (colonne "Version figée"). Valeurs relevées le 2026-10-03 (phase 0) dans `uv.lock`, `package-lock.json` et les `Dockerfile`.
- Les images Docker sont figées par **digest d'index multi-architecture** (`image:tag@sha256:...`), reporté dans les `Dockerfile` et `docker-compose.yml`.
- Plusieurs versions diffèrent de la série initialement prévue : correctifs de sécurité imposés par `pip-audit` et `npm audit` (jamais ignorés, voir section 2) et contraintes de compatibilité. Elles sont justifiées dans `docs/decisions.md` (D-014a à D-014e pour les montées de dépendances, D-015 pour les audits).
- Aucune montée de version majeure ou mineure sans une entrée dans `docs/decisions.md`. Les correctifs de sécurité proposés par Dependabot sont acceptés s'ils passent tous les contrôles.

### 1.2 Environnements d'exécution

| Élément | Série | Version figée |
|---|---|---|
| Python | 3.12 | 3.12.15 (image `python:3.12-slim-bookworm`) |
| uv (gestionnaire Python) | 0.5 | 0.5.31 (image `ghcr.io/astral-sh/uv:0.5.31@sha256:7bff3c3776ec467fc1437960f2c469d8beb30f536a6465a3350c647ccd260ec2` pour les images `api` ; paquet pip dans le toolbox) |
| Node.js | 22 (LTS) | 22.23.3 |
| npm | 10 | 10.9.9 |
| Supabase CLI (paquet npm `supabase`, `package.json` et `package-lock.json` à la racine, installé dans le toolbox) | 2.x | 2.119.0 |
| AWS CDK (`aws-cdk-lib` et CLI `aws-cdk`) | 2.173 | CLI `aws-cdk` 2.173.4 (installée dans le toolbox) ; `aws-cdk-lib` 2.173.4 et `constructs` 10.4.5 figés en phase 17 |
| AWS CLI v2 | 2.x | 2.37.9 (toolbox) |
| pre-commit | 4.x | 4.6.2 (toolbox ; jamais installé sur la machine hôte, voir D-012) |
| gitleaks | 8.x | 8.30.1 (toolbox, archive vérifiée par somme de contrôle) |
| Image Docker Python | `python:3.12-slim-bookworm` | `python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3` |
| Image Docker Node | `node:22-bookworm-slim` | `node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c` |
| Image Redis locale | `redis:7.4-alpine` | `redis:7.4-alpine@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499` |
| Images de la pile Supabase auto-hébergée, miroir `public.ecr.aws/supabase/*` (mêmes images que Docker Hub, sans limite de débit), digests d'index multi-architecture figés en phase 1 dans `deploy/supabase/docker-compose.yml` (détail ci-dessous, D-046) | ensemble cohérent de la Supabase CLI 2.119.0, plus `storage-api` du compose officiel du 2026-10-03 | voir le tableau « Images de la pile Supabase » ci-dessous |
| Image Mailpit locale | `public.ecr.aws/supabase/mailpit` (série 1.x) | `public.ecr.aws/supabase/mailpit:v1.30.2@sha256:37a38e48e9338cd7e89dfeb487f37b02ebfcd9cb23111bed2d345e79d37d6dd6` |
| Image pgTAP (service `pgtap`, `pg_prove`) | `public.ecr.aws/supabase/pg_prove` (série 3.x) | `public.ecr.aws/supabase/pg_prove:3.36@sha256:eda7c5e68719e9c8287e78c017118407b48df904a51c935f5ab6098b8c0bc6bc` (D-048) |
| Image toolbox | `soronua-predict-toolbox`, construite depuis `tools/Dockerfile` (base `python:3.12-slim-bookworm`, Node.js 22, uv, pre-commit, Supabase CLI, AWS CLI v2, AWS CDK, gitleaks) | versions internes figées dans le Dockerfile (arguments `UV_VERSION`, `PRE_COMMIT_VERSION`, `GITLEAKS_VERSION`, `AWSCLI_VERSION`, `CDK_VERSION`) et rappelées ci-dessus ; `make toolbox-versions` les affiche |
| Docker Engine | 29 | 29.7.2 (poste de développement) |
| Docker Compose | v2 (directive `include` requise, version 2.20 ou plus) | v5.4.0 (voir D-032) |
| GNU Make (poste hôte) | 3.81 | 3.81 (le `Makefile` reste compatible avec cette version, voir D-011) |
| Image Playwright | `mcr.microsoft.com/playwright:v1.63.0-noble` | `mcr.microsoft.com/playwright:v1.63.0-noble@sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27` ; identique à `@playwright/test` 1.63.0 (contrôle `make guards`) |
| Image Trivy (analyse) | `aquasec/trivy:0.58.x` | `aquasec/trivy:0.58.2@sha256:665030f4d33a82c1e8d9d5e0453365842236723c1ee5cc3becca698268e66a56` (digest consigné seulement ; le service n'est créé qu'en phase 18) |

**Images de la pile Supabase** (phase 1, `deploy/supabase/docker-compose.yml`). Écarts avec le compose officiel du jour (Envoy à la place de Kong, gotrue v2.196.0, postgrest v14.17, postgres 17.6.1.136, studio 2026.09.07, `postgres-meta` v0.99.0) : Kong est conservé parce que l'architecture l'impose (D-047), et l'ensemble déjà testé et en cache de la CLI 2.119.0 est retenu, avec le `storage-api` du compose officiel (D-046). Politique de montée de version : une image de la pile n'est mise à jour que par une entrée dans `decisions.md`, le digest d'index vérifié (`docker buildx imagetools inspect`) et, en production, une sauvegarde préalable réussie.

| Service | Image figée |
|---|---|
| `supabase-db` | `public.ecr.aws/supabase/postgres:17.6.1.159@sha256:86a2e078779e5bdccda1f6f6c5063aa9779a322d1fface5fb408d051909b230f` |
| `supabase-auth` | `public.ecr.aws/supabase/gotrue:v2.195.0@sha256:362659ca70eaa75ba05bbaf963caa84c1c5afe5e8fbf0777e17b830dd5f0f60a` |
| `supabase-rest` | `public.ecr.aws/supabase/postgrest:v16.1@sha256:5922bde07147b82b1c9d8f749e48c1e5b99ebb233f3888bb7ab65f07cf4ac82d` |
| `supabase-storage` | `public.ecr.aws/supabase/storage-api:v1.74.0@sha256:f1546fac6d1c7e345428ac904bfaa7be7cecd50a1f549fe1cf38c628a7b15c85` |
| `supabase-kong` | `public.ecr.aws/supabase/kong:2.8.1@sha256:1b53405d8680a09d6f44494b7990bf7da2ea43f84a258c59717d4539abf09f6d` |
| `supabase-meta` | `public.ecr.aws/supabase/postgres-meta:v0.98.0@sha256:cef71ba901751dcc242cc685cf13786935ea8926820fb342f23bb0fbef77de5a` |
| `supabase-studio` | `public.ecr.aws/supabase/studio:2026.08.17-sha-0c1da8f@sha256:08dc77f12e08faacc55960fef1dce37fa73d16acb52abeb216aa23dc5e70824b` |

Phase 1 : aucune dépendance Python ni Node n'est ajoutée ni modifiée (`httpx` 0.27.2 et `supabase` 2.10.0 étaient déjà figés ; `deploy/supabase/generate_keys.py` n'utilise que la bibliothèque standard).

### 1.3 Bibliothèques Python (`apps/api`)

| Paquet | Série | Version figée |
|---|---|---|
| fastapi | 0.115 | 0.142.2 (starlette 1.7.0 en dépendance) |
| uvicorn[standard] | 0.34 | 0.34.3 |
| pydantic | 2.10 | 2.10.6 |
| pydantic-settings | 2.7 | 2.7.1 |
| python-multipart | 0.0.20 | 0.0.31 |
| supabase | 2.10 | 2.10.0 |
| pyjwt[crypto] | 2.10 | 2.15.1 |
| redis | 5.2 | 5.2.1 |
| xgboost | 2.1 | 2.1.4 |
| numpy | 2.2 | 2.2.6 |
| pandas | 2.2 | 2.2.3 |
| scikit-learn | 1.6 (métriques uniquement) | 1.6.1 |
| sentry-sdk[fastapi] | 2.19 | 2.19.2 |
| structlog | 24.4 | 24.4.0 |
| httpx | 0.28 | 0.27.2 (`supabase` 2.10.0 exige `httpx<0.28`, voir D-014c) |

Développement (groupe `dev` de `pyproject.toml`) :

| Paquet | Série | Version figée |
|---|---|---|
| pytest | 8.3 | 9.1.1 |
| pytest-cov | 6.0 | 6.0.0 |
| ruff | 0.8 | 0.8.6 |
| mypy | 1.14 | 1.14.1 |
| pip-audit | 2.7 | 2.7.3 |
| pandas-stubs | série compatible 2.2 | 2.2.3.250527 |

Notebooks (groupe `notebooks` de `pyproject.toml`, développement seulement, absent de l'image `prod`, voir D-044) :

| Paquet | Série | Version figée |
|---|---|---|
| jupyterlab | 4.6 | 4.6.4 |
| ipykernel | 7.4 | 7.4.0 |
| nbconvert | 7.17 | 7.17.1 |
| nbformat | 5.11 | 5.11.1 |
| matplotlib | 3.11 | 3.11.2 |

### 1.4 Bibliothèques TypeScript (`apps/web`)

| Paquet | Série | Version figée |
|---|---|---|
| next | 15.1 | 15.5.27 (voir D-014d) |
| react, react-dom | 19.0 | 19.0.8 |
| typescript | 5.7 | 5.7.3 |
| tailwindcss | 3.4 | 3.4.19 |
| tailwindcss-animate (plugin Tailwind, devDependency) | n/a | 1.0.7 |
| postcss | n/a | 8.5.28 (surcharge `overrides` pour `next`, voir D-014d) |
| @supabase/supabase-js | 2.47 | 2.47.16 |
| @supabase/ssr | 0.5 | 0.5.2 |
| @tanstack/react-query | 5.62 | 5.62.16 |
| react-hook-form | 7.54 | 7.54.2 |
| @hookform/resolvers | 3.9 | 3.9.1 |
| zod | 3.24 | 3.24.4 |
| recharts | 2.15 | 2.15.4 |
| @sentry/nextjs | 8.x (dernière 8) | **non installé** : ajouté en phase 16, en série 10.x (voir D-014e et D-024) |
| lucide-react | version installée par shadcn/ui, figée | 0.577.0 (installée directement en phase 0 ; `shadcn` et ses composants sont reportés en phase 2, voir D-028) |
| class-variance-authority, clsx, tailwind-merge | n/a (socle de shadcn/ui) | 0.7.1, 2.1.1, 2.6.1 |

Développement (`devDependencies` de `package.json`) :

| Paquet | Série | Version figée |
|---|---|---|
| eslint | 9.17 | 9.17.0 |
| @eslint/eslintrc | n/a (configuration à plat avec `next/*`) | 3.3.7 |
| eslint-config-next | 15.1 | 15.5.27 |
| prettier | 3.4 | 3.4.2 |
| prettier-plugin-tailwindcss | 0.6 | 0.6.14 |
| vitest | 2.1 | 3.2.7 |
| @vitest/coverage-v8 | n/a (assorti à vitest) | 3.2.7 |
| @testing-library/react | 16.1 | 16.1.0 |
| @testing-library/dom | n/a (pair de `@testing-library/react`) | 10.4.2 |
| @testing-library/user-event | 14.5 | 14.5.2 |
| jsdom | 25 | 25.0.1 |
| msw | 2.7 | 2.7.6 |
| @playwright/test | 1.49.1 | 1.63.0 (égal à l'étiquette de l'image Playwright, section 1.2) |
| openapi-typescript | 7.4 | 7.4.4 |
| @types/node, @types/react, @types/react-dom | n/a | 22.20.5, 19.0.14, 19.0.6 |

Non installés en phase 0 : `@sentry/nextjs` (phase 16), `@testing-library/jest-dom`, `@vitejs/plugin-react`, `autoprefixer`, `shadcn` (phase 2).

Note : si `recharts` 2.x signale un conflit avec React 19 sur `react-is`, ajouter dans `package.json` une surcharge `"overrides": {"react-is": "<version de react>"}` et le consigner dans `docs/decisions.md`. Constat de la phase 0 : aucun conflit (`react-is` 17.0.2 résolu), seule la surcharge `postcss` pour `next` est présente.

### 1.5 Infrastructure (`infra/`)

| Paquet | Série | Version figée |
|---|---|---|
| aws-cdk-lib | 2.173 (identique au tableau 1.2) | 2.173.4, figée en phase 17 (rien n'est créé dans `infra/` en phase 0) |
| constructs | 10.4 | 10.4.5, figée en phase 17 |
| pytest | 8.3 | à figer en phase 17, en cohérence avec la version de `apps/api` (9.1.1 à ce jour) |

Attention : `infra/` désigne ici le paquet CDK à la racine du dépôt (phase 17). Le dossier `apps/api/app/infra/` (observabilité, contexte de requête) est un module de l'API, sans rapport (voir section 2 et D-033).

## 2. Formatage et linting

### Python
- `ruff format` (longueur de ligne 100, guillemets doubles).
- `ruff check` avec les règles `E, F, W, I, B, UP, N, S, SIM, RUF, PL, C90` ; complexité cyclomatique maximale 10 ; `S` (sécurité) jamais désactivée globalement.
- `mypy --strict` sur `app/` (dossier `apps/api/app`) et, à partir de la phase 17, sur le paquet CDK `infra/` à la racine. Ne pas confondre `apps/api/app/infra/` (module de l'API : `observability.py`, `request_context.py`) et `infra/` à la racine (AWS CDK, phase 17) ; voir D-033. Aucun `Any` explicite sans commentaire justificatif. Aucun `# type: ignore` sans code d'erreur et justification.
- Imports absolus depuis `app.`.

### TypeScript
- `prettier` (largeur 100, points-virgules, guillemets doubles, virgules finales, tri des classes Tailwind).
- `eslint` (configuration à plat) : `next/core-web-vitals`, `next/typescript`, règles `no-console: error` (sauf `console.error` dans `lib/observability.ts`), `@typescript-eslint/no-explicit-any: error`, `react-hooks/exhaustive-deps: error`.
- `tsconfig` : `strict: true`, `noUncheckedIndexedAccess: true`, `noImplicitOverride: true`.

### SQL
- Mots-clés en minuscules, une instruction par ligne logique, identifiants en `snake_case`.
- Chaque migration commence par un commentaire décrivant son objet.

### Contrôle unique
`make check` exécute, contre la pile locale en conteneurs, dans cet ordre, et échoue au premier problème (9 étapes, telles qu'implémentées dans le `Makefile`) :
1. `up` : démarrage de toute la pile locale (`redis`, `api`, `web`, `mailpit`, pile Supabase, profil `local` compris), attente de leur état sain, puis application des migrations (`db-migrate`, idempotent, D-056) ;
2. `format-check` : formatage, vérification seule (`ruff format --check`, `prettier --check`) ;
3. `lint` : contrôle `guards` (version de `@playwright/test` égale à l'étiquette de l'image Playwright ; aucun `skip`/`only`/`xfail` sans identifiant `D-NNN` de `docs/decisions.md` ; et, depuis la phase 1, quatre contrôles sur la configuration Compose **résolue**, jamais affichée car elle contient des secrets : images figées par digest, aucun secret Supabase dans `web` ni `e2e`, aucun port publié hors `127.0.0.1` ni par `supabase-db`, `-rest`, `-storage`, `-meta`, `-auth`, clé de service limitée aux services autorisés), `ruff check`, `eslint`, `docker compose config -q`, `uv lock --check`. `generate_keys.py`, hors de `apps/api`, est vérifié (ruff format, ruff check, mypy) avec l'image `api` et ses règles, dossier monté en lecture seule (cible `STACK_PY`) ;
4. `typecheck` : `mypy --strict` et `tsc --noEmit` ;
5. `api-types-check` : régénération de `types.gen.ts` depuis l'API en marche, comparée au fichier versionné (échec si différence) ; `make api-types` le régénère ;
6. `test-unit` : pytest unitaires et Vitest avec seuils de couverture, puis les tests `unittest` de la pile (`deploy/supabase/tests` : `generate_keys.py`, contrôles Compose, `kong.yml`, scripts d'initialisation de la base, migrations) dans le `toolbox` ;
7. `test-integration` : pytest d'intégration et seuil de couverture global de l'API (`fail_under = 85`, lignes et branches combinées, voir D-022) ;
8. `test-db` : tests de base (pgTAP), réels depuis la phase 1 : migrations appliquées, extension pgTAP créée dans la base locale, puis `pg_prove` (service `pgtap`) sur `supabase/tests/database/*.test.sql` ; la cible échoue s'il n'y a aucun test (remplace le garde-fou de la phase 0, D-030 ; `pg_prove` plutôt que `supabase test db`, D-048) ;
9. `audit` : voir ci-dessous.

Les tests Playwright ne font pas partie de `make check` : ils se lancent par `make test-e2e` (service `e2e`).

**Où s'exécutent les contrôles** (voir D-007) : les contrôles Python (ruff, mypy, pytest, pip-audit, `uv lock --check`) tournent dans l'**image de développement `api`** (`docker compose run --rm --no-deps -T api ...`) ; les contrôles web (prettier, eslint, tsc, Vitest, `npm audit`) dans l'**image de développement `web`** ; Playwright dans le service **`e2e`** ; le **toolbox** sert à `uv lock`, `gitleaks`, `pre-commit`, Supabase CLI, AWS CLI, CDK et `make toolbox-versions`. Le poste hôte n'a besoin que de `make`, `docker`, `git` et `gh`. Raison : pas d'environnement virtuel ni de `node_modules` d'une autre architecture dans le dossier monté, et mêmes versions de Python et de Node qu'en production.

**Barrières d'audit** (voir D-015). Aucune vulnérabilité n'est ignorée sans entrée dans `docs/decisions.md` (pas de `--ignore-vuln` sinon) :
- Python : `pip-audit` sur les dépendances exportées de `uv.lock` ; toute vulnérabilité ayant un correctif bloque ;
- Web : `npm audit --omit=dev --audit-level=high` (script `audit:prod`) **et** `npm audit --audit-level=critical` (script `audit:all`, dépendances de développement comprises). La commande littérale `npm audit --audit-level=high` sur l'ensemble ne peut pas passer : la chaîne `tailwindcss` 3 et `eslint-config-next` (dépendances de développement seulement : `braces`, `micromatch`) n'a pas de correctif avant Tailwind 4 et `eslint-config-next` 16 ;
- Racine (outillage Supabase CLI, `package.json` racine) : `npm audit --audit-level=high` ; si un défaut sans correctif apparaît, repli sur `--audit-level=critical` avec une entrée dans `docs/decisions.md`.

**Crochets Git** (voir D-012) : `make hooks` écrit `.git/hooks/pre-commit` et `.git/hooks/commit-msg` (scripts `sh` qui appellent `make`) ; `pre-commit install` n'est jamais lancé et le binaire `pre-commit` de la machine hôte n'est jamais utilisé. À chaque commit, `make pre-commit` exécute dans le toolbox les crochets locaux de `.pre-commit-config.yaml` avec `pre-commit run --all-files` (refus des vrais fichiers `.env` et de `.DS_Store`, détection de secrets par `gitleaks`) ; le mode « fichiers indexés » n'est pas utilisé, car son étape de mise à l'écart (`stash`) a corrompu l'index Git (D-059) puis `format-check` et `lint`. Le message de commit est vérifié par `make commit-msg` (type, portée obligatoire, `: ` puis résumé, première ligne de 72 caractères au plus). Les crochets n'exécutent jamais les tests. Les commits directs sur `main`, `staging` et `dev` sont refusés.

**Tests d'abord et `make check`** (voir D-013) : un commit `test(...)` peut être rouge sur ses seuls nouveaux tests ; `make check` doit être vert avant chaque poussée et chaque pull request. La fusion en squash masquant l'ordre des commits, le corps du message de fusion liste les commits `test(...)` et `feat(...)`.

## 3. Messages de commit

Format Conventional Commits, en anglais :

```
<type>(<portée>): <résumé à l'impératif, 72 caractères max>

<corps facultatif : pourquoi, pas comment>

Refs: phase-<NN>
```

- Types : `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `ci`, `build`, `perf`, `security`.
- Portées : `api`, `worker`, `web`, `db`, `ml`, `infra`, `ci`, `docs`, `e2e`.
- Exemples :
  - `test(ml): add golden tests for scoring thresholds`
  - `feat(web): show performance level badge`
  - `fix(api): return 404 for other users' predictions`
- Approche TDD visible dans l'historique : le commit `test(...)` précède le commit `feat(...)` correspondant.
- Un commit = un changement cohérent qui passe `make check`.

## 4. Stratégie de branches

### 4.1 Branches permanentes

| Branche | Rôle | Déploiement | Écriture |
|---|---|---|---|
| `dev` | Construction | aucun ; contrôles automatiques | par pull request uniquement, depuis `phase/*`, `fix/*`, `chore/*` |
| `staging` | Validation | environnement staging | par pull request uniquement, **depuis `dev` uniquement** |
| `main` | Production | environnement production, après approbation manuelle | par pull request uniquement, **depuis `staging` uniquement** |

### 4.2 Branches de travail
- Créées depuis `dev` à jour : `phase/<NN>-<slug>` (une par phase de la ROADMAP), `fix/<slug>`, `chore/<slug>`.
- Durée de vie : une session de travail.
- Fusion dans `dev` par pull request en **squash**, titre au format commit.

### 4.3 Promotions
- `dev` vers `staging` : pull request "Promote dev to staging", fusion par **merge commit** (pas de squash, pour garder l'historique), après contrôles verts. Déclenche le déploiement staging et les tests Playwright sur staging.
- `staging` vers `main` : pull request "Release <date>", fusion par **merge commit**, uniquement quand :
  - le pipeline staging du dernier commit est vert ;
  - l'utilisateur a validé le comportement sur staging.
- Le pipeline de production s'arrête ensuite sur une **approbation manuelle** de l'utilisateur (e-mail AWS avec lien, voir `CI_CD.md`).
- Correctif urgent : branche `fix/<slug>` depuis `dev`, puis même chemin (`dev` → `staging` → `main`). Aucun raccourci vers `main`.

### 4.4 Protections GitHub (configurées en phase 0)
- `main` et `staging` :
  - pull request obligatoire, contrôle `checks` obligatoire (dès la phase 18), branche à jour exigée ;
  - pas de poussée forcée, pas de suppression, règles appliquées aussi aux administrateurs ;
  - historique linéaire non exigé (merge commits autorisés).
- `dev` : pull request obligatoire, pas de poussée forcée, pas de suppression.
- Un contrôle dans `buildspecs/checks.yml` refuse une pull request vers `staging` dont la source n'est pas `dev`, et vers `main` dont la source n'est pas `staging`.
- Avant la phase 18 (CI non encore en place) : `make check` doit passer localement avant toute fusion, et la description de la pull request en colle le résultat.

## 5. Patterns à suivre

- **Tests d'abord** : pour chaque comportement, écrire le test, le voir échouer, implémenter, le voir passer, remanier.
- **Une responsabilité par module** (voir `LLD.md` section 2). Une fonction de plus de 40 lignes ou une complexité supérieure à 10 doit être découpée.
- **Logique métier pure dans `domain/`**, sans accès réseau, testée sans simulacre.
- **Entrées validées à la frontière** (schémas Pydantic avec `extra="forbid"`, Zod côté interface), puis types stricts à l'intérieur.
- **Erreurs métier par `AppError` avec un code de `API_SPEC.md`**, jamais de chaîne libre.
- **Accès base avec le jeton de l'utilisateur** par défaut ; clé de service uniquement dans les modules listés dans `ARCHITECTURE.md` 2.5.
- **Idempotence** des commandes d'exploitation et du worker.
- **Configuration par variables d'environnement** lues uniquement dans `config.py` et `lib/env.ts`.
- **Journalisation structurée** avec `request_id` ; `capture()` Sentry sur toute exception non prévue.
- **Textes de l'interface centralisés** dans `lib/labels.ts`.
- **Accessibilité** : chaque champ a un libellé, erreurs reliées par `aria-describedby`, navigation au clavier fonctionnelle, contraste AA.
- **Décisions consignées** : toute décision technique non couverte par les documents est ajoutée dans `docs/decisions.md` (date, décision, raison en une phrase).

## 6. Patterns à proscrire

- Écrire du code avant son test.
- Lire `os.environ` ou `process.env` ailleurs que dans les modules de configuration. Python : uniquement `app/config.py` (garde automatisée par un test d'architecture sur l'arbre syntaxique). TypeScript : uniquement `src/lib/env.ts` et les exceptions ci-dessous, listées dans la surcharge ESLint de `eslint.config.mjs` (voir D-023) :
  - `next.config.ts` (`API_PROXY_TARGET` : les réécritures s'exécutent avant l'application) ;
  - `playwright.config.ts`, `vitest.config.ts` ;
  - `instrumentation.ts`, `instrumentation-client.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts` (chargés avant l'application ; les deux derniers n'existent qu'à partir de la phase 16) ;
  - `e2e/**/*.ts` et `tests/**/*.{ts,tsx}` (configuration des tests).
- Mettre un secret, une clé ou un mot de passe dans le code, les tests, les journaux, les messages d'erreur ou Sentry.
- Utiliser la clé de service Supabase hors des modules autorisés, ou l'exposer au navigateur.
- Interroger les tables Supabase depuis le navigateur.
- Construire une requête SQL par concaténation de chaînes.
- Désactiver RLS, une règle de lint ou un test pour "faire passer".
- `except Exception: pass`, ou attraper une erreur sans la remonter ni la journaliser.
- Faire confiance à une valeur calculée par l'interface (prédiction, score, rôle) : l'API recalcule tout.
- Renvoyer 403 pour une ressource d'un autre utilisateur (toujours 404).
- Ajouter une dépendance sans la figer, ou une dépendance hors de la liste sans entrée dans `docs/decisions.md`.
- Pousser directement sur `dev`, `staging` ou `main`, ou forcer une poussée.
- Modifier une migration déjà appliquée.
- Utiliser `localStorage` : le brouillon va dans `sessionStorage`, la session est gérée par Supabase.
- Utiliser Gemini ou tout autre modèle de langage en première version.
- Substituer un élément de la stack imposée.
- Installer ou exécuter un composant de la solution hors d'un conteneur (base de données, service, outil de développement ou de CI).
- Mettre à jour une image de la pile Supabase sans avoir lu ses notes de version, figé son digest et fait passer toute la suite de tests contre la nouvelle version.
