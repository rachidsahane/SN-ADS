# PRD.md : Soro Nua Campaign Predictor

Document de référence n°2 sur 13.
Source de vérité fonctionnelle. Il découle de `docs/PROJECT_BRIEF.md` (validé). En cas de contradiction, PROJECT_BRIEF.md prévaut pour le "quoi", ce document prévaut pour le détail des fonctionnalités.

Nom du produit (affiché dans l'interface) : **Soro Nua Campaign Predictor**.
Langue de l'interface : **anglais uniquement**. Tous les libellés cités entre guillemets dans ce document sont les textes exacts à afficher.

---

## 1. Rappel du produit

Outil interne de Soro Nua Agency. Un membre de l'équipe marketing décrit une campagne publicitaire en ligne. L'outil prédit trois chiffres (taux de clic, taux de conversion, nombre de visites sur le site), en déduit un niveau de performance (low / medium / high), montre ce qui pèse le plus dans ces prédictions et propose jusqu'à trois changements pour obtenir un meilleur résultat.

Le système apprend à partir d'un jeu de données de départ (8 000 lignes, fabriqué, fourni dans le dépôt). L'agence pourra ensuite ajouter ses propres données au même format et relancer l'apprentissage.

## 2. Rôles

| Rôle | Nom technique | Description |
|---|---|---|
| Membre de l'équipe marketing | `marketer` | Décrit des campagnes, consulte prédictions, niveau, facteurs, conseils, son propre historique et la page de fiabilité du modèle. |
| Administrateur | `admin` | Tout ce que fait `marketer`, plus : gestion des utilisateurs, import des données, lancement des apprentissages, activation des versions du modèle, consultation du journal d'audit. |

Il n'existe pas d'inscription libre. Tout compte est créé par invitation d'un administrateur. Le tout premier administrateur est créé par une commande d'amorçage (voir `ENV_SETUP.md`).

---

## 3. Fonctionnalités priorisées

### 3.1 Indispensable (première version)

| ID | Fonctionnalité | Description |
|---|---|---|
| F-01 | Connexion | Connexion par e-mail et mot de passe. Message d'erreur générique en cas d'échec ("Invalid email or password."). |
| F-02 | Déconnexion | Bouton "Sign out" dans l'en-tête. Retour à l'écran de connexion. |
| F-03 | Acceptation d'invitation | Le lien reçu par e-mail ouvre un écran "Set your password". Après validation, l'utilisateur est connecté. |
| F-04 | Mot de passe oublié | Lien "Forgot password?" sur l'écran de connexion, envoi d'un e-mail, écran "Set your password". |
| F-05 | Invitation d'un utilisateur | L'administrateur saisit e-mail, nom complet et rôle. Un e-mail d'invitation est envoyé. |
| F-06 | Gestion des comptes | L'administrateur change le rôle d'un utilisateur, le désactive ou le réactive. Il ne peut ni se désactiver lui-même, ni retirer son propre rôle d'administrateur. Le système refuse toute action qui laisserait zéro administrateur actif. |
| F-07 | Journal d'audit | Liste chronologique des actions sensibles (invitation, changement de rôle, désactivation, import, apprentissage, activation). Lecture seule, administrateurs uniquement. |
| F-08 | Chargement du jeu de départ | Commande d'exploitation qui charge le fichier `data/seed/digital_marketing_campaign_dataset.csv` dans la base, une seule fois par environnement. |
| F-09 | Import de données de l'agence | L'administrateur envoie un fichier CSV au format exact du jeu de départ. Le fichier est vérifié en entier avant d'être accepté. En cas d'erreur, rien n'est importé et la liste des erreurs (ligne, colonne, raison) est affichée. |
| F-10 | Vue des données | Page listant les imports (date, origine, nombre de lignes, auteur, statut) et un résumé : nombre de lignes par origine, nombre de lignes mises de côté pour les tests. |
| F-11 | Lancement d'un apprentissage | L'administrateur lance un nouvel apprentissage en choisissant le périmètre : "All data" ou "Agency data only". Un seul apprentissage à la fois. |
| F-12 | Suivi d'un apprentissage | Statut visible et mis à jour automatiquement : "Queued", "Running", "Succeeded", "Failed" (avec raison lisible). |
| F-13 | Comparaison des versions | À la fin d'un apprentissage réussi, l'outil compare la nouvelle version à la version active sur les mêmes lignes de test et affiche l'avant/après pour chacun des trois chiffres. |
| F-14 | Activation d'une version | Bouton "Activate this version", actif seulement si la nouvelle version est au moins aussi fiable que la version active (ou s'il n'existe aucune version active). |
| F-15 | Page de fiabilité du modèle | Page "Model" visible par tous : version active, date, périmètre, fiabilité de chacun des trois chiffres, éléments qui comptent le plus toutes campagnes confondues. |
| F-16 | Formulaire de campagne | Trois blocs : "Campaign plan", "Target audience profile", "Expected engagement". Les champs du bloc "Expected engagement" sont pré-remplis avec la moyenne observée pour le même canal et le même type de campagne, et restent modifiables. |
| F-17 | Prédiction des trois chiffres | Affichage de "Click-through rate", "Conversion rate", "Website visits". |
| F-18 | Niveau de performance | Affichage du niveau ("Low", "Medium", "High"), du score global sur 100 et des trois notes (taux de clic, prospects estimés, coût par résultat estimé), calculés selon `LLD.md` section 6. |
| F-19 | Facteurs de la campagne | Pour chacun des trois chiffres, les 5 éléments qui l'ont le plus fait monter ou descendre, avec le sens de l'effet. |
| F-20 | Recommandations | Jusqu'à trois changements, un par levier, qui font gagner au moins 5 points au score global, avec l'avant/après. Sinon, le message "No tested change improves the result significantly." |
| F-21 | Simulation en direct | Toute modification d'un champ relance la prédiction après une courte pause de saisie, sans enregistrer. |
| F-22 | Enregistrement et historique personnel | Bouton "Save prediction" avec un nom facultatif. Page "History" listant uniquement les prédictions de l'utilisateur connecté ; ouverture d'une prédiction enregistrée ; suppression. |
| F-23 | Avertissements | Bandeaux explicites : aucune version active ("No active model yet. An administrator must train and activate a model."), fiabilité faible du modèle, valeurs saisies en dehors des valeurs connues du modèle. |
| F-24 | Conservation du brouillon | Si la session expire pendant la saisie, le formulaire est restauré après la reconnexion. |
| F-25 | Remontée des erreurs | Toute erreur (interface, API, worker) remonte dans Sentry avec son contexte. L'utilisateur voit un message clair et un identifiant d'erreur ("Reference: <request_id>"). |
| F-26 | Version affichée | Le numéro de version déployée est affiché discrètement en pied de page. |

### 3.2 Plus tard (hors première version, candidats)

| ID | Fonctionnalité | Raison du report |
|---|---|---|
| L-01 | Suppression d'un import déjà accepté | Le contrôle complet avant import limite le besoin ; la suppression implique de gérer les versions de modèle déjà entraînées dessus. |
| L-02 | Réactivation d'une ancienne version depuis l'interface | Disponible en première version uniquement via une commande d'exploitation (voir `CI_CD.md`, retour arrière). |
| L-03 | Export de l'historique en CSV | Non demandé dans le brief. |
| L-04 | Recommandations combinant plusieurs leviers à la fois | La première version teste un levier à la fois pour rester lisible. |
| L-05 | Rédaction des conseils en langage naturel par Gemini | Les conseils chiffrés suffisent pour la première version ; ajouter un modèle de langage n'apporte rien tant que les données sont fabriquées. |
| L-06 | Apprentissage programmé automatiquement | L'apprentissage est volontairement déclenché à la main par l'administrateur. |

### 3.3 Hors périmètre (repris du brief)

| ID | Élément | Raison |
|---|---|---|
| H-01 | Usage par d'autres agences ou entreprises | Solution spécifique à Soro Nua Agency. |
| H-02 | Prédiction d'autres chiffres | Seuls les trois chiffres retenus sont prédits. |
| H-03 | Conseils sur le contenu des annonces | Aucune information sur le contenu dans les données. |
| H-04 | Conseils sur une plateforme publicitaire précise | Plateforme masquée dans le jeu de départ. Elle sera prise en compte automatiquement si les données de l'agence la renseignent (voir `LLD.md` section 5). |
| H-05 | Récupération automatique depuis les plateformes publicitaires | Les données arrivent par import de fichier. |
| H-06 | Autre langue que l'anglais | Langue retenue. |
| H-07 | Inscription libre | Outil interne, comptes sur invitation. |

---

## 4. Récits utilisateurs

Format : En tant que <rôle>, je veux <action>, afin de <bénéfice>. Chaque récit liste ses critères d'acceptation vérifiables à l'écran.

### Authentification et comptes

**US-01** En tant qu'utilisateur invité, je veux définir mon mot de passe depuis le lien reçu, afin d'accéder à l'outil.
- Le lien ouvre "Set your password" avec deux champs (mot de passe, confirmation).
- Mot de passe de 10 caractères minimum ; message "Password must be at least 10 characters." sinon.
- Après validation, arrivée sur "Predict".
- Un lien expiré ou déjà utilisé affiche "This link is invalid or has expired. Ask an administrator for a new invitation."

**US-02** En tant qu'utilisateur, je veux me connecter et me déconnecter.
- Identifiants faux : "Invalid email or password." (même message que l'e-mail existe ou non).
- Compte désactivé : "Your account has been deactivated. Contact an administrator."
- Après déconnexion, toute page protégée renvoie vers "Sign in".

**US-03** En tant qu'administrateur, je veux inviter un collègue avec un rôle, afin qu'il utilise l'outil.
- Formulaire : "Email", "Full name", "Role" (Marketer / Admin).
- E-mail déjà existant : "A user with this email already exists."
- L'utilisateur apparaît dans la liste avec le statut "Invited" jusqu'à sa première connexion, puis "Active".

**US-04** En tant qu'administrateur, je veux changer un rôle ou désactiver un compte.
- Les actions sur son propre compte sont désactivées dans l'interface et refusées par l'API.
- Toute action qui laisserait zéro administrateur actif est refusée : "At least one active administrator is required."
- Un utilisateur désactivé perd l'accès dans la minute qui suit, y compris s'il est déjà connecté.

**US-05** En tant qu'administrateur, je veux consulter le journal d'audit.
- Colonnes : date, auteur, action, cible, détails.
- Pagination par 50.

### Données

**US-06** En tant qu'administrateur, je veux importer un fichier de données de l'agence.
- Case obligatoire : "I confirm that client names are anonymized in this file."
- Rappel visible : "Amounts must be in USD. Rates must be fractions between 0 and 1 (0.05 = 5%). One row per campaign, described by the typical person it targets."
- Fichier refusé : liste des erreurs (100 premières au maximum, plus le total), rien n'est importé.
- Fichier déjà importé (contenu identique) : "This file has already been imported."
- Fichier accepté : l'import apparaît avec le statut "Ready" et le nombre de lignes.

**US-07** En tant qu'administrateur, je veux voir les données disponibles.
- Résumé : lignes du jeu de départ, lignes de l'agence, lignes mises de côté pour les tests.
- Le choix "Agency data only" est grisé tant que l'agence a moins de 250 lignes, avec l'explication "Requires at least 250 agency rows."

### Modèle

**US-08** En tant qu'administrateur, je veux lancer un apprentissage et suivre son avancement.
- Bouton "Train a new version" avec le choix du périmètre.
- Si un apprentissage est déjà en cours : "A training run is already in progress."
- Le statut se met à jour sans recharger la page.
- En cas d'échec, raison lisible (exemple : "Not enough data: at least 200 training rows and 50 test rows are required.").

**US-09** En tant qu'administrateur, je veux comparer une nouvelle version à la version active et l'activer.
- Tableau : pour chacun des trois chiffres, l'erreur moyenne de l'ancienne et de la nouvelle version, et l'écart en pourcentage.
- Verdict : "At least as reliable as the active version" ou "Less reliable than the active version".
- Bouton "Activate this version" actif uniquement si le verdict est favorable ou s'il n'y a pas de version active.
- Si un autre administrateur a activé une version entre-temps : "The active version changed since you opened this page. Review the new comparison." et la page se recharge.

**US-10** En tant que membre de l'équipe, je veux savoir à quel point le modèle est fiable.
- Page "Model" : version, date d'activation, périmètre, fiabilité par chiffre en langage courant ("Low", "Moderate", "Good") avec la valeur chiffrée.
- Si la fiabilité est faible : "The current model has low accuracy. Its predictions stay close to average values. They will become more meaningful once the agency adds its own data."

### Prédiction

**US-11** En tant que membre de l'équipe, je veux décrire une campagne et obtenir les trois chiffres, le niveau, les facteurs et les conseils.
- Les champs du bloc "Expected engagement" se pré-remplissent dès que le canal et le type sont choisis.
- Les valeurs hors limites sont refusées champ par champ avec un message précis.
- Les valeurs acceptées mais hors des valeurs connues du modèle déclenchent l'avertissement "Outside the values the model has seen. Treat this prediction with caution." sur le champ concerné.

**US-12** En tant que membre de l'équipe, je veux modifier une valeur et voir immédiatement l'effet.
- Après 400 ms sans frappe, les résultats se mettent à jour.
- Un indicateur discret montre le recalcul en cours.

**US-13** En tant que membre de l'équipe, je veux appliquer une recommandation.
- Bouton "Apply" sur chaque recommandation : le formulaire prend la nouvelle valeur et les résultats se recalculent.

**US-14** En tant que membre de l'équipe, je veux enregistrer une prédiction et la retrouver plus tard.
- Bouton "Save prediction", nom facultatif (120 caractères au maximum).
- Page "History" : nom, date, canal, type, niveau. Pagination par 20.
- Une prédiction enregistrée s'affiche telle qu'elle a été calculée, avec la version du modèle utilisée, même si une autre version est active depuis.
- Aucun utilisateur, administrateur compris, ne voit l'historique d'un autre utilisateur.

---

## 5. Parcours principaux

### P-1 Mise en service d'un environnement (exploitation)
1. Les migrations de base sont appliquées par le pipeline.
2. La commande d'amorçage crée le premier administrateur et lui envoie une invitation.
3. La commande de chargement importe le jeu de départ.
4. L'administrateur se connecte, lance un apprentissage "All data", attend "Succeeded", clique "Activate this version".
5. L'outil est utilisable par l'équipe.

### P-2 Première connexion d'un membre invité
Invitation reçue → "Set your password" → "Predict".

### P-3 Prédire une campagne
1. "Predict" → le membre choisit canal et type → l'engagement attendu se pré-remplit.
2. Il complète budget et profil de la cible.
3. Dès que le formulaire est valide, les résultats apparaissent à droite (sous le formulaire sur mobile) : trois chiffres, niveau et score, facteurs, recommandations, avertissements.
4. Il modifie des valeurs ou applique une recommandation ; les résultats se recalculent.
5. Il clique "Save prediction" ; la prédiction apparaît dans "History".

### P-4 Importer des données de l'agence
"Data" → "Upload CSV" → choix du fichier + case d'anonymisation → "Upload" → résultat (accepté ou liste d'erreurs).

### P-5 Réentraîner et activer
"Models" → "Train a new version" → choix du périmètre → suivi du statut → comparaison → "Activate this version".

### P-6 Gérer les utilisateurs
"Users" → "Invite user" / changer rôle / désactiver / réactiver.

---

## 6. Cas limites critiques

| ID | Situation | Comportement attendu |
|---|---|---|
| CL-01 | Aucune version active | Page "Predict" affiche le bandeau F-23, formulaire désactivé. API : 409 `NO_ACTIVE_MODEL`. |
| CL-02 | Deux administrateurs lancent un apprentissage en même temps | Un seul est accepté ; l'autre reçoit "A training run is already in progress." |
| CL-03 | Deux administrateurs activent une version en même temps | Le second reçoit le message de US-09 ; aucune activation silencieuse par-dessus. |
| CL-04 | Le même fichier est envoyé deux fois, y compris simultanément | Un seul import accepté ; l'autre reçoit "This file has already been imported." |
| CL-05 | Import pendant un apprentissage | L'apprentissage en cours ignore l'import (il travaille sur les données prêtes au moment de sa création). |
| CL-06 | Session expirée pendant la saisie | Redirection vers "Sign in" avec "Your session has expired. Please sign in again." ; après connexion, retour sur "Predict" avec le brouillon restauré. |
| CL-07 | Un utilisateur tente d'ouvrir la prédiction d'un autre (URL modifiée) | "Prediction not found." (jamais "accès refusé", pour ne pas révéler l'existence). |
| CL-08 | Un `marketer` tente d'ouvrir une page d'administration | Redirection vers "Predict" avec "You do not have access to this page." ; l'API répond 403. |
| CL-09 | Utilisateur désactivé pendant sa session | Prochaine action refusée avec le message de US-02, puis déconnexion. |
| CL-10 | Fichier trop volumineux (plus de 10 Mo) ou plus de 50 000 lignes | Refus immédiat avec la limite indiquée. |
| CL-11 | Fichier au mauvais format (pas un CSV, mauvais encodage, colonnes manquantes ou en trop) | Refus avec un message précis ; rien n'est importé. |
| CL-12 | Cellule texte commençant par `=`, `+`, `-` ou `@` | Ligne refusée (protection contre l'injection de formules). |
| CL-13 | Prospects estimés égaux à zéro | Coût par résultat affiché "n/a", note du coût par résultat égale à 0. |
| CL-14 | Nombreuses requêtes rapprochées | Au-delà des limites (voir `API_SPEC.md`), message "Too many requests. Please wait a moment." |
| CL-15 | Apprentissage bloqué (worker arrêté) | Au redémarrage du worker, un apprentissage resté "Running" plus de 60 minutes passe en "Failed" avec la raison "Training was interrupted." |
| CL-16 | Nouvelle version activée pendant qu'un utilisateur consulte ses résultats | Les résultats affichés restent cohérents ; le prochain calcul utilise la nouvelle version et le numéro de version affiché change. |
| CL-17 | Service indisponible (base, cache) | Message "The service is temporarily unavailable. Please try again in a few minutes." ; erreur remontée dans Sentry. |

---

## 7. Contraintes

- Solution spécifique à Soro Nua Agency, interface en anglais.
- Stack imposée sans substitution (voir `ARCHITECTURE.md`).
- Tous les composants de la solution (interface, API, modèle, base de données, authentification, stockage de fichiers) tournent dans des conteneurs Docker, en local comme sur AWS. Seuls les services tiers en ligne de la stack (Upstash, Sentry, Amazon SES, GitHub, CI/CD AWS) restent externes.
- Méthode de prédiction : XGBoost, trois modèles séparés, un par chiffre.
- Données de départ fabriquées et sans lien exploitable entre les trois chiffres et le reste : les prédictions resteront proches de la moyenne et la plupart des campagnes seront classées "Medium" tant que l'agence n'a pas ajouté ses données. L'interface le dit clairement (F-23, US-10).
- Montants en USD, taux en fractions entre 0 et 1, pour toutes les données.
- Données clients anonymisées avant import (confirmation obligatoire).
- Aucune donnée d'un utilisateur visible par un autre utilisateur.
- Projet académique : le produit doit pouvoir être démontré et défendu devant un jury.

## 8. Glossaire des libellés de l'interface

| Terme français | Libellé anglais affiché | Colonne du jeu de données |
|---|---|---|
| Canal | Channel | CampaignChannel |
| Type de campagne | Campaign type | CampaignType |
| Budget | Ad spend (USD) | AdSpend |
| Âge | Age | Age |
| Genre | Gender | Gender |
| Revenu | Income (USD / year) | Income |
| Achats passés | Previous purchases | PreviousPurchases |
| Points de fidélité | Loyalty points | LoyaltyPoints |
| Pages vues par visite | Pages per visit | PagesPerVisit |
| Temps passé sur le site | Time on site (minutes) | TimeOnSite |
| Partages | Social shares | SocialShares |
| Ouvertures d'e-mails | Email opens | EmailOpens |
| Clics dans les e-mails | Email clicks | EmailClicks |
| Plateforme publicitaire | Advertising platform | AdvertisingPlatform |
| Outil publicitaire | Advertising tool | AdvertisingTool |
| Taux de clic | Click-through rate | ClickThroughRate |
| Taux de conversion | Conversion rate | ConversionRate |
| Visites sur le site | Website visits | WebsiteVisits |
| Prospects estimés | Estimated leads | (calculé) |
| Coût par résultat estimé | Estimated cost per result | (calculé) |
| Niveau de performance | Performance level | (calculé) |
