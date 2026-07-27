#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (2026-07-24, Kimi review response).

Full inference for the DeepSeek v4-flash placebo numbers reported in
08_crossmodel.tex line 13 (calendar-window D-M = +5.5pp; model-relative
window = +4.0pp, frozen in
outputs/bench/deepseek-v4-flash/model_relative_placebo.json) which were
frozen as point estimates only, with no CI and no n.

Estimator: mirrors EXACTLY the main-model placebo CI [-7.8, +3.2]
(06_exp3_recall.tex, produced by analyze_fm1c.py::boot_share_diff):
  - date-level bootstrap: resample the window's date list with replacement,
    independently for the D and M arms;
  - statistic = pooled bearish share (over all sketch directions of the
    resampled dates) of D minus that of M;
  - B = 10,000, rng = np.random.default_rng(2026), percentile CI [2.5, 97.5].
As in analyze_fm1c.py, each CI is the FIRST draw sequence from a freshly
seeded rng(2026) (fm1c computed dm_ci first after seeding), so each window's
CI here uses its own fresh rng(2026) rather than a shared stream.

Data (READ-ONLY, frozen): outputs/bench/deepseek-v4-flash/{D,M}/rep*/<date>/
01_sketches_valid.json, loaded identically to
analyze_model_relative_window.py::load_arm. Windows are reproduced from the
same rule: calendar = dates >= 2025-02; model-relative = month strictly after
the empirical LAP cutoff (frozen 2025-07, re-derived here from
lap_probe_results.jsonl as a cross-check).

Sanity gate: recomputed point estimates must equal the frozen
model_relative_placebo.json values (+0.05514706 / +0.03977273) to 1e-12;
any mismatch is reported in the output JSON, never papered over.

Output: outputs/review/deepseek_placebo_ci.json (new file; no frozen dir is
touched).

Usage:
  conda run --no-capture-output -n macrochain python \
      hindsight/scripts/analyze_deepseek_placebo_ci.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from hindsight_paths import REPO

BENCH = REPO / "hindsight/outputs/bench"
MODEL = "deepseek-v4-flash"
ROOT = BENCH / MODEL
OUT_DIR = REPO / "hindsight/outputs/review"
OUT = OUT_DIR / "deepseek_placebo_ci.json"
B, SEED = 10_000, 2026


def load_arm(arm: str) -> dict[str, list[str]]:
    # identical to analyze_model_relative_window.py::load_arm
    by_date = defaultdict(list)
    for node in (ROOT / arm).glob("rep*/*"):
        f = node / "01_sketches_valid.json"
        if f.exists():
            for s in json.loads(f.read_text()):
                if s.get("direction") in ("+", "-"):
                    by_date[node.name].append(s["direction"])
    return by_date


def bear_share(by_date, dates):
    # identical to analyze_fm1c.py::bear_share (returns share, b, t)
    b = t = 0
    for d in dates:
        xs = by_date.get(d, [])
        b += sum(1 for x in xs if x == "-")
        t += len(xs)
    return b / t if t else float("nan"), b, t


def boot_share_diff(bd1, d1, bd2, d2, rng):
    # identical to analyze_fm1c.py::boot_share_diff
    out = np.empty(B)
    a1, a2 = np.array(d1), np.array(d2)
    for i in range(B):
        s1 = list(rng.choice(a1, len(a1), replace=True))
        s2 = list(rng.choice(a2, len(a2), replace=True))
        out[i] = bear_share(bd1, s1)[0] - bear_share(bd2, s2)[0]
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def main() -> None:
    D, M = load_arm("D"), load_arm("M")

    # empirical cutoff, re-derived exactly as analyze_model_relative_window.py
    lap_cnt = defaultdict(lambda: defaultdict(int))
    for l in (ROOT / "lap_probe_results.jsonl").read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            lap_cnt[r["decision_date"]][r["answer"]] += 1
    LAP = {d: (c["up"] + c["down"]) / sum(c.values())
           for d, c in lap_cnt.items() if sum(c.values())}
    cutoff = max(d[:7] for d in LAP if LAP[d] > 0.1)

    post_dates = sorted(d for d in set(D) | set(M) if d >= "2025-02")
    cal = list(post_dates)
    rel = [d for d in post_dates if d[:7] > cutoff]

    frozen = json.loads((ROOT / "model_relative_placebo.json").read_text())

    def window_result(dates, frozen_block):
        sh_d, b_d, t_d = bear_share(D, dates)
        sh_m, b_m, t_m = bear_share(M, dates)
        point = sh_d - sh_m
        # fresh rng per window: mirrors fm1c where dm_ci is the first draw
        # sequence after np.random.default_rng(SEED)
        rng = np.random.default_rng(SEED)
        ci = boot_share_diff(D, dates, M, dates, rng)
        frozen_pt = frozen_block["D_minus_M"]
        return {
            "dates": dates,
            "n_dates": len(dates),
            "D_bearish_share": sh_d, "D_bearish_k": b_d, "D_sketches": t_d,
            "M_bearish_share": sh_m, "M_bearish_k": b_m, "M_sketches": t_m,
            "point_D_minus_M": point,
            "ci95": list(ci),
            "frozen_point": frozen_pt,
            "matches_frozen": bool(abs(point - frozen_pt) < 1e-12
                                   and len(dates) == frozen_block["n"]),
        }

    result = {
        "model": MODEL,
        "provenance": {
            "data": str(ROOT) + "/{D,M}/rep*/<date>/01_sketches_valid.json (frozen, read-only)",
            "frozen_points": str(ROOT / "model_relative_placebo.json"),
            "estimator": ("analyze_fm1c.py::boot_share_diff — date-level bootstrap, "
                          "independent D/M date resampling, pooled bearish-share diff, "
                          f"B={B}, np.random.default_rng({SEED}), percentile [2.5, 97.5]; "
                          "same family as the main-model placebo CI [-7.8, +3.2] "
                          "in 06_exp3_recall.tex"),
            "script": "hindsight/scripts/analyze_deepseek_placebo_ci.py",
        },
        "empirical_cutoff_LAP": {"recomputed": cutoff,
                                 "frozen": frozen["empirical_cutoff_LAP"],
                                 "match": cutoff == frozen["empirical_cutoff_LAP"]},
        "calendar_window": window_result(cal, frozen["calendar_window"]),
        "model_relative_window": window_result(rel, frozen["model_relative_window"]),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))

    for w in ("calendar_window", "model_relative_window"):
        r = result[w]
        print(f"{w}: point {r['point_D_minus_M']:+.6f} "
              f"CI95 [{r['ci95'][0]:+.4f}, {r['ci95'][1]:+.4f}] "
              f"n={r['n_dates']} matches_frozen={r['matches_frozen']}")
    print(f"cutoff: {result['empirical_cutoff_LAP']}")
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
