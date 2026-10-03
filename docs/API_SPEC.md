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
- Pagination par curseur : paramètres `limit` (défaut 20, maximum 100) et `cursor` (chaîne opaque). Réponse : `{"items": [...], "next_cursor": "..." | null}`.

## 2. Authentification

- Schéma : `Authorization: Bearer <access_token>`, jeton d'accès émis par `supabase-auth` (JWT).
- Vérification par l'API :
  - signature HS256 vérifiée avec `SUPABASE_JWT_SECRET` (secret propre à la pile Supabase de l'environnement) ; tout autre algorithme est refusé ;
  - `exp` non dépassé, `aud = "authenticated"`, `iss = SUPABASE_JWT_ISSUER`, `sub` présent, `role = "authenticated"`.
- Le profil (`role`, `is_active`) est ensuite lu (cache Upstash 60 s) :
  - profil introuvable ou `is_active = false` : `403 ACCOUNT_DISABLED` ;
  - route `/api/v1/admin/*` et `role != 'admin'` : `403 FORBIDDEN`.
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
| `SELF_ACTION_FORBIDDEN` | 409 | Un administrateur tente de modifier son propre rôle ou statut. |
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
- phase 2 : `cache` (Redis) s'ajoute ; phase 8 : `model` s'ajoute.

La vérification de la base appelle `POST /rest/v1/rpc/schema_version` sur Kong avec la clé `anon` (jamais la clé de service, `ARCHITECTURE.md` 2.5), délai de 2 secondes, et attend une chaîne de 14 chiffres ; tout autre résultat (clé absente, délai dépassé, connexion refusée, statut différent de 200, charge invalide) donne 503. La cause est journalisée au niveau `warning` (`readiness_failed`, `check=database`, `reason`) sans clé, URL complète ni corps de réponse, et n'est pas envoyée à Sentry (panne attendue). La route est synchrone (pool de threads) et sonde la base à chaque appel : l'interface l'interroge toutes les 5 secondes. `/api/health` reste 200 quand la base est arrêtée.

### 6.2 Utilisateur courant

**`GET /api/v1/me`**
200 :
```json
{"id": "uuid", "email": "a@soronua.com", "full_name": "Awa N.", "role": "marketer", "is_active": true}
```

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

**`GET /api/v1/admin/users?limit=50&cursor=...`**
200 : liste d'objets `{"id", "email", "full_name", "role", "is_active", "status": "invited" | "active" | "deactivated", "created_at"}`.
`status` vaut `invited` tant que l'utilisateur n'a jamais confirmé son invitation (lu via l'API d'administration Supabase).

**`POST /api/v1/admin/users/invite`**
Corps : `{"email": "x@soronua.com", "full_name": "Awa N.", "role": "marketer"}`.
Règles :
- e-mail valide, 254 caractères maximum, mis en minuscules ;
- `full_name` de 1 à 120 caractères ;
- lien de redirection de l'invitation : `${WEB_APP_URL}/auth/confirm`.

Réponses : 201 (objet utilisateur) ; 409 `EMAIL_ALREADY_REGISTERED`. Journalise `user.invited`.

**`PATCH /api/v1/admin/users/{id}`**
Corps (au moins un champ) : `{"role": "admin" | "marketer", "is_active": true | false, "full_name": "..."}`.
Réponses : 200 ; 409 `SELF_ACTION_FORBIDDEN` ; 409 `LAST_ADMIN` ; 404.
Effets :
- la désactivation bannit aussi le compte côté Supabase Auth (plus de rafraîchissement possible) ;
- la clé `auth:profile:{id}` est effacée immédiatement ;
- journalise `user.role_changed`, `user.deactivated` ou `user.reactivated`.

### 6.7 Administration : données

**`GET /api/v1/admin/dataset/summary`**
200 :
```json
{"seed_rows": 8000, "agency_rows": 0, "holdout_rows": 1603, "agency_holdout_rows": 0,
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
200 : liste `{"id", "created_at", "actor": {"id", "full_name"} | null, "action", "target_type", "target_id", "metadata"}`.
