#!/usr/bin/env python
"""Geo-entity audit of frozen BM-1 transcripts (zero API cost; post-freeze exploratory).

Question: does the date trigger carry a *spatial* narrative? For every row with full
D/M/W arms, scan the free-text fields of each valid sketch for non-US place terms tied to
dated episodes, and contrast arms:
  A. geo-reference rate per arm (share of sketches naming any non-US place)
  B. episode-place coupling on the COVID crisis nodes (2020-03/04): China/Wuhan/Italy/Europe
     mention rate, D vs M (and 2022 nodes: Russia/Ukraine/Europe)
  C. W arm: coupling keyed on the ASSERTED (fake) date vs the TRUE date
  D. anachronism: (place, episode) mentions in D whose episode starts after the true date
Outputs: outputs/review/geo_audit/geo_audit_rows.csv, GEO_AUDIT.md
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map  # noqa: E402
from hindsight_paths import REPO  # noqa: E402

BENCH = REPO / "hindsight/outputs/bench"
OUT = REPO / "hindsight/outputs/review/geo_audit"
FIELDS = ("mechanism_narrative", "candidate_trigger", "regime_hint", "failure_condition")

# place-term -> (place key, episode windows [start, end] in YYYY-MM where the place is topical)
GAZ = {
    r"\b(China|Chinese|Wuhan|Beijing|Shanghai)\b": ("china", [("2015-08", "2016-02"), ("2018-03", "2019-12"), ("2020-01", "2020-06")]),
    r"\b(Italy|Italian|Lombardy|Milan)\b": ("italy", [("2011-07", "2012-07"), ("2020-02", "2020-05")]),
    r"\b(Greece|Greek)\b": ("greece", [("2010-04", "2012-06"), ("2015-06", "2015-08")]),
    r"\b(Europe|European|Eurozone|euro[- ]area|ECB)\b": ("europe", [("2010-04", "2012-09"), ("2020-03", "2020-05"), ("2022-03", "2022-12")]),
    r"\b(Japan|Japanese|Fukushima|Tokyo|BoJ|Bank of Japan)\b": ("japan", [("2011-03", "2011-06"), ("2013-04", "2013-06")]),
    r"\b(UK|U\.K\.|United Kingdom|Britain|British|Brexit|London|Bank of England|BoE)\b": ("uk", [("2016-06", "2016-12"), ("2022-09", "2022-10")]),
    r"\b(Russia|Russian|Ukraine|Ukrainian|Crimea|Moscow)\b": ("russia_ukraine", [("2014-03", "2014-12"), ("2022-02", "2022-12")]),
    r"\b(Middle East|Saudi|OPEC|Iran|Iraq|Gulf|Persian)\b": ("mideast_oil", [("2008-05", "2008-08"), ("2014-11", "2016-02"), ("2019-09", "2019-10"), ("2022-03", "2022-07")]),
    r"\b(Silicon Valley|SVB|Credit Suisse|Swiss)\b": ("svb_cs", [("2023-03", "2023-05")]),
    r"\b(Iceland|Icelandic)\b": ("iceland", [("2008-10", "2009-01")]),
    r"\b(Cyprus|Cypriot)\b": ("cyprus", [("2013-03", "2013-04")]),
    r"\b(Turkey|Turkish|Argentina|Argentine)\b": ("turkey_arg", [("2018-08", "2018-10")]),
    r"\b(Hong Kong)\b": ("hongkong", [("2019-06", "2019-12")]),
    r"\b(emerging[- ]market\w*|EM economies|Asia(n)? (crisis|markets|economies))\b": ("em_asia", [("2013-05", "2013-09"), ("2015-08", "2016-02"), ("2018-05", "2018-10")]),
    r"\b(global|worldwide|international)\b": ("global", []),   # counted for A only, no episode
}
GAZ_C = [(re.compile(p, re.I), k, w) for p, (k, w) in GAZ.items()]
COVID_TRUE = {"2020-03-15", "2020-04-15"}
INFL22_TRUE = {"2022-06-15", "2022-09-15", "2022-10-15"}
COVID_KEYS, INFL_KEYS = {"china", "italy", "europe"}, {"russia_ukraine", "europe", "mideast_oil"}
# event vocabulary (non-spatial) for the contrast "events named, places not"
EVENT_RE = {"covid": re.compile(r"\b(COVID|coronavirus|pandemic|lockdown)", re.I),
            "infl22": re.compile(r"\b(war|invasion|energy (price|shock)|supply[- ]chain)", re.I),
            "gfc": re.compile(r"\b(Lehman|subprime|financial crisis|credit crisis|TARP)", re.I)}


def ym(d: str) -> str:
    return d[:7]


def scan(sketch: dict) -> set[str]:
    txt = " ".join(str(sketch.get(f, "")) for f in FIELDS) + " " + " ".join(map(str, sketch.get("evidence_refs", [])))
    keys = {k for rx, k, _ in GAZ_C if rx.search(txt)}
    keys |= {"EV_" + k for k, rx in EVENT_RE.items() if rx.search(txt)}
    return keys


def anachronistic(keys: set[str], true_date: str) -> set[str]:
    """place keys whose EVERY episode window starts after the true date (knowledge of the future)."""
    out = set()
    for _, k, wins in GAZ_C:
        if k in keys and wins and all(ws > ym(true_date) for ws, _ in wins):
            out.add(k)
    return out


def load_arm(row: Path, arm: str) -> dict[str, list[set[str]]]:
    by_date = defaultdict(list)
    for rep in sorted((row / arm).glob("rep*")):
        for node in rep.iterdir():
            f = node / "01_sketches_valid.json"
            if f.exists():
                for s in json.loads(f.read_text()):
                    by_date[node.name].append(scan(s))
    return by_date


def rate(by_date, dates, pred) -> tuple[float, int]:
    xs = [s for d in dates for s in by_date.get(d, [])]
    return (sum(1 for s in xs if pred(s)) / len(xs) if xs else float("nan")), len(xs)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dates = all_dates()
    fmap = fake_map(dates)
    inv = {v: k for k, v in fmap.items()}      # fake date -> true date
    rows = []
    for row in sorted(BENCH.iterdir()):
        if not all((row / a).is_dir() for a in ("D", "M", "W")):
            continue
        D, M, W = (load_arm(row, a) for a in ("D", "M", "W"))
        if len(D) < 200:
            continue   # skip smoke / reduced rows
        nonus = lambda s: bool({k for k in s if not k.startswith("EV_")} - {"global"})
        ev_covid = lambda s: "EV_covid" in s
        ev_infl = lambda s: "EV_infl22" in s
        e_d, _ = rate(D, COVID_TRUE, ev_covid); e_m, _ = rate(M, COVID_TRUE, ev_covid)
        e_d22, _ = rate(D, INFL22_TRUE, ev_infl); e_m22, _ = rate(M, INFL22_TRUE, ev_infl)
        w_fake_covid0 = [inv[d] for d in COVID_TRUE if d in inv]
        e_wf, _ = rate(W, w_fake_covid0, ev_covid); e_wt, _ = rate(W, COVID_TRUE, ev_covid)
        a_d, n_d = rate(D, dates, nonus)
        a_m, n_m = rate(M, dates, nonus)
        a_w, n_w = rate(W, dates, nonus)
        covid = lambda s: bool(s & COVID_KEYS)
        infl = lambda s: bool(s & INFL_KEYS)
        b_d, _ = rate(D, COVID_TRUE, covid)
        b_m, _ = rate(M, COVID_TRUE, covid)
        b_d22, _ = rate(D, INFL22_TRUE, infl)
        b_m22, _ = rate(M, INFL22_TRUE, infl)
        # C: W arm. fake-keyed: W cells whose ASSERTED date is a COVID month (true = inv[fake])
        w_fake_covid = [inv[d] for d in COVID_TRUE if d in inv]
        c_fake, _ = rate(W, w_fake_covid, covid)
        c_true, _ = rate(W, COVID_TRUE, covid)   # true date COVID, asserted date elsewhere
        # D: anachronism rate in D arm (any sketch naming a place whose episodes all lie in the future)
        an = [bool(anachronistic(s, d)) for d in dates for s in D.get(d, [])]
        d_an = sum(an) / len(an) if an else float("nan")
        an_m = [bool(anachronistic(s, d)) for d in dates for s in M.get(d, [])]
        m_an = sum(an_m) / len(an_m) if an_m else float("nan")
        rows.append({"model": row.name, "n_sketch_D": n_d, "A_geo_D": a_d, "A_geo_M": a_m, "A_geo_W": a_w,
                     "B_covid_D": b_d, "B_covid_M": b_m, "B_infl22_D": b_d22, "B_infl22_M": b_m22,
                     "C_W_fakeCOVID": c_fake, "C_W_trueCOVID": c_true,
                     "D_anachr_D": d_an, "D_anachr_M": m_an,
                     "EV_covid_D": e_d, "EV_covid_M": e_m, "EV_infl22_D": e_d22, "EV_infl22_M": e_m22,
                     "EV_W_fakeCOVID": e_wf, "EV_W_trueCOVID": e_wt})
    with (OUT / "geo_audit_rows.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    L = ["# Geo-entity audit (post-freeze exploratory; zero API cost)", "",
         "A: share of sketches naming a non-US place (any arm). B: on COVID crisis nodes (2020-03/04), share naming "
         "China/Wuhan/Italy/Europe; on 2022 nodes, Russia/Ukraine/Europe/oil. C: W arm, same COVID-place rate keyed on the "
         "asserted (fake) date vs the true date. D: share of D-arm sketches naming a place whose dated episodes all lie "
         "after the true decision date (M arm as floor).", "",
         "EV columns: the same contrasts for EVENT words (COVID/pandemic/lockdown; war/energy shock) -- the non-spatial face.", "",
         "| model | n | A geo D / M / W | B covid-place D / M | EV covid-event D / M | EV W fake / true | B 2022-place D / M | EV 2022-event D / M | D anachr D / M |", "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -(r["EV_covid_D"] - r["EV_covid_M"]) if r["EV_covid_D"] == r["EV_covid_D"] else 0):
        g = lambda k: f"{r[k]:.2f}" if r[k] == r[k] else "nan"
        L.append(f"| {r['model']} | {r['n_sketch_D']} | {g('A_geo_D')} / {g('A_geo_M')} / {g('A_geo_W')} | {g('B_covid_D')} / {g('B_covid_M')} "
                 f"| {g('EV_covid_D')} / {g('EV_covid_M')} | {g('EV_W_fakeCOVID')} / {g('EV_W_trueCOVID')} "
                 f"| {g('B_infl22_D')} / {g('B_infl22_M')} | {g('EV_infl22_D')} / {g('EV_infl22_M')} | {g('D_anachr_D')} / {g('D_anachr_M')} |")
    tot = len(rows)
    zero_geo = sum(1 for r in rows if r["A_geo_D"] == 0 and r["A_geo_M"] == 0 and r["A_geo_W"] == 0)
    L += ["", f"**Summary:** {zero_geo}/{tot} rows name no non-US place in any arm; event words are present on the COVID nodes "
          f"in {sum(1 for r in rows if r['EV_covid_D'] > r['EV_covid_M'])}/{tot} rows (D > M). The date trigger retrieves "
          "episodes, not geography, on this US-macro task: the spatial dimension cannot be mined from these transcripts and must "
          "come from a spatially indexed carrier task (ST-1)."]
    (OUT / "GEO_AUDIT.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
