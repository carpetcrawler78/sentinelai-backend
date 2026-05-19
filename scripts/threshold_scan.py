"""
Threshold scanner -- findet Signal-Schwellenwerte fuer Demo.

Konfiguration: config/signals.yml (Thresholds, Datumsbereiche)

Ausfuehren auf Hetzner:
    source scripts/load_host_env.sh
    python3 scripts/threshold_scan.py

Ausfuehren lokal:
    $env:PYTHONPATH = "src"
    $env:DATABASE_URL = "postgresql://vigilex:PW@localhost:5432/vigilex"
    python scripts/threshold_scan.py
"""

import os
import yaml
from datetime import date
from vigilex.signals.prr_ror import run_prr_ror

# -- Config laden -------------------------------------------------------------
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "signals.yml")

with open(CONFIG_PATH) as f:
    cfg = yaml.safe_load(f)["prr_ror"]

DATE_FROM  = date.fromisoformat(cfg["date_from"])
DATE_TO    = date.fromisoformat(cfg["date_to"])
THRESHOLDS = cfg["thresholds"]
TOP_N      = cfg.get("top_n", 10)

# -- Analyse ------------------------------------------------------------------
results = run_prr_ror(
    start_date=DATE_FROM,
    end_date=DATE_TO,
    thresholds=THRESHOLDS,
    dry_run=True,
)

print(f"Total results:              {len(results)}")
print(f"Results with PRR not None:  {sum(1 for r in results if r['prr'] is not None)}")
print(f"Active thresholds:          {THRESHOLDS}")

top = sorted(
    [r for r in results if r["prr"] is not None and r.get("is_signal")],
    key=lambda x: x["prr"],
    reverse=True,
)[:TOP_N]

print(f"\nTop {TOP_N} Signals (PRR >= {THRESHOLDS['prr_min']}, "
      f"n >= {THRESHOLDS['min_reports_focal']}, "
      f"CI_lower >= {THRESHOLDS['ci_lower_min']}):")
print(f"{'pt_name':<45} {'n_focal':>8} {'prr':>8} {'ror':>8} {'ci_lower':>10}")
print("-" * 85)
for r in top:
    print(
        f"{r['pt_name'][:44]:<45} "
        f"{r['n_reports_focal']:>8} "
        f"{r['prr']:>8.2f} "
        f"{r['ror']:>8.2f} "
        f"{r['prr_lower_ci']:>10.2f}"
    )
