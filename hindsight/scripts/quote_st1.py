#!/usr/bin/env python
"""ST-1 quote: tokens-first (repo convention), USD only at an explicitly labelled list price.

Calibration order: (1) smoke-run ledger records since --since; (2) GD-1 measured profile
(gemini-2.5-flash, 2026-07-03: arms 2425/1979/3284 prompt/output/thoughts; LAP 77/3/354)
scaled by the ST-1/GD-1 prompt-length ratio.

Usage: python quote_st1.py [--since 2026-10-14T00:00] [--in-usd 0.30 --out-usd 2.50]
"""
from __future__ import annotations

import argparse
import json
import statistics as st

from hindsight_paths import REPO

LEDGER = REPO / "hindsight/outputs/gemini_usage_log.jsonl"
N_NODES, N_ARMS, LAP_REPS = 310, 5, 20
GD1 = {"arm": (2425, 1979, 3284), "lap": (77, 3, 354)}
GD1_PROMPT_CHARS, ST1_PROMPT_CHARS = 9200, 6850 + 1100  # user+system, approx


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None)
    ap.add_argument("--in-usd", type=float, default=0.30, help="USD per 1M input tokens (ASSUMED list price, verify)")
    ap.add_argument("--out-usd", type=float, default=2.50, help="USD per 1M output+thinking tokens (ASSUMED, verify)")
    args = ap.parse_args()
    src = "GD-1 calibration (scaled)"
    arm = tuple(round(x * (ST1_PROMPT_CHARS / GD1_PROMPT_CHARS)) if i == 0 else x for i, x in enumerate(GD1["arm"]))
    lap = GD1["lap"]
    rec = (300, 30, 400)  # guess until smoke
    if args.since and LEDGER.exists():
        rs = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
        rs = [r for r in rs if r["ts"] >= args.since]
        a = [r for r in rs if r["prompt"] > 1200]
        s = [r for r in rs if r["prompt"] <= 1200 and r["prompt"] > 150]
        l = [r for r in rs if r["prompt"] <= 150]
        if a and l:
            f = lambda g: (round(st.mean(r["prompt"] for r in g)), round(st.mean(r["output"] for r in g)), round(st.mean(r["thoughts"] for r in g)))
            arm, lap = f(a), f(l)
            rec = f(s) if s else rec
            src = f"smoke ledger since {args.since}: {len(a)} arm / {len(l)} lap / {len(s)} rec calls"
    jobs = {"arms": (N_NODES * N_ARMS, arm), "lap": (N_NODES * LAP_REPS, lap), "rec": (N_NODES, rec)}
    print(f"calibration: {src}")
    print(f"{'job':6s} {'calls':>6s} {'prompt':>8s} {'out+think':>10s} {'USD@assumed':>12s}")
    tot_in = tot_out = tot_usd = 0.0
    for k, (n, (pi, po, pt)) in jobs.items():
        tin, tout = n * pi, n * (po + pt)
        usd = tin / 1e6 * args.in_usd + tout / 1e6 * args.out_usd
        tot_in += tin; tot_out += tout; tot_usd += usd
        print(f"{k:6s} {n:6d} {tin/1e6:7.2f}M {tout/1e6:9.2f}M {usd:12.2f}")
    print(f"{'TOTAL':6s} {sum(v[0] for v in jobs.values()):6d} {tot_in/1e6:7.2f}M {tot_out/1e6:9.2f}M {tot_usd:12.2f}")
    print(f"(USD at ASSUMED ${args.in_usd}/M in, ${args.out_usd}/M out+thinking -- gemini-2.5-flash is 'not on file' "
          f"in price_table.json; verify list price before approving)")


if __name__ == "__main__":
    main()
