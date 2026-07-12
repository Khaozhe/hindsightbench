#!/usr/bin/env python
"""FM-1e trigger decomposition: bare date vs retrospective framing.

Prereg: FM1e_prereg_trigger_decomposition.md (frozen 0c6c2a56).
Base = frozen M transform; variants swap M's date line only:
  DBARE  "Decision time point: {d}."
  DSNAP  "Decision time point: {d}. Only information contained in this
          snapshot is admissible as evidence."
47 window dates x 1 rep, temp 0.2, gemini-2.5-flash (identical to FM-1).

Usage:
  run_fm1e_trigger_decomp.py --job smoke     # 2 dates x 2 variants, print
  run_fm1e_trigger_decomp.py --job run       # full window (idempotent)
  run_fm1e_trigger_decomp.py --job analyze   # E2_bare / E2_snap vs E2_win
"""

from __future__ import annotations

import argparse
import asyncio
import json
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

OUT = REPO / "hindsight/outputs/fm1e"
M_LINE = ("Decision time point: [undisclosed]. Only information "
          "contained in this snapshot is admissible as evidence.")
SMOKE_DATES = ("2008-10-15", "2014-04-15")
B, SEED = 10_000, 2026


def window_dates() -> list[str]:
    return sorted(set(CRISIS) | {d for d in all_dates() if d[:4] in CALM_YEARS})


def variant_prompt(node: dict, kind: str) -> str:
    masked = clean_context(node["orig_user"], node["decision_date"], "none")
    assert M_LINE in masked, f"M date line not found for {node['decision_date']}"
    d = node["decision_date"]
    if kind == "DBARE":
        repl = f"Decision time point: {d}."
    else:
        repl = (f"Decision time point: {d}. Only information contained "
                "in this snapshot is admissible as evidence.")
    return masked.replace(M_LINE, repl, 1)


async def run(dates: list[str], concurrency: int) -> None:
    nodes = {n["decision_date"]: n for n in load_nodes()}
    key = load_api_key()
    sem = asyncio.Semaphore(concurrency)
    jobs = [(d, v) for d in dates for v in ("DBARE", "DSNAP")]

    async def cell(d, v):
        cdir = OUT / v / "rep1" / d
        if (cdir / "01_sketches_valid.json").exists():
            return "SKIP"
        prompt = variant_prompt(nodes[d], v)
        async with sem:
            raw, mv = await call_gemini(client, key, nodes[d]["system"], prompt,
                                        temperature=0.2, max_tokens=8192)
        valid, invalid = validate_sketches(raw, d)
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "04_raw_response.txt").write_text(raw)
        (cdir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
        (cdir / "03_run_meta.json").write_text(json.dumps({
            "decision_date": d, "variant": v, "model_reported": mv,
            "valid_count": len(valid), "invalid_count": invalid,
            "prereg": "FM1e_prereg_trigger_decomposition.md 0c6c2a56"}))
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
    print(f"fm1e: {ok} ok, {skip} skip, {len(rs)-ok-skip} err")


def load_variant(v: str) -> dict:
    bd = {}
    for node in (OUT / v / "rep1").glob("*"):
        f = node / "01_sketches_valid.json"
        if f.exists():
            bd[node.name] = [s["direction"] for s in json.loads(f.read_text())
                             if s.get("direction") in ("+", "-")]
    return bd


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

    res = {"prereg": "FM1e 0c6c2a56", "window_n": len(win)}
    e2_win = gap(D, crisis, calm) - gap(M, crisis, calm)
    res["E2_win_reference"] = {"est": e2_win, "ci95": list(boot(D, M))}
    for v in ("DBARE", "DSNAP"):
        bd = load_variant(v)
        missing = [d for d in win if d not in bd]
        est = gap(bd, crisis, calm) - gap(M, crisis, calm)
        res[f"E2_{v.lower()}"] = {"est": est, "ci95": list(boot(bd, M)),
                                  "gap_variant": gap(bd, crisis, calm),
                                  "n_dates": len(bd), "missing": missing}
    ref = res["E2_win_reference"]["est"]
    snap = res["E2_dsnap"]
    lo = snap["ci95"][0]
    res["decision"] = ("DATE-TOKEN-ALONE" if (lo > 0 and snap["est"] >= ref - 0.10)
                       else "CONDITION-ON-FRAMING")
    (OUT / "FM1E_RESULTS.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=["smoke", "run", "analyze"], required=True)
    ap.add_argument("--concurrency", type=int, default=16)
    a = ap.parse_args()
    if a.job == "analyze":
        analyze()
        return
    dates = list(SMOKE_DATES) if a.job == "smoke" else window_dates()
    OUT.mkdir(parents=True, exist_ok=True)
    asyncio.run(run(dates, a.concurrency))
    if a.job == "smoke":
        for v in ("DBARE", "DSNAP"):
            for d in SMOKE_DATES:
                f = OUT / v / "rep1" / d / "01_sketches_valid.json"
                if f.exists():
                    dirs = [s["direction"] for s in json.loads(f.read_text())]
                    print(f"smoke {v}/{d}: dirs={dirs}")


if __name__ == "__main__":
    main()
