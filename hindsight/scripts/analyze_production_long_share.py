#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (2026-07-25, design-review response).

Discriminating statistic for the reviewer question the paper never answers:
"Is the PRODUCTION row of the S7.3 ablation a weaker version of the same
'decontamination by lobotomy' that the paper concedes for in-sample top-1?"

The paper (sections/07_exp4_pipeline.tex:14,29-31) reports the production
aggregator at 70.4% OOS accuracy, "identical to always-long", and separately
concedes that top-1 hits zero rent by "collapsing to always-long (98% of
top-ranked hypotheses are bullish)". If the production aggregator ALSO goes
long nearly every month, then "the pipeline is the firewall" is substantially
a restatement of "the aggregator rarely goes short".

Computes, on the frozen FM-2 panels (outputs/fm2/{R,M}/):
  (a) LONG share of monthly decisions, production aggregator, both arms,
      on the S7.2 OOS window (2019+) and the full evaluated window;
  (b) the same for all five ablation architectures in the S7.3 table
      (+ A2 sum-of-signs, + A3.5 IC-weighting-no-penalties);
  (c) always-long benchmark accuracy on the identical month sets;
  (d) months where R and M disagree in sign, and each arm's accuracy there;
  (e) bullish share of the TOP-RANKED hypothesis (the "98%" claim) and of the
      whole top-K pool.
Also re-derives every published S7.2 / S7.3 number and flags mismatches.

Reads ONLY frozen inputs. Writes ONLY to outputs/review/.
Aggregator definitions are imported verbatim from analyze_fm2 / analyze_fm2b
so this cannot drift from the numbers the paper cites.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from analyze_fm2 import (CRISIS, CALM_YEARS, K_DEEP, TEST_START, B, SEED,
                         FM2, SPX, mult_w)
from analyze_fm2b import load_scores, topk_by_date, a1_majority, a2_equal_sum, \
    a3_binary_gate, a4_production, a5_top1
from hindsight_paths import REPO

OUT_DIR = REPO / "hindsight/outputs/review"


def a35_ic_weight_no_penalty(top: pd.DataFrame) -> float:
    """Exploratory A3.5 from outputs/fm2b/FM2B_RESULTS.md:25.

    Never existed as code -- only as prose in the frozen results file, and the
    paper's "IC weighting, no penalties*" row (07_exp4_pipeline.tex:29) cites
    it. Reimplemented here from that stated definition:
        w = max(U_disc_ic_V, 0);  decision = sign(sum w * dir_sign)
    """
    w = np.maximum(top["U_disc_ic_V"].to_numpy(float), 0.0)
    s = float((w * top["dir_sign"].to_numpy(float)).sum())
    return float(np.sign(s)) if s != 0 else 1.0


# Paper-table label -> aggregator fn.  Order matches the S7.3 table.
ARCHS = {
    "equal_weight_vote_no_gate": a1_majority,          # A1, table row 1
    "equal_weight_sum_no_gate": a2_equal_sum,          # A2, omitted from table
    "binary_ic_screen": a3_binary_gate,                # A3, table row 2
    "ic_weighting_no_penalties": a35_ic_weight_no_penalty,  # A3.5, table row 3
    "production_ic_wt_plus_pen": a4_production,        # A4, table row 4
    "in_sample_top1": a5_top1,                         # A5, table row 5
}
PRODUCTION = "production_ic_wt_plus_pen"


def load_real() -> tuple[dict, list[str]]:
    """Realized SPX forward direction/return per decision date (verbatim
    logic from analyze_fm2.main / analyze_fm2b.main)."""
    spx = pd.read_parquet(SPX).reset_index()
    spx["date"] = pd.to_datetime(spx["date"])
    spx = spx.sort_values("date")
    dates_all = sorted({json.loads(l)["decision_date"]
                        for l in (FM2 / "R/sketches_panel.jsonl").read_text().splitlines()
                        if l.strip()})
    real = {}
    for d in dates_all:
        after = spx[spx["date"] >= pd.Timestamp(d)]
        if len(after) and np.isfinite(after.iloc[0]["forward_return_20d"]):
            real[d] = {"dir": 1.0 if after.iloc[0]["forward_return_20d"] >= 0 else -1.0,
                       "ret": float(after.iloc[0]["forward_return_20d"])}
    return real, dates_all


def window_stats(preds: dict, months: list[str], real: dict) -> dict:
    p = np.array([preds[d] for d in months], float)
    truth = np.array([real[d]["dir"] for d in months], float)
    rets = np.array([real[d]["ret"] for d in months], float)
    strat = rets * p
    sharpe = (float(strat.mean() / strat.std() * math.sqrt(12))
              if len(strat) > 1 and strat.std() > 0 else float("nan"))
    n_long = int((p > 0).sum())
    return {
        "n_months": len(months),
        "n_long": n_long,
        "n_short": int((p < 0).sum()),
        "long_share": n_long / len(months) if months else float("nan"),
        "accuracy": float((p == truth).mean()),
        "sharpe_sign_only": sharpe,
    }


def main() -> None:
    real, dates_all = load_real()
    calm = [d for d in dates_all if d[:4] in CALM_YEARS]

    scores = {arm: load_scores(arm) for arm in ("R", "M")}
    tops = {arm: topk_by_date(scores[arm]) for arm in ("R", "M")}

    # ---- decision series per architecture per arm ----
    preds = {name: {arm: {dd: fn(top) for dd, top in tops[arm].items()}
                    for arm in ("R", "M")}
             for name, fn in ARCHS.items()}

    # month sets: identical across architectures (same top-K frames)
    covered = sorted(set(tops["R"]) & set(tops["M"]) & set(real))
    oos = [d for d in covered if d >= TEST_START]
    windows = {"oos_2019plus": oos, "full_evaluated": covered}

    # ---- always-long benchmark on the identical month sets ----
    always_long = {}
    for wname, months in windows.items():
        up = [d for d in months if real[d]["dir"] > 0]
        rets = np.array([real[d]["ret"] for d in months], float)
        always_long[wname] = {
            "n_months": len(months),
            "long_share": 1.0,
            "accuracy": len(up) / len(months) if months else float("nan"),
            "sharpe_sign_only": (float(rets.mean() / rets.std() * math.sqrt(12))
                                 if len(rets) > 1 and rets.std() > 0 else float("nan")),
        }

    # ---- (a),(b) long share + accuracy, every architecture x arm x window ----
    table = {}
    for name in ARCHS:
        table[name] = {}
        for wname, months in windows.items():
            table[name][wname] = {
                arm: window_stats(preds[name][arm], months, real) for arm in ("R", "M")
            }
            table[name][wname]["rent_T2_R_minus_M"] = (
                table[name][wname]["R"]["accuracy"] - table[name][wname]["M"]["accuracy"])

    # ---- (d) R/M sign disagreement ----
    disagree = {}
    for name in ARCHS:
        disagree[name] = {}
        for wname, months in windows.items():
            dm = [d for d in months if preds[name]["R"][d] != preds[name]["M"][d]]
            ent = {"n_disagree": len(dm), "months": dm}
            if dm:
                for arm in ("R", "M"):
                    p = np.array([preds[name][arm][d] for d in dm], float)
                    t = np.array([real[d]["dir"] for d in dm], float)
                    ent[f"acc_{arm}_on_disagree"] = float((p == t).mean())
                    ent[f"n_long_{arm}_on_disagree"] = int((p > 0).sum())
                ent["truth_up_share_on_disagree"] = float(
                    np.mean([1.0 if real[d]["dir"] > 0 else 0.0 for d in dm]))
            disagree[name][wname] = ent

    # ---- (e) bullish share of hypotheses: top-1 (the "98%" claim) and top-K ----
    bullish = {}
    for arm in ("R", "M"):
        b1 = t1 = bk = tk = 0
        for dd, top in tops[arm].items():
            if dd not in real:
                continue
            b1 += int(top.iloc[0]["dir_sign"] > 0); t1 += 1
            bk += int((top["dir_sign"] > 0).sum()); tk += len(top)
        bullish[arm] = {
            "top1_bullish": b1, "top1_n": t1, "top1_bullish_share": b1 / t1,
            "topK_bullish": bk, "topK_n": tk, "topK_bullish_share": bk / tk,
        }
    # pooled across arms (the paper's "98% of top-ranked hypotheses are bullish"
    # does not say which arm)
    bullish["pooled_RM"] = {
        "top1_bullish_share": (bullish["R"]["top1_bullish"] + bullish["M"]["top1_bullish"])
        / (bullish["R"]["top1_n"] + bullish["M"]["top1_n"]),
        "topK_bullish_share": (bullish["R"]["topK_bullish"] + bullish["M"]["topK_bullish"])
        / (bullish["R"]["topK_n"] + bullish["M"]["topK_n"]),
    }

    # ---- (3) reproduce published numbers ----
    prod_oos = table[PRODUCTION]["oos_2019plus"]
    rng = np.random.default_rng(SEED)
    diffs = np.array([int(preds[PRODUCTION]["R"][d] == real[d]["dir"])
                      - int(preds[PRODUCTION]["M"][d] == real[d]["dir"]) for d in oos], float)
    boots = np.array([diffs[rng.integers(0, len(diffs), len(diffs))].mean() for _ in range(B)])
    ci = np.percentile(boots, [2.5, 97.5])

    def chk(label, got, want, tol):
        ok = (got is not None) and abs(got - want) <= tol
        return {"claim": label, "published": want, "recomputed": got,
                "tol": tol, "reproduces": bool(ok)}

    checks = [
        chk("S7.2 revealed OOS accuracy 70.4%", prod_oos["R"]["accuracy"], 0.704, 0.0006),
        chk("S7.2 masked OOS accuracy 71.8%", prod_oos["M"]["accuracy"], 0.718, 0.0006),
        chk("S7.2 always-long OOS accuracy = revealed",
            always_long["oos_2019plus"]["accuracy"], prod_oos["R"]["accuracy"], 1e-12),
        chk("S7.2 paired diff -1.4pp", float(diffs.mean()), -0.0141, 0.0006),
        chk("S7.2 CI low -4.2pp", float(ci[0]), -0.0423, 0.0015),
        chk("S7.2 CI high +0.0pp", float(ci[1]), 0.0000, 0.0015),
        chk("S7.2 n = 71 months", float(prod_oos["R"]["n_months"]), 71.0, 0.0),
        chk("S7.2 masked sign-only Sharpe 0.794", prod_oos["M"]["sharpe_sign_only"], 0.794, 0.0006),
        chk("S7.2 revealed sign-only Sharpe 0.695", prod_oos["R"]["sharpe_sign_only"], 0.695, 0.0006),
        chk("S7.3 equal-weight vote OOS R .521",
            table["equal_weight_vote_no_gate"]["oos_2019plus"]["R"]["accuracy"], 0.521, 0.0006),
        chk("S7.3 equal-weight vote OOS M .592",
            table["equal_weight_vote_no_gate"]["oos_2019plus"]["M"]["accuracy"], 0.592, 0.0006),
        chk("S7.3 binary IC screen OOS R .634",
            table["binary_ic_screen"]["oos_2019plus"]["R"]["accuracy"], 0.634, 0.0006),
        chk("S7.3 binary IC screen OOS M .718",
            table["binary_ic_screen"]["oos_2019plus"]["M"]["accuracy"], 0.718, 0.0006),
        chk("S7.3 IC-wt no-pen OOS R .690",
            table["ic_weighting_no_penalties"]["oos_2019plus"]["R"]["accuracy"], 0.690, 0.0006),
        chk("S7.3 IC-wt no-pen OOS M .718",
            table["ic_weighting_no_penalties"]["oos_2019plus"]["M"]["accuracy"], 0.718, 0.0006),
        chk("S7.3 IC-wt no-pen T2 -2.8pp",
            table["ic_weighting_no_penalties"]["oos_2019plus"]["rent_T2_R_minus_M"],
            -0.028, 0.0006),
        chk("S7.3 top-1 OOS R .718",
            table["in_sample_top1"]["oos_2019plus"]["R"]["accuracy"], 0.718, 0.0006),
        chk("S7.3 top-1 OOS M .704",
            table["in_sample_top1"]["oos_2019plus"]["M"]["accuracy"], 0.704, 0.0006),
        chk("S7.3 top-1 '98% of top-ranked hypotheses are bullish' -- REVEALED arm",
            bullish["R"]["top1_bullish_share"], 0.98, 0.005),
        chk("S7.3 top-1 '98% ...' -- MASKED arm (same sentence, other arm)",
            bullish["M"]["top1_bullish_share"], 0.98, 0.005),
        chk("S7.3 top-1 '98% ...' -- pooled R+M",
            bullish["pooled_RM"]["top1_bullish_share"], 0.98, 0.005),
    ]

    # ---- how far is each architecture from being literally always-long? ----
    dist_al = {}
    for name in ARCHS:
        dist_al[name] = {}
        for wname, months in windows.items():
            dist_al[name][wname] = {}
            for arm in ("R", "M"):
                short_months = [d for d in months if preds[name][arm][d] < 0]
                dist_al[name][wname][arm] = {
                    "n_months_differing_from_always_long": len(short_months),
                    "short_months": short_months,
                    "n_short_correct": sum(1 for d in short_months if real[d]["dir"] < 0),
                    "acc_delta_vs_always_long":
                        table[name][wname][arm]["accuracy"] - always_long[wname]["accuracy"],
                }

    # ---- is the -1.4pp T2 rent carried by a single month? ----
    prod_short_M = [d for d in oos if preds[PRODUCTION]["M"][d] < 0]
    prod_short_R = [d for d in oos if preds[PRODUCTION]["R"][d] < 0]
    drop = set(prod_short_M) | set(prod_short_R)
    kept = [d for d in oos if d not in drop]
    lo_stats = {arm: window_stats(preds[PRODUCTION][arm], kept, real) for arm in ("R", "M")}
    single_month = {
        "production_short_months_M_oos": prod_short_M,
        "production_short_months_R_oos": prod_short_R,
        "note": "Drop every month where EITHER production arm deviates from always-long; "
                "on the remainder both arms are identical to always-long by construction.",
        "n_kept": len(kept),
        "acc_R_on_kept": lo_stats["R"]["accuracy"],
        "acc_M_on_kept": lo_stats["M"]["accuracy"],
        "T2_rent_on_kept": lo_stats["R"]["accuracy"] - lo_stats["M"]["accuracy"],
        "full_T2_rent": prod_oos["R"]["accuracy"] - prod_oos["M"]["accuracy"],
        "one_month_in_71_pp": -1.0 / len(oos),
    }

    # ---- IDENTITY: accuracy delta vs always-long == (correct shorts - wrong shorts)/n ----
    # Since always-long is right whenever truth is up, an architecture can only differ
    # from always-long on months it goes short. Therefore
    #     acc = always_long_acc + (s_correct - s_wrong)/n     [exact, not approximate]
    # i.e. the entire T2 column of the S7.3 table is a restatement of net short-call
    # scoring. Verified numerically below.
    identity = {"max_abs_residual": 0.0, "rows": []}
    for name in ARCHS:
        for wname, months in windows.items():
            for arm in ("R", "M"):
                e = dist_al[name][wname][arm]
                s_c = e["n_short_correct"]
                s_w = e["n_months_differing_from_always_long"] - s_c
                predicted = always_long[wname]["accuracy"] + (s_c - s_w) / len(months)
                actual = table[name][wname][arm]["accuracy"]
                resid = abs(predicted - actual)
                identity["max_abs_residual"] = max(identity["max_abs_residual"], resid)
                identity["rows"].append({
                    "arch": name, "window": wname, "arm": arm,
                    "n_short": e["n_months_differing_from_always_long"],
                    "short_correct": s_c, "short_wrong": s_w,
                    "predicted_acc": predicted, "actual_acc": actual, "residual": resid})
    identity["holds_exactly"] = identity["max_abs_residual"] < 1e-12

    # ---- verdict inputs ----
    verdict = {
        "production_long_share_oos_R": prod_oos["R"]["long_share"],
        "production_long_share_oos_M": prod_oos["M"]["long_share"],
        "production_short_months_oos_R": prod_oos["R"]["n_short"],
        "production_short_months_oos_M": prod_oos["M"]["n_short"],
        "production_long_share_full_R": table[PRODUCTION]["full_evaluated"]["R"]["long_share"],
        "production_long_share_full_M": table[PRODUCTION]["full_evaluated"]["M"]["long_share"],
        "top1_long_share_oos_R": table["in_sample_top1"]["oos_2019plus"]["R"]["long_share"],
        "top1_long_share_oos_M": table["in_sample_top1"]["oos_2019plus"]["M"]["long_share"],
        "n_disagree_oos_production": disagree[PRODUCTION]["oos_2019plus"]["n_disagree"],
    }

    payload = {
        "generated": "2026-07-25 POST-FREEZE EXPLORATORY (design-review response)",
        "source_artifacts": {
            "decision_sign_source": "recomputed in-memory; NO frozen artifact stores the "
            "per-month decision sign. Inputs: outputs/fm2/{R,M}/chain_scores.parquet "
            "(R_h, U_disc_ic_V, Rate_fals_V, cmplx_norm, Sens_bait, Sens_rev) joined to "
            "outputs/fm2/{R,M}/compiled_hypotheses_panel.jsonl (direction -> dir_sign) "
            "by (compiled_template_id, decision_date); realized direction from "
            "macrochain/data/processed/spx_target.parquet:forward_return_20d.",
            "aggregator_code": "scripts/analyze_fm2.py:73 mult_w / :107 predict; "
            "scripts/analyze_fm2b.py:60-89 A1-A5. A3.5 ('IC weighting, no penalties') "
            "has no code anywhere in the repo -- only prose at "
            "outputs/fm2b/FM2B_RESULTS.md:25; reimplemented here from that definition.",
        },
        "windows": {k: {"n": len(v), "first": v[0], "last": v[-1]} for k, v in windows.items()},
        "always_long_benchmark": always_long,
        "by_architecture": table,
        "sign_disagreement_R_vs_M": disagree,
        "distance_from_always_long": dist_al,
        "single_month_decomposition": single_month,
        "short_call_identity": identity,
        "hypothesis_bullish_shares": bullish,
        "published_number_checks": checks,
        "verdict_inputs": verdict,
        "production_monthly_decisions_oos": {
            "dates": oos,
            "R": [preds[PRODUCTION]["R"][d] for d in oos],
            "M": [preds[PRODUCTION]["M"][d] for d in oos],
            "realized": [real[d]["dir"] for d in oos],
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "production_long_share.json").write_text(json.dumps(payload, indent=2))

    # ---- markdown ----
    L = ["# Production long-share audit (POST-FREEZE EXPLORATORY, 2026-07-25)", "",
         "Question: is the S7.3 *production* row a weaker version of the "
         "\"decontamination by lobotomy\" the paper concedes for in-sample top-1?",
         "", "## Windows", ""]
    for k, v in windows.items():
        L.append(f"- `{k}`: n={len(v)} months, {v[0]} .. {v[-1]}")
    L += ["", "## (a),(b) LONG share and accuracy by architecture", "",
          "`long` = decision sign +1. Always-long = 100% long by definition.", ""]
    for wname in windows:
        L += [f"### Window: {wname} (n={windows[wname] and len(windows[wname])})", "",
              "| Architecture | long% R | long% M | short mo. R | short mo. M | acc R | acc M | T2 R−M | Sharpe R | Sharpe M |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for name in ARCHS:
            e = table[name][wname]
            L.append(f"| {name} | {e['R']['long_share']*100:.1f}% | {e['M']['long_share']*100:.1f}% | "
                     f"{e['R']['n_short']} | {e['M']['n_short']} | {e['R']['accuracy']:.3f} | "
                     f"{e['M']['accuracy']:.3f} | {e['rent_T2_R_minus_M']:+.4f} | "
                     f"{e['R']['sharpe_sign_only']:.3f} | {e['M']['sharpe_sign_only']:.3f} |")
        al = always_long[wname]
        L.append(f"| **always-long (benchmark)** | 100.0% | 100.0% | 0 | 0 | {al['accuracy']:.3f} | "
                 f"{al['accuracy']:.3f} | 0.0000 | {al['sharpe_sign_only']:.3f} | "
                 f"{al['sharpe_sign_only']:.3f} |")
        L.append("")
    L += ["## (c) always-long benchmark", ""]
    for wname, al in always_long.items():
        L.append(f"- `{wname}`: accuracy {al['accuracy']:.4f} (n={al['n_months']}), "
                 f"sign-only Sharpe {al['sharpe_sign_only']:.3f}")
    L += ["", "## (d) R vs M sign disagreement", "",
          "| Architecture | window | n disagree | acc R there | acc M there | truth-up share there |",
          "|---|---|---|---|---|---|"]
    for name in ARCHS:
        for wname in windows:
            e = disagree[name][wname]
            if e["n_disagree"] == 0:
                L.append(f"| {name} | {wname} | 0 | — | — | — |")
            else:
                L.append(f"| {name} | {wname} | {e['n_disagree']} | {e['acc_R_on_disagree']:.3f} | "
                         f"{e['acc_M_on_disagree']:.3f} | {e['truth_up_share_on_disagree']:.3f} |")
    L += ["", "Disagreeing months (production, OOS): "
          + (", ".join(disagree[PRODUCTION]["oos_2019plus"]["months"]) or "none"), ""]
    L += ["## (e) bullish share of hypotheses", "",
          "| Arm | top-1 bullish | top-K (K=20) bullish |", "|---|---|---|"]
    for arm in ("R", "M"):
        b = bullish[arm]
        L.append(f"| {arm} | {b['top1_bullish_share']*100:.1f}% ({b['top1_bullish']}/{b['top1_n']}) | "
                 f"{b['topK_bullish_share']*100:.1f}% ({b['topK_bullish']}/{b['topK_n']}) |")
    L.append(f"| pooled | {bullish['pooled_RM']['top1_bullish_share']*100:.1f}% | "
             f"{bullish['pooled_RM']['topK_bullish_share']*100:.1f}% |")
    L += ["", "## Distance from literal always-long", "",
          "Months where the architecture deviates from always-long (i.e. goes short), "
          "and how many of those short calls were right.", "",
          "| Architecture | window | arm | months != always-long | short calls correct | acc delta vs always-long |",
          "|---|---|---|---|---|---|"]
    for name in ARCHS:
        for wname in windows:
            for arm in ("R", "M"):
                e = dist_al[name][wname][arm]
                L.append(f"| {name} | {wname} | {arm} | {e['n_months_differing_from_always_long']} | "
                         f"{e['n_short_correct']} | {e['acc_delta_vs_always_long']:+.4f} |")
    L += ["", "Production-row short months in full (listed):", ""]
    for wname in windows:
        for arm in ("R", "M"):
            sm = dist_al[PRODUCTION][wname][arm]["short_months"]
            L.append(f"- production / {wname} / arm {arm}: {sm or 'NONE'} "
                     f"({dist_al[PRODUCTION][wname][arm]['n_short_correct']} correct)")
    L += ["", "Note: every short call the REVEALED production arm ever makes falls in "
          "2008-07..2009-04, i.e. inside the in-sample GFC crisis window that T1 measures "
          "and entirely outside the 2019+ OOS window that T2 measures. On the T2 window "
          "the revealed aggregator expresses no directional view other than long.", ""]
    L += ["", "## Single-month decomposition of the S7.2 headline", ""]
    L += [f"- production short months, revealed arm, OOS: {single_month['production_short_months_R_oos'] or 'NONE'}",
          f"- production short months, masked arm, OOS: {single_month['production_short_months_M_oos'] or 'NONE'}",
          f"- dropping those month(s): n={single_month['n_kept']}, "
          f"acc R={single_month['acc_R_on_kept']:.4f}, acc M={single_month['acc_M_on_kept']:.4f}, "
          f"T2 rent={single_month['T2_rent_on_kept']:+.4f}",
          f"- full-window T2 rent={single_month['full_T2_rent']:+.4f}; "
          f"one month out of {len(oos)} = {single_month['one_month_in_71_pp']*100:+.2f}pp"]
    L += ["", "## Identity: the whole T2 column is net short-call scoring", "",
          "`acc = always_long_acc + (short_correct - short_wrong)/n`, exactly. "
          f"Max abs residual across all {len(identity['rows'])} arch x window x arm cells: "
          f"{identity['max_abs_residual']:.2e} "
          f"({'EXACT' if identity['holds_exactly'] else 'NOT EXACT'}).", "",
          "An architecture can only differ from always-long on months it goes short, so "
          "its T2 rent is fully determined by how often it shorts and how often it is right "
          "to. On the OOS window the up-rate is "
          f"{always_long['oos_2019plus']['accuracy']:.3f}, so each short call is an "
          "ex-ante losing bet.", "",
          "## (3) Published-number reproduction", "",
          "| Claim | published | recomputed | reproduces |", "|---|---|---|---|"]
    for c in checks:
        got = "n/a" if c["recomputed"] is None else f"{c['recomputed']:.4f}"
        L.append(f"| {c['claim']} | {c['published']} | {got} | "
                 f"{'YES' if c['reproduces'] else '**NO**'} |")
    fails = [c for c in checks if not c["reproduces"]]
    L += ["", f"Failures: {len(fails)}/{len(checks)}"]
    for c in fails:
        L.append(f"- **MISMATCH** {c['claim']}: published {c['published']}, "
                 f"recomputed {c['recomputed']}")
    L += ["", "## Verdict inputs", ""]
    for k, v in verdict.items():
        L.append(f"- `{k}` = {v}")
    (OUT_DIR / "production_long_share.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
