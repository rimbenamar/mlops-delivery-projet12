# Correspondance avec le mini-projet 12

| Exigence du sujet | Implémentation |
|---|---|
| Modèle Scikit-learn | RandomForestClassifier avec seuil conservé dans ThresholdClassifier |
| Tracking des expériences | Paramètres, métriques, signature et artefacts MLflow |
| Model Registry | Version enregistrée, alias champion, chargement au démarrage de l’API |
| MLflow sur le port 5000 | Service mlflow dans docker-compose.yml |
| API REST asynchrone sur le port 8000 | FastAPI /predict ; calcul délégué au pool de threads |
| Validation stricte | Pydantic : types, bornes, champs supplémentaires interdits |
| Export Prometheus | /metrics ; compteur http_requests_total avec method, handler et status ; histogramme prediction_latency_seconds |
| Prometheus sur le port 9090 | Scrape de api:8000 toutes les 5 secondes |
| Grafana sur le port 3000 | Source Prometheus et dashboard provisionnés automatiquement |
| P95/P99, RPS, erreurs 5xx, drift | Panneaux dédiés dans grafana_dashboard.json |
| Orchestration interconnectée | docker-compose.yml : serveur MLflow → job train → API → Prometheus → Grafana |
| Vérification santé | Healthchecks des quatre services permanents ; succès du job train |
| Persistance | Volumes mlflow_data, prometheus_data et grafana_data |
| Livrable docker-compose.yml | Racine du projet |
| Livrable app/main.py | API, instrumentation et synthèse interface |
| Livrable grafana_dashboard.json | Racine du projet |
| Interface complémentaire demandée | app/static/index.html, style.css et app.js ; aucun service supplémentaire nécessaire |

Le sujet n’impose ni Iris ni un autre jeu de données. Le cas de retard de livraison Olist sert de support à la chaîne technique demandée.
