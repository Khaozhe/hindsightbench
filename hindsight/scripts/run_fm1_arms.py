#!/usr/bin/env python
"""FM-1 four-arm generation (prereg: hindsight/prereg/FM1_prereg.md, sha256 745b42e0...).

Arms (see prereg §1):
  R = V1 prompt verbatim (leaky context + true date), regenerated today
  D = clean context + true date line
  M = clean context + no date (KT-1 transform; rep1 reuses KT-1 output, this
      script generates rep2..repN)
  W = clean context + FAKE date line (66-month deterministic shift)

Usage:
  python run_fm1_arms.py --model flash --dry-run          # print sample prompts per arm
  python run_fm1_arms.py --model flash                    # full flash matrix (resumable)
  python run_fm1_arms.py --model pro --concurrency 16     # pro matrix, 1 rep per arm
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
from run_kt1_masked_arm import (  # noqa: E402
    DATE_LINE_RE, META_DROP_RE, SNAPSHOT_RE, SUMMARY_DROP_RE,
    call_gemini, load_api_key, load_nodes, month_diff, validate_sketches,
)
import run_kt1_masked_arm as kt1  # noqa: E402

from hindsight_paths import REPO
OUT_ROOT = REPO / "hindsight/outputs/fm1"
KT1_NODES = REPO / "hindsight/outputs/kt1/masked_nodes"
PREREG_SHA = "745b42e0e8e9b45f" + ""  # short prefix recorded; full file in prereg dir

MODELS = {
    "flash": "models/gemini-2.5-flash",
    "pro": "models/gemini-2.5-pro",
}
# reps per arm, per prereg §1 (flash M has rep1 = KT-1 reuse, so generate rep2..3)
REP_PLAN = {
    "flash": {"R": [1, 2, 3], "D": [1, 2, 3], "M": [2, 3], "W": [1, 2, 3]},
    # FM-1b addendum (prereg/FM1b_prereg_addendum.md): pro D/M reps 2-3 added
    # for E2 precision; R/W stay at 1 rep. rep1 cells resume-skip.
    "pro": {"R": [1], "D": [1, 2, 3], "M": [1, 2, 3], "W": [1]},
}
FAKE_SHIFT = 66  # months of decision-date index shift, prereg §1

LEAK_BASE = [re.compile(r"revised", re.I), re.compile(r"65\.5")]
DATE_PAT = re.compile(r"\d{4}-\d{2}")


def clean_context(text: str, decision_date: str, date_mode: str, fake_date: str | None = None) -> str:
    """date_mode: 'true' (keep real date line) | 'none' | 'fake'."""
    out_lines: list[str] = []
    for line in text.splitlines():
        m_date = DATE_LINE_RE.match(line)
        if m_date:
            indent = m_date.group(1)
            if date_mode == "true":
                out_lines.append(line)
            elif date_mode == "fake":
                out_lines.append(
                    f"{indent}Decision time point: {fake_date} - only information "
                    "available on or before this date is admissible as evidence."
                )
            else:
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
    cleaned = "\n".join(out_lines)

    check = cleaned.replace("Index 1982-1984=100", "")
    allowed = {"true": decision_date[:7], "fake": (fake_date or "")[:7], "none": None}[date_mode]
    for m in DATE_PAT.finditer(check):
        if allowed and m.group(0) == allowed:
            continue
        raise RuntimeError(f"[fail-closed] date {m.group(0)!r} in {date_mode}-arm prompt for {decision_date}")
    for leak_re in LEAK_BASE:
        if leak_re.search(check):
            raise RuntimeError(f"[fail-closed] {leak_re.pattern!r} in {date_mode}-arm prompt for {decision_date}")
    return cleaned


def build_arm_prompt(node: dict, arm: str, fake_date: str | None) -> str:
    if arm == "R":
        return node["orig_user"]
    if arm == "D":
        return clean_context(node["orig_user"], node["decision_date"], "true")
    if arm == "M":
        return clean_context(node["orig_user"], node["decision_date"], "none")
    if arm == "W":
        return clean_context(node["orig_user"], node["decision_date"], "fake", fake_date)
    raise ValueError(arm)


async def process_cell(sem, client, api_key, model_id, node, arm, rep, fake_date):
    date = node["decision_date"]
    cell_dir = OUT_ROOT / model_id.split("/")[-1] / arm / f"rep{rep}" / date
    if (cell_dir / "01_sketches_valid.json").exists():
        return f"{arm}/rep{rep}/{date} SKIP"
    prompt = build_arm_prompt(node, arm, fake_date)
    async with sem:
        raw, model_version = await call_gemini(
            client, api_key, node["system"], prompt, temperature=0.2, max_tokens=8192,
        )
    # call_gemini is bound to kt1.MODEL; we patch per-model below in main
    try:
        valid, invalid = validate_sketches(raw, date)
    except (json.JSONDecodeError, ValueError) as exc:
        cell_dir.mkdir(parents=True, exist_ok=True)
        (cell_dir / "04_raw_response.txt").write_text(raw)
        (cell_dir / "99_parse_error.txt").write_text(str(exc))
        return f"{arm}/rep{rep}/{date} PARSE_ERROR"
    cell_dir.mkdir(parents=True, exist_ok=True)
    (cell_dir / "04_raw_response.txt").write_text(raw)
    (cell_dir / "02_prompt.txt").write_text(prompt)
    (cell_dir / "03_run_meta.json").write_text(json.dumps({
        "decision_date": date, "arm": arm, "rep": rep,
        "fake_date": fake_date if arm == "W" else None,
        "model": model_id, "model_version_reported": model_version,
        "valid_count": len(valid), "invalid_count": invalid,
        "user_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "prereg": "FM1_prereg.md sha256 745b42e0e8e9b45f...",
    }, indent=2))
    (cell_dir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
    return f"{arm}/rep{rep}/{date} OK valid={len(valid)}"


def link_kt1_as_m_rep1() -> int:
    """Reuse KT-1 masked nodes as flash/M/rep1 per prereg §3 (copy metadata pointer)."""
    dst_root = OUT_ROOT / "gemini-2.5-flash" / "M" / "rep1"
    n = 0
    for src in sorted(KT1_NODES.iterdir()):
        if not (src / "01_sketches_valid.json").exists():
            continue
        dst = dst_root / src.name
        if (dst / "01_sketches_valid.json").exists():
            n += 1
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for f in ("01_sketches_valid.json", "03_run_meta.json", "04_raw_response.txt"):
            if (src / f).exists():
                (dst / f).write_text((src / f).read_text())
        (dst / "00_provenance.txt").write_text(f"reused from KT-1: {src}\n")
        n += 1
    return n


async def main_async(model_key: str, concurrency: int) -> None:
    model_id = MODELS[model_key]
    kt1.MODEL = model_id  # call_gemini reads module-level MODEL
    nodes = load_nodes()
    dates = [n["decision_date"] for n in nodes]
    fake_for = {dates[i]: dates[(i + FAKE_SHIFT) % len(dates)] for i in range(len(dates))}

    jobs = []
    for arm, reps in REP_PLAN[model_key].items():
        for rep in reps:
            for node in nodes:
                jobs.append((node, arm, rep, fake_for[node["decision_date"]]))
    print(f"{model_key}: {len(jobs)} cells (some may SKIP via resume)")

    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency + 2, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=180.0, limits=limits) as client:
        api_key = load_api_key()
        results = await asyncio.gather(
            *(process_cell(sem, client, api_key, model_id, n, a, r, f) for n, a, r, f in jobs),
            return_exceptions=True,
        )
    ok = skip = err = 0
    for r in results:
        if isinstance(r, Exception):
            err += 1
            print(f"CELL_ERROR: {r}", file=sys.stderr)
        elif r.endswith("SKIP"):
            skip += 1
        else:
            ok += 1
    print(f"{model_key}: {ok} generated, {skip} skipped, {err} errors")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["flash", "pro"], required=True)
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    nodes = load_nodes()
    dates = [n["decision_date"] for n in nodes]
    fake_for = {dates[i]: dates[(i + FAKE_SHIFT) % len(dates)] for i in range(len(dates))}

    if args.dry_run:
        n = next(x for x in nodes if x["decision_date"] == "2008-10-15")
        for arm in ("R", "D", "M", "W"):
            p = build_arm_prompt(n, arm, fake_for[n["decision_date"]])
            head = "\n".join(p.splitlines()[:1] + [l for l in p.splitlines() if "asof=" in l or "vintage_date=" in l][:3])
            print(f"===== {arm} (2008-10-15, fake={fake_for[n['decision_date']] if arm=='W' else '-'}) =====")
            print(head, "\n")
        for x in nodes:
            for arm in ("D", "M", "W"):
                build_arm_prompt(x, arm, fake_for[x["decision_date"]])
        print("all 240 dates × D/M/W passed fail-closed checks")
        return

    if MODELS[args.model].endswith("flash"):
        n_linked = link_kt1_as_m_rep1()
        print(f"linked KT-1 masked nodes as flash/M/rep1: {n_linked}/240")
    asyncio.run(main_async(args.model, args.concurrency))


if __name__ == "__main__":
    main()
