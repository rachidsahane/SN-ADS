# Soro Nua Campaign Predictor

Internal tool of Soro Nua Agency (Douala): describe an online ad campaign, get predicted click-through rate, conversion rate and website visits, a performance level, the main drivers and up to three suggested changes.

Everything runs in Docker containers. Nothing is installed on the host except Docker, Make and git.

## Quick start

```
make env-local   # creates .env and deploy/supabase/.env, generates the local secrets (never overwrites a real value)
make build       # builds the images and pulls the pinned Supabase, Mailpit and pg_prove images
make up          # starts redis, api, web, Mailpit and the Supabase stack, waits until healthy, applies the migrations
```

- Web: http://localhost:3000 (port set by `WEB_HOST_PORT` in `.env`); the home page shows "API: healthy" and "Database: connected (schema <number>)"
- API health: http://localhost:8000/api/health, readiness: http://localhost:8000/api/ready (port set by `API_HOST_PORT`)
- Supabase gateway: http://localhost:54321 (`KONG_HTTP_PORT` in `deploy/supabase/.env`)
- Supabase Studio (local only, no login, `127.0.0.1` only): http://localhost:54323 (`STUDIO_HOST_PORT` in `deploy/supabase/.env`)
- Local mailbox (Mailpit): http://localhost:54324 (`MAILPIT_HOST_PORT` in `.env`)
- No Postgres port is published: `make db-shell` opens `psql` inside the database container.

`make db-reset` rebuilds the database and storage volumes of this project from scratch and replays every migration; `make test-db` runs the pgTAP tests.

`make help` lists every target. `make check` runs the full local gate; `make test-e2e` runs the Playwright scenarios.

## Démonstration

Cette version est une **démonstration locale** : tout tourne sur votre machine, dans Docker, sans AWS ni service en ligne.

### Avant de commencer

- Docker Desktop lancé (prévoir au moins 8 Go de mémoire pour Docker), `make` et `git`.
- Une fois : `make env-local` puis `make build` (crée les fichiers de configuration locaux et construit les images ; compter plusieurs minutes la première fois).

### Tout démarrer avec une seule commande

```
make demo
```

La commande démarre l'application, charge les 8 000 lignes de départ, crée deux comptes de démonstration, puis entraîne et active un premier modèle. Elle peut être relancée sans risque : ce qui existe déjà n'est pas refait. À la fin, elle affiche l'adresse du site et les comptes.

### Adresses

- Application : http://localhost:3000
- Boîte mail locale (Mailpit) : http://localhost:54324
- Santé de l'API : http://localhost:8000/api/health

### Comptes de démonstration

Les e-mails et les mots de passe sont dans le fichier **`.demo-accounts.txt`** à la racine (créé par `make demo`, ignoré par Git, jamais à publier). Deux comptes : un **administrateur** (`demo-admin@example.test`) et un **marketer** (`demo-marketer@example.test`). Les mots de passe sont générés une seule fois et ne changent plus ensuite.

### Parcours de démonstration en 6 étapes

1. **Connexion administrateur** : ouvrir http://localhost:3000, se connecter avec le compte administrateur. Le menu montre Predict, Model, History, Data, Models, Users et Audit log.
2. **Data** : la page affiche « Seed rows: 8,000 » et le nombre de lignes de test (mises de côté pour mesurer la fiabilité).
3. **Models** : bouton « Train a new version » (statut Queued, Running puis Succeeded), ouvrir la version pour voir les mesures de chaque chiffre et sa fiabilité, puis « Activate this version ».
4. **Model** : version active, fiabilité et importance globale des facteurs (graphique).
5. **Predict** : décrire une campagne (canal, type, budget...), cliquer sur « Predict ». On obtient le taux de clic, le taux de conversion, les visites, les prospects estimés, le coût par résultat, le niveau Low / Medium / High, les facteurs principaux de chaque chiffre (onglets) et jusqu'à trois changements suggérés (« Apply » les applique et relance la prédiction).
6. **Save puis History** : « Save prediction » (donner un nom), puis menu **History** : la liste, puis « Open » pour revoir les résultats tels qu'ils étaient, ou « Delete ».

Ensuite, se déconnecter et se connecter avec le compte **marketer** : il voit Predict, Model et History, **aucun menu d'administration**, et ne peut pas ouvrir la prédiction d'un autre (« Prediction not found. »).

### À savoir pendant la présentation

Le jeu de départ est **fabriqué** : les variables n'ont presque aucun lien avec les résultats. La fiabilité du modèle est donc **Low** (un avertissement s'affiche) et les recommandations portent surtout sur le **budget**, qui domine les chiffres. Ce n'est pas un bug : avec les vraies données de l'agence, le modèle apprendrait de vraies relations.

### Si quelque chose ne va pas

- **Un port est déjà pris** (3000, 8000, 54321, 54323, 54324) : arrêter ce qui l'utilise, ou changer le port dans `.env` (`WEB_HOST_PORT`, `API_HOST_PORT`) ou `deploy/supabase/.env`, puis `make up`.
- **Docker lent, conteneurs qui redémarrent, erreur « out of memory »** : augmenter la mémoire dans Docker Desktop (Settings, Resources), fermer les autres projets Docker, puis `make down` et `make demo`. La première page visitée met quelques secondes à se préparer.
- **« No active model yet »** sur Predict : relancer `make demo` (il entraîne et active une version si besoin).
- **Mot de passe oublié** : il est dans `.demo-accounts.txt` ; si le fichier est perdu, le supprimer et relancer `make demo` (de nouveaux mots de passe sont générés).
- **Tout recommencer à zéro** : `make clean` (supprime aussi les données locales), puis `make demo`.

## Documentation

Reference documents are in `docs/` (start with `docs/PROJECT_BRIEF.md` and `docs/ROADMAP.md`). Working rules for Claude Code are in `CLAUDE.md`. Decisions taken along the way are in `docs/decisions.md`.
