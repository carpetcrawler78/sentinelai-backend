# Session 2026-05-18 -- PRR/ROR Multi-Device Setup

## Ausgangslage

PRR/ROR Signaldetektion zeigte fuer alle 430 PT-Kombinationen `prr=None`.

**Root Cause:** Nur ein Produkt-Code (LZG = Insulinpumpen) in der DB.
Die PRR-Formel benoetigt eine Hintergrundpopulation aus anderen Device-Typen.
Mit nur LZG ist `n_all_devices_total == n_reports_focal` -> Division by Zero -> None.

Ergebnis `threshold_scan.py`:
```
Total results: 430
Results with PRR not None: 0
Sample row: {'prr': None, 'is_signal': False, ...}
```

---

## Was wir gemacht haben

### 1. Ingest QFG (CGM-Sensoren) -- ERFOLGREICH

```bash
docker compose run --rm worker-ingest python3 -m vigilex.workers.ingest --product-code QFG --year 2024
```

- openFDA: 282.061 Records gesamt, API-Limit 10.000
- Ergebnis: **~20.000 neue Records** in `raw.maude_reports` (inkl. ACE-Pump Varianten)
- Beobachtung: erste Batches zeigten "0 records committed" (Dedup-Checks), dann Bulk-Insert

### 2. Ingest OYC (Herzschrittmacher) -- TEILWEISE

```bash
docker compose run --rm worker-ingest python3 -m vigilex.workers.ingest --product-code OYC --year 2024
```

- openFDA: 16.046 Records gesamt
- Batch-Rate: 1 record/Batch (~4 Sek/Record) -- sehr langsam
- Abgebrochen nach 17 Records (reicht als Proof-of-Concept)
- Pacemaker-Device-Namen erscheinen NICHT in `raw.maude_reports` GROUP BY device_name
  -> Die 17 Records wurden moeglicherweise rolled back oder haben NULL device_name

### 3. LZG-Rückstand skippen -- ERFOLGREICH

Problem: ~3.141 uncodierte LZG-Records blockieren die Queue (niedrigere IDs).
Coding-Worker wuerden QFG erst nach ~35 Stunden erreichen.

Loesung: Dummy-Eintrag in `processed.coding_results` fuer alle uncodierten LZG-Records:

```sql
INSERT INTO processed.coding_results
    (mdr_report_key, pt_code, pt_name, llt_code, llt_name, soc_name,
     vector_similarity, crossencoder_score, llm_confidence, final_confidence,
     model_version, coded_at)
SELECT r.mdr_report_key, NULL, 'SKIPPED_LZG', NULL, NULL, NULL,
       0.0, 0.0, 0.0, 0.0, 'skipped_lzg_remainder', NOW()
FROM raw.maude_reports r
LEFT JOIN processed.coding_results cr ON r.mdr_report_key = cr.mdr_report_key
WHERE cr.id IS NULL AND r.product_code = 'LZG';
```

Ergebnis: **2.601 LZG-Records geskippt**

Fuer PRR diese Records herausfiltern:
```sql
WHERE model_version != 'skipped_lzg_remainder'
```

### 4. Coding-Worker neu starten -- ERFOLGREICH

```bash
docker compose up -d worker-coding
```

Worker kodiert nun QFG-Records (mdr_report_key: `2032227-2024-*`)

---

## Problem: Ollama Timeouts

### Symptom
```
LLM coding failed (HTTPConnectionPool(host='ollama', port=11434): 
Read timed out. (read timeout=60)). Falling back to top CrossEncoder candidate.
conf=NULL   ~100-170 Sekunden pro Record
```

Ollama gibt HTTP 500 zurueck nach exakt 60 Sekunden.

### Root Cause: RAM-Mangel / Swap-Ueberlastung

```
free -h (vor Fix):
Mem:  7.6Gi  5.2Gi  156Mi   -- nur 156 MB frei!
Swap: 2.0Gi  1.9Gi   74Mi   -- Swap fast voll

free -h (nach Fix):
Mem:  7.6Gi  4.9Gi  440Mi
Swap: 2.0Gi  406Mi  1.6Gi   -- drastisch besser
```

Docker Container RAM-Verteilung:
```
vigilex-worker-coding   1.17 GB
vigilex-ollama          2.58 GB
vigilex-mlflow          273 MB   <- gestoppt
vigilex-grafana         102 MB   <- gestoppt
vigilex-postgres        172 MB
```

### Massnahme
```bash
docker compose stop mlflow grafana
```
-> Swap von 1.9 GB auf 406 MB reduziert

### Ergebnis nach Fix
Direkttest:
```bash
curl -m 90 http://localhost:11434/api/chat \
  -d '{"model":"llama3.2:3b","messages":[{"role":"user","content":"hi"}],"stream":false}'
# Antwort in 7.3 Sekunden -- Ollama grundsaetzlich OK
```

**Problem bleibt:** Echte MAUDE-Coding-Prompts sind viel laenger als "hi".
Ollama schafft komplexe Prompts nicht in 60 Sekunden auf CPU-only.
-> CrossEncoder-Fallback greift weiterhin, `conf=NULL`

---

## Aktueller Stand (Session-Ende ~18:15 Uhr)

| Component | Status |
|---|---|
| `raw.maude_reports` | ~30.000 Records (LZG + QFG + 17 OYC) |
| `processed.coding_results` | ~6.859 LZG coded + 2.601 skipped |
| worker-coding | Laeuft, kodiert QFG via CrossEncoder-Fallback |
| Ollama LLM | Timeoutet bei echten Prompts (>60s CPU-Inferenz) |
| Grafana | Gestoppt (RAM sparen) |
| MLflow | Gestoppt (RAM sparen) |
| Groq | Option offen (nicht gestartet) |

### Throughput Prognose
- Aktuell (CrossEncoder-Fallback): ~1 Record/90 Sek = ~480 Records bis morgen 8 Uhr
- Mit Groq (`--groq` Flag): ~3.69 rec/min = ~2.600 Records bis morgen 8 Uhr

---

## Offene Entscheidung: Groq fuer QFG-Coding?

**Pro:**
- 3.69 rec/min statt 0.67 rec/min
- Echte LLM-Confidence-Scores (nicht NULL)
- ~2.600 QFG Records bis morgen vs ~480

**Contra:**
- Groq = llama-3.1-8b, LZG war Ollama = llama-3.2-3b -> Modell-Drift
- Narratives gehen an externe API (DSGVO-Bedenken, nicht fuer Produktion)
- CLAUDE.md: "Groq = Upper-Bound-Reference, nicht Production-Proxy"

**Methodischer Hinweis:**
LZG hatte durch den 13.05-Bug auch ~83% CrossEncoder-Fallback.
Streng genommen ist LZG auch nicht "rein LLM-kodiert".
-> Der Äpfel/Birnen-Vergleich ist ohnehin schon kompromittiert.

---

## Naechste Schritte (Di 19.05)

1. Coding-Status pruefen:
```sql
SELECT model_version, COUNT(*), AVG(final_confidence)
FROM processed.coding_results
WHERE model_version != 'skipped_lzg_remainder'
GROUP BY model_version;
```

2. PRR/ROR mit Multi-Device laufen lassen:
```bash
cd vigilex
$env:PYTHONPATH="src"
$env:DATABASE_URL="postgresql://vigilex:PW@localhost:5432/vigilex"
python scripts/threshold_scan.py
```

3. Ollama-Timeout erhoehen (optional, Code-Aenderung noetig):
   - Datei: `src/vigilex/coding/llm_coder.py`
   - Timeout-Parameter von 60s auf 180s erhoehen

4. Grafana + MLflow wieder starten wenn PRR-Demo fertig:
```bash
docker compose start grafana mlflow
```

5. SSH-Key fuer Claude-Sandbox einrichten (5 Min):
```powershell
ssh-keygen -t ed25519 -f "$HOME\.ssh\claude_hetzner" -N ""
# Public Key auf Hetzner in ~/.ssh/authorized_keys einfuegen
```
-> Ermoeglicht direktes SSH aus Claude-Sandbox in kuenftigen Sessions

---

## Lektionen

- **RAM-Monitoring:** Hetzner-Server hat nur 7.6 GB RAM. Bei vollem Swap bricht Ollama-Inferenz ein.
  Grafana + MLflow stoppen wenn Worker + Ollama gleichzeitig laufen.
- **Queue-Reihenfolge:** Coding-Worker verarbeitet nach ID (FIFO). Neue Product-Codes kommen ans Ende.
  Skip-Insert ist der sauberste Weg um Prioritaeten umzukehren.
- **product_code Spalte:** `raw.maude_reports` hat `product_code` Spalte mit Index -- gut fuer gezielte Queries.
- **`docker compose run` vs `up`:** `run` erstellt neuen Container und entfernt ihn nach Ende (`--rm`).
  Fuer Worker die dauerhaft laufen sollen: `up -d` verwenden.
