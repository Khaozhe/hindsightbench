#!/usr/bin/env python
"""POST-HOC crosscheck (2026-09-24): same-snapshot W-vs-D and W-vs-M contrasts grouped by
asserted date, reproducing an external review (Astra) and testing its baseline dependence.
Zero API calls. Output: outputs/review/e3_within_node_crosscheck.txt"""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, "REPO_ROOT/hindsight/scripts")
from analyze_fm1 import all_dates, fake_map, CRISIS, CALM_YEARS, load_arm, gap
dates = all_dates(); fmap = fake_map(dates)
calm = [d for d in dates if d[:4] in CALM_YEARS]
cs, qs = set(CRISIS), set(calm)
A = {a: load_arm("gemini-2.5-flash", a) for a in "RDMW"}
print("E2", round((gap(A["D"], CRISIS, calm) - gap(A["M"], CRISIS, calm))*100, 1))
def sh(xs): return sum(x == "-" for x in xs) / len(xs)
def grp(pred):
    return [d for d in dates if pred(fmap[d]) and A["W"].get(d) and A["D"].get(d)]
gc, gq = grp(lambda a: a in cs), grp(lambda a: a in qs)
print("n nodes asserted-crisis", len(gc), "asserted-calm", len(gq))
print("true-date class of asserted-crisis nodes:", [("C" if d in cs else "Q" if d in qs else "o") + d[:7] for d in gc])
print("true-date class of asserted-calm nodes: crisis", sum(d in cs for d in gq), "calm", sum(d in qs for d in gq), "other", sum(d not in cs and d not in qs for d in gq))
def pooled(nodes, arm):
    xs = [x for d in nodes for x in A[arm][d]]; return sh(xs)
def eff_pooled(nodes): return pooled(nodes, "W") - pooled(nodes, "D")
def eff_mean(nodes): return float(np.mean([sh(A["W"][d]) - sh(A["D"][d]) for d in nodes]))
rng = np.random.default_rng(2026); B = 10000
for name, f in (("pooled-sketch", eff_pooled), ("node-mean", eff_mean)):
    ec, eq = f(gc), f(gq)
    bc, bq, bd = np.empty(B), np.empty(B), np.empty(B)
    for i in range(B):
        c = list(rng.choice(gc, len(gc))); q = list(rng.choice(gq, len(gq)))
        bc[i], bq[i] = f(c), f(q); bd[i] = bc[i] - bq[i]
    p = lambda v: f"[{np.percentile(v,2.5)*100:+.1f}, {np.percentile(v,97.5)*100:+.1f}]"
    print(f"{name}: to-crisis {ec*100:+.1f} {p(bc)} | to-calm {eq*100:+.1f} {p(bq)} | diff {(ec-eq)*100:+.1f} {p(bd)}")
# decomposition of to-calm by true-date class
for lab, sub in (("true-crisis", [d for d in gq if d in cs]), ("true-other", [d for d in gq if d not in cs])):
    if sub: print(f"  to-calm | {lab}: n={len(sub)} W {pooled(sub,'W')*100:.1f} D {pooled(sub,'D')*100:.1f} eff {eff_pooled(sub)*100:+.1f}")
print("  to-crisis: W", round(pooled(gc,'W')*100,1), "D", round(pooled(gc,'D')*100,1))
# M baseline for same nodes (within-node, date removed)
for lab, g in (("to-crisis", gc), ("to-calm", gq)):
    ok = [d for d in g if A["M"].get(d)]
    print(f"  {lab}: D-M {(pooled(ok,'D')-pooled(ok,'M'))*100:+.1f}  W-M {(pooled(ok,'W')-pooled(ok,'M'))*100:+.1f} (n={len(ok)})")
print("=== baseline M (date removed, same snapshot) ===")
def effM(nodes): return pooled(nodes, "W") - pooled(nodes, "M")
def effDM(nodes): return pooled(nodes, "D") - pooled(nodes, "M")
rng = np.random.default_rng(2026)
for name, f in (("W-M", effM), ("D-M (true date own effect)", effDM)):
    bc, bq, bd = np.empty(B), np.empty(B), np.empty(B)
    for i in range(B):
        c = list(rng.choice(gc, len(gc))); q = list(rng.choice(gq, len(gq)))
        bc[i], bq[i] = f(c), f(q); bd[i] = bc[i] - bq[i]
    p = lambda v: f"[{np.percentile(v,2.5)*100:+.1f}, {np.percentile(v,97.5)*100:+.1f}]"
    print(f"{name}: to-crisis {f(gc)*100:+.1f} {p(bc)} | to-calm {f(gq)*100:+.1f} {p(bq)} | diff {(f(gc)-f(gq))*100:+.1f} {p(bd)}")
print("=== §5.1 anecdotes (per node, bearish %) ===")
for td in ("2023-03-15", "2008-09-15"):
    print(td, "-> asserted", fmap[td], "| W", round(sh(A['W'][td])*100,1), "D", round(sh(A['D'][td])*100,1), "M", round(sh(A['M'][td])*100,1), "n", len(A['W'][td]))
inv = {v: k for k, v in fmap.items()}
for ad in ("2008-09-15", "2014-03-15"):
    print("D at", ad, round(sh(A['D'][ad])*100,1), "| W asserting", ad, "(true", inv[ad] + ")", round(sh(A['W'][inv[ad]])*100,1))
