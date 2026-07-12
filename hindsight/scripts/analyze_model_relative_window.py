#!/usr/bin/env python
"""Model-relative placebo window (audit TODO item 1; generalized 2026-07-06).

For models whose empirical cutoff (last month with LAP>0.1) falls inside the
calendar placebo window (>=2025-02), the calendar "post-cutoff" dates are
partially pre-cutoff for that model. This recomputes P1 = D-M bearish-share
gap on the model-relative window (strictly after the empirical cutoff month)
and freezes both numbers next to the model's row file.

Usage: analyze_model_relative_window.py --model <bench-dir-name> [--write]
Verification: --model deepseek-v4-flash must reproduce the 2026-07 frozen
values (cal +0.0551 n=17, rel +0.0398 n=11, cutoff 2025-07).
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from hindsight_paths import REPO
BENCH = REPO / "hindsight/outputs/bench"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--write", action="store_true",
                    help="freeze JSON next to the row file (default: print only)")
    args = ap.parse_args()
    root = BENCH / args.model

    def load_arm(arm):
        by_date = defaultdict(list)
        for node in (root / arm).glob("rep*/*"):
            f = node / "01_sketches_valid.json"
            if f.exists():
                for s in json.loads(f.read_text()):
                    if s.get("direction") in ("+", "-"):
                        by_date[node.name].append(s["direction"])
        return by_date

    lap_cnt = defaultdict(lambda: defaultdict(int))
    for l in (root / "lap_probe_results.jsonl").read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            lap_cnt[r["decision_date"]][r["answer"]] += 1
    LAP = {d: (c["up"] + c["down"]) / sum(c.values()) for d, c in lap_cnt.items() if sum(c.values())}
    cutoff = max(d[:7] for d in LAP if LAP[d] > 0.1)

    D, M = load_arm("D"), load_arm("M")

    def share(bd, sel):
        xs = [x for d in sel for x in bd.get(d, [])]
        return sum(1 for x in xs if x == "-") / len(xs) if xs else float("nan")

    post_dates = sorted(d for d in set(D) | set(M) if d >= "2025-02")
    cal = list(post_dates)
    rel = [d for d in post_dates if d[:7] > cutoff]

    row_f = root / f"{args.model.replace('/', '_')}_row.json"
    e2_ref = None
    if row_f.exists():
        e2 = json.loads(row_f.read_text()).get("E2_date_trigger") or {}
        e2_ref = round(e2["est"], 3) if e2.get("est") is not None else None

    out = {
        "model": args.model,
        "empirical_cutoff_LAP": cutoff,
        "calendar_window": {"dates": cal, "n": len(cal),
                            "D_minus_M": share(D, cal) - share(M, cal)},
        "model_relative_window": {"dates": rel, "n": len(rel),
                                  "D_minus_M": share(D, rel) - share(M, rel)},
        "pre_cutoff_E2_reference": e2_ref,
    }
    if args.write:
        (root / "model_relative_placebo.json").write_text(json.dumps(out, indent=2))
    slim = {k: (dict(v, dates=f"<{v['n']} dates>") if isinstance(v, dict) and "dates" in v else v)
            for k, v in out.items()}
    print(json.dumps(slim, indent=2))


if __name__ == "__main__":
    main()
