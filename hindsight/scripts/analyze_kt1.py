#!/usr/bin/env python
"""KT-1 analysis per frozen prereg (hindsight/prereg/KT1_prereg.md, sha256 12d4b6f8...).

Computes Gap_R (V1 revealed arm, stored panel) and Gap_M (KT-1 masked arm),
paired-by-date bootstrap on Delta = Gap_R - Gap_M, date-recovery rate, the
prereg decision rule, and descriptive secondaries. Writes KT1_DECISION.md.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from hindsight_paths import REPO
V1_PANEL = REPO / "macrochain/data/processed/sketches_panel.jsonl"
KT1 = REPO / "hindsight/outputs/kt1"
NODES = KT1 / "masked_nodes"
PROBES = KT1 / "date_probe_results.jsonl"
OUT_MD = KT1 / "KT1_DECISION.md"
OUT_JSON = KT1 / "kt1_metrics.json"

CRISIS = [
    "2008-09-15", "2008-10-15", "2008-11-15", "2008-12-15", "2009-01-15",
    "2009-02-15", "2020-03-15", "2020-04-15", "2022-06-15", "2022-09-15",
    "2022-10-15",
]
CALM_YEARS = {"2013", "2014", "2017"}

ERA_TERMS = [
    "financial crisis", "housing crisis", "subprime", "great recession",
    "pandemic", "covid", "lehman", "dot-com", "gfc", "post-crisis",
    "quantitative easing", "zero lower bound", "taper", "inflation surge",
]

B = 10_000
SEED = 2026


def load_arm_revealed() -> dict[str, list[str]]:
    by_date: dict[str, list[str]] = defaultdict(list)
    for line in V1_PANEL.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("direction") in ("+", "-"):
            by_date[d["decision_date"]].append(d["direction"])
    return by_date


def load_arm_masked() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    by_date: dict[str, list[str]] = defaultdict(list)
    narratives: dict[str, list[str]] = defaultdict(list)
    for node_dir in sorted(NODES.iterdir()):
        f = node_dir / "01_sketches_valid.json"
        if not f.exists():
            continue
        for s in json.loads(f.read_text()):
            if s.get("direction") in ("+", "-"):
                by_date[s["decision_date"]].append(s["direction"])
                narratives[s["decision_date"]].append(
                    " ".join(
                        str(s.get(k, "")) for k in ("mechanism_narrative", "regime_hint", "failure_condition")
                    ).lower()
                )
    return by_date, narratives


def window_counts(by_date: dict[str, list[str]], dates: list[str]) -> tuple[int, int]:
    bear = total = 0
    for d in dates:
        dirs = by_date.get(d, [])
        bear += sum(1 for x in dirs if x == "-")
        total += len(dirs)
    return bear, total


def gap(by_date: dict[str, list[str]], crisis: list[str], calm: list[str]) -> float:
    cb, ct = window_counts(by_date, crisis)
    qb, qt = window_counts(by_date, calm)
    if ct == 0 or qt == 0:
        raise RuntimeError("empty window")
    return cb / ct - qb / qt


def main() -> None:
    revealed = load_arm_revealed()
    masked, narratives = load_arm_masked()

    all_dates = sorted(revealed.keys())
    calm = [d for d in all_dates if d[:4] in CALM_YEARS]
    missing_masked = [d for d in all_dates if d not in masked]

    gap_r = gap(revealed, CRISIS, calm)
    gap_m = gap(masked, CRISIS, calm)
    delta_hat = gap_r - gap_m

    # paired-by-date bootstrap: resample crisis dates and calm dates (both arms
    # share the resampled date sets, preserving the pairing)
    rng = np.random.default_rng(SEED)
    deltas = np.empty(B)
    crisis_arr = np.array(CRISIS)
    calm_arr = np.array(calm)
    for b in range(B):
        cs = list(rng.choice(crisis_arr, size=len(crisis_arr), replace=True))
        qs = list(rng.choice(calm_arr, size=len(calm_arr), replace=True))
        deltas[b] = gap(revealed, cs, qs) - gap(masked, cs, qs)
    ci_lo, ci_hi = np.percentile(deltas, [2.5, 97.5])

    # date-recovery probe
    probe_rows = [json.loads(l) for l in PROBES.read_text().splitlines() if l.strip()]
    def months_off(row) -> int | None:
        est = row.get("estimated_date")
        if not est or len(est) < 7:
            return None
        try:
            ey, em = int(est[:4]), int(est[5:7])
        except ValueError:
            return None
        ty, tm = int(row["decision_date"][:4]), int(row["decision_date"][5:7])
        return abs((ty - ey) * 12 + (tm - em))
    offs = [months_off(r) for r in probe_rows]
    valid_offs = [o for o in offs if o is not None]
    rec12 = sum(1 for o in valid_offs if o <= 12) / len(valid_offs) if valid_offs else float("nan")
    rec_exact = sum(1 for o in valid_offs if o == 0) / len(valid_offs) if valid_offs else float("nan")
    med_off = float(np.median(valid_offs)) if valid_offs else float("nan")

    # prereg decision rule
    if delta_hat >= 0.10 and ci_lo > 0:
        decision = "GO"
        rationale = "Δ ≥ 10pp 且 95% CI 排除 0：C1/C2（日期/泄漏上下文）通道显著驱动危机月看空偏置。"
    elif gap_m >= gap_r - 0.05 and rec12 < 0.25:
        decision = "KILL"
        rationale = "masked 臂复现了 revealed 臂的 gap 且日期不可恢复：偏置由数据通道（C3）解释，无参数化 hindsight 故事。"
    elif gap_m >= gap_r - 0.05:
        decision = "GO-pivot"
        rationale = "masked 臂复现 gap 但日期高度可恢复：偏置经由值→日期隐式召回，设计转向 wrong-date 臂为主。"
    else:
        decision = "GO-reframe"
        rationale = "通道混合：C1/C2 与 C3 各有贡献，论文重心放在通道分解本身。"

    # descriptive secondaries
    def yearly(by_date):
        agg = defaultdict(lambda: [0, 0])
        for d, dirs in by_date.items():
            y = d[:4]
            agg[y][0] += sum(1 for x in dirs if x == "-")
            agg[y][1] += len(dirs)
        return {y: (b / t if t else float("nan")) for y, (b, t) in sorted(agg.items())}
    yearly_r, yearly_m = yearly(revealed), yearly(masked)

    era_hits = sum(1 for d, texts in narratives.items() for t in texts if any(e in t for e in ERA_TERMS))
    era_total = sum(len(t) for t in narratives.values())

    cb_r, ct_r = window_counts(revealed, CRISIS)
    qb_r, qt_r = window_counts(revealed, calm)
    cb_m, ct_m = window_counts(masked, CRISIS)
    qb_m, qt_m = window_counts(masked, calm)

    metrics = {
        "prereg_sha256": "12d4b6f85762d35e751f96dae5db62e8d8b1402ee71183e0f4b4bd6564a21128",
        "n_dates_masked": len(masked),
        "missing_masked_dates": missing_masked,
        "revealed": {"crisis": [cb_r, ct_r], "calm": [qb_r, qt_r], "gap": gap_r},
        "masked": {"crisis": [cb_m, ct_m], "calm": [qb_m, qt_m], "gap": gap_m},
        "delta_hat": delta_hat,
        "delta_ci95": [float(ci_lo), float(ci_hi)],
        "bootstrap": {"B": B, "seed": SEED, "scheme": "resample crisis dates and calm dates, shared across arms"},
        "date_recovery": {
            "n_probes": len(probe_rows), "n_parsed": len(valid_offs),
            "exact_month": rec_exact, "within_12mo": rec12, "median_months_off": med_off,
        },
        "decision": decision,
        "rationale": rationale,
        "yearly_bearish_revealed": yearly_r,
        "yearly_bearish_masked": yearly_m,
        "era_term_rate_masked": era_hits / era_total if era_total else float("nan"),
        "special": {
            "2020-03_masked": f"{sum(1 for x in masked.get('2020-03-15', []) if x == '-')}/{len(masked.get('2020-03-15', []))}",
            "2020-03_revealed": f"{sum(1 for x in revealed.get('2020-03-15', []) if x == '-')}/{len(revealed.get('2020-03-15', []))}",
            "2023_masked": yearly_m.get("2023"),
            "2023_revealed": yearly_r.get("2023"),
        },
    }
    OUT_JSON.write_text(json.dumps(metrics, indent=2))

    lines = [
        "# KT-1 Decision (per frozen prereg KT1_prereg.md)",
        "",
        f"**判定：{decision}** — {rationale}",
        "",
        f"- Gap_R (revealed) = {gap_r:.3f}  (crisis {cb_r}/{ct_r} = {cb_r/ct_r:.3f}, calm {qb_r}/{qt_r} = {qb_r/qt_r:.3f})",
        f"- Gap_M (masked)   = {gap_m:.3f}  (crisis {cb_m}/{ct_m} = {cb_m/ct_m:.3f}, calm {qb_m}/{qt_m} = {qb_m/qt_m:.3f})",
        f"- Δ = Gap_R − Gap_M = {delta_hat:.3f}, 95% CI [{ci_lo:.3f}, {ci_hi:.3f}] (paired bootstrap B={B}, seed={SEED})",
        f"- 日期恢复探针：精确月 {rec_exact:.1%}，±12 月内 {rec12:.1%}，中位偏差 {med_off:.0f} 个月 (n={len(valid_offs)})",
        f"- masked 臂时代专名出现率：{era_hits}/{era_total} = {era_hits/era_total if era_total else float('nan'):.2%}",
        f"- 2020-03 看空：revealed {metrics['special']['2020-03_revealed']} vs masked {metrics['special']['2020-03_masked']}",
        f"- 2023 年均看空率：revealed {yearly_r.get('2023', float('nan')):.3f} vs masked {yearly_m.get('2023', float('nan')):.3f}",
        f"- masked 面板完整性：{len(masked)}/240 日期" + (f"，缺失 {missing_masked}" if missing_masked else ""),
        "",
        "| 年份 | revealed bearish | masked bearish |",
        "|---|---|---|",
    ]
    for y in sorted(yearly_r):
        lines.append(f"| {y} | {yearly_r[y]:.3f} | {yearly_m.get(y, float('nan')):.3f} |")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:14]))
    print(f"\nwritten: {OUT_MD}\n         {OUT_JSON}")


if __name__ == "__main__":
    main()
