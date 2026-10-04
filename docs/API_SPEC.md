# API_SPEC.md : Soro Nua Campaign Predictor

Document de référence n°5 sur 13.
Service : `api` (FastAPI). Préfixe de toutes les routes : `/api`. Version : `/api/v1`.
La spécification OpenAPI générée par FastAPI (`/api/openapi.json`, désactivée en production) doit rester conforme à ce document. Les types TypeScript de l'interface sont générés depuis ce fichier (voir `LLD.md`).

---

## 1. Conventions générales

- Format : JSON UTF-8 (`Content-Type: application/json`), sauf l'import de fichier (`multipart/form-data`).
- Noms de champs : `snake_case`.
- Dates : ISO 8601 en UTC (`2026-09-23T14:05:00Z`).
- Identifiants : UUID v4 en texte.
- Nombres décimaux : nombres JSON, jamais de chaînes.
- Taux : fractions entre 0 et 1.
- Montants : USD.
- En-tête `X-Request-ID` : accepté s'il est fourni (UUID), sinon généré. Toujours renvoyé dans la réponse et dans le corps des erreurs.
- Pagination par curseur : paramètres `limit` (défaut 20, maximum 100 ; les routes de liste d'administration `admin/users` et `admin/audit-log` ont pour défaut 50, D-081) et `cursor` (chaîne opaque). Réponse : `{"items": [...], "next_cursor": "..." | null}`.

## 2. Authentification

- Schéma : `Authorization: Bearer <access_token>`, jeton d'accès émis par `supabase-auth` (JWT).
- Vérification par l'API :
  - signature HS256 vérifiée avec `SUPABASE_JWT_SECRET` (secret propre à la pile Supabase de l'environnement) ; tout autre algorithme est refusé ;
  - `exp` non dépassé, `aud = "authenticated"`, `iss = SUPABASE_JWT_ISSUER`, `sub` présent (de forme UUID), `role = "authenticated"` ;
  - tolérance d'horloge de 10 s (`leeway`) entre `supabase-auth` et l'API : un jeton tout juste émis n'est pas refusé comme « pas encore valide » ;
  - `role` est contrôlé après le décodage : les clés `anon` et de service partagent le secret de signature mais portent `role = "anon"` ou `"service_role"` et ne portent pas de `sub` ; utilisées comme jeton, elles donnent `401 UNAUTHENTICATED` ;
  - `SUPABASE_JWT_SECRET` ou `SUPABASE_JWT_ISSUER` vide est une erreur de configuration (500 franc), jamais un 401 qui masquerait la panne.
- Réponses 401 (phase 2) : en-tête absent, schéma autre que `Bearer`, jeton vide, mal formé, mal signé, mauvaise audience ou mauvais émetteur : `UNAUTHENTICATED`, message « Authentication is required. Please sign in. » ; jeton expiré (au-delà de la tolérance) : `TOKEN_EXPIRED`, message « Your session has expired. Please sign in again. ». Les deux portent `WWW-Authenticate: Bearer` et suivent le format de la section 3 (le 403 propre à FastAPI pour un en-tête absent n'est jamais renvoyé).
- Le profil (`role`, `is_active`) est ensuite lu (cache Upstash 60 s) :
  - profil introuvable ou `is_active = false` : `403 ACCOUNT_DISABLED`, message « Your account has been deactivated. Contact an administrator. » (sous RLS, un compte désactivé ne voit aucune ligne : « introuvable » et « désactivé » sont indiscernables, `is_active_user()` conditionne la lecture de `profiles`) ;
  - base indisponible pendant cette lecture : `503 SERVICE_UNAVAILABLE` ; Redis indisponible : la lecture se fait en base, la requête n'échoue pas ;
  - route `/api/v1/admin/*` et `role != 'admin'` : `403 FORBIDDEN`, message « You do not have permission to do this. » (livré en phase 3 ; la dépendance `require_admin` est déclarée une seule fois sur le routeur d'administration et s'exécute avant toute validation du chemin, de la requête ou du corps : un `marketer` obtient 403 même pour un identifiant mal formé, jamais 404 ni 422, SEC-02).
- Le cache ne contient que `role` et `is_active` (clé `auth:profile:<id>`, 60 s) ; `GET /api/v1/me` relit toujours le profil complet en base avec le jeton de l'utilisateur.
- Routes publiques (sans jeton) : `GET /api/health`, `GET /api/ready`.
- Connexion, déconnexion, invitation acceptée, mot de passe oublié : gérés directement par `supabase-auth` depuis l'interface, via `/auth/v1/*` sur la même origine (pas de route API).

## 3. Format standard des erreurs (tout le projet)

Toute erreur renvoie ce corps, sans exception :

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Some fields are invalid.",
    "details": [
      {"field": "ad_spend", "issue": "must_be_greater_than", "message": "Ad spend must be greater than 0."}
    ],
    "request_id": "3f1c2a9e-8f7b-4a53-9d0e-2b6c1f4e7a10"
  }
}
```

- `code` : constante en MAJUSCULES tirée de la table ci-dessous.
- `message` : phrase anglaise affichable telle quelle à l'utilisateur.
- `details` : liste, éventuellement vide. Pour les imports CSV, chaque élément contient `row` (numéro de ligne du fichier, en-tête = ligne 1), `column`, `issue`, `message`.
- `request_id` : identifiant de la requête, également attaché à l'événement Sentry.
- Jamais de trace technique, de requête SQL ou de nom interne dans `message` ou `details`.

| Code | Statut HTTP | Signification |
|---|---|---|
| `INVALID_REQUEST` | 400 | JSON mal formé, paramètre de requête invalide. |
| `UNAUTHENTICATED` | 401 | Jeton absent ou invalide. |
| `TOKEN_EXPIRED` | 401 | Jeton expiré ; l'interface tente un rafraîchissement unique puis renvoie vers la connexion. |
| `FORBIDDEN` | 403 | Rôle insuffisant. |
| `ACCOUNT_DISABLED` | 403 | Compte désactivé. |
| `NOT_FOUND` | 404 | Ressource inexistante **ou appartenant à un autre utilisateur**. |
| `NO_ACTIVE_MODEL` | 409 | Aucune version active. |
| `TRAINING_ALREADY_RUNNING` | 409 | Un apprentissage est déjà en file ou en cours. |
| `DUPLICATE_UPLOAD` | 409 | Fichier déjà importé (même empreinte). |
| `DUPLICATE_EXTERNAL_ID` | 409 | Un `CustomerID` du fichier existe déjà dans les données de l'agence. |
| `MODEL_NOT_ACTIVATABLE` | 409 | Version non réussie ou moins fiable que l'active. |
| `ACTIVE_VERSION_CHANGED` | 409 | La version active a changé depuis l'affichage. |
| `EMAIL_ALREADY_REGISTERED` | 409 | Invitation vers un e-mail existant. |
| `LAST_ADMIN` | 409 | L'action laisserait zéro administrateur actif. |
| `SELF_ACTION_FORBIDDEN` | 409 | Un administrateur tente de modifier son propre compte (rôle, statut ou nom : la RLS interdit toute mise à jour de sa propre ligne, D-082). |
| `PAYLOAD_TOO_LARGE` | 413 | Fichier de plus de 10 Mo ou corps JSON de plus de 64 Ko. |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Type de contenu non accepté. |
| `VALIDATION_ERROR` | 422 | Champs invalides. |
| `CSV_INVALID` | 422 | Fichier CSV non conforme (détails par ligne et colonne). |
| `NOT_ENOUGH_DATA` | 422 | Données insuffisantes pour le périmètre demandé. |
| `RATE_LIMITED` | 429 | Limite de débit atteinte ; en-tête `Retry-After` en secondes. |
| `INTERNAL_ERROR` | 500 | Erreur inattendue (toujours remontée dans Sentry). |
| `SERVICE_UNAVAILABLE` | 503 | Base, cache ou modèle indisponible. |

Codes de succès utilisés : `200` (lecture, calcul, action), `201` (création), `202` (apprentissage accepté), `204` (suppression).

### 3.1 Correspondance des erreurs de requête

Règles appliquées par l'API (gestionnaires de `api/errors.py` et middleware de garde), identiques pour toutes les routes :

| Situation | Réponse |
|---|---|
| Identifiant invalide dans le chemin (par exemple un UUID mal formé) | 404 `NOT_FOUND` (même réponse qu'une ressource inexistante ou d'un autre utilisateur) |
| Corps JSON mal formé | 400 `INVALID_REQUEST` |
| Paramètre `limit` ou `cursor` invalide | 400 `INVALID_REQUEST` (avec `details`) |
| Autre paramètre de requête ou champ de corps invalide, champ inconnu (`extra="forbid"`) | 422 `VALIDATION_ERROR`, un élément de `details` par problème (`field`, `issue`, `message`) |
| Route inexistante | 404 `NOT_FOUND` |
| Méthode non autorisée sur une route existante | 405 `INVALID_REQUEST`, avec l'en-tête `Allow` |
| Corps de type non accepté (hors JSON et `multipart/form-data`) | 415 `UNSUPPORTED_MEDIA_TYPE` |
| Corps trop gros : JSON > 64 Ko, fichier > 10 Mo | 413 `PAYLOAD_TOO_LARGE` (contrôlé aussi sur les octets réellement reçus, pas seulement sur `Content-Length`) |
| Exception inattendue, ou erreur HTTP 5xx | 500 `INTERNAL_ERROR`, message générique, remontée dans Sentry avec le `request_id` |

- Dans `details`, `issue` vaut `required`, `unknown_field`, `must_be_greater_than`, `must_be_at_least`, `must_be_less_than`, `must_be_at_most`, `too_short`, `too_long`, `invalid_choice`, `invalid_format`, `invalid_type` ou `invalid`.
- `field` est le chemin du champ sans sa zone (`ad_spend`, `age` ; pour une ligne imbriquée, chemin pointé) ; la valeur refusée n'est jamais recopiée dans la réponse.
- Les en-têtes de la réponse portent toujours `X-Request-ID`, même pour une 500.

### 3.2 En-têtes de sécurité

Dès la phase 0, chaque réponse de l'API (succès comme erreur, y compris 500) porte :

| En-tête | Valeur |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `X-Frame-Options` | `DENY` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` |
| `Cache-Control` | `no-store` |

Une route peut fixer elle-même l'un de ces en-têtes ; le middleware ne l'écrase pas. La politique de sécurité de contenu du site (Next.js) relève de la phase 15, qui revérifie aussi l'ensemble de ces en-têtes de bout en bout.

## 4. Limites de débit

Fenêtre fixe par utilisateur, stockée dans Upstash.

| Portée | Routes | Limite |
|---|---|---|
| `simulate` | `POST /api/v1/predictions/simulate` | 120 / minute |
| `save` | `POST /api/v1/predictions` | 30 / minute |
| `read` | toutes les routes `GET` authentifiées | 300 / minute |
| `upload` | `POST /api/v1/admin/uploads` | 10 / heure |
| `train` | `POST /api/v1/admin/model-versions` | 5 / heure |
| `admin_write` | autres routes admin en écriture | 60 / minute |

Les limites `read` et `admin_write` ne sont pas appliquées aux routes d'administration des utilisateurs en phase 3 : `rate_limit(scope)` n'existe qu'à partir de la phase 9 (le test E2E-RATE-01 est en phase 15).

## 5. Objets partagés

### 5.1 `CampaignInput`

| Champ | Type | Règle |
|---|---|---|
| `campaign_channel` | enum | `Social Media`, `Email`, `PPC`, `SEO`, `Referral` |
| `campaign_type` | enum | `Awareness`, `Consideration`, `Conversion`, `Retention` |
| `ad_spend` | number | `> 0` et `<= 10000000` |
| `age` | integer | 18 à 100 |
| `gender` | enum | `Male`, `Female` |
| `income` | integer | 0 à 100000000 |
| `previous_purchases` | integer | 0 à 10000 |
| `loyalty_points` | integer | 0 à 10000000 |
| `pages_per_visit` | number | 0 à 1000 |
| `time_on_site` | number | 0 à 1440 (minutes) |
| `social_shares` | integer | 0 à 10000000 |
| `email_opens` | integer | 0 à 10000000 |
| `email_clicks` | integer | 0 à 10000000 |
| `advertising_platform` | string ou null | requis seulement si le modèle actif l'utilise ; 1 à 100 caractères imprimables, espaces de début et de fin retirés |
| `advertising_tool` | string ou null | même règle |

Champs inconnus : refusés (`VALIDATION_ERROR`, `issue: "unknown_field"`). Aucun champ n'est deviné.

### 5.2 `PredictionResult`

```json
{
  "id": null,
  "created_at": null,
  "label": null,
  "model_version": {"id": "uuid", "version": 3},
  "input": { "...": "CampaignInput tel que reçu" },
  "predictions": {
    "click_through_rate": 0.1542,
    "conversion_rate": 0.1038,
    "website_visits": 24.7
  },
  "derived": {
    "estimated_leads": 2.56,
    "estimated_cost_per_result": 1953.12
  },
  "performance": {
    "score": 48.2,
    "level": "medium",
    "notes": {"click_through_rate": 51.0, "estimated_leads": 49.3, "estimated_cost_per_result": 44.2},
    "thresholds": {"low_below": 41.2, "high_from": 58.9},
    "reference": "campaign_type"
  },
  "drivers": {
    "click_through_rate": [
      {"field": "ad_spend", "value": 5000, "contribution": 0.0041, "direction": "up"}
    ],
    "conversion_rate": [],
    "website_visits": []
  },
  "recommendations": {
    "status": "none_significant",
    "items": [
      {
        "lever": "campaign_channel",
        "from_value": "Email",
        "to_value": "PPC",
        "score_gain": 6.1,
        "new_score": 54.3,
        "new_level": "medium",
        "new_predictions": {"click_through_rate": 0.16, "conversion_rate": 0.105, "website_visits": 25.3},
        "new_derived": {"estimated_leads": 2.66, "estimated_cost_per_result": 1879.7}
      }
    ]
  },
  "warnings": [
    {"code": "LOW_MODEL_RELIABILITY", "field": null, "message": "The current model has low accuracy. Its predictions stay close to average values."},
    {"code": "OUT_OF_TRAINING_RANGE", "field": "ad_spend", "message": "Outside the values the model has seen. Treat this prediction with caution."}
  ]
}
```

Règles :
- `estimated_cost_per_result` vaut `null` si `estimated_leads == 0`.
- `performance.reference` vaut `campaign_type` ou `all_types` (repli si moins de 30 lignes de référence pour le type).
- `drivers.<chiffre>` : au plus 5 éléments, triés par valeur absolue décroissante de `contribution` ; `direction` vaut `up` ou `down`.
- `recommendations.status` vaut `found` (1 à 3 éléments) ou `none_significant` (liste vide).
- Codes d'avertissement possibles : `LOW_MODEL_RELIABILITY`, `OUT_OF_TRAINING_RANGE`, `REFERENCE_FALLBACK`.

## 6. Routes

### 6.1 Santé

**`GET /api/health`** (public)
200 : `{"status": "ok", "release": "<git_sha>"}`
Corps exact : deux champs seulement, `status` vaut toujours `"ok"`. `release` reprend `APP_RELEASE` (`local` par défaut ; l'empreinte du commit sur AWS). La route ne dépend d'aucun service (ni base ni cache) : elle indique seulement que le processus répond.

**`GET /api/ready`** (public)
- 200 : `{"status": "ready", "checks": {"database": "ok", "cache": "ok", "model": "ok" | "none_active"}, "schema_version": "20260923120000", "release": "<git_sha>"}`
- 503 : même corps avec `"status": "not_ready"` et la vérification en échec (valeur `"error"`). Ce corps **n'est pas** le format d'erreur standard : la route renvoie le même schéma `ReadyResponse` dans les deux cas. `schema_version` est absent du corps 503.

`model: "none_active"` ne rend pas le service "non prêt".

Progression par phase (D-050). Une vérification non encore branchée est **omise** du corps (jamais simulée à `"ok"`) ; les champs `cache` et `model` existent déjà dans le schéma, optionnels, pour que le contrat ne change pas :
- phase 1 : `checks` ne contient que `database` (`"ok"` ou `"error"`). 200 : `{"status": "ready", "checks": {"database": "ok"}, "schema_version": "20261003135339", "release": "<git_sha>"}` ; 503 : `{"status": "not_ready", "checks": {"database": "error"}, "release": "<git_sha>"}` ;
- phase 2 (livrée, D-073) : `cache` (Redis) s'ajoute. 200 : `{"status": "ready", "checks": {"database": "ok", "cache": "ok"}, "schema_version": "20261003135339", "release": "<git_sha>"}` ; 503 si l'une des deux sondes échoue : `{"status": "not_ready", "checks": {"database": "ok", "cache": "error"}, "release": "<git_sha>"}` (chaque vérification vaut `"ok"` ou `"error"`, sans `schema_version`). La sonde du cache envoie un `PING` avec des délais de 2 secondes, échoue fermée, journalise `readiness_failed` (`check=cache`, `reason` parmi `timeout`, `connection_error`, `bad_response`) sans URL ni mot de passe et n'envoie rien à Sentry. Le contrôle de santé de l'ALB reste `/api/health` : une panne de Redis ne fait pas redémarrer les tâches ;
- phase 8 : `model` s'ajoute.

La vérification de la base appelle `POST /rest/v1/rpc/schema_version` sur Kong avec la clé `anon` (jamais la clé de service, `ARCHITECTURE.md` 2.5), délai de 2 secondes, et attend une chaîne de 14 chiffres ; tout autre résultat (clé absente, délai dépassé, connexion refusée, statut différent de 200, charge invalide) donne 503. La cause est journalisée au niveau `warning` (`readiness_failed`, `check=database`, `reason`) sans clé, URL complète ni corps de réponse, et n'est pas envoyée à Sentry (panne attendue). La route est synchrone (pool de threads) et sonde la base à chaque appel : l'interface l'interroge toutes les 5 secondes. `/api/health` reste 200 quand la base est arrêtée.

### 6.2 Utilisateur courant

**`GET /api/v1/me`**
200 :
```json
{"id": "uuid", "email": "a@soronua.com", "full_name": "Awa N.", "role": "marketer", "is_active": true}
```
Corps exact : ces cinq champs seulement (`MeResponse`, `extra="forbid"`). Erreurs : `401 UNAUTHENTICATED` (jeton absent, invalide ou clé `anon` / de service), `401 TOKEN_EXPIRED`, `403 ACCOUNT_DISABLED` (profil introuvable ou désactivé), `503 SERVICE_UNAVAILABLE` (base indisponible). Un paramètre de requête inconnu est ignoré. La réponse porte `X-Request-ID`, les en-têtes de sécurité (3.2) et `Cache-Control: no-store`. OpenAPI déclare le schéma de sécurité `BearerAuth`. Les types TypeScript (`MeResponse`) sont générés par `make api-types`.

### 6.3 Référentiel

**`GET /api/v1/reference/options`**
Décrit le formulaire selon le modèle actif. 200 :
```json
{
  "currency": "USD",
  "enums": {
    "campaign_channel": ["Social Media", "Email", "PPC", "SEO", "Referral"],
    "campaign_type": ["Awareness", "Consideration", "Conversion", "Retention"],
    "gender": ["Male", "Female"]
  },
  "limits": {"ad_spend": {"min_exclusive": 0, "max": 10000000}, "age": {"min": 18, "max": 100}},
  "training_ranges": {"ad_spend": {"min": 100.05, "max": 9997.91}},
  "features_used": ["campaign_channel", "campaign_type", "ad_spend", "..."],
  "optional_categories": {"advertising_platform": [], "advertising_tool": []},
  "model_version": {"id": "uuid", "version": 3} 
}
```
`model_version` vaut `null` et `training_ranges` vaut `{}` s'il n'y a aucune version active (pas d'erreur, pour que l'interface affiche le bandeau).

**`GET /api/v1/reference/engagement-defaults?campaign_channel=Email&campaign_type=Conversion`**
200 :
```json
{"pages_per_visit": 5.6, "time_on_site": 7.8, "social_shares": 50, "email_opens": 9, "email_clicks": 4, "basis": "channel_and_type"}
```
`basis` vaut `channel_and_type`, `channel` ou `all` (replis décrits dans `LLD.md` section 6.5). 409 `NO_ACTIVE_MODEL` s'il n'y a pas de version active. 422 si un paramètre est hors énumération.

Erreurs de requête communes à toutes les routes : voir la section 3.1 (un paramètre de requête hors énumération donne 422 `VALIDATION_ERROR` avec `details`, un identifiant de chemin invalide donne 404 `NOT_FOUND`).

### 6.4 Prédictions

**`POST /api/v1/predictions/simulate`**
Corps : `CampaignInput`. Aucun enregistrement.
- 200 : `PredictionResult` avec `id`, `created_at`, `label` à `null` ;
- 409 `NO_ACTIVE_MODEL` ;
- 422 `VALIDATION_ERROR` ;
- 429.

**`POST /api/v1/predictions`**
Corps : `{"label": "Black Friday email" | null, "input": CampaignInput}`.
Le calcul est refait côté serveur (le résultat envoyé par l'interface n'est jamais accepté).
201 : `PredictionResult` complet avec `id`, `created_at`, `label`.

**`GET /api/v1/predictions?limit=20&cursor=...`**
Uniquement les prédictions de l'utilisateur connecté, les plus récentes d'abord. 200 :
```json
{
  "items": [
    {"id": "uuid", "label": "Black Friday email", "created_at": "2026-09-23T14:05:00Z",
     "campaign_channel": "Email", "campaign_type": "Conversion", "level": "medium", "score": 48.2,
     "model_version": {"id": "uuid", "version": 3}}
  ],
  "next_cursor": "eyJjIjoiMjAyNi0wOS0yM1QxNDowNTowMFoiLCJpIjoiLi4uIn0="
}
```

**`GET /api/v1/predictions/{id}`**
200 : `PredictionResult` enregistré. 404 si inexistante ou appartenant à un autre utilisateur.

**`DELETE /api/v1/predictions/{id}`**
204. 404 dans les mêmes cas.

> **Mode démonstration (D-922)** : `POST /api/v1/predictions` reçoit `{"name": "...", "input": CampaignInput}` (nom obligatoire, 1 à 100 caractères) ; `GET /api/v1/predictions` renvoie `{"items": [{"id", "name", "created_at", "level", "model_version": <numéro>}]}` (50 dernières, sans curseur) ; `GET .../{id}` renvoie le `PredictionResult` figé avec `label` = nom ; 404 « Prediction not found. » pour une prédiction d'un autre utilisateur (administrateur compris) ; `DELETE` : 204 ou 404.

### 6.5 Modèle actif (tous les rôles)

**`GET /api/v1/model/active`**
200 :
```json
{
  "id": "uuid", "version": 3, "data_scope": "all", "activated_at": "2026-09-23T10:00:00Z",
  "train_row_count": 6412, "holdout_row_count": 1588,
  "metrics": { "...": "voir DATA_MODEL.md 4.7" },
  "global_importance": { "...": "voir DATA_MODEL.md 4.7" }
}
```
409 `NO_ACTIVE_MODEL`.

### 6.6 Administration : utilisateurs

Toutes les routes exigent un administrateur actif (`403 FORBIDDEN` sinon, avant toute validation). Les tables sont lues et écrites avec le jeton de l'administrateur (RLS) ; la clé de service ne sert qu'à l'API d'administration de `supabase-auth` (invitation, bannissement, dates de confirmation).

Objet utilisateur : `{"id", "email", "full_name", "role": "marketer" | "admin", "is_active", "status": "invited" | "active" | "deactivated", "created_at"}` (sept champs exactement). `status` vaut `deactivated` quand `is_active` est faux (même si l'invitation n'a jamais été confirmée), sinon `invited` tant que l'utilisateur n'a jamais confirmé son invitation (lu via l'API d'administration Supabase), sinon `active`.

**`GET /api/v1/admin/users?limit=50&cursor=...`**
200 : `{"items": [objet utilisateur, ...], "next_cursor": "..." | null}`, du plus récent au plus ancien (`created_at` puis `id` décroissants). `limit` de 1 à 100 (défaut 50), `cursor` de 512 caractères au plus : base64 URL d'un JSON `{"c": <horodatage ISO 8601 avec microsecondes>, "i": <id>}` ; un curseur illisible, hors de ce format ou dont l'identifiant n'a pas le type de la colonne (UUID canonique pour les utilisateurs, entier de la plage `bigint` pour le journal) est `400 INVALID_REQUEST` (`field = "cursor"`, la valeur n'est jamais recopiée, D-094). `next_cursor` n'est renseigné que s'il reste des lignes. Réponses d'erreur : 400, 401, 403, 503.

**`POST /api/v1/admin/users/invite`**
Corps : `{"email": "x@soronua.com", "full_name": "Awa N.", "role": "marketer"}` ; les trois champs sont obligatoires, tout champ inconnu est refusé.
Règles :
- e-mail valide (motif `^[^@\s]+@[^@\s]+\.[^@\s]+$`), de 3 à 254 caractères, espaces retirés, mis en minuscules ;
- `full_name` de 1 à 120 caractères après suppression des espaces de bordure, sans caractère de contrôle ;
- `role` vaut `marketer` ou `admin` (jamais transmis par les métadonnées de l'invitation : il est appliqué ensuite par une mise à jour du profil avec le jeton de l'administrateur, SEC-04) ;
- lien de redirection de l'invitation : `${WEB_APP_URL}/auth/confirm`.

Réponses : 201 (objet utilisateur, `status = "invited"`) ; 409 `EMAIL_ALREADY_REGISTERED` pour tout profil existant, invité, actif ou désactivé (message « A user with this email already exists. », aucun appel à `supabase-auth`) ; 403 `FORBIDDEN` si la base ne confirme plus que l'appelant est administrateur actif (cache de rôle périmé, D-093) ; 422 `VALIDATION_ERROR` (aussi pour une adresse que `supabase-auth` refuse, champ `email`, D-093) ; 429 `RATE_LIMITED` (`Retry-After: 60`) quand `supabase-auth` limite l'envoi d'e-mails ; 503 `SERVICE_UNAVAILABLE`. Si une étape échoue après la création du compte Auth, l'invitation est annulée (le compte créé est supprimé) avant le 503. Journalise `user.invited` (métadonnées `{"email", "role"}`) après l'effet ; un échec d'écriture de l'audit n'annule rien et n'échoue pas la requête (D-084). Il n'y a pas de « renvoi d'invitation » dans la première version (D-083).

**`PATCH /api/v1/admin/users/{id}`**
Corps (au moins un champ non nul) : `{"role": "admin" | "marketer", "is_active": true | false, "full_name": "..."}` ; `is_active` est un vrai booléen (une chaîne est refusée), un `null` explicite compte comme « absent », tout champ inconnu est refusé.
Réponses : 200 (objet utilisateur) ; 404 `NOT_FOUND` « User not found. » (identifiant inconnu ou qui n'est pas un UUID, pour un administrateur) ; 409 `SELF_ACTION_FORBIDDEN` ; 409 `LAST_ADMIN` ; 422 `VALIDATION_ERROR` (corps sans champ : `field = "body"`, « Provide at least one field to update: role, is_active or full_name. ») ; 503.
Règles :
- l'identifiant de l'appelant donne toujours 409 `SELF_ACTION_FORBIDDEN`, quel que soit le champ, avant toute lecture ;
- seules les valeurs qui diffèrent de l'état actuel sont écrites : une valeur identique ne produit ni écriture, ni entrée d'audit, ni effacement du cache ;
- tous les champs modifiés sont écrits par **une seule** instruction (le déclencheur du dernier administrateur voit l'état final) ; son erreur `LAST_ADMIN` devient 409 « At least one active administrator is required. ».

Effets, dans cet ordre :
1. la base (une instruction) ;
2. si le corps porte `is_active` : le compte Supabase Auth est banni (`ban_duration` `876000h`, plus de connexion ni de rafraîchissement) ou rétabli (`none`), même si le drapeau en base avait déjà cette valeur, de sorte qu'une nouvelle tentative répare un changement à moitié fait ;
3. la clé `auth:profile:{id}` est effacée immédiatement quand le rôle change ou que le corps porte `is_active` ; un échec de Redis est remonté mais n'échoue pas la requête (la RLS refuse déjà les données d'un compte désactivé et les 60 s de durée de vie bornent un rôle périmé) ;
4. l'audit : `user.role_changed` (`{"email", "from", "to"}`), `user.deactivated` ou `user.reactivated` (`{"email"}`), une entrée par changement réel (un rôle et un statut changés ensemble en donnent deux).

Si le bannissement échoue, les étapes 3 et 4 sont tout de même faites, puis la réponse est `503 SERVICE_UNAVAILABLE` (D-085).

### 6.7 Administration : données

**`GET /api/v1/admin/dataset/summary`**
200 :
```json
{"seed_rows": 8000, "agency_rows": 0, "holdout_rows": 1603, "seed_loaded_at": "2026-10-03T23:50:00Z", "agency_holdout_rows": 0,
 "agency_only_available": false, "agency_only_min_rows": 250}
```

**`GET /api/v1/admin/uploads?limit=20&cursor=...`**
200 : liste `{"id", "source", "status", "file_name", "row_count", "uploaded_by": {"id", "full_name"} | null, "created_at", "ready_at", "error_message"}`.

**`POST /api/v1/admin/uploads`** (`multipart/form-data`)
Champs :
- `file` (obligatoire, `.csv`, 10 Mo maximum) ;
- `anonymization_confirmed` (obligatoire, doit valoir `true`).

Traitement : validation complète (règles dans `SECURITY_NOTES.md` section 4.3), puis stockage, puis insertion par lots de 1 000 lignes, puis passage à `ready`.

Réponses :
- 201 : objet import avec `status: "ready"` ;
- 409 `DUPLICATE_UPLOAD` ou `DUPLICATE_EXTERNAL_ID` ;
- 413 ; 415 ;
- 422 `CSV_INVALID`, avec au plus 100 éléments dans `details` et le total dans `message` (ex. "The file contains 412 errors. The first 100 are listed.") ;
- 422 `VALIDATION_ERROR` si la case d'anonymisation n'est pas cochée.

Si l'insertion échoue en cours de route : l'import passe à `failed`, ses lignes sont supprimées, `upload.failed` est journalisé, la réponse est 500 `INTERNAL_ERROR`.

**Version démonstration (D-932)** : l'import est `POST /api/v1/admin/dataset/upload` (champ `file` seul, pas de case d'anonymisation côté API : l'interface la demande avant l'envoi ; pas de table `dataset_uploads`). 201 `{"rows_imported": 400, "agency_rows_total": 400}` ; 409 `DUPLICATE_UPLOAD` (« This file has already been imported. ») quand toutes les lignes sont déjà là ; 422 `CSV_INVALID` avec au plus 100 `details` `{row, column, issue, message}` (ligne 1 = en-tête) ; 413 ; 415 (« Only CSV files are accepted. »). Le résumé ajoute `agency_loaded_at`. Entraînement `agency_only` : 422 `NOT_ENOUGH_DATA` « Not enough agency data to train: at least 250 rows are needed. » sous 250 lignes d'agence.

### 6.8 Administration : versions du modèle

**`POST /api/v1/admin/model-versions`**
Corps : `{"data_scope": "all" | "agency_only"}`.
Réponses :
- 202 : objet version (`status: "queued"`) ;
- 409 `TRAINING_ALREADY_RUNNING` ;
- 422 `NOT_ENOUGH_DATA` si `agency_only` et moins de 250 lignes de l'agence ;
- 503 si la file est indisponible (la version créée est alors passée à `failed` avec la raison "Queue unavailable").

Journalise `model.training_requested`.

**`GET /api/v1/admin/model-versions?limit=20&cursor=...`**
200 : liste `{"id", "version", "status", "data_scope", "is_active", "is_activatable", "created_at", "finished_at", "requested_by": {"id", "full_name"}}`.

**`GET /api/v1/admin/model-versions/{id}`**
200 : objet complet :
- les champs de la liste ;
- `metrics`, `comparison`, `global_importance`, `features_used` ;
- `train_row_count`, `holdout_row_count` ;
- `error_message`, `started_at`, `activated_at`.

L'interface interroge cette route toutes les 3 secondes tant que le statut est `queued` ou `running`.

**`POST /api/v1/admin/model-versions/{id}/activate`**
Corps : `{"expected_active_version_id": "uuid" | null}`.
Réponses :
- 200 : objet version, `is_active: true` ;
- 409 `MODEL_NOT_ACTIVATABLE` ou `ACTIVE_VERSION_CHANGED` ;
- 404.

Effet : `SET model:active_version_id` dans Upstash. Toutes les tâches `api` rechargent le modèle en moins de 30 secondes.

### 6.9 Administration : audit

**`GET /api/v1/admin/audit-log?limit=50&cursor=...`**
200 : `{"items": [entrée, ...], "next_cursor": "..." | null}` où une entrée est `{"id" (entier), "created_at", "actor": {"id", "full_name"} | null, "action", "target_type", "target_id", "metadata"}`, du plus récent au plus ancien (`created_at` puis `id` décroissants), mêmes `limit` (défaut 50, 1 à 100) et `cursor` que 6.6. `actor` vaut `null` (jamais omis) quand l'auteur est absent (action du système). `action` est l'une des dix actions de `DATA_MODEL.md` 4.6, `target_type` l'un de `user`, `upload`, `model_version`. Pour les actions de la phase 3 `metadata` vaut `{"email", "role"}` (`user.invited`), `{"email", "from", "to"}` (`user.role_changed`) ou `{"email"}` (`user.deactivated`, `user.reactivated`) ; la table n'est lisible que par les administrateurs, et l'e-mail de la cible y est permis (jamais de mot de passe, de jeton ni de réponse complète). Réponses d'erreur : 400, 401, 403, 503.


## Ajouts de la démonstration (D-929)

- `PredictionResult.performance.averages` : `{click_through_rate, conversion_rate, website_visits}`, moyenne de chaque chiffre sur le jeu d'apprentissage ; `null` pour un modèle entraîné avant cet ajout.
- `PredictionSummary` (liste de l'historique) : champs supplémentaires `campaign_channel`, `campaign_type`, `score`.
- `DatasetSummary` : champ supplémentaire `seed_loaded_at` (date de chargement du jeu de départ).
- Journal d'audit `model.training_succeeded` : métadonnées `train_rows` et `test_rows`.
