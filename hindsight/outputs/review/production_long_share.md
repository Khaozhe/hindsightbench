# Production long-share audit (POST-FREEZE EXPLORATORY, 2026-07-25)

Question: is the S7.3 *production* row a weaker version of the "decontamination by lobotomy" the paper concedes for in-sample top-1?

## Windows

- `oos_2019plus`: n=71 months, 2019-01-15 .. 2024-11-15
- `full_evaluated`: n=239 months, 2005-01-15 .. 2024-11-15

## (a),(b) LONG share and accuracy by architecture

`long` = decision sign +1. Always-long = 100% long by definition.

### Window: oos_2019plus (n=71)

| Architecture | long% R | long% M | short mo. R | short mo. M | acc R | acc M | T2 R−M | Sharpe R | Sharpe M |
|---|---|---|---|---|---|---|---|---|---|
| equal_weight_vote_no_gate | 56.3% | 52.1% | 31 | 34 | 0.521 | 0.592 | -0.0704 | -0.065 | 0.331 |
| equal_weight_sum_no_gate | 56.3% | 52.1% | 31 | 34 | 0.521 | 0.592 | -0.0704 | -0.065 | 0.331 |
| binary_ic_screen | 87.3% | 90.1% | 9 | 7 | 0.634 | 0.718 | -0.0845 | 0.191 | 0.724 |
| ic_weighting_no_penalties | 98.6% | 98.6% | 1 | 1 | 0.690 | 0.718 | -0.0282 | 0.648 | 0.794 |
| production_ic_wt_plus_pen | 100.0% | 98.6% | 0 | 1 | 0.704 | 0.718 | -0.0141 | 0.695 | 0.794 |
| in_sample_top1 | 98.6% | 100.0% | 1 | 0 | 0.718 | 0.704 | +0.0141 | 0.702 | 0.695 |
| **always-long (benchmark)** | 100.0% | 100.0% | 0 | 0 | 0.704 | 0.704 | 0.0000 | 0.695 | 0.695 |

### Window: full_evaluated (n=239)

| Architecture | long% R | long% M | short mo. R | short mo. M | acc R | acc M | T2 R−M | Sharpe R | Sharpe M |
|---|---|---|---|---|---|---|---|---|---|
| equal_weight_vote_no_gate | 67.4% | 57.3% | 78 | 102 | 0.527 | 0.544 | -0.0167 | -0.047 | 0.232 |
| equal_weight_sum_no_gate | 67.4% | 57.3% | 78 | 102 | 0.527 | 0.544 | -0.0167 | -0.047 | 0.232 |
| binary_ic_screen | 90.4% | 95.0% | 23 | 12 | 0.607 | 0.636 | -0.0293 | 0.136 | 0.490 |
| ic_weighting_no_penalties | 97.9% | 99.2% | 5 | 2 | 0.623 | 0.644 | -0.0209 | 0.361 | 0.558 |
| production_ic_wt_plus_pen | 98.3% | 99.2% | 4 | 2 | 0.628 | 0.644 | -0.0167 | 0.377 | 0.558 |
| in_sample_top1 | 98.3% | 100.0% | 4 | 0 | 0.628 | 0.636 | -0.0084 | 0.360 | 0.495 |
| **always-long (benchmark)** | 100.0% | 100.0% | 0 | 0 | 0.636 | 0.636 | 0.0000 | 0.495 | 0.495 |

## (c) always-long benchmark

- `oos_2019plus`: accuracy 0.7042 (n=71), sign-only Sharpe 0.695
- `full_evaluated`: accuracy 0.6360 (n=239), sign-only Sharpe 0.495

## (d) R vs M sign disagreement

| Architecture | window | n disagree | acc R there | acc M there | truth-up share there |
|---|---|---|---|---|---|
| equal_weight_vote_no_gate | oos_2019plus | 29 | 0.414 | 0.586 | 0.724 |
| equal_weight_vote_no_gate | full_evaluated | 96 | 0.479 | 0.521 | 0.604 |
| equal_weight_sum_no_gate | oos_2019plus | 29 | 0.414 | 0.586 | 0.724 |
| equal_weight_sum_no_gate | full_evaluated | 96 | 0.479 | 0.521 | 0.604 |
| binary_ic_screen | oos_2019plus | 12 | 0.250 | 0.750 | 0.667 |
| binary_ic_screen | full_evaluated | 29 | 0.379 | 0.621 | 0.655 |
| ic_weighting_no_penalties | oos_2019plus | 2 | 0.000 | 1.000 | 0.500 |
| ic_weighting_no_penalties | full_evaluated | 7 | 0.143 | 0.857 | 0.571 |
| production_ic_wt_plus_pen | oos_2019plus | 1 | 0.000 | 1.000 | 0.000 |
| production_ic_wt_plus_pen | full_evaluated | 6 | 0.167 | 0.833 | 0.500 |
| in_sample_top1 | oos_2019plus | 1 | 1.000 | 0.000 | 0.000 |
| in_sample_top1 | full_evaluated | 4 | 0.250 | 0.750 | 0.750 |

Disagreeing months (production, OOS): 2024-07-15

## (e) bullish share of hypotheses

| Arm | top-1 bullish | top-K (K=20) bullish |
|---|---|---|
| R | 98.3% (235/239) | 55.6% (2635/4738) |
| M | 100.0% (239/239) | 52.7% (2500/4745) |
| pooled | 99.2% | 54.1% |

## Distance from literal always-long

Months where the architecture deviates from always-long (i.e. goes short), and how many of those short calls were right.

| Architecture | window | arm | months != always-long | short calls correct | acc delta vs always-long |
|---|---|---|---|---|---|
| equal_weight_vote_no_gate | oos_2019plus | R | 31 | 9 | -0.1831 |
| equal_weight_vote_no_gate | oos_2019plus | M | 34 | 13 | -0.1127 |
| equal_weight_vote_no_gate | full_evaluated | R | 78 | 26 | -0.1088 |
| equal_weight_vote_no_gate | full_evaluated | M | 102 | 40 | -0.0921 |
| equal_weight_sum_no_gate | oos_2019plus | R | 31 | 9 | -0.1831 |
| equal_weight_sum_no_gate | oos_2019plus | M | 34 | 13 | -0.1127 |
| equal_weight_sum_no_gate | full_evaluated | R | 78 | 26 | -0.1088 |
| equal_weight_sum_no_gate | full_evaluated | M | 102 | 40 | -0.0921 |
| binary_ic_screen | oos_2019plus | R | 9 | 2 | -0.0704 |
| binary_ic_screen | oos_2019plus | M | 7 | 4 | +0.0141 |
| binary_ic_screen | full_evaluated | R | 23 | 8 | -0.0293 |
| binary_ic_screen | full_evaluated | M | 12 | 6 | +0.0000 |
| ic_weighting_no_penalties | oos_2019plus | R | 1 | 0 | -0.0141 |
| ic_weighting_no_penalties | oos_2019plus | M | 1 | 1 | +0.0141 |
| ic_weighting_no_penalties | full_evaluated | R | 5 | 1 | -0.0126 |
| ic_weighting_no_penalties | full_evaluated | M | 2 | 2 | +0.0084 |
| production_ic_wt_plus_pen | oos_2019plus | R | 0 | 0 | +0.0000 |
| production_ic_wt_plus_pen | oos_2019plus | M | 1 | 1 | +0.0141 |
| production_ic_wt_plus_pen | full_evaluated | R | 4 | 1 | -0.0084 |
| production_ic_wt_plus_pen | full_evaluated | M | 2 | 2 | +0.0084 |
| in_sample_top1 | oos_2019plus | R | 1 | 1 | +0.0141 |
| in_sample_top1 | oos_2019plus | M | 0 | 0 | +0.0000 |
| in_sample_top1 | full_evaluated | R | 4 | 1 | -0.0084 |
| in_sample_top1 | full_evaluated | M | 0 | 0 | +0.0000 |

Production-row short months in full (listed):

- production / oos_2019plus / arm R: NONE (0 correct)
- production / oos_2019plus / arm M: ['2024-07-15'] (1 correct)
- production / full_evaluated / arm R: ['2008-07-15', '2008-12-15', '2009-03-15', '2009-04-15'] (1 correct)
- production / full_evaluated / arm M: ['2005-09-15', '2024-07-15'] (2 correct)

Note: every short call the REVEALED production arm ever makes falls in 2008-07..2009-04, i.e. inside the in-sample GFC crisis window that T1 measures and entirely outside the 2019+ OOS window that T2 measures. On the T2 window the revealed aggregator expresses no directional view other than long.


## Single-month decomposition of the S7.2 headline

- production short months, revealed arm, OOS: NONE
- production short months, masked arm, OOS: ['2024-07-15']
- dropping those month(s): n=70, acc R=0.7143, acc M=0.7143, T2 rent=+0.0000
- full-window T2 rent=-0.0141; one month out of 71 = -1.41pp

## Identity: the whole T2 column is net short-call scoring

`acc = always_long_acc + (short_correct - short_wrong)/n`, exactly. Max abs residual across all 24 arch x window x arm cells: 1.11e-16 (EXACT).

An architecture can only differ from always-long on months it goes short, so its T2 rent is fully determined by how often it shorts and how often it is right to. On the OOS window the up-rate is 0.704, so each short call is an ex-ante losing bet.

## (3) Published-number reproduction

| Claim | published | recomputed | reproduces |
|---|---|---|---|
| S7.2 revealed OOS accuracy 70.4% | 0.704 | 0.7042 | YES |
| S7.2 masked OOS accuracy 71.8% | 0.718 | 0.7183 | YES |
| S7.2 always-long OOS accuracy = revealed | 0.704225352112676 | 0.7042 | YES |
| S7.2 paired diff -1.4pp | -0.0141 | -0.0141 | YES |
| S7.2 CI low -4.2pp | -0.0423 | -0.0423 | YES |
| S7.2 CI high +0.0pp | 0.0 | 0.0000 | YES |
| S7.2 n = 71 months | 71.0 | 71.0000 | YES |
| S7.2 masked sign-only Sharpe 0.794 | 0.794 | 0.7943 | YES |
| S7.2 revealed sign-only Sharpe 0.695 | 0.695 | 0.6954 | YES |
| S7.3 equal-weight vote OOS R .521 | 0.521 | 0.5211 | YES |
| S7.3 equal-weight vote OOS M .592 | 0.592 | 0.5915 | YES |
| S7.3 binary IC screen OOS R .634 | 0.634 | 0.6338 | YES |
| S7.3 binary IC screen OOS M .718 | 0.718 | 0.7183 | YES |
| S7.3 IC-wt no-pen OOS R .690 | 0.69 | 0.6901 | YES |
| S7.3 IC-wt no-pen OOS M .718 | 0.718 | 0.7183 | YES |
| S7.3 IC-wt no-pen T2 -2.8pp | -0.028 | -0.0282 | YES |
| S7.3 top-1 OOS R .718 | 0.718 | 0.7183 | YES |
| S7.3 top-1 OOS M .704 | 0.704 | 0.7042 | YES |
| S7.3 top-1 '98% of top-ranked hypotheses are bullish' -- REVEALED arm | 0.98 | 0.9833 | YES |
| S7.3 top-1 '98% ...' -- MASKED arm (same sentence, other arm) | 0.98 | 1.0000 | **NO** |
| S7.3 top-1 '98% ...' -- pooled R+M | 0.98 | 0.9916 | **NO** |

Failures: 2/21
- **MISMATCH** S7.3 top-1 '98% ...' -- MASKED arm (same sentence, other arm): published 0.98, recomputed 1.0
- **MISMATCH** S7.3 top-1 '98% ...' -- pooled R+M: published 0.98, recomputed 0.9916317991631799

## Verdict inputs

- `production_long_share_oos_R` = 1.0
- `production_long_share_oos_M` = 0.9859154929577465
- `production_short_months_oos_R` = 0
- `production_short_months_oos_M` = 1
- `production_long_share_full_R` = 0.9832635983263598
- `production_long_share_full_M` = 0.9916317991631799
- `top1_long_share_oos_R` = 0.9859154929577465
- `top1_long_share_oos_M` = 1.0
- `n_disagree_oos_production` = 1
