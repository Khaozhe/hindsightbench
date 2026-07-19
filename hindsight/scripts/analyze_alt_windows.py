#!/usr/bin/env python
"""Alternative (moderate-stress) crisis windows for E2 — reviewer Q4 pack.

EXPLORATORY / POST-HOC by construction: the primary crisis and calm windows
were preregistered ex ante; the windows below were chosen after all results
were known, in response to a review question, and are disclosed as such.
Zero new API calls — everything recomputes from the frozen FM-1 flash arms
with the frozen convention (paired date-level bootstrap, B=10k, seed 2026).

Windows (decision dates are the 15th; none overlap the calm years 2013/14/17):
  euro2011   2011-08/09/10  US downgrade + euro debt stress (no US recession)
  riskoff15  2015-09, 2016-01/02  China devaluation / oil crash risk-off
  q4_2018    2018-11/12  Q4-2018 selloff (VIX ~36, S&P -9% December)

Mechanism prediction (§6.3: bias loads on USREC, i.e. recession-keyed
narrative memory): these non-recession stress windows should show POSITIVE
but SMALLER E2 than the preregistered recession-grade windows (+25.6pp) —
a dose-response reading. Whatever comes out is reported.

Writes outputs/fm1/ALT_WINDOWS_RESULTS.{json,md}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, gap, CRISIS, CALM_YEARS, load_arm
from analyze_design_review import boot_gap_diff, share
from hindsight_paths import REPO

OUT = REPO / "hindsight/outputs/fm1"
SEED = 2026

WINDOWS = {
    "euro2011":  ["2011-08-15", "2011-09-15", "2011-10-15"],
    "riskoff15": ["2015-09-15", "2016-01-15", "2016-02-15"],
    "q4_2018":   ["2018-11-15", "2018-12-15"],
}


def main() -> None:
    dates = all_dates()
    calm = [d for d in dates if d[:4] in CALM_YEARS]
    D = load_arm("gemini-2.5-flash", "D")
    M = load_arm("gemini-2.5-flash", "M")

    res = {"convention": "frozen FM-1 flash arms; paired date-level bootstrap "
                         "B=10k seed 2026; calm = 36 preregistered dates; "
                         "windows chosen POST-HOC (disclosed, reviewer Q4)"}

    rng = np.random.default_rng(SEED)
    e2_ref = gap(D, CRISIS, calm) - gap(M, CRISIS, calm)
    lo, hi = boot_gap_diff(D, M, CRISIS, calm, rng)
    res["reference_prereg"] = {"est": e2_ref, "ci95": [lo, hi],
                               "n_dates": len(CRISIS)}

    pooled: list[str] = []
    for name, win in WINDOWS.items():
        missing = [d for d in win if d not in dates]
        assert not missing, f"{name}: dates missing from panel: {missing}"
        rng = np.random.default_rng(SEED)
        e2 = gap(D, win, calm) - gap(M, win, calm)
        lo, hi = boot_gap_diff(D, M, win, calm, rng)
        res[name] = {"dates": win, "est": e2, "ci95": [lo, hi],
                     "D_share": share(D, win), "M_share": share(M, win)}
        pooled += win

    rng = np.random.default_rng(SEED)
    e2p = gap(D, pooled, calm) - gap(M, pooled, calm)
    lo, hi = boot_gap_diff(D, M, pooled, calm, rng)
    res["pooled_moderate"] = {"n_dates": len(pooled), "est": e2p,
                              "ci95": [lo, hi]}

    (OUT / "ALT_WINDOWS_RESULTS.json").write_text(json.dumps(res, indent=2))
    lines = ["# Alternative-window E2 (post-hoc, reviewer Q4)", ""]
    for k, v in res.items():
        if isinstance(v, dict) and "est" in v:
            lines.append(f"- **{k}**: E2 = {v['est']*100:+.1f}pp "
                         f"[{v['ci95'][0]*100:+.1f}, {v['ci95'][1]*100:+.1f}]")
    (OUT / "ALT_WINDOWS_RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
