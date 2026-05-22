# Session 2026-05-19 Morgen -- 92% Fallback Befund + Strategie

## Ausgangslage

Worker lief von 18.05 20:23 UTC bis 19.05 ~08:16 UTC (12 Stunden) autonom im tmux
'coding-weekend' fuer QFG-Records. ntfy-Pushes kamen bei 600 und ~942 Records.

Erwartung Morgen: ~600-700 QFG-Records mit echtem LLM-Confidence, ready fuer PRR/ROR.

## Befund

Confidence-Verteilung der 632 QFG-Records (Query Stand 08:16 UTC):

| Bucket | Count | Anteil | avg_final |
|---|---|---|---|
| `llm_confidence = 0.50` EXAKT | 430 | 68% | 0.354 |
| `llm_confidence = 0.80` EXAKT | 140 | 22% | 0.570 |
| `< 0.5` (gemischt, nicht NULL/0.3/0.5) | 45 | 7% | 0.021 |
| `>= 0.7` (nicht 0.8) | 16 | 2.5% | 0.712 |
| `NULL` | 1 | 0.16% | - |
| `0.5-0.7 exclusive` | **0** | **0%** | - |

**Schluesselindiz:** KEINE Records mit kontinuierlichem `llm_confidence` zwischen
0.5 und 0.7 (exclusive). Echter LLM-Output waere hier verteilt (z.B. 0.612, 0.587, 0.541).
Stattdessen alles auf exakt 0.5 oder 0.8 geclustert.

Hourly Throughput stabil:
- ~50-58 Records/Stunde
- `failed=0` (no NULL) -- Worker meldet keine Failures
- avg_llm hourly 0.5-0.6 (taeuscht: ist Average ueber discrete 0.5/0.8 Buckets)

## Interpretation

Worker schreibt "graceful fallback" statt echter LLM-Outputs. Vermutete Code-Pfade
in `llm_coder.py`:
- `llm_confidence = 0.5` -- Default wenn LLM-Response unparsbar oder Timeout
- `llm_confidence = 0.8` -- Default wenn CrossEncoder hohe Confidence hat (>threshold)
- `llm_confidence = NULL` -- nur bei explizitem Exception (selten, 1 Record)

## Korrektur zur 18.05-Abend-Session

In session_2026-05-18_evening_diagnostics.md wurde `conf=0.561-0.593` aus dem tmux-Log
als "echte LLM-Codings" interpretiert. Das war voreilig:

- Das `conf` im Log ist `final_confidence` (gemischte Score nach Stage 1+2+3)
- Die zugrundeliegende `llm_confidence` Spalte ist exakt 0.5 oder 0.8 (Fallback)
- `final_confidence = 0.3 * sigmoid(CE_logit) + 0.7 * llm_confidence` (laut vigilex/CLAUDE.md)
  -> bei llm_confidence=0.5 und CE_logit ~-8 wird final ~0.354
  -> bei llm_confidence=0.8 und CE_logit ~-6 wird final ~0.570

Die `conf=0.561-0.593` waren also rechnerisch konsistent mit Fallback-Pattern,
nicht mit echtem LLM-Output.

## Offene Diagnose-Fragen

1. **Ist Ollama gerade ueberhaupt aktiv?**
   ```
   time curl -s -m 30 http://localhost:11434/api/chat \
     -d '{"model":"llama3.2:3b","messages":[{"role":"user","content":"hi"}],"stream":false}'
   ```
   - <5s: Ollama OK, Problem ist im Worker-Code-Pfad
   - >30s: Memory-Pressure / Ollama-Saturation wieder da

2. **Welche `model_version`-Werte sind in den Records?**
   ```
   SELECT model_version, COUNT(*) FROM processed.coding_results
   WHERE coded_at >= '2026-05-18 20:23:00+00' GROUP BY model_version;
   ```
   Erwartung: alles `pipeline_v1` (zu generisch, sagt nicht ob Fallback oder echt)

3. **Wuerde STRICT_MODE=True helfen?**
   - Aktuell `VIGILEX_STRICT=False` -> Worker schreibt Fallback statt zu raisen
   - Mit STRICT=True wuerde Worker abbrechen bei Ollama-Failure
   - Trade-off: keine Fallback-Records (saubere Daten) vs. Worker stoppt komplett

## Strategische Optionen fuer heute (Di 19.05)

### Option A: Mit den 632 Records arbeiten (PRR/ROR jetzt)
- Argument: `pt_code` ist vom CrossEncoder, gueltig fuer Disproportionalitaets-Analyse
- Sprint-Realitaet: Final Demo 03.06, 15 Tage verbleibend
- Talk-Framing: "Multi-Stage Pipeline -- CrossEncoder + LLM-Calibration. Live-Demo zeigt
  Stage 2 + Stage 3 Tech-Preview. Production-Run wuerde GPU-Server fuer stabile LLM-Stage nutzen."
- **PRR/ROR Worker-Module fehlt noch** (`vigilex.workers.signal` nicht implementiert) -- muss
  noch gebaut werden

### Option B: Worker-Code debuggen, dann sauber neu coden
- `llm_coder.py` untersuchen warum Fallback-Pfad greift
- Vermutlich: Ollama-Timeout (60s) zu kurz fuer komplexere QFG-Prompts, oder Response-Parser
  zu strikt
- Kostet 2-4h, danach evtl. neuer 12h-Run noetig
- Trade-off: Risiko vs. Sprint-Zeit

### Option C: Worker auf Groq umstellen fuer QFG (mit `--groq` Flag)
- Existiert laut CLAUDE.md
- Schneller, zuverlaessiger LLM-Path (3.69 rec/min statt 1.67 rec/min)
- Trade-off: Model-Drift (llama-3.1-8b vs llama3.2:3b on-prem fuer LZG)
- Akzeptabel fuer Capstone-Demo (MAUDE = public domain, kein DSGVO-Issue)

## Empfehlung

**Option A + parallel Option B in <2h:**
1. Worker stoppen, Daten so wie sie sind nehmen
2. PRR/ROR-Modul implementieren (eh noetig laut CLAUDE.md "Naechste Schritte")
3. PRR/ROR auf 7325 LZG + 632 QFG laufen lassen -> echte Signals erwarten
4. PARALLEL: kurz in `llm_coder.py` schauen warum Fallback greift (max 1h)
5. Falls quick fix: Worker mit Fix erneut starten, frische Codings fuer Demo

## Datenstand zusammengefasst (19.05 08:16 UTC)

`processed.coding_results`:
- pipeline_v1, LZG-Wochenend-Run: 7325 Records (~7324 mit echtem LLM laut alter Statistik
  vom 13.05-Re-Coding -- ACHTUNG: koennte gleiches Fallback-Problem haben, neu verifizieren!)
- skipped_lzg_remainder: 2601 Records (Notloesung 18.05 Morgen)
- pipeline_v1, QFG seit 18.05 20:23 UTC: 632 Records (92% Fallback laut Bucket-Analyse)
- Total: ~10.558 Records

`raw.maude_reports`: ~30.000 Records
- LZG: ~7.000
- QFG: ~20.000 (Queue noch 19.300+ Records uncodiert)
- OYC: 17

## Reflektion (Memory-Material)

Eigene Lesson: am 18.05 Abend zu schnell "echte LLM-Codings" gesagt aufgrund von `conf=0.5xx`
im Worker-Log. Haette von Anfang an `llm_confidence` Spalte separat pruefen muessen (nicht
nur final_confidence aus dem Log-Output).

Memory-Update noetig: bei Confidence-Auswertung IMMER beide Spalten separat anschauen
(llm_confidence raw + final_confidence mixed), und Hardware-Sentinel-Werte (NULL, 0.3, 0.5, 0.8)
explizit als Fallback-Indikatoren behandeln.

## Verwandte Doku

- session_2026-05-18_prr_setup.md -- Vormittag/Nachmittag PRR-Multi-Device-Setup
- session_2026-05-18_evening_diagnostics.md -- Multi-Worker-Konflikt + Recovery
- CLAUDE.md (CAPSTONE II) -- Sprint-Wahrheit, Lessons, Talk-Story
- vigilex/CLAUDE.md -- Technische Repo-Doku (Architektur, Modules, Code-Pfade)
- DEVLOG.md (CAPSTONE II) -- Technical Diary
