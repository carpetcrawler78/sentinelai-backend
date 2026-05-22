# Session 2026-05-18 Abend -- Multi-Worker-Diagnose + Recovery

## Anlass

Nach session_2026-05-18_prr_setup.md (Vormittag/Nachmittag, PRR-Multi-Device-Setup) lief
der Coding-Worker auf Hetzner mit 100% Fallback-Rate. Symptom:
- `LLM coding failed (HTTPConnectionPool: Read timed out, read timeout=60)`
- Records mit `llm_confidence=NULL` und `final_confidence=NULL`
- Worker brach nicht ab (VIGILEX_STRICT=False) sondern produzierte Muell

## Initiale Hypothesen (alle falsch)

1. **QFG-Narratives sind laenger als LZG** -> Memory-Bandwidth-Bottleneck
2. **Ollama-Container hat strukturelles Problem** -> Restart noetig
3. **Hetzner-CPU-Steal-Time** -> Provider drosselt unter Last
4. **Postgres-Autovacuum konkurriert** -> Background-Indexing

## Methodische Wende durch Thomas

Nach ca. 4h Container-Diagnose (Ollama-Logs, Restart-Versuche, Container-RAM):
> "das ist ja alles auf hetzner, kann man da nicht schauen, was los ist?"

Sofort Host-Level-Diagnose:

```
uptime
 load average: 7.72, 8.87, 9.50   <- bei 4 CPUs! 2x ueberlastet

ps -ef | grep " docker" | grep -v grep
cap 1408034 ... docker compose run --rm worker-ingest python3 -m vigilex.workers.ingest --product-code QFG --year 2024
Gestartet: 16:58 UTC
Cumulative CPU: 249 Minuten

ps -ef | grep python3 | grep -v grep
cap 2728171 ... python3 -m vigilex.workers.coding
Gestartet: May15 (Freitag, im tmux 'coding-weekend')
```

## Tatsaechliche Root Causes (zwei parallel)

### 1. Zombie-Ingest-Prozess
- `scripts/hetzner_switch_to_qfg_oyc.sh` heute Morgen 16:58 UTC gestartet
- Bug im Script: `docker compose run --rm -d --name ingest-qfg worker-ingest python3 -m vigilex.workers.ingest --product-code QFG --year 2024`
- Der `-d` Flag startet zwar Container detached, aber der CLI-Prozess bleibt im Vordergrund haengen
- Vermutlich in openFDA-Retry-Loop oder Memory-Leak gestorben, brannte aber konstant ~100% CPU
- Lief seitdem fast 3 Stunden ungemerkt

### 2. Multi-Worker-Konflikt
- Host-Worker im tmux 'coding-weekend' lief seit Freitag 15.05 14:37 UTC durchgehend
- Docker-Worker (vigilex-worker-coding) wurde zusaetzlich heute gestartet (via Switch-Script)
- Beide Worker schickten parallel Ollama-Calls
- Auf 4 vCPU Hardware = CPU-Saturation -> Ollama-Inferenz wurde so langsam, dass interner 60s-Timeout griff
- HTTP 500 Responses, alle Calls fielen in Fallback

## Timeline (UTC)

| Zeit | Event |
|---|---|
| Fr 15.05 14:37 | Host-Worker im tmux 'coding-weekend' gestartet (lief durch bis 20:05) |
| Mo 16:58 | Switch-Script lief, QFG-Ingest gestartet -> Zombie-Prozess entsteht |
| Mo 17:01 | Erste Ollama HTTP 500 Responses (genau 60s Timeout) |
| Mo 17:00-19:00 | 100% Fallback-Rate, ~178 Muell-Records in DB |
| Mo 19:00 | Diagnose-Wende durch Thomas (Host-Level statt Container) |
| Mo 19:15 | Zombie-Ingest gekillt (kill -9 1408034 1408049) |
| Mo 19:30-20:05 | Host-Worker brachte trotzdem nur Fallbacks (immer noch ueberlastet) |
| Mo 20:05 | Host-Worker im tmux gestoppt (kill -INT 2728171) |
| Mo 20:06 | Ollama-Smoke-Test: 1.19s fuer "hi", 16 t/s = gesund |
| Mo 20:15 | DB-Cleanup: ~178 NULL/Fallback-Records seit 17:00 UTC geloescht |
| Mo 20:23 | Worker neu im tmux 'coding-weekend' gestartet, Single-Instance |
| Mo 20:24 | Erste echte LLM-Codings: conf=0.561-0.593, ~35s pro Record |

## Datenstand (Stand 18.05 21:30 lokal)

DB processed.coding_results:
- pipeline_v1: **7325 Records** (LZG, davon 7324 mit echtem LLM, 97%)
  Bisheriger CLAUDE.md-Eintrag "1092 echte LLM" war **veraltet** -- Re-Coding-Run nach 13.05 Bug-Fix
  war viel erfolgreicher als dokumentiert
- skipped_lzg_remainder: 2601 Records (Notloesung Switch-Script, um QFG vorzuziehen)
- Neue Records ab 20:23 UTC: QFG (laeuft autonom)

DB raw.maude_reports: ~30.000 Records
- LZG: ~7.000 (alle codiert)
- QFG: ~20.000 (in Coding-Queue)
- OYC: 17 (zu wenig fuer Statistik, openFDA-API war zu langsam)

## Engineering-Lessons (fuer CLAUDE.md + Talk-Story)

### Lesson 1: Host-Diagnostik zuerst
Bei Service-Performance-Issues ZUERST Host-Level pruefen (uptime, top, ps, vmstat).
Container-Logs sind nicht der erste Anlaufpunkt.

```bash
# Standard-Diagnose-Sequenz
uptime                                  # load avg vs nproc
top -bn1 -o %CPU | head -15            # wer brennt CPU?
ps -ef | grep <service> | grep -v grep # vergessene/duplizierte Prozesse?
vmstat 1 5                             # CPU-Steal (st-Spalte), Swap (si/so)
free -h                                # echte RAM-Lage
```

### Lesson 2: Single-Instance-Policy fuer Worker
Der Coding-Worker existiert in zwei Varianten (Host-tmux + Docker-Compose).
Nie beide gleichzeitig laufen lassen. Vor jedem Coding-Run pruefen:

```bash
ps -ef | grep "vigilex.workers.coding" | grep -v grep   # Host-Variante?
docker ps | grep worker-coding                            # Docker-Variante?
tmux ls                                                   # alte Sessions?
```

### Lesson 3: `docker compose run -d` Race-Condition
Der `-d` Flag macht den Container detached, aber der CLI-Prozess bleibt blocking.
Vergessene CLI-Prozesse koennen stundenlang CPU brennen ohne in `docker ps` aufzutauchen.

**Workaround:** stattdessen `docker compose up -d worker-ingest` verwenden, oder
explizit mit `nohup ... &` und `disown` arbeiten.

### Lesson 4: Schema nicht raten
Narrative-Spalte in `raw.maude_reports` heisst `mdr_text` (nicht `event_description`).
Coding-Timestamp ist `coded_at` (nicht `created_at`). Beim Vorschlagen von SQL/Code
ZUERST im Repo/CLAUDE.md/memory nachschlagen, nicht raten.

## Talk-Story-Update fuer Final Presentation

> "Production-Debug Story: Multi-Worker-Konflikt auf CPU-limitierter Hardware (4 vCPU AMD EPYC).
> Ein vergessener docker-CLI-Zombie aus einem Migration-Script plus parallele
> Worker-Instanzen (Host-Backup + Docker-Production) ueberlasteten das System bis Ollama
> nach genau 60 Sekunden in interne Timeouts kollabierte. Symptom sah wie Service-Crash aus,
> Container-Logs zeigten nur HTTP 500.
>
> Methodische Erkenntnis: Container-Diagnose ist nicht der erste Anlaufpunkt. Host-Level
> Tools (uptime, top, ps) deckten in 5 Minuten auf, was 4 Stunden Container-Debugging
> nicht zeigten: load average 9.5 auf 4 CPU = 2x ueberlastet.
>
> Production-Lesson: explizite Single-Instance-Policy fuer Worker + Watchdog fuer
> vergessene CLI-Prozesse. Plus: Schema/Code/Env-Vars NIE raten -- nachschlagen."

## Naechste Schritte (Di 19.05 morgens)

1. Worker-Status pruefen (laeuft er noch?)
2. QFG-Coding-Fortschritt: COUNT seit 20:23 UTC, conf-Verteilung
3. Bei ~300-500 QFG-Records: Worker stoppen (Ctrl+C im tmux)
4. PRR/ROR re-run mit LZG + QFG: erwartet jetzt > 0 Signals
5. Falls 3. Comparator-Device gewuenscht: DXY (Defibrillator) oder FRN (Infusion Pump) ingest

## Verwandte Memory-Eintraege (Auto-Memory)

- feedback_host_diagnostics_first: Performance-Probleme zuerst Host-Ebene
- reference_vigilex_worker_topology: Host + Docker Worker-Varianten + Single-Instance-Policy
- reference_vigilex_schema: mdr_text und coded_at Spaltennamen
- feedback_no_guessing_schema: Schema-Info nicht raten
- feedback_stop_decision: Thomas entscheidet wann Schluss ist
