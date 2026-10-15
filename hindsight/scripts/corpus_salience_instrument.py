#!/usr/bin/env python
"""Corpus-salience instrument (frozen: outputs/review/corpus_salience/INSTRUMENT.md).
Samples random documents containing a needle phrase from an open pretraining corpus (Infini-gram search_docs,
Dolma 1.7) and measures the share whose +-200-token window around the needle contains crisis vocabulary.
Unlike Infini-gram's approximate CNF count, the sample is exact per document and has no spurious zeros.

  python corpus_salience_instrument.py --job probe                      # 4 months x 2 calls, sanity
  python corpus_salience_instrument.py --job months --calls 10 --budget 160   # 240 months x 10 calls (100 docs each); resumable
  python corpus_salience_instrument.py --job cities --calls 20 --budget 160   # 10 regions x 20 calls
  python corpus_salience_instrument.py --job analyze
Throttle 1 req/s (public endpoint). Windows are cached raw, so vocabulary is applied at analysis time.
"""
from __future__ import annotations
import argparse, json, math, re, sys, time
from pathlib import Path
import numpy as np, requests
sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, CRISIS, CALM_YEARS  # noqa: E402
from hindsight_paths import REPO  # noqa: E402
from build_st_panel import REGIONS  # noqa: E402

API = "https://api.infini-gram.io/"; INDEX = "v4_dolma-v1_7_llama"; DISP = 400
OUT = REPO / "hindsight/outputs/review/corpus_salience"; OUT.mkdir(parents=True, exist_ok=True)
WIN = OUT / "windows.jsonl"          # one line per sampled document window: {query, doc_ix, text}
BENCH = REPO / "hindsight/outputs/bench"; ST1 = REPO / "hindsight/outputs/st1"
MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]
CRISIS_RX = re.compile(r"\b(crisis|recession|crash|collapse|meltdown|panic|bailout|depression|turmoil|pandemic|lockdown)\b", re.I)
FIN_RX = re.compile(r"\b(financial crisis|recession|market crash|stock market|bailout|Lehman|subprime|bear market)\b", re.I)
PAND_RX = re.compile(r"\b(lockdown|COVID|coronavirus|pandemic|quarantine|stay-at-home|social distancing)\b", re.I)
CITY_NEEDLE = {"nyc": "New York City", "milan": "Milan", "london": "London", "madrid": "Madrid", "tokyo": "Tokyo",
               "melbourne": "Melbourne", "sydney": "Sydney", "delhi": "Delhi", "hongkong": "Hong Kong", "singapore": "Singapore"}


def month_phrase(d): return f"{MONTHS[int(d[5:7]) - 1]} {d[:4]}"


def loaded():
    seen = {}
    if WIN.exists():
        for l in WIN.read_text().splitlines():
            if l.strip():
                r = json.loads(l); seen.setdefault(r["query"], set()).add(r["doc_ix"])
    return seen


def fetch(query: str) -> list[dict]:
    for attempt in range(6):
        try:
            r = requests.post(API, json={"index": INDEX, "query_type": "search_docs", "query": query, "maxnum": 10, "max_disp_len": DISP}, timeout=60)
            if r.status_code == 403 or r.status_code >= 500:
                time.sleep(5 + 5 * attempt); continue
            d = r.json()
            if "documents" not in d:
                time.sleep(3 + 3 * attempt); continue
            out = []
            for doc in d["documents"]:
                text = "".join(s[0] if isinstance(s, list) else str(s) for s in doc.get("spans", []))
                out.append({"query": query, "doc_ix": doc["doc_ix"], "text": text})
            return out
        except requests.RequestException:
            time.sleep(3 + 3 * attempt)
    return []


def sample(queries: list[str], calls: int, budget: float | None):
    t0 = time.time(); seen = loaded(); n_new = 0
    with WIN.open("a") as f:
        for q in queries:
            have = len(seen.get(q, set()))
            need_calls = max(0, math.ceil((calls * 10 - have) / 10))
            for _ in range(need_calls):
                if budget and time.time() - t0 > budget:
                    print(f"budget: stopped at {q} ({n_new} new windows)"); return
                for r in fetch(q):
                    if r["doc_ix"] not in seen.setdefault(q, set()):
                        seen[q].add(r["doc_ix"]); f.write(json.dumps(r) + "\n"); n_new += 1
                time.sleep(1.0)
    print(f"done: {n_new} new windows; coverage " + ", ".join(f"{q}:{len(seen.get(q, ()))}" for q in queries[:3]) + " ...")


def rates():
    by = {}
    for l in WIN.read_text().splitlines():
        if l.strip():
            r = json.loads(l); by.setdefault(r["query"], []).append(r["text"])
    return {q: {"n": len(ts), "crisis": sum(bool(CRISIS_RX.search(t)) for t in ts) / len(ts),
                "fin": sum(bool(FIN_RX.search(t)) for t in ts) / len(ts), "pand": sum(bool(PAND_RX.search(t)) for t in ts) / len(ts)}
            for q, ts in by.items() if ts}


def bearish_by_date(row: Path, arm: str):
    out = {}
    for node in (row / arm).glob("rep*/*"):
        f = node / "01_sketches_valid.json"
        if f.exists():
            ds = [s["direction"] for s in json.loads(f.read_text()) if s.get("direction") in ("+", "-")]
            if ds: out.setdefault(node.name, []).extend(ds)
    return {d: v.count("-") / len(v) for d, v in out.items()}


def analyze():
    from scipy.stats import spearmanr
    R = rates(); dates = all_dates()
    S = {d: R[month_phrase(d)]["crisis"] for d in dates if month_phrase(d) in R}
    Sf = {d: R[month_phrase(d)]["fin"] for d in S}
    n = {d: R[month_phrase(d)]["n"] for d in S}
    L = ["# Corpus salience, sampled-window instrument (Infini-gram search_docs, Dolma 1.7; post-freeze exploratory)", "",
         f"months covered: {len(S)}/240, median windows per month: {int(np.median(list(n.values()))) if n else 0}. "
         "S_T = share of sampled 'Month YYYY' windows (+-200 tokens) containing crisis vocabulary.", "",
         "Top months by S_T: " + ", ".join(f"{d[:7]} {S[d]:.2f}" for d in sorted(S, key=lambda d: -S[d])[:10]), "",
         "Crisis-set months: " + ", ".join(f"{d[:7]} {S[d]:.2f}" for d in CRISIS if d in S),
         f"\nmean S_T crisis set {np.mean([S[d] for d in CRISIS if d in S]):.3f} vs calm set {np.mean([S[d] for d in S if d[:4] in CALM_YEARS]):.3f} "
         f"vs all other months {np.mean([S[d] for d in S if d not in CRISIS and d[:4] not in CALM_YEARS]):.3f}", "",
         "| row | rho(h_t, S_T) all dates | p | rho outside crisis set | p | rho(h_t, S_fin) |", "|---|---|---|---|---|---|"]
    rows = []
    for row in sorted(BENCH.iterdir()):
        if not ((row / "D").is_dir() and (row / "M").is_dir()): continue
        D, M = bearish_by_date(row, "D"), bearish_by_date(row, "M")
        cm = [d for d in dates if d in D and d in M and d in S]
        if len(cm) < 200: continue
        h = np.array([D[d] - M[d] for d in cm]); s = np.array([S[d] for d in cm]); sf = np.array([Sf[d] for d in cm])
        r1, p1 = spearmanr(h, s); nc = [i for i, d in enumerate(cm) if d not in CRISIS]
        r2, p2 = spearmanr(h[nc], s[nc]); r3, _ = spearmanr(h, sf)
        rows.append((row.name, r1, p1, r2, p2, r3)); L.append(f"| {row.name} | {r1:+.3f} | {p1:.2g} | {r2:+.3f} | {p2:.2g} | {r3:+.3f} |")
    if rows:
        L += ["", f"**{len(rows)} rows:** median rho(h_t,S_T) = {np.median([r[1] for r in rows]):+.3f}; positive with p<0.05 on "
              f"{sum(1 for r in rows if r[1] > 0 and r[2] < 0.05)}/{len(rows)}; outside the crisis set: median {np.median([r[3] for r in rows]):+.3f}, "
              f"positive with p<0.05 on {sum(1 for r in rows if r[3] > 0 and r[4] < 0.05)}/{len(rows)}."]
    # spatial
    cities = {c: R[CITY_NEEDLE[c]] for c in REGIONS if CITY_NEEDLE[c] in R}
    if cities:
        L += ["", "## Spatial: pandemic association of the region name", "", "| region | n | share of windows with pandemic vocabulary |", "|---|---|---|"]
        for c, v in cities.items(): L.append(f"| {c} | {v['n']} | {v['pand']:.3f} |")
        for tag in ("deepseek-v4-flash", "gemini-2.5-flash-pooled"):
            rj = ST1 / tag / f"{tag}_st1_row.json"
            if rj.exists() and len(cities) == 10:
                lap = json.loads(rj.read_text())["lap"]
                xs = [cities[c]["pand"] for c in REGIONS]; rec = [lap[c]["recall"] for c in REGIONS]; hit = [lap[c]["hit"] for c in REGIONS]
                r1, p1 = spearmanr(xs, rec); r2, p2 = spearmanr(xs, hit)
                L.append(f"\n{tag}: rho(pandemic association, LAP recall) = {r1:+.2f} (p={p1:.2f}); rho(., LAP hit) = {r2:+.2f} (p={p2:.2f}); n=10")
    (OUT / "CORPUS_SALIENCE.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=["probe", "months", "cities", "analyze"], required=True)
    ap.add_argument("--calls", type=int, default=10); ap.add_argument("--budget", type=float, default=None)
    a = ap.parse_args()
    if a.job == "probe":
        sample([month_phrase(d) for d in ("2008-09-15", "2005-03-15", "2014-04-15", "2020-03-15")], 2, a.budget)
        for q, v in rates().items(): print(q, v)
    elif a.job == "months":
        sample([month_phrase(d) for d in all_dates()], a.calls, a.budget)
    elif a.job == "cities":
        sample([CITY_NEEDLE[c] for c in REGIONS], a.calls, a.budget)
    else:
        analyze()


if __name__ == "__main__":
    main()
