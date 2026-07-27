#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (2026-07-24, Kimi review response).

Taper-tantrum sensitivity: 2013-05 and 2013-06 sit inside the frozen "calm"
set (all months of 2013/2014/2017) but are the taper tantrum -- a textbook
BOND event. This script recomputes the two affected second-domain contrasts
with those two months REMOVED from the calm set (36 -> 34 dates), using the
exact frozen estimators:

  1. GD-1 10Y bond arm  (outputs/gd1/GD1_RESULTS.md):
     E2_10Y = down_gap(D, CRISIS, calm) - down_gap(M, CRISIS, calm),
     paired date-level bootstrap CI (boot_diff, B=10_000, seed=2026),
     identical to analyze_gd1.py (including rng consumption order:
     e2 CI first, then W-arm fake-true CI).
  2. GD-1b VIX micro-arm (outputs/gd1b/GD1B_RESULTS.json + paper 05_exp2
     date-level sentence): sketch-level VIX-up shares + Fisher exact
     (scipy fisher_exact, two-sided), and date-level up-majority counts
     (majority = strictly more '+' than '-') + Fisher exact.

Frozen originals are re-derived from the per-date frozen files and asserted
against the published numbers BEFORE the dropped-set variants are computed;
any mismatch aborts. Reads frozen dirs only; writes ONLY to
outputs/review/taper_dropped.{json,md}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import CRISIS, CALM_YEARS, all_dates, boot_diff, fake_map  # noqa: E402
from analyze_gd1 import GD1, down_gap, load_arm  # noqa: E402
from hindsight_paths import REPO  # noqa: E402

GD1B = REPO / "hindsight/outputs/gd1b"
OUT = REPO / "hindsight/outputs/review"
DROP = ("2013-05-15", "2013-06-15")
SEED = 2026  # matches analyze_gd1.py; B=10_000 lives inside boot_diff


# ---------------------------------------------------------------- GD-1 bond
def bond_block(calm: list[str]) -> dict:
    """Reproduce analyze_gd1.py main() estimator for a given calm set."""
    D, M, W = load_arm("D"), load_arm("M"), load_arm("W")
    fmap = fake_map(all_dates())
    w_fake: dict[str, list[str]] = {}
    for td, xs in W.items():
        w_fake.setdefault(fmap[td], []).extend(xs)

    rng = np.random.default_rng(SEED)  # fresh rng per calm set, frozen order
    g_d, g_m = down_gap(D, CRISIS, calm), down_gap(M, CRISIS, calm)
    e2 = g_d - g_m
    e2_ci = boot_diff(lambda c, q: down_gap(D, c, q),
                      lambda c, q: down_gap(M, c, q), CRISIS, calm, rng)
    g_wf, g_wt = down_gap(w_fake, CRISIS, calm), down_gap(W, CRISIS, calm)
    e3_ci = boot_diff(lambda c, q: down_gap(w_fake, c, q),
                      lambda c, q: down_gap(W, c, q), CRISIS, calm, rng)
    return {
        "n_calm_dates": len(calm),
        "gap_down_D": round(g_d, 4),
        "gap_down_M": round(g_m, 4),
        "E2_10Y": round(e2, 4),
        "E2_10Y_ci95": [round(e2_ci[0], 4), round(e2_ci[1], 4)],
        "W_gap_down_fake": round(g_wf, 4),
        "W_gap_down_true": round(g_wt, 4),
        "W_fake_minus_true": round(g_wf - g_wt, 4),
        "W_fake_minus_true_ci95": [round(e3_ci[0], 4), round(e3_ci[1], 4)],
    }


# --------------------------------------------------------------- GD-1b VIX
def vix_block(dropped_fake_labels: tuple[str, ...] = ()) -> dict:
    """Reproduce run_gd1b_vix.py analyze() + the paper's date-level counts."""
    dates = all_dates()
    fmap = fake_map(dates)
    fake_crisis = [(t, f) for t, f in fmap.items() if f in CRISIS]
    fake_calm = [(t, f) for t, f in fmap.items()
                 if f[:4] in CALM_YEARS and f not in dropped_fake_labels]

    def per_date(pairs):
        rows = []
        for t, f in pairs:
            fp = GD1B / "W" / "rep1" / t / "01_sketches_valid.json"
            if not fp.exists():
                continue
            up = dn = 0
            for s in json.loads(fp.read_text()):
                if s.get("direction") == "+":
                    up += 1
                elif s.get("direction") == "-":
                    dn += 1
            rows.append({"true_date": t, "fake_date": f, "up": up, "down": dn})
        return rows

    cr, ca = per_date(fake_crisis), per_date(fake_calm)
    cu, cd = sum(r["up"] for r in cr), sum(r["down"] for r in cr)
    qu, qd = sum(r["up"] for r in ca), sum(r["down"] for r in ca)
    _, p_sk = fisher_exact([[cu, cd], [qu, qd]])
    cr_maj = sum(1 for r in cr if r["up"] > r["down"])
    ca_maj = sum(1 for r in ca if r["up"] > r["down"])
    _, p_dt = fisher_exact([[cr_maj, len(cr) - cr_maj],
                            [ca_maj, len(ca) - ca_maj]])
    return {
        "fake_crisis": {"n_dates": len(cr), "up": cu, "down": cd,
                        "share_up": round(cu / (cu + cd), 4)},
        "fake_calm": {"n_dates": len(ca), "up": qu, "down": qd,
                      "share_up": round(qu / (qu + qd), 4)},
        "delta_vix_up_pp": round((cu / (cu + cd) - qu / (qu + qd)) * 100, 1),
        "fisher_sketch_two_sided_p": float(p_sk),
        "date_level_up_majority": {"crisis": f"{cr_maj}/{len(cr)}",
                                   "calm": f"{ca_maj}/{len(ca)}"},
        "fisher_date_two_sided_p": float(p_dt),
        "calm_per_date": ca,
    }


def main() -> None:
    dates = all_dates()
    calm_full = [d for d in dates if d[:4] in CALM_YEARS]
    calm_drop = [d for d in calm_full if d not in DROP]
    assert len(calm_full) == 36 and len(calm_drop) == 34

    # ---- originals, asserted against frozen/published numbers ----
    bond_orig = bond_block(calm_full)
    assert bond_orig["E2_10Y"] == 0.5675 or abs(bond_orig["E2_10Y"] - 0.567) < 6e-4, bond_orig
    assert abs(bond_orig["E2_10Y_ci95"][0] - 0.362) < 6e-4, bond_orig
    assert abs(bond_orig["E2_10Y_ci95"][1] - 0.757) < 6e-4, bond_orig

    vix_orig = vix_block()
    frozen = json.loads((GD1B / "GD1B_RESULTS.json").read_text())
    assert vix_orig["fake_crisis"]["up"] == frozen["fake_crisis"]["up"] == 81
    assert vix_orig["fake_crisis"]["down"] == frozen["fake_crisis"]["down"] == 7
    assert vix_orig["fake_calm"]["up"] == frozen["fake_calm"]["up"] == 160
    assert vix_orig["fake_calm"]["down"] == frozen["fake_calm"]["down"] == 128
    assert abs(vix_orig["fisher_sketch_two_sided_p"]
               - frozen["fisher_exact_two_sided_p"]) < 1e-15
    assert vix_orig["date_level_up_majority"] == {"crisis": "11/11", "calm": "19/36"}, \
        vix_orig["date_level_up_majority"]
    assert abs(vix_orig["fisher_date_two_sided_p"] - 3.8e-3) < 2e-4, \
        vix_orig["fisher_date_two_sided_p"]

    # ---- dropped-set variants (same machinery, calm = 34 dates) ----
    bond_drop = bond_block(calm_drop)
    vix_drop = vix_block(dropped_fake_labels=DROP)

    dropped_rows = [r for r in vix_orig["calm_per_date"] if r["fake_date"] in DROP]
    for blk in (vix_orig, vix_drop):
        blk.pop("calm_per_date")

    res = {
        "provenance": {
            "script": "hindsight/scripts/analyze_taper_dropped.py",
            "frozen_inputs": [
                "hindsight/outputs/gd1/{D,M,W}/rep1/*/01_sketches_valid.json",
                "hindsight/outputs/gd1b/W/rep1/*/01_sketches_valid.json",
                "hindsight/outputs/gd1/GD1_RESULTS.md (asserted)",
                "hindsight/outputs/gd1b/GD1B_RESULTS.json (asserted)",
                "macrochain/data/processed/sketches_panel.jsonl (date grid)",
            ],
            "estimators": "analyze_gd1.down_gap + analyze_fm1.boot_diff "
                          "(B=10000, seed=2026, paired date-level bootstrap); "
                          "scipy fisher_exact two-sided (sketch and date level; "
                          "date majority = up strictly > down)",
            "dropped_calm_dates": list(DROP),
            "reason": "2013-05/2013-06 = taper tantrum, a bond event; 'calm' "
                      "label invalid for the bond/VIX arms (review response)",
        },
        "bond_10y": {"original_36_calm": bond_orig, "dropped_34_calm": bond_drop},
        "vix_micro_arm": {"original_36_calm": vix_orig, "dropped_34_calm": vix_drop,
                          "dropped_fake_calm_dates_detail": dropped_rows},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "taper_dropped.json").write_text(json.dumps(res, indent=2))

    bo, bd = bond_orig, bond_drop
    vo, vd = vix_orig, vix_drop
    md = [
        "# Taper-tantrum calm-set sensitivity (POST-FREEZE EXPLORATORY, 2026-07-24)",
        "",
        "Kimi review: 2013-05/2013-06 are the taper tantrum (a textbook bond event)",
        "yet sit in the frozen calm set. Both second-domain contrasts recomputed with",
        "those two months dropped (calm 36 -> 34), same frozen estimators.",
        "",
        "## GD-1 10Y bond arm (E2_10Y = D-M yield-down gap)",
        "",
        "| calm set | Gap_down(D) | Gap_down(M) | E2_10Y | 95% CI |",
        "|---|---|---|---|---|",
        f"| 36 dates (frozen) | {bo['gap_down_D']:+.3f} | {bo['gap_down_M']:+.3f} "
        f"| **{bo['E2_10Y']:+.3f}** | [{bo['E2_10Y_ci95'][0]:+.3f}, {bo['E2_10Y_ci95'][1]:+.3f}] |",
        f"| 34 dates (dropped) | {bd['gap_down_D']:+.3f} | {bd['gap_down_M']:+.3f} "
        f"| **{bd['E2_10Y']:+.3f}** | [{bd['E2_10Y_ci95'][0]:+.3f}, {bd['E2_10Y_ci95'][1]:+.3f}] |",
        "",
        f"W-arm transplant, fake-minus-true: {bo['W_fake_minus_true']:+.3f} "
        f"CI [{bo['W_fake_minus_true_ci95'][0]:+.3f}, {bo['W_fake_minus_true_ci95'][1]:+.3f}] (36) -> "
        f"{bd['W_fake_minus_true']:+.3f} "
        f"CI [{bd['W_fake_minus_true_ci95'][0]:+.3f}, {bd['W_fake_minus_true_ci95'][1]:+.3f}] (34).",
        "",
        "## GD-1b VIX micro-arm",
        "",
        "| calm set | crisis up-share | calm up-share | delta pp | Fisher p (sketch) "
        "| date-level maj | Fisher p (date) |",
        "|---|---|---|---|---|---|---|",
        f"| 36 dates (frozen) | {vo['fake_crisis']['share_up']:.1%} ({vo['fake_crisis']['up']}/"
        f"{vo['fake_crisis']['up']+vo['fake_crisis']['down']}) | {vo['fake_calm']['share_up']:.1%} "
        f"({vo['fake_calm']['up']}/{vo['fake_calm']['up']+vo['fake_calm']['down']}) "
        f"| **{vo['delta_vix_up_pp']:+.1f}** | {vo['fisher_sketch_two_sided_p']:.2e} "
        f"| {vo['date_level_up_majority']['crisis']} vs {vo['date_level_up_majority']['calm']} "
        f"| {vo['fisher_date_two_sided_p']:.2e} |",
        f"| 34 dates (dropped) | {vd['fake_crisis']['share_up']:.1%} ({vd['fake_crisis']['up']}/"
        f"{vd['fake_crisis']['up']+vd['fake_crisis']['down']}) | {vd['fake_calm']['share_up']:.1%} "
        f"({vd['fake_calm']['up']}/{vd['fake_calm']['up']+vd['fake_calm']['down']}) "
        f"| **{vd['delta_vix_up_pp']:+.1f}** | {vd['fisher_sketch_two_sided_p']:.2e} "
        f"| {vd['date_level_up_majority']['crisis']} vs {vd['date_level_up_majority']['calm']} "
        f"| {vd['fisher_date_two_sided_p']:.2e} |",
        "",
        "Dropped fake-calm dates' own VIX sketches: "
        + "; ".join(f"{r['fake_date']} (true {r['true_date']}): up {r['up']} / down {r['down']}"
                    for r in dropped_rows),
        "",
        "All frozen originals were re-derived from per-date files and asserted",
        "against GD1_RESULTS.md / GD1B_RESULTS.json / paper text before dropping.",
    ]
    (OUT / "taper_dropped.md").write_text("\n".join(md) + "\n")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
