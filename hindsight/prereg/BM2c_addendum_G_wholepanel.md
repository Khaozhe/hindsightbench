# BM-2c addendum G: a whole-panel date-trigger estimand (G2)

Frozen 2026-09-23 before any addendum-F row other than F1 was read. Extends BM2c_prereg_olmo_ladder.md
(afa19e6d) and addenda D, E, F (6517a57b). Nothing already frozen changes: E2 stays every row's frozen
estimand and every existing reading stands.

## Why

E2 contrasts the date effect (D minus M bearish share) on 11 crisis versus 36 calm dates. Its
date-level bootstrap interval is dominated by having 11 crisis dates, not by sampling noise: on the
one row with three replicates (Gemini 2.5 Flash) the interval narrows only from 24.3 pp (one replicate)
to 22.3 pp (three). More replicates cannot make E2 decisive on the open-weight rows. The panel already
holds every row's D and M cells on all 258 dates; E2 uses 47 of them.

## Estimand (frozen)

For each row, y_t = bearish share of arm D at date t minus bearish share of arm M at date t, for every
panel date t <= 2023-12-31 at which both cells exist (the common pre-cutoff window of the lineages in
this study; 228 dates, 20 of them NBER recession months: 2008-01..2009-06 and 2020-03..04). OLS of y_t
on a constant and the NBER recession indicator USREC_t. Standard errors HAC (Newey-West) with 6 lags.

**G2 = the USREC coefficient** (pp of bearish share per recession month). This is paper 1's
remembered-regime regression (h_t = R minus M on USREC, HAC 6, t = 3.76), applied to the D minus M
contrast the benchmark uses for E2. The regressor and the standard errors are taken from paper 1 and
were not chosen here; VIX, drawdown and returns are not tested.

- G2 **triggers** when t >= 1.96; **NEG\*** when t <= -1.96; null otherwise. One-sided in the same sense
  as E2's frozen trigger definition.
- A row with fewer than 200 usable window dates gets no G2 reading ("insufficient coverage").
- Note on scope: 2022 is not an NBER recession, so G2 does not see the 2022 episode that E2 includes.
  G2 and E2 answer the same question on different date sets; neither is corrected by the other.
- Implementation: `scripts/analyze_wholepanel.py` (sha256 recorded in the freeze file).

## Status of rows

- **Prospective**: T1, T2, T3, F2, F3 (addendum F). At freeze time T1 had 384 of 1032 cells on the
  server and no row; its 8 smoke cells had been read for the post-hoc smoke inspection (directions
  visible in BM2c_note_T1_inspection.md). No other data of these five rows had been seen.
- **Post hoc**: every other row, including F1. G2 was computed for all of them on 2026-09-23 in an
  exploratory version (HC1 errors, plus a VIX regressor) before this addendum was written; that
  exploration is what motivated it. Their G2 values are reported in an appendix column labelled post
  hoc and are never used for a headline claim.

## Readings (frozen)

For the five prospective rows, the addendum-F readings (Tulu ladder monotonicity, panel count) are
computed twice: once with the E2 trigger (as frozen in addendum F) and once with the G2 trigger, under
the same memory clause. Both are reported side by side with equal prominence. If they disagree, the
disagreement is reported as the finding; neither is declared the winner.

## Cost

None. No new calls; the estimand reads cells already written.
