#!/usr/bin/env python
"""HindsightBench per-model row: the six BM-1 metrics.

Usage: python analyze_bench_row.py --model deepseek-v4-flash
Appends a row to hindsight/outputs/bench/BENCH_ROWS.md and writes <model>_row.json.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map, gap, CRISIS, CALM_YEARS

def crisis_episode(d: str) -> str:
    """Which preregistered crisis episode a CRISIS date belongs to."""
    y = d[:4]
    return "GFC" if y in ("2008", "2009") else ("COVID" if y == "2020" else "2022")


def boot_diff(f1, f2, crisis, calm, rng, B=10_000):
    c_a, q_a = np.array(crisis), np.array(calm)
    out = np.empty(B)
    for i in range(B):
        cs = list(rng.choice(c_a, len(c_a), replace=True))
        qs = list(rng.choice(q_a, len(q_a), replace=True))
        out[i] = f1(cs, qs) - f2(cs, qs)
    valid = out[~np.isnan(out)]
    if len(valid) < B * 0.5:
        return (float('nan'), float('nan'))
    return (float(np.percentile(valid, 2.5)), float(np.percentile(valid, 97.5)))

from hindsight_paths import REPO
BENCH = REPO / "hindsight/outputs/bench"
SPX_NEW = REPO / "macrochain/data/processed/spx_target_new.parquet"
B, SEED = 10_000, 2026


def load_arm(root: Path, arm: str) -> tuple[dict, dict]:
    """returns (by_date directions, stats {valid, invalid, parse_err, cells})"""
    by_date = defaultdict(list)
    stats = {"valid": 0, "invalid": 0, "parse_err": 0, "cells": 0}
    for node in (root / arm).glob("rep*/*"):
        stats["cells"] += 1
        if (node / "99_parse_error.txt").exists():
            stats["parse_err"] += 1
        f = node / "01_sketches_valid.json"
        if not f.exists():
            continue
        meta_f = node / "03_run_meta.json"
        if meta_f.exists():
            m = json.loads(meta_f.read_text())
            stats["valid"] += m.get("valid_count", 0)
            stats["invalid"] += m.get("invalid_count", 0)
        for s in json.loads(f.read_text()):
            if s.get("direction") in ("+", "-"):
                by_date[node.name].append(s["direction"])
    return by_date, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    root = BENCH / args.model
    rng = np.random.default_rng(SEED)

    pre = all_dates()
    calm = [d for d in pre if d[:4] in CALM_YEARS]
    fmap = fake_map(pre)

    arms, stats = {}, {}
    for a in ("R", "D", "M", "W"):
        arms[a], stats[a] = load_arm(root, a)

    def pre_only(bd):
        return {d: v for d, v in bd.items() if d in set(pre)}

    def post_only(bd):
        return {d: v for d, v in bd.items() if d >= "2025-02"}

    # E2 (pre-cutoff), on the dates BOTH arms actually cover.
    #
    # E2 differences two arms. If D and M are scored over different date sets,
    # the contrast mixes the arm effect with the date composition -- the same
    # sample-mismatch defect that made E1 wrong on gemini-2.5-pro. Intersecting
    # is a strict no-op wherever both arms cover the preregistered windows,
    # which is 14 of the 15 rows (verified: bit-identical estimates and CIs).
    D_pre, M_pre = pre_only(arms["D"]), pre_only(arms["M"])
    shared = {d for d in D_pre if d in M_pre and D_pre[d] and M_pre[d]}
    crisis_s = [d for d in CRISIS if d in shared]
    calm_s = [d for d in calm if d in shared]
    g_d, g_m = gap(D_pre, crisis_s, calm_s), gap(M_pre, crisis_s, calm_s)
    e2 = g_d - g_m
    e2_ci = boot_diff(lambda c, q: gap(D_pre, c, q), lambda c, q: gap(M_pre, c, q),
                      crisis_s, calm_s, rng)

    # Identification gate: ATTRITION SELECTION, not episode count.
    #
    # An earlier version of this gate fired on "shared crisis window spans
    # fewer than two preregistered episodes" and grounded that in E.1. That
    # rationale was wrong and self-contradictory: E.1's own per-episode column
    # reports single-episode E2 fits as confirming evidence (COVID on 2 crisis
    # dates, fewer than the cell this gate suppresses), and the main text cites
    # them. Deliberately restricting a window on COMPLETE data is a subgroup
    # analysis and is fine; it is not what goes wrong here.
    #
    # What goes wrong here is that the data chose which dates survive. Under
    # partial schema compliance each arm loses a different set of dates, so the
    # surviving intersection is selected -- and on llama3.2:3b it is selected
    # on the outcome: D's bearish rate is .542 on the shared crisis dates vs
    # .333 on the ones only D kept, while M's is .125 shared vs .375 M-only;
    # both arms' calm rates are flat (.333/.338 and .403/.396). The intersection
    # is exactly where the gap is widest, which is why the estimate moves
    # +25.2pp -> +48.6pp with the window. Neither window is trustworthy.
    #
    # The rule is therefore coverage completeness, with no tuned threshold:
    # a contrast is identified only if BOTH sides cover the full preregistered
    # windows. On 13 rows this is a strict no-op (verified bit-identical).
    e2_episodes = sorted({crisis_episode(d) for d in crisis_s})
    e2_gated = len(crisis_s) < len(CRISIS) or len(calm_s) < len(calm)
    e2_coverage = {
        "n_crisis_shared": len(crisis_s), "n_calm_shared": len(calm_s),
        "n_crisis_pre": len(CRISIS), "n_calm_pre": len(calm),
        "episodes_shared": e2_episodes,
        "arms_cover_same_dates": (
            {d for d in D_pre if D_pre[d]} == {d for d in M_pre if M_pre[d]}),
    }

    # E3 (pre-cutoff W transplant), under the same parity rule as E2.
    #
    # Both sides come from the W arm, so it is tempting to call E3 immune to
    # sample mismatch. That is wrong whenever W's coverage is partial: the
    # fake-date re-key maps W's covered dates onto their *images* under fmap,
    # so the two keyings populate different crisis/calm slots. With full
    # coverage fmap is a permutation of the covered set and the two sides
    # coincide (true on 13 rows -- verified bit-identical). On the reduced
    # 65-date tier they do not: llama3.2:3b ends up differencing two disjoint
    # crisis windows (5 dates true side, 1 fake side, 0 shared).
    W_pre = pre_only(arms["W"])
    w_fake = defaultdict(list)
    for td, xs in W_pre.items():
        if xs:
            w_fake[fmap[td]].extend(xs)
    shared_w = {d for d in w_fake if d in W_pre and w_fake[d] and W_pre[d]}
    crisis_w = [d for d in CRISIS if d in shared_w]
    calm_w = [d for d in calm if d in shared_w]
    g_wf, g_wt = gap(w_fake, crisis_w, calm_w), gap(W_pre, crisis_w, calm_w)
    e3 = g_wf - g_wt
    e3_ci = boot_diff(lambda c, q: gap(w_fake, c, q), lambda c, q: gap(W_pre, c, q),
                      crisis_w, calm_w, rng) if len(crisis_w) >= 2 and len(calm_w) >= 2 \
        else (float("nan"), float("nan"))
    e3_episodes = sorted({crisis_episode(d) for d in crisis_w})
    e3_gated = len(crisis_w) < len(CRISIS) or len(calm_w) < len(calm)
    e3_coverage = {
        "n_crisis_shared": len(crisis_w), "n_calm_shared": len(calm_w),
        "n_crisis_pre": len(CRISIS), "n_calm_pre": len(calm),
        "episodes_shared": e3_episodes,
    }

    # P1 placebo (post-cutoff D−M bearish share diff), under the same parity
    # rule. This contrast is a difference of pooled SHARES, not of gaps, but it
    # is still a two-sample contrast and the same attrition applies: on
    # llama3.2:3b, D covers 8 post-cutoff dates and M covers 11, sharing 6, and
    # the unmatched value (-.033) differs from the date-matched one (-.125) by
    # 9.2pp of pure date composition. Every covered cell carries 8 sketches in
    # both arms, so pooling equals a per-date mean and the whole gap is
    # composition.
    def share(bd, dates=None):
        src = bd if dates is None else {d: bd[d] for d in dates if d in bd}
        xs = [x for v in src.values() for x in v]
        return sum(1 for x in xs if x == "-") / len(xs) if xs else float("nan")
    D_post, M_post = post_only(arms["D"]), post_only(arms["M"])
    post_shared = sorted({d for d in D_post if d in M_post and D_post[d] and M_post[d]})
    p1 = share(D_post, post_shared) - share(M_post, post_shared)
    p1_gated = ({d for d in D_post if D_post[d]} != {d for d in M_post if M_post[d]})
    p1_coverage = {
        "n_post_D": len({d for d in D_post if D_post[d]}),
        "n_post_M": len({d for d in M_post if M_post[d]}),
        "n_post_shared": len(post_shared),
    }

    # REC (recovery probe, pre vs post); file absent = probe not run for this
    # row -> columns "-"
    rec_f = root / "date_probe_results.jsonl"
    rows = [json.loads(l) for l in rec_f.read_text().splitlines() if l.strip()] \
        if rec_f.exists() else []
    def rec_metrics(rs):
        yr = my = 0; offs = []
        n = 0
        for r in rs:
            est = r.get("estimated_date")
            if not est or len(est) < 7:
                continue
            try:
                ey, em = int(est[:4]), int(est[5:7])
            except ValueError:
                continue
            ty, tm = int(r["decision_date"][:4]), int(r["decision_date"][5:7])
            n += 1
            yr += (ey == ty); my += (ey == ty and em == tm)
            offs.append(abs((ty - ey) * 12 + (tm - em)))
        # n >= 10: a 2/258-coverage run (kimi rec non-convergence) must render
        # "-" — a 100% rate from n=2 survivors is an artifact, not a measurement
        thin = n < 10
        return {"n": n, "year": yr / n if n and not thin else None,
                "ym": my / n if n and not thin else None,
                "med_off": float(np.median(offs)) if offs and not thin else None}
    rec_pre = rec_metrics([r for r in rows if r["decision_date"] <= "2024-12-31"])
    rec_post = rec_metrics([r for r in rows if r["decision_date"] >= "2025-02"])

    # LAP + empirical cutoff (file may be absent: probes skipped for cost -> columns "-")
    lap_f = root / "lap_probe_results.jsonl"
    lap_rows = [json.loads(l) for l in lap_f.read_text().splitlines() if l.strip()] if lap_f.exists() else []
    lap_cnt = defaultdict(lambda: defaultdict(int))
    for r in lap_rows:
        lap_cnt[r["decision_date"]][r["answer"]] += 1
    LAP, UD = {}, {}
    for d, c in lap_cnt.items():
        n = sum(c.values())
        LAP[d] = (c["up"] + c["down"]) / n if n else np.nan
        UD[d] = (c["up"] - c["down"]) / n if n else np.nan
    lap_vals_pre = [LAP[d] for d in pre if d in LAP]
    lap_pre = float(np.mean(lap_vals_pre)) if lap_vals_pre else None
    # LAP 命中率:答了 up/down 的日期里,方向多数是否等于已实现方向(区分真召回与瞎猜)
    post_dates = sorted(d for d in LAP if d >= "2025-01")
    lap_post = float(np.mean([LAP[d] for d in post_dates])) if post_dates else None
    above = [d for d in sorted(LAP) if LAP[d] > 0.1]
    emp_cutoff = above[-1][:7] if above else None

    # delta (detection regression) + LAP hit rate
    import statsmodels.api as sm
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
    R_pre = pre_only(arms["R"])
    sig, hit, lap_v = [], [], []
    for d in pre:
        xs = R_pre.get(d, [])
        if not xs or real.get(d) is None or d not in LAP:
            continue
        net = sum(1 if x == "+" else -1 for x in xs)
        if net == 0:
            continue
        s = 1.0 if net > 0 else -1.0
        sig.append(s); hit.append(int(s == real[d])); lap_v.append(LAP[d])
    lap_hit_n = lap_hit_k = 0
    for d in pre:
        if d in UD and abs(UD[d]) > 1e-9 and real.get(d) is not None:
            lap_hit_n += 1
            lap_hit_k += int(np.sign(UD[d]) == real[d])
    lap_hit = lap_hit_k / lap_hit_n if lap_hit_n else None
    delta = t_delta = None
    # identifiability gate (2026-07-07): LAP with (near-)zero variance makes the
    # interaction column collinear with the signal column and the regression
    # degenerate (claude-sonnet-5: LAP pre == 1.000 exactly -> "delta" of 12.5).
    # Require genuine LAP variation; below threshold the column renders "-".
    if len(sig) > 30 and float(np.var(lap_v)) > 1e-4:
        X = pd.DataFrame({"signal": sig, "lap": lap_v})
        X["inter"] = X.signal * X.lap
        ols = sm.OLS(np.array(hit, float), sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
        delta, t_delta = float(ols.params["inter"]), float(ols.tvalues["inter"])

    # VALID
    total_valid = sum(s["valid"] for s in stats.values())
    total_expected = sum(s["cells"] for s in stats.values()) * 8
    total_perr = sum(s["parse_err"] for s in stats.values())

    row = {
        "model": args.model,
        "E2_date_trigger": {
            "est": e2, "ci95": e2_ci, "gap_D": g_d, "gap_M": g_m,
            "gated": e2_gated,
            "gate_reason": ("D and M return usable generations on different "
                            "dates, so the shared window is selected by "
                            "attrition rather than by design; E2 unidentified"
                            if e2_gated else None),
            "coverage": e2_coverage,
        },
        "E3_transplant": {
            "est": e3, "ci95": e3_ci, "gap_fake": g_wf, "gap_true": g_wt,
            "gated": e3_gated,
            "gate_reason": ("W's coverage is partial, so the true-date and "
                            "fake-date keyings populate different windows; "
                            "E3 unidentified" if e3_gated else None),
            "coverage": e3_coverage,
        },
        "P1_placebo_postcutoff": p1,
        "P1_placebo_detail": {
            "est": p1, "gated": p1_gated,
            "gate_reason": ("D and M cover different post-cutoff dates; the "
                            "placebo contrast is unidentified"
                            if p1_gated else None),
            "coverage": p1_coverage,
        },
        "REC": {"pre": rec_pre, "post": rec_post},
        "LAP": {"pre_mean": lap_pre, "post_mean": lap_post, "empirical_cutoff": emp_cutoff,
                "recall_hit_rate": lap_hit, "recall_n": lap_hit_n},
        "delta_dissociation": {"delta": delta, "t": t_delta, "n": len(sig)},
        "VALID": {"sketch_rate": total_valid / total_expected if total_expected else None,
                  "parse_err_cells": total_perr, "cells": sum(s["cells"] for s in stats.values())},
    }
    (root / f"{args.model.replace('/', '_')}_row.json").write_text(json.dumps(row, indent=2, default=float))

    def F(x, spec=".3f", pct=False):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return "-"
        return f"{x:{'.0%' if pct else spec}}"
    # preview only — the leaderboard table is owned by make_bench_rows.py
    # (regenerated from the row jsons; the old append-to-BENCH_ROWS.md path
    # was retired 2026-07-08 when the table became generated)
    line = (f"| {args.model} | {F(e2,'+.3f')} [{F(e2_ci[0],'.2f')},{F(e2_ci[1],'.2f')}] | "
            f"{F(e3,'+.3f')} [{F(e3_ci[0],'.2f')},{F(e3_ci[1],'.2f')}] | {F(p1,'+.3f')} | "
            f"{F(rec_pre['year'],pct=True)}/{F(rec_post['year'],pct=True)} | "
            f"{F(lap_pre)}/{F(lap_post)} (hit {F(lap_hit,pct=True)}) | {emp_cutoff or '-'} | "
            f"{F(delta)} (t={F(t_delta,'.2f')}) | {F(row['VALID']['sketch_rate'],pct=True)} |")
    print(line)
    print("row json written; run make_bench_rows.py to update the leaderboard")


if __name__ == "__main__":
    main()
