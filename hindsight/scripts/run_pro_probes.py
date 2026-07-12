#!/usr/bin/env python
"""Recovery + LAP probes for gemini-2.5-pro (completes the pro benchmark row).

Reuses the frozen probe prompts/parsers from run_kt1_masked_arm / run_fm1c;
only the model string differs (disclosed: same protocol, pro endpoint).
Writes outputs/bench/gemini-2.5-pro/{date_probe_results,lap_probe_results}.jsonl.

Usage: python run_pro_probes.py --job rec|lap [--concurrency 100]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import run_kt1_masked_arm as kt

kt.MODEL = "models/gemini-2.5-pro"  # must precede any call_gemini use

from run_kt1_masked_arm import (PROBE_SYSTEM, PROBE_TEMPLATE, call_gemini,
                                extract_snapshot_block, load_api_key)
from run_fm1c import LAP_PROMPT, LAP_SYSTEM, trading_day_end
from run_fm1_arms import clean_context
from run_bench_model import all_bench_nodes

from hindsight_paths import REPO
OUT = REPO / "hindsight/outputs/bench/gemini-2.5-pro"
MAX_TOKENS_REC = 16384  # 23 dates ate the 8192 thought budget whole; single-shot, no retry
MAX_TOKENS_LAP = 4096
LAP_REPS = 20


async def run_rec(concurrency: int) -> None:
    nodes = all_bench_nodes()
    out_f = OUT / "date_probe_results.jsonl"
    done = set()
    if out_f.exists():
        done = {json.loads(l)["decision_date"] for l in out_f.read_text().splitlines() if l.strip()}
    jobs = [n for n in nodes if n["decision_date"] not in done]
    print(f"rec: {len(jobs)} calls (of {len(nodes)})")
    api_key = load_api_key()
    sem = asyncio.Semaphore(concurrency)

    async def one(n):
        snapshot = extract_snapshot_block(clean_context(n["orig_user"], n["decision_date"], "none"))
        async with sem:
            raw, mv = await call_gemini(client, api_key, PROBE_SYSTEM,
                                        PROBE_TEMPLATE.format(snapshot=snapshot),
                                        temperature=0.0, max_tokens=MAX_TOKENS_REC)
        est = None
        try:
            est = json.loads(raw).get("estimated_date")
        except json.JSONDecodeError:
            import re
            m = re.search(r"(19|20)\d{2}-\d{2}", raw)
            est = m.group(0) if m else None
        return {"decision_date": n["decision_date"], "estimated_date": est,
                "raw": raw[:200], "model_version_reported": mv}

    global client
    limits = httpx.Limits(max_connections=concurrency + 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=300.0, limits=limits) as client:
        rs = await asyncio.gather(*(one(n) for n in jobs), return_exceptions=True)
    n_err = 0
    with out_f.open("a") as f:
        for r in rs:
            if isinstance(r, Exception):
                n_err += 1
                print("REC_ERROR:", r, file=sys.stderr)
            else:
                f.write(json.dumps(r) + "\n")
    print(f"rec: {len(rs)-n_err} ok, {n_err} err -> {out_f}")


async def run_lap(concurrency: int) -> None:
    nodes = all_bench_nodes()
    dates = [n["decision_date"] for n in nodes]
    ends = {t: trading_day_end(t) for t in dates}
    out_f = OUT / "lap_probe_results.jsonl"
    done: dict[str, int] = {}
    if out_f.exists():
        for l in out_f.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done[r["decision_date"]] = done.get(r["decision_date"], 0) + 1
    jobs = [(t, k) for t in dates for k in range(LAP_REPS) if k >= done.get(t, 0)]
    print(f"lap: {len(jobs)} calls (of {len(dates)*LAP_REPS})")
    api_key = load_api_key()
    sem = asyncio.Semaphore(concurrency)

    async def one(t, k):
        async with sem:
            raw, mv = await call_gemini(client, api_key, LAP_SYSTEM,
                                        LAP_PROMPT.format(t=t, t_end=ends[t]),
                                        temperature=1.0, max_tokens=MAX_TOKENS_LAP)
        ans = raw.strip().lower().split()[0].strip('."\'') if raw.strip() else ""
        if ans not in ("up", "down", "unknown"):
            ans = "invalid"
        return {"decision_date": t, "rep": k, "answer": ans,
                "raw": raw[:80], "model_version_reported": mv}

    global client
    limits = httpx.Limits(max_connections=concurrency + 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=300.0, limits=limits) as client:
        rs = await asyncio.gather(*(one(t, k) for t, k in jobs), return_exceptions=True)
    n_err = 0
    with out_f.open("a") as f:
        for r in rs:
            if isinstance(r, Exception):
                n_err += 1
                print("LAP_ERROR:", r, file=sys.stderr)
            else:
                f.write(json.dumps(r) + "\n")
    print(f"lap: {len(rs)-n_err} ok, {n_err} err -> {out_f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=["rec", "lap"], required=True)
    ap.add_argument("--concurrency", type=int, default=100)
    ap.add_argument("--confirm-cost", action="store_true",
                    help="required for lap: 5,160 pro calls, user must approve cost first")
    args = ap.parse_args()
    if args.job == "lap" and not args.confirm_cost:
        sys.exit("LAP blocked: pending user cost decision (2026-07-02). Re-run with --confirm-cost.")
    OUT.mkdir(parents=True, exist_ok=True)
    asyncio.run({"rec": run_rec, "lap": run_lap}[args.job](args.concurrency))


if __name__ == "__main__":
    main()
