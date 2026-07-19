#!/usr/bin/env python
"""FM-2b synthetic aggregator ablation (prereg 3d7d83e2 + addendum ed96cbdd).

All architectures operate on the SAME production top-K set (K=20 by R_h);
only the aggregation weighting differs:
  A1 equal-weight majority vote (no gate)
  A2 equal-weight sum sign (no gate)
  A3 binary IC gate + equal weight (addendum-corrected)
  A4 IC-gated multiplicative weighting (= production S4, recomputed control)
  A5 in-sample top-1 by R_h

Outputs: T1-style S4 gap per arm + rent, T2 OOS accuracy rent with paired
bootstrap, sign-only Sharpe. Writes outputs/fm2b/FM2B_RESULTS.md.
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

from hindsight_paths import REPO
OUT_DIR = REPO / "hindsight/outputs/fm2b"


def load_scores(arm: str) -> pd.DataFrame:
    w = FM2 / arm
    scores = pd.read_parquet(w / "chain_scores.parquet")
    dir_map = {}
    for line in (w / "compiled_hypotheses_panel.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        h = json.loads(line)
        dir_map[(h.get("compiled_template_id", ""), h.get("decision_date", ""))] = (
            1.0 if h.get("direction", "+") == "+" else -1.0)
    scores["dir_sign"] = scores.apply(
        lambda r: dir_map.get((r["compiled_template_id"], r["decision_date"]), 0.0), axis=1)
    return scores


def topk_by_date(scores: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for dd, grp in scores.groupby("decision_date"):
        valid = grp[np.isfinite(grp["R_h"])]
        top = valid.nlargest(min(K_DEEP, len(valid)), "R_h")
        if len(top):
            out[dd] = top
    return out


# --- architectures: top-K frame -> decision in {+1.0, -1.0} ---

def a1_majority(top: pd.DataFrame) -> float:
    s = (top["dir_sign"] > 0).sum() - (top["dir_sign"] < 0).sum()
    return float(np.sign(s)) if s != 0 else 1.0


def a2_equal_sum(top: pd.DataFrame) -> float:
    s = top["dir_sign"].sum()
    return float(np.sign(s)) if s != 0 else 1.0


def a3_binary_gate(top: pd.DataFrame) -> float:
    gated = top[top["U_disc_ic_V"] > 0]
    s = gated["dir_sign"].sum()
    return float(np.sign(s)) if s != 0 else 1.0


def a4_production(top: pd.DataFrame) -> float:
    ws = sum(row["dir_sign"] * mult_w(row) for _, row in top.iterrows())
    return float(np.sign(ws)) if ws != 0 else 1.0


def a5_top1(top: pd.DataFrame) -> float:
    row = top.iloc[0]  # already sorted desc by R_h via nlargest
    return row["dir_sign"] if row["dir_sign"] != 0 else 1.0


ARCHS = {
    "A1 等权多数票(无门控)": a1_majority,
    "A2 等权和符号(无门控)": a2_equal_sum,
    "A3 二值IC门控+等权": a3_binary_gate,
    "A4 生产(门控+乘性惩罚加权)": a4_production,
    "A5 样本内top-1": a5_top1,
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

    tops = {arm: topk_by_date(load_scores(arm)) for arm in ("R", "M")}
    rng = np.random.default_rng(SEED)

    def neg_share_gap(preds):
        def share(dates):
            xs = [1.0 if preds[dd] < 0 else 0.0 for dd in dates if dd in preds]
            return float(np.mean(xs)) if xs else float("nan")
        return share(CRISIS) - share(calm)

    rows, detail = [], {}
    for name, fn in ARCHS.items():
        preds = {arm: {dd: fn(top) for dd, top in tops[arm].items()} for arm in ("R", "M")}
        g = {arm: neg_share_gap(preds[arm]) for arm in ("R", "M")}
        oos = sorted(d for d in set(preds["R"]) & set(preds["M"])
                     if d >= TEST_START and d in real)
        hits = {arm: {d: int(preds[arm][d] == real[d]["dir"]) for d in oos} for arm in ("R", "M")}
        acc = {arm: float(np.mean(list(hits[arm].values()))) for arm in ("R", "M")}
        diffs = np.array([hits["R"][d] - hits["M"][d] for d in oos], float)
        boots = np.array([diffs[rng.integers(0, len(diffs), len(diffs))].mean() for _ in range(B)])
        ci = np.percentile(boots, [2.5, 97.5])
        sharpe = {}
        for arm in ("R", "M"):
            rets = np.array([real[d]["ret"] * preds[arm][d] for d in oos])
            sharpe[arm] = float(rets.mean() / rets.std() * math.sqrt(12)) if rets.std() > 0 else float("nan")
        rows.append((name, g["R"], g["M"], g["R"] - g["M"], acc["R"], acc["M"],
                     float(diffs.mean()), ci[0], ci[1], sharpe["R"], sharpe["M"], len(oos)))
        detail[name] = {"gap": g, "acc": acc, "ci": [float(ci[0]), float(ci[1])]}

    L = ["# FM-2b Results (prereg 3d7d83e2 + addendum ed96cbdd)", "",
         "所有架构作用于同一生产 top-K 集合（K=20 by R_h），仅聚合权重不同。", "",
         "## 消融主表",
         "",
         "| 架构 | T1 gap R | T1 gap M | T1 租金 R−M | OOS acc R | acc M | T2 租金 | 95% CI | Sharpe R | Sharpe M |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for (name, gr, gm, rent1, ar, am, rent2, lo, hi, sr, sm, n) in rows:
        L.append(f"| {name} | {gr:+.3f} | {gm:+.3f} | **{rent1:+.3f}** | {ar:.3f} | {am:.3f} | "
                 f"**{rent2:+.4f}** | [{lo:+.4f},{hi:+.4f}] | {sr:.3f} | {sm:.3f} |")
    L += ["", f"OOS n={rows[0][11]}（2019+，两臂共同覆盖）", "",
          "## 预注册假设判定",
          ""]
    h1_ungated = [r for r in rows if r[0].startswith(("A1", "A2"))]
    h1_gated = [r for r in rows if r[0].startswith(("A3", "A4"))]
    h1a = all(r[3] >= 0.075 for r in h1_ungated)
    h1b = all(abs(r[3]) < 0.05 for r in h1_gated)
    a3r = next(r[3] for r in rows if r[0].startswith("A3"))
    a4r = next(r[3] for r in rows if r[0].startswith("A4"))
    a5r = next(r[3] for r in rows if r[0].startswith("A5"))
    L += [f"- H1 (门控是关键): 无门控租金 ≥+7.5pp? {'PASS' if h1a else 'FAIL'} "
          f"(A1 {h1_ungated[0][3]:+.3f}, A2 {h1_ungated[1][3]:+.3f}); "
          f"有门控 |租金|<5pp? {'PASS' if h1b else 'FAIL'} (A3 {a3r:+.3f}, A4 {a4r:+.3f})",
          f"- H2 (连续加权非关键): |A3−A4| = {abs(a3r-a4r):.3f} {'<' if abs(a3r-a4r) < 0.03 else '>='} 0.03 → "
          f"{'PASS' if abs(a3r-a4r) < 0.03 else 'FAIL'}",
          f"- H3 (过拟合放大): A5 {a5r:+.3f} > A4 {a4r:+.3f}? {'PASS' if a5r > a4r else 'FAIL'}"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "FM2B_RESULTS.md").write_text("\n".join(L) + "\n")
    (OUT_DIR / "fm2b_metrics.json").write_text(json.dumps(detail, indent=2))
    print("\n".join(L))


if __name__ == "__main__":
    main()
