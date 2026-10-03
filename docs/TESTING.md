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
| Base de données | pgTAP (`supabase test db --db-url`, contre le conteneur `supabase-db`) | Chaque politique RLS (cas autorisé et refusé), déclencheurs (`handle_new_user`, `guard_last_admin`), index uniques (un seul actif, un seul en cours, doublons d'import), `activate_model_version` (tous les codes d'erreur), droits par colonne sur `profiles`. | conteneur `supabase-db` |
| Intégration API | pytest + `TestClient` FastAPI | Chaque route : authentification, rôles, validation, format d'erreur, codes de statut, isolation, limites de débit, import complet, demande d'apprentissage, activation, worker (un travail de bout en bout sur `small_dataset.csv`), rechargement du modèle par le pointeur. | pile locale en conteneurs (Supabase auto-hébergé, Redis, Mailpit) |
| Bout en bout | Playwright | Parcours utilisateurs réels dans le navigateur (section 3). | pile locale complète en conteneurs ou staging ; Playwright s'exécute dans son image Docker officielle |
| Fumée | Playwright (`@smoke`) | Après déploiement en production : connexion, page Model, une simulation. Aucune écriture. | Production |
| Infrastructure | pytest + assertions CDK | Présence et paramètres clés : HTTPS seul, tâches en sous-réseaux privés, worker sans entrée, disjoncteur activé, secrets référencés et non en clair ; hôte de données sans adresse publique ni SSH, volume chiffré, port 5432 ouvert au seul groupe CodeBuild, seul `/auth/v1/*` routé vers Kong, plan de sauvegarde présent. | aucune |

Tests de garde d'architecture (unitaire API) :
- `test_service_client_is_only_imported_by_allowed_modules` : analyse les imports et échoue si `get_service_client` apparaît hors des modules autorisés (`ARCHITECTURE.md` 2.5).
- `test_domain_has_no_io_imports` : `app/domain` n'importe ni `supabase`, ni `redis`, ni `httpx`, ni `app.infra`.
- `test_enum_values_match_database` : les énumérations de `dataset_schema.py` sont identiques à celles des migrations.
- `test_no_environment_reads_outside_config`.

## 3. Scénarios Playwright

Fichiers dans `apps/web/e2e/`. Navigateurs : Chromium (tous les scénarios), Firefox et WebKit (scénarios marqués `@cross`). Chaque scénario démarre d'un état connu (section 5).

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

Aucun fichier ne peut être exclu de la couverture sans entrée dans `docs/decisions.md`.

## 5. Données de test

- **Unitaire et intégration** :
  - `tests/fixtures/small_dataset.csv` : 300 lignes générées une fois par un script déterministe (graine 42), avec des relations volontairement fortes entre budget, canal et les trois cibles. Ce jeu permet de tester que les recommandations et les facteurs réagissent, ce que le jeu de départ ne permet pas.
  - Fichiers `invalid_*.csv` : un défaut par fichier.
  - `tests/fixtures/golden/` : résultats attendus figés (notes, seuils, niveau, recommandations) pour des saisies fixes sur un paquet entraîné à partir de `small_dataset.csv`. Toute modification d'un fichier `golden` doit être justifiée dans le commit.
- **Fabriques** (`tests/factories.py`) : `make_campaign_input(**overrides)`, `make_profile(role=...)`, `make_dataset_frame(n, seed)`.
- **Base locale** : `make db-reset` avant chaque session d'intégration ; chaque test d'intégration crée ses propres utilisateurs (préfixe d'e-mail aléatoire) et nettoie ce qu'il crée.
- **Playwright local** :
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
