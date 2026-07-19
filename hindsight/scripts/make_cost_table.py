#!/usr/bin/env python
"""Per-benchmark-row measured cost from the three usage ledgers + H800 log.

Reads  outputs/{anthropic,gemini,openai_compat}_usage_log.jsonl (exact tokens)
       outputs/price_table.json    (only repo-documented rates are verified)
       outputs/h800_rental_log.json (user-filled from the provider console)
Writes outputs/COST_TABLE.md

Design rules (llm_batch_ops):
- token counts are facts (per-call ledger); prices are config; actual provider
  billing (batch discounts, CNY) always overrides token-math -> every line
  carries an explicit status: EXACT-RATE / LOWER-BOUND / TOKENS-ONLY /
  PRE-LEDGER GAP / CONSOLE-PENDING.
- attribution is mechanical: fixed (model, ts-window) -> task map with exact
  expected call counts, asserted so appended runs fail loudly instead of
  being silently mis-attributed.

Usage: make_cost_table.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from hindsight_paths import REPO
OUT = REPO / "hindsight/outputs"
PRICES = json.loads((OUT / "price_table.json").read_text())
H800 = json.loads((OUT / "h800_rental_log.json").read_text())

# (ledger, model-prefix, ts_lo, ts_hi, task, expected_calls)
# haiku 07-07: one 161-min gap splits the day exactly into the BM-1 row
# (7,482 = 2,064 arms + 258 REC + 5,160 LAP) and GD-2 (195 cells).
ATTRIBUTION = [
    ("anthropic", "claude-haiku-4-5", "2026-07-07T00:00", "2026-07-07T22:00",
     "BM-1 row: claude-haiku-4-5 (arms+REC+LAP, direct after batch cancel)", 7482),
    ("anthropic", "claude-haiku-4-5", "2026-07-07T22:00", "2026-07-08T00:00",
     "GD-2: claude-haiku-4-5 (10Y arms)", 195),
    ("gemini", "gemini-2.5-pro", "2026-07-02T00:00", "2026-07-03T00:00",
     "FM-1b: pro four-arm + probes (shared: paper-1 core + bench row)", 5383),
    ("gemini", "gemini-2.5-flash", "2026-07-03T00:00", "2026-07-04T00:00",
     "BM-1 row: flash probe extension (shared with core experiments)", 5525),
    ("gemini", "gemini-2.5-flash", "2026-07-06T00:00", "2026-07-07T00:00",
     "GD-1b: VIX micro-arm", 51),
    ("gemini", "gemini-2.5-flash", "2026-07-10T00:00", "2026-07-11T00:00",
     "FM-1e: trigger decomposition ablation (2 variants x 47 window dates)", 94),
    ("gemini", "gemini-2.5-flash", "2026-07-19T00:00", "2026-07-20T00:00",
     "FM-1g: self-elicited two-stage (smoke 8 incl. discarded v1 vehicle + "
     "run 90 incl. 10 billed MAX_TOKENS + 16k backfill 10)", 108),
    ("openai_compat", "gpt-5.4-mini", "2026-07-03T00:00", "2026-07-04T00:00",
     "BM-1 row: gpt-5.4-mini (arms+REC+LAP)", 7482),
    ("openai_compat", "gpt-5.4-mini", "2026-07-07T00:00", "2026-07-08T00:00",
     "GD-2: gpt-5.4-mini (10Y arms)", 195),
    ("openai_compat", "gpt-5.5", "2026-07-03T00:00", "2026-07-04T00:00",
     "BM-1 row: gpt-5.5 (full dates x 1 rep + probes)", 6453),
    ("openai_compat", "deepseek-v4-flash", "2026-07-07T00:00", "2026-07-08T00:00",
     "GD-2: deepseek-v4-flash (10Y arms)", 195),
    ("openai_compat", "kimi-k2.6", "2026-07-04T00:00", "2026-07-07T00:00",
     "BM-1 row: kimi-k2.6 (smoke 13 + main 7,475 + direct top-up 54; "
     "batch portion billed at 50% list in CNY)", 7542),
    ("openai_compat", "gpt-5.1", "2026-07-03T00:00", "2026-07-04T00:00",
     "legacy smoke (row excluded)", 8),
    ("openai_compat", "gpt-5-mini", "2026-07-03T00:00", "2026-07-04T00:00",
     "legacy smoke (row excluded)", 7),
]

# rows whose spend never touched these ledgers — must appear explicitly so the
# cost table can't silently read as complete
GAPS = [
    ("BM-1 row: deepseek-v4-flash", "PRE-LEDGER GAP — row ran 07-02/03 before "
     "openai_compat ledger existed; reconstruct from provider console if needed"),
    ("BM-1 row: claude-sonnet-5", "TOKENS HARVESTED (2026-07-09) from the "
     "retrievable batch results: 6,450/6,450 requests, in 4,328,102 / out "
     "5,190,998 tokens (bench/claude-sonnet-5/batch_usage_summary.json); "
     "COST still pending a billing-anchored rate (Anthropic batch bills at "
     "50% of list; list rate not repo-frozen)"),
    ("FM-1/KT-1 core (gemini flash)", "PRE-LEDGER GAP — core four-arm matrix "
     "ran before the gemini ledger was instituted 07-02"),
    ("BM-1 rows: llama3.2:1b / llama3.2:3b", "local ollama, zero marginal cost"),
    ("BM-1 rows: 70B/27B/35B-A3B/8B + row 15 (30B-A3B) + BM-2a tiers",
     "H800 rental — see GPU section"),
]


def in_win(ts: str, lo: str, hi: str) -> bool:
    return lo <= ts < hi


def tokens(ledger: str, rec: dict) -> tuple[int, int]:
    """(input, output) tokens as billed: gemini thoughts bill as output;
    openai completion already includes reasoning."""
    if ledger == "anthropic":
        return rec["input"], rec["output"]
    if ledger == "gemini":
        return rec["prompt"], rec["output"] + rec.get("thoughts", 0)
    return rec["prompt"], rec["completion"]


def price_key(model: str) -> str:
    for k in PRICES:
        if k != "_doc" and model.startswith(k):
            return k
    return ""


def main() -> None:
    loaded = {}
    for led in ("anthropic", "gemini", "openai_compat"):
        loaded[led] = [json.loads(l)
                       for l in (OUT / f"{led}_usage_log.jsonl").read_text().splitlines() if l.strip()]

    lines = [
        "# Measured cost table (generated by make_cost_table.py — do not hand-edit)",
        "",
        f"Generated from ledgers on {datetime.now().strftime('%Y-%m-%d %H:%M')}; "
        "token counts are per-call ledger facts. Status legend: EXACT-RATE = "
        "repo-documented rate x ledger tokens; LOWER-BOUND = partial rate; "
        "TOKENS-ONLY = rate not on file; provider billing overrides all estimates.",
        "",
        "## API ledger attribution",
        "",
        "| task | calls | in tok | out tok | est. cost | status |",
        "|---|---|---|---|---|---|",
    ]

    unattributed = {led: 0 for led in loaded}
    seen = {led: [False] * len(loaded[led]) for led in loaded}
    gd2_total = 0.0
    for led, model, lo, hi, task, expect in ATTRIBUTION:
        recs = []
        for i, r in enumerate(loaded[led]):
            if r["model"].startswith(model) and in_win(r["ts"], lo, hi):
                recs.append(r)
                seen[led][i] = True
        assert len(recs) == expect, (
            f"attribution drift: {task!r} expected {expect} calls, found "
            f"{len(recs)} — ledger appended? add a new attribution window")
        ti = sum(tokens(led, r)[0] for r in recs)
        to = sum(tokens(led, r)[1] for r in recs)
        pk = price_key(model)
        p = PRICES.get(pk, {})
        if p.get("in") is not None and p.get("out") is not None:
            cost = ti / 1e6 * p["in"] + to / 1e6 * p["out"]
            cell, status = f"${cost:.2f}", "EXACT-RATE"
            if task.startswith("GD-2"):
                gd2_total += cost
        elif p.get("out") is not None:
            cost = to / 1e6 * p["out"]
            cell, status = f"≥${cost:.2f}", "LOWER-BOUND (output-only rate)"
        else:
            cell, status = "—", "TOKENS-ONLY"
        lines.append(f"| {task} | {len(recs):,} | {ti:,} | {to:,} | {cell} | {status} |")

    for led in loaded:
        unattributed[led] = seen[led].count(False)
        assert unattributed[led] == 0, (
            f"{led} ledger has {unattributed[led]} unattributed calls — "
            "extend ATTRIBUTION before trusting this table")

    lines += [
        "",
        f"Cross-check: GD-2 three-model total at frozen rates = "
        f"**${gd2_total:.2f}** (prereg approval envelope $11; quoted ≈$4.8).",
        "",
        "## Spend not in these ledgers (explicit gaps)",
        "",
    ]
    lines += [f"- **{k}**: {v}" for k, v in GAPS]

    lines += ["", "## GPU (H800 rental, self-hosted rows)", "",
              f"Provider: {H800['provider']}", ""]
    for s in H800["sessions"]:
        amt = (f"CNY {s['total_cny']}" if s["total_cny"] is not None
               else "— (fill from console)")
        v = "verified" if s["verified"] else "UNVERIFIED"
        lines.append(f"- {s['id']} ({s['dates']}): {amt} [{v}] — covers "
                     f"{', '.join(s['covers'])}. {s['note']}")

    (OUT / "COST_TABLE.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT / 'COST_TABLE.md'}")
    print(f"GD-2 cross-check total: ${gd2_total:.2f}")


if __name__ == "__main__":
    main()
