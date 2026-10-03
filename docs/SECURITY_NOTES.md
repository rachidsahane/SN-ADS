# SECURITY_NOTES.md : Sécurité

Document de référence n°10 sur 13.
Principes : sécurité par défaut, isolation stricte des données entre utilisateurs, validation de toutes les entrées, moindre privilège, aucun secret dans le code.

---

## 1. Acteurs

| Acteur | Identité | Canal |
|---|---|---|
| Anonyme | aucune | navigateur |
| `marketer` | compte Supabase actif, rôle `marketer` | navigateur, API avec jeton |
| `admin` | compte Supabase actif, rôle `admin` | navigateur, API avec jeton |
| Compte désactivé | compte Supabase, `is_active = false`, banni côté Auth | aucun accès |
| `api` (service) | clé de service, modules autorisés uniquement | serveur |
| `worker` (service) | clé de service | serveur |
| Pipeline CI/CD | rôle IAM CodeBuild (dans le VPC pour les migrations) | AWS |
| Exploitation de l'hôte de données | rôle IAM avec accès SSM (Claude Code, commandes tracées) | AWS Systems Manager uniquement |

## 2. Matrice des droits

L = lire, C = créer, M = modifier, S = supprimer, X = exécuter, "-" = aucun droit.

| Ressource | Anonyme | marketer | admin | worker | Pipeline |
|---|---|---|---|---|---|
| Pages publiques (connexion, mot de passe oublié) | L | L | L | - | - |
| Son propre profil | - | L | L | - | - |
| Profils des autres | - | - | L, M (rôle, statut, nom ; jamais le sien) | - | - |
| Invitation d'utilisateurs | - | - | X | - | - |
| Ses propres prédictions | - | L, C, S | L, C, S | - | - |
| Prédictions des autres | - | - | - | - | - |
| Simulation | - | X | X | - | - |
| Options et pré-remplissage du formulaire | - | L | L | - | - |
| Modèle actif (métadonnées, fiabilité, importance) | - | L | L | - | - |
| Versions du modèle (liste, détail, comparaison) | - | - | L | L, M | - |
| Lancer un apprentissage | - | - | X | - | - |
| Activer une version | - | - | X (via `activate_model_version`) | - | - |
| Imports et lignes de données | - | - | L, C | L | - |
| Fichiers CSV importés (Storage) | - | - | L, C | - | - |
| Artefacts du modèle (Storage) | - | - | - | L, C | - |
| Journal d'audit | - | - | L | C | - |
| Migrations de base | - | - | - | - | X |
| Déploiement | - | - | - | - | X (après approbation pour la production) |
| Commandes d'exploitation (`app.cli.*`) | - | - | - | - | exécutées uniquement par Claude Code avec la clé de service de l'environnement |

L'API applique cette matrice (dépendances `get_current_user`, `require_admin`) **et** la base l'applique indépendamment (RLS). Une faille dans l'une ne suffit pas à exposer des données.

## 3. Isolation des données au niveau de la base

Détail et SQL dans `DATA_MODEL.md` section 6. Règles non négociables :

1. RLS activée **et forcée** sur toutes les tables de `public`, dès la migration qui crée la table.
2. Aucun droit pour le rôle `anon`.
3. `predictions` : accès limité à `user_id = auth.uid()`. Aucune politique ne donne accès aux prédictions d'autrui, pas même aux administrateurs.
4. Tables d'administration (`dataset_uploads`, `dataset_rows`, `audit_log`) : `is_admin()` uniquement.
5. Toute politique exige aussi un compte actif (`is_active_user()` ou `is_admin()`), ce qui coupe l'accès d'un compte désactivé même avec un jeton encore valide.
6. Colonnes modifiables de `profiles` restreintes par droits de colonne (`full_name`, `role`, `is_active`) ; un administrateur ne peut pas modifier sa propre ligne ; le déclencheur `guard_last_admin` (avec verrou) garantit au moins un administrateur actif.
7. Fonctions `security definer` : toutes avec `set search_path = ''`, noms qualifiés (`public.`), contrôle du rôle en première instruction, droits `execute` accordés au seul rôle `authenticated`.
8. Espaces de stockage privés ; `model-artifacts` inaccessible avec un jeton utilisateur.
9. L'API interroge la base avec le jeton de l'utilisateur ; la clé de service est cantonnée aux modules de `ARCHITECTURE.md` 2.5, contrôlé par un test automatique.
10. Chaque politique est couverte par un test pgTAP positif et négatif (voir `TESTING.md`).
11. Seul `/auth/v1/*` de la pile Supabase est joignable depuis Internet (règle d'ALB). `/rest/v1`, `/storage/v1`, Postgres, Studio et `postgres-meta` ne sont pas exposés ; Studio et `postgres-meta` ne sont même pas déployés hors du poste local.

## 3 bis. Durcissement de l'hôte de données

- Instance en sous-réseau privé, sans adresse publique, sans paire de clés SSH ni port 22 ouvert ; administration uniquement par AWS Systems Manager (sessions et commandes journalisées dans CloudTrail).
- Groupe de sécurité : port 8000 (Kong) depuis l'ALB, `api`, `worker` et CodeBuild ; port 5432 depuis CodeBuild seulement ; rien d'autre.
- Volume EBS, instantanés et compartiments S3 chiffrés (clés gérées par AWS) ; compartiments sans accès public, versionnés, accès limité au rôle de l'hôte.
- Le fichier `.env` de la pile est produit au déploiement depuis Secrets Manager, avec les droits 600, propriétaire `root`, jamais journalisé.
- Mises à jour de sécurité du système : correctifs automatiques Amazon Linux (SSM Patch Manager, fenêtre hebdomadaire de nuit).
- Les conteneurs de la pile tournent avec les images officielles figées par digest, sans mode privilégié, avec redémarrage automatique.

## 4. Validation des entrées

### 4.1 Règles générales
- Toute entrée est validée à la frontière de l'API par un schéma Pydantic strict (`extra="forbid"`, types stricts, bornes). L'interface valide aussi (Zod) pour le confort, mais **l'API ne fait jamais confiance au navigateur**.
- Corps JSON limité à 64 Ko ; fichier limité à 10 Mo et 50 000 lignes.
- Chaînes : espaces de début et de fin retirés, caractères de contrôle refusés, longueurs maximales explicites.
- Identifiants de chemin : UUID valides, sinon 404 (pas 422, pour ne rien révéler).
- Paramètres de pagination : `limit` entre 1 et 100 ; curseur invalide : 400 `INVALID_REQUEST`.
- Aucune requête SQL construite par concaténation ; toutes les requêtes passent par le client Supabase (paramétré) ou des fonctions SQL.

### 4.2 Saisie de campagne
Bornes : `API_SPEC.md` section 5.1. Les valeurs calculées (prédictions, score, niveau, recommandations) ne sont jamais acceptées en entrée : l'API les recalcule toujours, y compris à l'enregistrement.

### 4.3 Import CSV (vérifié en entier avant toute écriture)
1. Type : extension `.csv` et contenu texte ; `Content-Type` `text/csv` ou `application/vnd.ms-excel` accepté, sinon 415.
2. Encodage UTF-8 (BOM toléré) ; sinon erreur de fichier.
3. Séparateur virgule, en-tête obligatoire, 20 colonnes exactement, noms exacts (`LLD.md` 5.1), aucune colonne en double.
4. Au moins 1 ligne, au plus 50 000.
5. Aucune cellule vide.
6. Types et bornes par colonne, identiques aux contraintes de `dataset_rows` (`DATA_MODEL.md` 4.3). Messages explicites, par exemple "ClickThroughRate must be a fraction between 0 and 1 (0.05 = 5%)."
7. Énumérations exactes (casse comprise) pour `Gender`, `CampaignChannel`, `CampaignType`.
8. `CustomerID` entier ≥ 1, unique dans le fichier et absent des données de l'agence déjà importées.
9. Cellules texte (`AdvertisingPlatform`, `AdvertisingTool`) : 1 à 100 caractères, refus si elles commencent par `=`, `+`, `-`, `@`, tabulation ou retour chariot (injection de formules).
10. Empreinte SHA-256 du contenu : refus si un import identique est `importing` ou `ready`.
11. Case d'anonymisation cochée obligatoire.
12. Nom de fichier : conservé pour affichage uniquement (255 caractères maximum) ; le chemin de stockage est `<upload_id>/upload.csv`, jamais le nom fourni.

### 4.4 Authentification
- Mots de passe : 10 caractères minimum (réglage Supabase Auth et contrôle de l'interface).
- Redirections après authentification (`next`) : chemins internes uniquement (commençant par `/` et pas par `//`), sinon `/predict`.
- Messages d'échec de connexion identiques que l'e-mail existe ou non.
- Protection contre les tentatives répétées de connexion : limites natives de Supabase Auth, laissées actives.

## 5. Gestion des secrets

- Aucun secret dans le dépôt, les images Docker, les journaux, Sentry ou les messages d'erreur. `gitleaks` en crochet `pre-commit` et en CI bloque tout commit contenant un secret.
- Local : fichiers `.env*` ignorés par Git ; seuls les `.env.example` sont versionnés, avec des valeurs factices.
- Staging et production : AWS Secrets Manager, injecté dans les tâches ECS par référence (`secrets` de la définition de tâche), jamais en variable d'environnement en clair dans CDK.
- Rôles IAM distincts, chacun limité à son besoin :
  - rôle d'exécution ECS : lecture du seul secret de son environnement et tirage depuis ECR ;
  - rôle de tâche `api` et `worker` : aucun droit AWS supplémentaire ;
  - rôle CodeBuild : ECR, ECS de ses environnements, secrets `cicd` et `web-build`, journaux.
- La clé de service Supabase n'est présente que dans les secrets `app` (api, worker) et `data` (pile Supabase), jamais dans `web-build`.
- En local, `docker-compose.yml` donne à chaque service une liste explicite de variables (`environment:`) et n'utilise jamais `env_file: .env` : le `.env` complet n'est jamais transmis en bloc, donc la clé de service n'atteint pas le conteneur `web` (voir `decisions.md` D-010).
- Les clés de la pile Supabase (`JWT_SECRET`, `ANON_KEY`, `SERVICE_ROLE_KEY`, `POSTGRES_PASSWORD`) sont propres à chaque environnement, générées par `deploy/supabase/generate_keys.py` directement dans Secrets Manager, sans jamais être affichées. Changer `JWT_SECRET` invalide toutes les sessions et impose de régénérer `ANON_KEY` et `SERVICE_ROLE_KEY`.
- Sentry : `send_default_pii=False`, suppression des en-têtes `Authorization` et `Cookie`, pas d'e-mail, pas de valeurs saisies ; seul l'identifiant utilisateur (UUID) est attaché.
- Rotation :
  - si une clé est exposée, la régénérer (pile Supabase, Upstash, Sentry ou SES), mettre à jour le secret AWS, redéployer ;
  - la procédure est décrite dans `CI_CD.md` section 6.4.
- En-têtes HTTP de sécurité posés par Next.js et l'API :
  - `Strict-Transport-Security` (1 an) ;
  - `X-Content-Type-Options: nosniff` ;
  - `Referrer-Policy: strict-origin-when-cross-origin` ;
  - `X-Frame-Options: DENY` ;
  - `Content-Security-Policy` limitée à l'origine elle-même (l'authentification est servie sur la même origine) et à l'URL d'ingestion Sentry.
  - Dès la phase 0, chaque réponse de l'API porte déjà ces en-têtes, avec une CSP stricte `default-src 'none'; frame-ancestors 'none'` et `Cache-Control: no-store` (valeurs exactes : `API_SPEC.md` 3.2). La CSP de Next.js et la revérification de l'ensemble relèvent de la phase 15 (voir `decisions.md` D-019).
- Cookies de session : `Secure`, `HttpOnly` quand le serveur les pose, `SameSite=Lax`.

## 6. Cas limites identifiés et comportement attendu

| ID | Cas | Comportement attendu |
|---|---|---|
| SEC-01 | Un utilisateur modifie l'identifiant dans l'URL ou l'API pour lire la prédiction d'un autre | 404 `NOT_FOUND`, aucune information sur l'existence ; la RLS renvoie zéro ligne même si l'API se trompait. |
| SEC-02 | Un `marketer` appelle une route `/api/v1/admin/*` | 403 `FORBIDDEN` ; tentative journalisée (niveau avertissement) avec `user_id` et route. |
| SEC-03 | Un `marketer` tente d'interroger directement les tables ou les fichiers via l'URL publique | 404 : `/rest/v1` et `/storage/v1` ne sont pas exposés. Même depuis le réseau privé, la RLS ne lui rendrait que ses prédictions, son profil et les métadonnées des versions. |
| SEC-04 | Un utilisateur modifie ses métadonnées Supabase pour se déclarer `admin` | Sans effet : le rôle vient uniquement de `profiles.role`, jamais des métadonnées. |
| SEC-05 | Jeton forgé, signé avec une autre clé, avec un autre algorithme, ou venant d'un autre environnement | 401 `UNAUTHENTICATED` (secret et émetteur propres à chaque environnement). |
| SEC-06 | Jeton expiré | 401 `TOKEN_EXPIRED` ; l'interface rafraîchit une fois, sinon renvoie à la connexion avec brouillon conservé. |
| SEC-07 | Compte désactivé avec un jeton encore valide | 403 `ACCOUNT_DISABLED` dès que le cache de profil est invalidé (immédiat à la désactivation, 60 s au maximum dans tous les cas) ; la RLS refuse de toute façon ; le rafraîchissement est impossible (bannissement Auth). |
| SEC-08 | Un administrateur tente de se rétrograder ou de se désactiver | 409 `SELF_ACTION_FORBIDDEN`. |
| SEC-09 | Suppression du dernier administrateur actif, y compris par deux actions simultanées | 409 `LAST_ADMIN` ; le verrou du déclencheur empêche la situation. |
| SEC-10 | Fichier CSV contenant des formules | Refusé avant toute écriture. |
| SEC-11 | Fichier CSV énorme ou compressé déguisé | Refus à 10 Mo dès la lecture du flux, sans tout charger en mémoire. |
| SEC-12 | Nom de fichier malveillant (`../../x`, caractères spéciaux) | Jamais utilisé comme chemin ; affiché échappé. |
| SEC-13 | Champ inconnu ou valeur calculée envoyée dans une requête | 422 `VALIDATION_ERROR` (`unknown_field`). |
| SEC-14 | Injection de texte dans le nom d'une prédiction (HTML, script) | Stocké tel quel, affiché échappé par React ; aucun rendu HTML de contenu utilisateur. |
| SEC-15 | Rafale de requêtes | 429 `RATE_LIMITED` selon les limites de `API_SPEC.md` 4. |
| SEC-16 | Upstash indisponible | Limitation de débit en mode ouvert (laisse passer), alerte Sentry ; lancement d'apprentissage refusé en 503 ; le reste fonctionne via la base. |
| SEC-17 | Redirection ouverte via `next` | Refusée, remplacée par `/predict`. |
| SEC-18 | Tentative d'exécuter une commande de test en production (`create_test_users`) | Refus immédiat si `APP_ENV=production`. |
| SEC-19 | Erreur inattendue | 500 `INTERNAL_ERROR` sans détail technique ; événement Sentry complet avec `request_id`, route, `user_id`, version. |
| SEC-20 | Artefact de modèle altéré ou d'un format inconnu | Chargement refusé (`bundle_schema_version`, présence des 4 fichiers) ; la version précédemment chargée reste en service ; alerte Sentry. |
| SEC-21 | Travail de file rejoué deux fois | Mise à jour conditionnelle `queued` vers `running` : le second passage est ignoré. |
| SEC-22 | Lien d'invitation ou de réinitialisation intercepté après usage | Lien à usage unique ; réutilisation refusée par Supabase Auth. |
| SEC-23 | Données clients non anonymisées importées malgré la case | Hors de portée d'un contrôle automatique fiable ; responsabilité de l'administrateur, tracée dans l'audit (`anonymization_confirmed`, auteur, date). |
| SEC-24 | Disque de l'hôte de données rempli à 80 % | Alarme CloudWatch par e-mail ; agrandissement du volume EBS sans arrêt, consigné dans `docs/decisions.md`. |
| SEC-25 | Sauvegarde nocturne absente ou en échec | Alarme CloudWatch (aucun nouvel objet dans le compartiment depuis 26 heures) ; relance manuelle par SSM et analyse. |
| SEC-26 | Hôte de données arrêté ou perdu | Alarme ; l'application renvoie 503 avec le message prévu ; reconstruction depuis le dernier instantané EBS ou la dernière sauvegarde (`CI_CD.md` 6.2). |
