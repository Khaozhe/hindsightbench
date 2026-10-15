#!/usr/bin/env python
"""Post-freeze exploratory: what the reasoning trace does with (or without) the date. Zero API cost.
Rows whose raw responses keep the <think> block (self-hosted reasoning models). Per row:
  trace_share        : cells with a </think> block
  len_D / len_M      : median trace length (chars), D vs M arm
  M_selfloc_crisis/calm : M-arm traces that name a calendar year (spontaneous self-localization), crisis vs calm dates
  M_year_hit         : among M-arm traces naming a year, share naming the TRUE year (+-1) of the node
  M_crisisvocab_c/q  : M-arm traces using crisis-episode vocabulary, crisis vs calm dates
  D_crisisvocab_c/q  : D-arm traces using crisis-episode vocabulary, crisis vs calm dates
  D_otheryears_c/q   : D-arm traces naming a year other than the stated one (era association), crisis vs calm
  M_bear_selfloc / M_bear_no : M-arm bearish share on nodes whose trace self-localizes vs not (crisis+calm pooled)
Outputs outputs/review/think_traces/THINK_TRACES.md
"""
from __future__ import annotations
import json, re, sys, statistics as st
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, CRISIS, CALM_YEARS  # noqa: E402
from hindsight_paths import REPO  # noqa: E402

BENCH = REPO / "hindsight/outputs/bench"
OUT = REPO / "hindsight/outputs/review/think_traces"
YEAR = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
UNIT_ECHO = re.compile(r"1982-1984|2017 Dollars|2017=100|Chained 2017", re.I)
# episode-matched vocabulary: a crisis date counts as "named" only if the trace names ITS episode
EP = {"gfc": re.compile(r"\b(Lehman|subprime|housing (bubble|crash|collapse)|mortgage crisis|2008 (financial )?crisis|global financial crisis|GFC|TARP|Bear Stearns)\b", re.I),
      "covid": re.compile(r"\b(pandemic|COVID|coronavirus|lockdown)\b", re.I),
      "infl22": re.compile(r"\b(inflation (surge|spike|shock)|aggressive (rate )?hikes?|Fed (tightening|hiking)|75 basis|Ukraine|energy (shock|prices))\b", re.I)}
ANY_EP = re.compile("|".join(r.pattern for r in EP.values()), re.I)
def episode_of(d): return "gfc" if d < "2010" else ("covid" if d.startswith("2020") else "infl22")
GUESS = re.compile(r"\b(looks like|consistent with|resembl|likely (in|around|the)|suggests? (the|a) (period|year|era)|"
                   r"reminiscent|similar to (the )?(20\d\d|19\d\d|period))\b", re.I)


def cells(row, arm):
    out = {}
    for rep in sorted((row / arm).glob("rep*")):
        for node in rep.iterdir():
            raw = node / "04_raw_response.txt"; val = node / "01_sketches_valid.json"
            if raw.exists() and val.exists():
                t = raw.read_text(errors="ignore")
                if "</think>" in t:
                    think = t.split("</think>")[0]
                    dirs = [s["direction"] for s in json.loads(val.read_text()) if s.get("direction") in ("+", "-")]
                    out[node.name] = (think, dirs)
    return out


def years(text):
    return {int(y) for y in YEAR.findall(UNIT_ECHO.sub(" ", text))}


def rate(cs, dates, pred):
    xs = [cs[d] for d in dates if d in cs]
    return (sum(1 for x in xs if pred(x)) / len(xs)) if xs else float("nan"), len(xs)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dates = all_dates(); calm = [d for d in dates if d[:4] in CALM_YEARS]
    rows = []
    for row in sorted(BENCH.iterdir()):
        if not all((row / a).is_dir() for a in ("D", "M")): continue
        D, M = cells(row, "D"), cells(row, "M")
        if len(M) < 100: continue
        selfloc = lambda c: bool(years(c[0]))
        def ep_rate(C):
            xs = [(d, C[d]) for d in CRISIS if d in C]
            return (sum(1 for d, c in xs if EP[episode_of(d)].search(c[0])) / len(xs)) if xs else float("nan")
        vocab = lambda c: bool(ANY_EP.search(c[0]))
        r = {"model": row.name, "n_D": len(D), "n_M": len(M),
             "len_D": st.median(len(c[0]) for c in D.values()), "len_M": st.median(len(c[0]) for c in M.values()),
             "M_selfloc_c": rate(M, CRISIS, selfloc)[0], "M_selfloc_q": rate(M, calm, selfloc)[0],
             "M_guess_c": rate(M, CRISIS, lambda c: bool(GUESS.search(c[0])))[0], "M_guess_q": rate(M, calm, lambda c: bool(GUESS.search(c[0])))[0],
             "M_vocab_c": ep_rate(M), "M_vocab_q": rate(M, calm, vocab)[0],
             "D_vocab_c": ep_rate(D), "D_vocab_q": rate(D, calm, vocab)[0]}
        # true-year hit among self-localizing M traces (year within +-1 of node's year)
        hits = [(abs(min(years(c[0]), key=lambda y: abs(y - int(d[:4]))) - int(d[:4])) <= 1) for d, c in M.items() if years(c[0])]
        r["M_year_hit"] = sum(hits) / len(hits) if hits else float("nan"); r["M_selfloc_n"] = len(hits)
        # D arm: other-year mentions (era association) beyond the stated year
        other = lambda d: (lambda c: bool(years(c[0]) - {int(d[:4]), int(d[:4]) - 1, int(d[:4]) + 1}))
        r["D_other_c"] = (sum(1 for d in CRISIS if d in D and other(d)(D[d])) / max(1, sum(1 for d in CRISIS if d in D)))
        r["D_other_q"] = (sum(1 for d in calm if d in D and other(d)(D[d])) / max(1, sum(1 for d in calm if d in D)))
        # bearish share conditional on self-localization (M arm, all pre-cutoff dates)
        b_s = [x for d, c in M.items() if selfloc(c) for x in c[1]]; b_n = [x for d, c in M.items() if not selfloc(c) for x in c[1]]
        r["M_bear_selfloc"] = (b_s.count("-") / len(b_s)) if b_s else float("nan"); r["M_bear_no"] = (b_n.count("-") / len(b_n)) if b_n else float("nan")
        rows.append(r)
    f = lambda x: "nan" if x != x else f"{x:.2f}"
    L = ["# Reasoning traces and the date (post-freeze exploratory; zero API cost)", "",
         "Rows whose raw responses keep the <think> block. selfloc: M-arm trace names a calendar year (unit echoes removed); "
         "year hit: the named year is within +-1 of the node's true year; vocab on crisis dates: the trace names THAT date's episode "
         "(Lehman/subprime; pandemic/COVID/lockdown; inflation surge/Fed hikes), on calm dates: any episode; "
         "D other-years: D-arm trace names a year beyond the stated one (+-1). c = crisis dates, q = calm dates.", "",
         "| model | cells D/M | len D/M (chars) | M selfloc c/q | M year hit (n) | M guess c/q | M vocab c/q | D vocab c/q | D other-years c/q | M bearish selfloc vs not |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['model']} | {r['n_D']}/{r['n_M']} | {int(r['len_D'])}/{int(r['len_M'])} | {f(r['M_selfloc_c'])}/{f(r['M_selfloc_q'])} | "
                 f"{f(r['M_year_hit'])} ({r['M_selfloc_n']}) | {f(r['M_guess_c'])}/{f(r['M_guess_q'])} | {f(r['M_vocab_c'])}/{f(r['M_vocab_q'])} | "
                 f"{f(r['D_vocab_c'])}/{f(r['D_vocab_q'])} | {f(r['D_other_c'])}/{f(r['D_other_q'])} | {f(r['M_bear_selfloc'])} vs {f(r['M_bear_no'])} |")
    (OUT / "THINK_TRACES.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
    (OUT / "think_traces_rows.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
