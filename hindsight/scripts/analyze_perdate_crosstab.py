#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls.

P0-4: per-date REC/LAP x trigger cross-tab (ICLR_REVISION_PLAN.md §P0-4,
reviewer Q6). Reads only frozen bench outputs; writes to outputs/review/.

Per model (llama-3.1-70b-awq + qwen3-30b-a3b-fp8dyn = memory-without-trigger;
gemini-2.5-flash + qwen3.6-27b-fp8 = triggered contrasts), per pre-cutoff
date (240):
  (a) trigger primitive  T(d) = bearish_share_D(d) - bearish_share_M(d),
      directions pooled over reps (E2 analogue at date grain);
  (b) transplant primitive  W(d) = agreement of W-cell directions with the
      fake-date realized sign minus agreement with the true-date realized
      sign (E3 analogue at date grain);
  (c) memory primitives: REC year/year-month hit from estimated_date,
      per-date LAP recall-hit (majority up/down vs realized; ties and
      all-unknown dates drop, matching the frozen recall_n), and the
      continuous LAP answer share (up+down)/n.
Then a quadrant analysis: among high-recall dates (REC year-hit==1 OR LAP
majority correct), the fraction with T(d) above the model's own calm-date
baseline, contrasted against low-recall dates and across the two model
groups. Loading recipes are copied verbatim from analyze_bench_row.py
(load_arm / realized / REC parse / per-date LAP recall-hit) so every
aggregate reconciles against the frozen *_row.json numbers, which this
script asserts (E2 to 1e-9; REC/LAP rates to 1e-9; recall_n exactly).

Outputs: hindsight/outputs/review/perdate_crosstab.{json,md} and
fig_perdate_crosstab.{pdf,png}.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import CALM_YEARS, CRISIS, all_dates, fake_map
from hindsight_paths import REPO

BENCH = REPO / "hindsight/outputs/bench"
SPX_NEW = REPO / "macrochain/data/processed/spx_target_new.parquet"
OUT = REPO / "hindsight/outputs/review"

# (model, group, arm reps, lap reps) — the 2x2 contrast frozen in the plan.
MODELS = [
    ("llama-3.1-70b-awq", "memory-without-trigger", 2, 20),
    ("qwen3-30b-a3b-fp8dyn", "memory-without-trigger", 1, 10),
    ("gemini-2.5-flash", "triggered", 3, 20),
    ("qwen3.6-27b-fp8", "triggered", 2, 20),
]

INK = "#2b2b2b"
CRISIS_C = "#B3402A"   # repo arm-D red
CURVE_C = "#2A6EB3"    # repo arm-M blue
BASE_C = "#9a7b2d"     # repo gold
GRAY = "#8a8a8a"


def load_arm(root: Path, arm: str) -> dict[str, list[str]]:
    """analyze_bench_row.py:40-59 recipe, directions only (pooled over reps)."""
    by_date: dict[str, list[str]] = defaultdict(list)
    for node in (root / arm).glob("rep*/*"):
        f = node / "01_sketches_valid.json"
        if not f.exists():
            continue
        for s in json.loads(f.read_text()):
            if s.get("direction") in ("+", "-"):
                by_date[node.name].append(s["direction"])
    return by_date


def build_realized(pre: list[str]) -> dict[str, float | None]:
    """analyze_bench_row.py:158-174 recipe: sign of forward_return_20d."""
    spx = pd.read_parquet(SPX_NEW).reset_index()
    dcol = "date" if "date" in spx.columns else spx.columns[0]
    spx[dcol] = pd.to_datetime(spx[dcol])
    spx = spx.sort_values(dcol)

    def realized(d):
        after = spx[spx[dcol] >= pd.Timestamp(d)]
        if not len(after) or pd.isna(after.iloc[0]["forward_return_20d"]):
            return None
        return 1.0 if after.iloc[0]["forward_return_20d"] >= 0 else -1.0

    return {d: realized(d) for d in pre}


def rec_hits(root: Path) -> dict[str, dict]:
    """analyze_bench_row.py:106-131 parse recipe, kept at date grain."""
    rows = [json.loads(l) for l in
            (root / "date_probe_results.jsonl").read_text().splitlines() if l.strip()]
    out = {}
    for r in rows:
        d = r["decision_date"]
        est = r.get("estimated_date")
        rec = {"estimated_date": est, "year_hit": None, "ym_hit": None}
        if est and len(est) >= 7:
            try:
                ey, em = int(est[:4]), int(est[5:7])
            except ValueError:
                out[d] = rec
                continue
            ty, tm = int(d[:4]), int(d[5:7])
            rec["year_hit"] = int(ey == ty)
            rec["ym_hit"] = int(ey == ty and em == tm)
        out[d] = rec
    return out


def lap_perdate(root: Path) -> dict[str, dict]:
    """LAP answer share + net direction per date (analyze_bench_row.py:136-143)."""
    rows = [json.loads(l) for l in
            (root / "lap_probe_results.jsonl").read_text().splitlines() if l.strip()]
    cnt: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        cnt[r["decision_date"]][r["answer"]] += 1
    out = {}
    for d, c in cnt.items():
        n = sum(c.values())
        out[d] = {"lap_share": (c["up"] + c["down"]) / n if n else float("nan"),
                  "lap_ud": (c["up"] - c["down"]) / n if n else float("nan")}
    return out


def share(xs: list[str]) -> float:
    return sum(1 for x in xs if x == "-") / len(xs) if xs else float("nan")


def pooled_gap(rows: list[dict], window: list[str], num: str, den: str) -> float:
    b = sum(r[num] for r in rows if r["date"] in set(window))
    t = sum(r[den] for r in rows if r["date"] in set(window))
    return b / t if t else float("nan")


def per_model(model: str, group: str, arm_reps: int, lap_reps: int,
              pre: list[str], calm: list[str], fmap: dict[str, str],
              real: dict[str, float | None]) -> dict:
    root = BENCH / model
    D, M, W = (load_arm(root, a) for a in ("D", "M", "W"))
    rec, lap = rec_hits(root), lap_perdate(root)

    # ---- done-criterion (a): 258/258 universe, 240 pre ----
    uni = set(D) & set(rec) & set(lap)
    assert len(uni) == 258, f"{model}: armD∩REC∩LAP = {len(uni)} != 258"
    pre_uni = uni & set(pre)
    assert len(pre_uni) == 240, f"{model}: pre subset = {len(pre_uni)} != 240"
    print(f"[assert OK] {model}: |armD∩REC∩LAP| = {len(uni)} == 258, "
          f"pre == {len(pre_uni)} == 240")

    rows = []
    for d in pre:
        xd, xm, xw = D.get(d, []), M.get(d, []), W.get(d, [])
        t = share(xd) - share(xm)
        # transplant primitive: W directions vs fake- vs true-date realized sign
        rt, rf = real.get(d), real.get(fmap[d])
        if xw and rt is not None and rf is not None:
            sgn = [1.0 if x == "+" else -1.0 for x in xw]
            wprim = float(np.mean([s == rf for s in sgn])
                          - np.mean([s == rt for s in sgn]))
        else:
            wprim = float("nan")
        lp = lap[d]
        # per-date LAP recall-hit (analyze_bench_row.py:175-180 gate verbatim)
        if abs(lp["lap_ud"]) > 1e-9 and real.get(d) is not None:
            lap_hit = int(np.sign(lp["lap_ud"]) == real[d])
        else:
            lap_hit = None   # tie / all-unknown / no realized -> date drops
        rows.append({
            "date": d, "crisis": d in CRISIS, "calm": d in set(calm),
            "trigger": t,
            "bear_D": sum(1 for x in xd if x == "-"), "tot_D": len(xd),
            "bear_M": sum(1 for x in xm if x == "-"), "tot_M": len(xm),
            "transplant": wprim,
            "rec_year_hit": rec[d]["year_hit"], "rec_ym_hit": rec[d]["ym_hit"],
            "estimated_date": rec[d]["estimated_date"],
            "lap_share": lp["lap_share"], "lap_ud": lp["lap_ud"],
            "lap_hit": lap_hit,
        })

    # ---- done-criterion (b): reconcile against the frozen row json ----
    frozen = json.loads((root / f"{model}_row.json").read_text())
    e2_recon = (pooled_gap(rows, CRISIS, "bear_D", "tot_D")
                - pooled_gap(rows, calm, "bear_D", "tot_D")
                - pooled_gap(rows, CRISIS, "bear_M", "tot_M")
                + pooled_gap(rows, calm, "bear_M", "tot_M"))
    e2_frozen = frozen["E2_date_trigger"]["est"]
    assert abs(e2_recon - e2_frozen) < 1e-9, (model, e2_recon, e2_frozen)
    rec_rate = float(np.mean([r["rec_year_hit"] for r in rows
                              if r["rec_year_hit"] is not None]))
    assert abs(rec_rate - frozen["REC"]["pre"]["year"]) < 1e-9
    hits = [r["lap_hit"] for r in rows if r["lap_hit"] is not None]
    # frozen recall_n / recall_hit_rate include the 18 post-cutoff dates in
    # principle, but post-cutoff LAP is all-unknown for these models (post_mean
    # 0.0), so every post date drops on the |ud|>0 gate and pre == frozen.
    assert len(hits) == frozen["LAP"]["recall_n"], (len(hits), frozen["LAP"]["recall_n"])
    assert abs(float(np.mean(hits)) - frozen["LAP"]["recall_hit_rate"]) < 1e-9
    print(f"[reconcile OK] {model}: E2 recon {e2_recon:+.6f} == frozen "
          f"{e2_frozen:+.6f}; REC-year {rec_rate:.4f}; LAP recall_n {len(hits)} "
          f"hit {np.mean(hits):.4f}")

    # ---- quadrant analysis ----
    baseline = float(np.nanmean([r["trigger"] for r in rows if r["calm"]]))
    for r in rows:
        r["high_recall"] = bool(r["rec_year_hit"] == 1 or r["lap_hit"] == 1)
        r["above_baseline"] = (None if np.isnan(r["trigger"])
                               else bool(r["trigger"] > baseline))
    q = {"HH": 0, "HL": 0, "LH": 0, "LL": 0}
    for r in rows:
        if r["above_baseline"] is None:
            continue
        key = ("H" if r["high_recall"] else "L") + ("H" if r["above_baseline"] else "L")
        q[key] += 1

    def frac(a, b):
        return a / (a + b) if a + b else None

    def stratum_mean(key, flag):
        vals = [r[key] for r in rows
                if r["high_recall"] == flag and not np.isnan(r[key])]
        return float(np.mean(vals)) if vals else None

    summary = {
        "group": group, "arm_reps": arm_reps, "lap_reps": lap_reps,
        "E2_frozen": e2_frozen, "E2_reconstructed": e2_recon,
        "REC_year_rate_pre": rec_rate,
        "LAP_recall_n_pre": len(hits), "LAP_recall_hit_rate": float(np.mean(hits)),
        "calm_baseline_trigger": baseline,
        "n_high_recall": q["HH"] + q["HL"], "n_low_recall": q["LH"] + q["LL"],
        "quadrants": q,
        "frac_above_baseline_high_recall": frac(q["HH"], q["HL"]),
        "frac_above_baseline_low_recall": frac(q["LH"], q["LL"]),
        "frac_diff_high_minus_low": (
            frac(q["HH"], q["HL"]) - frac(q["LH"], q["LL"])
            if frac(q["HH"], q["HL"]) is not None and frac(q["LH"], q["LL"]) is not None
            else None),
        "mean_trigger_high_recall": stratum_mean("trigger", True),
        "mean_trigger_low_recall": stratum_mean("trigger", False),
        "mean_transplant_high_recall": stratum_mean("transplant", True),
        "mean_transplant_low_recall": stratum_mean("transplant", False),
        # crisis stratum: where the frozen E2 actually lives at date grain
        "n_crisis_high_recall": sum(1 for r in rows if r["crisis"] and r["high_recall"]),
        "mean_trigger_crisis": float(np.nanmean(
            [r["trigger"] for r in rows if r["crisis"]])),
        "mean_trigger_high_recall_noncrisis": (
            lambda v: float(np.mean(v)) if v else None)(
            [r["trigger"] for r in rows
             if r["high_recall"] and not r["crisis"] and not np.isnan(r["trigger"])]),
    }
    return {"summary": summary, "per_date": rows}


def make_figure(res: dict) -> Path:
    plt.rcParams.update({
        "font.size": 7.6, "figure.dpi": 150, "savefig.bbox": "tight",
        "pdf.fonttype": 42, "ps.fonttype": 42,
        "axes.edgecolor": INK, "axes.labelcolor": INK,
        "xtick.color": INK, "ytick.color": INK, "text.color": INK,
    })
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 5.0), sharex=True)
    for ax, (model, group, arm_reps, lap_reps) in zip(axes.flat, MODELS):
        rows = res[model]["per_date"]
        s = res[model]["summary"]
        x = np.array([r["lap_share"] for r in rows])
        y = np.array([r["trigger"] for r in rows])
        cri = np.array([r["crisis"] for r in rows])
        ax.axhline(0, color="#d9d5cc", lw=0.7, zorder=0)
        ax.scatter(x[~cri], y[~cri], s=9, color=GRAY, alpha=0.55, lw=0,
                   label="other pre-cutoff date", zorder=2)
        ax.scatter(x[cri], y[cri], s=30, color=CRISIS_C, marker="x", lw=1.3,
                   label="crisis-window date", zorder=4)
        # binned mean curve: quantile bins on LAP (collapse duplicate edges)
        edges = np.unique(np.quantile(x, np.linspace(0, 1, 7)))
        if len(edges) > 2:
            idx = np.clip(np.digitize(x, edges[1:-1]), 0, len(edges) - 2)
            bx = [x[idx == i].mean() for i in range(len(edges) - 1) if (idx == i).any()]
            by = [np.nanmean(y[idx == i]) for i in range(len(edges) - 1) if (idx == i).any()]
            ax.plot(bx, by, color=CURVE_C, lw=1.6, marker="o", ms=3.5,
                    label="binned mean (LAP sextile)", zorder=3)
        ax.axhline(s["calm_baseline_trigger"], color=BASE_C, lw=1.1, ls="--",
                   label="calm-date baseline", zorder=1)
        rep_note = f"{arm_reps} rep" + ("s" if arm_reps > 1 else " — single-rep, noisy")
        ax.set_title(f"{model}  ({group}, {rep_note})\n"
                     f"E2={s['E2_frozen']:+.3f}  REC-yr={s['REC_year_rate_pre']:.0%}"
                     f"  LAP-hit={s['LAP_recall_hit_rate']:.0%}", fontsize=7.2)
        ax.grid(color="#eeebe4", lw=0.5, zorder=0)
        ax.set_axisbelow(True)
    for ax in axes[1]:
        ax.set_xlabel("per-date LAP answer share (up+down)/n")
    for ax in axes[:, 0]:
        ax.set_ylabel("trigger primitive\nbearish share D $-$ M")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False,
               fontsize=7.0, bbox_to_anchor=(0.5, -0.035))
    fig.suptitle("Per-date memory (LAP) x trigger (D$-$M) cross-tab, 240 pre-cutoff dates",
                 fontsize=8.4, y=0.995)
    fig.tight_layout(rect=(0, 0.015, 1, 1))
    out = OUT / "fig_perdate_crosstab"
    fig.savefig(out.with_suffix(".pdf"))
    fig.savefig(out.with_suffix(".png"), dpi=250)
    plt.close(fig)
    return out


def write_md(res: dict) -> None:
    L = ["# P0-4 per-date REC/LAP x trigger cross-tab",
         "",
         "POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls;",
         "reads frozen bench outputs only. Script: `scripts/analyze_perdate_crosstab.py`.",
         "",
         "Trigger primitive T(d) = per-date bearish share, arm D minus arm M,",
         "pooled over reps. High-recall date := REC year-hit == 1 OR per-date LAP",
         "majority direction correct. Baseline := model's own mean T(d) over the",
         "36 calm dates. Quadrants over the 240 pre-cutoff dates.",
         "",
         "| model | group | E2 (frozen) | REC-yr | LAP-hit | calm baseline | n high / n low | frac T>base (high) | frac T>base (low) | diff |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for model, group, *_ in MODELS:
        s = res[model]["summary"]
        L.append(
            f"| {model} | {group} | {s['E2_frozen']:+.3f} | "
            f"{s['REC_year_rate_pre']:.1%} | {s['LAP_recall_hit_rate']:.1%} | "
            f"{s['calm_baseline_trigger']:+.3f} | "
            f"{s['n_high_recall']} / {s['n_low_recall']} | "
            f"{s['frac_above_baseline_high_recall']:.1%} | "
            f"{s['frac_above_baseline_low_recall']:.1%} | "
            f"{s['frac_diff_high_minus_low']:+.1%} |")
    L += ["",
          "## Quadrant counts (high/low recall x above/below calm baseline)",
          "",
          "| model | HH | HL | LH | LL | mean T high | mean T low | mean Wprim high | mean Wprim low |",
          "|---|---|---|---|---|---|---|---|---|"]
    for model, *_ in MODELS:
        s = res[model]["summary"]
        q = s["quadrants"]

        def f(v):
            return "-" if v is None else f"{v:+.3f}"

        L.append(f"| {model} | {q['HH']} | {q['HL']} | {q['LH']} | {q['LL']} | "
                 f"{f(s['mean_trigger_high_recall'])} | {f(s['mean_trigger_low_recall'])} | "
                 f"{f(s['mean_transplant_high_recall'])} | {f(s['mean_transplant_low_recall'])} |")
    L += ["",
          "## Crisis stratum (where the frozen E2 lives at date grain)",
          "",
          "| model | crisis dates high-recall | mean T crisis | mean T high-recall non-crisis | calm baseline |",
          "|---|---|---|---|---|"]
    for model, *_ in MODELS:
        s = res[model]["summary"]
        L.append(f"| {model} | {s['n_crisis_high_recall']}/11 | "
                 f"{s['mean_trigger_crisis']:+.3f} | "
                 f"{s['mean_trigger_high_recall_noncrisis']:+.3f} | "
                 f"{s['calm_baseline_trigger']:+.3f} |")
    L += ["",
          "## Group contrast (computed above, read jointly)",
          "",
          "- **memory-without-trigger** (llama-70b-awq, qwen3-30b-a3b): per-date",
          "  recall exists (REC-yr ~18%, LAP-hit ~67%) but high-recall dates show",
          "  no trigger elevation (frac-diff "
          + " / ".join(f"{res[m]['summary']['frac_diff_high_minus_low']:+.1%}"
                       for m, g, *_ in MODELS if g == "memory-without-trigger")
          + "), and mean T on the crisis",
          "  dates themselves stays near the calm baseline ("
          + " / ".join(f"{res[m]['summary']['mean_trigger_crisis']:+.3f}"
                       for m, g, *_ in MODELS if g == "memory-without-trigger")
          + ").",
          "  Recall identified per-date does not translate into date-triggered",
          "  bearishness anywhere for these models.",
          "- **triggered** (gemini-2.5-flash, qwen3.6-27b-fp8): the trigger is",
          "  crisis-concentrated, not recall-general — mean T on crisis dates ("
          + " / ".join(f"{res[m]['summary']['mean_trigger_crisis']:+.3f}"
                       for m, g, *_ in MODELS if g == "triggered")
          + ")",
          "  sits far above both the calm baseline and the mean over high-recall",
          "  *non-crisis* dates ("
          + " / ".join(f"{res[m]['summary']['mean_trigger_high_recall_noncrisis']:+.3f}"
                       for m, g, *_ in MODELS if g == "triggered")
          + "). Generic per-date recall alone is not",
          "  sufficient; the elevation appears where recall coincides with crisis",
          "  semantics (gemini: "
          + f"{res['gemini-2.5-flash']['summary']['n_crisis_high_recall']}/11 crisis dates are high-recall).",
          "- The raw high-vs-low frac-diff is not interpretable for",
          "  gemini-2.5-flash: its low-recall cell has only "
          + f"{res['gemini-2.5-flash']['summary']['n_low_recall']} dates and its calm",
          "  baseline is deeply negative (D less bearish than M on calm dates), so",
          "  'above baseline' is a low bar met by most dates in both strata.",
          "",
          "## Caveats",
          "",
          "- **qwen3-30b-a3b-fp8dyn is single-rep (1 arm rep, 10 LAP reps):** its",
          "  per-date trigger primitive is a difference of two 8-sketch shares, so",
          "  date-level values are quantized to eighths and noisy; treat its",
          "  quadrant fractions as indicative only. All other models pool 2-3 reps.",
          "- Ties / all-unknown LAP dates drop from the recall-hit metric per the",
          "  frozen recipe: recall_n 222/240 (llama-70b), 224/240 (qwen3-30b),",
          "  211/240 (gemini-2.5-flash), 235/240 (qwen3.6-27b) — expected, matches",
          "  the frozen row jsons exactly (asserted in-script). Dropped dates can",
          "  still qualify as high-recall via REC year-hit.",
          "- Per-date REC is a single probe call per date (frozen design); the",
          "  year-hit indicator at date grain is therefore itself a 1-draw sample.",
          "- Exploratory, post-freeze: no preregistered hypothesis at date grain;",
          "  windows (11 crisis / 36 calm dates) and all recipes are frozen ones.",
          ""]
    (OUT / "perdate_crosstab.md").write_text("\n".join(L))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pre = all_dates()
    calm = [d for d in pre if d[:4] in CALM_YEARS]
    fmap = fake_map(pre)
    real = build_realized(pre)

    res = {}
    for model, group, arm_reps, lap_reps in MODELS:
        res[model] = per_model(model, group, arm_reps, lap_reps,
                               pre, calm, fmap, real)

    out_json = {
        "meta": {
            "status": "POST-FREEZE EXPLORATORY (review-response, 2026-07-21)",
            "script": "scripts/analyze_perdate_crosstab.py",
            "date_universe": {"all": 258, "pre": 240,
                              "crisis": len(CRISIS), "calm": len(calm)},
            "high_recall_def": "REC year-hit == 1 OR per-date LAP majority correct",
            "baseline_def": "mean per-date trigger primitive over 36 calm dates",
        },
        "models": res,
    }
    (OUT / "perdate_crosstab.json").write_text(
        json.dumps(out_json, indent=1, default=float))
    write_md(res)
    fig = make_figure(res)
    print(f"written: {OUT / 'perdate_crosstab.json'}")
    print(f"written: {OUT / 'perdate_crosstab.md'}")
    print(f"written: {fig}.pdf/.png")


if __name__ == "__main__":
    main()
