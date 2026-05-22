# SentinelAI / vigilex — Debug Summary 2026-05-19

## Context

This note summarizes the debugging session around the suspected “fallback explosion” in `processed.coding_results` after the QFG overnight coding run.

The initial concern was that SentinelAI had returned to an earlier bug pattern: thousands of records being coded through fallback instead of real LLM output. This concern was plausible because a previous major bug had caused mass fallback due to an incorrect Ollama URL in container mode.

The debugging objective was to determine whether the new QFG result pattern was:

1. a repeat of the old `localhost` / `OLLAMA_BASE_URL` bug,
2. a hardware or Ollama performance problem,
3. a stale-code / old-worker problem,
4. a real LLM-output pattern caused by the current prompt,
5. or a mixture of these issues.

---

## Initial symptom

The QFG overnight run showed a suspicious distribution:

- many records with `llm_confidence = 0.50`
- many records with `llm_confidence = 0.80`
- almost no continuous confidence values between `0.5` and `0.7`
- stable throughput
- almost no `NULL` values

The early interpretation was: “This looks like fallback.”

That interpretation was later corrected.

---

## Checks performed

### 1. Worker topology check

Commands used:

```bash
ps -ef | grep "vigilex.workers.coding" | grep -v grep
tmux ls
docker compose ps
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Command}}"
```

Findings:

- Docker `worker-coding` was not running.
- Only the host/tmux worker had been running earlier.
- Later, no host worker was running either.
- Active Docker services were only:
  - `vigilex-api`
  - `vigilex-ollama`
  - `vigilex-postgres`
  - `vigilex-redis`

Conclusion:

The current issue was not caused by two active coding workers at that moment. The previous multi-worker problem had been resolved.

---

### 2. Ollama health check

Command used:

```bash
time curl -s -m 30 http://localhost:11434/api/chat \
  -d '{"model":"llama3.2:3b","messages":[{"role":"user","content":"hi"}],"stream":false}' \
  -w "\nTime: %{time_total}s\n"
```

Observed results:

- One test took about 28.8 seconds.
- A later test took about 1.2 seconds.

Interpretation:

- Ollama was not permanently down.
- The 28.8 second result likely reflected a temporarily busy or still-running Ollama runner.
- After the system settled, Ollama returned to a healthy response time.

Conclusion:

There was no persistent hardware overload at the time of the later checks.

---

### 3. Host resource check

Commands used:

```bash
uptime
nproc
free -h
vmstat 1 5
top -bn1 -o %CPU | head -20
ps -ef | grep -E "python3|ollama|docker compose|worker" | grep -v grep
```

Findings:

- 4 CPUs
- load average around 1.5–2.1
- enough RAM available
- swap usage low
- no active coding worker
- no broad CPU saturation

Conclusion:

The host was not globally overloaded during the later diagnosis.

---

### 4. Import path and strict-mode check

The host Python environment initially could not import `vigilex` because `PYTHONPATH` was not set.

Correct setup:

```bash
cd /home/cap/vigilex

export PYTHONPATH=/home/cap/vigilex/src
export OLLAMA_BASE_URL=http://localhost:11434
export VIGILEX_STRICT=true
export MODEL_VERSION=debug_qfg_strict_20260519
```

Import check:

```bash
python3 - <<'PY'
import os
import vigilex.coding.llm_coder as lc
import vigilex.workers.coding as wc

print("llm_coder:", lc.__file__)
print("worker:", wc.__file__)
print("STRICT_MODE llm:", lc.STRICT_MODE)
print("STRICT_MODE worker:", wc.STRICT_MODE)
print("OLLAMA_BASE_URL:", os.environ.get("OLLAMA_BASE_URL"))
PY
```

Confirmed:

```text
llm_coder: /home/cap/vigilex/src/vigilex/coding/llm_coder.py
worker: /home/cap/vigilex/src/vigilex/workers/coding.py
STRICT_MODE llm: True
STRICT_MODE worker: True
OLLAMA_BASE_URL: http://localhost:11434
```

Conclusion:

The controlled debug run used the correct current source files and strict mode.

---

### 5. Host-mode environment issue: `DATABASE_URL`

The first strict run failed with:

```text
RuntimeError: DATABASE_URL environment variable not set.
```

Conclusion:

This was an environment-drift issue between Docker mode and host mode.

Docker Compose injects `DATABASE_URL` automatically for containers. A host/tmux worker does not receive that variable unless it is explicitly exported.

Correct host setup:

```bash
cd /home/cap/vigilex

set -a
source .env
set +a

export PYTHONPATH=/home/cap/vigilex/src
export DATABASE_URL="postgresql://${POSTGRES_USER:-vigilex}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-vigilex}"
export OLLAMA_BASE_URL=http://localhost:11434
export VIGILEX_STRICT=true
export MODEL_VERSION=debug_qfg_strict_20260519
```

Decision:

A dedicated host environment loader should be added, for example:

```bash
source scripts/load_host_env.sh
```

This prevents future host-mode runs from silently differing from Docker-mode runs.

---

## Controlled strict debug run

Command:

```bash
python3 -m vigilex.workers.coding \
  --product-code QFG \
  --limit 5 \
  --batch-size 1 \
  --verbose
```

Observed:

- `GET /api/tags` returned HTTP 200.
- Each `POST /api/chat` returned HTTP 200.
- The worker completed 5 records.
- Strict mode did not abort.
- Throughput was around 1.6 records/min.
- Individual records took about 25–48 seconds.

Result table:

```text
mdr_report_key          pt_name                                                              crossencoder_score  llm_confidence  final_confidence
3004464228-2024-04813   Circumstance or information capable of leading to device use error    -6.960213           0.8             0.560284
3004464228-2024-04814   Vascular complication associated with device                          -6.226337           0.8             0.560592
3004464228-2024-04816   Blood glucose false positive                                          -1.180753           0.5             0.420475
3004464228-2024-04818   Vascular complication associated with device                          -6.226337           0.8             0.560592
3004464228-2024-04819   Blood glucose false positive                                          -0.790967           0.5             0.443588
```

Conclusion:

For these five records:

- LLM calls succeeded.
- HTTP status was 200.
- Strict mode did not catch any LLM failure.
- `llm_confidence = 0.5` and `0.8` were real LLM outputs, not exception fallback values.

---

## LZG distribution check

The 7,000+ LZG records were checked for exact `llm_confidence` values.

Observed distribution:

```text
llm_confidence |  n   |  pct
---------------+------+-------
0.5            | 4077 | 55.46
0.8            | 1955 | 26.60
0.0            |  737 | 10.03
0.2            |  238 |  3.24
0.9            |  199 |  2.71
0.1            |   36 |  0.49
0.3            |   31 |  0.42
1.0            |   25 |  0.34
0.99           |   14 |  0.19
```

Conclusion:

The coarse confidence pattern was already present in LZG.

Therefore, the QFG pattern was not a new QFG-specific failure and not a return of the old fallback bug.

---

## Prompt finding

The current `SYSTEM_PROMPT` contains this instruction:

```text
Assign a confidence score from 0.0 to 1.0 (1.0 = perfect match, 0.5 = uncertain, <0.3 = flag for review)
```

This explains the observed distribution.

Conclusion:

The local LLM is using prompt-defined anchor values. `0.5` and `0.8` are not hidden fallback indicators. They are prompt-induced ordinal confidence outputs.

---

## Corrected diagnosis

Old interpretation:

```text
92% fallback
```

Corrected interpretation:

```text
The apparent fallback pattern was not a fallback pattern. It was a prompt-induced ordinal confidence pattern.
```

More precise statement:

```text
The local llama3.2:3b stage emits coarse confidence values, especially 0.5 and 0.8, under Prompt v1. These values are real LLM self-assessment outputs but should be treated as ordinal triage values, not calibrated probabilities.
```

---

## Methodological issue: final_confidence

Current formula:

```text
final_confidence = 0.3 * sigmoid(crossencoder_score) + 0.7 * llm_confidence
```

Problem:

- `crossencoder_score` is a raw relevance logit.
- `sigmoid(crossencoder_score)` maps it to 0–1, but this does not make it a calibrated probability.
- `llm_confidence` is not a calibrated probability either; it is an ordinal LLM self-assessment induced by the prompt.
- Therefore `final_confidence` is not a statistically valid probability.

Correct interpretation:

```text
final_confidence is a heuristic composite triage score, not a calibrated probability.
```

Recommended documentation wording:

```text
The score called final_confidence in v1 is not a calibrated probability. It is a weighted heuristic combining a sigmoid-normalized CrossEncoder relevance score with an ordinal LLM self-assessment emitted under Prompt v1. It is used only as a triage and review-priority score, not as a statistical confidence estimate.
```

---

## Decision: do not change the prompt now

Reason:

- More than 7,000 LZG records were already coded with Prompt v1.
- Changing the prompt now would break comparability between LZG and QFG.

Decision:

Do not change:

- `SYSTEM_PROMPT`
- confidence scale wording
- model (`llama3.2:3b`)
- temperature
- `num_predict`
- final score formula

Allowed changes:

- add trace/audit columns
- persist status information
- persist raw LLM response
- persist latency and backend
- improve logging

Not allowed for comparable runs:

- prompt changes
- confidence scale changes
- model changes
- formula changes
- parser reinterpretation that changes the stored semantic output

---

## Database trace columns

Trace columns were added to `processed.coding_results`.

Purpose:

Future records should explicitly store the coding path and not require reverse inference from `llm_confidence`.

Intended fields:

```text
coding_path
llm_backend
llm_status
fallback_reason
llm_latency_ms
llm_http_status
llm_raw_response
llm_parse_error
rationale
flagged
debug_meta
```

Target examples:

Success case:

```text
coding_path      = hybrid_ce_llm_success
llm_backend      = ollama:llama3.2:3b
llm_status       = success
fallback_reason  = NULL
llm_http_status  = 200
llm_latency_ms   = 32000
llm_confidence   = 0.8
```

Fallback case:

```text
coding_path      = hybrid_ce_llm_fallback
llm_backend      = ollama:llama3.2:3b
llm_status       = timeout
fallback_reason  = llm_timeout
llm_http_status  = NULL or 500
llm_latency_ms   = 60000
llm_confidence   = NULL
```

---

## Code patch status

A patch script was used to modify:

- `src/vigilex/coding/llm_coder.py`
- `src/vigilex/workers/coding.py`

The patch goal was only observability:

- capture LLM HTTP status
- capture LLM latency
- capture raw response
- capture parse error
- capture rationale
- persist trace fields into `processed.coding_results`

Important status:

The patch introduced a syntax error in `llm_coder.py`:

```text
SyntaxError: unterminated f-string literal
```

Cause:

A multi-line f-string was written with real line breaks inside string quotes instead of using `\n`.

The affected block is the `STRICT MODE: LLM coding failed` print block.

Required fix:

Replace the broken `print(...)` block with:

```python
                print(
                    f"STRICT MODE: LLM coding failed -- aborting worker.\n"
                    f"  top CE candidate: {top.pt_name} (code {top.pt_code}, "
                    f"score {top.crossencoder_score:.2f})\n"
                    f"  status: {llm_status}\n"
                    f"  fallback_reason: {fallback_reason}\n"
                    f"  http_status: {http_status}\n"
                    f"  latency_ms: {latency_ms}\n"
                    f"  error: {type(e).__name__}: {e}"
                )
                raise
```

After editing:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/cap/vigilex/src python3 -m py_compile \
  src/vigilex/coding/llm_coder.py \
  src/vigilex/workers/coding.py
```

If pycache permission errors occur:

```bash
sudo rm -rf src/vigilex/coding/__pycache__ src/vigilex/workers/__pycache__
```

or use:

```bash
PYTHONDONTWRITEBYTECODE=1 ...
```

---

## Environment decision

Host-worker runs must not be started manually without a standardized environment setup.

Recommended script:

```bash
# scripts/load_host_env.sh
#!/usr/bin/env bash
set -a
source /home/cap/vigilex/.env
set +a

export PYTHONPATH=/home/cap/vigilex/src
export DATABASE_URL="postgresql://${POSTGRES_USER:-vigilex}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-vigilex}"
export OLLAMA_BASE_URL=http://localhost:11434
export VIGILEX_STRICT=true
```

Future host-worker pattern:

```bash
cd /home/cap/vigilex
source scripts/load_host_env.sh
export MODEL_VERSION=trace_v1_qfg_20260519

python3 -m vigilex.workers.coding \
  --product-code QFG \
  --limit 5 \
  --batch-size 1 \
  --verbose
```

---

## Next steps

### Immediate

1. Fix the broken f-string in `llm_coder.py`.
2. Run `py_compile` on both changed files.
3. If syntax passes, run a 5-record trace test with `MODEL_VERSION=trace_v1_qfg_20260519`.
4. Query the new trace columns.

Query:

```sql
SELECT
  mdr_report_key,
  pt_name,
  llm_confidence,
  final_confidence,
  coding_path,
  llm_backend,
  llm_status,
  fallback_reason,
  llm_http_status,
  llm_latency_ms,
  flagged,
  LEFT(rationale, 80) AS rationale_short
FROM processed.coding_results
WHERE model_version = 'trace_v1_qfg_20260519'
ORDER BY coded_at;
```

### After trace test succeeds

1. Run a small QFG extension batch, e.g. 20–100 records.
2. Do not change prompt/model/formula.
3. Use trace columns to verify:
   - success rate
   - timeout rate
   - parse error rate
   - latency distribution
4. Proceed to PRR/ROR.

### PRR/ROR guidance

PRR/ROR should primarily use:

```text
product_code
pt_code
counts
```

Not `final_confidence` as probability.

Recommended analyses:

1. all coded records with `pt_code IS NOT NULL`
2. only `llm_status = 'success'` for trace-enabled future records
3. sensitivity analysis by heuristic score threshold:
   - no threshold
   - `final_confidence >= 0.3`
   - `final_confidence >= 0.5`

---

## Final conclusion

The suspected QFG fallback explosion was not confirmed.

The actual finding is:

```text
Prompt v1 induces coarse ordinal LLM confidence values. This was already present in the LZG run and is also present in QFG. The values 0.5 and 0.8 are real LLM outputs under the current prompt, not fallback markers.
```

The main engineering gap is:

```text
The coding pipeline did not persist enough trace metadata to prove the execution path per record.
```

The current plan is therefore:

```text
Do not change the model or prompt. Add traceability. Treat final_confidence as a heuristic triage score. Continue PRR/ROR using PT-code counts, with optional sensitivity analyses.
```
