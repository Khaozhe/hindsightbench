#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls.

Serving-stability checker (plan item P0-6, artifact-repo tool for Q7).

Given the SAME weights served under two configurations (precision /
quantization / kernel stack), decide whether a leaderboard row is portable
across them, using only stored arm outputs (or precomputed row jsons).
No model is ever called; everything is recomputed from frozen files.

Inputs (each of --model-a / --model-b):
  * an arms directory  (e.g. hindsight/outputs/bench/qwen3.6-27b-fp8)
    containing D/ M/ W/ rep*/<date>/01_sketches_valid.json — the metric and
    its bootstrap CI are recomputed exactly as in analyze_bench_row.py
    (B=10,000, seed 2026, E2 CI drawn before E3 CI, so numbers match the
    frozen leaderboard / BM-2a analysis bit-for-bit); or
  * a row json (analyze_bench_row *_row.json schema with E2_date_trigger /
    E3_transplant, or the BM2A_RESULTS.json {"E2": {est, ci95}} schema).

VERDICT RULE (calibrated so that it reproduces the published BM-2a
verdicts on the stored qwen3.6-27b fp8/bf16/awq data; the containment
clause is the BM2a preregistered descriptive stability rule, prereg
d672e12d):
  1. UNSTABLE      if the two 95% bootstrap CIs are disjoint;
  2. UNSTABLE      if mutual point-in-CI containment fails, i.e. either
                   point estimate falls outside the other config's CI
                   (CIs may still marginally overlap — this is what fires
                   for FP8-vs-BF16, where [10.8, 28.5] and [-2.3, +13.4]
                   share a sliver but neither point is contained);
  3. UNDERPOWERED  if (1)-(2) do not fire and either CI spans zero with
                   width > 20pp — too noisy to certify anything;
  4. STABLE        if |Δ| < half the pooled CI width, where pooled width
                   = mean of the two CI widths;
  5. UNDERPOWERED  otherwise (containment holds but the point gap is
                   large relative to pooled precision — add reps).

MINIMAL SWEEP (printed after every verdict): before trusting a row
served under a non-reference config, run at least the D and M arms (the
E2 ingredients) under (i) the config you intend to publish and (ii) one
reference precision, pass both through this checker, and only pool or
compare rows whose verdict is STABLE. BM-2a shows the check is not
optional: BF16 serving of an FP8-referenced checkpoint moved E2 by
-13.7pp (verdict flip), while AWQ-INT4 stayed within CI.

Usage:
  python check_serving_stability.py \
      --model-a hindsight/outputs/bench/qwen3.6-27b-fp8 \
      --model-b hindsight/outputs/bench/qwen3.6-27b-bf16 [--metric E2]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map, gap, CRISIS, CALM_YEARS
from analyze_bench_row import boot_diff

SEED = 2026
UNDERPOWERED_WIDTH = 0.20  # 20pp
ROW_KEYS = {"E2": ("E2", "E2_date_trigger"), "E3": ("E3", "E3_transplant")}


def load_arm_pooled(root: Path, arm: str) -> tuple[dict, int]:
    """Pool all reps: date -> list of directions. Follows symlinks
    (os.walk followlinks=True): bench model dirs may resolve through
    symlinks, where a plain glob/find silently yields 0 files."""
    by_date = defaultdict(list)
    cells = 0
    for dirpath, _dirnames, filenames in os.walk(root / arm, followlinks=True):
        if "01_sketches_valid.json" not in filenames:
            continue
        cells += 1
        node = Path(dirpath)
        for s in json.loads((node / "01_sketches_valid.json").read_text()):
            if s.get("direction") in ("+", "-"):
                by_date[node.name].append(s["direction"])
    return by_date, cells


def metrics_from_arms(root: Path, metric: str) -> dict:
    """Recompute E2 (and E3 if asked) exactly as analyze_bench_row /
    analyze_bm2a: fresh rng(2026) per model, E2 CI consumes the first
    10k draw pairs, E3 CI the next — frozen numbers reproduce exactly."""
    rng = np.random.default_rng(SEED)
    pre = all_dates()
    pre_set = set(pre)
    calm = [d for d in pre if d[:4] in CALM_YEARS]

    D, n_d = load_arm_pooled(root, "D")
    M, n_m = load_arm_pooled(root, "M")
    D_pre = {d: v for d, v in D.items() if d in pre_set}
    M_pre = {d: v for d, v in M.items() if d in pre_set}
    e2 = gap(D_pre, CRISIS, calm) - gap(M_pre, CRISIS, calm)
    e2_ci = boot_diff(lambda c, q: gap(D_pre, c, q),
                      lambda c, q: gap(M_pre, c, q), CRISIS, calm, rng)
    out = {"E2": {"est": float(e2), "ci95": list(e2_ci)},
           "cells": {"D": n_d, "M": n_m}}
    if metric == "E3":
        W, n_w = load_arm_pooled(root, "W")
        W_pre = {d: v for d, v in W.items() if d in pre_set}
        fmap = fake_map(pre)
        w_fake = defaultdict(list)
        for td, xs in W_pre.items():
            w_fake[fmap[td]].extend(xs)
        e3 = gap(w_fake, CRISIS, calm) - gap(W_pre, CRISIS, calm)
        e3_ci = boot_diff(lambda c, q: gap(w_fake, c, q),
                          lambda c, q: gap(W_pre, c, q), CRISIS, calm, rng)
        out["E3"] = {"est": float(e3), "ci95": list(e3_ci)}
        out["cells"]["W"] = n_w
    return out


def load_config(path_str: str, metric: str) -> dict:
    """Returns {name, est, ci95, source}."""
    p = Path(path_str)
    if p.is_dir():
        m = metrics_from_arms(p, metric)[metric]
        return {"name": p.name, "est": m["est"], "ci95": m["ci95"],
                "source": f"recomputed from arms dir {p}"}
    d = json.loads(p.read_text())
    for k in ROW_KEYS[metric]:
        if k in d:
            return {"name": d.get("model", p.stem), "est": d[k]["est"],
                    "ci95": list(d[k]["ci95"]), "source": f"row json {p}"}
    raise SystemExit(f"{p}: no {'/'.join(ROW_KEYS[metric])} key found")


def decide(a: dict, b: dict) -> tuple[str, str]:
    lo_a, hi_a = a["ci95"]
    lo_b, hi_b = b["ci95"]
    if any(np.isnan(x) for x in (lo_a, hi_a, lo_b, hi_b)):
        return "UNDERPOWERED", "bootstrap CI not identified (<50% valid draws)"
    if hi_a < lo_b or hi_b < lo_a:
        return "UNSTABLE", "95% CIs are disjoint"
    if not (lo_b <= a["est"] <= hi_b and lo_a <= b["est"] <= hi_a):
        return ("UNSTABLE",
                "mutual point-in-CI containment fails (BM2a prereg rule): "
                "a point estimate lies outside the other config's CI")
    w_a, w_b = hi_a - lo_a, hi_b - lo_b
    if (lo_a < 0 < hi_a and w_a > UNDERPOWERED_WIDTH) or \
       (lo_b < 0 < hi_b and w_b > UNDERPOWERED_WIDTH):
        return "UNDERPOWERED", "a CI spans zero with width > 20pp"
    half_pooled = (w_a + w_b) / 4  # half of the mean CI width
    delta = abs(a["est"] - b["est"])
    if delta < half_pooled:
        return ("STABLE",
                f"CIs overlap, containment holds, |Delta| {delta*100:.1f}pp "
                f"< half pooled CI width {half_pooled*100:.1f}pp")
    return ("UNDERPOWERED",
            f"containment holds but |Delta| {delta*100:.1f}pp >= half pooled "
            f"CI width {half_pooled*100:.1f}pp — add reps")


def fmt(c: dict) -> str:
    lo, hi = c["ci95"]
    return (f"  {c['name']:<24} {c['est']*100:+6.2f}pp  "
            f"CI95 [{lo*100:+.2f}, {hi*100:+.2f}]  "
            f"width {(hi-lo)*100:.2f}pp   ({c['source']})")


RECOMMEND = """\
Minimal sweep before trusting this row across serving configs:
  1. Run the D and M arms (the E2 ingredients; ~2 x n_dates x reps cells,
     no probes needed) under (i) the serving config you will publish and
     (ii) one reference precision of the same weights.
  2. Run this checker on the pair. STABLE -> the row is portable across
     the two configs; report the config alongside the row anyway.
     UNSTABLE -> report per-config rows; do not average or substitute.
     UNDERPOWERED -> double the reps on both configs and re-run.
  3. Never mix official-API rows with community-quantized checkpoints of
     'the same model' without this check: BM-2a measured a -13.7pp E2
     shift (verdict flip) from serving precision alone (FP8 -> BF16),
     while AWQ-INT4 stayed within CI of the FP8 reference."""


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-a", required=True,
                    help="arms dir or row json for serving config A")
    ap.add_argument("--model-b", required=True,
                    help="arms dir or row json for serving config B")
    ap.add_argument("--metric", default="E2", choices=("E2", "E3"))
    ap.add_argument("--json-out", default=None,
                    help="optional path for a machine-readable verdict json")
    args = ap.parse_args()

    a = load_config(args.model_a, args.metric)
    b = load_config(args.model_b, args.metric)
    v, why = decide(a, b)

    print(f"serving-stability check — metric {args.metric} "
          f"(B=10,000 bootstrap, seed {SEED})")
    print(fmt(a))
    print(fmt(b))
    print(f"  VERDICT: {v} — {why}")
    print()
    print(RECOMMEND)

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(
            {"metric": args.metric, "a": a, "b": b,
             "verdict": v, "reason": why}, indent=2, default=float))
        print(f"\njson written: {args.json_out}")


if __name__ == "__main__":
    main()
