# CONVENTIONS.md : Règles de code et de collaboration

Document de référence n°7 sur 13.

---

## 1. Versions figées

### 1.1 Règle de figement
- Les versions ci-dessous sont des **séries**. À la phase 0, Claude Code installe la dernière version corrective disponible de chaque série et la fige :
  - Python : `==` exact dans `pyproject.toml`, `uv.lock` versionné ;
  - Node : version exacte sans `^` ni `~` dans `package.json`, `package-lock.json` versionné, `save-exact=true` dans `.npmrc`.
- Claude Code remplace ensuite, **dans ce document**, chaque série par la version exacte installée (colonne "Version figée").
- Aucune montée de version majeure ou mineure sans une entrée dans `docs/decisions.md`. Les correctifs de sécurité proposés par Dependabot sont acceptés s'ils passent tous les contrôles.

### 1.2 Environnements d'exécution

| Élément | Série | Version figée |
|---|---|---|
| Python | 3.12 | à remplir en phase 0 |
| uv (gestionnaire Python) | 0.5 | à remplir en phase 0 |
| Node.js | 22 (LTS) | à remplir en phase 0 |
| npm | 10 | à remplir en phase 0 |
| Supabase CLI (paquet npm `supabase`) | 2.x | à remplir en phase 0 |
| AWS CDK (`aws-cdk-lib` et CLI `aws-cdk`) | 2.173 | à remplir en phase 0 |
| Image Docker Python | `python:3.12-slim-bookworm` | digest figé en phase 0 |
| Image Docker Node | `node:22-bookworm-slim` | digest figé en phase 0 |
| Image Redis locale | `redis:7.4-alpine` | digest figé en phase 0 |
| Images de la pile Supabase auto-hébergée (`supabase/postgres`, `supabase/gotrue`, `postgrest/postgrest`, `supabase/storage-api`, `kong`, `supabase/postgres-meta`, `supabase/studio`) | versions du fichier `docker-compose` officiel de Supabase (dépôt `supabase/supabase`, dossier `docker/`) à la date de la phase 1 | digests figés en phase 1, reportés ici |
| Image Mailpit locale | `axllent/mailpit` (série 1.x) | digest figé en phase 1 |
| Image toolbox | `soronua-predict-toolbox`, construite depuis `tools/Dockerfile` (base `python:3.12-slim-bookworm`, Node.js 22, Supabase CLI, AWS CLI v2, AWS CDK, gitleaks) | versions internes figées dans le Dockerfile |
| Docker Compose | v2 (directive `include` requise) | à remplir en phase 0 |
| Image Playwright | `mcr.microsoft.com/playwright:v1.49.1-noble` | identique à `@playwright/test` |
| Image Trivy (analyse) | `aquasec/trivy:0.58.x` | à remplir en phase 0 |

### 1.3 Bibliothèques Python (`apps/api`)

| Paquet | Série |
|---|---|
| fastapi | 0.115 |
| uvicorn[standard] | 0.34 |
| pydantic | 2.10 |
| pydantic-settings | 2.7 |
| python-multipart | 0.0.20 |
| supabase | 2.10 |
| pyjwt[crypto] | 2.10 |
| redis | 5.2 |
| xgboost | 2.1 |
| numpy | 2.2 |
| pandas | 2.2 |
| scikit-learn | 1.6 (métriques uniquement) |
| sentry-sdk[fastapi] | 2.19 |
| structlog | 24.4 |
| httpx | 0.28 |
| Développement : pytest 8.3, pytest-cov 6.0, ruff 0.8, mypy 1.14, pip-audit 2.7, pandas-stubs (série compatible 2.2) |

### 1.4 Bibliothèques TypeScript (`apps/web`)

| Paquet | Série |
|---|---|
| next | 15.1 |
| react, react-dom | 19.0 |
| typescript | 5.7 |
| tailwindcss | 3.4 |
| @supabase/supabase-js | 2.47 |
| @supabase/ssr | 0.5 |
| @tanstack/react-query | 5.62 |
| react-hook-form | 7.54 |
| @hookform/resolvers | 3.9 |
| zod | 3.24 |
| recharts | 2.15 |
| @sentry/nextjs | 8.x (dernière 8) |
| lucide-react | version installée par shadcn/ui, figée |
| Développement : eslint 9.17, eslint-config-next 15.1, prettier 3.4, prettier-plugin-tailwindcss 0.6, vitest 2.1, @testing-library/react 16.1, @testing-library/user-event 14.5, jsdom 25, msw 2.7, @playwright/test 1.49.1, openapi-typescript 7.4 |

Note : si `recharts` 2.x signale un conflit avec React 19 sur `react-is`, ajouter dans `package.json` une surcharge `"overrides": {"react-is": "<version de react>"}` et le consigner dans `docs/decisions.md`.

### 1.5 Infrastructure (`infra/`)
aws-cdk-lib (série 2.173, identique au tableau 1.2), constructs 10.4, pytest 8.3.

## 2. Formatage et linting

### Python
- `ruff format` (longueur de ligne 100, guillemets doubles).
- `ruff check` avec les règles `E, F, W, I, B, UP, N, S, SIM, RUF, PL, C90` ; complexité cyclomatique maximale 10 ; `S` (sécurité) jamais désactivée globalement.
- `mypy --strict` sur `app/` et `infra/`. Aucun `Any` explicite sans commentaire justificatif. Aucun `# type: ignore` sans code d'erreur et justification.
- Imports absolus depuis `app.`.

### TypeScript
- `prettier` (largeur 100, points-virgules, guillemets doubles, virgules finales, tri des classes Tailwind).
- `eslint` (configuration à plat) : `next/core-web-vitals`, `next/typescript`, règles `no-console: error` (sauf `console.error` dans `lib/observability.ts`), `@typescript-eslint/no-explicit-any: error`, `react-hooks/exhaustive-deps: error`.
- `tsconfig` : `strict: true`, `noUncheckedIndexedAccess: true`, `noImplicitOverride: true`.

### SQL
- Mots-clés en minuscules, une instruction par ligne logique, identifiants en `snake_case`.
- Chaque migration commence par un commentaire décrivant son objet.

### Contrôle unique
`make check` exécute, dans le conteneur `toolbox` et contre la pile locale en conteneurs, dans cet ordre, et échoue au premier problème :
1. formatage (vérification seule) ;
2. lint ;
3. types ;
4. `make api-types` puis vérification que `types.gen.ts` n'a pas changé ;
5. tests unitaires ;
6. tests d'intégration ;
7. tests de base (pgTAP) ;
8. `pip-audit` et `npm audit --audit-level=high`.

Les crochets `pre-commit` exécutent formatage, lint et détection de secrets (`gitleaks`) à chaque commit.

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
- Lire `os.environ` ou `process.env` ailleurs que dans les modules de configuration.
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
