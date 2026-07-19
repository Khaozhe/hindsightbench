#!/usr/bin/env python
"""FM-1 analysis per frozen prereg (FM1_prereg.md, sha256 745b42e0...).

Endpoints:
  E1 = Gap(R) - Gap(D)   leaky-context (C2) effect
  E2 = Gap(D) - Gap(M)   date-string (C1) effect
  E3 = wrong-date transplant: Gap_fake(W) vs Gap_true(W)
  E4 = salience regression of h_t = bearish_R(t) - bearish_M(t)
  E5 = hindsight vs accuracy per arm
Plus robustness: archived V1 panel (2026-04) vs today's R arm.

Frozen before generation completed; sha256 in analyze_fm1_freeze.json.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from hindsight_paths import REPO
FM1 = REPO / "hindsight/outputs/fm1"
COV = FM1 / "covariates"
V1_PANEL = REPO / "macrochain/data/processed/sketches_panel.jsonl"
SPX = REPO / "macrochain/data/processed/spx_target.parquet"
OUT_MD = FM1 / "FM1_RESULTS.md"
OUT_JSON = FM1 / "fm1_metrics.json"

CRISIS = [
    "2008-09-15", "2008-10-15", "2008-11-15", "2008-12-15", "2009-01-15",
    "2009-02-15", "2020-03-15", "2020-04-15", "2022-06-15", "2022-09-15",
    "2022-10-15",
]
CALM_YEARS = {"2013", "2014", "2017"}
B = 10_000
SEED = 2026
FAKE_SHIFT = 66


def all_dates() -> list[str]:
    ds = sorted({json.loads(l)["decision_date"] for l in V1_PANEL.read_text().splitlines() if l.strip()})
    assert len(ds) == 240
    return ds


def fake_map(dates: list[str]) -> dict[str, str]:
    return {dates[i]: dates[(i + FAKE_SHIFT) % len(dates)] for i in range(len(dates))}


def load_arm(model: str, arm: str) -> dict[str, list[str]]:
    """Pool all reps: date -> list of directions."""
    by_date: dict[str, list[str]] = defaultdict(list)
    arm_dir = FM1 / model / arm
    for rep_dir in sorted(arm_dir.glob("rep*")):
        for node in sorted(rep_dir.iterdir()):
            f = node / "01_sketches_valid.json"
            if not f.exists():
                continue
            for s in json.loads(f.read_text()):
                if s.get("direction") in ("+", "-"):
                    by_date[node.name].append(s["direction"])
    return by_date


def load_v1_archived() -> dict[str, list[str]]:
    by_date: dict[str, list[str]] = defaultdict(list)
    for line in V1_PANEL.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("direction") in ("+", "-"):
            by_date[d["decision_date"]].append(d["direction"])
    return by_date


def counts(by_date, dates):
    bear = tot = 0
    for d in dates:
        xs = by_date.get(d, [])
        bear += sum(1 for x in xs if x == "-")
        tot += len(xs)
    return bear, tot


def gap(by_date, crisis, calm):
    cb, ct = counts(by_date, crisis)
    qb, qt = counts(by_date, calm)
    return cb / ct - qb / qt if ct and qt else float("nan")


def boot_diff(f1, f2, crisis, calm, rng):
    """bootstrap CI for f1(gap) - f2(gap) with shared resampled windows."""
    crisis_arr, calm_arr = np.array(crisis), np.array(calm)
    out = np.empty(B)
    for b in range(B):
        cs = list(rng.choice(crisis_arr, len(crisis_arr), replace=True))
        qs = list(rng.choice(calm_arr, len(calm_arr), replace=True))
        out[b] = f1(cs, qs) - f2(cs, qs)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def bearish_rate_series(by_date, dates):
    return pd.Series(
        {d: (sum(1 for x in by_date.get(d, []) if x == "-") / len(by_date[d]))
         for d in dates if by_date.get(d)},
        name="rate",
    )


def build_covariates(dates: list[str]) -> pd.DataFrame:
    spx = pd.read_parquet(SPX).reset_index()
    spx["date"] = pd.to_datetime(spx["date"])
    spx = spx.sort_values("date").reset_index(drop=True)

    usrec = {o["date"][:7]: float(o["value"]) for o in json.load(open(COV / "USREC.json"))["observations"]}
    vix_rows = [(o["date"][:7], float(o["value"])) for o in json.load(open(COV / "VIXCLS.json"))["observations"] if o["value"] != "."]
    vix_df = pd.DataFrame(vix_rows, columns=["ym", "v"]).groupby("ym")["v"].mean()

    rows = []
    for d in dates:
        ts = pd.Timestamp(d)
        after = spx[spx["date"] >= ts]
        fwd = float(after.iloc[0]["forward_return_20d"]) if len(after) else np.nan
        month = spx[(spx["date"].dt.year == ts.year) & (spx["date"].dt.month == ts.month)]
        drawdown = float(month["Close"].min() / month["Close"].iloc[0] - 1) if len(month) else np.nan
        ym = d[:7]
        rows.append({
            "date": d, "fwd_ret": fwd, "drawdown": drawdown,
            "usrec": usrec.get(ym, np.nan), "vix": float(vix_df.get(ym, np.nan)),
            "realized_dir": 1.0 if fwd >= 0 else -1.0,
        })
    return pd.DataFrame(rows).set_index("date")


def accuracy(by_date, cov, dates):
    """majority-vote and sketch-level accuracy vs realized direction."""
    mv_hit = mv_tot = sk_hit = sk_tot = 0
    for d in dates:
        xs = by_date.get(d, [])
        if not xs or d not in cov.index or np.isnan(cov.loc[d, "fwd_ret"]):
            continue
        real = cov.loc[d, "realized_dir"]
        net = sum(1 if x == "+" else -1 for x in xs)
        if net != 0:
            mv_hit += int((1.0 if net > 0 else -1.0) == real)
            mv_tot += 1
        for x in xs:
            sk_hit += int((1.0 if x == "+" else -1.0) == real)
            sk_tot += 1
    return {"majority_acc": mv_hit / mv_tot if mv_tot else np.nan, "n_majority": mv_tot,
            "sketch_acc": sk_hit / sk_tot if sk_tot else np.nan, "n_sketch": sk_tot}


def main() -> None:
    import statsmodels.api as sm

    dates = all_dates()
    calm = [d for d in dates if d[:4] in CALM_YEARS]
    fmap = fake_map(dates)
    rng = np.random.default_rng(SEED)

    model = "gemini-2.5-flash"
    arms = {a: load_arm(model, a) for a in ("R", "D", "M", "W")}
    v1_arch = load_v1_archived()

    coverage = {a: len(v) for a, v in arms.items()}
    gaps = {a: gap(arms[a], CRISIS, calm) for a in ("R", "D", "M")}

    e1_ci = boot_diff(lambda c, q: gap(arms["R"], c, q), lambda c, q: gap(arms["D"], c, q), CRISIS, calm, rng)
    e2_ci = boot_diff(lambda c, q: gap(arms["D"], c, q), lambda c, q: gap(arms["M"], c, q), CRISIS, calm, rng)

    # E3: relabel W sketches by fake date -> windows defined on fake labels
    w_by_fake: dict[str, list[str]] = defaultdict(list)
    for true_d, xs in arms["W"].items():
        w_by_fake[fmap[true_d]].extend(xs)
    gap_fake_w = gap(w_by_fake, CRISIS, calm)
    gap_true_w = gap(arms["W"], CRISIS, calm)
    e3_fake_ci = boot_diff(lambda c, q: gap(w_by_fake, c, q), lambda c, q: 0.0, CRISIS, calm, rng)
    e3_diff_ci = boot_diff(lambda c, q: gap(w_by_fake, c, q), lambda c, q: gap(arms["W"], c, q), CRISIS, calm, rng)

    # E4: salience regression
    cov = build_covariates(dates)
    r_rate = bearish_rate_series(arms["R"], dates)
    m_rate = bearish_rate_series(arms["M"], dates)
    h = (r_rate - m_rate).dropna()
    reg = cov.loc[h.index, ["fwd_ret", "drawdown", "usrec", "vix"]].copy()
    reg["vix"] = (reg["vix"] - reg["vix"].mean()) / reg["vix"].std()
    X = sm.add_constant(reg)
    ols = sm.OLS(h.values, X.values, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    e4 = {name: {"coef": float(b), "t": float(t), "p": float(p)}
          for name, b, t, p in zip(["const"] + list(reg.columns), ols.params, ols.tvalues, ols.pvalues)}

    # E5: accuracy
    e5 = {a: accuracy(arms[a], cov, dates) for a in ("R", "D", "M", "W")}
    e5_windows = {a: {
        "crisis": accuracy(arms[a], cov, CRISIS),
        "calm": accuracy(arms[a], cov, calm),
    } for a in ("R", "M")}

    # robustness: archived V1 vs fresh R
    gap_v1_arch = gap(v1_arch, CRISIS, calm)

    metrics = {
        "prereg": "FM1_prereg.md 745b42e0...",
        "coverage_dates": coverage,
        "gaps": {**gaps, "W_true": gap_true_w, "W_fake": gap_fake_w, "V1_archived": gap_v1_arch},
        "E1_leaky_context": {"est": gaps["R"] - gaps["D"], "ci95": e1_ci},
        "E2_date_string": {"est": gaps["D"] - gaps["M"], "ci95": e2_ci},
        "E3_transplant": {
            "gap_fake": gap_fake_w, "gap_fake_ci95": e3_fake_ci,
            "gap_true": gap_true_w,
            "fake_minus_true": gap_fake_w - gap_true_w, "diff_ci95": e3_diff_ci,
        },
        "E4_salience_ols_hac6": e4,
        "E5_accuracy": e5,
        "E5_accuracy_windows": e5_windows,
        "bootstrap": {"B": B, "seed": SEED},
    }
    OUT_JSON.write_text(json.dumps(metrics, indent=2, default=float))

    L = [
        "# FM-1 Results (per frozen prereg FM1_prereg.md)", "",
        f"覆盖: {coverage}", "",
        f"Gap(R)={gaps['R']:.3f}  Gap(D)={gaps['D']:.3f}  Gap(M)={gaps['M']:.3f}  [V1 存档={gap_v1_arch:.3f}]", "",
        f"**E1 泄漏上下文效应** = {gaps['R']-gaps['D']:+.3f}, CI {e1_ci}",
        f"**E2 日期字符串效应** = {gaps['D']-gaps['M']:+.3f}, CI {e2_ci}",
        f"**E3 日期移植**: Gap_fake(W)={gap_fake_w:+.3f} CI {e3_fake_ci}; Gap_true(W)={gap_true_w:+.3f}; fake−true={gap_fake_w-gap_true_w:+.3f} CI {e3_diff_ci}",
        "",
        "**E4 salience 回归** (h_t = bearish_R − bearish_M, HAC lag 6):",
    ]
    for k, v in e4.items():
        L.append(f"  - {k}: coef={v['coef']:+.4f}, t={v['t']:+.2f}, p={v['p']:.4f}")
    L += ["", "**E5 accuracy** (majority | sketch):"]
    for a, v in e5.items():
        L.append(f"  - {a}: {v['majority_acc']:.3f} (n={v['n_majority']}) | {v['sketch_acc']:.3f} (n={v['n_sketch']})")
    L += ["", "E5 分窗 (R vs M):"]
    for a, w in e5_windows.items():
        L.append(f"  - {a}: crisis mv={w['crisis']['majority_acc']:.3f}, calm mv={w['calm']['majority_acc']:.3f}")
    OUT_MD.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
