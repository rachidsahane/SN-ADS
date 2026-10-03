# PROJECT_BRIEF : Prédiction de la performance des campagnes publicitaires de Soro Nua Agency

Document de référence n°1 sur 13.
Projet académique réalisé dans le cadre d'un stage chez Ets Soro Nua Agency.
Solution conçue spécifiquement pour le cas de Soro Nua Agency.

---

## 1. Problème

### Le problème précis

Chez Soro Nua Agency, les campagnes publicitaires en ligne sont planifiées à partir de l'expérience de l'équipe ou de suppositions. Au moment de fixer le budget, le canal, le type de campagne et l'audience visée, personne ne peut savoir à l'avance quels résultats la campagne va produire.

Le produit doit permettre, pour une campagne décrite par l'équipe :

- d'estimer trois chiffres : le taux de clic, le taux de conversion et le nombre de visites sur le site ;
- d'en déduire un niveau de performance attendu : faible, moyen ou élevé ;
- de montrer quels éléments de la campagne influencent le plus ces chiffres ;
- de conseiller quels éléments modifier pour obtenir un résultat différent.

### Pourquoi les solutions actuelles ne suffisent pas

- **L'expérience et l'intuition ne donnent pas de réponse chiffrée ni vérifiable.** Elles ne disent pas combien de clics, de conversions ou de visites attendre.
- **Les vrais résultats n'arrivent qu'après coup.** On ne sait si les choix étaient bons qu'une fois la campagne lancée et le budget dépensé.
- **L'agence ne dispose pas encore de données sur ses propres campagnes.** Elle n'a donc aucune base chiffrée sur laquelle appuyer ses décisions.

---

## 2. Utilisateur cible

### Qui

L'équipe de Soro Nua Agency qui prépare et planifie les campagnes publicitaires en ligne. L'outil est un outil interne, pensé pour le fonctionnement de cette agence. Il distingue deux rôles :

- **Membre de l'équipe marketing :** décrit une campagne, consulte les chiffres prédits, le niveau de performance, les éléments qui pèsent le plus et les conseils.
- **Administrateur :** la personne de l'agence chargée des données. Elle envoie les fichiers de données de l'agence, lance un nouvel apprentissage du système et valide son remplacement.

### Son contexte aujourd'hui

Quand elle prépare une campagne, l'équipe décide du budget, du canal, du type de campagne et de l'audience visée en s'appuyant sur son expérience et sur des suppositions. Elle ne découvre si ses choix étaient les bons qu'en regardant les résultats, une fois la campagne en cours ou terminée. Elle n'a pas d'historique chiffré de ses campagnes passées.

---

## 3. Proposition de valeur

> L'équipe de Soro Nua décrit une campagne et obtient le taux de clic, le taux de conversion et le nombre de visites attendus, un niveau de performance, et des conseils sur ce qu'il faut changer pour obtenir un autre résultat.

---

## 4. Critères de réussite

La première version sera considérée comme réussie si les points suivants sont vrais :

1. **Un membre de l'équipe peut décrire une campagne dans un tableau de bord interactif en anglais.** Il renseigne le plan de campagne, le profil type de la cible et l'engagement attendu (voir 7.1). Les champs d'engagement attendu sont déjà pré-remplis avec des valeurs habituelles, qu'il peut modifier.
2. **Le système affiche trois chiffres prédits :** le taux de clic (ClickThroughRate), le taux de conversion (ConversionRate) et le nombre de visites sur le site (WebsiteVisits).
3. **Le système affiche un niveau de performance attendu : faible, moyen ou élevé,** calculé selon les règles de la section 7.3.
4. **Le système montre quels éléments pèsent le plus :** de manière générale, et pour la campagne décrite en particulier.
5. **Le système propose jusqu'à trois changements qui améliorent le plus le résultat,** avec pour chacun l'effet attendu sur les trois chiffres et sur le niveau. Si aucun changement n'apporte d'amélioration notable, il le dit clairement.
6. **Le membre de l'équipe peut modifier lui-même n'importe quelle valeur** et voir immédiatement les nouveaux chiffres prédits.
7. **Les prédictions ont été testées sur une partie des données mise de côté,** que le système n'avait pas utilisée pour apprendre. Le niveau de fiabilité obtenu est mesuré et présenté tel qu'il est.
8. **L'administrateur peut envoyer un fichier de données de l'agence et relancer l'apprentissage.** L'outil refuse clairement un fichier qui ne respecte pas la structure. Le nouveau système ne remplace l'ancien que s'il est au moins aussi fiable.

---

## 5. Non-objectifs

La première version ne fera explicitement PAS les choses suivantes.

- **Servir d'outil général pour d'autres agences ou entreprises.**
  La solution est conçue pour le cas précis de Soro Nua Agency.

- **Prédire d'autres chiffres que les trois retenus.**
  Le projet se concentre sur le taux de clic, le taux de conversion et le nombre de visites sur le site.

- **Conseiller sur le contenu des annonces.**
  Le jeu de données de départ ne contient aucune information sur le contenu.

- **Conseiller sur une plateforme publicitaire précise** (Facebook, Google, TikTok...).
  La plateforme est masquée dans le jeu de départ. Le canal (email, référencement payant, référencement naturel, réseaux sociaux, recommandation) en tient lieu pour l'instant.

- **Récupérer automatiquement les données depuis les plateformes publicitaires.**
  L'agence ajoute ses propres données en envoyant un fichier au même format que le jeu de départ.

- **Proposer l'outil dans une autre langue que l'anglais.**
  L'anglais est la langue retenue pour l'outil.

---

## 6. Contraintes

### Cadre du projet

- Il s'agit d'un projet académique, réalisé pendant un stage chez Ets Soro Nua Agency.
- Il doit pouvoir être présenté et défendu devant un jury.
- La solution est spécifique à Soro Nua Agency.
- L'outil est en anglais.

### Résultat attendu

- Le résultat final est un système de prédiction qui apprend à partir de données passées, accompagné d'un tableau de bord interactif. On y décrit une campagne et on reçoit les chiffres prédits, un niveau de performance et des conseils.
- La méthode de prédiction retenue comme point de départ est XGBoost, une méthode courante d'apprentissage automatique qui apprend à partir d'exemples passés.

### Données

- **L'agence n'a pas de données propres pour l'instant.** Le système apprend donc à partir du jeu de données trouvé au départ (8 000 lignes).
- **Le jeu de départ sert uniquement à l'apprentissage du système.** Il est conservé dans la base de données pour relancer l'apprentissage plus tard, avec plus de données si nécessaire.
- **Les données futures de l'agence doivent respecter la structure du jeu de départ :** mêmes colonnes, mêmes noms, même format, mêmes valeurs possibles pour le canal et le type de campagne.
- **Limites connues du jeu de départ,** à garder en tête et à présenter honnêtement au jury :
  - il est fabriqué, et cela se voit dans la façon dont les chiffres sont répartis ;
  - chaque ligne décrit une personne, pas une campagne ;
  - la plateforme publicitaire y est masquée : toutes les lignes portent la même valeur ;
  - il ne contient ni coût par résultat ni nombre de prospects : ces deux éléments sont donc calculés (voir 7.3) ;
  - plusieurs informations ne sont connues qu'après le lancement : elles sont traitées comme des estimations saisies par l'équipe (voir 7.1) ;
  - **un test a déjà été fait : dans ce jeu, les trois chiffres à prédire n'ont aucun lien exploitable avec les autres informations.** Le système ne fera pas mieux qu'une moyenne, quelle que soit la campagne décrite. En conséquence, la plupart des campagnes seront classées « moyen » et les conseils trouveront rarement une amélioration notable. Les prédictions et les conseils ne deviendront parlants qu'avec les vraies données de l'agence.

### Confidentialité

- Les noms des clients de l'agence doivent être rendus anonymes dans les données envoyées dans l'outil.

---

## 7. Choix de fonctionnement retenus

### 7.1 Informations utilisées pour prédire

Les noms entre parenthèses sont ceux des colonnes du jeu de données.

- **Plan de campagne,** connu avant le lancement : canal (CampaignChannel), type de campagne (CampaignType), budget (AdSpend).
- **Profil type de la cible :** âge (Age), genre (Gender), revenu (Income), achats passés (PreviousPurchases), points de fidélité (LoyaltyPoints). Dans le jeu de départ, chaque ligne décrit une personne. Dans l'outil, l'équipe décrit la personne type que la campagne vise.
- **Engagement attendu,** connu seulement après le lancement : pages vues par visite (PagesPerVisit), temps passé sur le site (TimeOnSite), partages (SocialShares), ouvertures d'emails (EmailOpens), clics dans les emails (EmailClicks). L'équipe saisit des estimations. Chaque champ est pré-rempli avec la moyenne observée dans la base pour le même canal et le même type de campagne.
- **Informations écartées :**
  - le numéro de ligne (CustomerID), qui ne décrit rien ;
  - la conversion individuelle (Conversion), qui est un résultat et non une description de la campagne ;
  - la plateforme (AdvertisingPlatform) et l'outil publicitaire (AdvertisingTool), qui n'ont qu'une seule valeur dans le jeu de départ. Ces deux colonnes restent dans la structure et seront prises en compte automatiquement lors d'un nouvel apprentissage dès que les données de l'agence contiendront des valeurs variées.

### 7.2 Chiffres prédits

Le système prédit séparément les trois chiffres : taux de clic (ClickThroughRate), taux de conversion (ConversionRate) et nombre de visites sur le site (WebsiteVisits).

### 7.3 Calcul du niveau de performance

Le niveau est calculé à partir des chiffres prédits et du budget saisi :

1. **Nombre de prospects estimé** = nombre de visites × taux de conversion.
2. **Coût par résultat** = budget ÷ nombre de prospects estimé. S'il n'y a aucun prospect, le coût par résultat reçoit la plus mauvaise note possible.
3. **Chaque élément reçoit une note sur 100** selon sa position parmi les exemples enregistrés dans la base ayant le même type de campagne. Une note de 100 est la meilleure. Pour le taux de clic et le nombre de prospects, plus c'est haut, mieux c'est. Pour le coût par résultat, plus c'est bas, mieux c'est.
4. **Le score global** est la moyenne simple des trois notes : coût par résultat, taux de clic, nombre de prospects. Les trois ont le même poids.
5. **Les limites entre les niveaux** sont placées de sorte qu'un tiers des exemples de la base soit « faible », un tiers « moyen » et un tiers « élevé ». Ces limites sont recalculées à chaque nouvel apprentissage.

Le fait de comparer une campagne uniquement aux exemples du même type évite de juger une campagne de notoriété avec les mêmes attentes qu'une campagne de conversion.

### 7.4 Éléments qui pèsent le plus

L'outil présente deux vues :

- **Vue générale :** les informations qui comptent le plus pour le système, toutes campagnes confondues.
- **Vue de la campagne décrite :** les informations qui ont fait monter ou descendre chacun des trois chiffres prédits.

### 7.5 Conseils

- **Leviers que les conseils peuvent modifier :** uniquement ce que l'agence décide réellement, c'est-à-dire le budget, le canal, le type de campagne et le profil type de la cible. L'engagement attendu n'est pas proposé comme levier, car c'est une conséquence de la campagne et non une décision.
- **Méthode :** l'outil essaie automatiquement d'autres valeurs pour chaque levier : chacun des autres canaux, chacun des autres types, un budget de 50 % inférieur à 50 % supérieur par paliers de 10 %, d'autres tranches d'âge et de revenu, l'autre genre, d'autres niveaux d'achats passés et de fidélité. Il recalcule les prédictions et le score pour chaque essai.
- **Présentation :** l'outil garde les trois changements qui améliorent le plus le score global. Pour chacun, il affiche l'avant et l'après sur les trois chiffres et sur le niveau.
- **Seuil :** un changement n'est proposé que s'il fait gagner au moins 5 points sur 100 au score global. Sinon, l'outil indique qu'aucun changement testé n'améliore sensiblement le résultat.

### 7.6 Ajout des données de l'agence et nouvel apprentissage

Ces fonctions font partie de la première version.

- **Format :** l'administrateur envoie un fichier tableur au format CSV avec les mêmes colonnes que le jeu de départ. Pour l'agence, une ligne correspond à une campagne, décrite par le profil type de sa cible et par ses résultats réels. Le numéro de ligne sert alors de numéro de campagne.
- **Vérification :** l'outil vérifie le fichier avant de l'accepter. S'il ne respecte pas la structure, il le refuse et indique les lignes et colonnes en cause.
- **Stockage :** les données de l'agence s'ajoutent au jeu de départ dans la base. L'origine de chaque ligne (jeu de départ ou agence) est mémorisée.
- **Nouvel apprentissage :** il est déclenché manuellement par l'administrateur. Celui-ci peut choisir d'apprendre sur l'ensemble des données ou uniquement sur celles de l'agence, quand elle en aura assez.
- **Remplacement :** le nouveau système est testé sur des exemples mis de côté et comparé à l'ancien. L'administrateur voit la comparaison. Le nouveau système ne remplace l'ancien que s'il est au moins aussi fiable.

---

## À clarifier

Aucun point ouvert. Les choix de la section 7 ont été arrêtés par Claude à la demande du porteur du projet et restent modifiables.
