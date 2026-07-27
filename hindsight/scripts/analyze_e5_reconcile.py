#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (2026-07-24, Kimi review response).

E5 reconciliation for paper 1 (06_exp3_recall.tex line 21).

Questions answered from frozen outputs (READ-ONLY: outputs/fm1/):
  1. Exact exclusion rule producing n=186 in "R-M majority acc = +0.0699,
     CI95 [+0.0000,+0.1398] (n=186)" (FM1_RESULTS.md line 29).
  2. Population/metric of the 77.8/63.6/74.3/72.7 subgroup numbers
     (fm1_metrics.json E5_accuracy_windows): unpaired per-arm date-level
     majority accuracy on the 11 ex-ante CRISIS dates and the 36 calm-year
     dates (2013/2014/2017), each arm keeping only its own non-tied dates.
  3. Metric-consistent (paired) subgroup decomposition of the +7.0pp headline:
     crisis / calm / other partition of the 186 paired dates, with exact
     weighted-sum check.

Writes ONLY: outputs/review/e5_reconcile.json
Run: conda run --no-capture-output -n macrochain python analyze_e5_reconcile.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_fm1 import (  # noqa: E402
    CRISIS, CALM_YEARS, B, SEED, accuracy, all_dates, build_covariates, load_arm,
)
from hindsight_paths import REPO  # noqa: E402

OUT_DIR = REPO / "hindsight/outputs/review"
OUT_JSON = OUT_DIR / "e5_reconcile.json"
METRICS = REPO / "hindsight/outputs/fm1/fm1_metrics.json"


def majority(xs: list[str]) -> float | None:
    net = sum(1 if x == "+" else -1 for x in xs)
    if net == 0:
        return None
    return 1.0 if net > 0 else -1.0


def main() -> None:
    dates = all_dates()                      # 240 decision dates
    calm = [d for d in dates if d[:4] in CALM_YEARS]
    cov = build_covariates(dates)
    arms = {a: load_arm("gemini-2.5-flash", a) for a in ("R", "M")}

    # --- per-date state ------------------------------------------------
    nan_real = [d for d in dates if np.isnan(cov.loc[d, "fwd_ret"])]
    mv = {a: {d: majority(arms[a].get(d, [])) for d in dates} for a in ("R", "M")}
    ties = {a: sorted(d for d in dates if mv[a][d] is None) for a in ("R", "M")}
    tie_overlap = sorted(set(ties["R"]) & set(ties["M"]))

    # paired set: realized direction defined AND strict majority in BOTH arms
    paired = [d for d in dates
              if d not in nan_real and mv["R"][d] is not None and mv["M"][d] is not None]

    def hits(a: str, ds: list[str]) -> np.ndarray:
        return np.array([float(mv[a][d] == cov.loc[d, "realized_dir"]) for d in ds])

    hr, hm = hits("R", paired), hits("M", paired)
    delta = hr - hm
    est = float(delta.mean())

    # paired date-level bootstrap CI (same B/seed convention as analyze_fm1)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(paired), size=(B, len(paired)))
    boots = delta[idx].mean(axis=1)
    ci_boot = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    se = float(delta.std(ddof=1) / np.sqrt(len(delta)))
    ci_normal = [est - 1.96 * se, est + 1.96 * se]

    # --- reproduce the frozen unpaired subgroup numbers ----------------
    frozen = json.loads(METRICS.read_text())
    unpaired_repro = {a: {"crisis": accuracy(arms[a], cov, CRISIS),
                          "calm": accuracy(arms[a], cov, calm)} for a in ("R", "M")}
    frozen_match = all(
        abs(unpaired_repro[a][w]["majority_acc"]
            - frozen["E5_accuracy_windows"][a][w]["majority_acc"]) < 1e-12
        and unpaired_repro[a][w]["n_majority"]
        == frozen["E5_accuracy_windows"][a][w]["n_majority"]
        for a in ("R", "M") for w in ("crisis", "calm"))

    # --- paired (metric-consistent) subgroup decomposition -------------
    part = {
        "crisis": [d for d in paired if d in CRISIS],
        "calm": [d for d in paired if d in calm],
        "other": [d for d in paired if d not in CRISIS and d not in calm],
    }
    sub = {}
    for name, ds in part.items():
        h1, h0 = hits("R", ds), hits("M", ds)
        sub[name] = {
            "n_paired": len(ds),
            "acc_R": float(h1.mean()) if len(ds) else None,
            "acc_M": float(h0.mean()) if len(ds) else None,
            "diff_pp": float((h1 - h0).mean() * 100) if len(ds) else None,
            "weight": len(ds) / len(paired),
        }
    weighted_sum_pp = sum(s["diff_pp"] * s["weight"] for s in sub.values())

    out = {
        "provenance": {
            "sketch_source": "outputs/fm1/gemini-2.5-flash/{R,M}/rep*/<date>/01_sketches_valid.json via analyze_fm1.load_arm",
            "realized_dir": "macrochain/data/processed/spx_target.parquet forward_return_20d >= 0 via analyze_fm1.build_covariates",
            "frozen_reference": "outputs/fm1/fm1_metrics.json E5_accuracy_windows; FM1_RESULTS.md line 29",
            "bootstrap": {"B": B, "seed": SEED, "convention": "paired date-level resample of the 186 dates"},
        },
        "n186_rule": {
            "n_dates_total": len(dates),
            "n_realized_nan_dropped": len(nan_real),
            "nan_dates": nan_real,
            "n_R_majority_ties": len(ties["R"]),
            "n_M_majority_ties": len(ties["M"]),
            "n_tie_overlap": len(tie_overlap),
            "n_union_dropped": len(set(ties["R"]) | set(ties["M"]) | set(nan_real)),
            "n_paired": len(paired),
        },
        "headline_paired": {
            "acc_R": float(hr.mean()), "acc_M": float(hm.mean()),
            "diff": est, "net_extra_correct_R": int(delta.sum()),
            "ci95_bootstrap_percentile": ci_boot,
            "ci95_normal_approx": ci_normal,
            "frozen_claim": {"diff": 0.0699, "ci95": [0.0000, 0.1398], "n": 186},
        },
        "unpaired_subgroups_reproduced": unpaired_repro,
        "unpaired_matches_frozen_json": frozen_match,
        "paired_subgroups": sub,
        "weighted_sum_check": {
            "weighted_sum_pp": weighted_sum_pp,
            "headline_pp": est * 100,
            "exact": abs(weighted_sum_pp - est * 100) < 1e-9,
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
