#!/usr/bin/env python
"""FM-2 stage-wise analysis per frozen prereg (FM2_prereg.md, sha256 deb018b9...).

T1: crisis-calm bearish gap at S0 (sketch) -> S1 (compiled) -> S2 (L1) ->
    S3 (top-K) -> S4 (production prediction), per arm (R, M).
T2: production rent = OOS accuracy/Sharpe difference R vs M (paired bootstrap).
T3: attribution notes for any stage losing >50% of the gap.

Aggregator replicated verbatim from macrochain/scripts/run_final_recompute.py
(mult_w / predict_mult, alpha=gamma=0.2, beta1=beta2=1.0, K_DEEP=20).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from hindsight_paths import REPO
FM2 = REPO / "hindsight/outputs/fm2"
SPX = REPO / "macrochain/data/processed/spx_target.parquet"
OUT = FM2 / "FM2_RESULTS.md"

CRISIS = [
    "2008-09-15", "2008-10-15", "2008-11-15", "2008-12-15", "2009-01-15",
    "2009-02-15", "2020-03-15", "2020-04-15", "2022-06-15", "2022-09-15",
    "2022-10-15",
]
CALM_YEARS = {"2013", "2014", "2017"}
ALPHA = GAMMA = 0.2
BETA1 = BETA2 = 1.0
K_DEEP = 20
TEST_START = "2019-01-01"
B, SEED = 10_000, 2026


def direction_of(rec: dict) -> str | None:
    for k in ("direction", "dir", "dir_sign"):
        v = rec.get(k)
        if v in ("+", "-"):
            return v
        if v in (1, 1.0, -1, -1.0):
            return "+" if v > 0 else "-"
    return None


def gap_from_jsonl(path: Path, calm: list[str]) -> tuple[float, int]:
    by_date = defaultdict(lambda: [0, 0])
    n = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        d = rec.get("decision_date")
        s = direction_of(rec)
        if not d or s is None:
            continue
        by_date[d][0] += (s == "-")
        by_date[d][1] += 1
        n += 1
    def share(dates):
        b = t = 0
        for dd in dates:
            b += by_date[dd][0]; t += by_date[dd][1]
        return b / t if t else float("nan")
    return share(CRISIS) - share(calm), n


def mult_w(row) -> float:
    edge = max(row["U_disc_ic_V"], 0.0)
    pen = (ALPHA * max(row["Rate_fals_V"], 0) + GAMMA * row["cmplx_norm"]
           + BETA1 * row["Sens_bait"] + BETA2 * row["Sens_rev"])
    return edge * math.exp(-pen)


def arm_stage_metrics(arm: str, calm: list[str], real: dict) -> dict:
    w = FM2 / arm
    g0, n0 = gap_from_jsonl(w / "sketches_panel.jsonl", calm)
    g1, n1 = gap_from_jsonl(w / "compiled_hypotheses_panel.jsonl", calm)
    g2, n2 = gap_from_jsonl(w / "l1_survivors.jsonl", calm)

    scores = pd.read_parquet(w / "chain_scores.parquet")
    # dir_sign join, verbatim logic from run_final_recompute.py L13-20
    dir_map = {}
    for line in (w / "compiled_hypotheses_panel.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        h = json.loads(line)
        dir_map[(h.get("compiled_template_id", ""), h.get("decision_date", ""))] = (
            1.0 if h.get("direction", "+") == "+" else -1.0)
    scores["dir_sign"] = scores.apply(
        lambda r: dir_map.get((r["compiled_template_id"], r["decision_date"]), 0.0), axis=1)
    # S3: top-K bearish share by date
    by_date_topk = {}
    preds = {}
    for dd, grp in scores.groupby("decision_date"):
        valid = grp[np.isfinite(grp["R_h"])]
        top = valid.nlargest(min(K_DEEP, len(valid)), "R_h")
        if len(top) == 0:
            continue
        by_date_topk[dd] = (int((top["dir_sign"] < 0).sum()), len(top))
        ws = sum(row["dir_sign"] * mult_w(row) for _, row in top.iterrows())
        preds[dd] = float(np.sign(ws)) if ws != 0 else 1.0
    def topk_share(dates):
        b = t = 0
        for dd in dates:
            if dd in by_date_topk:
                b += by_date_topk[dd][0]; t += by_date_topk[dd][1]
        return b / t if t else float("nan")
    g3 = topk_share(CRISIS) - topk_share(calm)
    # S4: production prediction bearish share gap
    def pred_neg_share(dates):
        xs = [1.0 if preds.get(dd, 1.0) < 0 else 0.0 for dd in dates if dd in preds]
        return float(np.mean(xs)) if xs else float("nan")
    g4 = pred_neg_share(CRISIS) - pred_neg_share(calm)
    # S5: OOS production metrics
    oos = sorted(d for d in preds if d >= TEST_START and real.get(d) is not None)
    hits = {d: int(preds[d] == real[d]["dir"]) for d in oos}
    acc = float(np.mean(list(hits.values()))) if oos else float("nan")
    neg = sum(1 for d in oos if preds[d] < 0)
    rets = np.array([real[d]["ret"] * preds[d] for d in oos])
    sharpe = float(rets.mean() / rets.std() * math.sqrt(12)) if len(rets) > 1 and rets.std() > 0 else float("nan")
    crisis_oos = [d for d in oos if d in CRISIS]
    acc_crisis = float(np.mean([hits[d] for d in crisis_oos])) if crisis_oos else float("nan")
    return {
        "gaps": [g0, g1, g2, g3, g4], "counts": [n0, n1, n2],
        "preds": preds, "hits": hits, "oos": oos,
        "acc": acc, "acc_crisis": acc_crisis, "neg": neg, "sharpe": sharpe,
    }


def main() -> None:
    spx = pd.read_parquet(SPX).reset_index()
    spx["date"] = pd.to_datetime(spx["date"])
    spx = spx.sort_values("date")
    dates_all = sorted({json.loads(l)["decision_date"]
                        for l in (FM2 / "R/sketches_panel.jsonl").read_text().splitlines() if l.strip()})
    calm = [d for d in dates_all if d[:4] in CALM_YEARS]
    real = {}
    for d in dates_all:
        after = spx[spx["date"] >= pd.Timestamp(d)]
        if len(after) and np.isfinite(after.iloc[0]["forward_return_20d"]):
            real[d] = {"dir": 1.0 if after.iloc[0]["forward_return_20d"] >= 0 else -1.0,
                       "ret": float(after.iloc[0]["forward_return_20d"])}

    R = arm_stage_metrics("R", calm, real)
    M = arm_stage_metrics("M", calm, real)

    # T2 paired bootstrap on common OOS dates
    common = sorted(set(R["oos"]) & set(M["oos"]))
    diffs = np.array([R["hits"][d] - M["hits"][d] for d in common], float)
    rng = np.random.default_rng(SEED)
    boots = np.array([diffs[rng.integers(0, len(diffs), len(diffs))].mean() for _ in range(B)])
    ci = np.percentile(boots, [2.5, 97.5])

    # always-long baseline on same dates
    al_acc = float(np.mean([1.0 if real[d]["dir"] > 0 else 0.0 for d in common]))

    stage_names = ["S0 sketch", "S1 compiled", "S2 L1", "S3 top-K", "S4 production"]
    L = ["# FM-2 Results (per frozen prereg deb018b9)", "",
         "## T1 租金衰减曲线（危机窗−平静窗 bearish gap）", "",
         "| Stage | R 臂 | M 臂 | R−M |", "|---|---|---|---|"]
    for i, s in enumerate(stage_names):
        L.append(f"| {s} | {R['gaps'][i]:+.3f} | {M['gaps'][i]:+.3f} | {R['gaps'][i]-M['gaps'][i]:+.3f} |")
    L += ["",
          f"元素计数 R: sketch/compiled/L1 = {R['counts']}, M: {M['counts']}", "",
          "## T2 生产租金 (2019+ OOS)", "",
          f"- Acc: R={R['acc']:.4f} vs M={M['acc']:.4f} vs always-long={al_acc:.4f} (n={len(common)})",
          f"- Acc_R − Acc_M = {diffs.mean():+.4f}, 95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}] (paired bootstrap B={B})",
          f"- 危机窗(OOS内) Acc: R={R['acc_crisis']:.3f} vs M={M['acc_crisis']:.3f}",
          f"- neg calls: R={R['neg']} vs M={M['neg']}",
          f"- sign-only Sharpe: R={R['sharpe']:.3f} vs M={M['sharpe']:.3f}",
          ]
    OUT.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
