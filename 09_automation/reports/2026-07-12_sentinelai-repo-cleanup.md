# Auftrag 25 -- SentinelAI-Repos aufraeumen: Bericht

Ausgefuehrt: 2026-07-13 | Repos: `sentinelai-backend` (lokal `vigilex`), `sentinelai`

## Ergebnis

Alle 6 Teile (A-F) erledigt und gepusht.

- `sentinelai-backend`: 5 Commits (`8af21ca`, `0cdef24`, `b558920`, `c849e95`, `4afd6d4`), gepusht `97e7bf2..4afd6d4`
- `sentinelai`: 2 Commits (`b066fe5`, `de46c66`), gepusht `253546c..de46c66`

**Nachtrag (Fix, gleicher Tag):** Der Auftragstext ging davon aus, dass
`git mv` + `.gitignore`-Eintrag + normaler Commit die Dateien "aus dem
oeffentlich sichtbaren Tree verschwinden" laesst -- das stimmt nicht.
`.gitignore` verhindert nur kuenftige *untracked* Neuzugaenge, es entfernt
keine bereits committeten Dateien aus dem getrackten Tree. Nach dem ersten
Push waren alle 35 (`sentinelai-backend`) bzw. 3 (`sentinelai`) internen
Dateien unter `_internal_dev/` weiterhin voll sichtbar auf GitHub. Fix:
`git rm --cached -r _internal_dev/` in beiden Repos (Dateien bleiben lokal
auf der Platte, verschwinden aber aus dem aktuellen GitHub-Tree), je ein
weiterer Commit + Push. Die Inhalte bleiben in der Git-Historie auffindbar
(bewusst nicht bereinigt, siehe Auftrag).

## Teil A -- Dateien nach `_internal_dev/` verschoben

`sentinelai-backend`: alle 19 im Auftrag gelisteten Dateien/Ordner per `git mv`
verschoben (Historie erhalten), plus die eine bereits vorhandene untracked
Planungsdatei (`docs/CLAUDE_CODE_PROMPT_merge_work_into_main.md`) mit rein
aufgenommen. `_internal_dev/` in `.gitignore` eingetragen. `alt/` und
`scripts/archive/` sind jetzt leer (lokal entfernt, Git trackt leere Ordner
ohnehin nicht).

`sentinelai`: `.claude/settings.local.json`, `.lovable/plan.md`,
`.lovable/project.json` verschoben, `_internal_dev/` in `.gitignore`.

## Teil B -- Duplikate geloescht

- `notebooks/03b_features_and_model.ipynb`
- `notebooks/archive/02_recall_labels.ipynb`
- `scripts/archive/explore_product_codes.py`

## Teil C -- DEVLOG.md wiederhergestellt

`alt/DEVLOG_2026-06-01_merged.md` -> `DEVLOG.md` (Root). Letzte MISTAKE/RULE-
Zeilen umgeschrieben, Claude-Code-/CLAUDE_CODE_ERRORS.md-Verweis entfernt,
Kern-Learning (fragile lange Inline-SSH/Python-Einzeiler) behalten. README
verweist bereits korrekt auf `DEVLOG.md`, keine README-Aenderung noetig.

## Teil D -- Code-/Notebook-Referenzen auf CLAUDE.md entfernt

Alle 5 Stellen wie vorgegeben umgeschrieben:
`workers/coding.py:112`, `workers/coding.py:401`, `coding/llm_coder.py:60`,
`coding/llm_coder.py:239`, `notebooks/04_meddra_eda.ipynb` (Markdown-Zelle).
Keine weiteren Fundstellen in `scripts/` oder sonst in `src/`.

## Teil E -- Hetzner-IP entschaerft

`docs/evaluation/embedding_benchmark_2026-05-26.md`: IP raus, "Hetzner CX33
instance (EU)" wie im Auftrag vorgegeben. `EVAL_PLAN.md` und
`docs/decisions/DECISION_query_fusion.md` unveraendert gelassen (Auftrag
explizit).

## Teil F -- Kommentar-Ton Senior -> Junior/Lernender

Ca. **7 Stellen** in 2 Dateien umgeschrieben:
- `src/vigilex/coding/llm_coder.py` (6 Stellen: Ollama-Docstring/Privacy-Absatz,
  Ollama-URL-Banner, hardcoded-Modell-Kommentar, Strict-Mode-Banner, Groq-Banner,
  "graceful degradation"-Docstring-Zeile)
- `src/vigilex/workers/coding.py` (1 Stelle: Strict-Mode-Banner)

Alle Kalibrierungsbeispiele aus dem Auftrag 1:1 angewendet. Die restlichen 8
Dateien mit ASCII-Bannern in `src/vigilex/` (`signal.py`, `hybrid_search.py`,
`main.py`, `ingest.py`, `prr_ror.py`, `maude_client.py`, `import_meddra.py`,
`reranker.py`) sowie alle 13 verbleibenden `scripts/*.py` wurden geprueft --
keine echten Jargon-Treffer gefunden, Banner sind dort bereits schlichte
Abschnittsueberschriften ("Constants", "Helpers", "Main", etc.), unveraendert
gelassen. Zwei Vorkommen von "idempotent" (Fachbegriff, kein Banner-/ADR-Ton)
bewusst nicht angefasst -- kein Fall der im Auftrag beschriebenen Kategorie.

## Test-Ergebnis

Vorher: 36 passed | Nachher: 36 passed (nach jedem der 4 Commits erneut
geprueft, durchgehend gruen).

## Offene/unsichere Punkte

- `eval_candidates/` enthielt tatsaechlich mehr als im Auftrag aufgefuehrt:
  6 statt 5 `.xlsx`, plus 5 `.csv` und einen zusaetzlichen `v2/`-Unterordner
  mit 3 weiteren `.csv` (insgesamt 13 Dateien statt der genannten 2 `.py` +
  5 `.xlsx`). Da der Auftrag "kompletter Ordner" vorgab, wurde alles regulaer
  mitverschoben -- keine Aktion noetig, nur zur Kenntnis.
- `notebooks/04_meddra_eda.ipynb`: Das Editier-Tool hat beim Umschreiben der
  betroffenen Markdown-Zelle deren `source`-Feld von einer Zeilen-Liste auf
  einen einzelnen String umgestellt (beides gueltiges nbformat, oeffnet
  einwandfrei, aber inkonsistent zum Stil der uebrigen Zellen in der Datei).
  Rein kosmetisch, keine Funktionsaenderung.

## Nicht angefasst (wie vorgegeben)

Git-History, `DECISION_query_fusion.md`, `EVAL_PLAN.md`, `API.md`, uebrige
Notebooks, Test-/Pipeline-Logik.
