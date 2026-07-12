#!/usr/bin/env python
"""BM-2b analysis: base-vs-instruct verdicts (prereg 51e03b53).

Stage 1 (GO/KILL): instruct-chat row -> GO iff E2 95% CI excludes 0.
Stage 2: three-condition contrast; the contrast of record is
base-2shot vs instruct-2shot (identical prompt bytes). Preregistered readings:
  (i)   both trigger, CIs overlap        -> corpus-borne
  (ii)  instruct-2shot triggers, base CI includes 0 -> post-training-installed
  (iii) base VALID < 50%                 -> unmeasurable, no inference
  (iv)  both exclude 0, CIs disjoint     -> dose reading
Control: instruct-chat vs instruct-2shot disagreement beyond CIs -> prompting-
regime caveat attaches to all Stage-2 inference.

Morning flow: rsync condition dirs back first —
  rsync -az -e "ssh -p $PORT" root@$GPU_HOST:\
    "$HINDSIGHT_ROOT/hindsight/outputs/bench/qwen3-30b-a3b-fp8dyn \
     $HINDSIGHT_ROOT/hindsight/outputs/bench/qwen3-30b-a3b-2shot \
     $HINDSIGHT_ROOT/hindsight/outputs/bench/qwen3-30b-a3b-base-2shot" \
    hindsight/outputs/bench/
Usage:
  python analyze_bm2b.py --stage 1
  python analyze_bm2b.py --stage 2
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map, gap, CRISIS, CALM_YEARS
from analyze_bench_row import boot_diff, load_arm, BENCH

INSTRUCT_CHAT = "qwen3-30b-a3b-fp8dyn"
INSTRUCT_2SHOT = "qwen3-30b-a3b-2shot"
BASE_2SHOT = "qwen3-30b-a3b-base-2shot"
PREREG = "BM2b_prereg_base_vs_instruct.md 51e03b53"
VALID_GATE = 0.50


def condition_metrics(model: str) -> dict:
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

    D_pre, M_pre, W_pre = (pre_only(arms[a]) for a in ("D", "M", "W"))
    e2 = gap(D_pre, CRISIS, calm) - gap(M_pre, CRISIS, calm)
    e2_ci = boot_diff(lambda c, q: gap(D_pre, c, q), lambda c, q: gap(M_pre, c, q),
                      CRISIS, calm, rng)
    w_fake = defaultdict(list)
    for td, xs in W_pre.items():
        w_fake[fmap[td]].extend(xs)
    e3 = gap(w_fake, CRISIS, calm) - gap(W_pre, CRISIS, calm)
    e3_ci = boot_diff(lambda c, q: gap(w_fake, c, q), lambda c, q: gap(W_pre, c, q),
                      CRISIS, calm, rng)
    total_valid = sum(s["valid"] for s in stats.values())
    total_cells = sum(s["cells"] for s in stats.values())
    return {
        "E2": {"est": float(e2), "ci95": list(e2_ci)},
        "E3": {"est": float(e3), "ci95": list(e3_ci)},
        "VALID": total_valid / (total_cells * 8) if total_cells else 0.0,
        "cells": total_cells,
        "parse_err_cells": sum(s["parse_err"] for s in stats.values()),
    }


def excludes_zero(ci: list) -> bool:
    return not (ci[0] <= 0.0 <= ci[1])


def overlap(a: list, b: list) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def fmt(m: dict) -> str:
    return (f"E2 {m['E2']['est']*100:+.1f}pp [{m['E2']['ci95'][0]*100:.1f},"
            f"{m['E2']['ci95'][1]*100:.1f}] | E3 {m['E3']['est']*100:+.1f}pp "
            f"[{m['E3']['ci95'][0]*100:.1f},{m['E3']['ci95'][1]*100:.1f}] | "
            f"VALID {m['VALID']:.0%} ({m['parse_err_cells']} perr cells)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, choices=[1, 2], required=True)
    args = ap.parse_args()

    if args.stage == 1:
        m = condition_metrics(INSTRUCT_CHAT)
        go = excludes_zero(m["E2"]["ci95"]) and m["VALID"] >= VALID_GATE
        verdict = "GO" if go else "KILL"
        out = {"prereg": PREREG, "stage": 1, "condition": INSTRUCT_CHAT,
               "metrics": m, "verdict": verdict,
               "rule": "GO iff E2 95% CI excludes 0 (and VALID >= 50%)"}
        print(f"{INSTRUCT_CHAT}: {fmt(m)}")
        print(f"STAGE-1 VERDICT: {verdict}" + ("" if go else
              " (Qwen3-generation boundary datum; Stage 2 cancelled)"))
        (BENCH.parent / "BM2B_STAGE1.json").write_text(json.dumps(out, indent=2, default=float))
        return

    conds = {}
    for c in (INSTRUCT_CHAT, INSTRUCT_2SHOT, BASE_2SHOT):
        conds[c] = condition_metrics(c)
        print(f"{c}: {fmt(conds[c])}")

    base, ins2 = conds[BASE_2SHOT], conds[INSTRUCT_2SHOT]
    if base["VALID"] < VALID_GATE:
        reading = ("(iii) base-2shot unmeasurable (VALID "
                   f"{base['VALID']:.0%} < 50%): compliance failure, no inference")
    else:
        b_trig = excludes_zero(base["E2"]["ci95"])
        i_trig = excludes_zero(ins2["E2"]["ci95"])
        ci_over = overlap(base["E2"]["ci95"], ins2["E2"]["ci95"])
        if b_trig and i_trig and ci_over:
            reading = "(i) both trigger, CIs overlap: reflex is CORPUS-BORNE"
        elif i_trig and not b_trig:
            reading = "(ii) instruct triggers, base does not: reflex INSTALLED BY POST-TRAINING"
        elif b_trig and i_trig and not ci_over:
            reading = "(iv) both trigger, magnitudes differ beyond CIs: dose reading (corpus seeds, post-training amplifies)"
        else:
            reading = ("unclassified by prereg table (neither triggers or only base): "
                       "report as measured")
    regime_ok = overlap(conds[INSTRUCT_CHAT]["E2"]["ci95"], ins2["E2"]["ci95"])
    caveat = (None if regime_ok else
              "prompting-regime control FAILED: instruct-chat vs instruct-2shot "
              "disagree beyond CIs; caveat attaches to all Stage-2 inference")

    out = {"prereg": PREREG, "stage": 2, "conditions": conds,
           "contrast_of_record": f"{BASE_2SHOT} vs {INSTRUCT_2SHOT}",
           "reading": reading, "regime_control_ok": regime_ok, "caveat": caveat}
    (BENCH.parent / "BM2B_STAGE2.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"\nSTAGE-2 READING: {reading}")
    if caveat:
        print(f"CAVEAT: {caveat}")


if __name__ == "__main__":
    main()
