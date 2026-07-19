#!/usr/bin/env python
"""Independent check of the E1 claim, reusing the paper's OWN frozen code paths.

E1 = Gap(R) - Gap(D) on the pre-cutoff panel, exactly as paper 1 §3.3 defines it.
The paper reports E1 only for Gemini Flash (-3.4pp) and Pro (-1.2pp), and the
abstract states the leaky-context channel "contributes nothing". The bench panel
has R arms for every model (run_bench_model.arm_prompt: R = node['orig_user'],
the same leaky V1 prompt FM-1 used), so E1 is computable for all 15 rows.

Same estimator, same windows, same bootstrap (B=10,000, seed 2026) as the paper.
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from analyze_fm1 import all_dates, gap, CRISIS, CALM_YEARS
from analyze_bench_row import load_arm, boot_diff, BENCH, B, SEED

pre = all_dates()
calm = [d for d in pre if d[:4] in CALM_YEARS]
pre_set = set(pre)

models = sorted(p.name for p in BENCH.iterdir() if p.is_dir())
print(f"{'model':<24} {'Gap(R)':>8} {'Gap(D)':>8} {'E1':>8}  {'95% CI':>20}  {'nR':>4} {'nD':>4}")
print("-" * 92)

rows = []
for m in models:
    root = BENCH / m
    if not (root / "R").exists() or not (root / "D").exists():
        continue
    R, _ = load_arm(root, "R")
    D, _ = load_arm(root, "D")
    Rp = {d: v for d, v in R.items() if d in pre_set}
    Dp = {d: v for d, v in D.items() if d in pre_set}
    if not Rp or not Dp:
        continue

    gR = gap(Rp, CRISIS, calm)
    gD = gap(Dp, CRISIS, calm)
    if gR != gR or gD != gD:   # NaN guard
        continue
    e1 = gR - gD

    rng = np.random.default_rng(SEED)
    lo, hi = boot_diff(
        lambda c, q: gap(Rp, c, q),
        lambda c, q: gap(Dp, c, q),
        CRISIS, calm, rng, B=B,
    )
    sig = "" if (lo <= 0 <= hi) else "  <<< CI EXCLUDES ZERO"
    print(f"{m:<24} {gR:>8.4f} {gD:>8.4f} {e1:>+8.4f}  [{lo:>+7.4f},{hi:>+7.4f}]{sig}")
    rows.append({"model": m, "gap_R": gR, "gap_D": gD, "E1": e1, "ci": [lo, hi]})

print("-" * 92)
signs = [r for r in rows if r["E1"] > 0]
excl = [r for r in rows if not (r["ci"][0] <= 0 <= r["ci"][1])]
print(f"rows computed: {len(rows)} | E1>0: {len(signs)} | E1<0: {len(rows)-len(signs)}")
print(f"CI excludes zero: {len(excl)} -> {[(r['model'], round(r['E1'],4)) for r in excl]}")
out = Path(__file__).parent.parent / "outputs" / "e1_all_models.json"
out.write_text(json.dumps(rows, indent=1))
print(f"\nwritten: {out}")
