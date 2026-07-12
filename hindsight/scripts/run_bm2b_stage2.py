#!/usr/bin/env python
"""BM-2b Stage 2: 2-shot completion-format conditions (prereg 51e03b53).

Conditions share IDENTICAL prompt bytes and hit /v1/completions (raw completion,
no chat template) — the only difference is which weights vLLM serves:
  instruct-2shot -> outputs/bench/qwen3-30b-a3b-2shot/
  base-2shot     -> outputs/bench/qwen3-30b-a3b-base-2shot/

Prompt = exemplar1(system+user+Output:+sketches JSON) --- exemplar2(...) ---
target(system+user+Output:). Exemplars: BM2b_exemplars.json (fb0e0c14, frozen
before any Stage-2 call; both archived M-arm cells are natively 4+/4- balanced).
Stop sequence "\n---" prevents the base model from hallucinating a next example.

Run SERVER-SIDE against local vLLM (REMOTE_VLLM_URL), one condition at a time:
  python run_bm2b_stage2.py --outname qwen3-30b-a3b-2shot --served NAME --job arms
  python run_bm2b_stage2.py --outname ... --served NAME --job lap
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import validate_sketches
from run_bench_model import all_bench_nodes, arm_prompt
from run_fm1c import LAP_PROMPT, LAP_SYSTEM, trading_day_end
from llm_adapters import strip_fences

from hindsight_paths import REPO
BENCH = REPO / "hindsight/outputs/bench"
EXEMPLARS = REPO / "hindsight/prereg/BM2b_exemplars.json"
PREREG = "BM2b_prereg_base_vs_instruct.md 51e03b53 + exemplars fb0e0c14"
BASE_URL = os.environ.get("REMOTE_VLLM_URL", "http://localhost:8000/v1")
SEP = "\n\n---\n\n"
ARM_MAX_TOKENS = 8192
LAP_MAX_TOKENS = 8


def two_shot_prefix() -> str:
    ex = json.loads(EXEMPLARS.read_text())["exemplars"]
    blocks = []
    for e in ex:
        blocks.append(f"{e['system']}\n\n{e['user_masked']}\n\nOutput:\n"
                      + json.dumps(e["sketches"]))
    return SEP.join(blocks) + SEP


async def completion(client: httpx.AsyncClient, served: str, prompt: str,
                     max_tokens: int, temperature: float) -> str:
    r = await client.post(f"{BASE_URL}/completions", json={
        "model": served, "prompt": prompt, "max_tokens": max_tokens,
        "temperature": temperature, "stop": ["\n---"],
    })
    r.raise_for_status()
    return r.json()["choices"][0]["text"]


async def run_arms(outname: str, served: str, concurrency: int, smoke: bool) -> None:
    prefix = two_shot_prefix()
    nodes = all_bench_nodes()
    if smoke:
        nodes = [n for n in nodes if n["decision_date"] in ("2008-10-15", "2014-04-15")]
    root = BENCH / outname
    sem = asyncio.Semaphore(concurrency)
    jobs = [(n, a) for n in nodes for a in ("R", "D", "M", "W")
            if not (root / a / "rep1" / n["decision_date"] / "01_sketches_valid.json").exists()]
    print(f"{outname} arms: {len(jobs)} cells", flush=True)
    counts = {"OK": 0, "PARSE_ERR": 0, "ERR": 0}

    async def cell(n, arm):
        dd = n["decision_date"]
        user = arm_prompt(n, arm)
        prompt = prefix + f"{n['system']}\n\n{user}\n\nOutput:\n"
        try:
            async with sem:
                raw = await completion(client, served, prompt, ARM_MAX_TOKENS, 0.2)
        except Exception as exc:
            print(f"ERR {arm} {dd}: {exc}", file=sys.stderr, flush=True)
            counts["ERR"] += 1
            return
        cdir = root / arm / "rep1" / dd
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "04_raw_response.txt").write_text(raw)
        try:
            valid, invalid = validate_sketches(strip_fences(raw), dd)
        except (json.JSONDecodeError, ValueError) as exc:
            (cdir / "99_parse_error.txt").write_text(str(exc))
            counts["PARSE_ERR"] += 1
            return
        (cdir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
        (cdir / "03_run_meta.json").write_text(json.dumps({
            "decision_date": dd, "arm": arm, "rep": 1, "cohort": n["cohort"],
            "fake_date": n["fake_date"] if arm == "W" else None,
            "condition": outname, "served_model": served,
            "format": "2shot-completion", "temperature": 0.2,
            "valid_count": len(valid), "invalid_count": invalid,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "prereg": PREREG,
        }, indent=2))
        counts["OK"] += 1

    global client
    async with httpx.AsyncClient(timeout=900.0,
                                 limits=httpx.Limits(max_connections=concurrency + 2)) as client:
        await asyncio.gather(*(cell(*j) for j in jobs))
    print(f"{outname} arms done: {counts}", flush=True)


async def run_lap(outname: str, served: str, concurrency: int, reps: int) -> None:
    # zero-shot completion LAP (prompt already dictates one-word answers);
    # low answer rate for a base model is itself a compliance datum
    nodes = all_bench_nodes()
    dates = sorted({n["decision_date"] for n in nodes})
    root = BENCH / outname
    root.mkdir(parents=True, exist_ok=True)
    out_f = root / "lap_probe_results.jsonl"
    done: dict[str, int] = {}
    if out_f.exists():
        for l in out_f.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done[r["decision_date"]] = done.get(r["decision_date"], 0) + 1
    jobs = [(t, k) for t in dates for k in range(reps) if k >= done.get(t, 0)]
    print(f"{outname} lap: {len(jobs)} calls", flush=True)
    sem = asyncio.Semaphore(concurrency)

    async def one(t, k):
        prompt = f"{LAP_SYSTEM}\n\n{LAP_PROMPT.format(t=t, t_end=trading_day_end(t))}\nAnswer:"
        async with sem:
            raw = await completion(client, served, prompt, LAP_MAX_TOKENS, 1.0)
        ans = raw.strip().lower().split()[0].strip('."\'') if raw.strip() else ""
        if ans not in ("up", "down", "unknown"):
            ans = "invalid"
        return {"decision_date": t, "rep": k, "answer": ans, "raw": raw[:60],
                "condition": outname}

    global client
    async with httpx.AsyncClient(timeout=300.0,
                                 limits=httpx.Limits(max_connections=concurrency + 2)) as client:
        rs = await asyncio.gather(*(one(t, k) for t, k in jobs), return_exceptions=True)
    n_err = 0
    with out_f.open("a") as f:
        for r in rs:
            if isinstance(r, Exception):
                n_err += 1
            else:
                f.write(json.dumps(r) + "\n")
    print(f"{outname} lap done: {len(rs)-n_err} ok, {n_err} err", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outname", required=True)
    ap.add_argument("--served", required=True)
    ap.add_argument("--job", choices=["arms", "lap", "smoke"], required=True)
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--lap-reps", type=int, default=10)
    args = ap.parse_args()
    if args.job == "smoke":
        asyncio.run(run_arms(args.outname, args.served, 4, smoke=True))
    elif args.job == "arms":
        asyncio.run(run_arms(args.outname, args.served, args.concurrency, smoke=False))
    else:
        asyncio.run(run_lap(args.outname, args.served, args.concurrency, args.lap_reps))


if __name__ == "__main__":
    main()
