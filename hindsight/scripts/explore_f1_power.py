import sys, json, re, numpy as np
from pathlib import Path
sys.path.insert(0, "scripts")
from analyze_fm1 import CRISIS, CALM_YEARS, all_dates, gap
from analyze_bench_row import load_arm
B = 10_000
BENCH = Path("outputs/bench")
dates = all_dates()
crisis = [d for d in dates if d in CRISIS]; calm = [d for d in dates if d[:4] in CALM_YEARS]

def arms(key, reps=None):
    out = {}
    for a in "DM":
        bd = {}
        for node in (BENCH/key/a).glob("rep*/*"):
            if reps and node.parent.name not in reps: continue
            f = node/"01_sketches_valid.json"
            if f.exists():
                bd.setdefault(node.name, []).extend(s["direction"] for s in json.loads(f.read_text()) if s.get("direction") in "+-")
        out[a] = bd
    return out

def e2(A, cs, qs): return gap(A["D"], cs, qs) - gap(A["M"], cs, qs)

def ci(fn, seed=2026):
    rng = np.random.default_rng(seed); c = np.array(crisis); q = np.array(calm); out = np.empty(B)
    for b in range(B):
        out[b] = fn(list(rng.choice(c, len(c))), list(rng.choice(q, len(q))))
    return np.nanpercentile(out, 2.5)*100, np.nanpercentile(out, 97.5)*100

print(f"crisis {len(crisis)} calm {len(calm)}")
# 1. do extra reps narrow the CI? Gemini flash: rep1 only vs 3 reps
for reps in (["rep1"], ["rep2"], ["rep3"], ["rep1","rep2","rep3"]):
    A = arms("gemini-2.5-flash", reps); est = e2(A, crisis, calm)*100; lo, hi = ci(lambda cs, qs: e2(A, cs, qs))
    print(f"gemini flash {'+'.join(reps):15s} E2 {est:+.1f} [{lo:+.1f},{hi:+.1f}] width {hi-lo:.1f}")
# 2. paired contrast F1 vs Llama 3.3 on shared resampled dates
F, L = arms("r1-distill-llama-70b-awq"), arms("llama-3.3-70b-awq")
for name, A in (("F1", F), ("3.3", L)):
    lo, hi = ci(lambda cs, qs: e2(A, cs, qs)); print(f"{name} E2 {e2(A, crisis, calm)*100:+.1f} [{lo:+.1f},{hi:+.1f}]")
d = (e2(F, crisis, calm) - e2(L, crisis, calm))*100; lo, hi = ci(lambda cs, qs: e2(F, cs, qs) - e2(L, cs, qs))
print(f"paired E2(F1) - E2(3.3) = {d:+.1f} [{lo:+.1f},{hi:+.1f}]")
# per-date D-M on crisis dates, both models
def dm(A, dd): 
    b = lambda xs: sum(x == "-" for x in xs)/len(xs) if xs else float("nan")
    return b(A["D"].get(dd, [])) - b(A["M"].get(dd, []))
print("crisis date   F1 D-M   3.3 D-M")
for dd in crisis: print(f"  {dd}  {dm(F, dd):+.3f}  {dm(L, dd):+.3f}")
# 3. where does the recall go? crisis words in F1 think blocks vs answers, by arm
pat = re.compile(r"(financial crisis|great recession|lehman|subprime|housing (bubble|crash)|covid|pandemic|lockdown|2008 crisis|global financial|bear market|crash)", re.I)
for a in "RDMW":
    tk = ans = n = 0
    for dd in crisis:
        f = BENCH/"r1-distill-llama-70b-awq"/a/"rep1"/dd/"04_raw_response.txt"
        if not f.exists(): continue
        raw = f.read_text(); n += 1; th, _, an = raw.partition("</think>")
        tk += bool(pat.search(th)); ans += bool(pat.search(an))
    print(f"F1 arm {a} crisis cells {n}: crisis words in think {tk}/{n}, in answer {ans}/{n}")
