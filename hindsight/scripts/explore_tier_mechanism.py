#!/usr/bin/env python3
"""Exploratory (not preregistered): where does the AWQ-vs-FP8 difference on one checkpoint come from?
Reads cells already on disk. Compares tiers arm by arm on (1) bearish share crisis vs calm, (2) crisis
vocabulary in regime hints / narratives, (3) within-cell direction dispersion, (4) whether the response
echoes the decision year, (5) memory probes."""
import json, re, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import CRISIS, CALM_YEARS, all_dates
B = Path(__file__).resolve().parents[1] / "outputs/bench"
dates = all_dates(); crisis = [d for d in dates if d in CRISIS]; calm = [d for d in dates if d[:4] in CALM_YEARS]
VOC = re.compile(r"(recession|downturn|contraction|crisis|slowdown|stress|distress|panic|bear)", re.I)
PAIRS = [("tulu3-70b-rlvr-fp8dyn", "tulu3-70b-rlvr-awq"), ("qwen3.6-27b-bf16", "qwen3.6-27b-fp8"), ("qwen3.6-27b-bf16", "qwen3.6-27b-awq")]
EXTRA = ["llama-3.3-70b-awq", "llama-3.1-70b-awq", "tulu3-70b-dpo-fp8dyn", "tulu3-70b-sft-fp8dyn"]

def cell(key, arm, d, rep="rep1"):
    c = B / key / arm / rep / d
    f = c / "01_sketches_valid.json"
    if not f.exists():
        return None, ""
    raw = (c / "04_raw_response.txt").read_text() if (c / "04_raw_response.txt").exists() else ""
    return json.loads(f.read_text()), raw

def profile(key):
    out = {}
    for arm in "RDMW":
        row = {}
        for lab, ds in (("crisis", crisis), ("calm", calm)):
            bear = voc = n = allsame = echo = cells = 0; disp = []
            for d in ds:
                sk, raw = cell(key, arm, d)
                if not sk:
                    continue
                dirs = [s["direction"] for s in sk if s.get("direction") in ("+", "-")]
                if not dirs:
                    continue
                cells += 1; n += len(dirs); bear += dirs.count("-")
                p = dirs.count("-") / len(dirs); disp.append(p * (1 - p)); allsame += (p in (0, 1))
                voc += sum(bool(VOC.search(s.get("regime_hint", "") + " " + s.get("mechanism_narrative", ""))) for s in sk)
                echo += bool(re.search(d[:4], raw))
            row[lab] = dict(bear=bear / n, voc=voc / n, disp=float(np.mean(disp)), allsame=allsame / cells, echo=echo / cells)
        out[arm] = row
    return out

def show(key):
    p = profile(key)
    rf = B / key / f"{key}_row.json"
    if rf.exists():
        r = json.load(open(rf)); lap = r["LAP"]
        print(f"\n{key}: E2 {r['E2_date_trigger']['est']*100:+.1f}  LAP pre/post {lap.get('pre_mean'):.2f}/{lap.get('post_mean'):.2f}  hit {lap.get('recall_hit_rate', 0)*100:.0f}% on {lap.get('recall_n')}")
    else:
        print(f"\n{key}: (no row json)")
    print("  arm  bearish crisis/calm (gap)   crisis-vocab crisis/calm (gap)   within-cell disp  all-same cells  year echoed")
    for arm in "RDMW":
        c, q = p[arm]["crisis"], p[arm]["calm"]
        print(f"  {arm}    {c['bear']:.2f}/{q['bear']:.2f} ({c['bear']-q['bear']:+.2f})            {c['voc']:.2f}/{q['voc']:.2f} ({c['voc']-q['voc']:+.2f})               {c['disp']:.3f}/{q['disp']:.3f}      {c['allsame']:.2f}/{q['allsame']:.2f}      {c['echo']:.2f}/{q['echo']:.2f}")

for a, b in PAIRS:
    if (B / a).exists() and (B / b).exists():
        print("=" * 30, a, "vs", b); show(a); show(b)
print("=" * 30, "reference rows"); [show(k) for k in EXTRA if (B / k / f"{k}_row.json").exists()]


# whole-panel decomposition: each arm's own bearish share regressed on USREC (HAC 6), dates <= 2023-12
import statsmodels.api as sm
from analyze_fm1 import build_covariates
cov = build_covariates([d for d in dates if d <= "2023-12-31"])
def arm_share(key, arm):
    o = {}
    for n in (B / key / arm).glob("rep*/*"):
        f = n / "01_sketches_valid.json"
        if f.exists():
            xs = [s["direction"] for s in json.loads(f.read_text()) if s.get("direction") in ("+", "-")]
            if xs: o.setdefault(n.name, []).extend(xs)
    return {d: v.count("-") / len(v) for d, v in o.items()}
def slope(y):
    df = cov.copy(); df["y"] = [y.get(d, np.nan) for d in df.index]; df = df.dropna(subset=["y", "usrec"])
    f = sm.OLS(df["y"].values, sm.add_constant(df[["usrec"]].values)).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    return f.params[1] * 100, f.tvalues[1]
print("\n" + "=" * 30, "arm-level recession sensitivity (pp bearish per recession month, t) — D = date+data, M = data only")
keys = ["tulu3-70b-rlvr-fp8dyn", "tulu3-70b-rlvr-awq", "tulu3-70b-dpo-fp8dyn", "tulu3-70b-sft-fp8dyn", "hermes3-70b-fp8",
        "llama-3.1-70b-awq", "llama-3.1-70b-fp8dyn", "llama-3.3-70b-awq", "llama-3.3-70b-fp8dyn", "llama-3.1-nemotron-70b-awq", "r1-distill-llama-70b-awq",
        "qwen3.6-27b-bf16", "qwen3.6-27b-fp8", "qwen3.6-27b-awq", "qwen3-30b-a3b-thinking-2507-fp8dyn", "gemini-2.5-flash", "kimi-k2.6", "claude-sonnet-5"]
for k in keys:
    if not (B / k / "D").exists(): continue
    D, M = arm_share(k, "D"), arm_share(k, "M")
    bd, td = slope(D); bm, tm = slope(M)
    lvl = np.mean(list(M.values()))
    print(f"  {k:36s} D {bd:+6.1f} (t {td:+5.2f})   M {bm:+6.1f} (t {tm:+5.2f})   M-arm mean bearish {lvl:.2f}")
