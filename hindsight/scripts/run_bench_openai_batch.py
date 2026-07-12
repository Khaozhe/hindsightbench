#!/usr/bin/env python
"""HindsightBench OpenAI runner via Batch API (50% discount, 24h window).

Prereg: BM1_prereg.md + BM1d addendum (OpenAI adapter notes).

Model plan:
  gpt-5.5        reduced windows protocol (65 dates, 1 rep, LAP 10 reps) — cost
  gpt-5.4-mini   full protocol (258 dates, 2 reps, LAP 20 reps)

Reasoning-model constraints (disclosed): no custom temperature (provider default),
max_completion_tokens instead of max_tokens.

Usage:
  python run_bench_openai_batch.py --model gpt-5.5 export|submit|watch|materialize
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import PROBE_SYSTEM, PROBE_TEMPLATE, extract_snapshot_block, validate_sketches
from run_fm1_arms import clean_context
from run_fm1c import LAP_PROMPT, LAP_SYSTEM, trading_day_end
from run_bench_model import all_bench_nodes, arm_prompt, window_dates
from llm_adapters import load_key, strip_fences

from hindsight_paths import REPO
BENCH = REPO / "hindsight/outputs/bench"
BASES = {"openai": "https://api.openai.com/v1", "kimi": "https://api.moonshot.cn/v1"}
USAGE_LOG = REPO / "hindsight/outputs/openai_compat_usage_log.jsonl"

PLAN = {
    "gpt-5.5": {"reps": (1,), "windows_only": False, "lap_reps": 20, "provider": "openai"},  # option D 2026-07-03: full dates x 1 rep
    "gpt-5.4-mini": {"reps": (1, 2), "windows_only": False, "lap_reps": 20, "provider": "openai"},
    # kimi batch: 40% off, k2.5/k2.6 only, temperature/top_p forbidden (we omit anyway)
    "kimi-k2.6": {"reps": (1, 2), "windows_only": False, "lap_reps": 20, "provider": "kimi"},
}
MAX_TOKENS_ARMS = 16000
MAX_TOKENS_REC = 8192
MAX_TOKENS_LAP = 4096


PROVIDER = "openai"  # set per-invocation in main()


def base() -> str:
    return BASES[PROVIDER]


def hdrs() -> dict:
    return {"Authorization": f"Bearer {load_key(PROVIDER)}"}


def body(model: str, system: str, user: str, max_tokens: int, json_mode: bool) -> dict:
    b = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    if PROVIDER == "openai":
        b["max_completion_tokens"] = max_tokens  # gpt-5 reasoning models reject max_tokens
    else:
        b["max_tokens"] = max_tokens
    if json_mode:
        b["response_format"] = {"type": "json_object"}
    return b


def dd_c(dd: str) -> str:
    return dd.replace("-", "")


def dd_e(c: str) -> str:
    return f"{c[:4]}-{c[4:6]}-{c[6:]}"


def build_requests(model: str) -> list[dict]:
    plan = PLAN[model]
    nodes = all_bench_nodes()
    if plan["windows_only"]:
        wd = window_dates()
        nodes = [n for n in nodes if n["decision_date"] in wd]
    root = BENCH / model
    reqs: list[dict] = []
    for n in nodes:
        for arm in ("R", "D", "M", "W"):
            for rep in plan["reps"]:
                if (root / arm / f"rep{rep}" / n["decision_date"] / "01_sketches_valid.json").exists():
                    continue
                reqs.append({"custom_id": f"arm_{arm}_rep{rep}_{dd_c(n['decision_date'])}",
                             "method": "POST", "url": "/v1/chat/completions",
                             "body": body(model, n["system"], arm_prompt(n, arm), MAX_TOKENS_ARMS, False)})
    rec_f = root / "date_probe_results.jsonl"
    rec_done = set()
    if rec_f.exists():
        rec_done = {json.loads(l)["decision_date"] for l in rec_f.read_text().splitlines() if l.strip()}
    for n in nodes:
        if n["decision_date"] in rec_done:
            continue
        snap = extract_snapshot_block(clean_context(n["orig_user"], n["decision_date"], "none"))
        reqs.append({"custom_id": f"rec_{dd_c(n['decision_date'])}",
                     "method": "POST", "url": "/v1/chat/completions",
                     "body": body(model, PROBE_SYSTEM, PROBE_TEMPLATE.format(snapshot=snap), MAX_TOKENS_REC, True)})
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
        for k in range(lap_done.get(t, 0), plan["lap_reps"]):
            reqs.append({"custom_id": f"lap_{dd_c(t)}_{k:02d}",
                         "method": "POST", "url": "/v1/chat/completions",
                         "body": body(model, LAP_SYSTEM, LAP_PROMPT.format(t=t, t_end=ends[t]), MAX_TOKENS_LAP, False)})
    return reqs


def state_f(model: str) -> Path:
    p = BENCH / model / "openai_batch_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


CHUNK = 1000  # Moonshot hard cap: "batch input file has too many tasks, max is 1000" (实测 2026-07-04)


def cmd_submit(model: str) -> None:
    reqs = build_requests(model)
    print(f"{model}: {len(reqs)} batch requests")
    if not reqs:
        print("nothing to submit")
        return
    st = []
    if state_f(model).exists():
        st = json.loads(state_f(model).read_text())
    with httpx.Client(timeout=600.0) as c:
        for i in range(0, len(reqs), CHUNK):
            part = reqs[i:i + CHUNK]
            jsonl = "\n".join(json.dumps(r) for r in part)
            fr = c.post(f"{base()}/files", headers=hdrs(),
                        files={"file": (f"{model}_bench_{i//CHUNK}.jsonl", jsonl.encode(), "application/jsonl")},
                        data={"purpose": "batch"})
            fr.raise_for_status()
            fid = fr.json()["id"]
            br = c.post(f"{base()}/batches", headers=hdrs(), json={
                "input_file_id": fid, "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
                "metadata": {"project": "hindsightbench", "model": model, "chunk": str(i // CHUNK)}})
            br.raise_for_status()
            b = br.json()
            st.append({"batch_id": b["id"], "file_id": fid, "n_requests": len(part),
                       "submitted_at": dt.datetime.now().isoformat(timespec="seconds"),
                       "status": b["status"]})
            print(f"chunk {i//CHUNK}: submitted {b['id']} ({b['status']}, {len(part)} reqs, {len(jsonl)//1048576}MB)")
    state_f(model).write_text(json.dumps(st, indent=2))


def cmd_watch(model: str) -> None:
    bids = [s["batch_id"] for s in json.loads(state_f(model).read_text())]
    with httpx.Client(timeout=60.0) as c:
        while True:
            states = []
            for bid in bids:
                b = c.get(f"{base()}/batches/{bid}", headers=hdrs()).json()
                rc = b.get("request_counts", {})
                print(f"{dt.datetime.now():%H:%M:%S} {bid[-8:]}: {b['status']} "
                      f"(done={rc.get('completed', 0)}/{rc.get('total', 0)} failed={rc.get('failed', 0)})")
                states.append(b["status"])
            if all(s in ("completed", "failed", "expired", "cancelled") for s in states):
                break
            time.sleep(120)


def cmd_materialize(model: str) -> None:
    root = BENCH / model
    parts, errs_all = [], []
    with httpx.Client(timeout=600.0) as c:
        for s in json.loads(state_f(model).read_text()):
            bid = s["batch_id"]
            b = c.get(f"{base()}/batches/{bid}", headers=hdrs()).json()
            if not b.get("output_file_id"):
                print(f"batch {bid} status={b['status']}, no output file — skipping", file=sys.stderr)
                continue
            parts.append(c.get(f"{base()}/files/{b['output_file_id']}/content", headers=hdrs()).text)
            err_id = b.get("error_file_id")
            if err_id:
                errs_all.append(c.get(f"{base()}/files/{err_id}/content", headers=hdrs()).text)
    content = "\n".join(parts)
    if errs_all:
        (root / "batch_errors.jsonl").write_text("\n".join(errs_all))
        print(f"error file: {sum(len(e.splitlines()) for e in errs_all)} lines -> batch_errors.jsonl", file=sys.stderr)
    n_ok = n_err = 0
    rec_out = (root / "date_probe_results.jsonl").open("a")
    lap_out = (root / "lap_probe_results.jsonl").open("a")
    for line in content.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        cid = rec["custom_id"]
        resp = rec.get("response", {})
        if resp.get("status_code") != 200:
            n_err += 1
            continue
        d = resp["body"]
        _log_usage_line(d)
        choice = d["choices"][0]
        text = (choice["message"]["content"] or "").strip()
        mv = d.get("model", model)
        if choice.get("finish_reason") == "length" or not text:
            n_err += 1
            continue
        n_ok += 1
        if cid.startswith("arm_"):
            _, arm, rep, ddc = cid.split("_")
            dd = dd_e(ddc)
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
                "provider": "openai-batch", "model": model, "model_reported": mv,
                "valid_count": len(valid), "invalid_count": invalid,
                "sampling": "provider-default (reasoning model, disclosed deviation)",
                "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "prereg": "BM1_prereg.md + BM1d_openai_adapter_notes.md",
            }, indent=2))
        elif cid.startswith("rec_"):
            dd = dd_e(cid.split("_")[1])
            est = None
            try:
                est = json.loads(strip_fences(text)).get("estimated_date")
            except (json.JSONDecodeError, AttributeError):
                ms = re.findall(r"(?:19|20)\d{2}-\d{2}", text)
                est = ms[-1] if ms else None
            rec_out.write(json.dumps({"decision_date": dd, "estimated_date": est,
                                      "raw": text[-200:], "model_reported": mv}) + "\n")
        elif cid.startswith("lap_"):
            _, ddc, k = cid.split("_")
            words = re.findall(r"\b(up|down|unknown)\b", text.lower())
            ans = words[-1] if words else "invalid"
            lap_out.write(json.dumps({"decision_date": dd_e(ddc), "rep": int(k),
                                      "answer": ans, "raw": text[-60:]}) + "\n")
    rec_out.close()
    lap_out.close()
    print(f"{model}: materialized {n_ok} ok, {n_err} errored/truncated")


def _log_usage_line(d: dict) -> None:
    try:
        u = d.get("usage", {}) or {}
        det = u.get("completion_tokens_details", {}) or {}
        with USAGE_LOG.open("a") as f:
            f.write(json.dumps({
                "ts": dt.datetime.now().isoformat(timespec="seconds"),
                "provider": "openai-batch", "model": d.get("model", "unknown"),
                "prompt": u.get("prompt_tokens", 0),
                "completion": u.get("completion_tokens", 0),
                "reasoning": det.get("reasoning_tokens", 0),
            }) + "\n")
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=list(PLAN), required=True)
    ap.add_argument("cmd", choices=["export", "submit", "watch", "materialize"])
    a = ap.parse_args()
    global PROVIDER
    PROVIDER = PLAN[a.model].get("provider", "openai")
    if a.cmd == "export":
        reqs = build_requests(a.model)
        print(f"{a.model}: {len(reqs)} requests would be submitted")
        print("sample:", [r["custom_id"] for r in reqs[:3]])
    elif a.cmd == "submit":
        cmd_submit(a.model)
    elif a.cmd == "watch":
        cmd_watch(a.model)
    else:
        cmd_materialize(a.model)


if __name__ == "__main__":
    main()
