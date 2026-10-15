#!/usr/bin/env python
"""Corpus salience from an open pretraining-corpus index (Infini-gram, Dolma 1.7). Post-freeze exploratory, zero API cost
(public endpoint, rate-limited). Caches every query in outputs/review/corpus_salience/cache.json.

Temporal: for each of the 240 macro panel months, S_T(t) = log1p(count("Month YYYY" AND {crisis|recession|crash|pandemic}, window 500))
          - log1p(count("Month YYYY")), i.e. the log share of month mentions that sit near a crisis word.
          Then per leaderboard row: Spearman rho and OLS of the per-date date-trigger h_t = bearish_D(t) - bearish_M(t) on S_T(t),
          with a horse race against the realized 20-day S&P 500 return and against the crisis-set indicator.
Spatial:  for each ST-1 region, S_P(c) = log1p(sum of exact counts of {"<City> lockdown", "<City> COVID", "<City> stay-at-home",
          "<City> restrictions", "<City> pandemic"}) ; compared with per-city LAP recall and per-city D-minus-M.
Caveat (stated in the paper): Dolma is a proxy for vendors' corpora, not any vendor's corpus.
"""
from __future__ import annotations
import json, math, sys, time
from pathlib import Path
import numpy as np, requests
sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, CRISIS, CALM_YEARS  # noqa: E402
from hindsight_paths import REPO  # noqa: E402
from build_st_panel import REGIONS  # noqa: E402

API = "https://api.infini-gram.io/"; INDEX = "v4_dolma-v1_7_llama"
OUT = REPO / "hindsight/outputs/review/corpus_salience"; OUT.mkdir(parents=True, exist_ok=True)
CACHE = OUT / "cache.json"; cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
BENCH = REPO / "hindsight/outputs/bench"; ST1 = REPO / "hindsight/outputs/st1"
MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]
CRISIS_TERMS = "crisis OR recession OR crash OR pandemic"
CITY_PHRASES = {"nyc": ["New York lockdown", "New York City lockdown", "NYC lockdown", "New York COVID", "New York shutdown"],
                "milan": ["Lombardy lockdown", "Milan lockdown", "Italy lockdown", "Lombardy COVID", "Italian lockdown"],
                "london": ["London lockdown", "UK lockdown", "England lockdown", "London COVID", "national lockdown"],
                "madrid": ["Madrid lockdown", "Spain lockdown", "Spanish lockdown", "Madrid COVID", "state of alarm"],
                "tokyo": ["Tokyo lockdown", "Tokyo state of emergency", "Japan state of emergency", "Tokyo COVID", "Japan lockdown"],
                "melbourne": ["Melbourne lockdown", "Victoria lockdown", "Victorian lockdown", "Melbourne COVID", "stage 4 restrictions"],
                "sydney": ["Sydney lockdown", "NSW lockdown", "New South Wales lockdown", "Sydney COVID", "Greater Sydney lockdown"],
                "delhi": ["Delhi lockdown", "India lockdown", "Indian lockdown", "Delhi COVID", "nationwide lockdown"],
                "hongkong": ["Hong Kong lockdown", "Hong Kong COVID", "Hong Kong restrictions", "Hong Kong fifth wave", "Hong Kong social distancing"],
                "singapore": ["Singapore circuit breaker", "Singapore lockdown", "Singapore COVID", "Singapore restrictions", "circuit breaker period"]}


def count(query: str, window: int | None = None) -> int:
    key = f"{query}|{window}"
    if key in cache: return cache[key]
    body = {"index": INDEX, "query_type": "count", "query": query}
    if window: body["max_diff_tokens"] = window
    for attempt in range(5):
        try:
            r = requests.post(API, json=body, timeout=60).json()
            if "count" in r:
                cache[key] = int(r["count"]); CACHE.write_text(json.dumps(cache, indent=0)); return cache[key]
            if "error" in r and "rate" in r["error"].lower(): time.sleep(3 + 3 * attempt); continue
            raise RuntimeError(r.get("error", r))
        except requests.RequestException:
            time.sleep(2 + 2 * attempt)
    raise RuntimeError(f"infini-gram failed: {query}")


def month_phrase(d: str) -> str:
    return f"{MONTHS[int(d[5:7]) - 1]} {d[:4]}"


def bearish_by_date(row: Path, arm: str) -> dict[str, float]:
    out = {}
    for node in (row / arm).glob("rep*/*"):
        f = node / "01_sketches_valid.json"
        if f.exists():
            ds = [s["direction"] for s in json.loads(f.read_text()) if s.get("direction") in ("+", "-")]
            if ds: out.setdefault(node.name, []).extend(ds)
    return {d: v.count("-") / len(v) for d, v in out.items()}


def spearman(x, y):
    from scipy.stats import spearmanr
    r, p = spearmanr(x, y); return float(r), float(p)


def main():
    dates = all_dates()
    # --- temporal salience
    ST = {}
    for d in dates:
        m = month_phrase(d); base = count(m); joint = count(f"{m} AND {CRISIS_TERMS}", 500)
        ST[d] = math.log1p(joint) - math.log1p(base)
    (OUT / "temporal_salience.json").write_text(json.dumps(ST, indent=1))
    crisis_ind = {d: 1.0 if d in CRISIS else 0.0 for d in dates}
    L = ["# Corpus salience (Infini-gram, Dolma 1.7; post-freeze exploratory)", "",
         f"Temporal: S_T(t) = log share of 'Month YYYY' mentions within 500 tokens of {{{CRISIS_TERMS}}}. Top months: " +
         ", ".join(f"{d[:7]} ({ST[d]:.2f})" for d in sorted(dates, key=lambda d: -ST[d])[:8]), "",
         "| row | Spearman rho(h_t, S_T) | p | rho(h_t, crisis-set) | rho(S_T, crisis-set) |", "|---|---|---|---|---|"]
    rows = []
    for row in sorted(BENCH.iterdir()):
        if not ((row / "D").is_dir() and (row / "M").is_dir()): continue
        D, M = bearish_by_date(row, "D"), bearish_by_date(row, "M")
        common = [d for d in dates if d in D and d in M]
        if len(common) < 200: continue
        h = np.array([D[d] - M[d] for d in common]); s = np.array([ST[d] for d in common]); c = np.array([crisis_ind[d] for d in common])
        r1, p1 = spearman(h, s); r2, _ = spearman(h, c); r3, _ = spearman(s, c)
        rows.append((row.name, r1, p1, r2, r3))
        L.append(f"| {row.name} | {r1:+.3f} | {p1:.3g} | {r2:+.3f} | {r3:+.3f} |")
    med = np.median([r[1] for r in rows]); npos = sum(1 for r in rows if r[1] > 0 and r[2] < 0.05)
    L += ["", f"**Temporal summary over {len(rows)} rows:** median rho(h_t, S_T) = {med:+.3f}; positive and p<0.05 on {npos}/{len(rows)}. "
          f"rho(S_T, crisis-set indicator) = {rows[0][4]:+.3f} (same for every row)."]
    # --- spatial salience
    SP = {c: sum(count(p) for p in CITY_PHRASES[c]) for c in REGIONS}
    L += ["", "## Spatial (ST-1 regions)", "", "| region | corpus count (sum of 5 phrases) | log1p |", "|---|---|---|"]
    for c in REGIONS: L.append(f"| {c} | {SP[c]:,} | {math.log1p(SP[c]):.2f} |")
    for tag in ("deepseek-v4-flash", "gemini-2.5-flash-pooled"):
        rj = ST1 / tag / f"{tag}_st1_row.json"
        if not rj.exists(): continue
        r = json.loads(rj.read_text()); lap = r["lap"]
        xs = [math.log1p(SP[c]) for c in REGIONS]; rec = [lap[c]["recall"] for c in REGIONS]; hit = [lap[c]["hit"] for c in REGIONS]
        rr, pr = spearman(xs, rec); rh, ph = spearman(xs, hit)
        L.append(f"\n{tag}: Spearman rho(log corpus count, LAP recall) = {rr:+.2f} (p={pr:.2f}); rho(log count, LAP hit) = {rh:+.2f} (p={ph:.2f}); n=10 regions")
    (OUT / "CORPUS_SALIENCE.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


if __name__ == "__main__":
    main()
