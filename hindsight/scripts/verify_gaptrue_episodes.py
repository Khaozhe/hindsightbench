#!/usr/bin/env python
"""Is Gap_true(W) a measurement of the data channel, or of (data - date)?

Paper 1 §4.1 uses Gap_true(W) = -5.7pp as "the data channel's masked-regime-FREE
measurement"; §5.1 uses it as the 'true' half of E3 = Gap_fake - Gap_true.

The W arm asserts fake(t) = t + 66 months (cyclic). Grouping by TRUE date does
not remove the date channel -- it just doesn't look at it. So this checks:
what fake label did each true crisis date actually receive, and does Gap_true
hold its sign once you split by episode?

Reuses the paper's own code: analyze_fm1.{load_arm,gap,fake_map,all_dates,
boot_diff}, B=10,000, seed=2026.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from analyze_fm1 import (all_dates, fake_map, gap, load_arm, boot_diff,
                         CRISIS, CALM_YEARS, B, SEED)

M = "gemini-2.5-flash"
dates = all_dates()
calm = [d for d in dates if d[:4] in CALM_YEARS]
fmap = fake_map(dates)

W = load_arm(M, "W")

EPISODES = {
    "GFC (2008-09..2009-02)": ["2008-09-15", "2008-10-15", "2008-11-15",
                               "2008-12-15", "2009-01-15", "2009-02-15"],
    "COVID (2020-03/04)":     ["2020-03-15", "2020-04-15"],
    "Inflation (2022-06/09/10)": ["2022-06-15", "2022-09-15", "2022-10-15"],
}

def bearish_rate(by_date, ds):
    b = sum(x.count("-") for d in ds for x in [by_date.get(d, [])])
    t = sum(len(by_date.get(d, [])) for d in ds)
    return (b / t if t else float("nan")), t

print("=" * 78)
print("A) W 臂：真危机日期拿到的假标签，以及各自的看空率")
print("=" * 78)
lab = lambda d: "CRISIS" if d in CRISIS else ("calm" if d[:4] in CALM_YEARS else "其他")
gfc = EPISODES["GFC (2008-09..2009-02)"]
others = [d for d in CRISIS if d not in gfc]
r_gfc, n_gfc = bearish_rate(W, gfc)
r_oth, n_oth = bearish_rate(W, others)
r_calm, n_calm = bearish_rate(W, calm)
print(f"  6 个 GFC 真危机日期（假标签 = calm 2014）: 看空率 {r_gfc:.4f}  (n={n_gfc})")
print(f"  5 个其余真危机日期（假标签 = 其他）      : 看空率 {r_oth:.4f}  (n={n_oth})")
print(f"  36 个真平静日期                          : 看空率 {r_calm:.4f}  (n={n_calm})")
print(f"\n  → GFC 块比其余危机日期低 {(r_oth - r_gfc)*100:+.1f}pp —— 数据同为危机，差别只在假标签")

print()
print("=" * 78)
print("B) Gap_true(W) 按 episode 拆：符号稳吗？")
print("=" * 78)
rng = np.random.default_rng(SEED)
full = gap(W, CRISIS, calm)
lo, hi = boot_diff(lambda c, q: gap(W, c, q), lambda c, q: 0.0, CRISIS, calm, rng)
print(f"  {'合并 11 危机日期 (论文报的)':<30} {full:+.4f}  [{lo:+.4f}, {hi:+.4f}]"
      f"{'  ← 含零' if lo <= 0 <= hi else '  ← 排零'}")
print()
for name, ds in EPISODES.items():
    rng = np.random.default_rng(SEED)
    g = gap(W, ds, calm)
    lo, hi = boot_diff(lambda c, q: gap(W, c, q), lambda c, q: 0.0, ds, calm, rng)
    fl = {lab(fmap[d]) for d in ds}
    mark = "含零" if lo <= 0 <= hi else ("排零(负)" if hi < 0 else "排零(正)")
    print(f"  {name:<30} {g:+.4f}  [{lo:+.4f}, {hi:+.4f}]  ← {mark}")
    print(f"  {'':<30} 假标签落在: {'/'.join(sorted(fl))}")

print()
print("=" * 78)
print("C) Gap_true(W′) —— 72 月保月臂，论文从未报告")
print("=" * 78)
Wp = load_arm(M, "Wp72")
fmap72 = {dates[i]: dates[(i + 72) % 240] for i in range(240)}
wp_fake = {}
for td, xs in Wp.items():
    wp_fake.setdefault(fmap72[td], []).extend(xs)
g_true72 = gap(Wp, CRISIS, calm)
g_fake72 = gap(wp_fake, CRISIS, calm)
rng = np.random.default_rng(SEED)
lo72, hi72 = boot_diff(lambda c, q: gap(Wp, c, q), lambda c, q: 0.0, CRISIS, calm, rng)
print(f"  Gap_true(W′) = {g_true72:+.4f}  [{lo72:+.4f}, {hi72:+.4f}]"
      f"{'  ← 含零' if lo72 <= 0 <= hi72 else '  ← 排零'}")
print(f"  Gap_fake(W′) = {g_fake72:+.4f}")
print(f"\n  对照 66 月臂 Gap_true(W) = {full:+.4f}")
print(f"  → 66 月给负、72 月给{'正' if g_true72 > 0 else '负'}：同一个'数据通道',移位一换符号就{'翻' if g_true72*full < 0 else '不翻'}")
print("\n  72 月臂里 6 个 GFC 日期的假标签：")
for d in gfc:
    print(f"    {d} → {fmap72[d]}  ({lab(fmap72[d])})")
