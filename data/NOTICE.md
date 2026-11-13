# Données et attribution

Ce dossier contient une adaptation du **Brazilian E-Commerce Public Dataset by Olist**, publié par **Olist et ses collaborateurs**.

- Source originale : https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- Licence des données et de cette table dérivée : **CC BY-NC-SA 4.0**.
- Licence complète : https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.fr
- Copie des tables source utilisée : https://github.com/infobarbosa/dataset-olist/tree/main/data
- Empreintes SHA-256 des fichiers source et du CSV dérivé : `metadata.json`.

## Transformations réalisées

1. Jointure des commandes, articles, clients, vendeurs, produits et géolocalisations.
2. Conservation des commandes livrées et à vendeur unique, avec dates, poids et coordonnées complets.
3. Coordonnées médianes par préfixe postal (coordonnées hors bornes du Brésil exclues).
4. Calcul de la distance géographique à vol d’oiseau et du poids total des articles.
5. Agrégation du prix, du transport et du nombre d’articles par commande.
6. Calcul du délai annoncé, du mois et du jour de commande.
7. Cible : jour réel de livraison strictement postérieur au jour annoncé (comparaison de dates calendaires).
8. Exclusion des valeurs hors bornes documentées dans `scripts/prepare_data.py` ; arrondi des mesures à quatre décimales.
9. Export sans identifiants de clients, vendeurs ou commandes, sans adresses et sans texte d’avis.

Le fichier dérivé contient 94 689 lignes. Il ne s’agit pas de données simulées. Le scénario de drift, lui, modifie volontairement des mesures pour une démonstration.

## Reproduction facultative

Télécharger les six tables originales depuis Kaggle, puis lancer :

```bash
python scripts/prepare_data.py --raw /chemin/vers/les/csv
```

Les CSV originaux peuvent être bruts ou compressés `.csv.gz`. Aucun téléchargement de données n’est nécessaire pour démarrer la version livrée.

Cette adaptation n’est pas un produit officiel d’Olist et n’implique aucun soutien de sa part.
