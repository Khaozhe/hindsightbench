#!/usr/bin/env python
"""Sequential Kimi batch driver: one 1000-request chunk at a time.

Moonshot pre-reserves worst-case cost per batch (max_tokens x count); with
~RMB505 balance only one arms chunk fits at a time. Submit -> poll to terminal
-> next. Materialize runs ONCE at the end (probe appends are not idempotent).

Usage: python kimi_sequential_driver.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import run_bench_openai_batch as B

MODEL = "kimi-k2.6"
B.PROVIDER = "kimi"
POLL = 120


def log(msg: str) -> None:
    print(f"{dt.datetime.now():%H:%M:%S} {msg}", flush=True)


def main() -> None:
    reqs = B.build_requests(MODEL)
    log(f"total pending requests: {len(reqs)}")
    chunks = [reqs[i:i + B.CHUNK] for i in range(0, len(reqs), B.CHUNK)]
    state_path = B.state_f(MODEL)
    st = json.loads(state_path.read_text()) if state_path.exists() else []

    def with_retry(fn, what):
        delay = 30
        for attempt in range(120):  # ~1h of network outage tolerance
            try:
                return fn()
            except httpx.HTTPError as exc:
                log(f"RETRY {what}: {type(exc).__name__} {exc} (sleep {delay}s)")
                time.sleep(delay)
                delay = min(delay * 2, 300)
        raise RuntimeError(f"{what}: exhausted retries")

    with httpx.Client(timeout=600.0) as c:
        for ci, part in enumerate(chunks):
            jsonl = "\n".join(json.dumps(r) for r in part)
            def _upload():
                fr = c.post(f"{B.base()}/files", headers=B.hdrs(),
                            files={"file": (f"{MODEL}_seq_{ci}.jsonl", jsonl.encode(), "application/jsonl")},
                            data={"purpose": "batch"})
                fr.raise_for_status()
                return fr.json()["id"]
            fid = with_retry(_upload, f"upload chunk {ci}")
            def _create():
                br = c.post(f"{B.base()}/batches", headers=B.hdrs(), json={
                    "input_file_id": fid, "endpoint": "/v1/chat/completions",
                    "completion_window": "24h",
                    "metadata": {"project": "hindsightbench", "model": MODEL, "seq_chunk": str(ci)}})
                br.raise_for_status()
                return br.json()["id"]
            bid = with_retry(_create, f"create batch chunk {ci}")
            st.append({"batch_id": bid, "file_id": fid, "n_requests": len(part),
                       "submitted_at": dt.datetime.now().isoformat(timespec="seconds"),
                       "status": "submitted"})
            state_path.write_text(json.dumps(st, indent=2))
            log(f"chunk {ci}/{len(chunks)-1}: submitted {bid[-8:]} ({len(part)} reqs)")

            validating_since = time.time()
            while True:
                b = with_retry(lambda: c.get(f"{B.base()}/batches/{bid}", headers=B.hdrs()).json(),
                               f"poll chunk {ci}")
                rc = b.get("request_counts", {})
                status = b["status"]
                log(f"chunk {ci}: {status} {rc.get('completed', 0)}/{rc.get('total', 0)} fail={rc.get('failed', 0)}")
                if status != "validating":
                    validating_since = None
                elif validating_since and time.time() - validating_since > 1800:
                    # stuck in validating >30min: cancel and resubmit this chunk once
                    log(f"chunk {ci}: stuck validating >30min, cancelling and resubmitting")
                    with_retry(lambda: c.post(f"{B.base()}/batches/{bid}/cancel", headers=B.hdrs()),
                               f"cancel stuck chunk {ci}")
                    bid = with_retry(_create, f"recreate batch chunk {ci}")
                    st.append({"batch_id": bid, "file_id": fid, "n_requests": len(part),
                               "submitted_at": dt.datetime.now().isoformat(timespec="seconds"),
                               "status": "resubmitted-after-stuck-validating"})
                    state_path.write_text(json.dumps(st, indent=2))
                    validating_since = time.time()
                    continue
                if status in ("completed", "failed", "expired", "cancelled"):
                    if status != "completed":
                        errs = (b.get("errors") or {}).get("data", [])
                        log(f"CHUNK_{ci}_NOT_COMPLETED: {status} {errs[:1]}")
                    break
                time.sleep(POLL)

    log("ALL_CHUNKS_TERMINAL")


if __name__ == "__main__":
    main()
