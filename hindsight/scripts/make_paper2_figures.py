#!/usr/bin/env python3
"""Paper-2 figures, generated from frozen row files (no hand-typed numbers).

  fig_st1.pdf     Section 7: coordinate contrasts (forest) + per-region memory (dumbbell)
  fig_ladder.pdf  Sections 6 / 9.1: paired recipe-vs-tier contrasts + seven-configuration dose-response
  fig_traces.pdf  Sections 5.1 / 9.2: episode retrieval in traces, recoverability vs trigger, corpus salience

Every plotted number is also written to figures/fig_data.json; `--check` fails if that
sidecar would change, which is the drift gate (PDF bytes carry timestamps and are not compared).
Designed for the svjour3 smallextended text width (338pt = 4.7in): single column, panels stacked.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from hindsight_paths import REPO  # noqa: E402
from bench_registry import MODELS  # noqa: E402
from analyze_bm2c import CONTROL_C, CONTROL_D, CONTROL_H, PANEL_F, CONTROL_I  # noqa: E402
from analyze_fm1 import CRISIS, CALM_YEARS, all_dates  # noqa: E402
import corpus_salience_instrument as csi  # noqa: E402
from make_think_table import NAME as THINK_NAME, ORDER as THINK_ORDER  # noqa: E402

H = REPO / "hindsight"
BENCH = H / "outputs/bench"
ST = H / "outputs/st1"
FIG = H / "paper2/latex/figures"
SIDECAR = FIG / "fig_data.json"
NOISE_FLOOR_PP = 16.2  # largest same-model replicate |E2 diff| (outputs/bench/NOISE_FLOOR.md)

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7, "axes.titlesize": 7.5, "axes.labelsize": 7, "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5, "legend.fontsize": 6, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5,
    "ytick.major.size": 2.5, "pdf.fonttype": 42, "ps.fonttype": 42,
})
C_RED, C_BLUE, C_BLUE_LT, C_GOLD, C_GREEN, C_GRAY, C_BAND, C_PURPLE = (
    "#9E2A2B", "#2B5C8F", "#8FB3DE", "#C87D20", "#3E7B52", "#6E737B", "#E9ECEF", "#6A4C93")
W = 4.7  # inches, svjour3 smallextended text width

DATA: dict = {}
SVG_DIR = H / "paper2/figures_export/svg"


def save(fig, name, pdf_dir=None):
    """Paper PDF (pdf_dir) plus an editable SVG: text stays text, shapes stay vector paths."""
    if pdf_dir is not None:
        fig.savefig(pdf_dir / f"{name}.pdf", bbox_inches="tight", metadata={"CreationDate": None})
    SVG_DIR.mkdir(parents=True, exist_ok=True)
    with plt.rc_context({"svg.fonttype": "none", "svg.hashsalt": "hindsightbench"}):
        fig.savefig(SVG_DIR / f"{name}.svg", bbox_inches="tight", metadata={"Date": None})


def style(ax, grid="x"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if grid:
        ax.grid(axis=grid, linestyle=":", linewidth=0.4, color="#CCCCCC", zorder=0)
    ax.set_axisbelow(True)


def label(ax, letter, title):
    ax.set_title(f"{letter}  {title}", loc="left", fontweight="bold", pad=4)


def pp(x):
    return None if x is None else round(100 * float(x), 1)


def bench_e2(key):
    r = json.loads((BENCH / key / f"{key}_row.json").read_text())["E2_date_trigger"]
    return pp(r["est"]), pp(r["ci95"][0]), pp(r["ci95"][1])


# ---------------------------------------------------------------- figure 1: ST-1
def fig_st1():
    rows = {t: json.loads((ST / t / f"{t}_st1_row.json").read_text())
            for t in ("deepseek-v4-flash", "gemini-2.5-flash", "gemini-2.5-flash-r2", "gemini-2.5-flash-pooled",
                      "claude-sonnet-5", "gpt-5.4-mini", "claude-haiku-4-5")}
    READ = [t for t in rows if rows[t].get("memory_gate", True)]  # rows below the memory gate get no estimand reading
    est = [("E2DL", "Joint key  E2$_{d\\ell}$"), ("E2", "Date alone  E2"), ("E2L", "Place alone  E2$_\\ell$"),
           ("INT", "Interaction  INT"), ("relocation", "Relocation"), ("interference", "Interference")]
    d = {"estimands": {}}
    for k, _ in est:
        d["estimands"][k] = {t: {kk: pp(v) for kk, v in rows[t][k].items()} for t in rows}
    gate = rows["deepseek-v4-flash"]["plus_share"]
    cities = sorted((c for c in rows["deepseek-v4-flash"]["lap"] if c != "ALL"), key=lambda c: rows["deepseek-v4-flash"]["lap"][c]["recall"])
    d["cities"] = {c: {t: {"recall": round(rows[t]["lap"][c]["recall"], 3), "hit": round(rows[t]["lap"][c]["hit"], 3)}
                       for t in ("deepseek-v4-flash", "gemini-2.5-flash-pooled", "claude-sonnet-5", "gpt-5.4-mini", "claude-haiku-4-5")} for c in cities}
    d["gated"] = [t for t in rows if t not in READ]
    d["gate"] = round(gate, 3)
    DATA["fig_st1"] = d

    fig = plt.figure(figsize=(W, 8.2))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.15, 0.7, 1.0], hspace=0.75)
    ax, cx, bx = fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
    d["gaps"] = {t: {arm: pp(rows[t]["gaps"][arm]["gap"]) for arm in ("M", "L", "D", "DL")} for t in rows}
    # (a) forest
    style(ax, "x"); label(ax, "a", "Coordinate contrasts, four readable rows")
    y = np.arange(len(est))[::-1]
    ax.axvline(0, color="#222", lw=0.7, ls="--", zorder=1)
    off = 0.3
    for i, (k, name) in enumerate(est):
        for t, col, mk, dy in (("deepseek-v4-flash", C_RED, "o", +off), ("gemini-2.5-flash-pooled", C_BLUE, "s", +off / 3),
                               ("claude-sonnet-5", C_PURPLE, "p", -off / 3), ("gpt-5.4-mini", C_GOLD, "^", -off)):
            e = rows[t][k]
            ax.plot([pp(e["lo"]), pp(e["hi"])], [y[i] + dy] * 2, color=col, lw=0.9, zorder=3)
            if "clo" in e:
                ax.plot([pp(e["clo"]), pp(e["chi"])], [y[i] + dy] * 2, color=col, lw=2.6, alpha=0.45, zorder=2)
            sig = e["lo"] > 0 or e["hi"] < 0
            ax.scatter([pp(e["pt"])], [y[i] + dy], marker=mk, s=22, color=col if sig else "white",
                       edgecolor=col, lw=1.0, zorder=4)
        for t in ("gemini-2.5-flash", "gemini-2.5-flash-r2"):
            ax.scatter([pp(rows[t][k]["pt"])], [y[i] + off / 3], marker="d", s=10, color="none", edgecolor=C_BLUE_LT, lw=0.7, zorder=3)
    ax.set_yticks(y); ax.set_yticklabels([n for _, n in est])
    ax.set_xlabel("Crisis$-$calm bearish-gap contrast (pp)")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([0], [0], color=C_RED, marker="o", ms=4, lw=0.9, label="DeepSeek v4-flash"),
                       Line2D([0], [0], color=C_BLUE, marker="s", ms=4, lw=0.9, label="Gemini 2.5 Flash, pooled"),
                       Line2D([0], [0], color=C_PURPLE, marker="p", ms=4, lw=0.9, label="Claude Sonnet 5"),
                       Line2D([0], [0], color=C_GOLD, marker="^", ms=4, lw=0.9, label="GPT-5.4-mini"),
                       Line2D([0], [0], color="none", marker="d", ms=3.5, markeredgecolor=C_BLUE_LT, label="Gemini replicates 1, 2"),
                       Line2D([0], [0], color=C_GRAY, lw=2.6, alpha=0.5, label="city-cluster 95% CI (thick)")],
              loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, frameon=False)
    # (b) 2x2 interaction plot: x = date absent/present, lines = place absent/present
    style(cx, "y"); label(cx, "b", "The 2$\\times$2 design as an interaction plot")
    for t, col, name in (("deepseek-v4-flash", C_RED, "DeepSeek"), ("gemini-2.5-flash-pooled", C_BLUE, "Gemini, pooled"),
                         ("claude-sonnet-5", C_PURPLE, "Sonnet 5"), ("gpt-5.4-mini", C_GOLD, "GPT-5.4-mini")):
        g = {arm: pp(rows[t]["gaps"][arm]["gap"]) for arm in ("M", "L", "D", "DL")}
        cx.plot([0, 1], [g["M"], g["D"]], color=col, lw=1.3, marker="o", ms=3.5, label=f"{name}: place absent (M, D)")
        cx.plot([0, 1], [g["L"], g["DL"]], color=col, lw=1.3, ls="--", marker="s", ms=3.5, markerfacecolor="white", label=f"{name}: place stated (L, DL)")
    cx.set_xticks([0, 1]); cx.set_xticklabels(["date absent", "date stated"]); cx.set_xlim(-0.35, 1.35)
    cx.set_ylabel("crisis$-$calm bearish\ngap (pp)")
    cx.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), frameon=False, ncol=2, fontsize=5.0)
    # (c) cities
    style(bx, "x"); label(bx, "c", "Outcome memory per region (LAP-ST)")
    yc = np.arange(len(cities))
    bx.axvspan(0, gate, color=C_BAND, zorder=0)
    bx.axvline(gate, color="#444", ls="--", lw=0.6, zorder=1)
    bx.text(gate - 0.01, -0.55, f"majority-class rate {gate:.3f}: hit rates must clear it", ha="right", va="top", fontsize=5.8, color="#444")
    bx.set_ylim(-1.0, len(cities) - 0.4)
    names = {"nyc": "New York City", "milan": "Lombardy (Milan)", "london": "Greater London", "madrid": "Madrid",
             "tokyo": "Tokyo", "melbourne": "Victoria (Melbourne)", "sydney": "New South Wales", "delhi": "Delhi",
             "hongkong": "Hong Kong", "singapore": "Singapore"}
    for i, c in enumerate(cities):
        a, g = rows["deepseek-v4-flash"]["lap"][c], rows["gemini-2.5-flash-pooled"]["lap"][c]
        o, h, sn = rows["gpt-5.4-mini"]["lap"][c], rows["claude-haiku-4-5"]["lap"][c], rows["claude-sonnet-5"]["lap"][c]
        rc = [a["recall"], g["recall"], o["recall"], h["recall"], sn["recall"]]
        bx.plot([min(rc), max(rc)], [yc[i]] * 2, color="#CCC", lw=1.0, zorder=2)
        bx.scatter([sn["recall"]], [yc[i]], color=C_PURPLE, marker="p", s=20, zorder=4)
        bx.scatter([sn["hit"]], [yc[i]], marker="p", s=12, color="none", edgecolor=C_PURPLE, lw=0.7, zorder=3)
        bx.scatter([a["recall"]], [yc[i]], color=C_RED, s=20, zorder=4)
        bx.scatter([g["recall"]], [yc[i]], color=C_BLUE, marker="s", s=18, zorder=4)
        bx.scatter([o["recall"]], [yc[i]], color=C_GOLD, marker="^", s=20, zorder=4)
        bx.scatter([h["recall"]], [yc[i]], color=C_GREEN, marker="D", s=14, zorder=4)
        bx.scatter([a["hit"]], [yc[i] + 0.24], marker="o", s=12, color="none", edgecolor=C_RED, lw=0.7, zorder=3)
        bx.scatter([g["hit"]], [yc[i] - 0.24], marker="s", s=12, color="none", edgecolor=C_BLUE, lw=0.7, zorder=3)
        bx.scatter([o["hit"]], [yc[i] + 0.24], marker="^", s=12, color="none", edgecolor=C_GOLD, lw=0.7, zorder=3)
        bx.scatter([h["hit"]], [yc[i] - 0.24], marker="D", s=10, color="none", edgecolor=C_GREEN, lw=0.7, zorder=3)
    bx.set_yticks(yc); bx.set_yticklabels([names[c] for c in cities])
    bx.set_xlim(0.0, 1.03); bx.set_xlabel("Recall (filled) and hit rate (open) on the realized 4-week direction")
    bx.legend(handles=[Line2D([0], [0], color="none", marker="o", markerfacecolor=C_RED, ms=4, label="DeepSeek"),
                       Line2D([0], [0], color="none", marker="s", markerfacecolor=C_BLUE, ms=4, label="Gemini (2 reps)"),
                       Line2D([0], [0], color="none", marker="p", markerfacecolor=C_PURPLE, ms=4, label="Sonnet 5"),
                       Line2D([0], [0], color="none", marker="^", markerfacecolor=C_GOLD, ms=4, label="GPT-5.4-mini"),
                       Line2D([0], [0], color="none", marker="D", markerfacecolor=C_GREEN, ms=3.5, label="Haiku 4.5 (gated)")],
              loc="upper center", bbox_to_anchor=(0.5, -0.2), frameon=False, ncol=5, fontsize=5.2)
    save(fig, "fig_st1", FIG)
    plt.close(fig)


# ---------------------------------------------------------------- figure 2: ladder
def fig_ladder():
    key = {r: k for ladder in (CONTROL_C, CONTROL_D, CONTROL_H, PANEL_F, CONTROL_I) for r, k, _, _ in ladder}
    pairs = [  # (label, start rung, end rung, extra rung)
        ("Tülu 3 70B, FP8 → AWQ-INT4\n(one checkpoint, two tiers)", "T3", "F3", None),
        ("Qwen3-30B-A3B, 2025-04 → 2507 Thinking\n(one corpus, two recipes; boundary)", "D-ref", "D2", "D1"),
        ("Llama 3.1 → 3.3 70B, AWQ-INT4\n(one corpus, two recipes)", "C-ref", "C", None),
        ("Llama 3.1 → 3.3 70B, FP8\n(same pair, other tier)", "H2", "H1", None),
        ("Tülu 3 SFT, DPO, FP8\n(two stages, no reflex)", "T1", "T2", None),
        ("Hermes 3 (FP8), R1-distill (AWQ)\n(other recipes on the base)", "F2", "F1", None),
    ]
    d = {"pairs": [], "dose": {}, "noise_floor_pp": NOISE_FLOOR_PP}
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(W, 5.6), gridspec_kw={"height_ratios": [1.1, 1.0], "hspace": 0.6})
    style(ax, "x"); label(ax, "a", "Recipe contrasts against tier contrasts (E2)")
    ax.axvspan(-NOISE_FLOOR_PP, NOISE_FLOOR_PP, color=C_BAND, zorder=0)
    ax.axvline(0, color="#222", lw=0.7, ls="--", zorder=1)
    ax.text(-NOISE_FLOOR_PP + 0.5, -0.7, f"same-model replicate floor ±{NOISE_FLOOR_PP} pp", ha="left", va="top", fontsize=5.8, color="#555")
    ax.set_ylim(-1.1, len(pairs) - 0.5)
    y = np.arange(len(pairs))[::-1]
    for i, (lab, a, b, extra) in enumerate(pairs):
        ea, eb = bench_e2(key[a]), bench_e2(key[b])
        delta = round(eb[0] - ea[0], 1)
        col = C_RED if abs(delta) > NOISE_FLOOR_PP else C_GRAY
        ax.plot([ea[0], eb[0]], [y[i]] * 2, color=col, lw=1.6, zorder=3)
        ax.scatter([ea[0]], [y[i]], color="white", edgecolor=col, s=26, lw=1.1, zorder=4)
        ax.scatter([eb[0]], [y[i]], color=col, s=30, zorder=5)
        if abs(delta) > 10:
            ax.annotate("", xy=(eb[0], y[i]), xytext=(ea[0], y[i]), arrowprops=dict(arrowstyle="->", color=col, lw=1.4), zorder=4)
        ax.text(max(ea[0], eb[0]) + 1.5, y[i], f"{delta:+.1f} pp", va="center", fontsize=6.2, color=col,
                fontweight="bold" if col == C_RED else "normal")
        rec = {"label": lab, "from": a, "to": b, "e2_from": ea, "e2_to": eb, "delta_pp": delta}
        if extra:
            ee = bench_e2(key[extra]); rec["extra"] = {"rung": extra, "e2": ee}
            ax.scatter([ee[0]], [y[i]], marker="d", s=18, color="white", edgecolor=col, lw=0.9, zorder=5)
        d["pairs"].append(rec)
    ax.set_yticks(y); ax.set_yticklabels([p[0] for p in pairs], fontsize=6.2)
    ax.set_xlim(-20, 50); ax.set_xlabel("Date-trigger effect E2 (pp); open = first checkpoint, filled = second")
    # (b) dose-response
    style(bx, "x"); label(bx, "b", "Seven serving configurations, one checkpoint, one box")
    order = ["I1", "I3", "I7", "I6", "I5", "I4", "I2"]
    names = {"I1": "BF16, run 1 (reference)", "I3": "BF16, run 2", "I7": "BF16 weights, fp16 activations",
             "I6": "block-FP8 (TP=2)", "I5": "INT8 W8A8", "I4": "GPTQ-INT4 (TP=2)", "I2": "AWQ-INT4"}
    vals = {r: bench_e2(key[r]) for r in order}
    d["dose"] = {r: {"name": names[r], "e2": vals[r]} for r in order}
    run1, run2 = vals["I1"][0], vals["I3"][0]
    pooled = round((run1 + run2) / 2, 1)
    d["dose_pooled_reference_pp"] = pooled
    yb = np.arange(len(order))[::-1]
    bx.axvspan(min(run1, run2), max(run1, run2), color="#FFF3CD", alpha=0.7, zorder=0)
    bx.axvline(pooled, color=C_GOLD, ls="-.", lw=1.0, zorder=2)
    bx.axvline(0, color="#222", lw=0.7, ls="--", zorder=1)
    bx.text(54, 0.9, f"pooled BF16 reference {pooled:+.1f} pp\nrun 1 to run 2 spans {abs(run1-run2):.1f} pp", ha="right", va="center", fontsize=5.8, color="#854D0E")
    for i, r in enumerate(order):
        e, lo, hi = vals[r]
        col = C_GRAY if r in ("I1", "I3") else (C_GOLD if r == "I7" else C_BLUE)
        bx.plot([lo, hi], [yb[i]] * 2, color=col, lw=1.0, zorder=3)
        bx.scatter([e], [yb[i]], color=col if lo > 0 else "white", edgecolor=col, s=24, lw=1.0, zorder=4)
    bx.set_yticks(yb); bx.set_yticklabels([names[r] for r in order], fontsize=6.2)
    bx.set_xlim(-22, 55); bx.set_xlabel("Date-trigger effect E2 (pp, 95% date-level CI)")
    DATA["fig_ladder"] = d
    save(fig, "fig_ladder", FIG)
    plt.close(fig)


# ---------------------------------------------------------------- figure 3: traces, dissociation, salience
def fig_traces():
    rows = {r["model"]: r for r in json.loads((H / "outputs/review/think_traces/think_traces_rows.json").read_text())}
    order = [k for k in THINK_ORDER if k in rows]
    d = {"traces": {k: {"name": THINK_NAME[k], "D": round(rows[k]["D_vocab_c"], 3), "M": round(rows[k]["M_vocab_c"], 3)} for k in order}}
    # leaderboard: REC (pre, year accuracy) vs E2, sized by LAP pre
    lead = []
    for m in MODELS:
        p = BENCH / m["key"] / f"{m['key']}_row.json"
        if not p.exists():
            continue
        r = json.loads(p.read_text())
        if r["E2_date_trigger"].get("gated") or r["REC"]["pre"].get("year") is None or m["rec"] != "probe":
            continue
        lead.append({"name": m["tex"].replace("\\", ""), "gen": int(m["gen"]), "rec_year_pct": round(100 * r["REC"]["pre"]["year"], 1),
                     "e2_pp": pp(r["E2_date_trigger"]["est"]), "lap_pre": round(r["LAP"]["pre_mean"], 3)})
    d["leaderboard"] = lead
    # corpus salience
    R = csi.rates(); dates = all_dates()
    S = {dd: R[csi.month_phrase(dd)]["crisis"] for dd in dates if csi.month_phrase(dd) in R}
    md = (H / "outputs/review/corpus_salience/CORPUS_SALIENCE.md").read_text()
    rho = [float(m.group(1)) for m in re.finditer(r"^\| [a-z0-9.\-]+ \| ([+-]\d\.\d+) \|", md, re.M)]
    d["salience"] = {"n_months": len(S), "crisis_mean": round(float(np.mean([S[x] for x in CRISIS if x in S])), 3),
                     "calm_mean": round(float(np.mean([S[x] for x in S if x[:4] in CALM_YEARS])), 3),
                     "n_rows": len(rho), "rho_median": round(float(np.median(rho)), 3),
                     "rho_sig": sum(1 for _ in re.finditer(r"^\| [a-z0-9.\-]+ \| [+-]\d\.\d+ \| (0\.0[0-4]\d*|0\.00\d+|[0-9.]+e-\d+) \|", md, re.M)),
                     "top": sorted(((x[:7], round(S[x], 2)) for x in S), key=lambda t: -t[1])[:3]}
    DATA["fig_traces"] = d

    fig = plt.figure(figsize=(W, 7.0))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1.0], hspace=0.5, wspace=0.55)
    ax = fig.add_subplot(gs[0, 0]); bx = fig.add_subplot(gs[0, 1]); cx = fig.add_subplot(gs[1, :])
    # (a) traces
    style(ax, "x"); label(ax, "a", "Trace names the episode")
    ya = np.arange(len(order))[::-1]
    for i, k in enumerate(order):
        ax.plot([100 * rows[k]["M_vocab_c"], 100 * rows[k]["D_vocab_c"]], [ya[i]] * 2, color="#CCC", lw=1.2, zorder=2)
    ax.scatter([100 * rows[k]["M_vocab_c"] for k in order], ya, color="white", edgecolor=C_BLUE, s=20, lw=1.0, zorder=4, label="masked (M)")
    ax.scatter([100 * rows[k]["D_vocab_c"] for k in order], ya, color=C_RED, s=22, zorder=4, label="dated (D)")
    short = lambda n: n.replace("\\quad ", "      ").replace("Qwen3-30B-A3B Thinking 2507", "Qwen3-30B Thinking").replace("Qwen3-30B-A3B (2025-04 release)", "Qwen3-30B (2025-04)").replace("Qwen3.6-35B-A3B", "Qwen3.6-35B").replace("fp16 activations", "fp16 act").replace("second run", "run 2")
    ax.set_yticks(ya); ax.set_yticklabels([short(THINK_NAME[k]) for k in order], fontsize=5.4)
    ax.set_xlim(-3, 80); ax.set_xlabel("Crisis-date cells naming\nthe date's episode (%)")
    ax.legend(loc="lower right", frameon=False)
    # (b) REC vs E2
    style(bx, "both"); label(bx, "b", "Recoverable vs. triggered")
    bx.axhline(0, color="#333", ls="--", lw=0.6, zorder=1)
    gc = {2026: C_RED, 2025: C_GOLD, 2024: C_GREEN}
    for m in lead:
        bx.scatter([m["rec_year_pct"]], [m["e2_pp"]], s=10 + 50 * m["lap_pre"], color=gc[m["gen"]], alpha=0.75, edgecolor="#222", lw=0.4, zorder=4)
        dx, dy = {"Llama 3.1 8B": (3, -7), "Llama 3.1 70B": (3, -7), "Qwen3.6-27B": (-3, -8)}.get(m["name"], (3, 2))
        bx.annotate(m["name"], (m["rec_year_pct"], m["e2_pp"]), xytext=(dx, dy), textcoords="offset points", fontsize=5.2)
    bx.set_xlabel("Date recoverability REC,\npre-cutoff year accuracy (%)"); bx.set_ylabel("Date-trigger effect E2 (pp)")
    bx.set_xlim(-5, 110)
    bx.legend(handles=[plt.Line2D([0], [0], color="none", marker="o", markerfacecolor=c, ms=5, label=f"{g} generation") for g, c in gc.items()],
              loc="center right", bbox_to_anchor=(1.02, 0.3), frameon=False, title="size = LAP recall", title_fontsize=5.5)
    # (c) salience series
    style(cx, "y"); label(cx, "c", "Corpus salience of each month (Dolma 1.7) against the crisis set")
    xs = np.arange(len(dates)); ys = [S.get(x, np.nan) for x in dates]
    cx.plot(xs, ys, color=C_GRAY, lw=0.8, zorder=2)
    cidx = [i for i, x in enumerate(dates) if x in CRISIS]
    cx.scatter(cidx, [ys[i] for i in cidx], color=C_RED, s=14, zorder=4, label="preregistered crisis months")
    calm = [i for i, x in enumerate(dates) if x[:4] in CALM_YEARS]
    cx.scatter(calm, [ys[i] for i in calm], color=C_BLUE, s=6, zorder=3, label="calm years")
    ticks = [i for i, x in enumerate(dates) if x[5:7] == "01" and int(x[:4]) % 2 == 1]
    cx.set_xticks(ticks); cx.set_xticklabels([dates[i][:4] for i in ticks])
    cx.set_ylabel("share of windows with\ncrisis vocabulary, $S_T$")
    cx.legend(loc="upper right", frameon=False)
    cx.set_ylim(0, 0.42)
    ins = cx.inset_axes([0.06, 0.40, 0.36, 0.44]); style(ins, None)
    ins.hist(rho, bins=np.arange(-0.2, 0.26, 0.04), color=C_BAND, edgecolor="#555", lw=0.5)
    ins.axvline(0, color="#222", lw=0.6, ls="--")
    ins.set_title(f"Spearman($h_t$, $S_T$) per row, n={len(rho)}, median {np.median(rho):+.2f}", fontsize=5.4)
    ins.tick_params(labelsize=5)
    save(fig, "fig_traces", FIG)
    plt.close(fig)


# ---------------------------------------------------------------- figure 4: the coordinate mechanism
def fig_st_map():
    """Mechanism figure for the space coordinate.
    (a) schematic: what each part of the (date, place) key does to the same snapshot, with the measured effects;
    (b) 3D: per-(region, month) change in bearish share for three interventions, pooled over the readable rows;
    (c) memory against reflex for every model audited on both panels;
    (d) the false-place contrasts: relocation and interference per readable row."""
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    from build_st_panel import ONSETS
    READ = ["deepseek-v4-flash", "gemini-2.5-flash-pooled", "claude-sonnet-5", "gpt-5.4-mini"]
    rowj = {t: json.loads((ST / t / f"{t}_st1_row.json").read_text()) for t in READ + ["claude-haiku-4-5"]}
    cities = sorted(ONSETS, key=lambda c: (ONSETS[c][0], c))
    months = [f"{y}-{m:02d}" for y in (2020, 2021, 2022) for m in range(1, 13)][2:33]
    short = {"nyc": "New York", "milan": "Lombardy", "madrid": "Madrid", "london": "London", "delhi": "Delhi",
             "hongkong": "Hong Kong", "melbourne": "Victoria", "sydney": "NSW", "tokyo": "Tokyo", "singapore": "Singapore"}
    cache = {}

    def share(row, arm, node):
        k = (row, arm, node)
        if k not in cache:
            vals = []
            for f in (ST / row / arm).glob(f"rep*/{node}/01_sketches_valid.json"):
                d = [x["direction"] for x in json.loads(f.read_text()) if x.get("direction") in ("+", "-")]
                if d:
                    vals.append(d.count("-") / len(d))
            cache[k] = float(np.mean(vals)) if vals else np.nan
        return cache[k]

    def diff(a1, a0, node):
        ds = [share(r, a1, node) - share(r, a0, node) for r in READ]
        ds = [x for x in ds if not np.isnan(x)]
        return 100 * float(np.mean(ds)) if ds else np.nan

    slabs = [("D", "M", "date stated"), ("L", "M", "place stated"), ("DL", "M", "date and place stated"), ("S", "D", "false place added")]
    grids = {}
    for a1, a0, _ in slabs:
        grids[a1 + "-" + a0] = np.array([[diff(a1, a0, f"{c}_{m}") for m in months] for c in cities])
    mar = {k: float(np.nanmean(g[:, 0])) for k, g in grids.items()}
    rest = {k: float(np.nanmean(np.abs(g[:, 1:]))) for k, g in grids.items()}

    # memory vs reflex, both panels
    pairs = [("deepseek-v4-flash", "deepseek-v4-flash", "DeepSeek"), ("gemini-2.5-flash", "gemini-2.5-flash-pooled", "Gemini Flash"),
             ("claude-sonnet-5", "claude-sonnet-5", "Sonnet 5"), ("gpt-5.4-mini", "gpt-5.4-mini", "GPT-5.4-mini"),
             ("claude-haiku-4-5", "claude-haiku-4-5", "Haiku 4.5")]
    MACRO_GATE = 0.655
    macro = []
    for m in MODELS:
        pth = BENCH / m["key"] / f"{m['key']}_row.json"
        if not pth.exists():
            continue
        r = json.loads(pth.read_text())
        hit, e2 = r["LAP"].get("recall_hit_rate"), r["E2_date_trigger"]
        if hit is None or e2.get("gated") or e2.get("est") is None:
            continue
        macro.append({"key": m["key"], "name": m["tex"].replace("\\", ""), "x": round(100 * (hit - MACRO_GATE), 1),
                      "y": pp(e2["est"]), "sig": e2["ci95"][0] > 0 or e2["ci95"][1] < 0})
    st = []
    for mk, tag, nm in pairs:
        r = rowj[tag]
        e = r["E2DL"]
        st.append({"tag": tag, "macro_key": mk, "name": nm, "x": round(100 * (r["lap"]["ALL"]["hit"] - r["plus_share"]), 1),
                   "y": pp(e["pt"]), "sig": e["lo"] > 0 or e["hi"] < 0, "gate": bool(r["memory_gate"])})
    reloc = {t: {k: {kk: pp(v) for kk, v in rowj[t][k].items()} for k in ("relocation", "interference")} for t in READ}
    # per-row, region-averaged March 2020 effects (vendor dots on the trigger panels)
    def row_mar(row, a1, a0):
        v = [share(row, a1, f"{c}_{months[0]}") - share(row, a0, f"{c}_{months[0]}") for c in cities]
        v = [x for x in v if not np.isnan(x)]
        return round(100 * float(np.mean(v)), 1) if v else None
    vendor_mar = {r: {"D-M": row_mar(r, "D", "M"), "L-M": row_mar(r, "L", "M")} for r in READ}
    VNAME = {"deepseek-v4-flash": "DeepSeek", "gemini-2.5-flash-pooled": "Gemini", "claude-sonnet-5": "Sonnet 5", "gpt-5.4-mini": "GPT-mini"}
    VMARK = {"deepseek-v4-flash": "o", "gemini-2.5-flash-pooled": "s", "claude-sonnet-5": "p", "gpt-5.4-mini": "^"}
    ticks6 = [0, 12, 24]

    def draw_trigger(ax_, key, title, sub, col, big=True):
        prof_ = np.nanmean(grids[key], axis=0)
        xs_ = np.arange(len(months))
        other = prof_[1:]
        lo_, hi_ = float(np.nanmin(other)), float(np.nanmax(other))
        ax_.axhspan(lo_, hi_, color="#ECEEF1", zorder=0)
        ax_.text(len(months) - 0.6, hi_ + 0.6, "range of the\nother 30 months", ha="right", va="bottom", fontsize=5.2, color="#6E737B")
        ax_.axhline(0, color="#333", lw=0.6, zorder=1)
        colors_ = ["#C9CDD2"] * len(months); colors_[0] = col
        ax_.bar(xs_, prof_, 0.8, color=colors_, lw=0, zorder=2)
        ax_.bar([0], [prof_[0]], 1.1, color=col, lw=0, zorder=3)
        for r in READ:
            v = vendor_mar[r][key]
            if v is not None:
                ax_.scatter([-1.05], [v], marker=VMARK[r], s=13, color="white", edgecolor="#222", lw=0.6, zorder=4, clip_on=False)
        ax_.text(1.2, max(prof_[0], hi_) + 2.0, f"{prof_[0]:+.0f} pp", ha="left", va="bottom",
                 fontsize=10 if big else 8, fontweight="bold", color=col)
        ax_.text(1.2, max(prof_[0], hi_) + 0.2, "March 2020", ha="left", va="top", fontsize=5.6, color=col)
        ax_.set_title(title, loc="left", fontweight="bold", fontsize=8.5, pad=12, color=col)
        ax_.text(0, 1.015, sub, transform=ax_.transAxes, fontsize=6, color="#444", va="bottom")
        ax_.set_xlim(-1.7, len(months) - 0.2); ax_.set_ylim(-20, 32)
        ax_.set_xticks(ticks6); ax_.set_xticklabels([months[t] for t in ticks6], fontsize=6)
        for sp in ("top", "right"):
            ax_.spines[sp].set_visible(False)
        ax_.tick_params(labelsize=6)
        return prof_[0], lo_, hi_

    def draw_ridgeline(bx_):
        ribbons_ = [("D-M", "date stated", C_RED), ("DL-M", "date and place\nstated", C_PURPLE),
                    ("L-M", "place stated", C_BLUE), ("S-D", "false place\nadded to the date", C_GOLD)]
        xs_ = np.arange(len(months)); step_ = 22.0
        bx_.axvspan(-0.5, 0.5, color="#FBE3D6", zorder=0)
        bx_.text(0, len(ribbons_) * step_ + 2, "March 2020: global onset", ha="left", va="bottom", fontsize=5.4, color=C_RED, fontweight="bold")
        cs_ = [months.index(m) for m in ("2022-05", "2022-09")]
        bx_.axvspan(cs_[0] - 0.5, cs_[1] + 0.5, color="#E7F0FA", zorder=0)
        bx_.text((cs_[0] + cs_[1]) / 2, len(ribbons_) * step_ + 2, "calm months", ha="center", va="bottom", fontsize=5.4, color=C_BLUE)
        for ri, (k, lab, col) in enumerate(ribbons_):
            base = (len(ribbons_) - 1 - ri) * step_
            z = np.nanmean(grids[k], axis=0)
            bx_.axhline(base, color="#BBB", lw=0.5, zorder=1)
            bars_ = bx_.bar(xs_, z, 0.82, bottom=base, color=col, zorder=3, lw=0)
            for b_, v in zip(bars_, z):
                b_.set_alpha(0.95 if v >= 10 else (0.55 if v >= 0 else 0.25))
            bx_.text(-1.2, base + 2, lab, ha="right", va="center", fontsize=5.8, color=col, fontweight="bold")
            reg = grids[k][:, 0]; n_up = int(np.sum(reg >= 10)); ytop = base + max(z[0], 15.0)
            bx_.text(0.75, ytop - 1.0, f"{z[0]:+.0f} pp", ha="left", va="top", fontsize=6.2, color=col, fontweight="bold",
                     bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.85))
            bx_.text(0.75, ytop - 6.5, f"{n_up}/10 regions ≥ +10", ha="left", va="top", fontsize=4.8, color=col)
        bx_.set_xlim(-0.7, len(months) - 0.3); bx_.set_ylim(-step_ * 0.7, len(ribbons_) * step_ + 8)
        bx_.set_yticks([]); tk = [0, 6, 12, 18, 24, 30]
        bx_.set_xticks(tk); bx_.set_xticklabels([months[t] for t in tk], fontsize=5.6)
        for sp in ("top", "right", "left"):
            bx_.spines[sp].set_visible(False)
        bx_.plot([len(months) - 0.2] * 2, [0, 20], color="#333", lw=0.8, clip_on=False)
        bx_.text(len(months) + 0.1, 10, "20 pp", fontsize=5.2, va="center", rotation=90)
        bx_.text(len(months) / 2, -step_ * 0.62, "each bar: one month, averaged over ten regions and the four rows above the memory gate",
                 ha="center", fontsize=5.0, color="#555", style="italic")

    def trigger_legend(ax_):
        from matplotlib.lines import Line2D
        ax_.legend(handles=[Line2D([0], [0], color="none", marker=VMARK[r], markerfacecolor="white", markeredgecolor="#222", ms=4, label=VNAME[r]) for r in READ],
                   loc="lower right", frameon=False, fontsize=5.2, ncol=2, title="each vendor, March 2020", title_fontsize=5.2)

    DATA["fig_st_mech"] = {"rows_pooled": READ, "cities": cities, "months": months,
                           "mar2020_mean_pp": {k: round(v, 1) for k, v in mar.items()},
                           "other_months_mean_abs_pp": {k: round(v, 1) for k, v in rest.items()},
                           "grids": {k: [[None if np.isnan(x) else round(float(x), 1) for x in r] for r in g] for k, g in grids.items()},
                           "memory_reflex_macro": macro, "memory_reflex_st": st, "false_place": reloc,
                           "vendor_mar2020": vendor_mar}

    fig = plt.figure(figsize=(W, 8.2))
    gs = fig.add_gridspec(3, 2, height_ratios=[0.95, 1.2, 1.15], hspace=0.5, wspace=0.42)

    # ---------- (a) schematic
    ax = fig.add_subplot(gs[0, :]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_title("a  One snapshot, three keys", loc="left", fontweight="bold", fontsize=7.5, pad=2)
    lanes = [
        (0.80, C_RED, "date\nMarch 2020", "retrieves the\nglobal episode", f"{mar['D-M']:+.0f} pp bearish in March 2020;\nflat in every other month"),
        (0.48, C_BLUE, "place\nLombardy", "a place spans every\nperiod: no episode", f"{mar['L-M']:+.0f} pp in March 2020;\nflat everywhere"),
        (0.16, C_GOLD, "date +\nfalse place", "moves the episode to\nthe asserted place",
         f"{reloc['deepseek-v4-flash']['relocation']['pt']:+.1f} and {reloc['claude-sonnet-5']['relocation']['pt']:+.1f} pp on its onset months\n(2 of 4 rows); true months kept"),
    ]

    def box(x, y, w, h, fc, ec, txt, color="#111", fs=5.6, bold=False):
        ax.add_patch(FancyBboxPatch((x, y - h / 2), w, h, boxstyle="round,pad=0.006,rounding_size=0.02", fc=fc, ec=ec, lw=0.8))
        ax.text(x + w / 2, y, txt, ha="center", va="center", fontsize=fs, color=color, fontweight="bold" if bold else "normal", linespacing=1.15)

    def arrow(x0, x1, y, col="#444"):
        ax.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle="-|>", mutation_scale=7, lw=0.8, color=col))

    for y, col, key, mech, eff in lanes:
        box(0.0, y, 0.105, 0.22, "#F1F3F5", "#ADB5BD", "same\nsnapshot", fs=5.3)
        ax.text(0.119, y, "+", ha="center", va="center", fontsize=7, color="#555")
        box(0.132, y, 0.128, 0.24, col, col, key, color="white", bold=True, fs=5.1)
        arrow(0.262, 0.292, y)
        box(0.297, y, 0.06, 0.22, "#212529", "#212529", "LLM", color="white", bold=True, fs=5.4)
        arrow(0.362, 0.392, y)
        box(0.397, y, 0.235, 0.26, "white", col, mech, color=col, fs=5.4)
        arrow(0.637, 0.667, y, col)
        ax.text(0.672, y, eff, ha="left", va="center", fontsize=5.3, color="#111", linespacing=1.15)

    # ---------- (b) the trigger pair: date (left) against place (right), same scale
    gsb = gs[1, :].subgridspec(1, 2, wspace=0.12)
    bl = fig.add_subplot(gsb[0]); br = fig.add_subplot(gsb[1], sharey=bl)
    draw_trigger(bl, "D-M", "b  The date is the trigger", "date stated minus masked", C_RED)
    draw_trigger(br, "L-M", "The place alone is not", "place stated minus masked", C_BLUE)
    bl.set_ylabel("change in bearish share (pp)", fontsize=6)
    plt.setp(br.get_yticklabels(), visible=False)
    trigger_legend(br)

    # ---------- (c) memory vs reflex
    cx = fig.add_subplot(gs[2, 0]); style(cx, "both")
    cx.set_title("c  Memory is not the reflex", loc="left", fontweight="bold", fontsize=7.5, pad=3)
    cx.axhline(0, color="#333", lw=0.6, ls="--"); cx.axvline(0, color="#333", lw=0.6, ls="--")
    cx.axvspan(-40, 0, color=C_BAND, zorder=0)
    for m in macro:
        cx.scatter([m["x"]], [m["y"]], s=14, marker="o", color=C_GRAY if not m["sig"] else C_RED, alpha=0.55, lw=0, zorder=2)
    mk = {m["key"]: m for m in macro}
    for p_ in st:
        m = mk.get(p_["macro_key"])
        if m:
            cx.plot([m["x"], p_["x"]], [m["y"], p_["y"]], color="#999", lw=0.6, zorder=1)
        cx.scatter([p_["x"]], [p_["y"]], s=26, marker="D", zorder=4,
                   color=(C_BLUE if p_["sig"] else "white") if p_["gate"] else "white",
                   edgecolor=C_BLUE if p_["gate"] else C_GRAY, lw=0.9)
        cx.annotate(p_["name"], (p_["x"], p_["y"]), xytext=(3, -6 if p_["name"] in ("GPT-5.4-mini",) else 3), textcoords="offset points", fontsize=4.9)
    cx.text(36, -12, "memory,\nno reflex", fontsize=5.3, ha="center", color="#333", style="italic")
    cx.text(30, 38, "memory\nand reflex", fontsize=5.3, ha="center", color="#333", style="italic")
    cx.text(-20, 38, "below the\nmemory gate", fontsize=5.3, ha="center", color="#555", style="italic")
    cx.set_xlim(-30, 45); cx.set_ylim(-14, 46)
    cx.set_xlabel("outcome recall above the majority rate (pp)", fontsize=5.8)
    cx.set_ylabel("date trigger (pp)", fontsize=5.8)
    from matplotlib.lines import Line2D
    cx.legend(handles=[Line2D([0], [0], color="none", marker="o", markerfacecolor=C_RED, alpha=0.6, ms=4, label="macro panel (15 models)"),
                       Line2D([0], [0], color="none", marker="D", markerfacecolor=C_BLUE, markeredgecolor=C_BLUE, ms=4, label="sensing panel, joint key"),
                       Line2D([0], [0], color="#999", lw=0.6, label="same model, two panels")],
              loc="upper center", bbox_to_anchor=(0.5, -0.24), frameon=False, fontsize=4.9, ncol=1)

    # ---------- (d) false place
    dx = fig.add_subplot(gs[2, 1]); style(dx, "y")
    dx.set_title("d  A false place moves the episode", loc="left", fontweight="bold", fontsize=7.5, pad=3)
    names = {"deepseek-v4-flash": "DeepSeek", "gemini-2.5-flash-pooled": "Gemini", "claude-sonnet-5": "Sonnet 5", "gpt-5.4-mini": "GPT-mini"}
    xs = np.arange(len(READ)); w_ = 0.36
    for k, off, col, lab in (("relocation", -w_ / 2, C_GOLD, "asserted place's onset months (relocation)"),
                             ("interference", +w_ / 2, C_GRAY, "true place's onset months (interference)")):
        pts = [reloc[t][k]["pt"] for t in READ]; lo = [reloc[t][k]["lo"] for t in READ]; hi = [reloc[t][k]["hi"] for t in READ]
        sig = [(l > 0 or h < 0) for l, h in zip(lo, hi)]
        dx.bar(xs + off, pts, w_, color=[col if s else "white" for s in sig], edgecolor=col, lw=1.0, label=lab, zorder=3)
        dx.errorbar(xs + off, pts, yerr=[np.array(pts) - np.array(lo), np.array(hi) - np.array(pts)], fmt="none", ecolor="#333", lw=0.6, capsize=1.5, zorder=4)
    dx.axhline(0, color="#333", lw=0.6)
    dx.set_xticks(xs); dx.set_xticklabels([names[t] for t in READ], fontsize=5.6)
    dx.set_ylabel("change vs. date alone (pp)", fontsize=5.8)
    dx.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), frameon=False, fontsize=4.9, ncol=1)
    dx.set_ylim(-14, 24)

    save(fig, "fig_st_map", FIG)
    plt.close(fig)

    # standalone exports: the trigger pair and the four-intervention calendar ridgeline
    EXP = H / "paper2/figures_export"; EXP.mkdir(parents=True, exist_ok=True)
    f2, (l2, r2) = plt.subplots(1, 2, figsize=(W, 2.4), sharey=True, gridspec_kw={"wspace": 0.12})
    draw_trigger(l2, "D-M", "The date is the trigger", "date stated minus masked", C_RED)
    draw_trigger(r2, "L-M", "The place alone is not", "place stated minus masked", C_BLUE)
    l2.set_ylabel("change in bearish share (pp)", fontsize=6)
    trigger_legend(r2)
    for ext in ("pdf", "png"):
        f2.savefig(EXP / f"fig_trigger_pair.{ext}", bbox_inches="tight", dpi=300, metadata={"CreationDate": None} if ext == "pdf" else None)
    save(f2, "fig_trigger_pair")
    plt.close(f2)
    f3, a3 = plt.subplots(figsize=(W, 2.7))
    draw_ridgeline(a3)
    a3.set_title("Where on the calendar each key moves the judgment", loc="left", fontweight="bold", fontsize=7.5, pad=10)
    for ext in ("pdf", "png"):
        f3.savefig(EXP / f"fig_calendar_ridgeline.{ext}", bbox_inches="tight", dpi=300, metadata={"CreationDate": None} if ext == "pdf" else None)
    save(f3, "fig_calendar_ridgeline")
    plt.close(f3)


def main():
    check = "--check" in sys.argv
    FIG.mkdir(parents=True, exist_ok=True)
    fig_st1(); fig_ladder(); fig_traces(); fig_st_map()
    new = json.dumps(DATA, indent=1, ensure_ascii=False, sort_keys=True)
    old = SIDECAR.read_text() if SIDECAR.exists() else None
    if check:
        if old != new:
            sys.exit("CHECK FAIL: figure data would change (fig_data.json)")
        print("check OK: figure data matches the frozen rows")
    else:
        SIDECAR.write_text(new)
        print("wrote fig_st1.pdf fig_ladder.pdf fig_traces.pdf fig_st_map.pdf fig_data.json")


if __name__ == "__main__":
    main()
