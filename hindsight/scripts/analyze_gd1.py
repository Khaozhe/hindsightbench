#!/usr/bin/env python
"""GD-1 analysis per frozen prereg 394c9ad4: 10Y yield direction, G1-G4.

Direction semantics: "+" = yield rises, "-" = yield falls.
G3 uses the *yield-down share* (crisis flight-to-quality) as the object.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map, CRISIS, CALM_YEARS, boot_diff  # noqa: E402

from hindsight_paths import REPO
GD1 = REPO / "hindsight/outputs/gd1"
B, SEED = 10_000, 2026


def load_arm(arm: str) -> dict[str, list[str]]:
    by_date = defaultdict(list)
    for node in (GD1 / arm / "rep1").glob("*"):
        f = node / "01_sketches_valid.json"
        if f.exists():
            for s in json.loads(f.read_text()):
                if s.get("direction") in ("+", "-"):
                    by_date[node.name].append(s["direction"])
    return by_date


def down_gap(by_date, crisis, calm):
    def share(dates):
        xs = [x for d in dates for x in by_date.get(d, [])]
        return sum(1 for x in xs if x == "-") / len(xs) if xs else float("nan")
    return share(crisis) - share(calm)


def main() -> None:
    dates = all_dates()
    calm = [d for d in dates if d[:4] in CALM_YEARS]
    fmap = fake_map(dates)
    rng = np.random.default_rng(SEED)

    D, M, W = load_arm("D"), load_arm("M"), load_arm("W")
    w_fake = defaultdict(list)
    for td, xs in W.items():
        w_fake[fmap[td]].extend(xs)

    g_d, g_m = down_gap(D, CRISIS, calm), down_gap(M, CRISIS, calm)
    e2 = g_d - g_m
    e2_ci = boot_diff(lambda c, q: down_gap(D, c, q), lambda c, q: down_gap(M, c, q), CRISIS, calm, rng)
    g_wf, g_wt = down_gap(w_fake, CRISIS, calm), down_gap(W, CRISIS, calm)
    e3_ci = boot_diff(lambda c, q: down_gap(w_fake, c, q), lambda c, q: down_gap(W, c, q), CRISIS, calm, rng)

    # LAP-10Y
    lap_cnt = defaultdict(lambda: defaultdict(int))
    lf = GD1 / "lap10_results.jsonl"
    for l in lf.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            lap_cnt[r["decision_date"]][r["answer"]] += 1
    LAP, RF = {}, {}
    for d, c in lap_cnt.items():
        n = sum(c.values())
        LAP[d] = (c["rise"] + c["fall"]) / n if n else np.nan
        RF[d] = (c["rise"] - c["fall"]) / n if n else np.nan
    pre = [d for d in dates if d in LAP]
    lap_pre = float(np.mean([LAP[d] for d in pre]))
    # realized 10Y direction
    rows = list(csv.DictReader((GD1 / "dgs10.csv").open()))
    grid = [r["date"] for r in rows]
    vals = {r["date"]: float(r["dgs10"]) for r in rows}
    def realized(t):
        after = [d for d in grid if d >= t]
        if len(after) < 21:
            return None
        delta = vals[after[20]] - vals[after[0]]
        return 1.0 if delta >= 0 else -1.0
    hit_k = hit_n = 0
    for d in pre:
        r = realized(d)
        if r is not None and abs(RF[d]) > 1e-9:
            hit_n += 1
            hit_k += int(np.sign(RF[d]) == r)
    lap_hit = hit_k / hit_n if hit_n else None

    L = ["# GD-1 Results (prereg 394c9ad4)", "",
         f"覆盖: D={len(D)} M={len(M)} W={len(W)} 日期",
         "",
         "指标口径: yield-down share 的危机−平静 gap（+ = 危机窗更多'收益率降'）",
         "",
         f"- Gap_down(D) = {g_d:+.3f}, Gap_down(M) = {g_m:+.3f}",
         f"- **G1 E2_10Y = {e2:+.3f}, CI [{e2_ci[0]:+.3f}, {e2_ci[1]:+.3f}]** (判定: {'PASS' if abs(e2) >= 0.05 and (e2_ci[0] > 0 or e2_ci[1] < 0) else 'FAIL'})",
         f"- **G2 移植: Gap_down_fake(W) = {g_wf:+.3f} / Gap_down_true(W) = {g_wt:+.3f}, fake−true CI [{e3_ci[0]:+.3f}, {e3_ci[1]:+.3f}]**",
         f"- **G3 叙事内容: E2_10Y 符号 = {'+ (危机→收益率降，flight-to-quality，与 SPX 反号) PASS' if e2 > 0 else '− (与 SPX 同号看空反射) FAIL'}**",
         f"- **G4 LAP-10Y: pre 均值 {lap_pre:.3f}, hit {lap_hit:.1%} (n={hit_n})** (判定: {'PASS' if lap_pre > 0.15 and lap_hit and lap_hit > 0.65 else 'FAIL'})",
         ]
    (GD1 / "GD1_RESULTS.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
