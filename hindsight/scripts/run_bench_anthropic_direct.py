#!/usr/bin/env python
"""Direct (non-batch) Anthropic runner — fallback for a dead batch queue.

Reuses build_requests() from the batch runner (same prompts, same custom_ids,
same skip-done idempotency) and the same result-writing shapes, but fires
requests live via messages.create with bounded concurrency and 429 backoff.

Usage: python run_bench_anthropic_direct.py --model claude-haiku-4-5 [--concurrency 16]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_bench_anthropic_batch import build_requests, PLAN, dd_expand, KEY_FILE, BENCH
from run_kt1_masked_arm import validate_sketches
from llm_adapters import strip_fences

import anthropic

from hindsight_paths import REPO
USAGE_LOG = REPO / "hindsight/outputs/anthropic_usage_log.jsonl"


def log_usage(model: str, usage) -> None:
    try:
        with USAGE_LOG.open("a") as f:
            f.write(json.dumps({
                "ts": dt.datetime.now().isoformat(timespec="seconds"),
                "model": model,
                "input": usage.input_tokens,
                "output": usage.output_tokens,
            }) + "\n")
    except Exception:
        pass


def write_result(model: str, cid: str, text: str, model_reported: str,
                 rec_out, lap_out) -> str:
    root = BENCH / model
    if cid.startswith("arm_"):
        _, arm, rep, ddc = cid.split("_")
        dd = dd_expand(ddc)
        cdir = root / arm / rep / dd
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "04_raw_response.txt").write_text(text)
        try:
            valid, invalid = validate_sketches(strip_fences(text), dd)
        except (json.JSONDecodeError, ValueError) as exc:
            (cdir / "99_parse_error.txt").write_text(str(exc))
            return "PARSE_ERR"
        (cdir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
        (cdir / "03_run_meta.json").write_text(json.dumps({
            "decision_date": dd, "arm": arm, "rep": int(rep[3:]),
            "provider": "anthropic-direct", "model": model,
            "model_reported": model_reported,
            "valid_count": len(valid), "invalid_count": invalid,
            "sampling": "0.2" if PLAN[model]["temperature"] else "provider-default (disclosed deviation)",
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "prereg": "BM1_prereg.md + BM1c_anthropic_adapter_notes.md",
            "note": "direct fallback after 18.5h unscheduled batch (disclosed)",
        }, indent=2))
        return "OK"
    if cid.startswith("rec_"):
        dd = dd_expand(cid.split("_")[1])
        est = None
        try:
            est = json.loads(strip_fences(text)).get("estimated_date")
        except json.JSONDecodeError:
            m = re.search(r"(19|20)\d{2}-\d{2}", text)
            est = m.group(0) if m else None
        rec_out.write(json.dumps({"decision_date": dd, "estimated_date": est,
                                  "raw": text[:200], "model_reported": model_reported}) + "\n")
        rec_out.flush()
        return "OK"
    if cid.startswith("lap_"):
        _, ddc, k = cid.split("_")
        ans = text.strip().lower().split()[0].strip('."\'') if text else ""
        if ans not in ("up", "down", "unknown"):
            ans = "invalid"
        lap_out.write(json.dumps({"decision_date": dd_expand(ddc), "rep": int(k),
                                  "answer": ans, "raw": text[:60]}) + "\n")
        lap_out.flush()
        return "OK"
    return "SKIP"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--concurrency", type=int, default=16)
    args = ap.parse_args()
    model = args.model

    key = KEY_FILE.read_text().strip().split("=", 1)[1]
    client = anthropic.AsyncAnthropic(api_key=key, max_retries=8)  # SDK handles 429/5xx backoff
    reqs = build_requests(model)
    print(f"{model}: {len(reqs)} direct requests (skip-done applied)", flush=True)
    sem = asyncio.Semaphore(args.concurrency)
    root = BENCH / model
    root.mkdir(parents=True, exist_ok=True)
    counts = {"OK": 0, "PARSE_ERR": 0, "ERR": 0}
    done = 0

    rec_out = (root / "date_probe_results.jsonl").open("a")
    lap_out = (root / "lap_probe_results.jsonl").open("a")

    async def one(r):
        nonlocal done
        async with sem:
            try:
                msg = await client.messages.create(**r["params"])
            except Exception as exc:
                print(f"ERR {r['custom_id']}: {exc}", file=sys.stderr, flush=True)
                counts["ERR"] += 1
                return
        log_usage(model, msg.usage)
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        status = write_result(model, r["custom_id"], text, msg.model, rec_out, lap_out)
        counts[status] = counts.get(status, 0) + 1
        done += 1
        if done % 250 == 0:
            print(f"progress {done}/{len(reqs)}", flush=True)

    await asyncio.gather(*(one(r) for r in reqs))
    rec_out.close(); lap_out.close()
    print(f"{model} direct run done: {counts}", flush=True)
    print("DIRECT_RUN_EXIT=0", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
