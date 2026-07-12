#!/usr/bin/env python
"""KT-1 masked-arm generation (prereg: hindsight/prereg/KT1_prereg.md, frozen 2026-07-02).

Reads the 240 stored V1 sketch requests, applies the frozen masking transform
(remove explicit date / full-sample target summary / vintage_date / revised_value),
calls Gemini with V1-identical generation parameters, and stores per-node
provenance mirroring macrochain/data/processed/sketch_panel_nodes/.

Also runs the date-recovery probe (1 call per node, temperature=0).

Usage:
  python run_kt1_masked_arm.py --dry-run 2          # print transformed prompts, no API
  python run_kt1_masked_arm.py --limit 2            # live run, first 2 dates
  python run_kt1_masked_arm.py                      # full 240-date run (resumable)
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

from hindsight_paths import REPO
REQUESTS_JSONL = REPO / "macrochain/data/processed/sketch_batch_requests.jsonl"
KEY_FILE = REPO / "Gemini_API_KEY.env"
OUT_ROOT = REPO / "hindsight/outputs/kt1"
NODES_DIR = OUT_ROOT / "masked_nodes"
PROBE_JSONL = OUT_ROOT / "date_probe_results.jsonl"

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "models/gemini-2.5-flash"      # identical to V1 (03_run_meta.json)
CONCURRENCY = 64  # user is Gemini API tier 2; 429s handled by retry/backoff
REQUEST_TIMEOUT = 120.0
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0

DATE_LINE_RE = re.compile(
    r"^(\s*)Decision time point: \d{4}-\d{2}-\d{2} - only information available "
    r"on or before this date is admissible as evidence\.\s*$"
)
SUMMARY_DROP_RE = re.compile(
    r"^\s*(Date range|Total sessions|Positive days|Negative days|Pos/Neg ratio)\s*:"
)
META_DROP_RE = re.compile(r"^\s*(decision_date_used|model_ready_panel_rows):")
SNAPSHOT_RE = re.compile(
    r"^(\s*)- ([A-Z0-9]+): vintage_date=(\d{4}-\d{2})-\d{2}, "
    r"vintage_value=([^,]+), revised_value=.+$"
)
# fail-closed leak patterns (prereg §2): no absolute dates, no revised, no base rate
LEAK_RES = [re.compile(r"\d{4}-\d{2}"), re.compile(r"revised", re.I), re.compile(r"65\.5")]


def month_diff(decision_date: str, vintage_ym: str) -> int:
    dy, dm = int(decision_date[:4]), int(decision_date[5:7])
    vy, vm = int(vintage_ym[:4]), int(vintage_ym[5:7])
    return (dy - vy) * 12 + (dm - vm)


def transform_user_prompt(text: str, decision_date: str) -> str:
    out_lines: list[str] = []
    for line in text.splitlines():
        if DATE_LINE_RE.match(line):
            indent = DATE_LINE_RE.match(line).group(1)
            out_lines.append(
                f"{indent}Decision time point: [undisclosed]. Only information "
                "contained in this snapshot is admissible as evidence."
            )
            continue
        if SUMMARY_DROP_RE.match(line) or META_DROP_RE.match(line):
            continue
        m = SNAPSHOT_RE.match(line)
        if m:
            indent, sid, vym, vval = m.group(1), m.group(2), m.group(3), m.group(4)
            k = month_diff(decision_date, vym)
            out_lines.append(f"{indent}- {sid}: asof=t-{k}mo, value={vval.strip()}")
            continue
        out_lines.append(line)
    masked = "\n".join(out_lines)
    # benign unit base period in the observable catalog, not decision-date info
    check_text = masked.replace("Index 1982-1984=100", "")
    for leak_re in LEAK_RES:
        hit = leak_re.search(check_text)
        if hit:
            raise RuntimeError(
                f"[fail-closed] leak pattern {leak_re.pattern!r} survived masking "
                f"for {decision_date}: ...{check_text[max(0, hit.start()-40):hit.end()+40]}..."
            )
    return masked


def extract_snapshot_block(masked_prompt: str) -> str:
    lines = [l for l in masked_prompt.splitlines() if re.match(r"^\s*- [A-Z0-9]+: asof=t-\d+mo, value=", l)]
    if len(lines) != 8:
        raise RuntimeError(f"expected 8 snapshot lines, got {len(lines)}")
    return "\n".join(l.strip() for l in lines)


PROBE_SYSTEM = (
    "You are an expert on US macroeconomic data history. "
    "Respond with a single JSON object and nothing else."
)

PROBE_TEMPLATE = """Below is a snapshot of US macroeconomic indicator values. Each line shows a
FRED/ALFRED series ID, the observation lag relative to an undisclosed reference
date, and the value as it was reported at that reference date.

{snapshot}

Based only on these values, what is the most likely calendar year and month of
the undisclosed reference date? Respond with JSON: {{"estimated_date": "YYYY-MM"}}"""


def load_api_key() -> str:
    for line in KEY_FILE.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            if k.strip() in ("Gemini_API_KEY", "GEMINI_API_KEY") and v.strip():
                return v.strip()
    raise RuntimeError(f"no key found in {KEY_FILE}")


USAGE_LOG = REPO / "hindsight/outputs/gemini_usage_log.jsonl"


def _log_usage(data: dict) -> None:
    """Append per-call token usage (exact, from API usageMetadata) for cost accounting."""
    try:
        u = data.get("usageMetadata", {})
        import datetime as _dt
        with USAGE_LOG.open("a") as f:
            f.write(json.dumps({
                "ts": _dt.datetime.now().isoformat(timespec="seconds"),
                "model": data.get("modelVersion", "unknown"),
                "prompt": u.get("promptTokenCount", 0),
                "output": u.get("candidatesTokenCount", 0),
                "thoughts": u.get("thoughtsTokenCount", 0),
                "total": u.get("totalTokenCount", 0),
            }) + "\n")
    except Exception:
        pass  # usage accounting must never break a run


async def call_gemini(
    client: httpx.AsyncClient,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float,
    max_tokens: int,
    thinking_budget: int | None = None,
) -> tuple[str, str]:
    """Returns (text, modelVersion). Retries on 429/5xx/timeouts."""
    url = f"{GEMINI_BASE_URL}/{MODEL}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    if thinking_budget is not None:
        payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": thinking_budget}
    delay = RETRY_BASE_DELAY
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = await client.post(url, json=payload, params={"key": api_key})
            if resp.status_code == 429 or resp.status_code >= 500:
                raise httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
            resp.raise_for_status()
            data = resp.json()
            cands = data.get("candidates", [])
            if not cands:
                raise ValueError(f"no candidates: {str(data)[:300]}")
            parts = cands[0].get("content", {}).get("parts", [])
            texts = [p["text"] for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)]
            fr = cands[0].get("finishReason", "STOP")
            # MAX_TOKENS check MUST precede the empty-text check: truncation usually
            # presents as empty parts, and retrying re-bills the whole thought budget
            # (2026-07-02 lesson, twice: first 23x6x8k, then 2x6x16k because this
            # check originally sat after the empty-text raise)
            if fr == "MAX_TOKENS":
                _log_usage(data)  # tokens are billed even on truncation
                raise RuntimeError(f"MAX_TOKENS (thoughts={data.get('usageMetadata', {}).get('thoughtsTokenCount')}), not retrying")
            if not texts:
                raise ValueError(f"empty text parts: {str(data)[:300]}")
            if fr not in ("STOP", None):
                _log_usage(data)
                raise ValueError(f"finishReason={fr}")
            _log_usage(data)
            return "\n".join(texts).strip(), data.get("modelVersion", "unknown")
        except (httpx.HTTPStatusError, httpx.TimeoutException, ValueError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                await asyncio.sleep(delay)
                delay *= 2
    raise RuntimeError(f"gemini call failed after {MAX_RETRIES + 1} attempts: {last_error}")


def validate_sketches(raw_text: str, decision_date: str) -> tuple[list[dict], int]:
    try:
        arr = json.loads(raw_text)
    except json.JSONDecodeError:
        # parser v2 (2026-07-07, disclosed deviation): tolerate trailing commas.
        # claude-sonnet-5 emits them in ~10% of responses (content otherwise
        # schema-valid); normalization applied uniformly to all models --
        # recovers sonnet-5 100, gpt-5.4-mini 10, llama-1B 3, llama-3B 4 cells.
        import re as _re
        arr = json.loads(_re.sub(r",(\s*[}\]])", r"\1", raw_text))
    if not isinstance(arr, list):
        raise ValueError("response is not a JSON array")
    valid, invalid = [], 0
    for item in arr:
        ok = (
            isinstance(item, dict)
            and item.get("direction") in ("+", "-")
            and isinstance(item.get("mechanism_narrative"), str)
            and isinstance(item.get("candidate_proxies"), list)
            and isinstance(item.get("regime_hint"), str)
        )
        if ok:
            item["decision_date"] = decision_date  # caller-injected, as in V1
            valid.append(item)
        else:
            invalid += 1
    return valid, invalid


async def process_node(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    api_key: str,
    node: dict,
) -> str:
    date = node["decision_date"]
    node_dir = NODES_DIR / date
    done_marker = node_dir / "01_sketches_valid.json"
    if done_marker.exists():
        return f"{date} SKIP(resume)"
    async with sem:
        raw, model_version = await call_gemini(
            client, api_key, node["system"], node["masked_user"],
            # DEVIATION from prereg "V1-identical 4096": 37 nodes hit MAX_TOKENS
            # because the current endpoint spends thinking tokens inside the cap.
            # Cap is invisible to the model -> content-neutral; disclosed in KT1_DECISION.md.
            temperature=0.2, max_tokens=8192,
        )
    try:
        valid, invalid = validate_sketches(raw, date)
    except (json.JSONDecodeError, ValueError) as exc:
        node_dir.mkdir(parents=True, exist_ok=True)
        (node_dir / "04_raw_response.txt").write_text(raw)
        (node_dir / "99_parse_error.txt").write_text(str(exc))
        return f"{date} PARSE_ERROR"
    node_dir.mkdir(parents=True, exist_ok=True)
    (node_dir / "04_raw_response.txt").write_text(raw)
    (node_dir / "02_masked_prompt.txt").write_text(node["masked_user"])
    meta = {
        "decision_date": date,
        "arm": "masked (KT-1)",
        "model": MODEL,
        "model_version_reported": model_version,
        "valid_count": len(valid),
        "invalid_count": invalid,
        "system_sha256": hashlib.sha256(node["system"].encode()).hexdigest(),
        "user_sha256": hashlib.sha256(node["masked_user"].encode()).hexdigest(),
        "v1_user_sha256": hashlib.sha256(node["orig_user"].encode()).hexdigest(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "prereg_sha256": "12d4b6f85762d35e751f96dae5db62e8d8b1402ee71183e0f4b4bd6564a21128",
    }
    (node_dir / "03_run_meta.json").write_text(json.dumps(meta, indent=2))
    (node_dir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
    return f"{date} OK valid={len(valid)} invalid={invalid}"


async def process_probe(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    api_key: str,
    node: dict,
    done_dates: set[str],
) -> dict | None:
    date = node["decision_date"]
    if date in done_dates:
        return None
    snapshot = extract_snapshot_block(node["masked_user"])
    async with sem:
        raw, model_version = await call_gemini(
            client, api_key, PROBE_SYSTEM, PROBE_TEMPLATE.format(snapshot=snapshot),
            temperature=0.0, max_tokens=2048,
        )
    est = None
    try:
        est = json.loads(raw).get("estimated_date")
    except json.JSONDecodeError:
        m = re.search(r"(19|20)\d{2}-\d{2}", raw)
        est = m.group(0) if m else None
    return {
        "decision_date": date,
        "estimated_date": est,
        "raw": raw[:500],
        "model_version_reported": model_version,
    }


def load_nodes() -> list[dict]:
    nodes = []
    for line in REQUESTS_JSONL.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        key = d["key"]  # e.g. sketch_001_20050115
        ymd = key.rsplit("_", 1)[-1]
        date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
        orig_user = d["request"]["contents"][0]["parts"][0]["text"]
        system = d["request"]["systemInstruction"]["parts"][0]["text"]
        nodes.append({
            "decision_date": date,
            "orig_user": orig_user,
            "system": system,
            "masked_user": transform_user_prompt(orig_user, date),
        })
    nodes.sort(key=lambda n: n["decision_date"])
    return nodes


async def main_async(nodes: list[dict], api_key: str) -> None:
    sem = asyncio.Semaphore(CONCURRENCY)
    limits = httpx.Limits(max_connections=CONCURRENCY + 2, max_keepalive_connections=CONCURRENCY)
    probe_done: set[str] = set()
    if PROBE_JSONL.exists():
        probe_done = {
            json.loads(l)["decision_date"] for l in PROBE_JSONL.read_text().splitlines() if l.strip()
        }
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, limits=limits) as client:
        sketch_results = await asyncio.gather(
            *(process_node(sem, client, api_key, n) for n in nodes),
            return_exceptions=True,
        )
        probe_results = await asyncio.gather(
            *(process_probe(sem, client, api_key, n, probe_done) for n in nodes),
            return_exceptions=True,
        )
    ok = err = 0
    for r in sketch_results:
        if isinstance(r, Exception):
            err += 1
            print(f"NODE_ERROR: {r}", file=sys.stderr)
        else:
            ok += 1
            print(r)
    with PROBE_JSONL.open("a") as f:
        for r in probe_results:
            if isinstance(r, Exception):
                print(f"PROBE_ERROR: {r}", file=sys.stderr)
            elif r is not None:
                f.write(json.dumps(r) + "\n")
    print(f"\nsketch nodes: {ok} ok, {err} errors; probes appended to {PROBE_JSONL}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", type=int, default=0, metavar="N",
                    help="print N transformed prompts and exit (no API calls)")
    ap.add_argument("--limit", type=int, default=0, metavar="N",
                    help="live-run only the first N dates")
    args = ap.parse_args()

    nodes = load_nodes()
    print(f"loaded {len(nodes)} nodes; masking transform passed fail-closed checks on all")

    if args.dry_run:
        for n in nodes[: args.dry_run]:
            print("=" * 30, n["decision_date"], "=" * 30)
            print(n["masked_user"])
            print("-" * 20, "probe prompt", "-" * 20)
            print(PROBE_TEMPLATE.format(snapshot=extract_snapshot_block(n["masked_user"])))
        return

    if args.limit:
        nodes = nodes[: args.limit]
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(main_async(nodes, load_api_key()))


if __name__ == "__main__":
    main()
