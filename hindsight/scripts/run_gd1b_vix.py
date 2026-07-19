#!/usr/bin/env python
"""GD-1b VIX micro-arm (prereg 7bfb50e7): W arm only, fake-label ∈ crisis ∪ calm.

Sharp sign identification for GD-1's G3: a structured crisis narrative predicts
VIX UP (+) under fake crisis dates; an undifferentiated bearish reflex predicts
DOWN (−). Reuses the frozen GD-1 transforms; only the target sentence differs.

Usage:
  python run_gd1b_vix.py --job smoke              # 2 dates, prints usage-based quote
  python run_gd1b_vix.py --job arms [--concurrency 24]
  python run_gd1b_vix.py --job analyze
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import (call_gemini, load_api_key, load_nodes,
                                validate_sketches)
from run_fm1_arms import clean_context
from analyze_fm1 import fake_map, CRISIS, CALM_YEARS

from hindsight_paths import REPO
OUT = REPO / "hindsight/outputs/gd1b"

TARGET_OLD = "S&P 500 forward returns"
TARGET_NEW = "the direction of the CBOE Volatility Index (VIX) over the next 20 trading days"
ARM_MAX_TOKENS = 12288  # one smoke date ate 8192 in thoughts


def micro_dates() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(true_date, fake_date) pairs whose FAKE label is crisis / calm."""
    all_dates = sorted({n["decision_date"] for n in load_nodes()})
    fmap = fake_map(all_dates)
    fake_crisis = [(t, f) for t, f in fmap.items() if f in CRISIS]
    fake_calm = [(t, f) for t, f in fmap.items() if f[:4] in CALM_YEARS]
    return fake_crisis, fake_calm


def vix_system(orig_system: str) -> str:
    assert TARGET_OLD in orig_system, "target sentence not found in system prompt"
    return orig_system.replace(TARGET_OLD, TARGET_NEW)


def vix_user(node: dict, fake_date: str) -> str:
    u = clean_context(node["orig_user"], node["decision_date"], "fake", fake_date)
    u = u.replace("S&P 500 forward returns", "VIX direction (next 20 trading days)")
    return u + ("\nFor this target, direction '+' means the VIX rises (volatility "
                "increases); '-' means it falls.")


async def run_arms(concurrency: int, smoke: bool = False) -> None:
    fake_crisis, fake_calm = micro_dates()
    pairs = fake_crisis + fake_calm
    if smoke:
        pairs = [fake_crisis[0], fake_calm[0]]
    nodes = {n["decision_date"]: n for n in load_nodes()}
    api_key = load_api_key()
    sem = asyncio.Semaphore(concurrency)

    async def one(t: str, f: str):
        node_dir = OUT / "W" / "rep1" / t
        if (node_dir / "01_sketches_valid.json").exists():
            return "SKIP"
        node = nodes[t]
        sys_p = vix_system(node["system"])
        usr_p = vix_user(node, f)
        async with sem:
            try:
                raw, meta = await call_gemini(client, api_key, sys_p, usr_p,
                                              temperature=0.2, max_tokens=ARM_MAX_TOKENS)
            except Exception as e:
                print(f"ERR {t}: {e}", file=sys.stderr)
                return "ERR"
        valid, rejects = validate_sketches(raw, t)
        node_dir.mkdir(parents=True, exist_ok=True)
        (node_dir / "01_sketches_valid.json").write_text(json.dumps(valid, indent=1))
        (node_dir / "03_run_meta.json").write_text(json.dumps(
            {"true_date": t, "fake_date": f, "rejects": rejects, "model": meta}, indent=1))
        (node_dir / "04_raw_response.txt").write_text(raw)
        return "OK"

    global client
    async with httpx.AsyncClient(timeout=240.0) as client:
        rs = await asyncio.gather(*(one(t, f) for t, f in pairs), return_exceptions=True)
    print(f"gd1b W arm: {rs.count('OK')} ok, {rs.count('SKIP')} skip, {rs.count('ERR')} err "
          f"(fake-crisis {len(fake_crisis)}, fake-calm {len(fake_calm)}, smoke={smoke})")


def analyze() -> None:
    from scipy.stats import fisher_exact
    fake_crisis, fake_calm = micro_dates()
    def collect(pairs):
        up = dn = 0
        for t, _ in pairs:
            fp = OUT / "W" / "rep1" / t / "01_sketches_valid.json"
            if not fp.exists():
                continue
            for s in json.loads(fp.read_text()):
                if s.get("direction") == "+":
                    up += 1
                elif s.get("direction") == "-":
                    dn += 1
        return up, dn
    cu, cd = collect(fake_crisis)
    qu, qd = collect(fake_calm)
    sh_c = cu / (cu + cd) if cu + cd else float("nan")
    sh_q = qu / (qu + qd) if qu + qd else float("nan")
    odds, p = fisher_exact([[cu, cd], [qu, qd]])
    res = {
        "fake_crisis": {"up": cu, "down": cd, "share_up": round(sh_c, 4)},
        "fake_calm": {"up": qu, "down": qd, "share_up": round(sh_q, 4)},
        "delta_vix_up_pp": round((sh_c - sh_q) * 100, 1),
        "fisher_exact_two_sided_p": float(p),
        "prereg_prediction": "delta >= +15pp, p < 0.05 (structured narrative); delta <= 0 (bearish reflex)",
    }
    (OUT / "GD1B_RESULTS.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=["smoke", "arms", "analyze"], required=True)
    ap.add_argument("--concurrency", type=int, default=24)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.job == "analyze":
        analyze()
    else:
        asyncio.run(run_arms(args.concurrency, smoke=args.job == "smoke"))


if __name__ == "__main__":
    main()
