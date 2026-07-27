#!/usr/bin/env python
"""Regenerate paper Figures 1-3 from raw frozen outputs (no hand-copied numbers).

Fig 1: year-by-year bearish share, revealed (V1 archive) vs masked (KT-1).
Fig 2: W-arm bearish share by window, true-date vs fake-date labeling (FM-1).
Fig 3: contamination rent decay S0->S4 + production rent T2 (FM-2).

Usage: python make_figures.py            # writes hindsight/paper/figures/fig{1,2,3}.pdf + .png
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_kt1 import load_arm_revealed, load_arm_masked
from analyze_fm1 import all_dates, fake_map, gap, CRISIS, CALM_YEARS, load_arm
from bench_registry import MODELS as BENCH_MODELS

from hindsight_paths import REPO
FIGS = REPO / "hindsight/paper/figures"
FM2 = REPO / "hindsight/outputs/fm2/FM2_RESULTS.md"

CRISIS_SPANS = [("2008-09", "2009-02"), ("2020-03", "2020-04"), ("2022-06", "2022-10")]

plt.rcParams.update({
    "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 150, "savefig.bbox": "tight",
    "pdf.fonttype": 42, "ps.fonttype": 42,  # Type 3 fonts are a hard reject
})

# Findings-paper class geometry: \columnwidth = 239.394pt, \textwidth =
# 505.89pt (TeX pt, 72.27/in). Main-paper figures 1/2/4 are built at their
# FINAL printed size, so \includegraphics renders them at scale ~1.0 and every
# native >=9pt glyph stays >=9pt on the page (9pt floor).
TEXPT = 72.27
COLW_IN = 239.394 / TEXPT    # \columnwidth in inches
TEXTW_IN = 505.89 / TEXPT    # \textwidth in inches


def _pdf_size_in(path: Path) -> tuple[float, float]:
    m = re.search(rb"/MediaBox\s*\[([^\]]+)\]", path.read_bytes())
    x0, y0, x1, y1 = map(float, m.group(1).split())
    return (x1 - x0) / 72.0, (y1 - y0) / 72.0


def savefig_exact(fig, name: str, w_in: float, h_in: float, tol: float = 0.004) -> None:
    """Save {name}.pdf/.png with the tight-cropped output at exactly
    (w_in, h_in) inches: savefig.bbox="tight" crops to content, so the figsize
    is iteratively compensated until the cropped PDF hits the target size.
    Deterministic (fixed-point iteration on the same inputs)."""
    pdf = FIGS / f"{name}.pdf"
    fw, fh = w_in, h_in
    for _ in range(8):
        fig.set_size_inches(fw, fh)
        fig.savefig(pdf, pad_inches=0.02)  # thin pad: page real estate goes to >=9pt content
        aw, ah = _pdf_size_in(pdf)
        if abs(aw - w_in) < tol and abs(ah - h_in) < tol:
            break
        fw += w_in - aw
        fh += h_in - ah
    fig.savefig(FIGS / f"{name}.png", pad_inches=0.02)


def yearly_share(by_date: dict[str, list[str]]) -> dict[str, float]:
    grp: dict[str, list[str]] = defaultdict(list)
    for d, xs in by_date.items():
        grp[d[:4]].extend(xs)
    return {y: sum(1 for x in v if x == "-") / len(v) for y, v in sorted(grp.items()) if v}


def fig1() -> None:
    revealed = load_arm_revealed()
    masked, _ = load_arm_masked()
    yr_r, yr_m = yearly_share(revealed), yearly_share(masked)
    years = sorted(yr_r)
    xs = [int(y) for y in years]

    # true-size 0.9\columnwidth; height keeps the pre-change 405.8x130.2bp
    # aspect (0.3208) so the LaTeX layout does not move
    w_in = 0.9 * COLW_IN
    fig, ax = plt.subplots(figsize=(w_in, w_in * 0.3208))
    for a, b in [(2008, 2009), (2020, 2020), (2022, 2022)]:
        ax.axvspan(a - 0.4, b + 0.4, color="0.88", zorder=0)
    # legend labels are the arm letters only (caption defines R = revealed,
    # M = masked); the single row sits over the empty 2011-2017 high band
    ax.plot(xs, [yr_r[y] for y in years], "o-", ms=3, lw=1.1, color="#B3402A", label="R")
    ax.plot(xs, [yr_m[y] for y in years], "s-", ms=3, lw=1.1, color="#2A6EB3", label="M")
    ax.set_ylabel("bearish\nshare")  # two lines: the strip is shorter than the rotated one-liner
    ax.set_xticks(range(2005, 2026, 4))
    ax.set_xticks(range(2005, 2025, 1), minor=True)
    ax.set_yticks([0, 0.2, 0.4, 0.6])
    ax.set_ylim(0, 0.75)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.04),
              ncol=2, handlelength=1.5, columnspacing=1.2, handletextpad=0.5)
    savefig_exact(fig, "fig1_yearly_bearish", w_in, w_in * 0.3208)
    plt.close(fig)
    print("fig1:", {y: (round(yr_r[y], 3), round(yr_m[y], 3)) for y in ("2008", "2013", "2022")})


def fig2() -> None:
    dates = all_dates()
    calm = [d for d in dates if d[:4] in CALM_YEARS]
    fmap = fake_map(dates)
    w = load_arm("gemini-2.5-flash", "W")
    w_fake: dict[str, list[str]] = defaultdict(list)
    for td, xs in w.items():
        w_fake[fmap[td]].extend(xs)

    def share(by_date, sel):
        xs = [x for d in sel for x in by_date.get(d, [])]
        return sum(1 for x in xs if x == "-") / len(xs) if xs else float("nan")

    groups = {
        "true\ndate": (share(w, CRISIS), share(w, calm)),
        "fake\ndate": (share(w_fake, CRISIS), share(w_fake, calm)),
    }
    # true-size 0.5\columnwidth; height keeps the pre-change 238.4x170.5bp
    # aspect (0.7152) so the LaTeX layout does not move
    w_in = 0.5 * COLW_IN
    fig, ax = plt.subplots(figsize=(w_in, w_in * 0.7152))
    xpos = np.arange(2)
    width = 0.34
    ax.bar(xpos - width / 2, [g[0] for g in groups.values()], width,
           color="#B3402A", label="crisis")
    ax.bar(xpos + width / 2, [g[1] for g in groups.values()], width,
           color="#C8C8C8", label="calm")
    for i, (c, q) in enumerate(groups.values()):
        ax.annotate(f"{c - q:+.3f}", (i, max(c, q) + 0.02), ha="center")
    ax.set_xticks(xpos, list(groups))
    ax.set_xlim(-0.55, 1.45)  # keeps the "-0.057" annotation clear of the y-spine
    ax.set_ylabel("bearish share")
    ax.set_yticks([0, 0.3, 0.6])
    ax.set_ylim(0, 0.78)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.45, 0.98),
              ncol=2, handlelength=1.0, columnspacing=0.9, handletextpad=0.4)
    savefig_exact(fig, "fig2_transplant", w_in, w_in * 0.7152)
    plt.close(fig)
    print("fig2:", {k.replace(chr(10), " "): (round(v[0], 3), round(v[1], 3)) for k, v in groups.items()})


def fig3() -> None:
    # stage rents parsed from FM2_RESULTS.md table (itself generated by analyze_fm2.py)
    stages, rents = [], []
    import re
    for line in FM2.read_text().splitlines():
        if re.match(r"\| S\d ", line):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            stages.append(parts[0].split()[0])
            rents.append(float(parts[3]))
        if line.startswith("- Acc_R"):
            t2 = float(line.split("=")[1].split(",")[0])
    fig, ax = plt.subplots(figsize=(4.2, 2.2))
    xs = np.arange(len(stages) + 1)
    vals = rents + [t2]
    colors = ["#B3402A"] * len(rents) + ["#2A6EB3"]
    ax.bar(xs, vals, 0.55, color=colors)
    ax.axhline(0, color="0.3", lw=0.8)
    ax.set_xticks(xs, stages + ["T2 prod.\n(acc rent)"])
    ax.set_ylim(min(vals) - 0.035, max(vals) + 0.025)
    for x, v in zip(xs, vals):
        if v >= 0:
            ax.annotate(f"{v:+.3f}", (x, v + 0.005), ha="center", va="bottom", fontsize=8)
        else:
            ax.annotate(f"{v:+.3f}", (x, v - 0.005), ha="center", va="top", fontsize=8)
    ax.set_ylabel("R − M contamination rent")
    fig.savefig(FIGS / "fig3_rent_decay.pdf")
    fig.savefig(FIGS / "fig3_rent_decay.png")
    plt.close(fig)
    print("fig3:", dict(zip(stages + ["T2"], [round(v, 4) for v in vals])))


def fig4() -> None:
    """LAP heatmap: models (sorted by measured cutoff) x months. The collapse
    of each row from color to white IS the behaviorally effective cutoff; the
    right edge forms the 22-month staircase. Vendor-reported cutoffs = black ticks."""
    import json as _json
    from collections import defaultdict as _dd
    BENCH_DIR = REPO / "hindsight/outputs/bench"
    # rows = real-memory models (guessing-tier excluded via lap_at_chance),
    # ordered by measured cutoff (top -> bottom). measured = row json LAP
    # collapse month; vendor claims live in bench_registry (official only).
    models = sorted(
        ((m["key"],
          _json.loads((BENCH_DIR / m["key"] / f"{m['key']}_row.json")
                      .read_text())["LAP"]["empirical_cutoff"],
          m["fig4_claim"], m["tex"])
         for m in BENCH_MODELS if not m["lap_at_chance"]),
        key=lambda t: t[1])

    def frac_year(ym: str) -> float:
        return int(ym[:4]) + (int(ym[5:7]) - 0.5) / 12

    # month grid = the panel's 258 dates, taken from the first model
    rows = []
    month_axis = None
    for name, measured, claimed, disp in models:
        fp = BENCH_DIR / name / "lap_probe_results.jsonl"
        cnt = _dd(lambda: _dd(int))
        for l in fp.read_text().splitlines():
            if l.strip():
                r = _json.loads(l)
                cnt[r["decision_date"]][r["answer"]] += 1
        months = sorted(cnt)
        if month_axis is None:
            month_axis = [m[:7] for m in months]
        vals = []
        for d in months:
            c = cnt[d]
            n = sum(c.values())
            vals.append((c["up"] + c["down"]) / n if n else np.nan)
        rows.append(vals)
    M = np.array(rows, float)
    x0, x1 = frac_year(month_axis[0]) - 1 / 24, frac_year(month_axis[-1]) + 1 / 24

    # true-size 0.74\textwidth. Twelve 9pt label rows only fit inside the old
    # 111pt printed height by reclaiming every non-data band: the in-figure
    # legend is dropped (the caption already defines both tick types), the
    # tight-bbox pad is cropped 0.1->0.02in, and labels avoid tall parens.
    # Net: printed aspect preserved (0.2960 -> 0.2953).
    w_in = 0.74 * TEXTW_IN
    h_in = 1.53
    fig, ax = plt.subplots(figsize=(w_in, h_in))
    im = ax.imshow(M, aspect="auto", cmap="Blues", vmin=0, vmax=1,
                   extent=[x0, x1, len(models) - 0.5, -0.5], interpolation="nearest")
    # row separators
    for k in range(1, len(models)):
        ax.axhline(k - 0.5, color="white", lw=1.4)
    # measured cutoff: red tick at the row's collapse month; vendor claim: black tick
    for k, (name, measured, claimed, disp) in enumerate(models):
        ax.plot([frac_year(measured)] * 2, [k - 0.5, k + 0.5], color="#C1272D",
                lw=1.6, solid_capstyle="butt", zorder=4)
        if claimed:
            ax.plot([frac_year(claimed)] * 2, [k - 0.5, k + 0.5], color="0.15",
                    lw=1.4, ls=(0, (1, 1)), zorder=4)
    # paren-free cutoff month: "(" / ")" are the tallest glyphs at 9pt and
    # would force a taller row pitch than the digits/caps actually need
    labels = [f"{d} · {m}" for _, m, _, d in models]
    ax.set_yticks(range(len(models)), labels)
    ax.set_xticks(range(2005, 2027, 4))
    ax.tick_params(length=2, pad=1.5)
    ax.set_xlim(x0, x1)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.012)
    cb.set_label("LAP")
    cb.set_ticks([0, 0.5, 1])
    savefig_exact(fig, "fig4_lap_collapse", w_in, h_in)
    plt.close(fig)
    print("fig4: done (heatmap)")


def fig5() -> None:
    """E2 date-trigger effect vs parameter scale, colored by training generation.
    Open-weight rows at known (active) params; API rows in an undisclosed-size
    band. E2 + CI read from each model's frozen row json; panel/x-position/label
    from bench_registry; low-validity = schema compliance < 90%."""
    import json as _json
    BENCH_DIR = REPO / "hindsight/outputs/bench"

    def e2(m):
        r = _json.loads(
            (BENCH_DIR / m["key"] / f"{m['key']}_row.json").read_text())
        return (r["E2_date_trigger"]["est"], *r["E2_date_trigger"]["ci95"],
                r["VALID"]["sketch_rate"])

    open_rows = []  # (label, x pos B, E2, lo, hi, generation, low_validity)
    api_rows = []   # (label, slot, E2, lo, hi, generation)
    gated = []      # rows whose E2 is unidentified -> plotted as absent, not zero
    for m in BENCH_MODELS:
        f5 = m["fig5"]
        r = _json.loads(
            (BENCH_DIR / m["key"] / f"{m['key']}_row.json").read_text())
        if r["E2_date_trigger"].get("gated"):
            # An unidentified cell must not be drawn: a point at its estimate
            # would read as evidence, and omitting it silently would read as a
            # missing model. Record it so the caption can name it.
            gated.append(f5["label"])
            continue
        est, lo, hi, valid = e2(m)
        if f5["panel"] == "open":
            open_rows.append((f5["label"], f5["x"], est, lo, hi, m["gen"],
                              valid < 0.9))
        else:
            api_rows.append((f5["label"], f5["slot"], est, lo, hi, m["gen"]))
    api_rows.sort(key=lambda r: r[1])
    gen_color = {2024: "#5A9E5A", 2025: "#C9822B", 2026: "#B3402A"}

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(6.4, 2.5), sharey=True,
        gridspec_kw={"width_ratios": [3, 2], "wspace": 0.06})
    ax.axhline(0, color="0.4", lw=0.8)
    for label, p, e2, lo, hi, gen, low_valid in open_rows:
        c = gen_color[gen]
        mfc = "white" if low_valid else c
        ax.errorbar(p, e2, yerr=[[e2 - lo], [hi - e2]], fmt="o", ms=5,
                    color=c, markerfacecolor=mfc, capsize=2, lw=1.2)
        above = e2 >= 0 and "A3B" not in label and label not in ("3B", "27B")
        if label == "3B":       # low-validity outlier: label below to avoid clutter
            xy, va = (p, lo - 0.03), "top"
        elif label == "30B-A3B":  # 2025-gen null MoE: label below, clear of 35B-A3B
            xy, va = (p * 0.8, lo - 0.03), "top"
        elif "A3B" in label:
            xy, va = (p * 1.25, hi + 0.02), "bottom"
        else:
            xy, va = (p, hi + 0.03) if above else (p, lo - 0.03), "bottom" if above else "top"
        ax.annotate(label, xy, ha="center", va=va, fontsize=6.5, color=c)
    ax.set_xscale("log")
    ax.set_xticks([1, 3, 8, 27, 70], ["1B", "3B", "8B", "27B", "70B"])
    ax.set_xlim(0.6, 130)
    ax.set_ylim(-0.42, 0.62)
    ax.set_ylabel("E2 date-trigger effect")
    ax.set_xlabel("active parameters (open weights)")

    ax2.axhline(0, color="0.4", lw=0.8)
    for label, slot, e2, lo, hi, gen in api_rows:
        c = gen_color[gen]
        ax2.errorbar(slot, e2, yerr=[[e2 - lo], [hi - e2]], fmt="s", ms=5,
                     color=c, capsize=2, lw=1.2)
    ax2.set_xticks([r[1] for r in api_rows],
                   [r[0] for r in api_rows], rotation=40, ha="right", fontsize=6.5)
    ax2.set_xlim(-0.7, 7.7)
    ax2.set_xlabel("API models (size undisclosed)")
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=gen_color[g], marker="o", ls="", label=f"{g} generation")
               for g in (2024, 2025, 2026)]
    handles.append(Line2D([], [], color="0.4", marker="o", markerfacecolor="white",
                          ls="", label="low compliance (79%)"))
    ax.legend(handles=handles, frameon=False, fontsize=6.5, loc="upper right")
    fig.savefig(FIGS / "fig5_scale_generation.pdf")
    fig.savefig(FIGS / "fig5_scale_generation.png")
    plt.close(fig)
    print(f"fig5: done (E2 gated, not plotted: {gated or 'none'})")


if __name__ == "__main__":
    FIGS.mkdir(parents=True, exist_ok=True)
    todo = sys.argv[1:] or ["fig1", "fig2", "fig3", "fig4", "fig5"]
    for name in todo:
        globals()[name]()
    print("figures written to", FIGS)
