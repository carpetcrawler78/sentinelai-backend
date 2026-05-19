"""
Threshold scanner -- findet Signal-Schwellenwerte fuer Demo.
Ausfuehren:
    $env:PYTHONPATH = "src"
    $env:DATABASE_URL = "postgresql://vigilex:PW@localhost:5432/vigilex"
    python scripts/threshold_scan.py
"""

from datetime import date
from vigilex.signals.prr_ror import run_prr_ror

DATE_FROM = date(2024, 1, 1)
DATE_TO   = date(2026, 5, 18)

combos = [
    (min_r, prr, ci)
    for min_r in [2, 3, 5]
    for prr   in [1.5, 2.0, 3.0]
    for ci    in [0.5, 1.0]
]

# Top 10 PRR-Werte anzeigen
results = run_prr_ror(
    start_date=DATE_FROM,
    end_date=DATE_TO,
    thresholds={"min_reports_focal": 2, "prr_min": 0.0, "ci_lower_min": 0.0},
    dry_run=True,
)

print(f"Total results: {len(results)}")
print(f"Results with PRR not None: {sum(1 for r in results if r['prr'] is not None)}")
if results:
    print(f"Sample row: {results[0]}")
top = sorted([r for r in results if r["prr"] is not None], key=lambda x: x["prr"], reverse=True)[:10]
print(f"\nTop 10 PRR-Werte:")
print(f"{'pt_name':<45} {'n_focal':>8} {'prr':>8} {'is_signal':>10}")
print("-" * 75)
for r in top:
    print(f"{r['pt_name'][:44]:<45} {r['n_reports_focal']:>8} {r['prr']:>8.2f} {str(r['is_signal']):>10}")
