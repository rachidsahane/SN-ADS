# TESTING.md : Stratégie de tests

Document de référence n°9 sur 13.

---

## 1. Principes

- **TDD obligatoire** : pour chaque comportement, le test est écrit d'abord, exécuté pour constater l'échec, puis le code est écrit jusqu'à ce qu'il passe, puis remanié. L'historique Git le montre (`test(...)` avant `feat(...)`).
- Un bug corrigé commence par un test qui le reproduit.
- Tests déterministes : graine fixe (`42`), horloge contrôlée, aucune dépendance à Internet en unitaire et en intégration.
- Chaque test vérifie un seul comportement, nommé par ce comportement.

## 2. Niveaux de tests

| Niveau | Outil | Ce qui en relève | Dépendances réelles |
|---|---|---|---|
| Unitaire API | pytest | Tout `app/domain/` et `app/ml/` : validation CSV, lignes de test, codage des variables, dérivés, notes, score, seuils, niveau, valeurs de pré-remplissage, facteurs, recommandations, avertissements, comparaison, sérialisation du paquet, bornes des prédictions. Schémas Pydantic. Traduction des erreurs. | aucune |
| Unitaire web | Vitest + Testing Library + MSW | Schéma Zod du formulaire, formatage, `apiFetch` (rafraîchissement, redirections), `useFormDraft`, composants d'affichage (`PerformanceLevel`, `RecommendationsList`, `WarningBanner`), garde de rôle. | aucune (API simulée par MSW) |
| Base de données | pgTAP (`pg_prove` du service Compose `pgtap`, contre le conteneur `supabase-db` ; `make test-db`, D-048) | Chaque politique RLS (cas autorisé et refusé), déclencheurs (`handle_new_user`, `guard_last_admin`), index uniques (un seul actif, un seul en cours, doublons d'import), `activate_model_version` (tous les codes d'erreur), droits par colonne sur `profiles`. | conteneur `supabase-db` |
| Intégration API | pytest + `TestClient` FastAPI | Chaque route : authentification, rôles, validation, format d'erreur, codes de statut, isolation, limites de débit, import complet, demande d'apprentissage, activation, worker (un travail de bout en bout sur `small_dataset.csv`), rechargement du modèle par le pointeur. | pile locale en conteneurs (Supabase auto-hébergé, Redis, Mailpit) |
| Bout en bout | Playwright | Parcours utilisateurs réels dans le navigateur (section 3). | pile locale complète en conteneurs ou staging ; Playwright s'exécute dans son image Docker officielle |
| Fumée | Playwright (`@smoke`) | Après déploiement en production : connexion, page Model, une simulation. Aucune écriture. | Production |
| Infrastructure | pytest + assertions CDK | Présence et paramètres clés : HTTPS seul, tâches en sous-réseaux privés, worker sans entrée, disjoncteur activé, secrets référencés et non en clair ; hôte de données sans adresse publique ni SSH, volume chiffré, port 5432 ouvert au seul groupe CodeBuild, seul `/auth/v1/*` routé vers Kong, plan de sauvegarde présent. | aucune |

**Phase 0 : niveaux effectivement en place.**
- Unitaire API (`apps/api/tests/unit/`) : configuration, contexte de requête, format d'erreur, observabilité et gardes d'architecture. Les tests de configuration retirent d'abord les sept variables du processus (`monkeypatch.delenv`), car le conteneur les définit, et n'utilisent que des valeurs factices explicites (`test-only-not-a-secret`).
- Intégration API (`apps/api/tests/integration/test_health.py`, marqueur `integration`) : en phase 0, ces tests utilisent le `TestClient` de FastAPI **sans pile de conteneurs** (aucune base, aucun Redis). Ils couvrent `GET /api/health`, l'identifiant de requête, les en-têtes de sécurité, les erreurs au format standard (404, 405, 413, 415, 500), la journalisation JSON des requêtes, l'OpenAPI (servi hors production, désactivé en production) et l'absence de redirection sur la barre oblique finale. Les cas d'erreur sur des routes qui n'existent pas encore s'appuient sur une application de sondage créée dans le test. À partir de la phase 1, les tests d'intégration qui ont besoin de la pile (`supabase-db`, Redis, Mailpit) s'y connectent comme décrit dans le tableau ci-dessus ; ceux qui n'en ont pas besoin restent sur `TestClient`.
- Unitaire web (`apps/web/tests/`) : `api-status`, `env`, `observability`, client d'API et libellés, avec MSW.
- Base de données : aucun test pgTAP avant la phase 1. `make test-db` ne faisait rien en phase 0 (garde-fou de D-030 : il échouait dès qu'une migration existait).
- Bout en bout : `apps/web/e2e/health.spec.ts` (section 3), lancé par `make test-e2e` dans le service Playwright.

**Phase 1 : niveaux effectivement en place.**
- Base de données (`supabase/tests/database/*.test.sql`, `make test-db`) : le garde-fou de D-030 est remplacé par les vrais tests. `make test-db` applique les migrations, crée l'extension pgTAP dans la base **locale** seulement (jamais par une migration), puis lance `pg_prove` dans le service `pgtap` ; il échoue s'il n'y a aucun test. Fichiers : `001_types` (9 types et libellés dans l'ordre), `010_profiles_structure`, `020_handle_new_user` (dont le rôle jamais lu des métadonnées, SEC-04, et le repli de `full_name`), `030_guard_last_admin` (la concurrence réelle à deux sessions reste E2E-CONC-06, phase 3 ; ici la logique et la présence du verrou), `040_profiles_rls`, `050_access_functions` (table de vérité de `is_admin()` et `is_active_user()`), `060_audit_log` (ajout seul), `070_log_audit`, `080_schema_version`, `090_global_rls_and_privileges` (filet pour toutes les phases : toute table de `public` a RLS activée et forcée, `anon` sans aucun droit de table ni exécution hors `schema_version`, droits par défaut durcis, `search_path` vide sur toute fonction `security definer`, prémisse `postgres` avec `BYPASSRLS`). Chaque politique a au moins un test positif et un test négatif. Un fichier d'aide `_helpers.psql` (inclus par `\ir`) crée les utilisateurs de test dans la transaction du test.
- Unitaire API : `test_supabase_clients.py`, `test_readiness_service.py` (transport `httpx.MockTransport`), extension de `test_config.py` (`SUPABASE_*`, `SecretStr`) et de `test_architecture.py`.
- Unitaire pile (`deploy/supabase/tests/`, `unittest` dans le toolbox, lancés par `make test-unit`) : `generate_keys.py` (signatures HMAC recalculées à la main, idempotence, rotation, synchronisation du `.env` racine, aucune valeur affichée, refus de `--env staging` et `production`), configuration Compose, `kong.yml`, scripts d'initialisation de la base, migrations (analyse statique). Tout se fait dans un dossier temporaire : aucun vrai `.env` du dépôt n'est modifié.
- Intégration API : `test_ready.py` (`TestClient`, sans pile, `get_database_check` surchargée : corps exacts 200 et 503, en-têtes, journalisation, schéma OpenAPI) et `test_stack_wiring.py` (pile réelle, appels `httpx` directs vers `supabase-kong:8000` et `mailpit:8025` : clé exigée par Kong, aucun droit pour `anon`, inscription publique désactivée, déclencheur de profil de bout en bout par gotrue réel, e-mail d'invitation reçu dans Mailpit avec lien vers `http://localhost:54321/auth/v1/verify`, `/api/ready` réel). La fixture `require_stack` **échoue** (jamais `skip`) si la pile ne répond pas : lancer `make up` d'abord. Chaque test nettoie ce qu'il crée (adresses `phase1-<uuid>@example.test`).
- Unitaire web : `database-status.test.tsx` (sept cas : vérification en cours, connecté avec le numéro, erreur réseau, 503, 500 non JSON, 200 incomplet, passage de `connected` à `unreachable`) et libellés.
- Garde-fous Compose (`make guards`, exécutés par `lint`) : images figées par digest, aucun secret dans `web`, aucun port hors `127.0.0.1`, aucun port publié par la base, PostgREST, Storage, Auth ni `postgres-meta`.

**Phase 2 : niveaux effectivement en place.** Aucune migration ni nouvelle table : pas de nouvelle politique RLS.
- Base de données : `100_profiles_service_role.test.sql` (premiers consommateurs des droits de `service_role`, jamais testés : `bootstrap_admin` et `create_test_users`) : lecture de `profiles` et mise à jour de `role`, `is_active` et `full_name` autorisées ; droits de mise à jour sur `email` et `id` absents ; `insert` et `delete` refusés (`42501`) ; rétrograder ou désactiver le **dernier** administrateur actif par `service_role` lève `LAST_ADMIN` (le déclencheur s'applique aussi aux rôles qui contournent la RLS), l'opération réussit une fois un autre administrateur promu. Les tests `001` à `090` restent verts.
- Unitaire API (`apps/api/tests/unit/`) : `test_config.py` étendu (nouvelles variables, `SecretStr`, `E2ETestAccounts` : noms listés, jamais les valeurs) ; `test_auth.py` (jeton valide, expiré, mauvaise signature, `alg=none`, HS512, mauvaise audience ou émetteur, `sub` ou `exp` manquant, `sub` non UUID, clés `anon` et de service refusées, entrée vide ou illisible, secret ou émetteur vide = `ConfigError`, en-tête `WWW-Authenticate`, le jeton jamais dans les journaux) ; `test_deps.py` ; `test_redis_client.py` ; `test_profile_cache.py` (faux Redis écrit à la main, pas de bibliothèque ajoutée : format de clé, durée 60 s, contenu limité à `role` et `is_active`, JSON illisible = absence, erreurs Redis avalées par `get` et `set` mais pas par `invalidate`) ; `test_profiles_repo.py` ; `test_user_schemas.py` ; `test_auth_service.py` (cache présent : aucune lecture en base ; absent : lecture puis mise en cache ; profil absent ou inactif : 403 `ACCOUNT_DISABLED` ; Redis arrêté : lecture en base ; base arrêtée : 503 et `capture` avec identifiants métier seulement ; `set_user_id` avant la lecture) ; `test_readiness_service.py` étendu (`check_cache`) ; `test_architecture.py` étendu (`redis` importé seulement sous `app/infra/`, secret JWT lu par `infra/auth.py` seul, `infra/auth.py` n'importe ni Supabase ni Redis) ; `test_bootstrap_admin.py` (les six comportements, adresse en minuscules, entrée invalide sans appel réseau, `--print-link` sans e-mail ni jeton dans les journaux, clé de service vide, idempotence) ; `test_create_test_users.py` (refus en production avant tout appel, cinq comptes, mots de passe réinitialisés à la seconde exécution, administrateurs d'abord, invité laissé tel quel s'il est confirmé, rien de secret affiché). Pour ruff (`S105`, `S106`), les valeurs factices de mot de passe ou de jeton sont assemblées à l'exécution, jamais écrites en littéral ressemblant à un jeton.
- Intégration API sans pile : `test_me.py` (`GET /api/v1/me` : sans en-tête, schéma `Basic`, jeton illisible, expiré, mauvais secret, clés `anon` et de service : 401 au format standard ; profil absent ou inactif : 403 ; corps exact de cinq champs ; `X-Request-ID`, en-têtes de sécurité et `Cache-Control: no-store` ; journal de requête avec `user_id` et sans jeton ni e-mail ; OpenAPI : `BearerAuth` et `MeResponse`) ; `test_ready.py` mis à jour (200 avec `cache: "ok"`, 503 quand le cache ou la base ou les deux sont arrêtés, sans `schema_version`, `/api/health` toujours 200).
- Intégration API avec la pile réelle (`require_stack`, comptes `phase2-<uuid>@example.test` toujours nettoyés) : `test_auth_stack.py` (connexion réelle, `/me`, clé `auth:profile:<id>` présente avec une durée de vie d'au plus 60 s et sans e-mail, compte désactivé puis cache vidé : 403, jeton d'un autre secret et clé de service : 401, `/api/ready` réel avec `cache: "ok"`) ; `test_stack_wiring.py` étendu (les e-mails d'invitation et de réinitialisation reçus dans Mailpit portent les objets fixes et le lien `.../auth/confirm?token_hash=<hex>&type=...&next=/auth/set-password` sur l'origine `SITE_URL`, ce qui prouve que gotrue lit les gabarits servis par `web` ; `/auth-templates/invite.html` est servi sans session et sans redirection) ; `test_bootstrap_admin_stack.py` (`main` contre la pile : compte créé, e-mail dans Mailpit, `role = admin`, seconde exécution sans second compte, `token_hash` reçu échangeable une seule fois).
- Unitaire web (Vitest + MSW, `apps/web/tests/`) : `env` (Supabase obligatoire), `labels` (chaînes de `auth.*` et `predict.title`), `redirect` (`/predict` et `/history/abc?x=1` acceptés ; `//evil.com`, `/\evil.com`, `https://evil.com`, `javascript:alert(1)`, tabulations et caractères de contrôle, vide, `null`, `undefined` : repli), `schemas/auth` (9 caractères refusés, 10 acceptés, 73 refusés, confirmation différente), `api-client` (jeton ajouté seulement avec session, 401 : déconnexion locale et `/login?next=...`, 403 `ACCOUNT_DISABLED` : `/login?reason=disabled`), `supabase/middleware` (`isPublicPath`, cookies rafraîchis, erreur réseau = pas d'utilisateur), `supabase/browser` et `server` (origine, nom de cookie `soronua-auth`, `secure` faux seulement en local), `supabase/lock` (verrou sérialisé, D-077), `middleware` (redirections, cookies conservés, `matcher`), `app/auth-confirm-route` (environnement `node` : invitation et réinitialisation valides, `next` malveillant, `type` invalide, jeton absent ou déjà utilisé, jeton jamais dans la redirection ni dans `reportError`), `app/pages`, `components/login-form`, `forgot-password-form`, `set-password-form`, `app-header`, `hooks/use-me`.
- Bout en bout : `auth.spec.ts` (E2E-AUTH-01, 02, 03, 04, 06, 07) et `health.spec.ts` réduit aux deux tests d'API (voir section 3). `global-setup.ts` préchauffe le serveur de développement (première compilation des pages, quelques secondes). `playwright.config.ts` déclare aussi `http://web:3000` contexte sécurisé pour Firefox (préférences `dom.securecontext.allowlist`), comme pour Chromium, sinon son avertissement de console sur les champs mot de passe ferait échouer les scénarios sans erreur. Les scénarios E2E-AUTH-05 et 08 arrivent en phase 3, E2E-SESS-* en phases 3 et 15.
- Garde-fous Compose et pile (`deploy/supabase/tests/`) : le service `cli` (profil `tools`, sans port, liste de variables explicite, clé de service autorisée), `SUPABASE_JWT_SECRET` seulement dans `api` (garde G5), `web` et `e2e` sans clé de service (seule exception : `NEXT_PUBLIC_SUPABASE_ANON_KEY` copie de la clé publique), gabarits d'e-mails branchés (`GOTRUE_MAILER_TEMPLATES_*`, objets fixes), `SUPABASE_JWT_ISSUER` égal à `<SUPABASE_PUBLIC_URL>/auth/v1` et `WEB_APP_URL` égal à `SITE_URL`, `generate_keys.py` (copie de `SUPABASE_JWT_SECRET`, génération idempotente des cinq `E2E_*_PASSWORD`, valeur réelle conservée, `--rotate`, aucune valeur affichée), `Makefile` (cibles `bootstrap-admin` et `test-users`, ordre de `test-e2e`).

Tests de garde d'architecture (unitaire API) :
- `test_service_client_is_only_imported_by_allowed_modules` : analyse les imports et échoue si `get_service_client` apparaît hors des modules autorisés (`ARCHITECTURE.md` 2.5). *Ajouté en phase 1, avec `infra/supabase_clients.py`.*
- `test_domain_has_no_io_imports` : `app/domain` n'importe ni `supabase`, ni `redis`, ni `httpx`, ni `app.infra`. *Présent dès la phase 0.*
- `test_enum_values_match_database` : les énumérations de `dataset_schema.py` sont identiques à celles des migrations. *Ajouté en phase 4.*
- `test_no_environment_reads_outside_config` : *présent dès la phase 0.* Il vérifie aussi qu'il a bien analysé au moins un fichier (sans cela, un mauvais chemin le rendrait toujours vert).

## 3. Scénarios Playwright

Fichiers dans `apps/web/e2e/`. Navigateurs : Chromium (tous les scénarios), Firefox et WebKit (scénarios marqués `@cross`). Chaque scénario démarre d'un état connu (section 5).

### health.spec.ts (phases 0 à 2)
**Depuis la phase 2**, la page d'accueil provisoire a disparu (`/` redirige vers `/predict`, ou vers "Sign in" sans session) : les quatre tests d'interface ci-dessous sont supprimés et le fichier ne garde que les deux tests d'API (`API health is reachable through the web origin`, et `API readiness is reachable through the web origin` qui vérifie aussi `checks.cache === "ok"`), qui prouvent les réécritures `/api/*` et le contrôle du cache. Le tableau ci-dessous décrit l'état des phases 0 et 1 pour mémoire.

Fichier propre aux phases 0 et 1 : il vérifiait la page d'accueil provisoire (état de l'API, puis de la base) et n'a **pas d'identifiant de scénario** (les identifiants `E2E-*` ci-dessous sont attribués aux phases 2 et suivantes). Il ne porte aucune étiquette `@cross` ni `@smoke` : le nom `smoke.spec.ts` et l'étiquette `@smoke` restent réservés au parcours de fumée de production. Il ne nécessite aucun compte de test (section 5) ; à partir de la phase 1, il suppose la pile Supabase démarrée (`make test-e2e` appelle `make up`, qui applique les migrations).

| Test | Comportement vérifié |
|---|---|
| `home page shows the product title and a healthy API` | La page `/` affiche le titre "Soro Nua Campaign Predictor" et la ligne `API: healthy` en vert (`data-state="healthy"`) ; aucune erreur ni avertissement dans la console du navigateur, aucune erreur de page. |
| `home page shows 'API: unreachable' in red when the API cannot be reached` | Avec l'appel `/api/health` coupé par `page.route(...).abort`, la ligne devient `API: unreachable` en rouge (`data-state="unreachable"`). Aucune assertion sur la console : une panne volontaire produit légitimement une ligne d'erreur réseau. L'arrêt réel du conteneur `api` est vérifié à la main (définition de terminé de la phase 0, `ROADMAP.md`). |
| `API health is reachable through the web origin` | `GET /api/health` sur l'origine du web répond 200, `status: "ok"` et une version non vide (prouve la réécriture `/api/*` de Next.js en local). |
| `home page shows a connected database with the schema number` (phase 1) | La ligne `database-status` affiche `Database: connected (schema <14 chiffres>)` en vert (`data-state="connected"`, `rgb(22, 100, 52)`) ; aucune erreur ni avertissement dans la console. Nécessite la pile Supabase démarrée et les migrations appliquées (`make up`). |
| `home page shows 'Database: unreachable' in red when readiness cannot be reached` (phase 1) | Avec `/api/ready` coupé par `page.route(...).abort`, la ligne devient `Database: unreachable` en rouge (`rgb(180, 35, 24)`, `data-state="unreachable"`) pendant que `API: healthy` reste vert : les deux sondes sont indépendantes. L'arrêt réel de `supabase-kong` est vérifié à la main (définition de terminé de la phase 1). |
| `API readiness is reachable through the web origin` (phase 1) | `GET /api/ready` sur l'origine du web répond 200, `status: "ready"`, `checks.database: "ok"`, `schema_version` de 14 chiffres, `release` non vide, et les en-têtes de sécurité. |

Particularité de l'environnement : `http://web:3000` n'est pas un contexte sécurisé pour Chromium (pas de `crypto.subtle`). `playwright.config.ts` ajoute l'option `--unsafely-treat-insecure-origin-as-secure=<origine testée>` (honorée seulement par le Chromium complet : `channel: "chromium"`, D-080), et `newRequestId` retombe sur `getRandomValues` quand `crypto.randomUUID` est absent.

### auth.spec.ts
| ID | Scénario |
|---|---|
| E2E-AUTH-01 | Connexion réussie d'un `marketer`, arrivée sur "Predict", nom affiché dans l'en-tête. `@cross` `@smoke` |
| E2E-AUTH-02 | Mauvais mot de passe : "Invalid email or password.", toujours sur "Sign in". |
| E2E-AUTH-03 | E-mail inexistant : même message que E2E-AUTH-02. |
| E2E-AUTH-04 | Déconnexion puis accès direct à `/predict` : redirection vers "Sign in". |
| E2E-AUTH-05 | Invitation : l'administrateur invite, le lien de la boîte mail locale ouvre "Set your password", mot de passe trop court refusé, mot de passe valide accepté, arrivée sur "Predict". |
| E2E-AUTH-06 | Lien d'invitation réutilisé : message de lien invalide ou expiré. |
| E2E-AUTH-07 | Mot de passe oublié : e-mail reçu, nouveau mot de passe, connexion avec celui-ci. |
| E2E-AUTH-08 | Compte désactivé : connexion refusée avec le message de désactivation. |

Phase 2 : E2E-AUTH-01, 02, 03, 04, 06 et 07 sont livrés (05 et 08 arrivent en phase 3, avec l'administration des utilisateurs). Mise en œuvre :
- E2E-AUTH-01 : connexion de `E2E_MARKETER_A`, URL `/predict`, titre "Predict", `getByTestId("user-name")` vaut "E2E Marketer A", bouton "Sign out" visible, aucune erreur ni avertissement de console.
- E2E-AUTH-02 et 03 : même texte d'alerte "Invalid email or password." et toujours l'URL `/login` (mauvais mot de passe, puis adresse inconnue).
- E2E-AUTH-04 : "Sign out" renvoie vers `/login` ; `goto("/predict")` mène à `/login?next=%2Fpredict` ; le nom de l'utilisateur n'est plus affiché.
- E2E-AUTH-06 : lien d'invitation du plus récent message adressé à `E2E_INVITEE_EMAIL` (invité par `make test-users`) ; première ouverture : "Set your password" ; seconde ouverture dans un contexte de navigateur neuf : `/login?reason=invalid_link` et le message "This link is invalid or has expired. Ask an administrator for a new invitation.".
- E2E-AUTH-07 : sur `/login`, "Forgot password?" puis l'adresse de `E2E_RESET_*` ; message neutre ; e-mail de réinitialisation lu dans Mailpit ; "Set your password" ; 9 caractères refusés ("Password must be at least 10 characters."), un mot de passe valide différent mène à `/predict` ; déconnexion ; reconnexion avec le nouveau mot de passe. Compte dédié, **une seule demande par exécution** (gotrue refuse une seconde demande pour le même compte pendant environ 60 s : 429 `over_email_send_rate_limit`) ; les autres scénarios utilisent A et B en parallèle.
- Règle des liens d'e-mail : le lien porte l'origine `SITE_URL` (`http://localhost:3000`), inatteignable depuis le conteneur Playwright ; `confirmPathFromMail` ne garde que le chemin et la requête (avec `&amp;` décodé) et le test navigue avec `baseURL + chemin`.

### session.spec.ts (session expirée)
| ID | Scénario |
|---|---|
| E2E-SESS-01 | L'utilisateur remplit le formulaire, sa session est révoquée côté serveur (déconnexion globale via l'API d'administration de test), il modifie un champ : redirection vers "Sign in" avec "Your session has expired. Please sign in again." ; après connexion, retour sur "Predict" avec toutes les valeurs restaurées. |
| E2E-SESS-02 | Jeton d'accès expiré mais rafraîchissement valide (horloge avancée de 61 minutes avec `page.clock`) : l'action réussit sans redirection. |
| E2E-SESS-03 | Utilisateur désactivé pendant sa session : prochaine action refusée avec le message de désactivation puis retour à "Sign in". |
| E2E-SESS-04 | Retour arrière du navigateur après déconnexion : aucune donnée protégée affichée. |

### predict.spec.ts
| ID | Scénario |
|---|---|
| E2E-PRED-01 | Choix du canal et du type : les 5 champs d'engagement se pré-remplissent. `@cross` |
| E2E-PRED-02 | Un champ d'engagement modifié à la main n'est pas écrasé quand le canal change. |
| E2E-PRED-03 | Formulaire complet : trois chiffres, niveau, score, facteurs et recommandations (ou message "No tested change...") affichés. `@smoke` |
| E2E-PRED-04 | Modification du budget : les résultats changent après la pause de saisie, sans clic. |
| E2E-PRED-05 | "Apply" sur une recommandation (données de test préparées pour en produire une) : le champ prend la valeur proposée et les résultats se recalculent. |
| E2E-PRED-06 | Aucune version active : bandeau "No active model yet..." et formulaire désactivé. |
| E2E-PRED-07 | Bandeau de fiabilité faible visible avec le modèle entraîné sur le jeu de départ. |
| E2E-PRED-08 | Valeur hors des valeurs connues (budget 5 000 000) : avertissement sur le champ, résultats affichés. |

### Entrées invalides (dans predict.spec.ts et admin-data.spec.ts)
| ID | Scénario |
|---|---|
| E2E-INV-01 | Budget négatif, nul, vide, texte : message sous le champ, aucun appel de calcul. |
| E2E-INV-02 | Âge 17 et 101 : message sous le champ. |
| E2E-INV-03 | Nom de prédiction de 121 caractères : refusé. |
| E2E-INV-04 | Appel direct à l'API avec un champ inconnu ou un type faux (via `request` Playwright) : 422 au format standard. |
| E2E-INV-05 | Import d'un fichier non CSV : refusé avec message. |
| E2E-INV-06 | Import avec une colonne manquante, une colonne en trop, un taux à 5 (au lieu de 0.05), un canal inconnu, une cellule vide, une cellule `=HYPERLINK(...)` : liste d'erreurs avec ligne et colonne, aucune ligne importée (résumé inchangé). |
| E2E-INV-07 | Import de plus de 10 Mo : refus avec la limite indiquée. |
| E2E-INV-08 | Import sans cocher la case d'anonymisation : bouton désactivé ; appel direct à l'API : 422. |

### history.spec.ts
| ID | Scénario |
|---|---|
| E2E-HIST-01 | Enregistrement avec un nom : visible en tête de "History" avec niveau et date. |
| E2E-HIST-02 | Ouverture d'une prédiction : résultats figés identiques à ceux affichés au moment de l'enregistrement, numéro de version affiché. |
| E2E-HIST-03 | Après activation d'une nouvelle version, l'ancienne prédiction affiche toujours ses résultats et son ancienne version. |
| E2E-HIST-04 | Suppression : disparaît de la liste ; l'URL directe affiche "Prediction not found." |
| E2E-HIST-05 | Pagination : 25 prédictions, deux pages. |

### isolation.spec.ts (tentative d'accès aux données d'un autre utilisateur)
| ID | Scénario |
|---|---|
| E2E-ISO-01 | A enregistre une prédiction ; B ouvre `/history/<id de A>` : "Prediction not found." |
| E2E-ISO-02 | B appelle `GET /api/v1/predictions/<id de A>` avec son jeton : 404, corps au format standard. |
| E2E-ISO-03 | B appelle `DELETE /api/v1/predictions/<id de A>` : 404 ; A voit toujours sa prédiction. |
| E2E-ISO-04 | La liste "History" de B ne contient aucune prédiction de A. |
| E2E-ISO-05 | Un administrateur ne voit pas non plus la prédiction de A (liste et accès direct : 404). |
| E2E-ISO-06 | B (`marketer`) ouvre `/admin/users`, `/admin/data`, `/admin/models`, `/admin/audit` : redirection vers "Predict" avec "You do not have access to this page." |
| E2E-ISO-07 | B appelle chaque route `/api/v1/admin/*` : 403 `FORBIDDEN`. |
| E2E-ISO-08 | Appel direct depuis le navigateur de B aux routes internes de la pile Supabase (`/rest/v1/predictions`, `/rest/v1/dataset_rows`, `/storage/v1/object/...`) sur l'URL publique : 404, ces routes ne sont pas exposées. Le même contrôle d'isolation au niveau des lignes est couvert par les tests pgTAP et d'intégration. |

### admin-users.spec.ts
| ID | Scénario |
|---|---|
| E2E-USR-01 | Invitation d'un `marketer` : apparaît "Invited", entrée d'audit `user.invited`. |
| E2E-USR-02 | Invitation d'un e-mail existant : "A user with this email already exists." |
| E2E-USR-03 | Passage d'un `marketer` en `admin` puis retour : visible dans la liste et l'audit. |
| E2E-USR-04 | L'administrateur ne peut agir sur son propre compte (boutons désactivés ; appel direct : 409). |
| E2E-USR-05 | Seul administrateur actif restant : sa rétrogradation par l'autre voie est refusée avec "At least one active administrator is required." |

### admin-data.spec.ts
| ID | Scénario |
|---|---|
| E2E-DATA-01 | Résumé initial : 8 000 lignes de départ, 0 ligne agence, environ 1 600 lignes de test ; "Agency data only" grisé avec explication. |
| E2E-DATA-02 | Import d'un fichier agence valide de 300 lignes : statut "Ready", résumé mis à jour, audit `upload.accepted`. |
| E2E-DATA-03 | Réimport du même fichier : "This file has already been imported." |
| E2E-DATA-04 | Fichier dont un `CustomerID` existe déjà côté agence : refus 409 avec l'identifiant en cause. |

### admin-models.spec.ts
| ID | Scénario |
|---|---|
| E2E-MOD-01 | Lancement d'un apprentissage "All data" : "Queued" puis "Running" puis "Succeeded" sans recharger la page ; métriques affichées. |
| E2E-MOD-02 | Première version : activable ; activation ; la page "Model" affiche la version. |
| E2E-MOD-03 | Seconde version : tableau de comparaison affiché avec verdict ; bouton activé seulement si verdict favorable. |
| E2E-MOD-04 | Version moins fiable (préparée par les données de test) : bouton désactivé, appel direct : 409 `MODEL_NOT_ACTIVATABLE`. |
| E2E-MOD-05 | Échec d'apprentissage ("Agency data only" forcé par l'API avec trop peu de lignes) : "Failed" avec raison lisible. |

### concurrency.spec.ts (accès concurrent)
Deux contextes de navigateur indépendants, actions déclenchées ensemble (`Promise.all`).

| ID | Scénario |
|---|---|
| E2E-CONC-01 | Deux administrateurs cliquent "Train a new version" en même temps : une seule version créée ; l'autre voit "A training run is already in progress." |
| E2E-CONC-02 | Deux administrateurs activent deux versions différentes depuis des pages ouvertes avant toute activation : une seule réussit ; l'autre voit le message "The active version changed..." ; une seule version active en base. |
| E2E-CONC-03 | Le même fichier importé en même temps par deux administrateurs : un seul import accepté. |
| E2E-CONC-04 | Un utilisateur simule pendant qu'une nouvelle version est activée : aucune erreur, les résultats suivants portent le nouveau numéro de version. |
| E2E-CONC-05 | Même utilisateur dans deux onglets : suppression d'une prédiction dans l'un, ouverture dans l'autre : "Prediction not found." |
| E2E-CONC-06 | Deux administrateurs désactivent chacun l'autre alors qu'ils sont les deux seuls administrateurs actifs : au moins un administrateur actif reste en base. |

### Limites de débit
| ID | Scénario |
|---|---|
| E2E-RATE-01 | 31 enregistrements en moins d'une minute via l'API : la 31e reçoit 429 avec `Retry-After` ; l'interface affiche "Too many requests. Please wait a moment." |

Tests de la pile de données (dans `infra/tests` et `deploy/supabase`) :
- `apply.sh` exécuté deux fois de suite sur la pile locale ne change rien (idempotence) ;
- `backup.sh` puis `restore.sh` sur une base locale jetable restituent le même nombre de lignes dans chaque table et les mêmes fichiers.

## 4. Couverture attendue

| Périmètre | Lignes | Branches | Bloquant en CI |
|---|---|---|---|
| `apps/api/app/domain` et `apps/api/app/ml` | 95 % | 90 % | oui |
| `apps/api/app` (global) | 85 % | 80 % | oui |
| `apps/web/src/lib` et `apps/web/src/hooks` | 85 % | 80 % | oui |
| `apps/web/src/components` | 70 % | 60 % | oui |
| Politiques RLS | 100 % des politiques ont un test positif et un test négatif | n/a | oui |
| Scénarios Playwright de la section 3 | 100 % présents et verts | n/a | oui (staging) |

Aucun fichier ne peut être exclu de la couverture sans entrée dans `docs/decisions.md`. Phase 1 : les nouvelles tables (`profiles`, `audit_log`) respectent la ligne « Politiques RLS » (chaque politique a un test positif et un test négatif) et `090_global_rls_and_privileges.test.sql` vérifie RLS activée et forcée sur **toutes** les tables de `public`, y compris celles des phases suivantes. Aucune exclusion de couverture n'est ajoutée.

**Mise en œuvre en phase 0.**
- API : `fail_under = 85` dans `[tool.coverage.report]` de `apps/api/pyproject.toml`, sur la couverture combinée lignes et branches de `apps/api/app`, mesurée sur `make test-unit` puis `make test-integration` (le second cumule avec le premier et applique le seuil). Les seuils séparés lignes/branches (85/80), et ceux par sous-ensemble (`domain` et `ml` à 95/90), exigent un contrôle par périmètre que `coverage` ne fait pas seul : le script `tools/check_coverage.py` est **reporté à la phase 7**, quand `app/domain` et `app/ml` cessent d'être vides. D'ici là, seul le seuil global de 85 % est bloquant.
- Web : les seuils par dossier de la table sont déclarés dans `apps/web/vitest.config.ts` (`src/lib/**` et `src/hooks/**` à 85/80, `src/components/**` à 70/60) et appliqués par `make test-unit` (`vitest run --coverage`).
- Exclusions de la couverture web (consignées dans `docs/decisions.md`) : `src/lib/api/types.gen.ts` (fichier généré) et `src/components/ui/**` (composants à l'API shadcn/ui, écrits à la main en phase 2, D-070).

## 5. Données de test

- **Unitaire et intégration** :
  - `tests/fixtures/small_dataset.csv` : 300 lignes générées une fois par un script déterministe (graine 42), avec des relations volontairement fortes entre budget, canal et les trois cibles. Ce jeu permet de tester que les recommandations et les facteurs réagissent, ce que le jeu de départ ne permet pas.
  - Fichiers `invalid_*.csv` : un défaut par fichier.
  - `tests/fixtures/golden/` : résultats attendus figés (notes, seuils, niveau, recommandations) pour des saisies fixes sur un paquet entraîné à partir de `small_dataset.csv`. Toute modification d'un fichier `golden` doit être justifiée dans le commit.
- **Fabriques** (`tests/factories.py`) : `make_campaign_input(**overrides)`, `make_profile(role=...)`, `make_dataset_frame(n, seed)`.
- **Base locale** : `make db-reset` avant chaque session d'intégration (il ne supprime que les volumes du projet `soronua-predict`) ; chaque test d'intégration crée ses propres utilisateurs (préfixe d'e-mail aléatoire) et nettoie ce qu'il crée.
- **Playwright local** (à partir de la phase 2 ; en phase 0, `make test-e2e` démarre seulement `redis`, `api` et `web` puis lance `health.spec.ts`, sans base ni compte de test). Séquence de la phase 2 (D-074) : `make up`, `make db-reset`, `make test-users`, puis Playwright ; les phases suivantes l'étendent avec le jeu de départ et l'entraînement. **`make test-e2e` supprime la base locale du projet** (jamais les volumes d'un autre projet, D-056). Comptes (`E2E_ADMIN`, `E2E_ADMIN2`, `E2E_MARKETER_A`, `E2E_MARKETER_B`, `E2E_RESET`, plus l'adresse invitée `E2E_INVITEE_EMAIL`) : adresses en `@example.test`, mots de passe générés par `make env-local` (jamais versionnés). Redis garde d'anciennes clés `auth:profile:*` après une réinitialisation : sans effet (60 s). Séquence complète prévue :
  - `make test-e2e` réinitialise la base ;
  - charge le jeu de départ ;
  - crée les comptes de test ;
  - entraîne et active une version sur `small_dataset.csv` importé comme données agence (pour E2E-PRED-05) ;
  - lance les scénarios.

  Les scénarios qui exigent "aucune version active" utilisent un projet Playwright séparé qui s'exécute avant l'activation.
- **Staging** :
  - comptes de test créés par `create_test_users` (idempotent) ;
  - les données produites par les tests portent le préfixe `e2e-` (noms de prédictions, noms de fichiers) ;
  - un nettoyage en fin de suite supprime les prédictions des comptes de test ;
  - les imports de test utilisent des `CustomerID` à partir de 900000000 pour ne jamais entrer en conflit avec de vraies données.
- **Production** : aucune donnée de test créée ; le compte de fumée ne fait que lire et simuler.
- Aucune donnée réelle de client de Soro Nua n'est jamais utilisée dans les tests.
