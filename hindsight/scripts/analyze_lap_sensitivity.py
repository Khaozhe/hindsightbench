#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls.

LAP threshold / sample sensitivity — zero-cost half of the reviewer pack
(ICLR_REVISION_PLAN.md P0-3, answering Q2/W3/W7). Everything recomputes from
the frozen per-sample LAP answers (outputs/bench/<model>/lap_probe_results.jsonl)
and the frozen R arms; nothing under outputs/bench/ is touched.

Three exercises, per model (all 17 dirs holding a lap_probe_results.jsonl —
the 15 leaderboard rows plus the two BM2a serving arms qwen3.6-27b-awq/bf16):

1. Cutoff re-sweep at theta in {0.05, 0.1, 0.2}. Frozen rule replicated
   verbatim (analyze_bench_row.py:149-150): empirical cutoff = last month,
   over all 258 probe dates, with LAP > theta (strict). theta=0.1 must
   reproduce the frozen cutoffs exactly (row jsons; BM2A_RESULTS.json for
   the two serving arms).

2. Rep-jackknife on the cutoff. Full tier (20 reps/date): 200 deterministic
   10-of-20 rep-ID subsets; reduced tier (10 reps/date: llama3.2:1b/3b,
   qwen3-30b-a3b-fp8dyn, qwen3.6-27b-awq/bf16): 200 5-of-10 subsets the same
   way. Seed = first 8 bytes of sha256(model dir name), so every subset is
   reproducible from this script alone. Notes: (a) duplicate (date,rep)
   lines exist (deepseek 139, kimi 39, awq 32, bf16 5 — resume artifacts);
   the frozen metric pools ALL lines per date, so a selected rep ID brings
   all of its lines. (b) For the reduced tier C(10,5)=252 < 200 draws is
   sampling over the subset space, not unique enumeration — repeats are
   expected and harmless. (c) qwen3.6-27b-awq is missing 2 of 2,580 lines
   (2007-08-15, 2016-02-15 have 9); a date drops out of a subset's LAP dict
   only if it has zero selected lines (never happens here).

3. delta under jackknifed LAP. The delta regression (analyze_bench_row.py:
   152-190) consumes the CONTINUOUS per-date LAP — theta never enters it, so
   the theta sweep cannot change delta by construction; it is computed once
   and stated as theta-invariant rather than re-reported three times.
   Per jackknife subset the full frozen pipeline reruns (same R-arm signals,
   same realized directions from spx_target_new.parquet, same HAC maxlags=6
   OLS) with the identifiability gates applied verbatim per subset:
   n(sig)>30 and var(LAP)>1e-4, else the column renders "-".
   Significance label: sig+/sig- at |t|>=1.96, ns otherwise, "-" if gated.

   Reconciliation nuance found while writing this (2026-07-21): the frozen
   gpt-5.5 row json (2026-07-03) PREDATES the 2026-07-07 variance gate and
   was never regenerated. Recomputing today: all 152 of its sig dates have
   LAP == 1.0 exactly (var == 0; the one low-LAP pre date, 2024-11-15 at
   0.75, drops out via net==0), so the interaction column is PERFECTLY
   collinear with the signal column and the frozen delta=+0.0654 (t=2.96)
   is the pre-gate pinv least-norm artifact — same pathology that voided
   sonnet-5 (12.46) and mini (1.48), both of which this script reproduces
   bit-exactly via the same pre-gate path. Under the leaderboard's own gate
   the gpt-5.5 delta column renders "-". The BENCH_ROWS.md dagger-cross
   footnote ("identified off a few low-LAP dates") is empirically wrong:
   zero low-LAP dates sit in the estimation sample. Frozen floats are still
   reproduced to the last bit (pre-gate path), so the pipeline reconciles
   15/15 row jsons; the gate verdict for gpt-5.5 is flagged as a finding.

Headline for the paper (S3.3/S9): max cutoff displacement across
theta in [0.05,0.2], reported both over the 14 cutoff-valid models and over
all 17; the three hit~random rows (llama-3.1-8b, llama3.2:1b/3b) carry the
frozen dagger-dagger caveat (cutoff never collapses = artifact, BENCH_ROWS.md)
and are excluded from the primary number.

Writes outputs/review/lap_sensitivity.{json,md}. Usage:
  conda run -n macrochain python analyze_lap_sensitivity.py
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).parent))
from analyze_bench_row import BENCH, SPX_NEW, load_arm
from analyze_fm1 import all_dates

REVIEW = BENCH.parent / "review"
BM2A = BENCH.parent / "BM2A_RESULTS.json"
THETAS = (0.05, 0.1, 0.2)
N_SUBSETS = 200
SIG_T = 1.96
# BENCH_ROWS.md dagger-dagger rows: hit rate ~ random -> "cutoff" never
# collapses and is an artifact; emp.cutoff is only defined when hit is
# significantly above random. Excluded from the primary headline.
CUTOFF_ARTIFACT = ("llama-3.1-8b", "llama3.2:1b", "llama3.2:3b")


def month_idx(ym: str) -> int:
    return int(ym[:4]) * 12 + int(ym[5:7])


def idx_month(i: int) -> str:
    y, m = divmod(i - 1, 12)
    return f"{y}-{m + 1:02d}"


def load_lap(model: str):
    """date -> rep -> [n_lines, n_updown]; duplicates pool (frozen behavior)."""
    per = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    f = BENCH / model / "lap_probe_results.jsonl"
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        cell = per[r["decision_date"]][r["rep"]]
        cell[0] += 1
        cell[1] += r["answer"] in ("up", "down")
    return {d: dict(reps) for d, reps in per.items()}


def lap_from(per: dict, rep_set=None) -> dict:
    out = {}
    for d, reps in per.items():
        n = ud = 0
        for rep, (c, u) in reps.items():
            if rep_set is None or rep in rep_set:
                n += c
                ud += u
        if n:
            out[d] = ud / n
    return out


def cutoff(lap: dict, theta: float):
    above = [d for d in sorted(lap) if lap[d] > theta]
    return above[-1][:7] if above else None


def delta_pipeline(lap: dict, R_pre: dict, real: dict, pre: list,
                   pregate: bool = False) -> dict:
    """Verbatim replication of analyze_bench_row.py:164-190 (delta only).

    pregate=True additionally reports the regression WITHOUT the 2026-07-07
    variance gate (n>30 only) — the code path that produced the 07-03-vintage
    frozen rows (gpt-5.5) and the later-voided sonnet-5/mini artifacts. Used
    for bit-exact reconciliation only, never for headline columns.
    """
    sig, hit, lap_v = [], [], []
    for d in pre:
        xs = R_pre.get(d, [])
        if not xs or real.get(d) is None or d not in lap:
            continue
        net = sum(1 if x == "+" else -1 for x in xs)
        if net == 0:
            continue
        s = 1.0 if net > 0 else -1.0
        sig.append(s)
        hit.append(int(s == real[d]))
        lap_v.append(lap[d])

    def _ols():
        X = pd.DataFrame({"signal": sig, "lap": lap_v})
        X["inter"] = X.signal * X.lap
        ols = sm.OLS(np.array(hit, float), sm.add_constant(X)).fit(
            cov_type="HAC", cov_kwds={"maxlags": 6})
        return float(ols.params["inter"]), float(ols.tvalues["inter"])

    if not (len(sig) > 30 and float(np.var(lap_v)) > 1e-4):
        reason = "n<=30" if len(sig) <= 30 else "var(LAP)<=1e-4"
        out = {"delta": None, "t": None, "n": len(sig), "gate": reason}
        if pregate and len(sig) > 30:
            out["pregate_delta"], out["pregate_t"] = _ols()
        return out
    d_, t_ = _ols()
    return {"delta": d_, "t": t_, "n": len(sig), "gate": None}


def dstatus(d: dict) -> str:
    if d["delta"] is None:
        return "-"
    if abs(d["t"]) >= SIG_T:
        return "sig+" if d["delta"] > 0 else "sig-"
    return "ns"


def F(x, spec=".3f"):
    return "-" if x is None else f"{x:{spec}}"


def main() -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    models = sorted(p.parent.name for p in BENCH.glob("*/lap_probe_results.jsonl"))

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
    bm2a = json.loads(BM2A.read_text())["tiers"] if BM2A.exists() else {}

    out = {"meta": {
        "status": "POST-FREEZE EXPLORATORY (review-response, 2026-07-21); zero API calls",
        "thetas": list(THETAS), "n_subsets": N_SUBSETS,
        "seed_rule": "int.from_bytes(sha256(model_dir_name)[:8], 'big') -> np.random.default_rng",
        "cutoff_rule": "last month with LAP > theta over all 258 probe dates (analyze_bench_row.py:149-150)",
        "delta_gates": "n(sig)>30 and var(LAP)>1e-4, verbatim (analyze_bench_row.py:186)",
        "sig_rule": f"|t| >= {SIG_T}",
        "cutoff_artifact_rows": list(CUTOFF_ARTIFACT),
        "versions": {"numpy": np.__version__, "pandas": pd.__version__,
                     "statsmodels": sm.__version__ if hasattr(sm, "__version__")
                     else __import__("statsmodels").__version__},
    }, "models": {}}

    for model in models:
        per = load_lap(model)
        rep_ids = sorted({rep for reps in per.values() for rep in reps})
        n_lines = sum(c for reps in per.values() for c, _ in reps.values())
        tier = "full" if len(rep_ids) == 20 else "reduced"
        assert len(rep_ids) in (10, 20), (model, rep_ids)
        k = len(rep_ids) // 2

        lap_all = lap_from(per)
        cuts = {str(t): cutoff(lap_all, t) for t in THETAS}
        disp = {str(t): (month_idx(cuts[str(t)]) - month_idx(cuts["0.1"])
                         if cuts[str(t)] and cuts["0.1"] else None)
                for t in THETAS if t != 0.1}
        disp_vals = [abs(v) for v in disp.values() if v is not None]
        max_disp = max(disp_vals) if disp_vals else None

        # frozen anchors
        row_f = BENCH / model / f"{model.replace('/', '_')}_row.json"
        frozen_cut = frozen_delta = None
        frozen_src = None
        if row_f.exists():
            row = json.loads(row_f.read_text())
            frozen_cut = row["LAP"]["empirical_cutoff"]
            frozen_delta = row["delta_dissociation"]
            frozen_src = row_f.name
        elif model in bm2a:
            frozen_cut = bm2a[model]["metrics"]["empirical_cutoff"]
            frozen_src = "BM2A_RESULTS.json (no delta frozen there)"

        # delta at full reps (theta-invariant by construction: the pipeline
        # consumes continuous LAP; theta only exists in the cutoff rule)
        R_pre_all, _ = load_arm(BENCH / model, "R")
        R_pre = {d: v for d, v in R_pre_all.items() if d in set(pre)}
        d_full = delta_pipeline(lap_all, R_pre, real, pre, pregate=True)
        d_match = None
        if frozen_delta is not None:
            if frozen_delta["delta"] is None:
                d_match = {"exact": d_full["delta"] is None, "via": "both gated/None"}
            elif d_full["delta"] is not None:
                d_match = {"exact": d_full["delta"] == frozen_delta["delta"]
                           and d_full["t"] == frozen_delta["t"],
                           "via": "current-gate pipeline"}
            else:
                # frozen has a value but today's gate fires: frozen row predates
                # the 2026-07-07 variance gate -> reconcile via pre-gate path
                pg = d_full.get("pregate_delta")
                d_match = {"exact": pg == frozen_delta["delta"]
                           and d_full.get("pregate_t") == frozen_delta["t"],
                           "via": "PRE-GATE path (frozen row predates 07-07 gate; "
                                  "current gate renders '-')",
                           "gate_discrepancy": True}

        # jackknife
        seed = int.from_bytes(hashlib.sha256(model.encode()).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        jk_cuts, jk_deltas, jk_status = [], [], []
        # baseline = full-rep status under the CURRENT gates (for gpt-5.5 this
        # is "-", not the pre-gate frozen "sig+" — else every subset would
        # spuriously count as a change); frozen-row status kept alongside
        base_status = dstatus(d_full)
        frozen_row_status = None if frozen_delta is None else \
            dstatus({"delta": frozen_delta["delta"], "t": frozen_delta["t"]})
        for _ in range(N_SUBSETS):
            sub = set(rng.choice(rep_ids, size=k, replace=False).tolist())
            lap_s = lap_from(per, sub)
            jk_cuts.append(cutoff(lap_s, 0.1))
            ds = delta_pipeline(lap_s, R_pre, real, pre)
            jk_deltas.append(ds["delta"])
            jk_status.append(dstatus(ds))
        cut_idx = [month_idx(c) for c in jk_cuts if c is not None]
        defined = [x for x in jk_deltas if x is not None]
        jk = {
            "k_of_n": f"{k}-of-{len(rep_ids)}", "seed": seed,
            "cutoff_min": idx_month(min(cut_idx)) if cut_idx else None,
            "cutoff_median": idx_month(statistics.median_low(cut_idx)) if cut_idx else None,
            "cutoff_max": idx_month(max(cut_idx)) if cut_idx else None,
            "cutoff_span_months": max(cut_idx) - min(cut_idx) if cut_idx else None,
            "cutoff_none_count": sum(c is None for c in jk_cuts),
            "cutoff_agree_frozen_pct": 100.0 * sum(c == cuts["0.1"] for c in jk_cuts) / N_SUBSETS,
            "delta_defined_pct": 100.0 * len(defined) / N_SUBSETS,
            "delta_median": float(np.median(defined)) if defined else None,
            "status_baseline": base_status,
            "frozen_row_status": frozen_row_status,
            "status_change_pct": 100.0 * sum(s != base_status for s in jk_status) / N_SUBSETS,
            "status_counts": {s: jk_status.count(s) for s in sorted(set(jk_status))},
        }

        out["models"][model] = {
            "tier": tier, "n_lap_lines": n_lines, "n_rep_ids": len(rep_ids),
            "cutoff_by_theta": cuts, "displacement_months_vs_0.1": disp,
            "max_abs_displacement_months": max_disp,
            "frozen_cutoff": frozen_cut, "frozen_source": frozen_src,
            "cutoff_matches_frozen": (cuts["0.1"] == frozen_cut) if frozen_cut else None,
            "cutoff_artifact_flag": model in CUTOFF_ARTIFACT,
            "delta_full": d_full, "delta_frozen": frozen_delta,
            "delta_matches_frozen": d_match,
            "delta_theta_invariant": True,
            "jackknife": jk,
        }
        print(f"{model:24s} cut@.05/.1/.2 = {cuts['0.05']}/{cuts['0.1']}/{cuts['0.2']}"
              f"  frozen={frozen_cut} match={out['models'][model]['cutoff_matches_frozen']}"
              f"  jk_agree={jk['cutoff_agree_frozen_pct']:.1f}%"
              f"  delta={F(d_full['delta'])} (frozen {F(None if frozen_delta is None else frozen_delta['delta'])})")

    ms = out["models"]
    valid = [m for m in ms if not ms[m]["cutoff_artifact_flag"]]
    hl_valid = max(ms[m]["max_abs_displacement_months"] for m in valid)
    hl_all = max(ms[m]["max_abs_displacement_months"] for m in ms)
    argmax_valid = max(valid, key=lambda m: ms[m]["max_abs_displacement_months"])
    n_le1 = sum(1 for m in valid if ms[m]["max_abs_displacement_months"] <= 1)
    out["headline"] = {
        "max_abs_cutoff_displacement_months_cutoff_valid_models": hl_valid,
        "max_abs_cutoff_displacement_months_all_models": hl_all,
        "argmax_model": argmax_valid,
        "n_cutoff_valid_models": len(valid),
        "n_valid_models_within_1_month": n_le1,
        "statement": (f"Across theta in [0.05, 0.2] the empirical cutoff moves at most "
                      f"{hl_valid} month(s) on the {len(valid)} cutoff-valid models "
                      f"(driver: {argmax_valid}; {n_le1}/{len(valid)} move <= 1 month; "
                      f"{hl_all} across all 17 incl. the hit~random artifact rows)."),
        "reconciliation": {
            "cutoff_theta01_matches": sum(1 for m in ms if ms[m]["cutoff_matches_frozen"]),
            "cutoff_frozen_anchors": sum(1 for m in ms if ms[m]["frozen_cutoff"]),
            "delta_exact_matches": sum(1 for m in ms if ms[m]["delta_matches_frozen"]
                                       and ms[m]["delta_matches_frozen"]["exact"]),
            "delta_frozen_anchors": sum(1 for m in ms if ms[m]["delta_frozen"] is not None),
            "gate_discrepancy_rows": [m for m in ms if ms[m]["delta_matches_frozen"]
                                      and ms[m]["delta_matches_frozen"].get("gate_discrepancy")],
        },
    }

    (REVIEW / "lap_sensitivity.json").write_text(json.dumps(out, indent=2, default=float))

    # markdown
    L = ["# LAP threshold / sample sensitivity (P0-3, zero-cost half)", "",
         "POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls — ",
         "recomputed from frozen `outputs/bench/<model>/lap_probe_results.jsonl` + frozen R arms.",
         "Generated by `scripts/analyze_lap_sensitivity.py`; machine-readable twin `lap_sensitivity.json`.", "",
         f"**Headline: {out['headline']['statement']}**", "",
         "Cutoff rule (frozen, replicated verbatim): last month with LAP > theta over all 258",
         "probe dates. Jackknife: 200 deterministic rep-ID subsets per model (10-of-20 full",
         "tier, 5-of-10 reduced tier; seed = sha256(model)[:8]; for the reduced tier the 200",
         "draws sample the C(10,5)=252 subset space with repeats, by design). Duplicate",
         "(date,rep) lines from resume runs pool into their rep ID exactly as the frozen",
         "metric pools all lines.", "",
         "## Cutoff: theta sweep + rep-jackknife", "",
         "| model | tier | cut@0.05 | cut@0.1 | cut@0.2 | frozen | match | max disp (mo) | jk min/med/max | jk span | agree% |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        r = ms[m]
        jk = r["jackknife"]
        mark = {True: "yes", False: "**NO**", None: "n/a"}[r["cutoff_matches_frozen"]]
        art = "^(a)" if r["cutoff_artifact_flag"] else ""
        L.append(f"| {m}{art} | {r['tier']} | {r['cutoff_by_theta']['0.05']} | {r['cutoff_by_theta']['0.1']} "
                 f"| {r['cutoff_by_theta']['0.2']} | {r['frozen_cutoff'] or '-'} | {mark} "
                 f"| {r['max_abs_displacement_months']} "
                 f"| {jk['cutoff_min']}/{jk['cutoff_median']}/{jk['cutoff_max']} "
                 f"| {jk['cutoff_span_months']} | {jk['cutoff_agree_frozen_pct']:.0f}% |")
    L += ["",
          "^(a) hit rate ~ random (BENCH_ROWS.md dagger-dagger): the 'cutoff' never collapses and is an",
          "artifact; excluded from the primary headline (reported under the all-models variant).", "",
          "## delta under jackknifed LAP", "",
          "delta is theta-invariant **by construction**: the detection regression",
          "(analyze_bench_row.py:152-190) consumes the continuous per-date LAP; theta exists",
          "only in the cutoff rule (:149-150). It is therefore computed once (not re-reported",
          "per theta). Gates applied verbatim per subset: n(sig)>30 and var(LAP)>1e-4, '-' when gated.", "",
          "| model | delta full-rep (t, n) | frozen delta | bit-exact | jk median delta | jk defined% | baseline status | status change% |",
          "|---|---|---|---|---|---|---|---|"]
    for m in models:
        r = ms[m]
        d, fz, jk = r["delta_full"], r["delta_frozen"], r["jackknife"]
        d_s = "-" if d["delta"] is None else f"{d['delta']:+.4f} (t={d['t']:.2f}, n={d['n']})"
        if d["delta"] is None:
            d_s += f" [{d['gate']}]"
        fz_s = "n/a (no frozen delta)" if fz is None else \
            ("-" if fz["delta"] is None else f"{fz['delta']:+.4f}")
        mt = r["delta_matches_frozen"]
        if mt is None:
            mt_s = "n/a"
        elif not mt["exact"]:
            mt_s = "**NO**"
        elif mt.get("gate_discrepancy"):
            mt_s = "yes^(g) (pre-gate path)"
        else:
            mt_s = "yes"
        L.append(f"| {m} | {d_s} | {fz_s} | {mt_s} "
                 f"| {F(jk['delta_median'], '+.4f')} | {jk['delta_defined_pct']:.0f}% "
                 f"| {jk['status_baseline']} | {jk['status_change_pct']:.1f}% |")
    rec = out["headline"]["reconciliation"]
    gd = rec["gate_discrepancy_rows"]
    L += ["",
          "^(g) **Gate-discrepancy finding (2026-07-21)**: the frozen gpt-5.5 row json",
          "(2026-07-03) predates the 2026-07-07 delta identifiability gate and was never",
          "regenerated. Recomputed today, all 152 of its estimation dates carry LAP == 1.0",
          "exactly (var == 0; the single low-LAP pre date 2024-11-15 = 0.75 exits via",
          "net==0), so the frozen +0.0654 (t=2.96) is the pre-gate pinv artifact of a",
          "perfectly collinear regression — the same pathology that voided sonnet-5",
          "(pre-gate 12.4646, reproduced bit-exactly here) and mini (pre-gate 1.4819,",
          "ditto). Under the leaderboard's own gate the gpt-5.5 delta renders '-', and the",
          "BENCH_ROWS.md double-dagger footnote ('identified off a few low-LAP dates') is",
          "empirically wrong: zero low-LAP dates are in the estimation sample.",
          "",
          "## Reconciliation vs frozen artifacts",
          "",
          f"- theta=0.1 cutoff: {rec['cutoff_theta01_matches']}/{rec['cutoff_frozen_anchors']} frozen anchors reproduced "
          "(15 row jsons + 2 BM2a serving arms from BM2A_RESULTS.json).",
          f"- delta at full reps: {rec['delta_exact_matches']}/{rec['delta_frozen_anchors']} frozen row-json values reproduced "
          "bit-exactly (gated '-' rows reproducing as gated; "
          f"gate-discrepancy rows: {', '.join(gd) if gd else 'none'} — see ^(g)).",
          "- Known blind spots: jackknife subsets are sampled (not exhaustive); reduced-tier",
          "  agreement rates ride on 10 reps/date and are noisier by construction; the",
          "  theta grid is 3 points, not a continuum (P1 paid half covers sample-size);",
          "  the gate-discrepancy row means the frozen leaderboard's delta column for",
          "  gpt-5.5 needs an editorial decision (P0-5), not just this appendix table.", ""]
    (REVIEW / "lap_sensitivity.md").write_text("\n".join(L))
    print(f"\nwrote {REVIEW / 'lap_sensitivity.json'}")
    print(f"wrote {REVIEW / 'lap_sensitivity.md'}")
    print(out["headline"]["statement"])


if __name__ == "__main__":
    main()
