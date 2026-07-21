#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls.

Alternative-transplant-offset re-analysis for reviewer Q5, extracted from data
already on disk: the frozen W arm's single fake-date map
    fake_for[dates[i]] = dates[(i + 66) % 240]      (run_bench_model.py:36,60;
                                                     run_fm1_arms.py:53,173)
is NOT one displacement — over the 240 sorted pre-cutoff monthly dates
(2005-01-15 .. 2024-12-15, verified consecutive at runtime) it contains two
displacement families:
    fwd66   source cells i < 174  (true dates 2005-01 .. 2019-06): +66 months
    bwd174  source cells i >= 174 (true dates 2019-07 .. 2024-12): -174 months
Both offsets share the seasonal phase (+66 = -174 = +6 mod 12), so the split
probes displacement magnitude/direction robustness, NOT seasonal phase
(the Wp72 arm, FM-1c C3 month-preserving 72-month shift, covers phase).

Premise verification (also asserted at runtime, "verify before proceeding"):
  - stored 03_run_meta.json fake_date values match the +66 map with ZERO
    mismatches for every model that records the field (12 models incl.
    deepseek 480/480, gemini-flash 720/720, kimi 480/480); anthropic-batch/
    direct and openai-batch writers omit the field (absent != mismatch), but
    those runners import all_bench_nodes/arm_prompt from run_bench_model
    (run_bench_anthropic_batch.py:32, run_bench_openai_batch.py:33), i.e. the
    same map by construction; user_sha256, where stored, matches the
    recomputed W prompt hash under the +66 map.
  - post-cutoff W cells (18 dates) use the CRISIS/CALM_ANCHORS alternation
    (run_fm1c.py:34-42 + build_postcutoff_nodes: even sorted-index -> crisis
    anchor, odd -> calm anchor, 9/9); stored meta agrees where recorded.

Endpoints per full-tier model:
  1. E3 restricted to each family, frozen windows: both labelings restricted
     to dates sourced from the family's cells. Window geometry is asymmetric
     BY CONSTRUCTION (asserted): fwd66 true-crisis = 6 GFC dates / fake-crisis
     = 5 COVID+inflation dates (calm 36/36); bwd174 mirrored crisis sets but
     calm = 0 under BOTH labelings (calm years 2013/14/17 all lie inside
     fwd66's true side and outside bwd174's fake image 2005-01..2010-06), so
     the strict E3_bwd174 gap difference is NOT computable — rendered '-',
     never imputed, with per-window n reported.
  2. POST-HOC SUPPLEMENT (rest-baseline): same family contrast with the calm
     window replaced by "all family dates outside the crisis window under the
     same labeling". Computable for both families; baseline differs from the
     frozen calm definition — clearly marked, reported next to the full-data
     rest-baseline reference value.
  3. Post-cutoff anchor-transplant readout: crisis-anchor vs calm-anchor
     pooled bearish-share difference on the 18 post-cutoff W cells (9/9
     dates, shift-free, descriptive; all 18 design dates used — this is NOT
     the frozen P1 which starts at 2025-02).

RECONCILIATION GATE (asserted in-script): unrestricted union of the two
families must reproduce each model's frozen E3 (est, gap_fake, gap_true AND
ci95) from <model>_row.json bit-exactly, under the frozen rng discipline
(fresh default_rng(2026) per model, E2 bootstrap draws consumed before the E3
draws on one stream, exactly as analyze_bench_row.main).

New family/anchor CIs (no frozen counterpart) use a second fresh
default_rng(2026) per model, draws in fixed documented order:
rest_full -> fwd66_strict -> fwd66_rest -> bwd174_rest -> anchor.
Windows are resampled at the date level, independently per window, EXCEPT the
calm draws which are shared when the two labelings' calm windows are the
identical date set (fwd66 strict: both are the same 36 calm dates —
mirrors the frozen boot_diff's shared-calm behavior).

Excluded rows are listed explicitly in the output with reasons
(llama3.2 65-date reduced tier, smoke dirs, BM2a serving variants).

Writes outputs/review/w_offset_split.{json,md}.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map, gap, CRISIS, CALM_YEARS  # noqa: E402
from analyze_fm1 import FAKE_SHIFT as FM1_SHIFT                        # noqa: E402
from analyze_bench_row import load_arm, boot_diff                      # noqa: E402
from run_fm1_arms import clean_context, FAKE_SHIFT as ARMS_SHIFT       # noqa: E402
from run_fm1c import build_postcutoff_nodes, CALM_ANCHORS              # noqa: E402
from run_fm1c import CRISIS as FM1C_CRISIS                             # noqa: E402
from run_kt1_masked_arm import load_nodes                              # noqa: E402
from hindsight_paths import REPO                                       # noqa: E402

BENCH = REPO / "hindsight/outputs/bench"
OUT_DIR = REPO / "hindsight/outputs/review"
B, SEED = 10_000, 2026
SPLIT_I = 240 - 66  # = 174: first wrap index of (i + 66) % 240

INCLUDED = [  # frozen leaderboard order (bench_registry) minus reduced tier
    "gpt-5.5", "claude-sonnet-5", "kimi-k2.6", "qwen3.6-35b-a3b-fp8",
    "qwen3.6-27b-fp8", "gpt-5.4-mini", "claude-haiku-4-5",
    "deepseek-v4-flash", "gemini-2.5-flash", "gemini-2.5-pro",
    "qwen3-30b-a3b-fp8dyn", "llama-3.1-70b-awq", "llama-3.1-8b",
]

EXCLUDED = {
    "llama3.2:1b": "reduced 65-date tier (windows-only sampling): the fwd66/"
                   "bwd174 re-partition leaves near-empty windows and the "
                   "frozen row is already e3_sparse-flagged in bench_registry",
    "llama3.2:3b": "reduced 65-date tier: same as llama3.2:1b",
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


# ---------------------------------------------------------------- premise --

def verify_universe() -> dict:
    """Assert the 240-date universe and the two displacement families."""
    assert FM1_SHIFT == ARMS_SHIFT == 66, (FM1_SHIFT, ARMS_SHIFT)
    ds = all_dates()
    assert len(ds) == 240 and ds[0] == "2005-01-15" and ds[-1] == "2024-12-15"
    mo = lambda d: int(d[:4]) * 12 + int(d[5:7])  # noqa: E731
    assert all(mo(b) - mo(a) == 1 for a, b in zip(ds, ds[1:])), "not consecutive"
    assert all(d[8:] == "15" for d in ds)
    fm = fake_map(ds)
    offs_fwd = {mo(fm[ds[i]]) - mo(ds[i]) for i in range(SPLIT_I)}
    offs_bwd = {mo(fm[ds[i]]) - mo(ds[i]) for i in range(SPLIT_I, 240)}
    assert offs_fwd == {66} and offs_bwd == {-174}, (offs_fwd, offs_bwd)
    assert {o % 12 for o in offs_fwd | offs_bwd} == {6}, "phase not +6 mod 12"
    return {
        "formula": "fake_for[dates[i]] = dates[(i+66) % 240] "
                   "(run_bench_model.py:36,60; run_fm1_arms.py:53,173)",
        "universe": "240 consecutive monthly day-15 dates 2005-01..2024-12",
        "families": {
            "fwd66":  {"source_idx": "i < 174", "true_range": "2005-01..2019-06",
                       "offset_months": 66, "n_cells_dates": SPLIT_I},
            "bwd174": {"source_idx": "i >= 174", "true_range": "2019-07..2024-12",
                       "offset_months": -174, "n_cells_dates": 240 - SPLIT_I},
        },
        "seasonal_phase_mod12": 6,
    }


def verify_meta(fm: dict[str, str], post_fake: dict[str, str]) -> dict:
    """Scan every included model's stored W meta: fake_date (pre + post) and
    user_sha256 (pre) against the +66 map. absent != mismatch (the anthropic
    and openai-batch writers do not record these fields; their prompt builder
    is run_bench_model.arm_prompt by import, same map by construction)."""
    nodes = {n["decision_date"]: n for n in load_nodes()}
    exp_sha = {d: hashlib.sha256(
        clean_context(nodes[d]["orig_user"], d, "fake", fm[d]).encode()
    ).hexdigest() for d in fm}
    out = {}
    for model in INCLUDED:
        c = defaultdict(int)
        for mf in (BENCH / model / "W").glob("rep*/*/03_run_meta.json"):
            m = json.loads(mf.read_text())
            dd = m.get("decision_date", mf.parent.name)
            fd, us = m.get("fake_date"), m.get("user_sha256")
            if dd in fm:                       # pre-cutoff cell
                c["pre_cells"] += 1
                c["fd_match" if fd == fm[dd] else
                  "fd_absent" if fd is None else "fd_MISMATCH"] += 1
                c["sha_match" if us == exp_sha[dd] else
                  "sha_absent" if us is None else "sha_MISMATCH"] += 1
            elif dd in post_fake:              # post-cutoff cell
                c["post_cells"] += 1
                c["post_fd_match" if fd == post_fake[dd] else
                  "post_fd_absent" if fd is None else "post_fd_MISMATCH"] += 1
            else:
                c["unknown_date_cells"] += 1
        assert c["fd_MISMATCH"] == c["sha_MISMATCH"] == c["post_fd_MISMATCH"] == 0, \
            (model, dict(c))
        assert c["unknown_date_cells"] == 0, (model, dict(c))
        out[model] = dict(c)
    return out


# ------------------------------------------------------------- estimators --

def boot_windows(bd_f, bd_t, fc, fq, tc, tq, rng):
    """CI for gap(bd_f; fc,fq) - gap(bd_t; tc,tq) with per-window date
    resampling; calm draws shared iff the two calm windows are the identical
    date set. Returns (lo, hi, valid_frac) with the frozen 50% validity guard."""
    share_calm = sorted(fq) == sorted(tq)
    fc_a, fq_a = np.array(fc), np.array(fq)
    tc_a, tq_a = np.array(tc), np.array(tq)
    out = np.empty(B)
    for b in range(B):
        fcs = list(rng.choice(fc_a, len(fc_a), replace=True))
        fqs = list(rng.choice(fq_a, len(fq_a), replace=True))
        tcs = list(rng.choice(tc_a, len(tc_a), replace=True))
        tqs = fqs if share_calm else list(rng.choice(tq_a, len(tq_a), replace=True))
        out[b] = gap(bd_f, fcs, fqs) - gap(bd_t, tcs, tqs)
    valid = out[~np.isnan(out)]
    if len(valid) < B * 0.5:
        return (float("nan"), float("nan")), len(valid) / B, share_calm
    return (float(np.percentile(valid, 2.5)),
            float(np.percentile(valid, 97.5))), len(valid) / B, share_calm


def ci_excludes_zero(ci):
    lo, hi = ci
    if np.isnan(lo) or np.isnan(hi):
        return None
    return bool(lo > 0 or hi < 0)


def split_cell(bd_true, bd_fake, fc, fq, tc, tq, rng, label):
    """One family (or full-data) E3-style contrast. Empty window -> None,
    never imputed. Bootstrap only when all four windows have n >= 3 dates."""
    gf = gap(bd_fake, fc, fq) if fc and fq else None
    gt = gap(bd_true, tc, tq) if tc and tq else None
    est = gf - gt if gf is not None and gt is not None else None
    cell = {"label": label, "est": est, "gap_fake": gf, "gap_true": gt,
            "n_crisis_fake": len(fc), "n_calm_fake": len(fq),
            "n_crisis_true": len(tc), "n_calm_true": len(tq),
            "dates_with_data_true": sum(1 for d in set(tc) | set(tq) if bd_true.get(d)),
            "dates_with_data_fake": sum(1 for d in set(fc) | set(fq) if bd_fake.get(d))}
    if est is None:
        cell["ci_kind"] = "not_computable(empty window)"
    elif min(len(fc), len(fq), len(tc), len(tq)) >= 3:
        ci, vf, shared = boot_windows(bd_fake, bd_true, fc, fq, tc, tq, rng)
        cell.update(ci95=list(ci), boot_valid_frac=vf,
                    ci_excludes_zero=ci_excludes_zero(ci),
                    ci_kind="bootstrap(B=10k, per-window date resampling"
                            + (", shared calm draws)" if shared else ")"))
    else:
        cell["ci_kind"] = "point_estimate_only(window n<3)"
    return cell


def anchor_cell(post_by, anchor_cri, anchor_calm, rng):
    """Post-cutoff shift-free readout: pooled bearish share, crisis-anchor
    minus calm-anchor dates. Descriptive (n=9/9 dates, wide)."""
    def pooled(dd):
        return [x for d in dd for x in post_by.get(d, [])]

    def share(xs):
        return sum(1 for x in xs if x == "-") / len(xs) if xs else None

    xs_c, xs_q = pooled(anchor_cri), pooled(anchor_calm)
    s_c, s_q = share(xs_c), share(xs_q)
    cell = {"share_crisis_anchor": s_c, "share_calm_anchor": s_q,
            "diff": s_c - s_q if s_c is not None and s_q is not None else None,
            "n_dates_design": [len(anchor_cri), len(anchor_calm)],
            "n_dates_with_data": [sum(1 for d in anchor_cri if post_by.get(d)),
                                  sum(1 for d in anchor_calm if post_by.get(d))],
            "n_sketches": [len(xs_c), len(xs_q)]}
    if cell["diff"] is not None:
        cri_a, calm_a = np.array(anchor_cri), np.array(anchor_calm)
        out = np.empty(B)
        for b in range(B):
            cs = pooled(rng.choice(cri_a, len(cri_a), replace=True))
            qs = pooled(rng.choice(calm_a, len(calm_a), replace=True))
            out[b] = (share(cs) - share(qs)) if cs and qs else np.nan
        valid = out[~np.isnan(out)]
        if len(valid) >= B * 0.5:
            cell["ci95"] = [float(np.percentile(valid, 2.5)),
                            float(np.percentile(valid, 97.5))]
            cell["ci_excludes_zero"] = ci_excludes_zero(cell["ci95"])
        cell["boot_valid_frac"] = len(valid) / B
        cell["ci_kind"] = "bootstrap(B=10k, date resampling; descriptive)"
    return cell


def same_sign(est, ref):
    if est is None or ref is None or (isinstance(est, float) and np.isnan(est)):
        return None
    if est == 0.0 or ref == 0.0:
        return None
    return bool(np.sign(est) == np.sign(ref))


# ------------------------------------------------------------------- main --

def main() -> None:
    universe = verify_universe()
    pre = all_dates()
    preset = set(pre)
    idx = {d: i for i, d in enumerate(pre)}
    fmap = fake_map(pre)
    calm = [d for d in pre if d[:4] in CALM_YEARS]

    post_nodes = build_postcutoff_nodes()
    assert len(post_nodes) == 18
    assert FM1C_CRISIS == CRISIS
    post_fake = {n["decision_date"]: n["fake_date"] for n in post_nodes}
    post_sorted = sorted(post_fake)
    anchor_cri = [d for d in post_sorted if post_fake[d] in set(CRISIS)]
    anchor_calm = [d for d in post_sorted if post_fake[d] in set(CALM_ANCHORS)]
    assert len(anchor_cri) == len(anchor_calm) == 9
    assert set(anchor_cri) | set(anchor_calm) == set(post_sorted)
    # alternation: even sorted index -> crisis anchor, odd -> calm anchor
    assert all((post_sorted.index(d) % 2 == 0) == (d in set(anchor_cri))
               for d in post_sorted)

    meta_check = verify_meta(fmap, post_fake)

    # family geometry (design-level, model-independent) — asserted
    fams = {"fwd66": pre[:SPLIT_I], "bwd174": pre[SPLIT_I:]}
    geo = {}
    for name, fam in fams.items():
        fam_s, img_s = set(fam), {fmap[d] for d in fam}
        geo[name] = {
            "tc": [d for d in CRISIS if d in fam_s],
            "tq": [d for d in calm if d in fam_s],
            "fc": [d for d in CRISIS if d in img_s],
            "fq": [d for d in calm if d in img_s],
        }
    assert [len(geo["fwd66"][k]) for k in ("tc", "tq", "fc", "fq")] == [6, 36, 5, 36]
    assert [len(geo["bwd174"][k]) for k in ("tc", "tq", "fc", "fq")] == [5, 0, 6, 0]
    # true-label crisis split: 6 GFC dates -> fwd66, 5 COVID/inflation -> bwd174
    assert all(d.startswith(("2008", "2009")) for d in geo["fwd66"]["tc"])
    assert all(d.startswith(("2020", "2022")) for d in geo["bwd174"]["tc"])

    rest = {  # POST-HOC SUPPLEMENT windows: family complement of the crisis set
        name: {"rest_t": [d for d in fams[name] if d not in set(CRISIS)],
               "rest_f": [fmap[d] for d in fams[name] if fmap[d] not in set(CRISIS)]}
        for name in fams
    }
    rest_full_baseline = [d for d in pre if d not in set(CRISIS)]  # n=229

    reconciliation, results = {}, {}
    for model in INCLUDED:
        t0 = time.time()
        root = BENCH / model
        frozen = json.loads((root / f"{model}_row.json").read_text())["E3_transplant"]

        D, _ = load_arm(root, "D")
        M, _ = load_arm(root, "M")
        W, _ = load_arm(root, "W")
        D_pre = {d: v for d, v in D.items() if d in preset}
        M_pre = {d: v for d, v in M.items() if d in preset}
        W_pre = {d: v for d, v in W.items() if d in preset}
        W_post = {d: v for d, v in W.items() if d in post_fake}
        w_fake = defaultdict(list)
        for td, xs in W_pre.items():
            w_fake[fmap[td]].extend(xs)

        # ---- RECONCILIATION GATE: union of families == frozen E3, bit-exact
        fam_union = set(fams["fwd66"]) | set(fams["bwd174"])
        miss = [d for d in W_pre if d not in fam_union]
        assert not miss and fam_union == preset, (model, miss)
        g_wf, g_wt = gap(w_fake, CRISIS, calm), gap(W_pre, CRISIS, calm)
        e3 = g_wf - g_wt
        rng_frozen = np.random.default_rng(SEED)   # frozen per-model discipline:
        boot_diff(lambda c, q: gap(D_pre, c, q),   # E2 draws consumed first,
                  lambda c, q: gap(M_pre, c, q), CRISIS, calm, rng_frozen)
        e3_ci = boot_diff(lambda c, q: gap(w_fake, c, q),
                          lambda c, q: gap(W_pre, c, q), CRISIS, calm, rng_frozen)
        bit_exact = bool(e3 == frozen["est"] and g_wf == frozen["gap_fake"]
                         and g_wt == frozen["gap_true"]
                         and list(e3_ci) == list(frozen["ci95"]))
        reconciliation[model] = {
            "frozen": {"est": frozen["est"], "gap_fake": frozen["gap_fake"],
                       "gap_true": frozen["gap_true"], "ci95": frozen["ci95"]},
            "recomputed": {"est": e3, "gap_fake": g_wf, "gap_true": g_wt,
                           "ci95": list(e3_ci)},
            "bit_exact": bit_exact,
            "max_abs_diff": max(abs(e3 - frozen["est"]),
                                abs(g_wf - frozen["gap_fake"]),
                                abs(g_wt - frozen["gap_true"]),
                                *(abs(a - b) for a, b in zip(e3_ci, frozen["ci95"]))),
        }
        assert bit_exact, (model, reconciliation[model])

        # ---- family cells (new CIs: second fresh rng, fixed draw order)
        rng = np.random.default_rng(SEED)
        res = {"E3_full_frozen": frozen["est"],
               "E3_full_recomputed": e3,
               "E3rest_full": None, "strict": {}, "rest": {}}

        res["E3rest_full"] = split_cell(
            W_pre, w_fake, list(CRISIS), rest_full_baseline,
            list(CRISIS), rest_full_baseline, rng,
            "full-data rest-baseline reference (crisis vs 229 non-crisis dates, "
            "both labelings; POST-HOC baseline, not the frozen calm set)")

        for name in ("fwd66", "bwd174"):
            fam_s = set(fams[name])
            W_fam = {d: v for d, v in W_pre.items() if d in fam_s}
            wf_fam = defaultdict(list)
            for td, xs in W_fam.items():
                wf_fam[fmap[td]].extend(xs)
            g = geo[name]
            if name == "fwd66":   # strict cell (bwd174 strict has empty calms:
                res["strict"][name] = split_cell(   # cell emitted below w/o CI)
                    W_fam, wf_fam, g["fc"], g["fq"], g["tc"], g["tq"], rng,
                    f"{name} strict frozen windows")
            else:
                res["strict"][name] = split_cell(
                    W_fam, wf_fam, g["fc"], g["fq"], g["tc"], g["tq"], rng,
                    f"{name} strict frozen windows (calm empty both labelings "
                    "-> not computable)")
        for name in ("fwd66", "bwd174"):
            fam_s = set(fams[name])
            W_fam = {d: v for d, v in W_pre.items() if d in fam_s}
            wf_fam = defaultdict(list)
            for td, xs in W_fam.items():
                wf_fam[fmap[td]].extend(xs)
            g = geo[name]
            res["rest"][name] = split_cell(
                W_fam, wf_fam, g["fc"], rest[name]["rest_f"],
                g["tc"], rest[name]["rest_t"], rng,
                f"{name} POST-HOC rest-baseline supplement")

        # ---- post-cutoff anchor readout
        if W_post:
            res["anchor"] = anchor_cell(W_post, anchor_cri, anchor_calm, rng)
        else:
            res["anchor"] = {"diff": None,
                             "reason": "post-cutoff W arms absent for this row "
                                       "(bench_registry p1='absent')"}

        # ---- sign agreement vs frozen full E3
        ref = frozen["est"]
        res["signs"] = {
            "fwd66_strict":  same_sign(res["strict"]["fwd66"]["est"], ref),
            "bwd174_strict": same_sign(res["strict"]["bwd174"]["est"], ref),
            "fwd66_rest":    same_sign(res["rest"]["fwd66"]["est"], ref),
            "bwd174_rest":   same_sign(res["rest"]["bwd174"]["est"], ref),
            "rest_full":     same_sign(res["E3rest_full"]["est"], ref),
            "anchor":        same_sign(res["anchor"].get("diff"), ref),
        }
        results[model] = res
        print(f"[{model}] done in {time.time()-t0:.1f}s bit_exact={bit_exact} "
              f"E3={e3:+.3f} fwd66={res['strict']['fwd66']['est']:+.3f}", flush=True)

    # ---- summary
    def count(key):
        vals = [results[m]["signs"][key] for m in INCLUDED]
        return {"same_sign": sum(1 for v in vals if v is True),
                "opposite": sum(1 for v in vals if v is False),
                "undefined": sum(1 for v in vals if v is None)}

    sign_summary = {k: count(k) for k in
                    ("fwd66_strict", "bwd174_strict", "fwd66_rest",
                     "bwd174_rest", "rest_full", "anchor")}
    sign_summary["n_models"] = len(INCLUDED)
    sign_summary["fwd66_strict_ci_excludes_zero"] = sum(
        1 for m in INCLUDED
        if results[m]["strict"]["fwd66"].get("ci_excludes_zero"))
    sign_summary["anchor_ci_excludes_zero"] = sum(
        1 for m in INCLUDED if results[m]["anchor"].get("ci_excludes_zero"))

    caveats = [
        "Same seasonal phase for both families (+66 = -174 = +6 mod 12): this "
        "split tests displacement magnitude/direction robustness, NOT "
        "seasonal-phase variation — the Wp72 month-preserving 72-month arm "
        "(FM-1c C3) covers phase.",
        "Asymmetric event composition across families: fwd66 contrasts "
        "fake-COVID/inflation (5 dates) against true-GFC (6 dates); bwd174 is "
        "mirrored. Family differences therefore confound offset with event "
        "era — a fwd66-vs-bwd174 gap is NOT evidence of offset sensitivity "
        "per se.",
        "E3_bwd174 under the strict frozen windows is not computable: the "
        "calm years {2013,2014,2017} lie entirely in fwd66's true side, and "
        "bwd174's fake image (2005-01..2010-06) contains no calm date — calm "
        "n=0 under BOTH labelings; rendered '-', never imputed.",
        "The rest-baseline supplement (crisis vs family complement) is a "
        "POST-HOC analytic choice forced by the empty calm windows; its "
        "baseline includes non-calm, non-crisis dates and is NOT the frozen "
        "calm definition. The full-data rest-baseline reference column shows "
        "how the baseline swap moves the full-sample number.",
        "Anchor readout uses all 18 post-cutoff design dates (9/9); the "
        "frozen P1 placebo starts at 2025-02 and 2026-generation models' "
        "vendor cutoffs overlap early post dates — descriptive only.",
        "Single-rep rows (gpt-5.5, claude-sonnet-5, gemini-2.5-pro, "
        "qwen3-30b-a3b-fp8dyn) carry per-date n of ~8 sketches; family "
        "windows of 5-6 dates make these CIs very wide by construction.",
    ]

    out = {
        "status": "POST-FREEZE EXPLORATORY (review-response, 2026-07-21); "
                  "zero API calls; reviewer Q5 (alternative transplant "
                  "offsets) — re-analysis of frozen W arms, no new generation",
        "premise_verification": {"universe_and_map": universe,
                                 "per_model_meta_check": meta_check,
                                 "postcutoff_anchors": {
                                     "rule": "even sorted-index -> CRISIS "
                                             "anchor, odd -> CALM anchor "
                                             "(run_fm1c.py build_postcutoff_"
                                             "nodes; asserted)",
                                     "crisis_anchor_dates": anchor_cri,
                                     "calm_anchor_dates": anchor_calm}},
        "window_geometry": {name: {k: geo[name][k] for k in ("tc", "tq", "fc", "fq")}
                            for name in geo},
        "rest_baseline_n": {name: {"rest_true": len(rest[name]["rest_t"]),
                                   "rest_fake": len(rest[name]["rest_f"])}
                            for name in rest},
        "included_models": INCLUDED,
        "excluded_models": EXCLUDED,
        "design_caveats": caveats,
        "reconciliation": reconciliation,
        "results": results,
        "sign_summary": sign_summary,
        "bootstrap": {"B": B, "seed": SEED,
                      "frozen_gate_rng": "fresh default_rng(2026)/model, E2 "
                                         "draws then E3 draws (frozen "
                                         "discipline of analyze_bench_row)",
                      "new_ci_rng": "second fresh default_rng(2026)/model; "
                                    "order: rest_full, fwd66_strict, "
                                    "fwd66_rest, bwd174_rest, anchor; "
                                    "per-window date resampling, calm draws "
                                    "shared iff identical window sets"},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "w_offset_split.json").write_text(json.dumps(out, indent=2, default=float))

    # ------------------------------------------------------------ markdown --
    def pp(x):
        return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:+.1f}"

    def ci_s(cell):
        c = cell.get("ci95")
        if c is None or np.isnan(c[0]):
            return "-"
        return f"[{c[0]*100:+.1f},{c[1]*100:+.1f}]"

    def yn(v):
        return "-" if v is None else ("yes" if v else "NO")

    L = ["# W-arm displacement-family split + post-cutoff anchor transplant (reviewer Q5)", "",
         "POST-FREEZE EXPLORATORY (review-response, 2026-07-21); zero API calls.",
         "All numbers recomputed from the frozen W arms; the fake-date map is an",
         "analysis-time constant of the frozen design (`(i+66) % 240`), verified",
         "against stored run meta (zero mismatches; counts in the json).", "",
         "The single frozen map contains two displacement families: **fwd66**",
         "(source cells i<174, +66 months) and **bwd174** (source cells i>=174,",
         "wrap to -174 months). Both share seasonal phase (+6 mod 12). Units: pp.", "",
         "## Reconciliation gate (union of families vs frozen row json)", "",
         "| model | frozen E3 [CI] | recomputed E3 [CI] | bit-exact |",
         "|---|---|---|---|"]
    for m in INCLUDED:
        r = reconciliation[m]
        L.append(f"| {m} | {pp(r['frozen']['est'])} "
                 f"[{r['frozen']['ci95'][0]*100:+.1f},{r['frozen']['ci95'][1]*100:+.1f}] | "
                 f"{pp(r['recomputed']['est'])} "
                 f"[{r['recomputed']['ci95'][0]*100:+.1f},{r['recomputed']['ci95'][1]*100:+.1f}] | "
                 f"{'yes' if r['bit_exact'] else 'NO'} |")
    L += ["",
          "## Strict frozen windows per family", "",
          "fwd66 windows: fake crisis n=5 (COVID+inflation) / fake calm n=36 /",
          "true crisis n=6 (GFC) / true calm n=36. bwd174 windows: fake crisis",
          "n=6 (GFC) / true crisis n=5 (COVID+inflation), but **calm n=0 under",
          "both labelings** (calm years 2013/14/17 are all in fwd66's true side",
          "and outside bwd174's fake image 2005-01..2010-06) — E3_bwd174 is not",
          "computable under the frozen windows and is rendered '-', not imputed.", "",
          "| model | E3_full | E3_fwd66 [CI] | excl.0 | sign=full? | E3_bwd174 | gapf_bwd | gapt_bwd |",
          "|---|---|---|---|---|---|---|---|"]
    for m in INCLUDED:
        r = results[m]
        s, b = r["strict"]["fwd66"], r["strict"]["bwd174"]
        L.append(f"| {m} | {pp(r['E3_full_frozen'])} | {pp(s['est'])} {ci_s(s)} | "
                 f"{yn(s.get('ci_excludes_zero'))} | {yn(r['signs']['fwd66_strict'])} | "
                 f"{pp(b['est'])} | {pp(b['gap_fake'])} | {pp(b['gap_true'])} |")
    L += ["",
          "## POST-HOC rest-baseline supplement (both families computable)", "",
          "Baseline = family complement of the crisis window under the same",
          "labeling (fwd66: 169/168 dates; bwd174: 60/61) — NOT the frozen calm",
          "set. `rest_full` = same construction on all 240 dates (reference for",
          "the baseline swap).", "",
          "| model | E3rest_full [CI] | E3rest_fwd66 [CI] | sign=full? | E3rest_bwd174 [CI] | sign=full? |",
          "|---|---|---|---|---|---|"]
    for m in INCLUDED:
        r = results[m]
        rf, f6, b1 = r["E3rest_full"], r["rest"]["fwd66"], r["rest"]["bwd174"]
        L.append(f"| {m} | {pp(rf['est'])} {ci_s(rf)} | {pp(f6['est'])} {ci_s(f6)} | "
                 f"{yn(r['signs']['fwd66_rest'])} | {pp(b1['est'])} {ci_s(b1)} | "
                 f"{yn(r['signs']['bwd174_rest'])} |")
    L += ["",
          "## Post-cutoff anchor transplant (shift-free, descriptive)", "",
          "18 post-cutoff W cells; fake dates alternate crisis anchors (9 dates)",
          "vs calm anchors (9 dates) by design. Diff = pooled bearish share",
          "(crisis-anchor) - (calm-anchor). Not the frozen P1 (which starts",
          "2025-02).", "",
          "| model | share crisis-anchor | share calm-anchor | diff [CI] | n sketches (c/q) | sign=full E3? |",
          "|---|---|---|---|---|---|"]
    for m in INCLUDED:
        a = results[m]["anchor"]
        if a.get("diff") is None and "reason" in a:
            L.append(f"| {m} | - | - | - ({a['reason']}) | - | - |")
        else:
            L.append(f"| {m} | {pp(a['share_crisis_anchor'])} | {pp(a['share_calm_anchor'])} | "
                     f"{pp(a['diff'])} {ci_s(a)} | {a['n_sketches'][0]}/{a['n_sketches'][1]} | "
                     f"{yn(results[m]['signs']['anchor'])} |")
    ss = sign_summary
    L += ["",
          "## Sign agreement summary "
          f"(n = {ss['n_models']} full-tier models)", ""]
    for k, lbl in (("fwd66_strict", "fwd66 strict"), ("bwd174_strict", "bwd174 strict"),
                   ("fwd66_rest", "fwd66 rest-baseline"), ("bwd174_rest", "bwd174 rest-baseline"),
                   ("rest_full", "full-data rest-baseline"), ("anchor", "post-cutoff anchor")):
        c = ss[k]
        L.append(f"- {lbl}: same sign as frozen full E3 {c['same_sign']}/{ss['n_models']}"
                 f" (opposite {c['opposite']}, undefined {c['undefined']})")
    L += [f"- fwd66 strict CI excludes zero: {ss['fwd66_strict_ci_excludes_zero']}/{ss['n_models']}",
          f"- anchor CI excludes zero: {ss['anchor_ci_excludes_zero']}/{ss['n_models']}",
          "", "## Design caveats", ""]
    L += [f"{i}. {c}" for i, c in enumerate(caveats, 1)]
    L += ["", "## Excluded rows", ""]
    L += [f"- `{k}`: {v}" for k, v in EXCLUDED.items()]
    L += ["", "Regenerate: `python hindsight/scripts/analyze_w_offset_split.py` "
          "(no arguments; deterministic, seed 2026).", ""]
    (OUT_DIR / "w_offset_split.md").write_text("\n".join(L))
    print(f"wrote {OUT_DIR}/w_offset_split.json + .md")
    print("sign_summary:", json.dumps(sign_summary))


if __name__ == "__main__":
    main()
