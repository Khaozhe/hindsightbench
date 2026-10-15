#!/usr/bin/env python
"""Post-freeze exploratory: does the date move WHICH series the model blames, not only the direction?
Reads candidate_proxies from every valid sketch of every full row (D/M/W). Zero API cost.
Outputs outputs/review/proxy_attribution/PROXY_ATTRIBUTION.md (+ per-row csv).

Measures (per row):
  JSD_crisis / JSD_calm : Jensen-Shannon divergence between D and M proxy distributions, pooled over crisis vs calm dates
  HOUST_gfc  (D - M)    : share of HOUST among proxies on the six GFC crisis dates, D minus M        (housing stereotype)
  CPI_22     (D - M)    : share of CPIAUCSL on the three 2022 inflation dates, D minus M              (inflation stereotype)
  LAB_covid  (D - M)    : share of UNRATE+PAYEMS on the two COVID dates, D minus M                    (labor-shock stereotype)
  HOUST_Wgfc            : W-arm HOUST share on nodes whose ASSERTED date is a GFC month minus the same nodes' D-arm share (hijack)
  dH_crisis / dH_calm   : mean per-node Shannon entropy of the proxy multiset, D minus M (negative = collapse)
"""
from __future__ import annotations
import csv, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map, CRISIS, CALM_YEARS  # noqa: E402
from hindsight_paths import REPO  # noqa: E402

BENCH = REPO / "hindsight/outputs/bench"
OUT = REPO / "hindsight/outputs/review/proxy_attribution"
SERIES = ["GDPC1", "CPIAUCSL", "PAYEMS", "INDPRO", "RSAFS", "UNRATE", "HOUST", "FEDFUNDS"]
GFC = [d for d in CRISIS if d < "2010"]; COVID = [d for d in CRISIS if d.startswith("2020")]; INFL = [d for d in CRISIS if d.startswith("2022")]


def load(row, arm):
    by = defaultdict(list)
    for rep in sorted((row / arm).glob("rep*")):
        for node in rep.iterdir():
            f = node / "01_sketches_valid.json"
            if f.exists():
                for s in json.loads(f.read_text()):
                    by[node.name].append([p for p in s.get("candidate_proxies", []) if p in SERIES])
    return by


def dist(by, dates):
    c = Counter(p for d in dates for sk in by.get(d, []) for p in sk)
    n = sum(c.values())
    return {s: c[s] / n for s in SERIES} if n else None


def share(by, dates, keys):
    c = Counter(p for d in dates for sk in by.get(d, []) for p in sk); n = sum(c.values())
    return sum(c[k] for k in keys) / n if n else float("nan")


def jsd(p, q):
    if p is None or q is None: return float("nan")
    m = {s: (p[s] + q[s]) / 2 for s in SERIES}
    kl = lambda a, b: sum(a[s] * math.log2(a[s] / b[s]) for s in SERIES if a[s] > 0)
    return (kl(p, m) + kl(q, m)) / 2


def entropy(by, dates):
    hs = []
    for d in dates:
        c = Counter(p for sk in by.get(d, []) for p in sk); n = sum(c.values())
        if n: hs.append(-sum(v / n * math.log2(v / n) for v in c.values()))
    return sum(hs) / len(hs) if hs else float("nan")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dates = all_dates(); calm = [d for d in dates if d[:4] in CALM_YEARS]; fmap = fake_map(dates); inv = {v: k for k, v in fmap.items()}
    w_gfc_nodes = [inv[d] for d in GFC if d in inv]   # true nodes whose asserted date is a GFC month
    rows = []
    for row in sorted(BENCH.iterdir()):
        if not all((row / a).is_dir() for a in ("D", "M", "W")): continue
        D, M, W = load(row, "D"), load(row, "M"), load(row, "W")
        if len(D) < 200: continue
        r = {"model": row.name,
             "JSD_crisis": jsd(dist(D, CRISIS), dist(M, CRISIS)), "JSD_calm": jsd(dist(D, calm), dist(M, calm)),
             "HOUST_gfc": share(D, GFC, ["HOUST"]) - share(M, GFC, ["HOUST"]),
             "CPI_22": share(D, INFL, ["CPIAUCSL"]) - share(M, INFL, ["CPIAUCSL"]),
             "LAB_covid": share(D, COVID, ["UNRATE", "PAYEMS"]) - share(M, COVID, ["UNRATE", "PAYEMS"]),
             "HOUST_Wgfc": share(W, w_gfc_nodes, ["HOUST"]) - share(D, w_gfc_nodes, ["HOUST"]),
             "dH_crisis": entropy(D, CRISIS) - entropy(M, CRISIS), "dH_calm": entropy(D, calm) - entropy(M, calm),
             "H_M_crisis": entropy(M, CRISIS), "H_D_crisis": entropy(D, CRISIS)}
        rows.append(r)
    with (OUT / "proxy_attribution_rows.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    f = lambda x: "nan" if x != x else f"{x:+.3f}"
    L = ["# Proxy attribution under the date (post-freeze exploratory; zero API cost)", "",
         "JSD: divergence of the D-arm proxy distribution from the M-arm one (crisis vs calm dates). HOUST_gfc / CPI_22 / LAB_covid: "
         "D-minus-M share of the period-stereotype series on that episode's crisis dates. HOUST_Wgfc: W-arm HOUST share on nodes whose "
         "asserted date is a GFC month, minus the same nodes' D-arm share (hijack by a false date). dH: per-node proxy entropy, D minus M.", "",
         "| model | JSD crisis / calm | HOUST gfc | CPI 2022 | labor covid | HOUST W-gfc | dH crisis / calm | H(M) crisis |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -(r["JSD_crisis"] if r["JSD_crisis"] == r["JSD_crisis"] else -1)):
        L.append(f"| {r['model']} | {r['JSD_crisis']:.3f} / {r['JSD_calm']:.3f} | {f(r['HOUST_gfc'])} | {f(r['CPI_22'])} | {f(r['LAB_covid'])} | "
                 f"{f(r['HOUST_Wgfc'])} | {f(r['dH_crisis'])} / {f(r['dH_calm'])} | {r['H_M_crisis']:.2f} |")
    n = len(rows)
    L += ["", f"**Summary over {n} rows:** JSD crisis > calm on {sum(1 for r in rows if r['JSD_crisis'] > r['JSD_calm'])}/{n}; "
          f"HOUST_gfc > 0 on {sum(1 for r in rows if r['HOUST_gfc'] > 0)}/{n}; CPI_22 > 0 on {sum(1 for r in rows if r['CPI_22'] > 0)}/{n}; "
          f"labor_covid > 0 on {sum(1 for r in rows if r['LAB_covid'] > 0)}/{n}; HOUST hijack by a false GFC date > 0 on "
          f"{sum(1 for r in rows if r['HOUST_Wgfc'] > 0)}/{n}; entropy drop on crisis dates (dH_crisis < 0) on {sum(1 for r in rows if r['dH_crisis'] < 0)}/{n}, "
          f"on calm dates {sum(1 for r in rows if r['dH_calm'] < 0)}/{n}."]
    (OUT / "PROXY_ATTRIBUTION.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


if __name__ == "__main__":
    main()
