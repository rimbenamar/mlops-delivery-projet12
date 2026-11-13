# Vérification de la version DeliveryOps

## Contrôles réussis

- **16 tests pytest**, sous Python 3.12, avec les dépendances de `requirements.lock.txt`.
- Contrôle du SHA-256 du CSV inclus et séparation chronologique des périodes.
- Validation stricte des entrées, seuil de décision, métriques, erreurs HTTP 500, drift et retour au trafic normal.
- Endpoints de l’interface et de la synthèse de supervision ; services indisponibles et métriques non finies traités.
- **Serveur MLflow réel avec SQLite et artefacts par HTTP** : entraînement, tracking, signature, registre et alias `champion`.
- **Serveur Uvicorn réel** : chargement du modèle depuis le registre, prédiction, réponse 422, 35 observations décalées, métrique de drift et endpoint de synthèse.
- **Tests DOM JavaScript avec jsdom** : données de la vraie exécution pour la synthèse et les exemples ; réponse de prédiction simulée pour tester le rendu. Formulaire prérempli valide, affichage du score, simulation arrêtée, indisponibilité de l’API, liens locaux et hôtes Codespaces.
- Syntaxe JavaScript, script Bash, fichiers YAML, JSON et configurations locales analysés.

## Résultats de référence sur le test temporel

Les résultats détaillés sont dans `reports/evaluation.json`.

| Mesure | Valeur mesurée |
|---|---:|
| Commandes préparées | 94 689 |
| Commandes d’entraînement | 55 777 |
| Commandes de validation | 20 443 |
| Commandes de test | 18 469 |
| Fréquence des retards dans le test | 3,60 % |
| Seuil choisi sur validation | 0,39 |
| Précision des retards | 8,45 % |
| Rappel des retards | 45,86 % |
| F1 des retards | 0,143 |
| ROC AUC | 0,723 |
| Average precision | 0,075 |
| Accuracy du modèle | 80,16 % |
| Baseline « toujours à l’heure » | 96,40 % |

Le modèle repère une partie des retards mais produit beaucoup de faux positifs. Sa précision est insuffisante pour une décision autonome. Ces résultats sont affichés sans modification dans l’interface ; ils illustrent le déséquilibre des classes et le décalage temporel entre les périodes. Le sujet évalue ici le pipeline d’industrialisation et de monitoring, pas une promesse de performance commerciale.

## Limites de vérification

Docker n’est pas installé dans l’environnement de préparation : les images, le réseau Compose, les healthchecks conteneurisés et le rendu Grafana n’ont pas été exécutés ici. Les scripts de lancement vérifient les services sur la machine cible.

L’ouverture d’un navigateur Chromium a été bloquée par les restrictions de sockets de l’environnement. Les contrôles JavaScript ont été réalisés dans un DOM simulé : ils ne remplacent pas un contrôle visuel du rendu CSS.

Les tests ne constituent pas un benchmark de charge ni une preuve de fiabilité en production. Aucune mesure d’accuracy sur de nouvelles livraisons réelles n’est revendiquée.
