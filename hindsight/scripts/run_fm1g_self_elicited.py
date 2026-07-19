#!/usr/bin/env python
"""FM-1g: self-elicited date two-stage experiment (reviewer Q1).

Prereg: FM1g_prereg_self_elicited.md (frozen 10643458, before any call).
Base = frozen M transform VERBATIM (the [undisclosed] date line is kept —
no date is asserted by anyone). A preamble task is appended to the user
prompt:
  GDATE  infer the most likely decision date, output `INFERRED DATE: YYYY-MM`,
         then generate the 8 sketches (no instruction to use the date)
  GNEUT  matched-structure neutral preamble (`SALIENT SERIES: NAME`)
47 window dates x 2 variants x 1 rep, temp 0.2, gemini-2.5-flash.

Usage:
  run_fm1g_self_elicited.py --job smoke    # 2 dates x 2 variants
  run_fm1g_self_elicited.py --job run      # full window (idempotent)
  run_fm1g_self_elicited.py --job analyze  # E2_gdate / E2_gneut vs frozen M
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import (call_gemini, load_api_key, load_nodes,
                                validate_sketches)
from run_fm1_arms import clean_context
from analyze_fm1 import all_dates, gap, CRISIS, CALM_YEARS, load_arm
from hindsight_paths import REPO

OUT = REPO / "hindsight/outputs/fm1g"
M_LINE = ("Decision time point: [undisclosed]. Only information "
          "contained in this snapshot is admissible as evidence.")
SMOKE_DATES = ("2008-10-15", "2014-04-15")
B, SEED = 10_000, 2026
PREREG = "FM1g_prereg_self_elicited.md 10643458"

# Addendum 798f5fb0: the frozen system contract ("a single JSON array,
# nothing else") suppresses prose preambles, so the elicited value rides as
# the ARRAY'S FIRST ELEMENT instead; estimands unchanged.
PREAMBLE = {
    "GDATE": (
        "\n\nAdditional requirement: from the snapshot alone, first infer "
        "the single most likely decision date. Output one single JSON array "
        "whose FIRST element is exactly of the form "
        '{"inferred_decision_date": "YYYY-MM"} and whose remaining elements '
        "are the 8 hypothesis sketches exactly as specified above."),
    "GNEUT": (
        "\n\nAdditional requirement: from the snapshot alone, first "
        "identify the single series with the largest recent change. Output "
        "one single JSON array whose FIRST element is exactly of the form "
        '{"salient_series": "NAME"} and whose remaining elements are the 8 '
        "hypothesis sketches exactly as specified above."),
}
INFER_RX = re.compile(r'"inferred_decision_date"\s*:\s*"(\d{4})-(\d{2})"')


def window_dates() -> list[str]:
    return sorted(set(CRISIS) | {d for d in all_dates() if d[:4] in CALM_YEARS})


def variant_prompt(node: dict, kind: str) -> str:
    masked = clean_context(node["orig_user"], node["decision_date"], "none")
    assert M_LINE in masked, f"M date line not found for {node['decision_date']}"
    return masked + PREAMBLE[kind]


async def run(dates: list[str], concurrency: int,
              max_tokens: int = 8192) -> None:
    nodes = {n["decision_date"]: n for n in load_nodes()}
    key = load_api_key()
    sem = asyncio.Semaphore(concurrency)
    jobs = [(d, v) for d in dates for v in ("GDATE", "GNEUT")]

    async def cell(d, v):
        cdir = OUT / v / "rep1" / d
        if (cdir / "01_sketches_valid.json").exists():
            return "SKIP"
        prompt = variant_prompt(nodes[d], v)
        async with sem:
            raw, mv = await call_gemini(client, key, nodes[d]["system"], prompt,
                                        temperature=0.2, max_tokens=max_tokens)
        valid, invalid = validate_sketches(raw, d)
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "04_raw_response.txt").write_text(raw)
        (cdir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
        (cdir / "03_run_meta.json").write_text(json.dumps({
            "decision_date": d, "variant": v, "model_reported": mv,
            "valid_count": len(valid), "invalid_count": invalid,
            "max_tokens": max_tokens,
            "prereg": PREREG}))
        return f"OK {v}/{d} n={len(valid)}"

    async with httpx.AsyncClient(timeout=240.0) as c:
        global client
        client = c
        rs = await asyncio.gather(*(cell(d, v) for d, v in jobs),
                                  return_exceptions=True)
    for r in rs:
        if isinstance(r, Exception):
            print("CELL_ERROR:", r, file=sys.stderr)
    ok = sum(1 for r in rs if isinstance(r, str) and r.startswith("OK"))
    skip = sum(1 for r in rs if r == "SKIP")
    print(f"fm1g: {ok} ok, {skip} skip, {len(rs)-ok-skip} err")


def load_variant(v: str) -> dict:
    bd = {}
    for node in (OUT / v / "rep1").glob("*"):
        f = node / "01_sketches_valid.json"
        if f.exists():
            bd[node.name] = [s["direction"] for s in json.loads(f.read_text())
                             if s.get("direction") in ("+", "-")]
    return bd


def inferred_dates(v: str = "GDATE") -> dict:
    out = {}
    for node in (OUT / v / "rep1").glob("*"):
        f = node / "04_raw_response.txt"
        if f.exists():
            m = INFER_RX.search(f.read_text())
            out[node.name] = f"{m.group(1)}-{m.group(2)}" if m else None
    return out


def analyze() -> None:
    win = window_dates()
    crisis, calm = list(CRISIS), [d for d in win if d not in set(CRISIS)]
    D = load_arm("gemini-2.5-flash", "D")
    M = load_arm("gemini-2.5-flash", "M")

    def boot(A, Bm):
        rng = np.random.default_rng(SEED)
        bs = []
        for _ in range(B):
            c = [crisis[i] for i in rng.integers(0, len(crisis), len(crisis))]
            q = [calm[i] for i in rng.integers(0, len(calm), len(calm))]
            bs.append(gap(A, c, q) - gap(Bm, c, q))
        return (float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5)))

    res = {"prereg": PREREG, "window_n": len(win)}
    e2_win = gap(D, crisis, calm) - gap(M, crisis, calm)
    res["E2_win_reference"] = {"est": e2_win, "ci95": list(boot(D, M))}

    for v in ("GDATE", "GNEUT"):
        bd = load_variant(v)
        est = gap(bd, crisis, calm) - gap(M, crisis, calm)
        res[f"E2_{v.lower()}"] = {"est": est, "ci95": list(boot(bd, M)),
                                  "gap_variant": gap(bd, crisis, calm),
                                  "n_dates": len(bd),
                                  "missing": [d for d in win if d not in bd]}

    # secondary: inference accuracy + gap scored by each run's inferred date
    inf = inferred_dates()
    parsed = {d: v for d, v in inf.items() if v}
    exact = sum(1 for d, v in parsed.items() if v == d[:7])
    within12 = sum(1 for d, v in parsed.items()
                   if abs((int(v[:4]) - int(d[:4])) * 12
                          + int(v[5:7]) - int(d[5:7])) <= 12)
    res["inference"] = {"n": len(inf), "parsed": len(parsed),
                        "exact_month": exact, "within_12m": within12}
    bd = load_variant("GDATE")
    cr_i = [d for d, v in parsed.items() if v + "-15" in set(CRISIS)]
    ca_i = [d for d, v in parsed.items() if v[:4] in CALM_YEARS]
    res["gap_by_inferred_date"] = {
        "crisis_labeled_n": len(cr_i), "calm_labeled_n": len(ca_i),
        "gap": gap(bd, cr_i, ca_i) if cr_i and ca_i else None}

    g = res["E2_gdate"]
    lo = g["ci95"][0]
    if lo > 0 and g["est"] >= e2_win - 0.10:
        res["decision"] = "SELF-TRIGGER"
    elif not (lo > 0) and g["est"] < 0.10:
        res["decision"] = "NO-SELF-TRIGGER"
    else:
        res["decision"] = "PARTIAL"
    (OUT / "FM1G_RESULTS.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=["smoke", "run", "analyze"], required=True)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--max-tokens", type=int, default=8192,
                    help="raise for cells whose thinking exhausts the budget "
                         "(deterministic MAX_TOKENS; disclosed per cell)")
    a = ap.parse_args()
    if a.job == "analyze":
        analyze()
        return
    dates = list(SMOKE_DATES) if a.job == "smoke" else window_dates()
    OUT.mkdir(parents=True, exist_ok=True)
    asyncio.run(run(dates, a.concurrency, a.max_tokens))
    if a.job == "smoke":
        for v in ("GDATE", "GNEUT"):
            for d in SMOKE_DATES:
                nd = OUT / v / "rep1" / d
                f = nd / "01_sketches_valid.json"
                if f.exists():
                    dirs = [s["direction"] for s in json.loads(f.read_text())]
                    raw = (nd / "04_raw_response.txt").read_text()
                    m = INFER_RX.search(raw)
                    extra = f" inferred={m.group(1)}-{m.group(2)}" if m else ""
                    print(f"smoke {v}/{d}: dirs={dirs}{extra}")


if __name__ == "__main__":
    main()
