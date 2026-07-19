# Design-review robustness pack (frozen FM-1 flash arms, zero new API)

Convention: paired date-level bootstrap B=10000 seed=2026, frozen FM-1 flash arms, gap = crisis-calm bearish share

**E2 full (baseline reproduction)**: +0.256 [+0.145, +0.368] (paper: +0.256 [0.143, 0.372])

## Leave-one-episode-out E2

- drop_GFC (crisis n=5): +0.228 [+0.150, +0.304]
- drop_COVID (crisis n=9): +0.267 [+0.137, +0.404]
- drop_inflation (crisis n=8): +0.260 [+0.116, +0.407]

## Per-episode E2

- GFC (n=6): +0.279 [+0.091, +0.464]
- COVID (n=2): +0.203 [+0.137, +0.269]
- inflation (n=3): +0.244 [+0.127, +0.337]

## Within-M data sensitivity

- M crisis-calm gap: +0.059 [+0.013, +0.110]
- M bearish share on snapshot UNRATE (per 1 SD): -0.033 [-0.044, -0.022]  (n=240 dates)

## Per-date share dispersion (hedging diagnostic)

- D: mean 0.409, sd 0.177, p10-p90 [0.204, 0.625] (n=240)
- M: mean 0.461, sd 0.086, p10-p90 [0.375, 0.583] (n=240)
