#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker info >/dev/null
docker compose up -d --build
ready=0
for attempt in {1..96}; do
  if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1; then ready=1; break; fi
  sleep 5
done
if [ "$ready" -ne 1 ]; then docker compose logs --tail=80; exit 1; fi
docker compose run --rm --no-deps api python -m pytest -q
docker compose exec -T api python scripts/traffic.py --count 150
docker compose ps -a
printf '\nInterface : http://localhost:8000\nGrafana : http://localhost:3000/d/projet12 (admin / admin-projet12)\nDans Codespaces : ouvrir les ports 8000, 3000, 5000 et 9090.\n'
