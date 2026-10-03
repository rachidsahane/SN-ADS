# notebooks/ : analyse et entraînement exploratoires (préparation de la phase 7)

Trois notebooks qui montrent, avec les règles exactes de `docs/LLD.md` section 5, ce que contient le jeu de départ et ce que valent les trois modèles XGBoost. Tout tourne dans Docker (image `soronua-predict-notebooks`, cible `notebooks` de `apps/api/Dockerfile`). Rien n'est écrit en base ni dans le stockage : les notebooks lisent `data/seed/` et écrivent dans `notebooks/_out/` (ignoré par Git). Décision : D-044.

| Notebook | Contenu |
|---|---|
| `01_data_profile.ipynb` | colonnes, plages, colonnes constantes, distributions, corrélations |
| `02_train_three_models.ipynb` | lignes de test, entraînement des trois modèles, métriques, importance, fichiers de modèle |
| `03_evaluation_and_scoring.ipynb` | contrôles d'honnêteté (cible mélangée, validation croisée, jeu avec signal), score et seuils |

`common.py` regroupe les règles du LLD (lignes de test, variables, paramètres, métriques, score). La phase 7 le remplacera par `app.domain` et `app.ml`.

## Commandes

```
make notebooks-run   # exécute les trois notebooks (résultats enregistrés dans les fichiers .ipynb + copies HTML dans _out/)
make notebooks-lab   # JupyterLab sur http://127.0.0.1:8888 (le jeton s'affiche dans la console)
```

Pour lire les résultats sans rien lancer : ouvrir `notebooks/_out/*.html` dans un navigateur.

## Résultat attendu sur le jeu de départ

Le jeu est fabriqué (aucun signal) : R² proche de 0 (légèrement négatif) pour les trois chiffres, fiabilité « low », importance répartie presque également. Un jeu avec un vrai signal (notebook 03) atteint R² > 0,9 : la chaîne d'apprentissage est saine, ce sont les données qui limitent.
