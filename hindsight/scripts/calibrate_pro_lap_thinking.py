#!/usr/bin/env python
"""A/B calibration: does capping pro's thinking budget change LAP answers?

20 dates x 5 reps x {default dynamic thinking, thinkingBudget=128}.
If per-date LAP/U-D agree, the full pro LAP run uses budget=128 (cost 1/6)
with this calibration attached as the deviation disclosure.

Writes outputs/bench/gemini-2.5-pro/lap_thinking_calibration.json.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import run_kt1_masked_arm as kt

kt.MODEL = "models/gemini-2.5-pro"

from run_kt1_masked_arm import call_gemini, load_api_key
from run_fm1c import LAP_PROMPT, LAP_SYSTEM, trading_day_end

from hindsight_paths import REPO
OUT = REPO / "hindsight/outputs/bench/gemini-2.5-pro"
REPS = 5
BUDGET = 128

# 20 dates spanning crisis / calm / full panel range (fixed ex ante)
DATES = [
    "2005-06-15", "2006-03-15", "2007-09-15", "2008-10-15", "2009-02-15",
    "2010-05-15", "2011-08-15", "2012-11-15", "2013-06-15", "2014-09-15",
    "2015-04-15", "2016-10-15", "2017-03-15", "2018-05-15", "2019-07-15",
    "2020-03-15", "2021-02-15", "2022-06-15", "2023-08-15", "2024-04-15",
]


def parse(raw: str) -> str:
    ans = raw.strip().lower().split()[0].strip('."\'') if raw.strip() else ""
    return ans if ans in ("up", "down", "unknown") else "invalid"


async def main() -> None:
    api_key = load_api_key()
    ends = {t: trading_day_end(t) for t in DATES}
    sem = asyncio.Semaphore(40)

    async def one(t, k, budget):
        async with sem:
            try:
                raw, _ = await call_gemini(client, api_key, LAP_SYSTEM,
                                           LAP_PROMPT.format(t=t, t_end=ends[t]),
                                           temperature=1.0, max_tokens=4096,
                                           thinking_budget=budget)
            except RuntimeError as exc:
                return {"date": t, "rep": k, "cond": "capped" if budget else "default",
                        "answer": "error", "err": str(exc)[:80]}
        return {"date": t, "rep": k, "cond": "capped" if budget else "default",
                "answer": parse(raw)}

    jobs = [(t, k, b) for t in DATES for k in range(REPS) for b in (None, BUDGET)]
    global client
    async with httpx.AsyncClient(timeout=300.0,
                                 limits=httpx.Limits(max_connections=42)) as client:
        rows = await asyncio.gather(*(one(t, k, b) for t, k, b in jobs))

    agg: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for r in rows:
        agg[r["date"]][r["cond"]][r["answer"]] += 1

    def lap_ud(c):
        n = sum(v for k, v in c.items() if k != "error")
        if not n:
            return None, None
        return (c["up"] + c["down"]) / n, (c["up"] - c["down"]) / n

    table, diffs, sign_agree, sign_n = {}, [], 0, 0
    for d in DATES:
        l_def, ud_def = lap_ud(agg[d]["default"])
        l_cap, ud_cap = lap_ud(agg[d]["capped"])
        table[d] = {"default": {"LAP": l_def, "UD": ud_def, "raw": dict(agg[d]["default"])},
                    "capped": {"LAP": l_cap, "UD": ud_cap, "raw": dict(agg[d]["capped"])}}
        if l_def is not None and l_cap is not None:
            diffs.append(abs(l_def - l_cap))
            if abs(ud_def) > 1e-9 or abs(ud_cap) > 1e-9:
                sign_n += 1
                sign_agree += int((ud_def > 0) == (ud_cap > 0) if ud_def * ud_cap != 0
                                  else abs(ud_def - ud_cap) < 0.21)
    summary = {
        "n_dates": len(DATES), "reps": REPS, "budget": BUDGET,
        "mean_abs_LAP_diff": sum(diffs) / len(diffs) if diffs else None,
        "max_abs_LAP_diff": max(diffs) if diffs else None,
        "UD_sign_agreement": f"{sign_agree}/{sign_n}",
        "errors": sum(1 for r in rows if r["answer"] == "error"),
    }
    out = {"summary": summary, "per_date": table}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lap_thinking_calibration.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(summary, indent=2))
    for d in DATES:
        t = table[d]
        print(d, "default", t["default"]["raw"], "| capped", t["capped"]["raw"])


if __name__ == "__main__":
    asyncio.run(main())
