# SpaceCraft — Craft Profitability (fan tool)

Outil non officiel pour le jeu **SpaceCraft** (Shiro Games) : explorer la rentabilité du craft, les chaînes de production, la carte de l'univers et où trouver les ressources.

**App en ligne :** _(ajoute ici le lien Streamlit après déploiement)_

## Fonctions
- 📈 **Recettes** : les 479 recettes avec leur Valeur Ajoutée (prix de vente − prix des entrées), tri/filtres, VA/heure.
- 📦 **Items & prix** : 585 items.
- 🕸️ **Chaînes de craft** : graphe interactif d'un produit jusqu'aux matières brutes.
- 🌌 **Univers** : carte-réseau Secteur → Système → Planète/Station ; survol = ressources minables.
- 🔍 **Où trouver** : un minerai → gisements (type/tier/%) + secteurs.
- 🌐 Interface **FR / EN**.

## Données
Les données proviennent du jeu (fichier `data.cdb`), incluses dans `extracted/`. C'est un **outil de fan**, sans affiliation avec Shiro Games ; toutes les données et marques appartiennent à leurs propriétaires. Les valeurs peuvent changer entre patchs (Early Access).

## Lancer en local
```
pip install -r requirements.txt
streamlit run app/app.py
```

## Déploiement (Streamlit Community Cloud)
- Main file path : **`app/app.py`**
- `requirements.txt` est à la racine.
