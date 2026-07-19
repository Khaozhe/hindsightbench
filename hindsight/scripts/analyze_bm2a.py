#!/usr/bin/env python
"""BM-2a analysis: quantization sensitivity verdict (prereg d672e12d).

Computes E2/E3 (B=10k seed 2026), LAP answer rate + hit rate, empirical cutoff,
and VALID for each new tier, then applies the preregistered descriptive
stability rule against the FROZEN FP8 row:
  stable(E2/E3) = each tier's point estimate inside the FP8 row's 95% CI AND
                  the FP8 point estimate inside the tier's 95% CI
  stable(cutoff) = within +/-1 month of the FP8 row's (2024-11), defined only
                   where LAP hit rate exceeds chance (inherited gate)

Morning flow: rsync the tier dirs back first —
  rsync -az -e "ssh -p $PORT" root@$GPU_HOST:\
    "$HINDSIGHT_ROOT/hindsight/outputs/bench/qwen3.6-27b-bf16 \
     $HINDSIGHT_ROOT/hindsight/outputs/bench/qwen3.6-27b-awq" \
    hindsight/outputs/bench/
Usage: python analyze_bm2a.py [--tiers qwen3.6-27b-bf16 qwen3.6-27b-awq]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map, gap, CRISIS, CALM_YEARS
from analyze_bench_row import boot_diff, load_arm, BENCH, SPX_NEW

FROZEN_FP8 = "qwen3.6-27b-fp8"
PREREG = "BM2a_prereg_quant_sensitivity.md d672e12d"


def months_apart(a: str, b: str) -> int:
    ay, am = int(a[:4]), int(a[5:7])
    by, bm = int(b[:4]), int(b[5:7])
    return abs((ay - by) * 12 + (am - bm))


def tier_metrics(model: str) -> dict:
    root = BENCH / model
    rng = np.random.default_rng(2026)
    pre = all_dates()
    calm = [d for d in pre if d[:4] in CALM_YEARS]
    fmap = fake_map(pre)

    arms, stats = {}, {}
    for a in ("R", "D", "M", "W"):
        arms[a], stats[a] = load_arm(root, a)

    def pre_only(bd):
        return {d: v for d, v in bd.items() if d in set(pre)}

    D_pre, M_pre = pre_only(arms["D"]), pre_only(arms["M"])
    e2 = gap(D_pre, CRISIS, calm) - gap(M_pre, CRISIS, calm)
    e2_ci = boot_diff(lambda c, q: gap(D_pre, c, q), lambda c, q: gap(M_pre, c, q),
                      CRISIS, calm, rng)
    W_pre = pre_only(arms["W"])
    w_fake = defaultdict(list)
    for td, xs in W_pre.items():
        w_fake[fmap[td]].extend(xs)
    e3 = gap(w_fake, CRISIS, calm) - gap(W_pre, CRISIS, calm)
    e3_ci = boot_diff(lambda c, q: gap(w_fake, c, q), lambda c, q: gap(W_pre, c, q),
                      CRISIS, calm, rng)

    # LAP (10 reps/date in BM-2a): answer rate, hit rate, empirical cutoff
    lap_f = root / "lap_probe_results.jsonl"
    lap_rows = [json.loads(l) for l in lap_f.read_text().splitlines() if l.strip()] \
        if lap_f.exists() else []
    cnt = defaultdict(lambda: defaultdict(int))
    for r in lap_rows:
        cnt[r["decision_date"]][r["answer"]] += 1
    LAP, UD = {}, {}
    for d, c in cnt.items():
        n = sum(c.values())
        LAP[d] = (c["up"] + c["down"]) / n if n else np.nan
        UD[d] = (c["up"] - c["down"]) / n if n else np.nan
    above = [d for d in sorted(LAP) if LAP[d] > 0.1]
    cutoff = above[-1][:7] if above else None
    lap_pre = float(np.mean([LAP[d] for d in pre if d in LAP])) if LAP else None

    spx = pd.read_parquet(SPX_NEW).reset_index()
    dcol = "date" if "date" in spx.columns else spx.columns[0]
    spx[dcol] = pd.to_datetime(spx[dcol])
    spx = spx.sort_values(dcol)

    def realized(d):
        after = spx[spx[dcol] >= pd.Timestamp(d)]
        if not len(after) or pd.isna(after.iloc[0]["forward_return_20d"]):
            return None
        return 1.0 if after.iloc[0]["forward_return_20d"] >= 0 else -1.0
    hit_n = hit_k = 0
    for d in pre:
        r = realized(d)
        if d in UD and abs(UD[d]) > 1e-9 and r is not None:
            hit_n += 1
            hit_k += int(np.sign(UD[d]) == r)
    hit = hit_k / hit_n if hit_n else None

    total_valid = sum(s["valid"] for s in stats.values())
    total_cells = sum(s["cells"] for s in stats.values())
    return {
        "E2": {"est": float(e2), "ci95": list(e2_ci)},
        "E3": {"est": float(e3), "ci95": list(e3_ci)},
        "LAP_pre_mean": lap_pre, "LAP_hit_rate": hit, "empirical_cutoff": cutoff,
        "VALID": total_valid / (total_cells * 8) if total_cells else None,
        "cells": total_cells,
        "parse_err_cells": sum(s["parse_err"] for s in stats.values()),
    }


def inside(x: float, ci: list) -> bool:
    return ci[0] <= x <= ci[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", nargs="+",
                    default=["qwen3.6-27b-bf16", "qwen3.6-27b-awq"])
    args = ap.parse_args()

    frozen = json.loads((BENCH / FROZEN_FP8 / f"{FROZEN_FP8}_row.json").read_text())
    f_e2, f_e2ci = frozen["E2_date_trigger"]["est"], frozen["E2_date_trigger"]["ci95"]
    f_e3, f_e3ci = frozen["E3_transplant"]["est"], frozen["E3_transplant"]["ci95"]
    f_cut = frozen["LAP"]["empirical_cutoff"]

    out = {"prereg": PREREG, "frozen_reference": {
        "model": FROZEN_FP8, "E2": {"est": f_e2, "ci95": f_e2ci},
        "E3": {"est": f_e3, "ci95": f_e3ci}, "cutoff": f_cut}, "tiers": {}}

    for tier in args.tiers:
        m = tier_metrics(tier)
        hit_defined = m["LAP_hit_rate"] is not None and m["LAP_hit_rate"] > 0.60
        verdict = {
            "E2_stable": inside(m["E2"]["est"], f_e2ci) and inside(f_e2, m["E2"]["ci95"]),
            "E3_stable": inside(m["E3"]["est"], f_e3ci) and inside(f_e3, m["E3"]["ci95"]),
            "cutoff_defined": hit_defined,
            "cutoff_stable": (hit_defined and m["empirical_cutoff"] is not None
                              and months_apart(m["empirical_cutoff"], f_cut) <= 1),
        }
        verdict["STABLE"] = all([verdict["E2_stable"], verdict["E3_stable"],
                                 verdict["cutoff_stable"]])
        out["tiers"][tier] = {"metrics": m, "verdict": verdict}
        print(f"{tier}: E2 {m['E2']['est']*100:+.1f}pp {[round(x*100,1) for x in m['E2']['ci95']]} "
              f"E3 {m['E3']['est']*100:+.1f}pp {[round(x*100,1) for x in m['E3']['ci95']]} "
              f"cutoff {m['empirical_cutoff']} (hit {m['LAP_hit_rate']}) VALID {m['VALID']:.0%} "
              f"-> {'STABLE' if verdict['STABLE'] else 'UNSTABLE: ' + str(verdict)}")

    (BENCH.parent / "BM2A_RESULTS.json").write_text(json.dumps(out, indent=2, default=float))
    print("written:", BENCH.parent / "BM2A_RESULTS.json")


if __name__ == "__main__":
    main()
