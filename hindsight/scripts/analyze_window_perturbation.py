#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls.

Crisis/calm window perturbation ablation for E2/E3 — ICLR revision plan
§P0-2 (answers reviewer Q1/W5). The preregistered crisis set (11 dates) and
calm years {2013,2014,2017} are analysis-time constructs only (prompts are
partition-independent, run_bench_model.py:70-78), so every perturbation below
recomputes from the frozen bench arms with zero new generation.

Perturbation families (per full-tier model, E2 and E3 both):
  1. leave-one-event-out  drop the GFC block (6 dates), COVID block (2),
     or inflation block (3) — bootstrap CI (frozen util, B=10k, seed 2026)
  2. drop-1-crisis-date jackknife  11 variants, point estimates;
     min/max/sign-flip count reported
  3. alternative calm years  {2013,2014}, {2014,2017}, {2013,2017}, and a
     4-year set. The plan names {2004,...} but 2004 is NOT in the 240-date
     universe (first date 2005-01-15, checked at runtime); the plan's stated
     fallback 2006 is used — verified calm-ish (mean VIX 12.81 from the frozen
     VIXCLS covariate, tied-lowest eligible year with 2005).
  4. balanced-n  calm subsampled to n=11, seed-free deterministic rule:
     walk crisis dates chronologically, each takes its nearest (in days,
     tie -> earlier) not-yet-used calm date.

Reconciliation: with perturbation "none" the recomputed E2/E3 (point AND CI)
must equal the frozen <model>_row.json values bit-exactly — same loaders
(analyze_bench_row.load_arm), same gap/fake_map (analyze_fm1), same bootstrap
util and rng discipline (fresh default_rng(2026) per model, E2 draws then E3
draws, exactly as in the per-model analyze_bench_row invocations).

Excluded rows are listed explicitly in the output with reasons
(llama3.2 65-date reduced tier, smoke dirs, BM2a serving variants).

Writes outputs/review/window_perturbation.{json,md}.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map, gap, CRISIS, CALM_YEARS  # noqa: E402
from analyze_bench_row import load_arm, boot_diff                      # noqa: E402
from hindsight_paths import REPO                                       # noqa: E402

BENCH = REPO / "hindsight/outputs/bench"
VIX_COV = REPO / "hindsight/outputs/fm1/covariates/VIXCLS.json"
OUT_DIR = REPO / "hindsight/outputs/review"
SEED = 2026

INCLUDED = [  # frozen leaderboard order (bench_registry) minus reduced tier
    "gpt-5.5", "claude-sonnet-5", "kimi-k2.6", "qwen3.6-35b-a3b-fp8",
    "qwen3.6-27b-fp8", "gpt-5.4-mini", "claude-haiku-4-5",
    "deepseek-v4-flash", "gemini-2.5-flash", "gemini-2.5-pro",
    "qwen3-30b-a3b-fp8dyn", "llama-3.1-70b-awq", "llama-3.1-8b",
]

EXCLUDED = {
    "llama3.2:1b": "reduced 65-date tier (plan P0-2 边界): crisis/calm blocks "
                   "only partially sampled, re-partition leaves empty cells",
    "llama3.2:3b": "reduced 65-date tier (plan P0-2 边界): same as llama3.2:1b",
    "gpt-5-mini":  "smoke-test dir (<=2 dates), never a leaderboard row, "
                   "no frozen row json",
    "gpt-5.1":     "smoke-test dir (<=2 dates), never a leaderboard row, "
                   "no frozen row json",
    "llama3.1:8b": "smoke-test dir (<=2 dates; the leaderboard row is "
                   "llama-3.1-8b), no frozen row json",
    "qwen3.6-27b-awq":  "BM2a serving-config variant of qwen3.6-27b-fp8, "
                        "not a leaderboard row, no frozen row json",
    "qwen3.6-27b-bf16": "BM2a serving-config variant of qwen3.6-27b-fp8, "
                        "not a leaderboard row, no frozen row json",
}

EVENTS = {
    "GFC":       ["2008-09-15", "2008-10-15", "2008-11-15", "2008-12-15",
                  "2009-01-15", "2009-02-15"],
    "COVID":     ["2020-03-15", "2020-04-15"],
    "inflation": ["2022-06-15", "2022-09-15", "2022-10-15"],
}


def check_universe_and_pick_year(dates: list[str]) -> dict:
    """2004 presence check + VIX-based justification of the fallback year."""
    years = sorted({d[:4] for d in dates})
    crisis_years = sorted({d[:4] for d in CRISIS})
    from collections import defaultdict
    by_year = defaultdict(list)
    for o in json.load(open(VIX_COV))["observations"]:
        if o["value"] != "." and o["date"][:4] in years:
            by_year[o["date"][:4]].append(float(o["value"]))
    vix_mean = {y: round(float(np.mean(v)), 2) for y, v in sorted(by_year.items())}
    eligible = [y for y in years if y not in CALM_YEARS and y not in crisis_years]
    return {
        "2004_in_universe": "2004" in years,
        "universe_years": f"{years[0]}..{years[-1]}",
        "substitute_year": "2006",
        "rationale": "plan fallback 2006; mean VIX 2006 = "
                     f"{vix_mean['2006']} (tied-lowest eligible with 2005 = "
                     f"{vix_mean['2005']}); eligible = universe years minus "
                     "calm years minus crisis-event years",
        "eligible_year_vix_means": {y: vix_mean[y] for y in eligible},
    }


def balanced_calm(calm_full: list[str]) -> list[str]:
    """Deterministic seed-free n=11 calm subsample: crisis dates in
    chronological order each claim their nearest (abs day distance,
    tie -> earlier calm date) not-yet-used calm date."""
    import datetime as dt
    def day(d):
        return dt.date.fromisoformat(d).toordinal()
    used: list[str] = []
    for c in sorted(CRISIS):
        cand = sorted((abs(day(q) - day(c)), q) for q in calm_full if q not in used)
        used.append(cand[0][1])
    return used


def endpoints(D_pre, M_pre, W_pre, w_fake, crisis, calm):
    g_d, g_m = gap(D_pre, crisis, calm), gap(M_pre, crisis, calm)
    g_wf, g_wt = gap(w_fake, crisis, calm), gap(W_pre, crisis, calm)
    return {"E2": {"est": g_d - g_m, "gap_D": g_d, "gap_M": g_m},
            "E3": {"est": g_wf - g_wt, "gap_fake": g_wf, "gap_true": g_wt}}


def cis(D_pre, M_pre, W_pre, w_fake, crisis, calm):
    """Frozen rng discipline: fresh default_rng(SEED), E2 draws then E3 draws
    on the same stream — the exact per-model order of analyze_bench_row."""
    rng = np.random.default_rng(SEED)
    e2_ci = boot_diff(lambda c, q: gap(D_pre, c, q),
                      lambda c, q: gap(M_pre, c, q), crisis, calm, rng)
    e3_ci = boot_diff(lambda c, q: gap(w_fake, c, q),
                      lambda c, q: gap(W_pre, c, q), crisis, calm, rng)
    return list(e2_ci), list(e3_ci)


def sign_held(est, frozen_est):
    if est is None or (isinstance(est, float) and np.isnan(est)):
        return None
    return bool(np.sign(est) == np.sign(frozen_est))


def ci_excludes_zero(ci):
    lo, hi = ci
    if np.isnan(lo) or np.isnan(hi):
        return None
    return bool(lo > 0 or hi < 0)


def main() -> None:
    pre = all_dates()
    preset = set(pre)
    calm_full = [d for d in pre if d[:4] in CALM_YEARS]
    fmap = fake_map(pre)
    assert sorted(d for ev in EVENTS.values() for d in ev) == sorted(CRISIS)

    year_check = check_universe_and_pick_year(pre)
    assert not year_check["2004_in_universe"], "plan branch: 2004 unexpectedly present"
    alt_year = year_check["substitute_year"]
    bal = balanced_calm(calm_full)
    assert len(bal) == len(set(bal)) == len(CRISIS)

    def calm_of(years):
        return [d for d in pre if d[:4] in years]

    # (name, crisis set, calm set, with_ci)
    perts = [("none", list(CRISIS), calm_full, True)]
    perts += [(f"drop_{ev}", [d for d in CRISIS if d not in set(block)],
               calm_full, True) for ev, block in EVENTS.items()]
    perts += [(f"calm_{'_'.join(ys)}", list(CRISIS), calm_of(set(ys)), False)
              for ys in (("2013", "2014"), ("2014", "2017"), ("2013", "2017"),
                         (alt_year, "2013", "2014", "2017"))]
    perts += [("balanced_n11", list(CRISIS), bal, False)]
    jack = [(f"jack_drop_{c}", [d for d in CRISIS if d != c]) for c in CRISIS]

    results, reconciliation, jack_summary = {}, {}, {}
    flips = []
    for model in INCLUDED:
        t0 = time.time()
        root = BENCH / model
        frozen = json.loads((root / f"{model}_row.json").read_text())
        D, _ = load_arm(root, "D")
        M, _ = load_arm(root, "M")
        W, _ = load_arm(root, "W")
        D_pre = {d: v for d, v in D.items() if d in preset}
        M_pre = {d: v for d, v in M.items() if d in preset}
        W_pre = {d: v for d, v in W.items() if d in preset}
        from collections import defaultdict
        w_fake = defaultdict(list)
        for td, xs in W_pre.items():
            w_fake[fmap[td]].extend(xs)

        f_e2, f_e3 = frozen["E2_date_trigger"], frozen["E3_transplant"]
        res = {}
        for name, crisis, calm, with_ci in perts:
            cell = endpoints(D_pre, M_pre, W_pre, w_fake, crisis, calm)
            cell["n_crisis"], cell["n_calm"] = len(crisis), len(calm)
            if with_ci:
                e2_ci, e3_ci = cis(D_pre, M_pre, W_pre, w_fake, crisis, calm)
                cell["E2"]["ci95"] = e2_ci
                cell["E3"]["ci95"] = e3_ci
                cell["E2"]["ci_excludes_zero"] = ci_excludes_zero(e2_ci)
                cell["E3"]["ci_excludes_zero"] = ci_excludes_zero(e3_ci)
            for ep, fro in (("E2", f_e2), ("E3", f_e3)):
                held = sign_held(cell[ep]["est"], fro["est"])
                cell[ep]["sign_held"] = held
                if held is False and name != "none":
                    flips.append({"model": model, "perturbation": name,
                                  "endpoint": ep, "est": cell[ep]["est"],
                                  "frozen_est": fro["est"],
                                  "exact_zero_boundary": cell[ep]["est"] == 0.0})
            res[name] = cell

        jk = {"E2": [], "E3": []}
        for name, crisis in jack:
            cell = endpoints(D_pre, M_pre, W_pre, w_fake, crisis, calm_full)
            jk["E2"].append(cell["E2"]["est"])
            jk["E3"].append(cell["E3"]["est"])
            res[name] = {k: {"est": cell[k]["est"],
                             "sign_held": sign_held(cell[k]["est"],
                                                    (f_e2 if k == "E2" else f_e3)["est"])}
                         for k in ("E2", "E3")}
        jack_summary[model] = {
            ep: {"min": min(jk[ep]), "max": max(jk[ep]),
                 "sign_flips": sum(1 for v in jk[ep]
                                   if np.sign(v) != np.sign((f_e2 if ep == "E2" else f_e3)["est"])),
                 "exact_zeros": sum(1 for v in jk[ep] if v == 0.0),
                 "n_variants": len(jk[ep])}
            for ep in ("E2", "E3")}

        none = res["none"]
        reconciliation[model] = {
            "frozen_E2": {"est": f_e2["est"], "ci95": f_e2["ci95"]},
            "recomputed_E2": {"est": none["E2"]["est"], "ci95": none["E2"]["ci95"]},
            "frozen_E3": {"est": f_e3["est"], "ci95": f_e3["ci95"]},
            "recomputed_E3": {"est": none["E3"]["est"], "ci95": none["E3"]["ci95"]},
            "frozen_E2_ci_excludes_zero": ci_excludes_zero(f_e2["ci95"]),
            "frozen_E3_ci_excludes_zero": ci_excludes_zero(f_e3["ci95"]),
            "bit_exact": bool(
                none["E2"]["est"] == f_e2["est"] and none["E3"]["est"] == f_e3["est"]
                and none["E2"]["ci95"] == list(f_e2["ci95"])
                and none["E3"]["ci95"] == list(f_e3["ci95"])),
            "max_abs_diff": max(
                abs(none["E2"]["est"] - f_e2["est"]),
                abs(none["E3"]["est"] - f_e3["est"]),
                *(abs(a - b) for a, b in zip(none["E2"]["ci95"], f_e2["ci95"])),
                *(abs(a - b) for a, b in zip(none["E3"]["ci95"], f_e3["ci95"]))),
        }
        results[model] = res
        print(f"[{model}] done in {time.time()-t0:.1f}s  "
              f"bit_exact={reconciliation[model]['bit_exact']}", flush=True)

    n_sig = {m: reconciliation[m]["frozen_E2_ci_excludes_zero"] for m in INCLUDED}
    table_perts = [p[0] for p in perts if p[0] != "none"]
    flip_summary = {
        "cells_total_non_jackknife": len(INCLUDED) * len(table_perts) * 2,
        "flips_non_jackknife": len(flips),
        "flips_detail": flips,
        "flips_in_models_with_frozen_E2_ci_excluding_zero": sum(
            1 for f in flips if f["endpoint"] == "E2" and n_sig[f["model"]]),
        "flips_in_models_with_frozen_E3_ci_excluding_zero": sum(
            1 for f in flips if f["endpoint"] == "E3"
            and reconciliation[f["model"]]["frozen_E3_ci_excludes_zero"]),
        "flips_exact_zero_boundary": sum(
            1 for f in flips if f["exact_zero_boundary"]),
        "jackknife_flips_total": sum(
            jack_summary[m][ep]["sign_flips"] for m in INCLUDED for ep in ("E2", "E3")),
    }

    out = {
        "status": "POST-FREEZE EXPLORATORY (review-response, 2026-07-21); "
                  "zero API calls; plan item ICLR_REVISION_PLAN.md §P0-2",
        "convention": "frozen bench arms; pre-cutoff 240-date universe; "
                      "gap/fake_map/loaders reused from analyze_fm1 / "
                      "analyze_bench_row; bootstrap B=10k, fresh "
                      "default_rng(2026) per (model, CI variant), E2 draws "
                      "then E3 draws on one stream (frozen discipline)",
        "universe": {"n_pre_dates": len(pre), "crisis": CRISIS,
                     "calm_years": sorted(CALM_YEARS), "n_calm": len(calm_full),
                     "event_blocks": EVENTS},
        "calm_year_2004_check": year_check,
        "balanced_n11": {"rule": "crisis dates chronological; each claims "
                                 "nearest (abs days, tie -> earlier) unused "
                                 "calm date; seed-free",
                         "dates": bal},
        "included_models": INCLUDED,
        "excluded_models": EXCLUDED,
        "perturbations": {name: {"n_crisis": len(crisis), "n_calm": len(calm),
                                 "ci": with_ci}
                          for name, crisis, calm, with_ci in perts},
        "reconciliation": reconciliation,
        "results": results,
        "jackknife_summary": jack_summary,
        "flip_summary": flip_summary,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "window_perturbation.json").write_text(
        json.dumps(out, indent=2, default=float))

    # ---- markdown summary ----
    def pp(x):
        return "-" if x is None or np.isnan(x) else f"{x*100:+.1f}"

    def ci_s(cell):
        c = cell.get("ci95")
        return "-" if c is None else f"[{c[0]*100:+.1f},{c[1]*100:+.1f}]"

    def ex_s(cell):
        v = cell.get("ci_excludes_zero")
        return "-" if v is None else ("yes" if v else "no")

    L = ["# Crisis/calm window perturbation ablation (P0-2)", "",
         "POST-FREEZE EXPLORATORY (review-response, 2026-07-21); zero API calls.",
         "All numbers recomputed from frozen bench arms; windows are "
         "analysis-time constructs (prompts partition-independent).", "",
         "## Reconciliation (perturbation = none vs frozen row json)", "",
         "| model | frozen E2 | recomputed E2 | frozen E3 | recomputed E3 | bit-exact |",
         "|---|---|---|---|---|---|"]
    for m in INCLUDED:
        r = reconciliation[m]
        L.append(f"| {m} | {pp(r['frozen_E2']['est'])} | "
                 f"{pp(r['recomputed_E2']['est'])} | {pp(r['frozen_E3']['est'])} | "
                 f"{pp(r['recomputed_E3']['est'])} | "
                 f"{'YES' if r['bit_exact'] else 'NO'} |")
    L += ["", "## Excluded rows", ""]
    for k, v in EXCLUDED.items():
        L.append(f"- **{k}**: {v}")
    L += ["", "## Per model x perturbation (E2 / E3, pp; sign-held vs frozen)",
          "", "CIs (B=10k, frozen util/seed) computed for none + "
          "leave-one-event-out only, per plan.", "",
          "| model | perturbation | E2 | E2 CI95 | E2 sign held | E2 CI excl 0 "
          "| E3 | E3 CI95 | E3 sign held | E3 CI excl 0 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for m in INCLUDED:
        for name in ["none"] + table_perts:
            c = results[m][name]
            L.append(f"| {m} | {name} | {pp(c['E2']['est'])} | {ci_s(c['E2'])} | "
                     f"{c['E2']['sign_held']} | {ex_s(c['E2'])} | "
                     f"{pp(c['E3']['est'])} | {ci_s(c['E3'])} | "
                     f"{c['E3']['sign_held']} | {ex_s(c['E3'])} |")
    L += ["", "## Drop-1-crisis-date jackknife (11 variants per model)", "",
          "| model | E2 min..max (pp) | E2 sign flips | E3 min..max (pp) | E3 sign flips |",
          "|---|---|---|---|---|"]
    for m in INCLUDED:
        j = jack_summary[m]
        L.append(f"| {m} | {pp(j['E2']['min'])}..{pp(j['E2']['max'])} | "
                 f"{j['E2']['sign_flips']}/11 | "
                 f"{pp(j['E3']['min'])}..{pp(j['E3']['max'])} | "
                 f"{j['E3']['sign_flips']}/11 |")
    fs = flip_summary
    L += ["", "## Sign-flip summary", "",
          f"- non-jackknife cells (model x perturbation x endpoint): "
          f"{fs['flips_non_jackknife']} flips / {fs['cells_total_non_jackknife']} cells",
          f"- of those, flips where the frozen E2 CI excluded zero: "
          f"{fs['flips_in_models_with_frozen_E2_ci_excluding_zero']}; "
          f"frozen E3 CI excluded zero: "
          f"{fs['flips_in_models_with_frozen_E3_ci_excluding_zero']}",
          f"- of the non-jackknife flips, exact-zero boundaries (estimate "
          f"exactly 0, i.e. gap_fake == gap_true — not a reversal): "
          f"{fs['flips_exact_zero_boundary']}",
          f"- jackknife variant flips (all models, both endpoints): "
          f"{fs['jackknife_flips_total']} / {len(INCLUDED)*2*11}",
          "", f"- calm-year substitute: 2004 not in universe "
          f"({year_check['universe_years']}); used {alt_year} "
          f"(mean VIX {year_check['eligible_year_vix_means'].get('2006')})",
          f"- balanced-n11 calm dates: {', '.join(bal)}"]
    (OUT_DIR / "window_perturbation.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[-8:]))
    print(f"\nwrote {OUT_DIR}/window_perturbation.json + .md")


if __name__ == "__main__":
    main()
