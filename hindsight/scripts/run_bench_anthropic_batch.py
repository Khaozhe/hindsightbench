#!/usr/bin/env python
"""HindsightBench Anthropic runner via Message Batches API (50% discount).

Prereg: BM1_prereg.md + BM1c_anthropic_adapter_notes.md (sha256 88cf4687...).

Models & rep plan:
  claude-haiku-4-5   full protocol, 2 reps, temperature=0.2
  claude-sonnet-5    1 rep arms + full probes, temperature omitted (model
                     rejects non-default sampling; disclosed deviation)

Usage:
  python run_bench_anthropic_batch.py --model claude-haiku-4-5 submit
  python run_bench_anthropic_batch.py --model claude-haiku-4-5 watch
  python run_bench_anthropic_batch.py --model claude-haiku-4-5 materialize
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import validate_sketches
from run_kt1_masked_arm import PROBE_SYSTEM, PROBE_TEMPLATE, extract_snapshot_block
from run_fm1_arms import clean_context
from run_fm1c import LAP_PROMPT, LAP_SYSTEM, trading_day_end
from run_bench_model import all_bench_nodes, arm_prompt
from llm_adapters import strip_fences

import anthropic

from hindsight_paths import REPO
BENCH = REPO / "hindsight/outputs/bench"
KEY_FILE = REPO / "Anthropic_API_KEY.env"

PLAN = {
    "claude-haiku-4-5": {"reps": (1, 2), "temperature": 0.2},
    "claude-sonnet-5": {"reps": (1,), "temperature": None},  # rejects non-default sampling
}
MAX_TOKENS_ARMS = 16000
MAX_TOKENS_REC = 8192
MAX_TOKENS_LAP = 2048
LAP_REPS = 20


def client_() -> anthropic.Anthropic:
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text().splitlines():
            if "=" in line and line.split("=", 1)[1].strip():
                return anthropic.Anthropic(api_key=line.split("=", 1)[1].strip())
    return anthropic.Anthropic()  # env var / ant auth profile resolution


def dd_compact(dd: str) -> str:
    return dd.replace("-", "")


def dd_expand(c: str) -> str:
    return f"{c[:4]}-{c[4:6]}-{c[6:]}"


def build_requests(model: str) -> list[dict]:
    plan = PLAN[model]
    nodes = all_bench_nodes()
    reqs: list[dict] = []

    def params(system: str, user: str, max_tokens: int, temp: float | None) -> dict:
        p = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if temp is not None and plan["temperature"] is not None:
            p["temperature"] = temp
        return p

    root = BENCH / model
    # arms
    for n in nodes:
        for arm in ("R", "D", "M", "W"):
            for rep in plan["reps"]:
                if (root / arm / f"rep{rep}" / n["decision_date"] / "01_sketches_valid.json").exists():
                    continue
                reqs.append({
                    "custom_id": f"arm_{arm}_rep{rep}_{dd_compact(n['decision_date'])}",
                    "params": params(n["system"], arm_prompt(n, arm), MAX_TOKENS_ARMS, 0.2),
                })
    # recovery probes
    rec_f = root / "date_probe_results.jsonl"
    rec_done = set()
    if rec_f.exists():
        rec_done = {json.loads(l)["decision_date"] for l in rec_f.read_text().splitlines() if l.strip()}
    for n in nodes:
        if n["decision_date"] in rec_done:
            continue
        snapshot = extract_snapshot_block(clean_context(n["orig_user"], n["decision_date"], "none"))
        reqs.append({
            "custom_id": f"rec_{dd_compact(n['decision_date'])}",
            "params": params(PROBE_SYSTEM, PROBE_TEMPLATE.format(snapshot=snapshot), MAX_TOKENS_REC, 0.0),
        })
    # LAP probes
    lap_f = root / "lap_probe_results.jsonl"
    lap_done: dict[str, int] = {}
    if lap_f.exists():
        for l in lap_f.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                lap_done[r["decision_date"]] = lap_done.get(r["decision_date"], 0) + 1
    ends = {n["decision_date"]: trading_day_end(n["decision_date"]) for n in nodes}
    for n in nodes:
        t = n["decision_date"]
        for k in range(lap_done.get(t, 0), LAP_REPS):
            reqs.append({
                "custom_id": f"lap_{dd_compact(t)}_{k:02d}",
                "params": params(LAP_SYSTEM, LAP_PROMPT.format(t=t, t_end=ends[t]), MAX_TOKENS_LAP, 1.0),
            })
    return reqs


def cmd_submit(model: str) -> None:
    client = client_()
    reqs = build_requests(model)
    print(f"{model}: {len(reqs)} batch requests")
    if not reqs:
        print("nothing to submit")
        return
    batch = client.messages.batches.create(requests=reqs)
    state_f = BENCH / model / "anthropic_batch_state.json"
    state_f.parent.mkdir(parents=True, exist_ok=True)
    state = []
    if state_f.exists():
        state = json.loads(state_f.read_text())
    state.append({"batch_id": batch.id, "n_requests": len(reqs),
                  "submitted_at": dt.datetime.now().isoformat(timespec="seconds"),
                  "status": batch.processing_status})
    state_f.write_text(json.dumps(state, indent=2))
    print(f"submitted batch {batch.id} ({batch.processing_status})")


def cmd_watch(model: str) -> None:
    client = client_()
    state_f = BENCH / model / "anthropic_batch_state.json"
    state = json.loads(state_f.read_text())
    bid = state[-1]["batch_id"]
    while True:
        b = client.messages.batches.retrieve(bid)
        c = b.request_counts
        print(f"{dt.datetime.now():%H:%M:%S} {bid}: {b.processing_status} "
              f"(processing={c.processing} succeeded={c.succeeded} errored={c.errored})")
        if b.processing_status == "ended":
            break
        time.sleep(60)


def cmd_materialize(model: str) -> None:
    client = client_()
    root = BENCH / model
    state = json.loads((root / "anthropic_batch_state.json").read_text())
    bid = state[-1]["batch_id"]
    n_ok = n_err = 0
    rec_f = root / "date_probe_results.jsonl"
    lap_f = root / "lap_probe_results.jsonl"
    with rec_f.open("a") as rec_out, lap_f.open("a") as lap_out:
        for result in client.messages.batches.results(bid):
            cid = result.custom_id
            if result.result.type != "succeeded":
                n_err += 1
                print(f"BATCH_ERR {cid}: {result.result.type}", file=sys.stderr)
                continue
            msg = result.result.message
            text = "".join(b.text for b in msg.content if b.type == "text").strip()
            n_ok += 1
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
                    continue
                (cdir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
                (cdir / "03_run_meta.json").write_text(json.dumps({
                    "decision_date": dd, "arm": arm, "rep": int(rep[3:]),
                    "provider": "anthropic-batch", "model": model,
                    "model_reported": msg.model,
                    "valid_count": len(valid), "invalid_count": invalid,
                    "sampling": "0.2" if PLAN[model]["temperature"] else "provider-default (disclosed deviation)",
                    "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "prereg": "BM1_prereg.md + BM1c_anthropic_adapter_notes.md",
                }, indent=2))
            elif cid.startswith("rec_"):
                dd = dd_expand(cid.split("_")[1])
                est = None
                try:
                    est = json.loads(strip_fences(text)).get("estimated_date")
                except json.JSONDecodeError:
                    import re
                    m = re.search(r"(19|20)\d{2}-\d{2}", text)
                    est = m.group(0) if m else None
                rec_out.write(json.dumps({"decision_date": dd, "estimated_date": est,
                                          "raw": text[:200], "model_reported": msg.model}) + "\n")
            elif cid.startswith("lap_"):
                _, ddc, k = cid.split("_")
                ans = text.strip().lower().split()[0].strip('."\'') if text else ""
                if ans not in ("up", "down", "unknown"):
                    ans = "invalid"
                lap_out.write(json.dumps({"decision_date": dd_expand(ddc), "rep": int(k),
                                          "answer": ans, "raw": text[:60]}) + "\n")
    print(f"{model}: materialized {n_ok} results, {n_err} batch errors")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(PLAN), required=True)
    ap.add_argument("cmd", choices=["export", "submit", "watch", "materialize"])
    args = ap.parse_args()
    if args.cmd == "export":
        reqs = build_requests(args.model)
        print(f"{args.model}: {len(reqs)} requests would be submitted")
        print("sample custom_ids:", [r["custom_id"] for r in reqs[:3]])
    elif args.cmd == "submit":
        cmd_submit(args.model)
    elif args.cmd == "watch":
        cmd_watch(args.model)
    else:
        cmd_materialize(args.model)


if __name__ == "__main__":
    main()
