# SOURCE.md : origine et licence du jeu de départ

| Élément | Valeur |
|---|---|
| Fichier | `digital_marketing_campaign_dataset.csv` |
| Contenu | 8 000 lignes de données + 1 ligne d'en-tête, 20 colonnes |
| Taille | 1 386 056 octets (fins de ligne LF, sans BOM) |
| Empreinte SHA-256 | `5df30382d7e6701b856479361b28a3f7f983bc485030fdd033994e273aa3fe91` |
| Date du fichier | 21 juin 2024 |
| Date de récupération | inconnue |

## Origine

Jeu de données public **« Predict Conversion in Digital Marketing Dataset »**, publié sur Kaggle (adresse : `kaggle.com/datasets/rabieelkharoua/predict-conversion-in-digital-marketing-dataset`).

- **Auteur** : à confirmer sur la page Kaggle (probablement Rabie El Kharoua).
- **Licence** : **À CONFIRMER sur la page Kaggle** (probablement CC BY 4.0, non vérifié). Tant que la licence n'est pas confirmée, ne pas rendre le dépôt public.
- **Mention d'attribution à conserver** : « Predict Conversion in Digital Marketing Dataset, via Kaggle ».

## Nature des données

- Jeu **fabriqué (synthétique)** : valeurs presque uniformes, corrélation absolue inférieure à 0,025 entre les variables et les cibles.
- Aucune donnée personnelle réelle.
- `AdvertisingPlatform` (`IsConfid`) et `AdvertisingTool` (`ToolConfid`) sont constantes.
- `Conversion` vaut 1 sur 87,65 % des lignes ; la colonne est ignorée par le système.
- `CustomerID` va de 8000 à 15999 et est unique.

## Utilisation

Ce fichier sert uniquement de jeu de départ pour l'apprentissage. Les données de l'agence sont importées ensuite, au même format.

**Le fichier ne doit jamais être modifié.** Contrôle d'intégrité (depuis la racine du dépôt) :

```
shasum -a 256 -c <<< "5df30382d7e6701b856479361b28a3f7f983bc485030fdd033994e273aa3fe91  data/seed/digital_marketing_campaign_dataset.csv"
```
