$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Demarrez Docker Desktop (conteneurs Linux), puis relancez cette commande.' }
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Echec Docker Compose. Consulter les messages ci-dessus.' }
$deadline = (Get-Date).AddMinutes(8)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod 'http://localhost:8000/health' -TimeoutSec 5
        $grafana = Invoke-RestMethod 'http://localhost:3000/api/health' -TimeoutSec 5
        if ($health.status -eq 'ok' -and $grafana.database -eq 'ok') { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
}
if (-not $ready) { docker compose logs --tail 80; throw 'Delai de demarrage depasse. Voir les logs.' }
docker compose run --rm --no-deps api python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Les tests ont echoue.' }
docker compose exec api python scripts/traffic.py --count 150
if ($LASTEXITCODE -ne 0) { throw 'Le test de trafic a echoue.' }
docker compose ps -a
Write-Host 'Interface : http://localhost:8000'
Write-Host 'API : http://localhost:8000/docs'
Write-Host 'MLflow : http://localhost:5000'
Write-Host 'Prometheus : http://localhost:9090'
Write-Host 'Grafana : http://localhost:3000/d/projet12'
Write-Host 'Identifiants Grafana : admin / admin-projet12'
Start-Process 'http://localhost:8000'
