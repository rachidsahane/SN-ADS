# CLAUDE.md : Référence permanente de Claude Code

Ce fichier est placé à la racine du dépôt. Les 12 autres documents sont dans `docs/`. Relire ce fichier au début de chaque session.

---

## 1. Le projet en bref

**Soro Nua Campaign Predictor** est un outil interne de Soro Nua Agency (Douala), réalisé dans le cadre d'un stage.

- **Ce que fait l'outil** :
  - un membre de l'équipe marketing décrit une campagne publicitaire en ligne ;
  - l'outil prédit le taux de clic, le taux de conversion et le nombre de visites ;
  - il en déduit un niveau de performance (low / medium / high) ;
  - il montre ce qui pèse sur chaque chiffre et propose jusqu'à trois changements pour faire mieux.
- **Données** : un jeu de départ fabriqué (8 000 lignes) sert à apprendre ; l'agence pourra importer ses propres données au même format.
- **Modèle** : les administrateurs relancent l'apprentissage et activent une nouvelle version seulement si elle est au moins aussi fiable.
- **Tout est conteneurisé** : interface, API, modèle, base de données, authentification, stockage et outils tournent dans des conteneurs Docker, en local comme sur AWS. Seuls Upstash, Sentry, Amazon SES, GitHub et la CI/CD AWS sont des services en ligne.
- **Langue** : interface en anglais.
- **Destinataire** : l'utilisateur n'est pas développeur. Il ne lit ni ne modifie le code. Tout est construit par Claude Code à partir des documents ci-dessous.

| Document | Contenu | À consulter quand |
|---|---|---|
| `docs/PROJECT_BRIEF.md` | Le besoin validé | Toujours en cas de doute sur le "quoi" |
| `docs/PRD.md` | Fonctionnalités, récits, parcours, cas limites, libellés | Avant toute fonctionnalité |
| `docs/ARCHITECTURE.md` | Composants, échanges, stack, déploiement | Avant tout choix structurant |
| `docs/DATA_MODEL.md` | Tables, contraintes, RLS, migrations | Avant toute migration ou requête |
| `docs/API_SPEC.md` | Routes, formats, erreurs, codes | Avant toute route ou appel |
| `docs/LLD.md` | Arborescence, modules, algorithmes, signatures, nommage | Avant tout fichier ou fonction |
| `docs/CONVENTIONS.md` | Versions, style, commits, branches, patterns | À chaque commit |
| `docs/ENV_SETUP.md` | Variables d'environnement, installation | Avant toute configuration |
| `docs/TESTING.md` | Niveaux, scénarios Playwright, couverture, données | Avant d'écrire du code (tests d'abord) |
| `docs/SECURITY_NOTES.md` | Droits, isolation, validation, secrets, cas limites | Avant toute route, table ou entrée |
| `docs/CI_CD.md` | Pipelines, blocages, retour arrière | Avant toute livraison |
| `docs/ROADMAP.md` | Phases et suivi | Au début et à la fin de chaque session |
| `docs/decisions.md` | Décisions prises en cours de route | Chaque fois qu'un choix n'est pas couvert |

Ordre de priorité en cas de contradiction : `PROJECT_BRIEF.md` > `SECURITY_NOTES.md` > `DATA_MODEL.md` > `API_SPEC.md` > `LLD.md` > autres. Toute contradiction trouvée est corrigée dans le document de rang inférieur et consignée dans `docs/decisions.md`.

## 2. Stack imposée : aucune substitution possible

| Besoin | Outil imposé |
|---|---|
| Base de données, authentification, stockage de fichiers | Supabase **auto-hébergé** : pile Docker officielle réduite (`deploy/supabase/`), en local et sur un hôte EC2 dédié par environnement |
| Hébergement et infrastructure | AWS (ECS Fargate, ALB, ECR, Secrets Manager, CloudWatch, Route 53, ACM, région `eu-west-3`), décrite avec AWS CDK en Python |
| CI/CD | AWS CodePipeline V2 + CodeBuild + CodeConnections |
| Conteneurs | Docker pour **tous** les composants (Docker Compose en local et sur l'hôte de données, ECS Fargate pour l'application) |
| Surveillance des erreurs | Sentry |
| Cache et file d'attente | Upstash Redis (conteneur `redis` en local uniquement) |
| Tests d'interface | Playwright |
| Versionnement | GitHub |
| E-mails | Amazon SES (SMTP de `supabase-auth`) ; Mailpit en local |
| IA générative | Gemini, **non utilisé en première version** |
| Code | Python 3.12 + FastAPI + XGBoost (api, worker) ; Next.js 15 + TypeScript + Tailwind + shadcn/ui + TanStack Query + React Hook Form + Zod + Recharts (web) |

Aucun autre service externe, aucune autre bibliothèque majeure, sans analyse en plan mode et entrée dans `docs/decisions.md`.

## 3. TOUJOURS

1. Lire `docs/ROADMAP.md` au début de la session et travailler **uniquement** sur la phase en cours.
2. Écrire les tests **avant** le code, les voir échouer, puis implémenter (commit `test(...)` avant `feat(...)`).
3. Respecter l'arborescence, les noms et les signatures de `docs/LLD.md`.
4. Valider toute entrée à la frontière (Pydantic `extra="forbid"`, Zod) avec les bornes de `docs/API_SPEC.md`.
5. Interroger la base avec le **jeton de l'utilisateur** ; créer RLS activée et forcée, politiques et tests pgTAP dans la migration qui crée une table.
6. Renvoyer 404 pour toute ressource d'un autre utilisateur.
7. Utiliser le format d'erreur standard et les codes de `docs/API_SPEC.md` section 3, partout.
8. Faire remonter toute exception inattendue via `infra/observability.py` ou `lib/observability.ts` (Sentry à partir de la phase 16), avec `request_id`, `user_id`, route, version et identifiants métier, jamais de donnée personnelle.
9. Lire la configuration uniquement dans `app/config.py` et `src/lib/env.ts` ; documenter toute nouvelle variable dans `docs/ENV_SETUP.md` et les `.env.example` dans le même commit.
10. Figer toute dépendance à une version exacte et la noter dans `docs/CONVENTIONS.md`.
11. Mettre les textes affichés en anglais dans `src/lib/labels.ts`, conformes au glossaire du PRD.
12. Lancer `make check` avant chaque commit poussé et avant chaque pull request.
13. Tenir à jour le tableau de suivi de `docs/ROADMAP.md` et `docs/decisions.md`.
14. Expliquer à l'utilisateur, en fin de session et en langage courant (sans jargon, en français), ce qui a été fait, ce qu'il peut vérifier à l'écran et comment.
15. Garder les commandes d'exploitation et le worker idempotents.
16. Corriger un bug en commençant par un test qui le reproduit.
17. Exécuter toute commande (tests, contrôles, migrations, CDK, CLI) via le `Makefile` ou les buildspecs, dans le conteneur `toolbox` ou les images du projet.

## 4. JAMAIS

1. Jamais de secret, clé, mot de passe ou jeton dans le code, les tests, les journaux, Sentry, les commits, les pull requests ou les messages à l'utilisateur.
2. Jamais obtenir la clé de service Supabase hors de cette liste fermée (identique à `docs/ARCHITECTURE.md` 2.5) :
   - le worker (`app/worker.py`, `services/training_job.py`) ;
   - `services/model_registry.py` ;
   - `services/user_admin_service.py` ;
   - `app/cli/*`.

   Le client de service est défini uniquement dans `infra/supabase_clients.py` ; les `repositories` le reçoivent en paramètre et ne l'obtiennent jamais eux-mêmes. Jamais dans l'image `web` ni le navigateur.
3. Jamais d'accès direct aux tables Supabase depuis le navigateur.
4. Jamais désactiver RLS, contourner une politique, affaiblir une contrainte, ignorer un test ou une règle de lint pour faire passer un contrôle.
5. Jamais de poussée directe sur `dev`, `staging` ou `main`, jamais de poussée forcée, jamais de réécriture d'historique partagé.
6. Jamais modifier une migration déjà appliquée.
7. Jamais faire confiance à une valeur calculée par l'interface (prédiction, score, rôle).
8. Jamais substituer un élément de la stack imposée, ni utiliser Gemini ou un autre modèle de langage en première version.
9. Jamais implémenter une fonctionnalité "plus tard" ou "hors périmètre" du PRD sans passer par la règle de la section 7.
10. Jamais créer de données de test en production, ni exécuter `create_test_users` en production.
11. Jamais afficher de trace technique à l'utilisateur de l'application.
12. Jamais poser de question technique à l'utilisateur (section 6).
13. Jamais déclarer une phase terminée si un seul critère de la section 8 n'est pas rempli.
14. Jamais installer ou lancer un composant de la solution hors d'un conteneur, ni exposer sur Internet autre chose que le site, `/api/*` et `/auth/v1/*` (pas de `/rest/v1`, `/storage/v1`, Postgres, Studio).
15. Jamais mettre à jour une image de la pile Supabase de production sans sauvegarde préalable réussie.

## 5. Règle des trois branches

- `dev` = construction. `staging` = validation (déployé sur staging). `main` = production (déployé après approbation manuelle de l'utilisateur).
- Travail d'une phase :
  1. partir de `dev` à jour ;
  2. créer la branche `phase/<NN>-<slug>` ;
  3. commits TDD ;
  4. `make check` ;
  5. pull request vers `dev`, fusion en squash quand `checks` est vert (avant la phase 18 : `make check` vert collé dans la pull request).
- Promotion vers `staging` : pull request depuis `dev` uniquement, fusion par merge commit.
- Promotion vers `main` : pull request depuis `staging` uniquement, quand le pipeline staging du commit est vert et que l'utilisateur a validé sur staging. La mise en production attend ensuite son approbation par e-mail.
- Correctif urgent : `fix/<slug>` depuis `dev`, même chemin, aucun raccourci.
- Seule exception : le premier déploiement de staging de la phase 17, fait à la main et documenté, avant que les pipelines existent.

## 6. Ne jamais poser de question technique à l'utilisateur

L'utilisateur n'est pas développeur. Quand un choix technique n'est pas couvert par les documents :
1. décider en appliquant, dans l'ordre : sécurité par défaut, simplicité, cohérence avec les documents existants, solution la plus standard et la mieux documentée ;
2. appliquer la décision ;
3. la consigner dans `docs/decisions.md` (date, phase, décision, raison en une phrase, documents mis à jour) et mettre à jour le document de référence concerné ;
4. l'expliquer à l'utilisateur en fin de session, en une ou deux phrases de langage courant.

Seules exceptions (ce ne sont pas des questions techniques) : demander à l'utilisateur ce que lui seul peut fournir, c'est-à-dire :
- accès et comptes (AWS, Upstash, Sentry, GitHub) ;
- domaine ;
- adresses e-mail de notification et du premier administrateur ;
- approbation d'une mise en production ;
- validation fonctionnelle sur staging.

Ces demandes sont formulées en langage courant, avec les étapes exactes à suivre.

## 7. Demandes hors ROADMAP : plan mode d'abord

Toute demande de l'utilisateur qui sort du périmètre de `docs/ROADMAP.md` (nouvelle fonctionnalité, changement de comportement, nouvelle dépendance, nouveau service) passe d'abord par une analyse en **plan mode**, sans aucune modification de fichier. Le plan présente en langage courant :
- ce qui serait fait ;
- les documents touchés ;
- les risques (sécurité, données, coûts) ;
- l'effet sur les phases restantes ;
- une proposition de place dans la ROADMAP.

L'implémentation ne commence qu'après accord explicite de l'utilisateur sur ce plan. Les documents de référence sont mis à jour **avant** le code.

## 8. Définition de terminé d'une phase

Une phase est terminée quand **tous** les points suivants sont vrais :
1. Tous les éléments du périmètre de la phase dans `docs/ROADMAP.md` sont réalisés, rien de plus.
2. Chaque comportement ajouté a été couvert par un test écrit avant le code ; les scénarios Playwright attribués à la phase existent et passent.
3. `make check` est vert (formatage, lint, types, types OpenAPI, unitaires, intégration, pgTAP, audits) et la couverture respecte `docs/TESTING.md`.
4. Chaque nouvelle table a RLS activée et forcée, avec tests positifs et négatifs.
5. Aucune erreur ni avertissement dans la console du navigateur et les journaux pendant le parcours de la phase.
6. Les erreurs possibles de la phase sont remontées avec leur contexte (observabilité locale avant la phase 16, Sentry ensuite).
7. Les documents touchés sont à jour (`LLD.md`, `API_SPEC.md`, `DATA_MODEL.md`, `ENV_SETUP.md`, `CONVENTIONS.md`...), ainsi que `docs/decisions.md`.
8. La pull request vers `dev` est fusionnée (contrôle `checks` vert à partir de la phase 18).
9. La "définition de terminé à l'écran" de la phase a été vérifiée par Claude Code lui-même en suivant les étapes, puis décrite à l'utilisateur sous forme d'étapes simples qu'il peut refaire.
10. Le tableau de suivi de `docs/ROADMAP.md` est mis à jour (statut "terminé", lien de la pull request, date).

## 9. Déroulé type d'une session

1. Lire ce fichier, puis `docs/ROADMAP.md` : identifier la phase suivante non terminée.
2. Relire les sections des documents concernées par la phase.
3. `git checkout dev && git pull`, puis créer `phase/<NN>-<slug>`.
4. Écrire les tests (unitaires, intégration, pgTAP, Playwright) de la phase ; constater leur échec.
5. Implémenter jusqu'au vert, remanier.
6. `make check`, vérification manuelle de la définition de terminé à l'écran.
7. Mettre à jour la documentation, `docs/decisions.md`, le suivi.
8. Pull request vers `dev`, fusion.
9. Message de fin de session à l'utilisateur, en français courant : ce qui est fait, comment le voir, ce qui vient ensuite, et ce dont on a éventuellement besoin de lui.

## 10. Mode démonstration (décision de l'utilisateur, D-910)

Le projet est une démonstration locale (plan `fuzzy-sauteeing-token`). Les sections 3, 4 et 8 sont **allégées** : pas de seuil de couverture, pas de branche ni de pull request par phase, pas de revue adversariale, pas de `make check` complet obligatoire (seulement les tests utiles de ce qu'on touche), pas d'AWS, de CI/CD, de Sentry ni de SES. **Restent obligatoires** : RLS activée et forcée avec politiques et test pgTAP sur chaque table, accès à la base avec le jeton de l'utilisateur (clé de service seulement dans la liste fermée de la section 4.2), 404 pour les ressources d'autrui, format d'erreur standard, aucun secret dans le code ou Git, versions exactes, tout dans Docker (via le `Makefile`), libellés dans `labels.ts`. Parcours de démonstration : `make demo`, puis `README.md`.
