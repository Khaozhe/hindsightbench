#!/usr/bin/env python
"""GD-1 second-domain mini panel: 10Y Treasury yield direction (prereg 394c9ad4).

Arms D/M/W x 240 dates x 1 rep + LAP-10Y (240 x 20 reps), gemini-2.5-flash.
Reuses the frozen masking/cleaning/transplant transforms; only the target
sentence differs (SPX forward returns -> 10Y yield direction).

Usage:
  python run_gd1.py --job smoke                # 2 dates x 3 arms + 2 LAP, prints usage-based quote
  python run_gd1.py --job arms [--concurrency 64]
  python run_gd1.py --job lap  [--concurrency 100]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import (call_gemini, load_api_key, load_nodes,
                                validate_sketches)
from run_fm1_arms import clean_context
from analyze_fm1 import fake_map

from hindsight_paths import REPO
OUT = REPO / "hindsight/outputs/gd1"
DGS10 = OUT / "dgs10.csv"

TARGET_OLD = "S&P 500 forward returns"
TARGET_NEW = "the direction of the 10-year U.S. Treasury yield over the next 20 trading days"
SUMMARY_MARK = "## Target Panel Summary"

LAP10_SYSTEM = "You answer questions about historical U.S. Treasury market outcomes. Answer with exactly one word."
LAP10_PROMPT = ("Between {t} and {t_end}, did the 10-year U.S. Treasury constant maturity yield "
                "rise or fall? Answer with exactly one word: rise, fall, or unknown.")
LAP_REPS = 20
ARM_MAX_TOKENS = 8192
LAP_MAX_TOKENS = 2048


def dgs10_dates() -> list[str]:
    with DGS10.open() as f:
        return [row["date"] for row in csv.DictReader(f)]


def yield_end(t: str, dates: list[str]) -> str:
    after = [d for d in dates if d >= t]
    return after[20] if len(after) > 20 else after[-1]


def gd1_system(orig_system: str) -> str:
    assert TARGET_OLD in orig_system, "target sentence not found in system prompt"
    return orig_system.replace(TARGET_OLD, TARGET_NEW)


def gd1_user(node: dict, date_mode: str, fake_date: str | None = None) -> str:
    u = clean_context(node["orig_user"], node["decision_date"], date_mode, fake_date)
    return u.replace("S&P 500 forward returns", "10-year Treasury yield direction (next 20 trading days)")


async def run_arms(concurrency: int, smoke: bool = False) -> None:
    nodes = load_nodes()
    if smoke:
        nodes = [n for n in nodes if n["decision_date"] in ("2008-10-15", "2014-04-15")]
    dates = [n["decision_date"] for n in nodes]
    fmap = fake_map(sorted({n["decision_date"] for n in load_nodes()}))
    api_key = load_api_key()
    sem = asyncio.Semaphore(concurrency)
    jobs = []
    for n in nodes:
        for arm, mode in (("D", "true"), ("M", "none"), ("W", "fake")):
            node_dir = OUT / arm / "rep1" / n["decision_date"]
            if (node_dir / "01_sketches_valid.json").exists():
                continue
            jobs.append((n, arm, mode))
    print(f"gd1 arms: {len(jobs)} cells")

    async def one(n, arm, mode):
        fake = fmap[n["decision_date"]] if mode == "fake" else None
        async with sem:
            raw, mv = await call_gemini(client, api_key, gd1_system(n["system"]),
                                        gd1_user(n, mode, fake),
                                        temperature=0.2, max_tokens=ARM_MAX_TOKENS)
        node_dir = OUT / arm / "rep1" / n["decision_date"]
        node_dir.mkdir(parents=True, exist_ok=True)
        (node_dir / "04_raw_response.txt").write_text(raw)
        try:
            valid, invalid = validate_sketches(raw, n["decision_date"])
        except (json.JSONDecodeError, ValueError) as exc:
            (node_dir / "99_parse_error.txt").write_text(str(exc))
            return "perr"
        (node_dir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
        (node_dir / "03_run_meta.json").write_text(json.dumps({
            "decision_date": n["decision_date"], "arm": arm, "rep": 1,
            "model_reported": mv, "valid_count": len(valid), "invalid_count": invalid,
            "target": "DGS10-20td", "prereg": "GD1_prereg_second_domain.md 394c9ad4",
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        }, indent=2))
        return "ok"

    global client
    limits = httpx.Limits(max_connections=concurrency + 2)
    async with httpx.AsyncClient(timeout=300.0, limits=limits) as client:
        rs = await asyncio.gather(*(one(*j) for j in jobs), return_exceptions=True)
    ok = sum(1 for r in rs if r == "ok")
    perr = sum(1 for r in rs if r == "perr")
    err = sum(1 for r in rs if isinstance(r, Exception))
    print(f"gd1 arms: {ok} ok, {perr} parse_err, {err} err")
    for r in rs:
        if isinstance(r, Exception):
            print("ARM_ERROR:", r, file=sys.stderr)


async def run_lap(concurrency: int, smoke: bool = False) -> None:
    dates = sorted({n["decision_date"] for n in load_nodes()})
    if smoke:
        dates = ["2008-10-15", "2014-04-15"]
    grid = dgs10_dates()
    ends = {t: yield_end(t, grid) for t in dates}
    out_f = OUT / "lap10_results.jsonl"
    done: dict[str, int] = {}
    if out_f.exists():
        for l in out_f.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done[r["decision_date"]] = done.get(r["decision_date"], 0) + 1
    reps = 1 if smoke else LAP_REPS
    jobs = [(t, k) for t in dates for k in range(reps) if k >= done.get(t, 0)]
    print(f"gd1 lap: {len(jobs)} calls")
    api_key = load_api_key()
    sem = asyncio.Semaphore(concurrency)

    async def one(t, k):
        async with sem:
            raw, mv = await call_gemini(client, api_key, LAP10_SYSTEM,
                                        LAP10_PROMPT.format(t=t, t_end=ends[t]),
                                        temperature=1.0, max_tokens=LAP_MAX_TOKENS)
        ans = raw.strip().lower().split()[0].strip('."\'') if raw.strip() else ""
        if ans not in ("rise", "fall", "unknown"):
            ans = "invalid"
        return {"decision_date": t, "rep": k, "answer": ans,
                "raw": raw[:60], "model_reported": mv}

    global client
    limits = httpx.Limits(max_connections=concurrency + 2)
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
    print(f"gd1 lap: {len(rs)-n_err} ok, {n_err} err")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=["smoke", "arms", "lap"], required=True)
    ap.add_argument("--concurrency", type=int, default=64)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.job == "smoke":
        asyncio.run(run_arms(4, smoke=True))
        asyncio.run(run_lap(2, smoke=True))
        print("smoke done -> check outputs/gd1 and gemini_usage_log.jsonl tail for per-call profile")
    elif args.job == "arms":
        asyncio.run(run_arms(args.concurrency))
    else:
        asyncio.run(run_lap(args.concurrency))


if __name__ == "__main__":
    main()
