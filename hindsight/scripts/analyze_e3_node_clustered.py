#!/usr/bin/env python
"""E3 sensitivity: resample true decision NODES as clusters, not window labels.

Why. The preregistered E3 interval is a window bootstrap: it resamples the
crisis/calm *date labels* and applies the same draw to both keyings of the W
arm (analyze_fm1.py:94-101). That is a legitimate inferential object -- the
uncertainty induced by which windows we call crisis and calm -- but it is not
the only one, and it is not the one the transplantation narrative is about.
Because E3 reuses the same W generations under two labelings, a drawn label
indexes DIFFERENT generation records on the two sides (on the 11 preregistered
crisis labels the two sides share zero records), so the pairing is over the
label, not the observation.

This script reports the complementary object: resample the true decision node
as the cluster, carrying its asserted-date label, its true-date label and all
replicate sketches together, and recompute Gap_fake, Gap_true and their
difference inside the same draw. It does NOT resample the two sides
independently and does NOT resample date labels.

The preregistered window-label CI stays primary; this is a sensitivity. No
frozen value is overwritten -- output goes to outputs/review/.

PRE-COMMITMENT, recorded before the first run (2026-07-27): if the
node-clustered interval is materially wider than the preregistered one, or
crosses zero, the confidence language in section 9 and the abstract is
downgraded accordingly. It does not get filed as an inconspicuous robustness
line.

Usage: python analyze_e3_node_clustered.py [--model gemini-2.5-flash]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, fake_map, gap, CRISIS, CALM_YEARS  # noqa: E402
from analyze_fm1c import load_dir_tree  # noqa: E402
from hindsight_paths import REPO  # noqa: E402

B, SEED = 10_000, 2026
OUT = REPO / "hindsight/outputs/review/e3_node_clustered.json"


def gaps_from_nodes(nodes, w_by_true, fmap, crisis_set, calm_set):
    """Gap_fake and Gap_true from one multiset of true decision nodes.

    A node lands in Gap_true's crisis cell iff its TRUE date is a crisis date,
    and in Gap_fake's crisis cell iff its ASSERTED date is. Both are read off
    the same drawn node, so the two sides move together by construction.
    """
    cells = {"fc": [0, 0], "fq": [0, 0], "tc": [0, 0], "tq": [0, 0]}  # [bear, tot]

    def add(key, xs):
        cells[key][0] += sum(1 for x in xs if x == "-")
        cells[key][1] += len(xs)

    for d in nodes:
        xs = w_by_true.get(d, [])
        if not xs:
            continue
        a = fmap[d]
        if a in crisis_set:
            add("fc", xs)
        elif a in calm_set:
            add("fq", xs)
        if d in crisis_set:
            add("tc", xs)
        elif d in calm_set:
            add("tq", xs)

    def share(k):
        b, t = cells[k]
        return b / t if t else float("nan")

    return share("fc") - share("fq"), share("tc") - share("tq")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemini-2.5-flash")
    a = ap.parse_args()

    dates = all_dates()
    calm = [d for d in dates if d[:4] in CALM_YEARS]
    crisis_set, calm_set = set(CRISIS), set(calm)
    fmap = fake_map(dates)
    W = load_dir_tree(REPO / f"hindsight/outputs/fm1/{a.model}/W")

    # Point estimates must reproduce the frozen ones exactly: same records,
    # same windows, no resampling.
    w_fake = defaultdict(list)
    for td, xs in W.items():
        w_fake[fmap[td]].extend(xs)
    gf_ref, gt_ref = gap(w_fake, CRISIS, calm), gap(W, CRISIS, calm)
    gf, gt = gaps_from_nodes(dates, W, fmap, crisis_set, calm_set)
    for name, ref, got in (("Gap_fake", gf_ref, gf), ("Gap_true", gt_ref, gt)):
        if abs(ref - got) > 1e-12:
            sys.exit(f"FAIL: node-indexed {name} {got!r} != frozen path {ref!r}")

    rng = np.random.default_rng(SEED)
    node_arr = np.array(dates)
    diffs = np.empty(B)
    for i in range(B):
        draw = list(rng.choice(node_arr, len(node_arr), replace=True))
        f, t = gaps_from_nodes(draw, W, fmap, crisis_set, calm_set)
        diffs[i] = f - t
    valid = diffs[~np.isnan(diffs)]
    if len(valid) < B * 0.5:
        sys.exit(f"FAIL: only {len(valid)}/{B} bootstrap draws were valid")
    lo, hi = float(np.percentile(valid, 2.5)), float(np.percentile(valid, 97.5))

    res = {
        "note": "POST-HOC SENSITIVITY. The preregistered window-label interval "
                "stays primary; this resamples true decision nodes as clusters.",
        "model": a.model,
        "n_nodes": len(dates),
        "B": B, "seed": SEED,
        "point_estimate": gf - gt,
        "gap_fake": gf, "gap_true": gt,
        "ci95_node_clustered": [lo, hi],
        "ci95_window_label_preregistered": [0.19675662878787872, 0.42961121632996635],
        "n_valid_draws": int(len(valid)),
        "width_node_clustered_pp": (hi - lo) * 100,
        "width_window_label_pp": (0.42961121632996635 - 0.19675662878787872) * 100,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2) + "\n")

    print(f"model {a.model}: {len(dates)} nodes, B={B}, seed={SEED}")
    print(f"  Gap_fake {gf:+.6f}   Gap_true {gt:+.6f}   (both reproduce the frozen path)")
    print(f"  E3 point estimate            {gf-gt:+.4f}  ({(gf-gt)*100:+.1f}pp)")
    print(f"  node-clustered  95% CI  [{lo*100:+.1f}, {hi*100:+.1f}]pp   width {(hi-lo)*100:.1f}pp")
    print(f"  window-label    95% CI  [+19.7, +43.0]pp   width {res['width_window_label_pp']:.1f}pp")
    print(f"  crosses zero: {'YES' if lo <= 0 <= hi else 'no'}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
