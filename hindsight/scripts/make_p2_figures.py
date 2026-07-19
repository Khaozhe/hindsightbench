#!/usr/bin/env python
"""Paper-2-specific figures. fig6: BM-1 protocol overview schematic.

Pure layout code — no measured numbers appear here except the frozen
protocol constants (dates, reps, thresholds), so there is nothing to drift.

Writes hindsight/paper/figures/fig6_protocol_auto.{pdf,png} — the FALLBACK
rendering. The shipped asset fig6_protocol.{pdf,png} is a hand-finished
version of the same layout (identical text and topology, proofread
character-by-character); this script intentionally does NOT overwrite it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).parent))
from hindsight_paths import REPO

FIGS = REPO / "hindsight/paper/figures"

plt.rcParams.update({
    "font.size": 7.2, "figure.dpi": 150, "savefig.bbox": "tight",
    "pdf.fonttype": 42, "ps.fonttype": 42,
})

INK = "#2b2b2b"
ARM = {"R": "#8a8a8a", "D": "#B3402A", "M": "#2A6EB3", "W": "#7a4fa3"}
GOLD = "#9a7b2d"


def box(ax, x, y, w, h, text, fc="#f4f2ee", ec=INK, fs=7.2, lw=0.9,
        weight="normal", tc=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012",
                                fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc or INK, weight=weight, linespacing=1.25)


def arrow(ax, x0, y0, x1, y1, color=INK, lw=1.0):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>",
                                 mutation_scale=8, color=color, lw=lw,
                                 shrinkA=1, shrinkB=1))


def fig6() -> None:
    fig, ax = plt.subplots(figsize=(7.6, 2.55))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 33)
    ax.axis("off")

    # ---- column 1: panel node ----
    box(ax, 0.5, 11.5, 16, 12,
        "vintage-correct\nmacro snapshot\nat decision date $t$\n"
        "(240 pre + 18 post\nmonthly nodes)", fc="#eee9df", fs=7.0)

    # ---- column 2: four arms ----
    arms = [
        ("R  revealed", "date + auxiliary\ncontext as-is", 26.5),
        ("D  date-only", "masked + explicit\ndate string", 18.5),
        ("M  masked", "date and identifying\ncontext scrubbed", 10.5),
        ("W  transplant", "true data, date\nshifted 66 mo", 2.5),
    ]
    for (title, sub, y), k in zip(arms, "RDMW"):
        box(ax, 24, y, 16.5, 6.5, f"{title}\n{sub}", fc="white",
            ec=ARM[k], fs=6.6, lw=1.2)
        arrow(ax, 16.2, 17.5, 23.8, y + 3.25, color=ARM[k], lw=0.9)

    # ---- column 3: readout + probes ----
    box(ax, 45.5, 19.5, 23.5, 9.5,
        "generate 8 hypothesis\nsketches per arm\n"
        "readout: crisis$-$calm\nbearish gap (11 vs 36 dates)",
        fc="#f7f3ea", fs=6.4)
    for k, y in zip("RDMW", (29.75, 21.75, 13.75, 5.75)):
        arrow(ax, 40.7, y, 45.8, 22.5 + (y - 17.75) * 0.28, color=ARM[k],
              lw=0.8)

    box(ax, 46.5, 8.0, 22, 8,
        "dual memory probes\nREC: date the masked data\n"
        "LAP: recall outcome from\ndate alone (20 samples)",
        fc="white", ec=GOLD, fs=6.5, lw=1.2)
    # probe feed routed along the bottom so it crosses no arm box
    ax.plot([8.5, 8.5], [11.3, 1.2], color=GOLD, lw=0.9)
    ax.plot([8.5, 57.0], [1.2, 1.2], color=GOLD, lw=0.9)
    arrow(ax, 57.0, 1.2, 57.0, 7.8, color=GOLD, lw=0.9)

    # ---- column 4: metrics + gates -> audit row ----
    box(ax, 73.5, 2.5, 26, 26,
        "six gated metrics\n"
        "E2 trigger = Gap(D)$-$Gap(M)\n"
        "E3 transplant = fake$-$true (W)\n"
        "P1 placebo (model-relative)\n"
        "REC recoverability ($n{\\geq}10$)\n"
        "cutoff = LAP collapse (hit>chance)\n"
        "$\\delta$ dissociation (LAP var. gate)\n"
        "+ VALID compliance floor",
        fc="#f4f2ee", fs=6.4)
    arrow(ax, 69.2, 24, 73.2, 20, lw=1.0)
    arrow(ax, 68.8, 12, 73.2, 12, color=GOLD, lw=1.0)

    ax.text(86.5, 30.6, "one audit row per model\n(frozen prereg, "
            "bootstrap $B{=}10^4$)", ha="center", fontsize=6.9,
            style="italic", color=INK)

    fig.savefig(FIGS / "fig6_protocol_auto.pdf")
    fig.savefig(FIGS / "fig6_protocol_auto.png")
    plt.close(fig)
    print("fig6: done (protocol schematic, _auto fallback)")


if __name__ == "__main__":
    FIGS.mkdir(parents=True, exist_ok=True)
    fig6()
