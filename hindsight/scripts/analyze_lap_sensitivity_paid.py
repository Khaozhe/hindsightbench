#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls.

BM-1c LAP sensitivity — PAID half (prereg BM1c_lap_sensitivity_addendum.md,
sha256 48d4d968..., s4 analysis plan, frozen before the run). Consumes the
already-collected arms under outputs/review/lap_sensitivity_runs/ plus the
frozen outputs/bench/<model>/lap_probe_results.jsonl; nothing under
outputs/bench/ is touched and no API is called.

Frozen s4 matrix, per model in {gpt-5.4-mini, claude-haiku-4-5,
deepseek-v4-flash}: sample size {20, 40} x temperature {0.3, 0.7, 1.0} x
theta {0.05, 0.1, 0.2} -> empirical cutoff month + signed displacement
(months) vs the frozen reference cell (20 samples / t=1.0 / theta=0.1).
Structural note (stated, not hidden): the addendum's arm design (s1) collected
20 reps at t=0.3/0.7 and +20 reps only at t=1.0, so the 40-sample axis exists
only at t=1.0; the 2x3 sample-x-temperature face has two structurally empty
cells per theta, rendered "n/a (not collected)". Every collected cell is
emitted — no selective reporting.

delta is recomputed under each variant LAP series via
analyze_lap_sensitivity.delta_pipeline — the verbatim replication of
analyze_bench_row.py:164-190 with the identifiability gates n(sig)>30 and
var(LAP)>1e-4 (analyze_bench_row.py:181-186); gated cells render "-".
delta is theta-invariant by construction (the regression consumes the
continuous per-date LAP; theta exists only in the cutoff rule), so it is
computed once per (sample, temperature) series.

Sanity anchor (hard assert): the (20, t=1.0, theta=0.1) cell recomputed from
the frozen lap_probe_results.jsonl must equal the frozen row-json
LAP.empirical_cutoff for all three models, and the same-series delta must
reconcile with the frozen row-json delta_dissociation (bit-exact where the
frozen row is un-gated; both-gated where gated).

Interpretation boundary (pre-declared in the addendum, s4): the temperature
arms change the sampling distribution itself; cutoff movement with temperature
is not a protocol defect but further evidence that an audit contract must pin
the sampling parameters (paper s7).

Writes outputs/review/lap_sensitivity_paid.{json,md}. Usage:
  conda run -n macrochain python analyze_lap_sensitivity_paid.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from analyze_bench_row import BENCH, SPX_NEW, load_arm
from analyze_fm1 import all_dates
from analyze_lap_sensitivity import (month_idx, load_lap, lap_from, cutoff,
                                     delta_pipeline, dstatus, F)

RUNS = BENCH.parent / "review/lap_sensitivity_runs"
REVIEW = BENCH.parent / "review"
PREREG = "BM1c_lap_sensitivity_addendum.md sha256 48d4d968..."
MODELS = ("gpt-5.4-mini", "claude-haiku-4-5", "deepseek-v4-flash")
THETAS = (0.05, 0.1, 0.2)
TEMPS = ("0.3", "0.7", "1.0")
ARM_FILES = {"ext": "lap_ext_t1.0_reps20-39.jsonl",
             "0.3": "lap_t0.3_probe.jsonl",
             "0.7": "lap_t0.7_probe.jsonl"}


def load_runs(model: str, arm: str):
    """Same shape as analyze_lap_sensitivity.load_lap: date -> rep -> [n, n_updown]."""
    per = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    counts = defaultdict(int)
    for line in (RUNS / model / ARM_FILES[arm]).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        cell = per[r["decision_date"]][r["rep"]]
        cell[0] += 1
        cell[1] += r["answer"] in ("up", "down")
        counts[r["answer"]] += 1
    return {d: dict(reps) for d, reps in per.items()}, dict(counts)


def merge(a: dict, b: dict) -> dict:
    """Pool two per-date/rep count structures (frozen reps 0-19 + ext 20-39;
    duplicate rep IDs pool additively, matching the frozen all-lines metric)."""
    out = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for src in (a, b):
        for d, reps in src.items():
            for rep, (c, u) in reps.items():
                cell = out[d][rep]
                cell[0] += c
                cell[1] += u
    return {d: dict(reps) for d, reps in out.items()}


def main() -> None:
    pre = all_dates()
    spx = pd.read_parquet(SPX_NEW).reset_index()
    dcol = "date" if "date" in spx.columns else spx.columns[0]
    spx[dcol] = pd.to_datetime(spx[dcol])
    spx = spx.sort_values(dcol)

    def realized(d):
        after = spx[spx[dcol] >= pd.Timestamp(d)]
        if not len(after) or pd.isna(after.iloc[0]["forward_return_20d"]):
            return None
        return 1.0 if after.iloc[0]["forward_return_20d"] >= 0 else -1.0

    real = {d: realized(d) for d in pre}

    out = {"meta": {
        "status": "POST-FREEZE EXPLORATORY (review-response, 2026-07-21); zero API calls",
        "prereg": PREREG,
        "matrix": "sample {20,40} x temperature {0.3,0.7,1.0} x theta {0.05,0.1,0.2}",
        "structural_gap": "40-sample axis exists only at t=1.0 (addendum s1 arm "
                          "design: alternate temperatures collected 20 reps)",
        "reference_cell": "20 samples / t=1.0 / theta=0.1 (frozen row-json cutoff)",
        "cutoff_rule": "last month with LAP > theta over all 258 probe dates "
                       "(analyze_bench_row.py:149-150, replicated via "
                       "analyze_lap_sensitivity.cutoff)",
        "delta_gates": "n(sig)>30 and var(LAP)>1e-4, verbatim "
                       "(analyze_bench_row.py:181-186 via delta_pipeline)",
        "interpretation_boundary": "temperature arms change the sampling "
            "distribution itself; cutoff movement with temperature is not a "
            "protocol defect but evidence that the audit contract must pin "
            "sampling parameters (addendum s4, pre-declared)",
    }, "models": {}}

    anchor_fail = []
    for model in MODELS:
        frozen = load_lap(model)                      # 20 reps, t=1.0 (frozen file)
        ext, cnt_ext = load_runs(model, "ext")        # +20 reps, t=1.0
        t03, cnt_03 = load_runs(model, "0.3")
        t07, cnt_07 = load_runs(model, "0.7")
        series = {  # (sample, temp) -> per-date structure; None = not collected
            ("20", "1.0"): frozen,
            ("40", "1.0"): merge(frozen, ext),
            ("20", "0.3"): t03,
            ("20", "0.7"): t07,
            ("40", "0.3"): None,
            ("40", "0.7"): None,
        }
        row_f = BENCH / model / f"{model.replace('/', '_')}_row.json"
        row = json.loads(row_f.read_text())
        frozen_cut = row["LAP"]["empirical_cutoff"]
        frozen_delta = row["delta_dissociation"]

        R_pre_all, _ = load_arm(BENCH / model, "R")
        R_pre = {d: v for d, v in R_pre_all.items() if d in set(pre)}

        cells = {}
        deltas = {}
        ref = None
        for (n_s, t_s), per in series.items():
            key = f"n{n_s}_t{t_s}"
            if per is None:
                cells[key] = {"collected": False,
                              "note": "n/a (not collected: addendum s1 design)"}
                deltas[key] = {"collected": False}
                continue
            lap = lap_from(per)
            n_lines = sum(c for reps in per.values() for c, _ in reps.values())
            cuts = {str(th): cutoff(lap, th) for th in THETAS}
            cells[key] = {"collected": True, "n_lines": n_lines,
                          "n_dates": len(lap), "cutoff_by_theta": cuts}
            deltas[key] = {"collected": True,
                           **delta_pipeline(lap, R_pre, real, pre)}
            deltas[key]["status"] = dstatus(deltas[key])
            if (n_s, t_s) == ("20", "1.0"):
                ref = cuts["0.1"]

        # anchor: reference cell == frozen row json
        anchor_cut_ok = (ref == frozen_cut)
        d_ref = deltas["n20_t1.0"]
        if frozen_delta["delta"] is None:
            anchor_delta = {"ok": d_ref["delta"] is None,
                            "via": "both gated/None"}
        else:
            anchor_delta = {"ok": d_ref["delta"] == frozen_delta["delta"]
                            and d_ref["t"] == frozen_delta["t"],
                            "via": "bit-exact"}
        if not (anchor_cut_ok and anchor_delta["ok"]):
            anchor_fail.append(model)

        # displacements vs the frozen reference cell
        for key, c in cells.items():
            if not c["collected"]:
                continue
            c["displacement_months_vs_ref"] = {
                th: (month_idx(c["cutoff_by_theta"][th]) - month_idx(ref)
                     if c["cutoff_by_theta"][th] and ref else None)
                for th in c["cutoff_by_theta"]}

        disp_all = [abs(v) for c in cells.values() if c.get("collected")
                    for v in c["displacement_months_vs_ref"].values()
                    if v is not None]
        temp_disp = [abs(c["displacement_months_vs_ref"]["0.1"])
                     for k, c in cells.items()
                     if c.get("collected") and k in ("n20_t0.3", "n20_t0.7")
                     and c["displacement_months_vs_ref"]["0.1"] is not None]
        out["models"][model] = {
            "answer_counts": {"ext_t1.0": cnt_ext, "t0.3": cnt_03, "t0.7": cnt_07},
            "frozen_cutoff": frozen_cut, "frozen_delta": frozen_delta,
            "anchor_cutoff_ok": anchor_cut_ok, "anchor_delta": anchor_delta,
            "cells": cells, "delta_by_series": deltas,
            "max_abs_displacement_all_cells": max(disp_all) if disp_all else 0,
            "max_abs_temp_displacement_theta01": max(temp_disp) if temp_disp else None,
        }
        print(f"{model}: anchor cutoff {'OK' if anchor_cut_ok else 'FAIL'} "
              f"({ref} vs frozen {frozen_cut}), anchor delta "
              f"{'OK' if anchor_delta['ok'] else 'FAIL'} ({anchor_delta['via']}); "
              f"max|disp| all cells = {out['models'][model]['max_abs_displacement_all_cells']} mo")

    ms = out["models"]
    out["headline"] = {
        "anchors": "3/3 reference cells reproduce the frozen row-json cutoff "
                   "and reconcile delta" if not anchor_fail else
                   f"ANCHOR FAILURES: {anchor_fail}",
        "max_abs_displacement_any_cell_months":
            max(m["max_abs_displacement_all_cells"] for m in ms.values()),
        "max_abs_temperature_displacement_theta01_months":
            max(m["max_abs_temp_displacement_theta01"] for m in ms.values()
                if m["max_abs_temp_displacement_theta01"] is not None),
    }
    assert not anchor_fail, f"sanity anchors failed: {anchor_fail}"

    (REVIEW / "lap_sensitivity_paid.json").write_text(
        json.dumps(out, indent=2, default=float))

    # ---------------------------------------------------------------- md ---
    L = ["# BM-1c LAP sensitivity — paid matrix (s4 of the frozen addendum)", "",
         "POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls in this",
         "script — it consumes `outputs/review/lap_sensitivity_runs/` (46,440 collected",
         "calls, addendum sha256 48d4d968...) plus the frozen",
         "`outputs/bench/<model>/lap_probe_results.jsonl`. Generated by",
         "`scripts/analyze_lap_sensitivity_paid.py`; machine twin `lap_sensitivity_paid.json`.", "",
         "**Structural note (frozen arm design, s1)**: alternate temperatures were",
         "collected at 20 reps only; the +20-rep extension exists only at t=1.0. The",
         "sample-size {20, 40} axis therefore applies only at t=1.0, and the",
         "(40, t=0.3)/(40, t=0.7) cells are structurally empty — rendered n/a, not",
         "omitted. Every collected cell is reported; no selection.", "",
         "Cutoff rule (frozen, replicated verbatim): last month with LAP > theta over all",
         "258 probe dates. Displacement = signed months vs the frozen reference cell",
         "(20 samples / t=1.0 / theta=0.1). delta gates n(sig)>30, var(LAP)>1e-4 verbatim;",
         "'-' where gated. delta is theta-invariant by construction (regression consumes",
         "continuous LAP; theta exists only in the cutoff rule).", "",
         f"**Sanity anchors: {out['headline']['anchors']}** (gpt-5.4-mini 2025-09 /",
         "claude-haiku-4-5 2024-10 / deepseek-v4-flash 2025-07; delta reconciliation:",
         "haiku and deepseek bit-exact, gpt-5.4-mini both-gated).", "",
         "## Cutoff matrix (cell: cutoff month; parenthesis: displacement vs ref, months)", "",
         "| model | samples | temp | theta=0.05 | theta=0.1 | theta=0.2 |",
         "|---|---|---|---|---|---|"]

    def cell_s(c, th):
        cut = c["cutoff_by_theta"][th]
        d = c["displacement_months_vs_ref"][th]
        if cut is None:
            return "never>theta"
        return f"{cut} ({d:+d})" if d is not None else f"{cut}"

    order = [("20", "1.0"), ("40", "1.0"), ("20", "0.3"), ("40", "0.3"),
             ("20", "0.7"), ("40", "0.7")]
    for model in MODELS:
        r = ms[model]
        for n_s, t_s in order:
            c = r["cells"][f"n{n_s}_t{t_s}"]
            ref_mark = " (ref)" if (n_s, t_s) == ("20", "1.0") else ""
            if not c["collected"]:
                L.append(f"| {model} | {n_s} | {t_s}{ref_mark} | n/a | n/a | n/a |")
            else:
                L.append(f"| {model} | {n_s} | {t_s}{ref_mark} | "
                         f"{cell_s(c, '0.05')} | {cell_s(c, '0.1')} | {cell_s(c, '0.2')} |")
    L += ["",
          "n/a = structurally empty (not collected; s1 arm design). (ref) row's",
          "theta=0.1 cell is the frozen reference (displacement +0 by construction).", "",
          "## delta under each variant LAP series (theta-invariant)", "",
          "| model | samples | temp | delta | t | n | status |",
          "|---|---|---|---|---|---|---|"]
    for model in MODELS:
        r = ms[model]
        for n_s, t_s in order:
            d = r["delta_by_series"][f"n{n_s}_t{t_s}"]
            if not d["collected"]:
                L.append(f"| {model} | {n_s} | {t_s} | n/a | n/a | n/a | n/a |")
            elif d["delta"] is None:
                L.append(f"| {model} | {n_s} | {t_s} | - | - | {d['n']} | "
                         f"- [{d['gate']}] |")
            else:
                L.append(f"| {model} | {n_s} | {t_s} | {d['delta']:+.4f} | "
                         f"{d['t']:.2f} | {d['n']} | {d['status']} |")
    hl = out["headline"]
    L += ["",
          "## Reading (pre-declared interpretation boundary)", "",
          f"- Max |cutoff displacement| across every collected cell: "
          f"**{hl['max_abs_displacement_any_cell_months']} month(s)**.",
          f"- Max |cutoff displacement| attributable to temperature alone "
          f"(n=20, theta=0.1, t=0.3/0.7 vs ref): "
          f"**{hl['max_abs_temperature_displacement_theta01_months']} month(s)**.",
          "- Per the addendum (s4, frozen before data): the temperature arms change the",
          "  sampling distribution itself, so cutoff movement with temperature is not a",
          "  protocol defect; it is further evidence for the paper's s7 claim that an",
          "  audit contract must pin the sampling parameters. Sample-size (20 vs 40 at",
          "  t=1.0) and theta rows speak to estimator stability at the frozen regime.", ""]
    (REVIEW / "lap_sensitivity_paid.md").write_text("\n".join(L))
    print(f"wrote {REVIEW / 'lap_sensitivity_paid.json'}")
    print(f"wrote {REVIEW / 'lap_sensitivity_paid.md'}")


if __name__ == "__main__":
    main()
