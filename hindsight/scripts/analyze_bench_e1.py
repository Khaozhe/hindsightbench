"""POST-FREEZE EXPLORATORY (2026-07-26, pre-deadline self-audit).

E1 = Gap(R) - Gap(D) across the fifteen-model benchmark panel.

Why this exists: the paper estimates E1 only on the causal core (the two
Gemini rows). The benchmark panel ships R and D arms for every model -- the
generations were paid for and are in the frozen artifact -- but
analyze_bench_row.py never constructs Gap(R) - Gap(D), and Appendix D has no
E1 column. Section 8.1's "E1 on the Geminis only" therefore reads as a data
limitation when it is in fact a quantity we never computed. A reviewer with
the released artifact can compute it in a few lines, so we compute it first.

Estimator: identical to the frozen pipeline -- analyze_fm1.gap over
analyze_bench_row.load_arm output, analyze_bench_row.boot_diff with
B = 10,000 and np.random.default_rng(2026), the preregistered CRISIS set and
the calm-year set restricted to each model's available pre-cutoff dates.

Replicate parity (added 2026-07-26 after the first version of this table
shipped a wrong Gemini 2.5 Pro row): E1 is a *within-batch* contrast, per the
same-batch discipline the paper imposes on every other estimand (section 4.1,
E.10). Pooling unequal replicate counts across the two arms is exactly the
cross-batch comparison the paper refuses elsewhere, and it is not harmless --
Gemini 2.5 Pro ships R at 1 rep and D at 3, and the unmatched contrast reads
-7.6pp against the matched -1.2pp, a 6.5pp artifact of the mismatch. Every row
is therefore restricted to the replicates its two arms have in common, and
rows where that discards data are flagged in the output.

Three hard anchors abort the run if the estimator has drifted:
  (1) gemini-2.5-flash E1 must reproduce the paper's frozen -3.4pp (its bench
      arm cells are symlinks into outputs/fm1, so this is an identity, not an
      approximation);
  (2) gpt-5.4-mini Gap(D) must match the gap_D recorded in its frozen row json;
  (3) gemini-2.5-pro E1 under replicate parity must reproduce the -1.2pp that
      section 4.3 reports for the causal core.

Read-only: writes only under outputs/review/.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "hindsight" / "scripts"))

from analyze_bench_row import boot_diff, load_arm  # noqa: E402
from analyze_fm1 import CALM_YEARS, CRISIS, all_dates, gap  # noqa: E402
from bench_registry import MODELS  # noqa: E402

BENCH = REPO / "hindsight" / "outputs" / "bench"
OUT = REPO / "hindsight" / "outputs" / "review"
SEED = 2026

FLASH_ANCHOR = -0.03367003367003367   # paper section 4.2: E1 = -3.4pp
MINI_GAPD_KEY = "gpt-5.4-mini"
PRO_KEY = "gemini-2.5-pro"
PRO_ANCHOR = -0.011670  # paper section 4.3: E1 = -1.2pp (rep-matched)


def arm_reps(root: Path, arm: str) -> list[str]:
    d = root / arm
    return sorted(p.name for p in d.glob("rep*")) if d.is_dir() else []


def load_arm_reps(root: Path, arm: str, reps: list[str]) -> dict:
    """load_arm restricted to named replicate dirs (same parsing rules)."""
    by_date: dict[str, list[str]] = {}
    for rep in reps:
        for node in sorted((root / arm / rep).glob("*")):
            f = node / "01_sketches_valid.json"
            if not f.exists():
                continue
            for s in json.loads(f.read_text()):
                if s.get("direction") in ("+", "-"):
                    by_date.setdefault(node.name, []).append(s["direction"])
    return by_date


def windows(by_date: dict) -> tuple[list[str], list[str]]:
    """Frozen windows intersected with the dates this model actually has."""
    pre = set(all_dates())
    have = {d for d in by_date if d in pre}
    crisis = [d for d in CRISIS if d in have]
    calm = sorted(d for d in have if d[:4] in CALM_YEARS)
    return crisis, calm


def main() -> None:
    rows = []
    for m in MODELS:
        key = m["key"]
        root = BENCH / key
        if not root.exists():
            rows.append({"model": key, "tex": m["tex"], "status": "missing_dir"})
            continue
        # replicate parity: E1 is a within-batch contrast (see module docstring)
        reps_R, reps_D = arm_reps(root, "R"), arm_reps(root, "D")
        shared = [r for r in reps_R if r in set(reps_D)]
        restricted = shared != reps_R or shared != reps_D
        if shared:
            R = load_arm_reps(root, "R", shared)
            D = load_arm_reps(root, "D", shared)
        else:  # no rep dirs (legacy layout): fall back, nothing to match on
            R, _ = load_arm(root, "R")
            D, _ = load_arm(root, "D")
        common = {d: v for d, v in R.items() if d in D}
        crisis, calm = windows(common)
        if len(crisis) < 2 or len(calm) < 2:
            rows.append({"model": key, "tex": m["tex"], "status": "insufficient_windows",
                         "n_crisis": len(crisis), "n_calm": len(calm)})
            continue
        g_r, g_d = gap(R, crisis, calm), gap(D, crisis, calm)
        if any(math.isnan(x) for x in (g_r, g_d)):
            rows.append({"model": key, "tex": m["tex"], "status": "nan_gap"})
            continue
        rng = np.random.default_rng(SEED)
        lo, hi = boot_diff(lambda c, q: gap(R, c, q),
                           lambda c, q: gap(D, c, q), crisis, calm, rng)
        degenerate = math.isnan(lo) or math.isnan(hi)
        rows.append({
            "model": key, "tex": m["tex"], "generation": m["gen"],
            "status": "ok",
            "gap_R": round(g_r, 6), "gap_D": round(g_d, 6),
            "E1": round(g_r - g_d, 6),
            "E1_ci95": None if degenerate else [round(lo, 6), round(hi, 6)],
            # NaN CIs must never be read as "significant" -- the prior
            # in-session script had exactly that bug on the degenerate dirs.
            "significant": (not degenerate) and (lo > 0 or hi < 0),
            "sign": "+" if g_r - g_d > 0 else "-",
            "n_crisis": len(crisis), "n_calm": len(calm),
            "reps_used": shared, "reps_R_all": reps_R, "reps_D_all": reps_D,
            "reps_restricted": restricted,
        })

    ok = [r for r in rows if r["status"] == "ok"]
    by_key = {r["model"]: r for r in ok}

    # ---- anchor 1: flash reproduces the paper's frozen E1 -------------------
    fl = by_key.get("gemini-2.5-flash")
    assert fl is not None, "gemini-2.5-flash row missing; cannot anchor"
    assert abs(fl["E1"] - FLASH_ANCHOR) < 5e-6, (
        f"ANCHOR 1 FAILED: flash bench E1 {fl['E1']} != paper -3.4pp "
        f"({FLASH_ANCHOR}); estimator has drifted, refusing to report.")

    # ---- anchor 2: gap_D matches the frozen row json ------------------------
    mini_json = json.loads((BENCH / MINI_GAPD_KEY / f"{MINI_GAPD_KEY}_row.json").read_text())
    frozen_gap_d = mini_json["E2_date_trigger"]["gap_D"]
    mini = by_key[MINI_GAPD_KEY]
    assert abs(mini["gap_D"] - frozen_gap_d) < 1e-6, (
        f"ANCHOR 2 FAILED: recomputed gap_D {mini['gap_D']} != frozen "
        f"{frozen_gap_d}")

    # ---- anchor 3: rep-matched Pro reproduces section 4.3's -1.2pp ---------
    # Guards the replicate-parity fix: without it Pro reads -7.6pp and silently
    # contradicts the main text.
    pro = by_key.get(PRO_KEY)
    assert pro is not None, "gemini-2.5-pro row missing; cannot anchor"
    assert abs(pro["E1"] - PRO_ANCHOR) < 5e-5, (
        f"ANCHOR 3 FAILED: rep-matched Pro E1 {pro['E1']} != section 4.3's "
        f"{PRO_ANCHOR} (-1.2pp); replicate parity has regressed.")

    sig = [r for r in ok if r["significant"]]
    pos = [r for r in ok if r["sign"] == "+"]
    res = {
        "note": "POST-FREEZE EXPLORATORY (2026-07-26). Frozen bench arms, zero "
                "new API calls. Estimator identical to analyze_bench_row "
                f"(boot_diff, B=10000, seed {SEED}).",
        "anchors": {
            "flash_E1_matches_paper_minus_3_4pp": True,
            "flash_E1": fl["E1"],
            "gpt_5_4_mini_gap_D_matches_row_json": True,
            "gap_D": mini["gap_D"], "frozen_gap_D": frozen_gap_d,
            "pro_E1_matches_paper_minus_1_2pp": True,
            "pro_E1": pro["E1"],
        },
        "replicate_parity": {
            "rule": "E1 restricted to replicates present in BOTH the R and D "
                    "arms (within-batch contrast, per section 4.1 / E.10).",
            "rows_restricted": [
                {"model": r["model"], "reps_used": r["reps_used"],
                 "reps_R_all": r["reps_R_all"], "reps_D_all": r["reps_D_all"]}
                for r in ok if r.get("reps_restricted")],
        },
        "n_models_estimated": len(ok),
        "n_significant": len(sig),
        "significant_models": [
            {"model": r["model"], "E1_pp": round(r["E1"] * 100, 2),
             "ci95_pp": [round(c * 100, 2) for c in r["E1_ci95"]]} for r in sig],
        "sign_split": {"positive": len(pos), "negative": len(ok) - len(pos)},
        "rows": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bench_e1.json").write_text(json.dumps(res, indent=2) + "\n")

    L = ["# Cross-model E1 = Gap(R) - Gap(D) (2026-07-26 pre-deadline audit)",
         "", res["note"], "",
         f"Anchors PASSED: flash E1 = {fl['E1']:.6f} (paper -3.4pp); "
         f"gpt-5.4-mini gap_D = {mini['gap_D']:.6f} (frozen row json); "
         f"rep-matched pro E1 = {pro['E1']:.6f} (paper -1.2pp).", "",
         "Replicate parity enforced (E1 is a within-batch contrast). Rows "
         "restricted to the reps their two arms share: "
         + (", ".join(f"{r['model']} (R {r['reps_R_all']} vs D {r['reps_D_all']}"
                      f" -> {r['reps_used']})"
                      for r in ok if r.get("reps_restricted")) or "none") + ".", "",
         "| model | gen | Gap(R) | Gap(D) | E1 (pp) | CI95 (pp) | sig |",
         "|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] != "ok":
            L.append(f"| {r.get('tex', r['model'])} | | | | — | — | {r['status']} |")
            continue
        ci = ("—" if r["E1_ci95"] is None
              else f"[{r['E1_ci95'][0]*100:+.1f}, {r['E1_ci95'][1]*100:+.1f}]")
        L.append(f"| {r['tex']} | {r['generation']} | {r['gap_R']:.3f} | "
                 f"{r['gap_D']:.3f} | {r['E1']*100:+.1f} | {ci} | "
                 f"{'YES' if r['significant'] else ''} |")
    L += ["", f"Estimated on {len(ok)} models; {len(sig)} significant; "
              f"signs {len(pos)} positive / {len(ok)-len(pos)} negative."]
    for r in sig:
        e2 = None
        p = BENCH / r["model"] / f"{r['model']}_row.json"
        if p.exists():
            e2 = json.loads(p.read_text())["E2_date_trigger"]["est"]
        L.append(f"- **{r['tex']}**: E1 {r['E1']*100:+.1f}pp "
                 f"[{r['E1_ci95'][0]*100:+.1f}, {r['E1_ci95'][1]*100:+.1f}]"
                 + (f", against its own E2 {e2*100:+.1f}pp" if e2 is not None else ""))
    (OUT / "bench_e1.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
