#!/usr/bin/env python
"""FM-1c generation (prereg: FM1c_prereg.md, sha256 d8d5f66e...).

Jobs:
  --job postcutoff   C1: 18 post-cutoff dates x 4 arms x 3 reps (+ date-recovery probes)
  --job wprime       C3: W' arm, 72-month month-preserving shift, 3 reps x 240
  --job lap          C2: LAP probe, (240+18) dates x 20 reps, temperature=1.0
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import call_gemini, load_api_key, load_nodes, validate_sketches
from run_kt1_masked_arm import PROBE_SYSTEM, PROBE_TEMPLATE, extract_snapshot_block
from run_fm1_arms import clean_context
import run_kt1_masked_arm as kt1

from hindsight_paths import REPO
FM1C = REPO / "hindsight/outputs/fm1c"
SNAPS = FM1C / "postcutoff_snapshots.json"
FM1_FLASH = REPO / "hindsight/outputs/fm1/gemini-2.5-flash"
SPX_NEW = REPO / "macrochain/data/processed/spx_target_new.parquet"

CRISIS = [
    "2008-09-15", "2008-10-15", "2008-11-15", "2008-12-15", "2009-01-15",
    "2009-02-15", "2020-03-15", "2020-04-15", "2022-06-15", "2022-09-15",
    "2022-10-15",
]
CALM_ANCHORS = [
    "2013-02-15", "2013-06-15", "2013-10-15", "2014-02-15", "2014-06-15",
    "2014-10-15", "2017-02-15", "2017-06-15", "2017-10-15",
]
CONCURRENCY = 64
PREREG = "FM1c_prereg.md sha256 d8d5f66e1c79ccc5..."


# --------------------------------------------------------------------------
# C1: post-cutoff node construction from the 2024-12-15 archived template
# --------------------------------------------------------------------------

def build_postcutoff_nodes() -> list[dict]:
    nodes = load_nodes()
    tmpl = next(n for n in nodes if n["decision_date"] == "2024-12-15")
    snaps = json.loads(SNAPS.read_text())["snapshots"]
    out = []
    dates = sorted(snaps.keys())
    for i, dd in enumerate(dates):
        snap = snaps[dd]
        if any("error" in v for v in snap.values()):
            raise RuntimeError(f"{dd}: snapshot has errors")
        lines = []
        for line in tmpl["orig_user"].splitlines():
            if "Decision time point: 2024-12-15" in line:
                lines.append(line.replace("2024-12-15", dd))
            elif "decision_date_used:" in line:
                lines.append(line.split("decision_date_used:")[0] + f"decision_date_used: {dd}")
            elif kt1.SNAPSHOT_RE.match(line):
                m = kt1.SNAPSHOT_RE.match(line)
                indent, sid = m.group(1), m.group(2)
                s = snap[sid]
                lines.append(
                    f"{indent}- {sid}: vintage_date={s['vintage_date']}, "
                    f"vintage_value={s['vintage_value']}, revised_value={s['revised_value']}"
                )
            else:
                lines.append(line)
        orig_user = "\n".join(lines)
        # W fake date: even i -> crisis, odd i -> calm anchor (prereg C1)
        fake = CRISIS[(i // 2) % len(CRISIS)] if i % 2 == 0 else CALM_ANCHORS[(i // 2) % len(CALM_ANCHORS)]
        out.append({
            "decision_date": dd, "orig_user": orig_user,
            "system": tmpl["system"], "fake_date": fake,
        })
    return out


async def run_postcutoff(concurrency: int) -> None:
    nodes = build_postcutoff_nodes()
    api_key = load_api_key()
    sem = asyncio.Semaphore(concurrency)
    jobs = []
    for node in nodes:
        for arm in ("R", "D", "M", "W"):
            for rep in (1, 2, 3):
                jobs.append((node, arm, rep))
    print(f"postcutoff: {len(jobs)} cells + {len(nodes)} probes")

    async def cell(node, arm, rep):
        dd = node["decision_date"]
        cdir = FM1C / "gemini-2.5-flash" / arm / f"rep{rep}" / dd
        if (cdir / "01_sketches_valid.json").exists():
            return "SKIP"
        if arm == "R":
            prompt = node["orig_user"]
        elif arm == "D":
            prompt = clean_context(node["orig_user"], dd, "true")
        elif arm == "M":
            prompt = clean_context(node["orig_user"], dd, "none")
        else:
            prompt = clean_context(node["orig_user"], dd, "fake", node["fake_date"])
        async with sem:
            raw, mv = await call_gemini(client, api_key, node["system"], prompt,
                                        temperature=0.2, max_tokens=8192)
        try:
            valid, invalid = validate_sketches(raw, dd)
        except (json.JSONDecodeError, ValueError) as exc:
            cdir.mkdir(parents=True, exist_ok=True)
            (cdir / "04_raw_response.txt").write_text(raw)
            (cdir / "99_parse_error.txt").write_text(str(exc))
            return "PARSE_ERROR"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "04_raw_response.txt").write_text(raw)
        (cdir / "02_prompt.txt").write_text(prompt)
        (cdir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
        (cdir / "03_run_meta.json").write_text(json.dumps({
            "decision_date": dd, "arm": arm, "rep": rep,
            "fake_date": node["fake_date"] if arm == "W" else None,
            "model": "models/gemini-2.5-flash", "model_version_reported": mv,
            "valid_count": len(valid), "invalid_count": invalid,
            "user_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "prereg": PREREG,
        }, indent=2))
        return "OK"

    async def probe(node):
        dd = node["decision_date"]
        pf = FM1C / "date_probe_postcutoff.jsonl"
        done = set()
        if pf.exists():
            done = {json.loads(l)["decision_date"] for l in pf.read_text().splitlines() if l.strip()}
        if dd in done:
            return None
        masked = clean_context(node["orig_user"], dd, "none")
        snapshot = extract_snapshot_block(masked)
        async with sem:
            raw, mv = await call_gemini(client, api_key, PROBE_SYSTEM,
                                        PROBE_TEMPLATE.format(snapshot=snapshot),
                                        temperature=0.0, max_tokens=2048)
        est = None
        try:
            est = json.loads(raw).get("estimated_date")
        except json.JSONDecodeError:
            import re
            m = re.search(r"(19|20)\d{2}-\d{2}", raw)
            est = m.group(0) if m else None
        with pf.open("a") as f:
            f.write(json.dumps({"decision_date": dd, "estimated_date": est,
                                "raw": raw[:300], "model_version_reported": mv}) + "\n")
        return "PROBE_OK"

    limits = httpx.Limits(max_connections=concurrency + 2, max_keepalive_connections=concurrency)
    global client
    async with httpx.AsyncClient(timeout=180.0, limits=limits) as client:
        rs = await asyncio.gather(*(cell(n, a, r) for n, a, r in jobs), return_exceptions=True)
        ps = await asyncio.gather(*(probe(n) for n in nodes), return_exceptions=True)
    err = sum(1 for r in rs if isinstance(r, Exception))
    for r in rs:
        if isinstance(r, Exception):
            print("CELL_ERROR:", r, file=sys.stderr)
    print(f"postcutoff cells: {sum(1 for r in rs if r=='OK')} ok, "
          f"{sum(1 for r in rs if r=='SKIP')} skip, {err} err; probes done")


# --------------------------------------------------------------------------
# C3: W' month-preserving arm (72-month shift) on the 240 pre-cutoff dates
# --------------------------------------------------------------------------

async def run_wprime(concurrency: int) -> None:
    nodes = load_nodes()
    dates = [n["decision_date"] for n in nodes]
    fake_for = {dates[i]: dates[(i + 72) % len(dates)] for i in range(len(dates))}
    api_key = load_api_key()
    sem = asyncio.Semaphore(concurrency)
    jobs = [(n, rep) for n in nodes for rep in (1, 2, 3)]
    print(f"wprime: {len(jobs)} cells")

    async def cell(node, rep):
        dd = node["decision_date"]
        cdir = FM1_FLASH / "Wp72" / f"rep{rep}" / dd
        if (cdir / "01_sketches_valid.json").exists():
            return "SKIP"
        prompt = clean_context(node["orig_user"], dd, "fake", fake_for[dd])
        async with sem:
            raw, mv = await call_gemini(client, api_key, node["system"], prompt,
                                        temperature=0.2, max_tokens=8192)
        try:
            valid, invalid = validate_sketches(raw, dd)
        except (json.JSONDecodeError, ValueError) as exc:
            cdir.mkdir(parents=True, exist_ok=True)
            (cdir / "04_raw_response.txt").write_text(raw)
            (cdir / "99_parse_error.txt").write_text(str(exc))
            return "PARSE_ERROR"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "04_raw_response.txt").write_text(raw)
        (cdir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
        (cdir / "03_run_meta.json").write_text(json.dumps({
            "decision_date": dd, "arm": "Wp72", "rep": rep, "fake_date": fake_for[dd],
            "model": "models/gemini-2.5-flash", "model_version_reported": mv,
            "valid_count": len(valid), "invalid_count": invalid,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "prereg": PREREG,
        }, indent=2))
        return "OK"

    limits = httpx.Limits(max_connections=concurrency + 2, max_keepalive_connections=concurrency)
    global client
    async with httpx.AsyncClient(timeout=180.0, limits=limits) as client:
        rs = await asyncio.gather(*(cell(n, r) for n, r in jobs), return_exceptions=True)
    for r in rs:
        if isinstance(r, Exception):
            print("CELL_ERROR:", r, file=sys.stderr)
    print(f"wprime: {sum(1 for r in rs if r=='OK')} ok, {sum(1 for r in rs if r=='SKIP')} skip, "
          f"{sum(1 for r in rs if isinstance(r, Exception))} err")


# --------------------------------------------------------------------------
# C2: LAP probe, 20 reps per date, temperature=1.0
# --------------------------------------------------------------------------

LAP_PROMPT = (
    "Between {t} and {t_end}, did the S&P 500 index go up or down? "
    "Answer based only on what you recall about the U.S. stock market in that "
    "specific period. If you do not recall, answer unknown. "
    "Respond with exactly one word: up, down, or unknown."
)
LAP_SYSTEM = "You answer with exactly one word: up, down, or unknown."


def trading_day_end(t: str) -> str:
    import pandas as pd
    spx = pd.read_parquet(SPX_NEW).reset_index()
    col = "date" if "date" in spx.columns else spx.columns[0]
    days = pd.to_datetime(spx[col]).sort_values().reset_index(drop=True)
    ts = pd.Timestamp(t)
    after = days[days >= ts].reset_index(drop=True)
    if len(after) > 20:
        return str(after.iloc[20].date())
    return str((ts + pd.Timedelta(days=28)).date())  # +28d approximation, prereg C2


async def run_lap(concurrency: int) -> None:
    nodes = load_nodes()
    dates = [n["decision_date"] for n in nodes]
    dates += sorted(json.loads(SNAPS.read_text())["snapshots"].keys())
    ends = {t: trading_day_end(t) for t in dates}
    out_f = FM1C / "lap_probe_results.jsonl"
    done: dict[str, int] = {}
    if out_f.exists():
        for l in out_f.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done[r["decision_date"]] = done.get(r["decision_date"], 0) + 1
    api_key = load_api_key()
    sem = asyncio.Semaphore(concurrency)
    jobs = [(t, k) for t in dates for k in range(20) if k >= done.get(t, 0)]
    print(f"lap: {len(jobs)} calls (of {len(dates)*20})")

    async def one(t, k):
        async with sem:
            raw, mv = await call_gemini(client, api_key, LAP_SYSTEM,
                                        LAP_PROMPT.format(t=t, t_end=ends[t]),
                                        temperature=1.0, max_tokens=2048)
        ans = raw.strip().lower().split()[0].strip('."\'') if raw.strip() else ""
        if ans not in ("up", "down", "unknown"):
            ans = "invalid"
        return {"decision_date": t, "rep": k, "answer": ans,
                "raw": raw[:80], "model_version_reported": mv}

    limits = httpx.Limits(max_connections=concurrency + 2, max_keepalive_connections=concurrency)
    global client
    async with httpx.AsyncClient(timeout=120.0, limits=limits) as client:
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
    ap.add_argument("--job", choices=["postcutoff", "wprime", "lap"], required=True)
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    args = ap.parse_args()
    FM1C.mkdir(parents=True, exist_ok=True)
    if args.job == "postcutoff":
        asyncio.run(run_postcutoff(args.concurrency))
    elif args.job == "wprime":
        asyncio.run(run_wprime(args.concurrency))
    else:
        asyncio.run(run_lap(args.concurrency))


if __name__ == "__main__":
    main()
