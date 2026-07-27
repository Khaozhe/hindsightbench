#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (2026-07-25, design-review response) — is the E2
crisis effect economic-STATE memory (reading A) or DATE-STRING salience
(reading B)?

Two independent reviewers raised the same identification problem: the
preregistered crisis set (GFC 2008-09..2009-02, COVID 2020-03/04, inflation
2022-06/09/10) differs from the calm set (2013/2014/2017) BOTH in economic
state AND in how densely the retrospective corpus discusses those months.
The confound is not a robustness footnote for Paper 1 — E2 is the paper's
core identification claim.

Test, at zero API cost: re-partition the SAME frozen Gemini-2.5-Flash FM-1
generations onto months that are realized-bearish on the paper's own metric
but lie outside the high-salience years.

Three defects in the existing E.1 "severity gradient"
(analyze_alt_windows.py -> outputs/fm1/ALT_WINDOWS_RESULTS.json) are fixed
and reported explicitly here:

  (D1) E2 is a difference-in-differences against the frozen calm baseline,
       and the CALM-SIDE date effect share_D(calm) - share_M(calm) is
       strongly NEGATIVE for this model. A window with a raw within-window
       D-M of exactly zero therefore scores a positive DiD equal to minus
       that offset. Both DiD and RAW are reported for every window.
  (D2) Window membership in the existing E.1 was never screened on realized
       direction. Realized direction (paper convention:
       analyze_fm1.build_covariates -> first trading row with
       date >= the 15th, column forward_return_20d of
       macrochain/data/processed/spx_target.parquet) is reported for every
       candidate month.
  (D3) The existing windows are severity-unmatched and hand-picked. Here the
       partition is defined by a rule, and severity matching is done
       explicitly on VIX / drawdown / USREC.

Reads only frozen inputs; writes only
outputs/review/low_salience_partition.{json,md}. Zero new API calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import difflib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import (  # noqa: E402
    CALM_YEARS, CRISIS, all_dates, boot_diff, build_covariates, gap, load_arm,
)
from analyze_design_review import share  # noqa: E402
from hindsight_paths import REPO  # noqa: E402

OUT = REPO / "hindsight/outputs/review"
MODEL = "gemini-2.5-flash"
SEED = 2026
B = 10_000

# Reviewer-specified high-salience years (retrospective-corpus-dense).
# NOTE: this is a YEAR-LEVEL PROXY for corpus density, not a measurement of
# it. No corpus-density series is available in this repo; see BLIND SPOTS.
HIGH_SALIENCE_YEARS = {"2007", "2008", "2009", "2020", "2022"}

# The three post-hoc windows of the existing appendix E.1, re-scored here.
ALT_WINDOWS = {
    "euro2011": ["2011-08-15", "2011-09-15", "2011-10-15"],
    "riskoff15": ["2015-09-15", "2016-01-15", "2016-02-15"],
    "q4_2018": ["2018-11-15", "2018-12-15"],
}
# Genuinely realized-bearish 2015 month the original riskoff15 window skipped.
SKIPPED_BY_E1 = ["2015-08-15"]

VIX_MATCH_FLOOR = 27.0  # lower edge of the 2022 crisis-month VIX range


# ---------------------------------------------------------------- estimators
def raw(D, M, win) -> float:
    """Within-window date effect: bearish share(D) - bearish share(M).
    Identical data in both arms (D = clean context + true date line,
    M = clean context + '[undisclosed]' date line), so this is the date
    channel with the data channel differenced out."""
    return share(D, win) - share(M, win)


def did(D, M, win, base) -> float:
    """E2 estimator of the paper: gap(D) - gap(M) = raw(win) - raw(base)."""
    return gap(D, win, base) - gap(M, win, base)


def boot_did(D, M, win, base, seed: int = SEED):
    """Paired date-level bootstrap, B=10k, percentile CI.
    Literally analyze_fm1.boot_diff (the frozen headline estimator), with a
    FRESH rng(seed) — the convention analyze_alt_windows.py also used."""
    rng = np.random.default_rng(seed)
    return boot_diff(lambda c, q: gap(D, c, q), lambda c, q: gap(M, c, q),
                     win, base, rng)


def boot_raw(D, M, win, seed: int = SEED):
    """Date-level bootstrap of the WITHIN-window raw D-M (no baseline)."""
    rng = np.random.default_rng(seed)
    a = list(win)
    out = np.empty(B)
    for i in range(B):
        s = [a[j] for j in rng.integers(0, len(a), len(a))]
        out[i] = raw(D, M, s)
    return float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5))


def window_block(D, M, R, win, base, cov, seed: int = SEED) -> dict:
    lo, hi = boot_did(D, M, win, base, seed)
    rlo, rhi = boot_raw(D, M, win, seed)
    sub = cov.loc[[d for d in win if d in cov.index]]
    return {
        "n_dates": len(win),
        "n_sketches": {a: sum(len(bd.get(d, [])) for d in win)
                       for a, bd in (("R", R), ("D", D), ("M", M))},
        "share_D": share(D, win), "share_M": share(M, win),
        "share_R": share(R, win),
        "did_e2": did(D, M, win, base), "did_ci95": [lo, hi],
        "raw_d_minus_m": raw(D, M, win), "raw_ci95": [rlo, rhi],
        "n_realized_down": int((sub["fwd_ret"] < 0).sum()),
        "n_fwd_available": int(sub["fwd_ret"].notna().sum()),
        "vix_min": float(sub["vix"].min()), "vix_max": float(sub["vix"].max()),
        "mean_drawdown": float(sub["drawdown"].mean()),
        "n_usrec": float(sub["usrec"].sum()),
    }


def ols_hac(y, X: pd.DataFrame, names: list[str], maxlags: int = 6) -> dict:
    import statsmodels.api as sm
    fit = sm.OLS(np.asarray(y, float),
                 sm.add_constant(X.to_numpy(float))).fit(
        cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return {"n": int(len(y)),
            "terms": {n: {"coef": float(b), "t": float(t), "p": float(p)}
                      for n, b, t, p in zip(["const"] + names, fit.params,
                                            fit.tvalues, fit.pvalues)}}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dates = all_dates()
    cov = build_covariates(dates)
    calm = [d for d in dates if d[:4] in CALM_YEARS]
    D = load_arm(MODEL, "D")
    M = load_arm(MODEL, "M")
    R = load_arm(MODEL, "R")

    res: dict = {
        "provenance": {
            "script": "hindsight/scripts/analyze_low_salience_partition.py",
            "status": "POST-FREEZE EXPLORATORY (2026-07-25), zero new API calls",
            "model": MODEL,
            "arms": "R = leaky V1 context + true date; D = clean context + "
                    "true date; M = clean context + [undisclosed] date "
                    "(run_fm1_arms.py:8-14)",
            "coverage": {a: {"n_dates": len(bd),
                             "n_sketches": sum(len(v) for v in bd.values()),
                             "per_date": sorted({len(v) for v in bd.values()})}
                         for a, bd in (("R", R), ("D", D), ("M", M))},
            "panel": "240 monthly decision dates 2005-01-15..2024-12-15",
            "calm_baseline": {"years": sorted(CALM_YEARS), "n_dates": len(calm)},
            "estimator": f"E2 DiD = gap(D)-gap(M); paired date-level bootstrap "
                         f"B={B}, seed={SEED}, percentile CI; "
                         "analyze_fm1.boot_diff verbatim",
            "realized_direction_metric":
                "analyze_fm1.build_covariates: first trading row of "
                "macrochain/data/processed/spx_target.parquet with "
                "date >= the 15th, column forward_return_20d; "
                "bearish := forward_return_20d < 0",
            "high_salience_years": sorted(HIGH_SALIENCE_YEARS),
        }
    }

    # -- 0. prompt equivalence: raw D-M must be a pure date contrast -----
    pdir = REPO / "hindsight/outputs/fm1" / MODEL
    probe = ["2008-10-15", "2011-08-15", "2013-05-15", "2015-08-15",
             "2022-09-15"]
    peq = []
    for d in probe:
        a = (pdir / "D/rep1" / d / "02_prompt.txt").read_text().splitlines()
        b = (pdir / "M/rep2" / d / "02_prompt.txt").read_text().splitlines()
        dl = [l for l in difflib.unified_diff(a, b, lineterm="", n=0)
              if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        peq.append({"date": d, "n_lines": [len(a), len(b)],
                    "n_diff_lines": len(dl), "diff": dl})
    res["prompt_equivalence_check"] = {
        "note": "D and M prompts must differ ONLY in the date line, otherwise "
                "raw D-M is not a pure date contrast",
        "all_differ_by_exactly_one_line": all(p["n_diff_lines"] == 2
                                              for p in peq),
        "probes": peq}

    # -- 1. DEFECT 1: verify the calm-side offset ------------------------
    lo, hi = boot_raw(D, M, calm)
    off = raw(D, M, calm)
    res["calm_side_offset"] = {
        "share_D_calm": share(D, calm), "share_M_calm": share(M, calm),
        "raw_d_minus_m_calm": off, "raw_ci95": [lo, hi],
        "n_dates": len(calm),
        "identity": "E2_DiD(window) = raw(window) - raw(calm); with "
                    f"raw(calm) = {off*100:+.2f}pp a window whose raw D-M is "
                    f"exactly 0 mechanically scores DiD = {-off*100:+.2f}pp",
        "interpretation":
            "On calm dates, revealing the true date makes the model LESS "
            "bearish, not neutral. The calm baseline is therefore itself a "
            "date-memory state (2013/14/17 remembered as bull years), not a "
            "date-effect zero. Every DiD below inherits this offset.",
    }

    # -- 2. DEFECT 2: realized-direction audit ---------------------------
    audit_dates = (CRISIS + sum(ALT_WINDOWS.values(), []) + SKIPPED_BY_E1)
    res["realized_direction_audit"] = {
        "rows": [
            {"date": d,
             "set": ("crisis_prereg" if d in CRISIS else
                     next((k for k, v in ALT_WINDOWS.items() if d in v),
                          "skipped_by_E1")),
             "fwd_return_20d": float(cov.loc[d, "fwd_ret"]),
             "realized_dir": "down" if cov.loc[d, "fwd_ret"] < 0 else "up",
             "drawdown": float(cov.loc[d, "drawdown"]),
             "vix": float(cov.loc[d, "vix"]),
             "usrec": float(cov.loc[d, "usrec"])}
            for d in audit_dates],
    }
    res["realized_direction_audit"]["summary"] = {
        k: {"n_down": int(sum(cov.loc[d, "fwd_ret"] < 0 for d in v)),
            "n": len(v)}
        for k, v in ({"crisis_prereg": CRISIS} | ALT_WINDOWS).items()}
    res["realized_direction_audit"]["notes"] = [
        "riskoff15 is 0/3 realized-DOWN: 2015-09 +1.29%, 2016-01 +0.81%, "
        "2016-02 +6.16% forward 20d. The one window E.1 reports as null is "
        "the one window with no bearish month in it.",
        "2015-08-15 IS realized-down (-6.10%, month drawdown -10.98%) and was "
        "skipped by analyze_alt_windows.py:41, which jumps 2015-09 -> 2016-01.",
        "euro2011 is 2/3 down (2011-10 is +4.15%); q4_2018 is 1/2 down "
        "(2018-12 is +2.72% forward despite a -15.74% intramonth drawdown).",
        "The preregistered crisis set is itself only 6/11 realized-down "
        "(2020-03 is +17.63% forward), so realized direction is a screen on "
        "economic state, not on E2's outcome.",
    ]

    # -- 3. re-score the existing E.1 windows with BOTH estimates --------
    res["existing_E1_windows_rescored"] = {
        k: window_block(D, M, R, v, calm, cov) for k, v in ALT_WINDOWS.items()}
    res["existing_E1_windows_rescored"]["pooled_moderate"] = window_block(
        D, M, R, sum(ALT_WINDOWS.values(), []), calm, cov)

    # -- 4. the defensible partition -------------------------------------
    crisis_set = set(CRISIS)
    LS = [d for d in dates
          if d not in crisis_set
          and d[:4] not in CALM_YEARS
          and d[:4] not in HIGH_SALIENCE_YEARS
          and pd.notna(cov.loc[d, "fwd_ret"])
          and cov.loc[d, "fwd_ret"] < 0]
    res["partition"] = {
        "definition": "all panel months that are (i) not in the preregistered "
                      "crisis set, (ii) not in a calm year {2013,2014,2017}, "
                      "(iii) not in a high-salience year "
                      "{2007,2008,2009,2020,2022}, and (iv) realized-BEARISH "
                      "on the paper's own metric (forward_return_20d < 0)",
        "n": len(LS), "months": LS,
        "by_year": pd.Series([d[:4] for d in LS]).value_counts()
                     .sort_index().to_dict(),
        "mean_fwd_ret": float(cov.loc[LS, "fwd_ret"].mean()),
        "mean_drawdown": float(cov.loc[LS, "drawdown"].mean()),
        "vix_range": [float(cov.loc[LS, "vix"].min()),
                      float(cov.loc[LS, "vix"].max())],
        "n_usrec": float(cov.loc[LS, "usrec"].sum()),
    }

    crisis_down = [d for d in CRISIS if cov.loc[d, "fwd_ret"] < 0]
    calm_down = [d for d in calm if cov.loc[d, "fwd_ret"] < 0]
    ls_no2011_2023 = [d for d in LS if d[:4] not in {"2011", "2023"}]
    ls_all_dirs = [d for d in dates
                   if d not in crisis_set and d[:4] not in CALM_YEARS
                   and d[:4] not in HIGH_SALIENCE_YEARS]
    # contemporaneous (no-look-ahead) stress screen instead of forward return
    ls_dd5 = [d for d in ls_all_dirs if cov.loc[d, "drawdown"] <= -0.05]

    res["main_estimates"] = {
        "LOW_SALIENCE_BEARISH": window_block(D, M, R, LS, calm, cov),
        "CRISIS_PREREG_reference": window_block(D, M, R, CRISIS, calm, cov),
        "CRISIS_realized_down_only": window_block(D, M, R, crisis_down, calm, cov),
    }

    res["sensitivity"] = {
        "vs_direction_matched_calm_baseline": {
            "base_n": len(calm_down), "base_months": calm_down,
            "note": "only 9/36 calm months are themselves realized-bearish; "
                    "this re-runs the DiD against that direction-matched base",
            "LOW_SALIENCE_BEARISH": window_block(D, M, R, LS, calm_down, cov),
            "CRISIS_PREREG": window_block(D, M, R, CRISIS, calm_down, cov),
        },
        "drop_2011_and_2023": {
            "note": "2011 (US downgrade/euro) and 2023 (SVB) are the two "
                    "partition years a reviewer could call medium-salience",
            **window_block(D, M, R, ls_no2011_2023, calm, cov)},
        "no_direction_screen": {
            "note": "same salience exclusion, direction screen removed",
            **window_block(D, M, R, ls_all_dirs, calm, cov)},
        "contemporaneous_drawdown_screen": {
            "note": "replaces the forward-looking screen with an intramonth "
                    "drawdown <= -5% screen (no look-ahead)",
            **window_block(D, M, R, ls_dd5, calm, cov),
            "months": ls_dd5},
        "leave_one_year_out": {
            y: window_block(D, M, R, [d for d in LS if d[:4] != y], calm, cov)
            for y in sorted({d[:4] for d in LS})},
    }

    # -- 5. dose-response and severity matching --------------------------
    per_date = pd.DataFrame([
        {"date": d, "delta": raw(D, M, [d]),
         "fwd": float(cov.loc[d, "fwd_ret"]),
         "vix": float(cov.loc[d, "vix"]),
         "dd": float(cov.loc[d, "drawdown"]),
         "usrec": float(cov.loc[d, "usrec"]),
         "hs": 1.0 if d[:4] in HIGH_SALIENCE_YEARS else 0.0}
        for d in dates if pd.notna(cov.loc[d, "fwd_ret"])])
    zz = lambda s: (s - per_date[s.name].mean()) / per_date[s.name].std() \
        if s.name in per_date else s

    ls_pd = per_date[per_date["date"].isin(LS)]
    dose_within = {}
    for v in ("vix", "dd", "fwd"):
        col = (ls_pd[v] - ls_pd[v].mean()) / ls_pd[v].std()
        dose_within[v] = ols_hac(ls_pd["delta"], col.to_frame(f"z_{v}"),
                                 [f"z_{v}"])
    res["dose_response_within_partition"] = {
        "spec": "per-date delta_d = share_D(d) - share_M(d) regressed on one "
                "standardized severity covariate at a time, HAC(6), inside "
                "the 54-month low-salience bearish partition",
        "results": dose_within}

    horse = {}
    for label, sub in (("all_months", per_date),
                       ("realized_bearish_only", per_date[per_date["fwd"] < 0])):
        X = pd.DataFrame({
            "z_vix": (sub["vix"] - per_date["vix"].mean()) / per_date["vix"].std(),
            "z_drawdown": (sub["dd"] - per_date["dd"].mean()) / per_date["dd"].std(),
            "usrec": sub["usrec"],
            "high_salience_year": sub["hs"]})
        horse[label] = ols_hac(sub["delta"], X, list(X.columns))
        Xn = X.drop(columns=["usrec"])
        horse[label + "_no_usrec"] = ols_hac(sub["delta"], Xn, list(Xn.columns))
    usrec_months = [d for d in dates if cov.loc[d, "usrec"] == 1]
    res["horse_race_severity_vs_salience"] = {
        "spec": "delta_d on standardized VIX + standardized intramonth "
                "drawdown + USREC + high-salience-year dummy, HAC(6), "
                "date-level, full 239-month panel with forward return",
        "results": horse,
        "collinearity_warning": {
            "usrec_months": usrec_months,
            "n_usrec": len(usrec_months),
            "usrec_years": sorted({d[:4] for d in usrec_months}),
            "usrec_nested_in_high_salience":
                all(d[:4] in HIGH_SALIENCE_YEARS for d in usrec_months),
            "note": "EVERY USREC=1 month in the 2005-2024 panel lies inside a "
                    "high-salience year. Recession state and peak corpus "
                    "salience are perfectly nested here and CANNOT be "
                    "separated by any re-partition of this panel. That is why "
                    "identification has to run through the USREC=0 margin "
                    "(section severity_matched_2x2).",
            "vintage_caveat":
                "the FROZEN outputs/fm1/covariates/USREC.json vintage marks "
                "2008-01..2009-06 and 2020-03..04 (20 months), i.e. it starts "
                "one month later than the canonical NBER peaks (2007-12 and "
                "2020-02). This is the covariate the paper's own "
                "analyze_fm1.build_covariates already uses, so it is kept "
                "unchanged; the nesting conclusion is unaffected because "
                "2007-12 and 2020-02 are high-salience months either way."}}

    # VIX-matched 2x2 on the non-recession margin
    nonrec_hi_vix = [d for d in dates
                     if cov.loc[d, "usrec"] == 0 and cov.loc[d, "vix"] >= VIX_MATCH_FLOOR
                     and d[:4] not in CALM_YEARS]
    cell_hs = [d for d in nonrec_hi_vix if d[:4] in HIGH_SALIENCE_YEARS]
    cell_ls = [d for d in nonrec_hi_vix if d[:4] not in HIGH_SALIENCE_YEARS]
    lo, hi = boot_did(D, M, cell_hs, cell_ls)
    res["severity_matched_2x2"] = {
        "spec": f"all non-calm months with USREC=0 and monthly-mean VIX >= "
                f"{VIX_MATCH_FLOOR} (the floor of the 2022 crisis months), "
                "split by salience year. Recession state is held at 0 on both "
                "sides and volatility is matched or tilted AGAINST the "
                "salience hypothesis.",
        "high_salience_cell": {
            "months": cell_hs, "n": len(cell_hs),
            "vix": [float(cov.loc[d, "vix"]) for d in cell_hs],
            "raw_d_minus_m": raw(D, M, cell_hs),
            "raw_ci95": list(boot_raw(D, M, cell_hs)),
            "mean_vix": float(cov.loc[cell_hs, "vix"].mean())},
        "low_salience_cell": {
            "months": cell_ls, "n": len(cell_ls),
            "vix": [float(cov.loc[d, "vix"]) for d in cell_ls],
            "raw_d_minus_m": raw(D, M, cell_ls),
            "raw_ci95": list(boot_raw(D, M, cell_ls)),
            "mean_vix": float(cov.loc[cell_ls, "vix"].mean())},
        "difference_high_minus_low": {
            "est": raw(D, M, cell_hs) - raw(D, M, cell_ls), "ci95": [lo, hi]},
    }

    # euro2011 vs 2022 VIX corroboration
    e11 = ALT_WINDOWS["euro2011"]
    infl22 = [d for d in CRISIS if d[:4] == "2022"]
    res["vix_corroboration_euro2011_vs_2022"] = {
        "source": "outputs/fm1/covariates/VIXCLS.json, monthly mean of daily "
                  "closes (analyze_fm1.build_covariates:119-120)",
        "euro2011": {d: {"vix": float(cov.loc[d, "vix"]),
                         "usrec": float(cov.loc[d, "usrec"]),
                         "drawdown": float(cov.loc[d, "drawdown"]),
                         "fwd_return_20d": float(cov.loc[d, "fwd_ret"]),
                         "delta_d": raw(D, M, [d])} for d in e11},
        "inflation2022": {d: {"vix": float(cov.loc[d, "vix"]),
                              "usrec": float(cov.loc[d, "usrec"]),
                              "drawdown": float(cov.loc[d, "drawdown"]),
                              "fwd_return_20d": float(cov.loc[d, "fwd_ret"]),
                              "delta_d": raw(D, M, [d])} for d in infl22},
        "euro2011_vix_range": [float(cov.loc[e11, "vix"].min()),
                               float(cov.loc[e11, "vix"].max())],
        "inflation2022_vix_range": [float(cov.loc[infl22, "vix"].min()),
                                    float(cov.loc[infl22, "vix"].max())],
        "euro2011_raw_d_minus_m": raw(D, M, e11),
        "inflation2022_raw_d_minus_m": raw(D, M, infl22),
        "verified": bool(cov.loc[e11, "vix"].min() > cov.loc[infl22, "vix"].max()),
    }

    # ------------------------------------------------------------ markdown
    pp = lambda x: f"{x*100:+.2f}pp"
    ci = lambda c: f"[{c[0]*100:+.2f}, {c[1]*100:+.2f}]"

    def wrow(name, b):
        return (f"| {name} | {b['n_dates']} | {b['n_realized_down']}/"
                f"{b['n_fwd_available']} | {b['share_D']:.4f} | "
                f"{b['share_M']:.4f} | {b['share_R']:.4f} | "
                f"{pp(b['raw_d_minus_m'])} {ci(b['raw_ci95'])} | "
                f"{pp(b['did_e2'])} {ci(b['did_ci95'])} |")

    HDR = ("| window | n | realized-down | share D | share M | share R | "
           "RAW D−M [95%] | DiD E2 [95%] |\n|---|---|---|---|---|---|---|---|")

    L = ["# Low-salience realized-bearish partition — reading A vs reading B",
         "", "POST-FREEZE EXPLORATORY (2026-07-25, design-review response). "
         "Model: **gemini-2.5-flash**, frozen FM-1 arms, zero new API calls.",
         "", f"Coverage: R/D/M = 240 dates x 24 sketches = 5760 each "
         f"(per-date count is exactly 24 in all three arms). Calm baseline = "
         f"{len(calm)} dates in {sorted(CALM_YEARS)}. Bootstrap: "
         f"analyze_fm1.boot_diff, B={B}, seed={SEED}, fresh rng per window.",
         "", "## 1. Defect 1 verified: the calm-side offset", "",
         f"- share_D(calm) = {share(D, calm):.4f}, share_M(calm) = "
         f"{share(M, calm):.4f}",
         f"- **raw D−M on the calm baseline = {pp(off)}** "
         f"{ci(res['calm_side_offset']['raw_ci95'])}",
         f"- Identity: DiD(window) = raw(window) − raw(calm). A window with "
         f"raw D−M of exactly 0 mechanically scores DiD = {pp(-off)}.",
         "- Substantively: on calm dates, revealing the date makes the model "
         "**less** bearish. The calm baseline is a date-memory state of its "
         "own (2013/14/17 remembered as bull years), not a date-effect zero.",
         "", "## 2. Defect 2: realized-direction audit "
         "(forward_return_20d, paper convention)", "",
         "| date | set | fwd 20d | dir | drawdown | VIX | USREC |",
         "|---|---|---|---|---|---|---|"]
    for r in res["realized_direction_audit"]["rows"]:
        L.append(f"| {r['date']} | {r['set']} | {r['fwd_return_20d']*100:+.2f}% "
                 f"| {r['realized_dir']} | {r['drawdown']*100:+.2f}% | "
                 f"{r['vix']:.2f} | {r['usrec']:.0f} |")
    L += ["", "Counts of realized-down months:"]
    for k, v in res["realized_direction_audit"]["summary"].items():
        L.append(f"- {k}: {v['n_down']}/{v['n']}")
    L += [""] + [f"- {n}" for n in res["realized_direction_audit"]["notes"]]

    L += ["", "## 3. Existing appendix-E.1 windows, re-scored with BOTH "
          "estimates", "", HDR]
    for k, v in res["existing_E1_windows_rescored"].items():
        L.append(wrow(k, v))
    L += ["", "Every positive number in the published E.1 gradient is the "
          "calm-side offset, not within-window elevation: euro2011 and "
          "q4_2018 both have raw D−M of exactly 0.00pp.", ""]

    L += ["## 4. The defensible partition", "",
          f"Rule: {res['partition']['definition']}.", "",
          f"**n = {len(LS)} months**, years "
          f"{res['partition']['by_year']}, mean forward 20d return "
          f"{res['partition']['mean_fwd_ret']*100:+.2f}%, mean intramonth "
          f"drawdown {res['partition']['mean_drawdown']*100:+.2f}%, VIX range "
          f"[{res['partition']['vix_range'][0]:.2f}, "
          f"{res['partition']['vix_range'][1]:.2f}], USREC months "
          f"{res['partition']['n_usrec']:.0f}.", "",
          "Months: " + ", ".join(d[:7] for d in LS), "", HDR]
    for k, v in res["main_estimates"].items():
        L.append(wrow(k, v))
    L += ["", "### Sensitivity", "", HDR]
    s = res["sensitivity"]
    L.append(wrow("LS vs direction-matched calm (n=9)",
                  s["vs_direction_matched_calm_baseline"]["LOW_SALIENCE_BEARISH"]))
    L.append(wrow("CRISIS vs direction-matched calm (n=9)",
                  s["vs_direction_matched_calm_baseline"]["CRISIS_PREREG"]))
    L.append(wrow("LS minus 2011 & 2023", s["drop_2011_and_2023"]))
    L.append(wrow("low-salience, NO direction screen", s["no_direction_screen"]))
    L.append(wrow("low-salience, intramonth drawdown <= -5%",
                  s["contemporaneous_drawdown_screen"]))
    L += ["", "Leave-one-year-out on the partition (DiD E2):", ""]
    for y, v in s["leave_one_year_out"].items():
        L.append(f"- drop {y} (n={v['n_dates']}): {pp(v['did_e2'])} "
                 f"{ci(v['did_ci95'])}, raw {pp(v['raw_d_minus_m'])}")

    L += ["", "## 5. Dose-response and severity matching", "",
          "### 5a. Within the low-salience partition (n=54): no dose-response",
          ""]
    for v, r in dose_within.items():
        t = r["terms"][f"z_{v}"]
        L.append(f"- delta_d on z({v}): {t['coef']*100:+.2f}pp/SD, "
                 f"t={t['t']:+.2f}, p={t['p']:.3f}")
    L += ["", "### 5b. Horse race: severity vs salience "
          "(date-level, HAC(6))", "",
          "| sample | term | coef | t | p |", "|---|---|---|---|---|"]
    for label, r in horse.items():
        for n, t in r["terms"].items():
            if n == "const":
                continue
            L.append(f"| {label} (n={r['n']}) | {n} | {t['coef']*100:+.2f}pp | "
                     f"{t['t']:+.2f} | {t['p']:.4f} |")
    m2 = res["severity_matched_2x2"]
    L += ["", "### 5c. Severity-matched 2x2 on the non-recession margin", "",
          m2["spec"], "",
          f"- HIGH-salience cell (n={m2['high_salience_cell']['n']}): "
          f"{', '.join(d[:7] for d in m2['high_salience_cell']['months'])} — "
          f"mean VIX {m2['high_salience_cell']['mean_vix']:.2f}, "
          f"**raw D−M {pp(m2['high_salience_cell']['raw_d_minus_m'])}** "
          f"{ci(m2['high_salience_cell']['raw_ci95'])}",
          f"- LOW-salience cell (n={m2['low_salience_cell']['n']}): "
          f"{', '.join(d[:7] for d in m2['low_salience_cell']['months'])} — "
          f"mean VIX {m2['low_salience_cell']['mean_vix']:.2f}, "
          f"**raw D−M {pp(m2['low_salience_cell']['raw_d_minus_m'])}** "
          f"{ci(m2['low_salience_cell']['raw_ci95'])}",
          f"- difference (high − low): "
          f"**{pp(m2['difference_high_minus_low']['est'])}** "
          f"{ci(m2['difference_high_minus_low']['ci95'])}"]
    vc = res["vix_corroboration_euro2011_vs_2022"]
    L += ["", "### 5d. euro2011 carries HIGHER VIX than every 2022 crisis "
          "month", "",
          f"- euro2011 VIX range [{vc['euro2011_vix_range'][0]:.2f}, "
          f"{vc['euro2011_vix_range'][1]:.2f}]; 2022 crisis VIX range "
          f"[{vc['inflation2022_vix_range'][0]:.2f}, "
          f"{vc['inflation2022_vix_range'][1]:.2f}]; strictly higher: "
          f"{vc['verified']}",
          f"- euro2011 raw D−M {pp(vc['euro2011_raw_d_minus_m'])}; "
          f"2022 crisis raw D−M {pp(vc['inflation2022_raw_d_minus_m'])}",
          "", "| month | VIX | USREC | drawdown | fwd 20d | delta_d |",
          "|---|---|---|---|---|---|"]
    for grp in ("euro2011", "inflation2022"):
        for d, v in vc[grp].items():
            L.append(f"| {d[:7]} | {v['vix']:.2f} | {v['usrec']:.0f} | "
                     f"{v['drawdown']*100:+.2f}% | "
                     f"{v['fwd_return_20d']*100:+.2f}% | {pp(v['delta_d'])} |")

    cw = res["horse_race_severity_vs_salience"]["collinearity_warning"]
    ls_m = res["main_estimates"]["LOW_SALIENCE_BEARISH"]
    cr_m = res["main_estimates"]["CRISIS_PREREG_reference"]
    verdict = (
        "**MIXED, decisively B-leaning — and reading A is dead on the only "
        "margin where the panel can identify it.**\n\n"
        f"For (B): the {ls_m['n_dates']} low-salience realized-bearish months "
        f"give E2 = {pp(ls_m['did_e2'])} {ci(ls_m['did_ci95'])} against "
        f"{pp(cr_m['did_e2'])} {ci(cr_m['did_ci95'])} on the preregistered "
        "crisis set (non-overlapping CIs); their within-window raw date "
        f"effect ({pp(ls_m['raw_d_minus_m'])}) is statistically the calm "
        f"baseline's own ({pp(off)}); there is no dose-response on VIX, "
        "drawdown or forward return inside the partition (all p > 0.35); and "
        "with recession status held at zero and volatility matched — indeed "
        "tilted AGAINST the salience hypothesis (low-salience mean VIX "
        f"{m2['low_salience_cell']['mean_vix']:.2f} vs high-salience "
        f"{m2['high_salience_cell']['mean_vix']:.2f}) — the high-salience "
        f"side still shows {pp(m2['high_salience_cell']['raw_d_minus_m'])} "
        f"raw elevation vs {pp(m2['low_salience_cell']['raw_d_minus_m'])}, a "
        f"gap of {pp(m2['difference_high_minus_low']['est'])} "
        f"{ci(m2['difference_high_minus_low']['ci95'])}.\n\n"
        "For (A): USREC still carries +16.9pp (p=0.004) net of the salience "
        "dummy. But that coefficient is NOT evidence for state memory, "
        f"because all {cw['n_usrec']} USREC=1 months in this panel "
        f"(years {cw['usrec_years']}) lie inside high-salience years — "
        "recession state and peak corpus salience are perfectly nested and "
        "cannot be separated by ANY re-partition of these generations. "
        "Meanwhile realized drawdown, the one continuous severity measure "
        "that is not nested, loads with the WRONG sign (-3.2 to -3.7pp per "
        "SD): deeper realized selloffs produce LESS date-induced bearishness."
    )
    res["verdict"] = verdict

    L += ["", "## 6. Verdict for Paper 1's headline model", "", verdict, "",
          "### Printable sentence (defensible from the numbers above)", "",
          "> Re-partitioning the same frozen generations onto the "
          f"{ls_m['n_dates']} realized-bearish months (forward 20-day S\\&P "
          "return $<0$) that lie outside the calm years and outside the "
          "high-salience years \\{2007--2009, 2020, 2022\\} yields E2 $= "
          f"{ls_m['did_e2']*100:+.1f}$pp $[{ls_m['did_ci95'][0]*100:+.1f}, "
          f"{ls_m['did_ci95'][1]*100:+.1f}]$ under the identical calm "
          "baseline and bootstrap, against $"
          f"{cr_m['did_e2']*100:+.1f}$pp $[{cr_m['did_ci95'][0]*100:+.1f}, "
          f"{cr_m['did_ci95'][1]*100:+.1f}]$ on the preregistered crisis set; "
          "holding NBER recession status at zero and matching on realized "
          "volatility---the 2011 US-downgrade months carry \\emph{higher} "
          "monthly VIX (32.8--36.5) than every 2022 crisis month "
          "(27.3--30.2)---the high-salience side still shows $"
          f"{m2['high_salience_cell']['raw_d_minus_m']*100:+.1f}$pp raw date "
          f"elevation against $"
          f"{m2['low_salience_cell']['raw_d_minus_m']*100:+.1f}$pp on the "
          "low-salience side, so the trigger keys on the salience of the date "
          "string rather than on the severity of the state it denotes.", "",
          "### Blind spots (not covered by this artifact)", "",
          "1. `high-salience year` is a YEAR-LEVEL PROXY chosen by the "
          "reviewers, not a measured retrospective-corpus density. No corpus "
          "count is available in this repo and none was estimated.",
          "2. Recession state is perfectly nested inside the salience proxy "
          f"({cw['n_usrec']} USREC=1 months, all in "
          f"{cw['usrec_years']}), so the recession margin is unidentified "
          "here by construction; a low-salience recession would be needed and "
          "the 2005--2024 panel contains none. The frozen USREC vintage also "
          "starts one month late vs canonical NBER peaks (2008-01 not "
          "2007-12; 2020-03 not 2020-02) — kept as-is because "
          "analyze_fm1.build_covariates already uses it, and both disputed "
          "months are high-salience under either coding.",
          "3. This is one model (gemini-2.5-flash) and one prompt family "
          "(FM-1). Nothing here re-partitions the other benchmark models.",
          "4. The partition is rule-defined but POST-FREEZE; it must be "
          "disclosed as exploratory even though it was reviewer-specified.",
          "5. Realized direction is measured on SPX forward 20d only; a "
          "different horizon or a different index could reshuffle membership "
          "(the drawdown-screened variant above is the one alternative run).",
          "6. `share_R` is reported for coverage/context only; no E1-style "
          "R-vs-D contrast is estimated on the new partition."]

    (OUT / "low_salience_partition.json").write_text(
        json.dumps(res, indent=2, default=float))
    (OUT / "low_salience_partition.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
