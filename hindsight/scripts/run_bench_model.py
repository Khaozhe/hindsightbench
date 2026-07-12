#!/usr/bin/env python
"""HindsightBench per-model runner (prereg: BM1_prereg.md).

Runs the frozen four-arm matrix (2 reps x [240 pre + 18 post] dates), the
date-recovery probe (258 x 1), and the LAP probe (258 x 20) against any
OpenAI-compatible provider.

Usage:
  python run_bench_model.py --provider deepseek --model deepseek-v4-flash --smoke
  python run_bench_model.py --provider deepseek --model deepseek-v4-flash --job arms
  python run_bench_model.py --provider deepseek --model deepseek-v4-flash --job probes
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import load_nodes, validate_sketches
from run_kt1_masked_arm import PROBE_SYSTEM, PROBE_TEMPLATE, extract_snapshot_block
from run_fm1_arms import clean_context
from run_fm1c import build_postcutoff_nodes, LAP_PROMPT, LAP_SYSTEM, trading_day_end, CRISIS, CALM_ANCHORS
from llm_adapters import call_openai_compat, strip_fences

from hindsight_paths import REPO
BENCH = REPO / "hindsight/outputs/bench"
FAKE_SHIFT = 66
PREREG = "BM1_prereg.md"
WINDOWS_ONLY = False
N_REPS = 2
LAP_REPS = 20
LAP_ONLY = False
# vLLM enforces prompt + max_tokens <= max_model_len (400 otherwise); API providers
# treat it as an output cap only. Self-hosted tiers therefore pass --arm-max-tokens
# 8192 (frozen fp8-row outputs max out ~7k tokens, so 8192 reproduces its regime).
ARM_MAX_TOKENS = 16384
CALM_DATES = None  # computed in all_bench_nodes when WINDOWS_ONLY


def window_dates() -> set[str]:
    calm_years = {"2013", "2014", "2017"}
    pre = [n["decision_date"] for n in load_nodes()]
    calm = {d for d in pre if d[:4] in calm_years}
    post = {n["decision_date"] for n in build_postcutoff_nodes()}
    return set(CRISIS) | calm | post


def all_bench_nodes() -> list[dict]:
    pre = load_nodes()
    dates = [n["decision_date"] for n in pre]
    fake_for = {dates[i]: dates[(i + FAKE_SHIFT) % len(dates)] for i in range(len(dates))}
    for n in pre:
        n["fake_date"] = fake_for[n["decision_date"]]
        n["cohort"] = "pre"
    post = build_postcutoff_nodes()
    for n in post:
        n["cohort"] = "post"
    return pre + post


def arm_prompt(node: dict, arm: str) -> str:
    dd = node["decision_date"]
    if arm == "R":
        return node["orig_user"]
    if arm == "D":
        return clean_context(node["orig_user"], dd, "true")
    if arm == "M":
        return clean_context(node["orig_user"], dd, "none")
    return clean_context(node["orig_user"], dd, "fake", node["fake_date"])


async def run_arms(provider: str, model: str, concurrency: int, smoke: bool) -> None:
    nodes = all_bench_nodes()
    if smoke:
        nodes = [n for n in nodes if n["decision_date"] in ("2008-10-15", "2014-04-15")]
    elif WINDOWS_ONLY:
        wd = window_dates()
        nodes = [n for n in nodes if n["decision_date"] in wd]
    reps = (1,) if smoke else tuple(range(1, N_REPS + 1))
    root = BENCH / model
    sem = asyncio.Semaphore(concurrency)
    jobs = [(n, a, r) for n in nodes for a in ("R", "D", "M", "W") for r in reps]
    print(f"{model} arms: {len(jobs)} cells")

    async def cell(node, arm, rep):
        dd = node["decision_date"]
        cdir = root / arm / f"rep{rep}" / dd
        if (cdir / "01_sketches_valid.json").exists():
            return "SKIP"
        prompt = arm_prompt(node, arm)
        async with sem:
            raw, mv = await call_openai_compat(
                client, provider, model, node["system"], prompt,
                temperature=0.2, max_tokens=ARM_MAX_TOKENS, json_mode=False,
            )
        try:
            valid, invalid = validate_sketches(strip_fences(raw), dd)
        except (json.JSONDecodeError, ValueError) as exc:
            cdir.mkdir(parents=True, exist_ok=True)
            (cdir / "04_raw_response.txt").write_text(raw)
            (cdir / "99_parse_error.txt").write_text(str(exc))
            return "PARSE_ERROR"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "04_raw_response.txt").write_text(raw)
        (cdir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
        (cdir / "03_run_meta.json").write_text(json.dumps({
            "decision_date": dd, "arm": arm, "rep": rep, "cohort": node["cohort"],
            "fake_date": node["fake_date"] if arm == "W" else None,
            "provider": provider, "model": model, "model_reported": mv,
            "valid_count": len(valid), "invalid_count": invalid,
            "arm_max_tokens": ARM_MAX_TOKENS,
            "user_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "prereg": PREREG,
        }, indent=2))
        return f"OK v={len(valid)}"

    limits = httpx.Limits(max_connections=concurrency + 2, max_keepalive_connections=concurrency)
    global client
    # 900s: BF16 self-hosted streams run ~25 tok/s under load — an 8k-cap
    # generation needs ~330s wall. The old 240s killed nearly every request
    # pre-completion (timeout->retry livelock: 10 cells/h at 750 tok/s served);
    # fp8 only ever fit because it is ~2x faster. Same kimi lesson as probes.
    async with httpx.AsyncClient(timeout=900.0, limits=limits) as client:
        rs = await asyncio.gather(*(cell(n, a, r) for n, a, r in jobs), return_exceptions=True)
    ok = sum(1 for r in rs if isinstance(r, str) and r.startswith("OK"))
    skip = sum(1 for r in rs if r == "SKIP")
    perr = sum(1 for r in rs if r == "PARSE_ERROR")
    err = sum(1 for r in rs if isinstance(r, Exception))
    for r in rs:
        if isinstance(r, Exception):
            print("CELL_ERROR:", r, file=sys.stderr)
    print(f"{model} arms: {ok} ok, {skip} skip, {perr} parse_err, {err} err")
    if smoke:
        for n in nodes:
            for arm in ("R", "M"):
                f = root / arm / "rep1" / n["decision_date"] / "01_sketches_valid.json"
                if f.exists():
                    v = json.loads(f.read_text())
                    dirs = [s["direction"] for s in v]
                    print(f"  smoke {arm}/{n['decision_date']}: n={len(v)} dirs={dirs}")


async def run_probes(provider: str, model: str, concurrency: int) -> None:
    nodes = all_bench_nodes()
    root = BENCH / model
    root.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(concurrency)

    rec_f = root / "date_probe_results.jsonl"
    rec_done = set()
    if rec_f.exists():
        rec_done = {json.loads(l)["decision_date"] for l in rec_f.read_text().splitlines() if l.strip()}

    lap_f = root / "lap_probe_results.jsonl"
    lap_done: dict[str, int] = {}
    if lap_f.exists():
        for l in lap_f.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                lap_done[r["decision_date"]] = lap_done.get(r["decision_date"], 0) + 1
    ends = {n["decision_date"]: trading_day_end(n["decision_date"]) for n in nodes}

    async def rec_probe(node):
        dd = node["decision_date"]
        if LAP_ONLY or dd in rec_done:
            return None
        masked = clean_context(node["orig_user"], dd, "none")
        snapshot = extract_snapshot_block(masked)
        async with sem:
            raw, mv = await call_openai_compat(
                client, provider, model, PROBE_SYSTEM,
                PROBE_TEMPLATE.format(snapshot=snapshot),
                temperature=0.0, max_tokens=16384, json_mode=True,
            )
        est = None
        try:
            est = json.loads(strip_fences(raw)).get("estimated_date")
        except (json.JSONDecodeError, AttributeError):
            # reasoning preambles mention many dates; the answer converges last
            ms = re.findall(r"(?:19|20)\d{2}-\d{2}", raw)
            est = ms[-1] if ms else None
        return {"decision_date": dd, "estimated_date": est, "raw": raw[-200:], "model_reported": mv}

    async def lap_probe(t, k):
        async with sem:
            raw, mv = await call_openai_compat(
                client, provider, model, LAP_SYSTEM,
                LAP_PROMPT.format(t=t, t_end=ends[t]),
                temperature=1.0, max_tokens=8192, json_mode=False,
            )
        # last standalone occurrence tolerates untagged reasoning preambles;
        # single-word answers (all prior models) parse identically
        words = re.findall(r"\b(up|down|unknown)\b", raw.lower())
        ans = words[-1] if words else "invalid"
        return {"decision_date": t, "rep": k, "answer": ans, "raw": raw[-60:]}

    lap_jobs = [(n["decision_date"], k) for n in nodes for k in range(LAP_REPS)
                if k >= lap_done.get(n["decision_date"], 0)]
    n_rec = 0 if LAP_ONLY else sum(1 for n in nodes if n["decision_date"] not in rec_done)
    print(f"{model} probes: {n_rec} recovery + {len(lap_jobs)} LAP")
    limits = httpx.Limits(max_connections=concurrency + 2, max_keepalive_connections=concurrency)
    global client
    # 600s: K2.6 rec probes think past 120s; client timeout aborts the request
    # but the server bills the partial generation — timeout-retry burns money
    async with httpx.AsyncClient(timeout=600.0, limits=limits) as client:
        rec_rs = await asyncio.gather(*(rec_probe(n) for n in nodes), return_exceptions=True)
        lap_rs = await asyncio.gather(*(lap_probe(t, k) for t, k in lap_jobs), return_exceptions=True)
    with rec_f.open("a") as f:
        for r in rec_rs:
            if isinstance(r, dict):
                f.write(json.dumps(r) + "\n")
            elif isinstance(r, Exception):
                print("REC_ERROR:", r, file=sys.stderr)
    n_lap_err = 0
    with lap_f.open("a") as f:
        for r in lap_rs:
            if isinstance(r, dict):
                f.write(json.dumps(r) + "\n")
            elif isinstance(r, Exception):
                n_lap_err += 1
    print(f"{model} probes done (lap errors: {n_lap_err})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--job", choices=["arms", "probes"], default="arms")
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--windows-only", action="store_true",
                    help="BM-1b local tier: arms restricted to crisis+calm+postcutoff dates")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--lap-reps", type=int, default=20)
    ap.add_argument("--lap-only", action="store_true",
                    help="probes: skip date-recovery calls (kimi-k2.6 rec probe is "
                         "non-convergent — 256/258 length-truncated at 16k budget)")
    ap.add_argument("--arm-max-tokens", type=int, default=16384,
                    help="8192 for self-hosted vLLM (ctx 16384 enforces prompt+cap)")
    args = ap.parse_args()
    global WINDOWS_ONLY, N_REPS, LAP_REPS, LAP_ONLY, ARM_MAX_TOKENS
    WINDOWS_ONLY, N_REPS, LAP_REPS = args.windows_only, args.reps, args.lap_reps
    LAP_ONLY = args.lap_only
    ARM_MAX_TOKENS = args.arm_max_tokens
    BENCH.mkdir(parents=True, exist_ok=True)
    if args.smoke or args.job == "arms":
        asyncio.run(run_arms(args.provider, args.model, args.concurrency, args.smoke))
    else:
        asyncio.run(run_probes(args.provider, args.model, args.concurrency))


if __name__ == "__main__":
    main()
