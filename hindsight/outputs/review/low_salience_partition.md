# Low-salience realized-bearish partition — reading A vs reading B

POST-FREEZE EXPLORATORY (2026-07-25, design-review response). Model: **gemini-2.5-flash**, frozen FM-1 arms, zero new API calls.

Coverage: R/D/M = 240 dates x 24 sketches = 5760 each (per-date count is exactly 24 in all three arms). Calm baseline = 36 dates in ['2013', '2014', '2017']. Bootstrap: analyze_fm1.boot_diff, B=10000, seed=2026, fresh rng per window.

## 1. Defect 1 verified: the calm-side offset

- share_D(calm) = 0.2986, share_M(calm) = 0.4178
- **raw D−M on the calm baseline = -11.92pp** [-15.62, -8.22]
- Identity: DiD(window) = raw(window) − raw(calm). A window with raw D−M of exactly 0 mechanically scores DiD = +11.92pp.
- Substantively: on calm dates, revealing the date makes the model **less** bearish. The calm baseline is a date-memory state of its own (2013/14/17 remembered as bull years), not a date-effect zero.

## 2. Defect 2: realized-direction audit (forward_return_20d, paper convention)

| date | set | fwd 20d | dir | drawdown | VIX | USREC |
|---|---|---|---|---|---|---|
| 2008-09-15 | crisis_prereg | -17.29% | down | -13.40% | 30.24 | 1 |
| 2008-10-15 | crisis_prereg | -6.31% | down | -26.88% | 61.18 | 1 |
| 2008-11-15 | crisis_prereg | +7.08% | up | -22.13% | 62.67 | 1 |
| 2008-12-15 | crisis_prereg | -3.03% | down | +0.00% | 52.41 | 1 |
| 2009-01-15 | crisis_prereg | -2.02% | down | -13.58% | 44.68 | 1 |
| 2009-02-15 | crisis_prereg | -1.41% | down | -10.95% | 45.57 | 1 |
| 2020-03-15 | crisis_prereg | +17.63% | up | -27.60% | 57.74 | 1 |
| 2020-04-15 | crisis_prereg | +1.31% | up | +0.00% | 41.45 | 1 |
| 2022-06-15 | crisis_prereg | +1.91% | up | -10.59% | 28.23 | 0 |
| 2022-09-15 | crisis_prereg | -6.12% | down | -9.61% | 27.34 | 0 |
| 2022-10-15 | crisis_prereg | +7.32% | up | -2.76% | 30.01 | 0 |
| 2011-08-15 | euro2011 | -2.66% | down | -13.01% | 35.03 | 0 |
| 2011-09-15 | euro2011 | -0.45% | down | -6.22% | 36.53 | 0 |
| 2011-10-15 | euro2011 | +4.15% | up | +0.00% | 32.83 | 0 |
| 2015-09-15 | riskoff15 | +1.29% | up | -1.68% | 24.38 | 0 |
| 2016-01-15 | riskoff15 | +0.81% | up | -7.62% | 23.72 | 0 |
| 2016-02-15 | riskoff15 | +6.16% | up | -5.69% | 22.52 | 0 |
| 2018-11-15 | q4_2018 | -6.99% | down | -3.93% | 19.39 | 0 |
| 2018-12-15 | q4_2018 | +2.72% | up | -15.74% | 24.95 | 0 |
| 2015-08-15 | skipped_by_E1 | -6.10% | down | -10.98% | 19.43 | 0 |

Counts of realized-down months:
- crisis_prereg: 6/11
- euro2011: 2/3
- riskoff15: 0/3
- q4_2018: 1/2

- riskoff15 is 0/3 realized-DOWN: 2015-09 +1.29%, 2016-01 +0.81%, 2016-02 +6.16% forward 20d. The one window E.1 reports as null is the one window with no bearish month in it.
- 2015-08-15 IS realized-down (-6.10%, month drawdown -10.98%) and was skipped by analyze_alt_windows.py:41, which jumps 2015-09 -> 2016-01.
- euro2011 is 2/3 down (2011-10 is +4.15%); q4_2018 is 1/2 down (2018-12 is +2.72% forward despite a -15.74% intramonth drawdown).
- The preregistered crisis set is itself only 6/11 realized-down (2020-03 is +17.63% forward), so realized direction is a screen on economic state, not on E2's outcome.

## 3. Existing appendix-E.1 windows, re-scored with BOTH estimates

| window | n | realized-down | share D | share M | share R | RAW D−M [95%] | DiD E2 [95%] |
|---|---|---|---|---|---|---|---|
| euro2011 | 3 | 2/3 | 0.4028 | 0.4028 | 0.4306 | +0.00pp [-12.50, +20.83] | +11.92pp [-1.50, +31.94] |
| riskoff15 | 3 | 0/3 | 0.2917 | 0.4167 | 0.3472 | -12.50pp [-25.00, -4.17] | -0.58pp [-12.38, +8.68] |
| q4_2018 | 2 | 1/2 | 0.4792 | 0.4792 | 0.5417 | +0.00pp [-12.50, +12.50] | +11.92pp [-3.01, +26.85] |
| pooled_moderate | 8 | 3/8 | 0.3802 | 0.4271 | 0.4271 | -4.69pp [-13.54, +5.21] | +7.23pp [-2.55, +17.77] |

Every positive number in the published E.1 gradient is the calm-side offset, not within-window elevation: euro2011 and q4_2018 both have raw D−M of exactly 0.00pp.

## 4. The defensible partition

Rule: all panel months that are (i) not in the preregistered crisis set, (ii) not in a calm year {2013,2014,2017}, (iii) not in a high-salience year {2007,2008,2009,2020,2022}, and (iv) realized-BEARISH on the paper's own metric (forward_return_20d < 0).

**n = 54 months**, years {'2005': 4, '2006': 5, '2010': 5, '2011': 6, '2012': 5, '2015': 7, '2016': 3, '2018': 5, '2019': 3, '2021': 5, '2023': 4, '2024': 2}, mean forward 20d return -2.65%, mean intramonth drawdown -2.80%, VIX range [10.96, 36.53], USREC months 0.

Months: 2005-02, 2005-03, 2005-08, 2005-09, 2006-01, 2006-03, 2006-05, 2006-06, 2006-12, 2010-01, 2010-04, 2010-05, 2010-06, 2010-07, 2011-02, 2011-05, 2011-07, 2011-08, 2011-09, 2011-11, 2012-03, 2012-04, 2012-05, 2012-09, 2012-10, 2015-02, 2015-04, 2015-05, 2015-07, 2015-08, 2015-11, 2015-12, 2016-04, 2016-08, 2016-09, 2018-01, 2018-03, 2018-09, 2018-10, 2018-11, 2019-04, 2019-07, 2019-09, 2021-04, 2021-08, 2021-09, 2021-11, 2021-12, 2023-02, 2023-04, 2023-07, 2023-09, 2024-03, 2024-07

| window | n | realized-down | share D | share M | share R | RAW D−M [95%] | DiD E2 [95%] |
|---|---|---|---|---|---|---|---|
| LOW_SALIENCE_BEARISH | 54 | 54/54 | 0.3657 | 0.4660 | 0.4074 | -10.03pp [-13.66, -6.40] | +1.89pp [-3.28, +7.10] |
| CRISIS_PREREG_reference | 11 | 6/11 | 0.6136 | 0.4773 | 0.6402 | +13.64pp [+3.03, +24.24] | +25.56pp [+14.46, +36.76] |
| CRISIS_realized_down_only | 6 | 6/6 | 0.6250 | 0.5069 | 0.6736 | +11.81pp [-3.47, +26.39] | +23.73pp [+8.10, +39.47] |

### Sensitivity

| window | n | realized-down | share D | share M | share R | RAW D−M [95%] | DiD E2 [95%] |
|---|---|---|---|---|---|---|---|
| LS vs direction-matched calm (n=9) | 54 | 54/54 | 0.3657 | 0.4660 | 0.4074 | -10.03pp [-13.66, -6.40] | +0.15pp [-8.64, +8.56] |
| CRISIS vs direction-matched calm (n=9) | 11 | 6/11 | 0.6136 | 0.4773 | 0.6402 | +13.64pp [+3.03, +24.24] | +23.82pp [+10.52, +37.12] |
| LS minus 2011 & 2023 | 44 | 44/44 | 0.3400 | 0.4650 | 0.3920 | -12.50pp [-16.38, -8.71] | -0.58pp [-6.02, +4.57] |
| low-salience, NO direction screen | 144 | 54/143 | 0.3874 | 0.4742 | 0.4170 | -8.68pp [-10.85, -6.51] | +3.24pp [-1.10, +7.49] |
| low-salience, intramonth drawdown <= -5% | 16 | 8/16 | 0.3750 | 0.4453 | 0.3906 | -7.03pp [-13.28, -0.52] | +4.89pp [-2.55, +12.36] |

Leave-one-year-out on the partition (DiD E2):

- drop 2005 (n=50): +2.09pp [-3.24, +7.22], raw -9.83pp
- drop 2006 (n=49): +1.29pp [-4.12, +6.62], raw -10.63pp
- drop 2010 (n=49): +3.59pp [-1.56, +8.62], raw -8.33pp
- drop 2011 (n=48): +0.90pp [-4.37, +6.08], raw -11.02pp
- drop 2012 (n=49): +2.99pp [-2.26, +8.16], raw -8.93pp
- drop 2015 (n=47): +2.61pp [-2.60, +7.87], raw -9.31pp
- drop 2016 (n=51): +1.71pp [-3.51, +6.82], raw -10.21pp
- drop 2018 (n=49): +2.31pp [-3.02, +7.54], raw -9.61pp
- drop 2019 (n=51): +1.71pp [-3.53, +6.88], raw -10.21pp
- drop 2021 (n=49): +1.21pp [-4.08, +6.44], raw -10.71pp
- drop 2023 (n=50): +0.67pp [-4.53, +5.81], raw -11.25pp
- drop 2024 (n=52): +1.66pp [-3.59, +6.89], raw -10.26pp

## 5. Dose-response and severity matching

### 5a. Within the low-salience partition (n=54): no dose-response

- delta_d on z(vix): +1.06pp/SD, t=+0.45, p=0.652
- delta_d on z(dd): -1.72pp/SD, t=-0.92, p=0.358
- delta_d on z(fwd): -0.31pp/SD, t=-0.18, p=0.855

### 5b. Horse race: severity vs salience (date-level, HAC(6))

| sample | term | coef | t | p |
|---|---|---|---|---|
| all_months (n=239) | z_vix | -1.76pp | -1.08 | 0.2784 |
| all_months (n=239) | z_drawdown | -3.23pp | -2.43 | 0.0150 |
| all_months (n=239) | usrec | +16.94pp | +2.85 | 0.0044 |
| all_months (n=239) | high_salience_year | +10.44pp | +2.64 | 0.0084 |
| all_months_no_usrec (n=239) | z_vix | +0.39pp | +0.22 | 0.8260 |
| all_months_no_usrec (n=239) | z_drawdown | -3.36pp | -2.02 | 0.0438 |
| all_months_no_usrec (n=239) | high_salience_year | +13.20pp | +3.20 | 0.0014 |
| realized_bearish_only (n=87) | z_vix | -2.58pp | -0.95 | 0.3445 |
| realized_bearish_only (n=87) | z_drawdown | -3.72pp | -1.97 | 0.0491 |
| realized_bearish_only (n=87) | usrec | +11.08pp | +1.29 | 0.1987 |
| realized_bearish_only (n=87) | high_salience_year | +14.00pp | +2.48 | 0.0130 |
| realized_bearish_only_no_usrec (n=87) | z_vix | -1.25pp | -0.55 | 0.5856 |
| realized_bearish_only_no_usrec (n=87) | z_drawdown | -3.65pp | -1.76 | 0.0776 |
| realized_bearish_only_no_usrec (n=87) | high_salience_year | +17.46pp | +2.86 | 0.0042 |

### 5c. Severity-matched 2x2 on the non-recession margin

all non-calm months with USREC=0 and monthly-mean VIX >= 27.0 (the floor of the 2022 crisis months), split by salience year. Recession state is held at 0 on both sides and volatility is matched or tilted AGAINST the salience hypothesis.

- HIGH-salience cell (n=8): 2020-05, 2020-06, 2020-09, 2020-10, 2022-05, 2022-06, 2022-09, 2022-10 — mean VIX 29.25, **raw D−M +7.29pp** [+1.04, +13.54]
- LOW-salience cell (n=6): 2010-05, 2010-06, 2011-08, 2011-09, 2011-10, 2011-11 — mean VIX 33.03, **raw D−M -10.42pp** [-21.53, +2.78]
- difference (high − low): **+17.71pp** [+2.60, +31.08]

### 5d. euro2011 carries HIGHER VIX than every 2022 crisis month

- euro2011 VIX range [32.83, 36.53]; 2022 crisis VIX range [27.34, 30.01]; strictly higher: True
- euro2011 raw D−M +0.00pp; 2022 crisis raw D−M +12.50pp

| month | VIX | USREC | drawdown | fwd 20d | delta_d |
|---|---|---|---|---|---|
| 2011-08 | 35.03 | 0 | -13.01% | -2.66% | +20.83pp |
| 2011-09 | 36.53 | 0 | -6.22% | -0.45% | -8.33pp |
| 2011-10 | 32.83 | 0 | +0.00% | +4.15% | -12.50pp |
| 2022-06 | 28.23 | 0 | -10.59% | +1.91% | +16.67pp |
| 2022-09 | 27.34 | 0 | -9.61% | -6.12% | +20.83pp |
| 2022-10 | 30.01 | 0 | -2.76% | +7.32% | +0.00pp |

## 6. Verdict for Paper 1's headline model

**MIXED, decisively B-leaning — and reading A is dead on the only margin where the panel can identify it.**

For (B): the 54 low-salience realized-bearish months give E2 = +1.89pp [-3.28, +7.10] against +25.56pp [+14.46, +36.76] on the preregistered crisis set (non-overlapping CIs); their within-window raw date effect (-10.03pp) is statistically the calm baseline's own (-11.92pp); there is no dose-response on VIX, drawdown or forward return inside the partition (all p > 0.35); and with recession status held at zero and volatility matched — indeed tilted AGAINST the salience hypothesis (low-salience mean VIX 33.03 vs high-salience 29.25) — the high-salience side still shows +7.29pp raw elevation vs -10.42pp, a gap of +17.71pp [+2.60, +31.08].

For (A): USREC still carries +16.9pp (p=0.004) net of the salience dummy. But that coefficient is NOT evidence for state memory, because all 20 USREC=1 months in this panel (years ['2008', '2009', '2020']) lie inside high-salience years — recession state and peak corpus salience are perfectly nested and cannot be separated by ANY re-partition of these generations. Meanwhile realized drawdown, the one continuous severity measure that is not nested, loads with the WRONG sign (-3.2 to -3.7pp per SD): deeper realized selloffs produce LESS date-induced bearishness.

### Printable sentence (defensible from the numbers above)

> Re-partitioning the same frozen generations onto the 54 realized-bearish months (forward 20-day S\&P return $<0$) that lie outside the calm years and outside the high-salience years \{2007--2009, 2020, 2022\} yields E2 $= +1.9$pp $[-3.3, +7.1]$ under the identical calm baseline and bootstrap, against $+25.6$pp $[+14.5, +36.8]$ on the preregistered crisis set; holding NBER recession status at zero and matching on realized volatility---the 2011 US-downgrade months carry \emph{higher} monthly VIX (32.8--36.5) than every 2022 crisis month (27.3--30.2)---the high-salience side still shows $+7.3$pp raw date elevation against $-10.4$pp on the low-salience side, so the trigger keys on the salience of the date string rather than on the severity of the state it denotes.

### Blind spots (not covered by this artifact)

1. `high-salience year` is a YEAR-LEVEL PROXY chosen by the reviewers, not a measured retrospective-corpus density. No corpus count is available in this repo and none was estimated.
2. Recession state is perfectly nested inside the salience proxy (20 USREC=1 months, all in ['2008', '2009', '2020']), so the recession margin is unidentified here by construction; a low-salience recession would be needed and the 2005--2024 panel contains none. The frozen USREC vintage also starts one month late vs canonical NBER peaks (2008-01 not 2007-12; 2020-03 not 2020-02) — kept as-is because analyze_fm1.build_covariates already uses it, and both disputed months are high-salience under either coding.
3. This is one model (gemini-2.5-flash) and one prompt family (FM-1). Nothing here re-partitions the other benchmark models.
4. The partition is rule-defined but POST-FREEZE; it must be disclosed as exploratory even though it was reviewer-specified.
5. Realized direction is measured on SPX forward 20d only; a different horizon or a different index could reshuffle membership (the drawdown-screened variant above is the one alternative run).
6. `share_R` is reported for coverage/context only; no E1-style R-vs-D contrast is estimated on the new partition.
