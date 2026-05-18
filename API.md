# SentinelAI API -- Dokumentation & Kurzanleitung

REST API fuer den Zugriff auf die coding_results aus der vigilex Pipeline.
Laeuft als FastAPI-Service im bestehenden Docker Compose Stack auf Hetzner.

---

## Schnellstart

### 1. API Key setzen (einmalig)

```bash
# Auf dem Hetzner-Server:
ssh cap@46.225.109.99
cd ~/vigilex

# Starken Key generieren und in .env eintragen:
echo "API_KEY=$(openssl rand -hex 32)" >> .env

# Pruefen:
grep API_KEY .env
```

### 2. API starten

```bash
# Nur den API-Service starten (Postgres muss laufen):
docker compose up api --build -d

# Logs checken:
docker logs -f vigilex-api
```

### 3. Erster Test

```bash
# Key aus .env lesen:
API_KEY=$(grep '^API_KEY=' ~/vigilex/.env | cut -d= -f2)

# Health Check (kein Key noetig):
curl http://localhost:8000/health

# Statistik-Uebersicht:
curl -H "X-API-Key: $API_KEY" http://localhost:8000/coding-results/stats

# Erste 10 Ergebnisse:
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/coding-results?limit=10"
```

### 4. Swagger UI (interaktiv)

SSH-Tunnel oeffnen und im Browser aufrufen:

```bash
# Lokal (Windows):
ssh -L 8000:localhost:8000 cap@46.225.109.99
```

Dann: [http://localhost:8000/docs](http://localhost:8000/docs)

Dort koennen alle Endpoints direkt ausprobiert werden inkl. Auth-Eingabe.

---

## Authentifizierung

Alle Endpoints ausser `/health` benoetigen den Header:

```
X-API-Key: <dein API_KEY aus .env>
```

Beispiel mit curl:
```bash
curl -H "X-API-Key: abc123..." http://localhost:8000/coding-results
```

Beispiel mit Python:
```python
import requests

BASE = "http://localhost:8000"
HEADERS = {"X-API-Key": "abc123..."}

resp = requests.get(f"{BASE}/coding-results/stats", headers=HEADERS)
print(resp.json())
```

---

## Endpoints

### `GET /health`

Liveness-Check. Kein API-Key noetig.
Testet auch die Datenbankverbindung.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "db": "ok",
  "version": "1.0.0"
}
```

---

### `GET /coding-results`

Paginierte Liste von Coding-Ergebnissen mit optionalen Filtern.

**Query-Parameter:**

| Parameter         | Typ     | Default | Beschreibung                                      |
|-------------------|---------|---------|---------------------------------------------------|
| `limit`           | int     | 50      | Max. Ergebnisse (1-500)                           |
| `offset`          | int     | 0       | Ueberspringen fuer Pagination                    |
| `min_confidence`  | float   | -       | Nur Ergebnisse mit final_confidence >= Wert       |
| `max_confidence`  | float   | -       | Nur Ergebnisse mit final_confidence <= Wert       |
| `pt_code`         | int     | -       | Filter auf einen MedDRA PT Code                   |
| `soc_name`        | string  | -       | Filter auf System Organ Class (Teilstring)        |
| `from_date`       | date    | -       | coded_at >= Datum (YYYY-MM-DD)                    |
| `to_date`         | date    | -       | coded_at <= Datum (YYYY-MM-DD)                    |
| `exclude_fallback`| bool    | true    | Fallback-Records (llm_confidence=0.3) ausblenden  |

**Beispiele:**

```bash
KEY="dein-api-key"

# Hochverlaessliche Ergebnisse (confidence >= 0.5):
curl -H "X-API-Key: $KEY" \
  "http://localhost:8000/coding-results?min_confidence=0.5&limit=100"

# Bestimmter SOC (Nervous System Disorders):
curl -H "X-API-Key: $KEY" \
  "http://localhost:8000/coding-results?soc_name=Nervous&limit=50"

# Seite 2 (Records 51-100):
curl -H "X-API-Key: $KEY" \
  "http://localhost:8000/coding-results?limit=50&offset=50"

# Zeitraum + kein Fallback-Filter:
curl -H "X-API-Key: $KEY" \
  "http://localhost:8000/coding-results?from_date=2026-05-13&exclude_fallback=false"
```

**Antwort (Array):**

```json
[
  {
    "id": 42,
    "mdr_report_key": "MDR2024001234",
    "pt_code": 10019211,
    "pt_name": "Hypoglycaemia",
    "llt_code": 10020993,
    "llt_name": "Insulin-induced hypoglycaemia",
    "soc_name": "Metabolism and nutrition disorders",
    "vector_similarity": 0.847,
    "crossencoder_score": 3.12,
    "llm_confidence": 0.72,
    "final_confidence": 0.68,
    "model_version": "pipeline_v1",
    "coded_at": "2026-05-13T10:22:41"
  }
]
```

---

### `GET /coding-results/stats`

Aggregat-Uebersicht ueber die gesamte coding_results Tabelle.
Gut fuer Dashboard-Panels und Pipeline-Health-Checks.

```bash
curl -H "X-API-Key: $KEY" http://localhost:8000/coding-results/stats
```

```json
{
  "total_records": 1247,
  "records_with_llm": 1089,
  "fallback_count": 158,
  "avg_final_confidence": 0.3821,
  "median_final_confidence": 0.3600,
  "high_confidence_count": 43,
  "distinct_pt_codes": 187,
  "earliest_coded_at": "2026-05-11T11:04:22",
  "latest_coded_at": "2026-05-13T14:55:01"
}
```

**Felder erklaert:**

- `fallback_count` -- Records bei denen der LLM-Call fehlschlug (Sentinel-Wert 0.3).
  Hoher Wert = Pipeline-Problem (siehe Befund 13.05).
- `records_with_llm` -- Echte LLM-Codings (kein Fallback).
- `high_confidence_count` -- final_confidence >= 0.5 (Auto-Accept-Kandidaten).

---

### `GET /coding-results/{id}`

Einzelner Record per Primaerschluessel.

```bash
curl -H "X-API-Key: $KEY" http://localhost:8000/coding-results/42
```

Gibt 404 zurueck wenn die ID nicht existiert.

---

## Pagination

Fuer grosse Datenmengen: `limit` + `offset` kombinieren.

```python
import requests

BASE = "http://localhost:8000"
HEADERS = {"X-API-Key": "dein-key"}

all_results = []
offset = 0
limit = 100

while True:
    resp = requests.get(
        f"{BASE}/coding-results",
        headers=HEADERS,
        params={"limit": limit, "offset": offset, "exclude_fallback": "true"},
    )
    batch = resp.json()
    if not batch:
        break
    all_results.extend(batch)
    offset += limit

print(f"Gesamt: {len(all_results)} Records geladen")
```

---

## Lokale Entwicklung (ohne Docker)

SSH-Tunnel zu Hetzner + lokaler uvicorn:

```bash
# 1. Tunnel oeffnen (eigenes Terminal):
ssh -L 5432:localhost:5432 cap@46.225.109.99

# 2. Umgebungsvariablen setzen:
export DATABASE_URL=postgresql://vigilex:<pw>@localhost:5432/vigilex
export API_KEY=dev-secret-local

# 3. API starten:
cd vigilex
.venv\Scripts\activate        # Windows
uvicorn vigilex.api.main:app --reload --port 8000

# 4. Testen:
curl -H "X-API-Key: dev-secret-local" http://localhost:8000/health
```

---

## Datei-Uebersicht

```
vigilex/
  src/vigilex/api/
    __init__.py          -- Package-Marker
    main.py              -- FastAPI App (Endpoints, Auth, Pydantic-Models)
  docker/
    Dockerfile.api       -- Production Image (referenziert vigilex.api.main:app)
  docker-compose.yml     -- api Service mit DATABASE_URL + API_KEY
  .env.example           -- Vorlage inkl. API_KEY Eintrag
  API.md                 -- dieses Dokument
```

---

## Haeufige Fehler

| Symptom | Ursache | Fix |
|---|---|---|
| `401 Invalid or missing API key` | Header fehlt oder falscher Key | `X-API-Key` Header setzen |
| `500 Database error: connection refused` | Postgres laeuft nicht / Tunnel zu | `docker compose ps`, SSH-Tunnel checken |
| `API_KEY required` beim compose up | `API_KEY` fehlt in `.env` | `echo "API_KEY=..." >> .env` |
| Container startet nicht | Build-Fehler | `docker compose logs api` |
