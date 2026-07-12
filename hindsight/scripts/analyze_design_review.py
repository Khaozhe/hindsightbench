#!/usr/bin/env python
"""Design-review robustness pack (2026-07-10; zero new API calls).

Three analyses on the frozen FM-1 flash arms, answering the design-level
review of the E2 identification:

1. Episode structure: the 11 crisis dates form 3 macro episodes (GFC 6,
   COVID 2, inflation 3). Leave-one-episode-out E2 + per-episode E2 make the
   effective inferential unit explicit.
2. Within-M data sensitivity: does the masked arm respond to what the data
   says? (a) crisis-vs-calm gap inside M with CI; (b) per-date M bearish
   share regressed on the snapshot's UNRATE value (the one unambiguous
   distress level among the 8 series); (c) hedging diagnostic: dispersion of
   per-date bearish share by arm (a max-entropy hedging regime predicts M
   collapses toward a date-invariant p ~ 0.5).
3. Baseline reproduction: full-sample E2 must equal the paper's +25.6pp.

Writes outputs/fm1/DESIGN_REVIEW_RESULTS.{json,md}.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, gap, CRISIS, CALM_YEARS, load_arm
from run_kt1_masked_arm import load_nodes
from hindsight_paths import REPO

OUT = REPO / "hindsight/outputs/fm1"
B, SEED = 10_000, 2026

EPISODES = {
    "GFC":       [d for d in CRISIS if d[:4] in ("2008", "2009")],
    "COVID":     [d for d in CRISIS if d[:4] == "2020"],
    "inflation": [d for d in CRISIS if d[:4] == "2022"],
}


def boot_gap_diff(D, M, crisis, calm, rng):
    """paired date-level bootstrap of gap(D)-gap(M), same convention as the
    frozen analysis (B=10k, percentile CI)."""
    cr, ca = list(crisis), list(calm)
    bs = []
    for _ in range(B):
        c = [cr[i] for i in rng.integers(0, len(cr), len(cr))]
        q = [ca[i] for i in rng.integers(0, len(ca), len(ca))]
        bs.append(gap(D, c, q) - gap(M, c, q))
    return float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))


def share(bd, sel):
    xs = [x for d in sel for x in bd.get(d, [])]
    return sum(1 for x in xs if x == "-") / len(xs) if xs else float("nan")


def main() -> None:
    dates = all_dates()
    calm = [d for d in dates if d[:4] in CALM_YEARS]
    D = load_arm("gemini-2.5-flash", "D")
    M = load_arm("gemini-2.5-flash", "M")

    res = {"convention": f"paired date-level bootstrap B={B} seed={SEED}, "
                         "frozen FM-1 flash arms, gap = crisis-calm bearish share"}

    # -- 0. baseline reproduction --------------------------------------
    rng = np.random.default_rng(SEED)
    e2 = gap(D, CRISIS, calm) - gap(M, CRISIS, calm)
    lo, hi = boot_gap_diff(D, M, CRISIS, calm, rng)
    res["E2_full"] = {"est": e2, "ci95": [lo, hi], "crisis_n": len(CRISIS)}

    # -- 1a. leave-one-episode-out -------------------------------------
    res["E2_leave_one_episode_out"] = {}
    for name, eps in EPISODES.items():
        rest = [d for d in CRISIS if d not in set(eps)]
        rng = np.random.default_rng(SEED)
        est = gap(D, rest, calm) - gap(M, rest, calm)
        lo, hi = boot_gap_diff(D, M, rest, calm, rng)
        res["E2_leave_one_episode_out"][f"drop_{name}"] = {
            "est": est, "ci95": [lo, hi], "crisis_n": len(rest)}

    # -- 1b. per-episode ------------------------------------------------
    res["E2_per_episode"] = {}
    for name, eps in EPISODES.items():
        rng = np.random.default_rng(SEED)
        est = gap(D, eps, calm) - gap(M, eps, calm)
        lo, hi = boot_gap_diff(D, M, eps, calm, rng)
        res["E2_per_episode"][name] = {
            "est": est, "ci95": [lo, hi], "crisis_n": len(eps)}

    # -- 2a. within-M crisis discrimination -----------------------------
    rng = np.random.default_rng(SEED)
    gm = gap(M, CRISIS, calm)
    cr, ca = list(CRISIS), list(calm)
    bs = []
    for _ in range(B):
        c = [cr[i] for i in rng.integers(0, len(cr), len(cr))]
        q = [ca[i] for i in rng.integers(0, len(ca), len(ca))]
        bs.append(gap(M, c, q))
    res["M_crisis_calm_gap"] = {
        "est": gm, "ci95": [float(np.nanpercentile(bs, 2.5)),
                            float(np.nanpercentile(bs, 97.5))]}

    # -- 2b. within-M UNRATE sensitivity --------------------------------
    unrate = {}
    for n in load_nodes():
        m = re.search(r"UNRATE[^\n]*?value=([0-9.]+)", n["masked_user"])
        if m:
            unrate[n["decision_date"]] = float(m.group(1))
    xs, ys, ws = [], [], []
    for d, gens in M.items():
        if d in unrate and gens:
            xs.append(unrate[d])
            ys.append(sum(1 for x in gens if x == "-") / len(gens))
            ws.append(len(gens))
    xs, ys, ws = map(np.asarray, (xs, ys, ws))
    xz = (xs - xs.mean()) / xs.std()
    # weighted OLS slope + date-level bootstrap CI
    def wslope(x, y, w):
        xm = np.average(x, weights=w); ym = np.average(y, weights=w)
        return float(np.sum(w * (x - xm) * (y - ym)) / np.sum(w * (x - xm) ** 2))
    slope = wslope(xz, ys, ws)
    rng = np.random.default_rng(SEED)
    bs = []
    idx = np.arange(len(xs))
    for _ in range(B):
        k = rng.integers(0, len(idx), len(idx))
        if xz[k].std() == 0:
            continue
        bs.append(wslope(xz[k], ys[k], ws[k]))
    res["M_unrate_slope_per_sd"] = {
        "est": slope, "ci95": [float(np.percentile(bs, 2.5)),
                               float(np.percentile(bs, 97.5))],
        "n_dates": int(len(xs)),
        "note": "bearish-share change per 1 SD of snapshot UNRATE, M arm only",
    }

    # -- 2c. hedging diagnostic: per-date share dispersion by arm --------
    disp = {}
    for arm_name, bd in (("D", D), ("M", M)):
        ps = np.array([sum(1 for x in v if x == "-") / len(v)
                       for d, v in bd.items() if v and d in set(dates)])
        disp[arm_name] = {"mean": float(ps.mean()), "sd": float(ps.std()),
                          "p10": float(np.percentile(ps, 10)),
                          "p90": float(np.percentile(ps, 90)),
                          "n_dates": int(len(ps))}
    res["per_date_share_dispersion"] = disp
    res["hedging_note"] = (
        "a max-entropy hedging regime predicts M collapses to a date-invariant "
        "p~0.5 (sd~0); a weak-but-live data channel predicts residual "
        "date-level variation")

    (OUT / "DESIGN_REVIEW_RESULTS.json").write_text(json.dumps(res, indent=1))

    # -- markdown ---------------------------------------------------------
    L = ["# Design-review robustness pack (frozen FM-1 flash arms, zero new API)",
         "", f"Convention: {res['convention']}", "",
         f"**E2 full (baseline reproduction)**: {e2:+.3f} "
         f"[{res['E2_full']['ci95'][0]:+.3f}, {res['E2_full']['ci95'][1]:+.3f}] "
         "(paper: +0.256 [0.143, 0.372])", "",
         "## Leave-one-episode-out E2", ""]
    for k, v in res["E2_leave_one_episode_out"].items():
        L.append(f"- {k} (crisis n={v['crisis_n']}): {v['est']:+.3f} "
                 f"[{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")
    L += ["", "## Per-episode E2", ""]
    for k, v in res["E2_per_episode"].items():
        L.append(f"- {k} (n={v['crisis_n']}): {v['est']:+.3f} "
                 f"[{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")
    mg = res["M_crisis_calm_gap"]
    us = res["M_unrate_slope_per_sd"]
    L += ["", "## Within-M data sensitivity", "",
          f"- M crisis-calm gap: {mg['est']:+.3f} "
          f"[{mg['ci95'][0]:+.3f}, {mg['ci95'][1]:+.3f}]",
          f"- M bearish share on snapshot UNRATE (per 1 SD): {us['est']:+.3f} "
          f"[{us['ci95'][0]:+.3f}, {us['ci95'][1]:+.3f}]  (n={us['n_dates']} dates)",
          "", "## Per-date share dispersion (hedging diagnostic)", ""]
    for a, v in disp.items():
        L.append(f"- {a}: mean {v['mean']:.3f}, sd {v['sd']:.3f}, "
                 f"p10-p90 [{v['p10']:.3f}, {v['p90']:.3f}] (n={v['n_dates']})")
    (OUT / "DESIGN_REVIEW_RESULTS.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
