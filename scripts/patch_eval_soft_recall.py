"""
patch_eval_soft_recall.py
Adds soft_recall_at_5 and soft_recall_at_10 to eval_golden_set.py.

Changes:
  1. eval loop: add acceptable_pt_codes to each result record
  2. summarize(): add soft_recall_at_5, soft_recall_at_10 metrics

Run once: python3 scripts/patch_eval_soft_recall.py
Idempotent: skips if markers already present.
"""
from pathlib import Path

TARGET = Path("scripts/eval_golden_set.py")

# ---------------------------------------------------------------------------
# Patch 1: add acceptable_pt_codes to rec dict in eval loop
# ---------------------------------------------------------------------------
OLD_REC = '''\
                rec = {
                    "mdr_report_key":    mdr_key,
                    "expected_pt_code":  expected_code,
                    "expected_pt_name":  expected_name,
                    "stage1_top10_codes": stage1_codes[:10],
                    "stage2_top5_codes":  stage2_codes,
                    "difficulty":        case["difficulty"],
                    "product_code":      case["product_code"],
                    "llm_pt_code":       None,
                }'''

NEW_REC = '''\
                rec = {
                    "mdr_report_key":    mdr_key,
                    "expected_pt_code":  expected_code,
                    "expected_pt_name":  expected_name,
                    "stage1_top10_codes": stage1_codes[:10],
                    "stage2_top5_codes":  stage2_codes,
                    "difficulty":        case["difficulty"],
                    "product_code":      case["product_code"],
                    "llm_pt_code":       None,
                    # acceptable_pt_codes: case-specific plausible alternatives
                    # (empty set for cases without the field)
                    "acceptable_pt_codes": set(case.get("acceptable_pt_codes", [])),
                }'''

# ---------------------------------------------------------------------------
# Patch 2: add soft recall metrics to summarize()
# Insert after recall_at_10 line
# ---------------------------------------------------------------------------
OLD_RECALL = '''\
    recall_at_5  = avg([int(r["expected_pt_code"] in r["stage2_top5_codes"]) for r in results])
    recall_at_10 = avg([int(r["expected_pt_code"] in r["stage1_top10_codes"]) for r in results])'''

NEW_RECALL = '''\
    recall_at_5  = avg([int(r["expected_pt_code"] in r["stage2_top5_codes"]) for r in results])
    recall_at_10 = avg([int(r["expected_pt_code"] in r["stage1_top10_codes"]) for r in results])

    def soft_hit(r, codes_field):
        """Hit if expected PT or any acceptable PT is in the candidate list."""
        acceptable = r.get("acceptable_pt_codes", set())
        codes = set(r[codes_field])
        return int(r["expected_pt_code"] in codes or bool(codes & acceptable))

    soft_recall_at_5  = avg([soft_hit(r, "stage2_top5_codes")  for r in results])
    soft_recall_at_10 = avg([soft_hit(r, "stage1_top10_codes") for r in results])'''

# ---------------------------------------------------------------------------
# Patch 3: add soft metrics to the returned metrics dict
# ---------------------------------------------------------------------------
OLD_METRICS = '''\
    metrics = {
        "recall_at_5":     round(recall_at_5,  4),
        "recall_at_10":    round(recall_at_10, 4),
        "p_at_1_reranker": round(p_at_1_re,    4),
        "mrr":             round(mrr,           4),
        "n_evaluated":     n,
    }'''

NEW_METRICS = '''\
    metrics = {
        "recall_at_5":       round(recall_at_5,       4),
        "soft_recall_at_5":  round(soft_recall_at_5,  4),
        "recall_at_10":      round(recall_at_10,      4),
        "soft_recall_at_10": round(soft_recall_at_10, 4),
        "p_at_1_reranker":   round(p_at_1_re,         4),
        "mrr":               round(mrr,                4),
        "n_evaluated":       n,
    }'''


def apply(text, old, new, label):
    if old not in text:
        if new in text:
            print(f"  {label}: already patched, skipping.")
        else:
            print(f"  {label}: ERROR -- pattern not found. Check indentation.")
        return text
    result = text.replace(old, new, 1)
    print(f"  {label}: OK")
    return result


def main():
    content = TARGET.read_text()
    content = apply(content, OLD_REC,     NEW_REC,     "Patch 1 (rec dict)")
    content = apply(content, OLD_RECALL,  NEW_RECALL,  "Patch 2 (soft recall compute)")
    content = apply(content, OLD_METRICS, NEW_METRICS, "Patch 3 (metrics dict)")
    TARGET.write_text(content)
    print(f"Written: {TARGET}")


if __name__ == "__main__":
    main()
