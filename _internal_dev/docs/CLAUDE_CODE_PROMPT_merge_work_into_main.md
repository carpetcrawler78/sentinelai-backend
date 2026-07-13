# CC Prompt — Reset Cowork's angefangenen Merge + `work` sauber in `main` mergen

**Datum:** 2026-07-11
**Ausgangslage:** GitHub zeigt für dieses Repo standardmäßig den `main`-Branch — der ist 47
Commits hinter `work` zurück (kompletter FastAPI/PRR-ROR/Grafana/MLflow-Ausbau inkl. eines
bereits guten, aktuellen `README.md` fehlt auf `main`). `work` und `origin/work` sind
identisch (Stand HEAD `eebb112`). Ziel: `work` nach `main` mergen und pushen, damit GitHub den
echten, aktuellen Stand zeigt.

## Schritt 0 — Cowork's angefangenen Merge zurücksetzen (ZUERST, wichtig)

Cowork (Claude im Sandbox) hat bereits versucht, `git checkout main && git merge work --no-edit`
auszuführen — das ist **nicht sauber durchgelaufen**, weil die Sandbox-Mount-Bridge beim
Schreiben/Löschen mehrerer Dateien "Operation not permitted" geworfen hat (bekanntes Phänomen
dieser Session, gleiche Ursache wie frühere `index.lock`-Probleme im job-search-system-Repo).

**Aktueller Zustand (Stand vor diesem Prompt), zur Orientierung:**
- `HEAD` auf `main` ist **unverändert** bei Commit `2991fc7` — kein Commit wurde erstellt.
- Trotzdem liegen im Arbeitsverzeichnis bereits Änderungen: 9 Dateien als modifiziert
  (`.github/workflows/ci.yml`, `CLAUDE.md`, `README.md`, `docker-compose.yml`,
  `grafana/provisioning/dashboards/sentinelai_coding.json`, `requirements-coding.txt`,
  `src/vigilex/api/main.py`, `src/vigilex/coding/hybrid_search.py`,
  `src/vigilex/workers/coding.py`), plus mehrere neue, untracked Dateien/Ordner aus `work`
  (`migrations/`, `scripts/*.py`, `tests/*.py`, `config/`, `docs/`, `alt/`, u. a.).
- Eine verwaiste `.git/index.lock` (0 Byte) blockiert git-Kommandos — von der Sandbox aus nicht
  löschbar.

**Weil nicht sicher verifizierbar ist, ob die bereits geschriebenen Dateien wirklich vollständig
und unbeschädigt sind (die Unlink-Fehler kamen unregelmäßig, teils bei Dateien die als "M" und
teils bei Dateien die als "??" endeten), NICHT auf diesem Zwischenstand aufbauen. Stattdessen
komplett verwerfen und sauber neu mergen:**

```bash
cd "C:\Users\thheg\bootcamps\CAPSTONE II\vigilex"

# 1. Verwaiste Lock-Datei entfernen (lokal problemlos möglich, kein echter paralleler Git-Prozess)
del .git\index.lock

# 2. Sicherstellen, dass wirklich kein Merge "in progress" registriert ist
git status

# 3. Cowork's angefangenen Merge-Versuch komplett verwerfen -- verlustfrei, HEAD war nie verändert
git merge --abort 2>nul
git reset --hard HEAD
git clean -fd

# 4. Verifizieren: Arbeitsverzeichnis muss jetzt exakt HEAD (main, 2991fc7) entsprechen
git status --short
```

`git status --short` muss danach **leer** sein (keine M/??/!!-Zeilen). Falls nicht leer:
STOPP, nicht weitermachen, sondern den tatsächlichen Zustand im Abschlussbericht (s. u.)
dokumentieren statt zu raten.

## Schritt 1 — `work` sauber in `main` mergen

```bash
git checkout main
git merge work --no-edit
```

Da `work` und `main` bisher keine echten inhaltlichen Konflikte zeigten (nur die job-search-
system-Kontamination auf `main`, s. Schritt 3), sollte das ohne Konfliktmarker durchlaufen.

**Falls doch Konflikte auftreten:** nicht automatisch/blind auflösen. Auflisten, welche Dateien
betroffen sind, und im Abschlussbericht (s. u.) für Thomas dokumentieren statt zu entscheiden.

## Schritt 2 — Verifikation vor dem Push

```bash
# Testsuite muss grün bleiben
pytest

# README.md muss jetzt die aktuelle, ausführliche Version zeigen (nicht mehr die alte
# "LightGBM + Optuna / Phase II LangChain+FAISS"-Beschreibung)
git show HEAD:README.md | head -20

# Kurzer Sanity-Check: PRR/ROR, FastAPI, Grafana, MLflow muessen jetzt im README erwaehnt sein
git show HEAD:README.md | grep -iE "PRR|ROR|FastAPI|Grafana|MLflow"
```

Falls `pytest` nicht grün ist: **nicht pushen**, im Abschlussbericht dokumentieren.

## Schritt 3 — Push

```bash
git push origin main
```

## Schritt 4 — NICHT tun (bewusst außerhalb dieses Prompts)

- **Keine History-Bereinigung.** `main` enthält in seiner Historie 10 Commits, die versehentlich
  job-search-system-Dateien (`PROJECT_MEMORY.md`, `status-chatgpt.md`, ein Sync-Rules-Prompt)
  committet und später wieder entfernt haben (`2991fc7`). Diese Inhalte sind weiterhin vollständig
  aus der Git-History rekonstruierbar. Thomas hat dazu bereits explizit "nur informieren, nichts
  tun" entschieden (2026-07-11) — **kein `git filter-repo`/BFG in diesem Prompt.**
- **Keine Bereinigung der Hetzner-IP** (`46.225.109.99` + SSH-User `cap`), die in mehreren
  Dateien in diesem Repo hardcoded ist (u. a. `src/vigilex/workers/coding.py`,
  `src/vigilex/workers/signal.py`, diverse Scripts) — Thomas hat das ebenfalls bereits separat
  auf "nur informieren, nichts tun" gesetzt (gilt für das öffentliche `sentinelai`-Repo, dieselbe
  Zurückhaltung hier übernehmen, bis Thomas explizit etwas anderes sagt).
- Keine Änderungen an `work` selbst — nur `main` wird durch den Merge bewegt.

## Abschluss

Kurzer Eintrag in `DEVLOG.md` (Datum 2026-07-11): dass Cowork's Merge-Versuch verworfen und neu
sauber durchgeführt wurde, Testergebnis, Commit-Hash des Merge-Commits, ob gepusht wurde oder
nicht (und warum, falls nicht).
