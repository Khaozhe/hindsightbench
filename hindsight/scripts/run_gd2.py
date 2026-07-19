#!/usr/bin/env python
"""GD-2: second-domain (10Y Treasury) date trigger, cross-model mini panel.

Prereg: GD2_prereg_second_domain_crossmodel.md (1f31a145, frozen 2026-07-07).
Models: claude-haiku-4-5 (Anthropic direct, temp 0.2), gpt-5.4-mini (OpenAI,
provider-default sampling), deepseek-v4-flash (DeepSeek, temp 0.2).
Window: BM-1b reduced 65 dates (11 crisis + 36 calm + 18 post-cutoff).
Arms: D/M/W x 1 rep x 8 sketches = 195 calls/model. Direction semantics pinned.

Usage:
  python run_gd2.py --job smoke                 # 2 dates x 3 arms x 3 models + quote
  python run_gd2.py --job arms [--model M] [--concurrency 16]
  python run_gd2.py --job analyze
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import validate_sketches
from run_fm1_arms import clean_context
from run_bench_model import all_bench_nodes, window_dates
from llm_adapters import call_openai_compat, strip_fences

from hindsight_paths import REPO
OUT = REPO / "hindsight/outputs/gd2"
ANTHROPIC_LOG = REPO / "hindsight/outputs/anthropic_usage_log.jsonl"
OPENAI_LOG = REPO / "hindsight/outputs/openai_compat_usage_log.jsonl"
PREREG = "GD2_prereg_second_domain_crossmodel.md 1f31a145"

TARGET_OLD = "S&P 500 forward returns"
TARGET_NEW = "the direction of the 10-year U.S. Treasury yield over the next 20 trading days"
PIN_LINE = ("\nFor this target, direction '+' means the 10-year Treasury yield rises; "
            "'-' means it falls.")
ARM_MAX_TOKENS = 16384
SMOKE_DATES = ("2008-10-15", "2014-04-15")

MODELS = {
    "claude-haiku-4-5": {"provider": "anthropic", "temperature": 0.2},
    "gpt-5.4-mini": {"provider": "openai", "temperature": 0.2},  # adapter drops temp for gpt-5*
    "deepseek-v4-flash": {"provider": "deepseek", "temperature": 0.2},
}
PRICES = {  # $/1M tokens (in, out) — quoted in the frozen prereg
    "claude-haiku-4-5": (1.00, 5.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "deepseek-v4-flash": (0.14, 0.28),
}


def gd2_system(orig_system: str) -> str:
    assert TARGET_OLD in orig_system, "target sentence not found in system prompt"
    return orig_system.replace(TARGET_OLD, TARGET_NEW)


def gd2_user(node: dict, mode: str, fake_date: str | None) -> str:
    u = clean_context(node["orig_user"], node["decision_date"], mode, fake_date)
    u = u.replace("S&P 500 forward returns", "10-year Treasury yield direction (next 20 trading days)")
    return u + PIN_LINE


def gd2_nodes(smoke: bool) -> list[dict]:
    nodes = all_bench_nodes()
    keep = set(SMOKE_DATES) if smoke else window_dates()
    return [n for n in nodes if n["decision_date"] in keep]


async def call_anthropic(client, system: str, user: str, temperature: float) -> tuple[str, str]:
    msg = await client.messages.create(
        model="claude-haiku-4-5", max_tokens=ARM_MAX_TOKENS, temperature=temperature,
        system=system, messages=[{"role": "user", "content": user}],
    )
    with ANTHROPIC_LOG.open("a") as f:
        f.write(json.dumps({"ts": dt.datetime.now().isoformat(timespec="seconds"),
                            "model": "claude-haiku-4-5", "input": msg.usage.input_tokens,
                            "output": msg.usage.output_tokens, "tag": "gd2"}) + "\n")
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    return text, msg.model


async def run_model(model: str, nodes: list[dict], concurrency: int) -> dict:
    cfg = MODELS[model]
    root = OUT / model
    sem = asyncio.Semaphore(concurrency)
    counts = {"OK": 0, "SKIP": 0, "PARSE_ERR": 0, "ERR": 0}

    jobs = []
    for n in nodes:
        for arm, mode in (("D", "true"), ("M", "none"), ("W", "fake")):
            cdir = root / arm / "rep1" / n["decision_date"]
            if (cdir / "01_sketches_valid.json").exists():
                counts["SKIP"] += 1
                continue
            jobs.append((n, arm, mode))
    print(f"{model}: {len(jobs)} cells to run ({counts['SKIP']} done)", flush=True)

    if cfg["provider"] == "anthropic":
        import anthropic
        key = (REPO / "Anthropic_API_KEY.env").read_text().strip().split("=", 1)[1]
        aclient = anthropic.AsyncAnthropic(api_key=key, max_retries=8)
    else:
        aclient = None

    async def cell(n, arm, mode):
        dd = n["decision_date"]
        fake = n["fake_date"] if mode == "fake" else None
        sys_p, usr_p = gd2_system(n["system"]), gd2_user(n, mode, fake)
        try:
            async with sem:
                if cfg["provider"] == "anthropic":
                    raw, mv = await call_anthropic(aclient, sys_p, usr_p, cfg["temperature"])
                else:
                    raw, mv = await call_openai_compat(
                        hclient, cfg["provider"], model, sys_p, usr_p,
                        temperature=cfg["temperature"], max_tokens=ARM_MAX_TOKENS,
                        json_mode=False)
        except Exception as exc:
            print(f"ERR {model} {arm} {dd}: {exc}", file=sys.stderr, flush=True)
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
            "fake_date": fake, "model": model, "model_reported": mv,
            "valid_count": len(valid), "invalid_count": invalid,
            "target": "DGS10-20td", "direction_pinned": True,
            "sampling": "provider-default" if model.startswith("gpt-5") else str(cfg["temperature"]),
            "user_sha256": hashlib.sha256(usr_p.encode()).hexdigest(),
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "prereg": PREREG,
        }, indent=2))
        counts["OK"] += 1

    global hclient
    async with httpx.AsyncClient(timeout=600.0,
                                 limits=httpx.Limits(max_connections=concurrency + 2)) as hclient:
        await asyncio.gather(*(cell(*j) for j in jobs))
    print(f"{model} done: {counts}", flush=True)
    return counts


def smoke_quote(start_iso: str) -> None:
    """Extrapolate full-run cost from smoke calls logged after start_iso."""
    per_model = defaultdict(lambda: {"n": 0, "in": 0, "out": 0})
    for path, fin, fout in ((ANTHROPIC_LOG, "input", "output"),
                            (OPENAI_LOG, "prompt", "completion")):
        if not path.exists():
            continue
        for l in path.read_text().splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            if r.get("ts", "") < start_iso:
                continue
            m = r.get("model", "")
            key = next((k for k in MODELS if m.startswith(k.split("-2026")[0]) or k in m), None)
            if key is None:
                for k in MODELS:
                    if m.startswith("gpt-5.4-mini") and k == "gpt-5.4-mini":
                        key = k
            if key is None:
                continue
            per_model[key]["n"] += 1
            per_model[key]["in"] += r.get(fin, 0)
            per_model[key]["out"] += r.get(fout, 0) + r.get("reasoning", 0)
    total = 0.0
    print("\n--- smoke-extrapolated full-run quote (195 calls/model) ---")
    for k, s in per_model.items():
        if not s["n"]:
            continue
        pin, pout = PRICES[k]
        cost = 195 * (s["in"] / s["n"] * pin + s["out"] / s["n"] * pout) / 1e6
        total += cost
        print(f"{k:20s} smoke n={s['n']} mean_in={s['in']/s['n']:,.0f} "
              f"mean_out={s['out']/s['n']:,.0f} -> full-run ${cost:.2f}")
    print(f"TOTAL ${total:.2f} (envelope $11; STOP if exceeded)")


def analyze() -> None:
    import numpy as np
    from analyze_fm1 import all_dates, fake_map, CRISIS, CALM_YEARS

    # NaN-robust bootstrap (analyze_bench_row's frozen policy): on the reduced
    # 65-date window, w_fake covers only 4 crisis / 6 calm dates, so ~0.5% of
    # draws produce an empty window (NaN). analyze_fm1.boot_diff percentiles the
    # raw array, so a single NaN draw poisons the CI; here NaN draws are dropped
    # and a CI is reported only if >=50% of draws are valid.
    def boot_diff(f1, f2, crisis, calm, rng, B=10_000):
        c_a, q_a = np.array(crisis), np.array(calm)
        out = np.empty(B)
        for i in range(B):
            cs = list(rng.choice(c_a, len(c_a), replace=True))
            qs = list(rng.choice(q_a, len(q_a), replace=True))
            out[i] = f1(cs, qs) - f2(cs, qs)
        valid = out[~np.isnan(out)]
        if len(valid) < B * 0.5:
            return (float("nan"), float("nan"))
        return (float(np.percentile(valid, 2.5)), float(np.percentile(valid, 97.5)))

    pre_dates = all_dates()
    calm = [d for d in pre_dates if d[:4] in CALM_YEARS]
    fmap = fake_map(pre_dates)
    results = {}
    for model in MODELS:
        root = OUT / model
        if not root.exists():
            continue

        def load_arm(arm):
            by = defaultdict(list)
            for node in (root / arm / "rep1").glob("*"):
                f = node / "01_sketches_valid.json"
                if f.exists():
                    for s in json.loads(f.read_text()):
                        if s.get("direction") in ("+", "-"):
                            by[node.name].append(s["direction"])
            return by

        def down_gap(bd, crisis, calm_d):
            def share(ds):
                xs = [x for d in ds for x in bd.get(d, [])]
                return sum(1 for x in xs if x == "-") / len(xs) if xs else float("nan")
            return share(crisis) - share(calm_d)

        rng = np.random.default_rng(2026)
        D, M, W = load_arm("D"), load_arm("M"), load_arm("W")
        D_pre = {d: v for d, v in D.items() if d in set(pre_dates)}
        M_pre = {d: v for d, v in M.items() if d in set(pre_dates)}
        W_pre = {d: v for d, v in W.items() if d in set(pre_dates)}
        w_fake = defaultdict(list)
        for td, xs in W_pre.items():
            w_fake[fmap[td]].extend(xs)

        e2 = down_gap(D_pre, CRISIS, calm) - down_gap(M_pre, CRISIS, calm)
        e2_ci = boot_diff(lambda c, q: down_gap(D_pre, c, q),
                          lambda c, q: down_gap(M_pre, c, q), CRISIS, calm, rng)
        e3 = down_gap(w_fake, CRISIS, calm) - down_gap(W_pre, CRISIS, calm)
        e3_ci = boot_diff(lambda c, q: down_gap(w_fake, c, q),
                          lambda c, q: down_gap(W_pre, c, q), CRISIS, calm, rng)

        # secondary: post-cutoff calendar D-M down-share diff (per-model
        # model-relative caveat handled at reporting time, per prereg)
        def post_share(bd):
            xs = [x for d, v in bd.items() if d >= "2025-02" for x in v]
            return sum(1 for x in xs if x == "-") / len(xs) if xs else float("nan")
        p_post = post_share(D) - post_share(M)

        results[model] = {
            "E2_10Y": {"est": e2, "ci95": e2_ci,
                       "gap_D": down_gap(D_pre, CRISIS, calm), "gap_M": down_gap(M_pre, CRISIS, calm)},
            "E3_10Y": {"est": e3, "ci95": e3_ci,
                       "gap_fake": down_gap(w_fake, CRISIS, calm), "gap_true": down_gap(W_pre, CRISIS, calm)},
            "post_calendar_D_minus_M_downshare": p_post,
            "cells": {a: len(load_arm(a)) for a in ("D", "M", "W")},
        }
    (OUT / "GD2_RESULTS.json").write_text(json.dumps(results, indent=2, default=float))
    print(json.dumps(results, indent=2, default=float))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=["smoke", "arms", "analyze"], required=True)
    ap.add_argument("--model", choices=list(MODELS), default=None)
    ap.add_argument("--concurrency", type=int, default=16)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.job == "analyze":
        analyze()
        return
    smoke = args.job == "smoke"
    start = dt.datetime.now().isoformat(timespec="seconds")
    models = [args.model] if args.model else list(MODELS)
    for m in models:
        asyncio.run(run_model(m, gd2_nodes(smoke), 4 if smoke else args.concurrency))
    if smoke:
        smoke_quote(start)


if __name__ == "__main__":
    main()
