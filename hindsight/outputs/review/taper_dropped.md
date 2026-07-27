# Taper-tantrum calm-set sensitivity (POST-FREEZE EXPLORATORY, 2026-07-24)

Kimi review: 2013-05/2013-06 are the taper tantrum (a textbook bond event)
yet sit in the frozen calm set. Both second-domain contrasts recomputed with
those two months dropped (calm 36 -> 34), same frozen estimators.

## GD-1 10Y bond arm (E2_10Y = D-M yield-down gap)

| calm set | Gap_down(D) | Gap_down(M) | E2_10Y | 95% CI |
|---|---|---|---|---|
| 36 dates (frozen) | +0.550 | -0.017 | **+0.567** | [+0.362, +0.757] |
| 34 dates (dropped) | +0.556 | -0.027 | **+0.583** | [+0.378, +0.775] |

W-arm transplant, fake-minus-true: +0.617 CI [+0.334, +0.876] (36) -> +0.604 CI [+0.325, +0.860] (34).

## GD-1b VIX micro-arm

| calm set | crisis up-share | calm up-share | delta pp | Fisher p (sketch) | date-level maj | Fisher p (date) |
|---|---|---|---|---|---|---|
| 36 dates (frozen) | 92.0% (81/88) | 55.6% (160/288) | **+36.5** | 2.45e-11 | 11/11 vs 19/36 | 3.78e-03 |
| 34 dates (dropped) | 92.0% (81/88) | 54.8% (149/272) | **+37.3** | 1.78e-11 | 11/11 vs 17/34 | 3.08e-03 |

Dropped fake-calm dates' own VIX sketches: 2013-05-15 (true 2007-11-15): up 6 / down 2; 2013-06-15 (true 2007-12-15): up 5 / down 3

All frozen originals were re-derived from per-date files and asserted
against GD1_RESULTS.md / GD1B_RESULTS.json / paper text before dropping.
