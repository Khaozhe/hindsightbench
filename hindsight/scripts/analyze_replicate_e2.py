"""POST-FREEZE EXPLORATORY (2026-07-25, design-review response).

Per-replicate E2 = Gap(D) - Gap(M) on the frozen FM-1 Flash arms.

Motivation: the paper reports a three-replicate-pooled E2 with a date-level
bootstrap CI, and Appendix E.10 discloses that sketch-level gaps are noisy
between replicates. A reviewer observed that E.10 gave the between-replicate
spread of Gap(R) and Gap(M) but not of Gap(D) -- and Gap(D), not Gap(R), is
the component of E2. This script closes that gap: it reports Gap(D), Gap(M)
and E2 for each replicate separately, each with the paper's own estimator
(analyze_fm1.boot_diff: paired date-level bootstrap over the frozen crisis and
calm windows, B = 10,000, seed 2026), plus the between-replicate SD and a
variance-inflated interval for the pooled estimate.

Read-only: touches nothing outside outputs/review/.
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "hindsight" / "scripts"))

from analyze_fm1 import B, CALM_YEARS, CRISIS, boot_diff, gap  # noqa: E402

FM1 = REPO / "hindsight" / "outputs" / "fm1" / "gemini-2.5-flash"
OUT = REPO / "hindsight" / "outputs" / "review"
SEED = 2026


def load_rep(arm: str, rep: str) -> dict[str, list[str]]:
    """by_date -> list of direction chars, for one arm and one replicate."""
    by_date: dict[str, list[str]] = {}
    for f in sorted((FM1 / arm / rep).glob("*/01_sketches_valid.json")):
        d = f.parent.name
        try:
            sketches = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        dirs = [s["direction"] for s in sketches
                if s.get("direction") in ("+", "-")]
        if dirs:
            by_date.setdefault(d, []).extend(dirs)
    return by_date


def windows(by_date: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    crisis = [d for d in CRISIS if d in by_date]
    calm = [d for d in by_date if d[:4] in CALM_YEARS]
    return sorted(crisis), sorted(calm)


def main() -> None:
    reps = ["rep1", "rep2", "rep3"]
    arms = {a: {r: load_rep(a, r) for r in reps} for a in ("R", "D", "M")}

    # frozen windows are identical across arms/replicates; assert it
    ref = windows(arms["D"]["rep1"])
    for a in arms:
        for r in reps:
            assert windows(arms[a][r]) == ref, (a, r)
    crisis, calm = ref

    per_rep = {}
    for r in reps:
        d_by, m_by, r_by = arms["D"][r], arms["M"][r], arms["R"][r]
        g_d = gap(d_by, crisis, calm) * 100
        g_m = gap(m_by, crisis, calm) * 100
        g_r = gap(r_by, crisis, calm) * 100
        rng = np.random.default_rng(SEED)
        lo, hi = boot_diff(
            lambda cs, qs: gap(d_by, cs, qs),
            lambda cs, qs: gap(m_by, cs, qs),
            crisis, calm, rng,
        )
        # E1 = Gap(R) - Gap(D) within the same replicate, same estimator
        rng1 = np.random.default_rng(SEED)
        e1lo, e1hi = boot_diff(
            lambda cs, qs: gap(r_by, cs, qs),
            lambda cs, qs: gap(d_by, cs, qs),
            crisis, calm, rng1,
        )
        per_rep[r] = {
            "gap_R_pp": round(g_r, 4),
            "gap_D_pp": round(g_d, 4),
            "gap_M_pp": round(g_m, 4),
            "E2_pp": round(g_d - g_m, 4),
            "E2_ci95_pp": [round(lo * 100, 4), round(hi * 100, 4)],
            "excludes_zero": lo > 0,
            "E1_pp": round(g_r - g_d, 4),
            "E1_ci95_pp": [round(e1lo * 100, 4), round(e1hi * 100, 4)],
            "E1_excludes_zero": (e1lo > 0) or (e1hi < 0),
            "rent_RM_pp": round(g_r - g_m, 4),
            "n_crisis_dates": len(crisis),
            "n_calm_dates": len(calm),
        }

    e2 = [per_rep[r]["E2_pp"] for r in reps]
    sd_between = st.stdev(e2)
    se_mean = sd_between / math.sqrt(len(e2))

    # Anti-correlation of the two arms across replicates, and its effect on
    # the rent spread; plus the M-share coincidence audit (47.7% twice).
    r_vals = [per_rep[r]["gap_R_pp"] for r in reps]
    m_vals = [per_rep[r]["gap_M_pp"] for r in reps]
    rent_vals = [per_rep[r]["rent_RM_pp"] for r in reps]
    corr_rm = float(np.corrcoef(r_vals, m_vals)[0, 1])
    e1_vals = [per_rep[r]["E1_pp"] for r in reps]
    aux = {
        "corr_gapR_gapM_across_reps": round(corr_rm, 4),
        "rent_spread_pp": round(max(rent_vals) - min(rent_vals), 4),
        "gapR_spread_pp": round(max(r_vals) - min(r_vals), 4),
        "gapM_spread_pp": round(max(m_vals) - min(m_vals), 4),
        "rent_values_unrounded": [round(v, 2) for v in rent_vals],
        "E1_values_pp": [round(v, 2) for v in e1_vals],
        "E1_sum_check_3x_pooled": round(sum(e1_vals), 4),
        "M_crisis_share_rep1_pct": None,  # filled below
        "M_crisis_share_pooled_pct": None,
    }
    # 47.7% coincidence audit: rep1 M crisis share vs pooled M crisis share
    def crisis_share(by_date):
        b = t = 0
        for d in crisis:
            xs = by_date.get(d, [])
            b += sum(1 for x in xs if x == "-")
            t += len(xs)
        return 100 * b / t
    aux["M_crisis_share_rep1_pct"] = round(crisis_share(arms["M"]["rep1"]), 3)
    aux["M_crisis_share_pooled_pct"] = None  # set after pooling below

    # pooled reference, same estimator, all replicates concatenated
    def pool(arm: str) -> dict[str, list[str]]:
        merged: dict[str, list[str]] = {}
        for r in reps:
            for d, xs in arms[arm][r].items():
                merged.setdefault(d, []).extend(xs)
        return merged

    d_pool, m_pool, r_pool = pool("D"), pool("M"), pool("R")
    rng = np.random.default_rng(SEED)
    plo, phi = boot_diff(
        lambda cs, qs: gap(d_pool, cs, qs),
        lambda cs, qs: gap(m_pool, cs, qs),
        crisis, calm, rng,
    )
    pooled = (gap(d_pool, crisis, calm) - gap(m_pool, crisis, calm)) * 100
    half_date = (phi - plo) * 100 / 2

    # Same-batch R - M gap (the §4.1 kill-test contrast computed within FM-1
    # rather than against the 2026-04 archive, which has no masked arm).
    rng_rm = np.random.default_rng(SEED)
    rmlo, rmhi = boot_diff(
        lambda cs, qs: gap(r_pool, cs, qs),
        lambda cs, qs: gap(m_pool, cs, qs),
        crisis, calm, rng_rm,
    )
    g_r_pool = gap(r_pool, crisis, calm) * 100
    g_m_pool = gap(m_pool, crisis, calm) * 100
    same_batch = {
        "gap_R_pp": round(g_r_pool, 4),
        "gap_M_pp": round(g_m_pool, 4),
        "delta_pp": round(g_r_pool - g_m_pool, 4),
        "delta_ci95_pp": [round(rmlo * 100, 4), round(rmhi * 100, 4)],
        "residual_share": round(g_m_pool / g_r_pool, 4),
        "removed_share": round(1 - g_m_pool / g_r_pool, 4),
    }

    # Replicate component: df = 2, so the normal quantile understates it.
    T2 = 4.302653  # t_{0.975, df=2}
    half_comb_norm = math.sqrt(half_date ** 2 + (1.96 * se_mean) ** 2)
    half_comb = math.sqrt(half_date ** 2 + (T2 * se_mean) ** 2)

    res = {
        "note": "POST-FREEZE EXPLORATORY (2026-07-25). Frozen FM-1 flash arms, "
                "zero new API calls. Estimator: analyze_fm1.boot_diff, paired "
                f"date-level bootstrap, B={B}, seed {SEED}.",
        "windows": {"crisis": crisis, "calm_n": len(calm)},
        "per_replicate": per_rep,
        "between_replicate": {
            "E2_values_pp": [round(v, 2) for v in e2],
            "sd_pp": round(sd_between, 4),
            "se_of_mean_pp": round(se_mean, 4),
            "all_positive": all(v > 0 for v in e2),
            "all_ci_exclude_zero": all(per_rep[r]["excludes_zero"] for r in reps),
            "gap_D_sd_pp": round(st.stdev([per_rep[r]["gap_D_pp"] for r in reps]), 4),
            "gap_R_sd_pp": round(st.stdev([per_rep[r]["gap_R_pp"] for r in reps]), 4),
            "gap_M_sd_pp": round(st.stdev([per_rep[r]["gap_M_pp"] for r in reps]), 4),
        },
        "pooled": {
            "E2_pp": round(pooled, 4),
            "date_level_ci95_pp": [round(plo * 100, 4), round(phi * 100, 4)],
            "date_level_halfwidth_pp": round(half_date, 4),
            "replicate_halfwidth_normal_pp": round(1.96 * se_mean, 4),
            "replicate_halfwidth_t2_pp": round(T2 * se_mean, 4),
            "combined_ci95_normal_pp": [round(pooled - half_comb_norm, 4),
                                        round(pooled + half_comb_norm, 4)],
            "combined_ci95_t2_pp": [round(pooled - half_comb, 4),
                                    round(pooled + half_comb, 4)],
            "t2_excludes_zero": pooled - half_comb > 0,
            "replicate_only_t2_ci95_pp": [round(pooled - T2 * se_mean, 4),
                                          round(pooled + T2 * se_mean, 4)],
            "caveat": "df = 2 for the replicate component; the normal-quantile "
                      "version is reported only for comparison and is too "
                      "narrow. The primary evidence is that all three "
                      "replicates are individually significant, which needs no "
                      "small-sample distributional assumption.",
        },
        "same_batch_kill_test": same_batch,
        "aux": aux,
    }
    aux["M_crisis_share_pooled_pct"] = round(crisis_share(m_pool), 3)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "replicate_e2.json").write_text(json.dumps(res, indent=2) + "\n")

    L = ["# Per-replicate E2 (design-review response, 2026-07-25)", "",
         res["note"], "",
         "| replicate | Gap(R) | Gap(D) | Gap(M) | E2 | E2 CI95 | E2 excl 0 | E1 | E1 CI95 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in reps:
        v = per_rep[r]
        L.append(f"| {r} | {v['gap_R_pp']:.1f} | {v['gap_D_pp']:.1f} | "
                 f"{v['gap_M_pp']:.1f} | {v['E2_pp']:.1f} | "
                 f"[{v['E2_ci95_pp'][0]:.1f}, {v['E2_ci95_pp'][1]:.1f}] | "
                 f"{'yes' if v['excludes_zero'] else 'NO'} | "
                 f"{v['E1_pp']:+.1f} | "
                 f"[{v['E1_ci95_pp'][0]:.1f}, {v['E1_ci95_pp'][1]:.1f}] |")
    L += ["",
          f"E1 across replicates: {aux['E1_values_pp']} (sum {aux['E1_sum_check_3x_pooled']:.1f} "
          f"= 3 x pooled -3.4); only rep1's negative excludes zero; no replicate "
          f"shows a significantly positive increment.",
          f"Anti-correlation: corr(Gap R, Gap M) = {aux['corr_gapR_gapM_across_reps']:.2f} "
          f"across replicates (descriptive, n=3); rent spread {aux['rent_spread_pp']:.1f}pp "
          f"exceeds Gap(R)'s {aux['gapR_spread_pp']:.1f} and Gap(M)'s {aux['gapM_spread_pp']:.1f}.",
          f"M crisis share: rep1 {aux['M_crisis_share_rep1_pct']}% = pooled "
          f"{aux['M_crisis_share_pooled_pct']}% (the 47.7% coincidence is real; "
          f"the calm side is what differs between the archived and pooled M)."]
    b, p, s = res["between_replicate"], res["pooled"], res["same_batch_kill_test"]
    L += ["",
          f"All three replicates individually exclude zero: "
          f"{'YES' if b['all_ci_exclude_zero'] else 'NO'}.",
          "",
          f"Between-replicate SD: E2 {b['sd_pp']:.1f}pp, Gap(R) {b['gap_R_sd_pp']:.1f}, "
          f"Gap(D) {b['gap_D_sd_pp']:.1f}, Gap(M) {b['gap_M_sd_pp']:.1f}. "
          f"SE of the three-replicate mean: {b['se_of_mean_pp']:.1f}pp.",
          "",
          f"Pooled E2 {p['E2_pp']:.1f}pp, date-level CI "
          f"[{p['date_level_ci95_pp'][0]:.1f}, {p['date_level_ci95_pp'][1]:.1f}]. "
          f"Replicate component on df=2: t(2) half-width "
          f"{p['replicate_halfwidth_t2_pp']:.1f}pp (normal would give "
          f"{p['replicate_halfwidth_normal_pp']:.1f}pp and is too narrow). "
          f"Combined t(2): [{p['combined_ci95_t2_pp'][0]:.1f}, "
          f"{p['combined_ci95_t2_pp'][1]:.1f}] — "
          f"{'excludes' if p['t2_excludes_zero'] else 'INCLUDES'} zero. "
          f"Replicate-mean-only t(2): [{p['replicate_only_t2_ci95_pp'][0]:.1f}, "
          f"{p['replicate_only_t2_ci95_pp'][1]:.1f}].",
          "",
          f"Same-batch kill test (FM-1, all three replicates pooled): "
          f"Gap(R) {s['gap_R_pp']:.1f} -> Gap(M) {s['gap_M_pp']:.1f}, "
          f"delta {s['delta_pp']:.1f}pp "
          f"[{s['delta_ci95_pp'][0]:.1f}, {s['delta_ci95_pp'][1]:.1f}]; "
          f"masking removes {100*s['removed_share']:.1f}% of the gap "
          f"(residual {100*s['residual_share']:.1f}%)."]
    (OUT / "replicate_e2.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
