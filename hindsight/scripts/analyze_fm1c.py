#!/usr/bin/env python
"""FM-1c analysis per frozen prereg (FM1c_prereg.md, sha256 d8d5f66e...)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import load_arm, all_dates, fake_map, gap, boot_diff, CRISIS, CALM_YEARS

from hindsight_paths import REPO
FM1C = REPO / "hindsight/outputs/fm1c"
SPX_NEW = REPO / "macrochain/data/processed/spx_target_new.parquet"
OUT = FM1C / "FM1C_RESULTS.md"
B, SEED = 10_000, 2026


def load_dir_tree(root: Path) -> dict[str, list[str]]:
    by_date = defaultdict(list)
    for f in root.glob("rep*/*/01_sketches_valid.json"):
        for s in json.loads(f.read_text()):
            if s.get("direction") in ("+", "-"):
                by_date[f.parent.name].append(s["direction"])
    return by_date


def bear_share(by_date, dates):
    b = t = 0
    for d in dates:
        xs = by_date.get(d, [])
        b += sum(1 for x in xs if x == "-")
        t += len(xs)
    return b / t if t else float("nan"), b, t


def boot_share_diff(bd1, d1, bd2, d2, rng):
    out = np.empty(B)
    a1, a2 = np.array(d1), np.array(d2)
    for i in range(B):
        s1 = list(rng.choice(a1, len(a1), replace=True))
        s2 = list(rng.choice(a2, len(a2), replace=True))
        out[i] = bear_share(bd1, s1)[0] - bear_share(bd2, s2)[0]
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def main() -> None:
    import statsmodels.api as sm
    rng = np.random.default_rng(SEED)
    L = ["# FM-1c Results (per frozen prereg d8d5f66e)", ""]

    # ---------- C1: post-cutoff placebo ----------
    pc_root = FM1C / "gemini-2.5-flash"
    pc = {a: load_dir_tree(pc_root / a) for a in ("R", "D", "M", "W")}
    pc_dates = sorted(pc["D"].keys())
    placebo = [d for d in pc_dates if d >= "2025-02"]
    dm_diff = bear_share(pc["D"], placebo)[0] - bear_share(pc["M"], placebo)[0]
    dm_ci = boot_share_diff(pc["D"], placebo, pc["M"], placebo, rng)
    # W crisis-fake vs calm-fake split by run_meta fake_date
    fake_of = {}
    for f in (pc_root / "W").glob("rep1/*/03_run_meta.json"):
        m = json.loads(f.read_text())
        fake_of[m["decision_date"]] = m["fake_date"]
    cf = [d for d in placebo if fake_of.get(d) in CRISIS]
    qf = [d for d in placebo if fake_of.get(d) not in CRISIS]
    w_cf, w_qf = bear_share(pc["W"], cf)[0], bear_share(pc["W"], qf)[0]
    w_ci = boot_share_diff(pc["W"], cf, pc["W"], qf, rng)
    # P3: post-cutoff date recovery
    rows = [json.loads(l) for l in (FM1C / "date_probe_postcutoff.jsonl").read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r["decision_date"] >= "2025-02"]
    yr = sum(1 for r in rows if r.get("estimated_date") and r["estimated_date"][:4] == r["decision_date"][:4])
    L += [
        "## C1 Post-cutoff placebo (2025-02..2026-06)",
        f"- P1: D−M bearish diff = {dm_diff:+.3f}, CI [{dm_ci[0]:.3f}, {dm_ci[1]:.3f}]  (pre-cutoff E2=+0.256)",
        f"- P2: W crisis-fake {w_cf:.3f} vs calm-fake {w_qf:.3f}, diff {w_cf-w_qf:+.3f}, CI [{w_ci[0]:.3f}, {w_ci[1]:.3f}]",
        f"- P3: 日期恢复(日历年命中) = {yr}/{len(rows)} = {yr/len(rows):.1%}  (pre-cutoff 80.4%; Lopez-Lira post 28.8%)",
        "",
    ]

    # ---------- C2: LAP ----------
    lap_rows = [json.loads(l) for l in (FM1C / "lap_probe_results.jsonl").read_text().splitlines() if l.strip()]
    lap = defaultdict(lambda: {"up": 0, "down": 0, "unknown": 0, "invalid": 0})
    for r in lap_rows:
        lap[r["decision_date"]][r["answer"]] += 1
    LAP, UD = {}, {}
    for d, c in lap.items():
        n = c["up"] + c["down"] + c["unknown"] + c["invalid"]
        LAP[d] = (c["up"] + c["down"]) / n if n else np.nan
        UD[d] = (c["up"] - c["down"]) / n if n else np.nan
    pre = [d for d in all_dates()]
    post = [d for d in lap if d >= "2025-02"]
    # realized directions
    spx = pd.read_parquet(SPX_NEW).reset_index()
    dcol = "date" if "date" in spx.columns else spx.columns[0]
    spx[dcol] = pd.to_datetime(spx[dcol])
    spx = spx.sort_values(dcol)
    def realized(d):
        after = spx[spx[dcol] >= pd.Timestamp(d)]
        if not len(after) or pd.isna(after.iloc[0]["forward_return_20d"]):
            return None
        return 1.0 if after.iloc[0]["forward_return_20d"] >= 0 else -1.0
    real = {d: realized(d) for d in set(pre) | set(post)}
    # A1 validation
    med = np.median([LAP[d] for d in pre])
    def hitrate(ds):
        h = t = 0
        for d in ds:
            if real.get(d) is None or abs(UD[d]) < 1e-9:
                continue
            h += int(np.sign(UD[d]) == real[d]); t += 1
        return h / t if t else np.nan, t
    hi, n_hi = hitrate([d for d in pre if LAP[d] > med])
    lo, n_lo = hitrate([d for d in pre if LAP[d] <= med])
    # A2 detection regression: hit_t of R-arm majority vs signal x LAP
    arms_R = load_arm("gemini-2.5-flash", "R")
    sig, hit, lap_v = [], [], []
    for d in pre:
        xs = arms_R.get(d, [])
        if not xs or real.get(d) is None:
            continue
        net = sum(1 if x == "+" else -1 for x in xs)
        if net == 0:
            continue
        s = 1.0 if net > 0 else -1.0
        sig.append(s); hit.append(int(s == real[d])); lap_v.append(LAP[d])
    X = pd.DataFrame({"signal": sig, "lap": lap_v})
    X["inter"] = X.signal * X.lap
    ols = sm.OLS(np.array(hit, float), sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    delta, t_delta = ols.params["inter"], ols.tvalues["inter"]
    # A3 transplant third evidence: W bearish rate vs UD at fake vs true dates
    arms_W = load_arm("gemini-2.5-flash", "W")
    fmap = fake_map(all_dates())
    wb, ud_f, ud_t = [], [], []
    for d in pre:
        xs = arms_W.get(d, [])
        if not xs:
            continue
        wb.append(sum(1 for x in xs if x == "-") / len(xs))
        ud_f.append(UD[fmap[d]]); ud_t.append(UD[d])
    Xw = sm.add_constant(pd.DataFrame({"ud_fake": ud_f, "ud_true": ud_t}))
    olsw = sm.OLS(np.array(wb), Xw).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    # A4
    lap_post = [LAP[d] for d in post]
    L += [
        "## C2 LAP bridge (20 reps/date, temp=1.0)",
        f"- A1: 高LAP半样本 (U−D) 命中率 {hi:.3f} (n={n_hi}) vs 低LAP {lo:.3f} (n={n_lo})",
        f"- A2: 检测回归 δ(signal×LAP) = {delta:+.3f}, t = {t_delta:+.2f} (单边 δ>0)",
        f"- A3: W臂看空率 ~ UD_fake 系数 {olsw.params['ud_fake']:+.3f} (t={olsw.tvalues['ud_fake']:+.2f}); UD_true {olsw.params['ud_true']:+.3f} (t={olsw.tvalues['ud_true']:+.2f})",
        f"- A4: post-cutoff LAP 均值 {np.mean(lap_post):.4f} / 最大 {np.max(lap_post):.4f}  (pre-cutoff 均值 {np.mean([LAP[d] for d in pre]):.4f})",
        "",
    ]

    # ---------- C3: W' seasonality robustness ----------
    wp = load_dir_tree(REPO / "hindsight/outputs/fm1/gemini-2.5-flash/Wp72")
    dates = all_dates()
    calm = [d for d in dates if d[:4] in CALM_YEARS]
    fmap72 = {dates[i]: dates[(i + 72) % 240] for i in range(240)}
    wp_fake = defaultdict(list)
    for td, xs in wp.items():
        wp_fake[fmap72[td]].extend(xs)
    g_fake72 = gap(wp_fake, CRISIS, calm)
    g_true72 = gap(wp, CRISIS, calm)
    ci72 = boot_diff(lambda c, q: gap(wp_fake, c, q), lambda c, q: gap(wp, c, q), CRISIS, calm, rng)
    L += [
        "## C3 W' (72-month, month-preserving)",
        f"- E3': Gap_fake(W')={g_fake72:+.3f}, Gap_true(W')={g_true72:+.3f}, diff CI [{ci72[0]:.3f}, {ci72[1]:.3f}]",
        f"- 对照 E3 (66月): Gap_fake=+0.253, fake−true=+0.311 → 差异 {abs(g_fake72-0.253)*100:.1f}pp (<10pp 判季节性不驱动)",
        "",
    ]
    OUT.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
