# P0-4 per-date REC/LAP x trigger cross-tab

POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls;
reads frozen bench outputs only. Script: `scripts/analyze_perdate_crosstab.py`.

Trigger primitive T(d) = per-date bearish share, arm D minus arm M,
pooled over reps. High-recall date := REC year-hit == 1 OR per-date LAP
majority direction correct. Baseline := model's own mean T(d) over the
36 calm dates. Quadrants over the 240 pre-cutoff dates.

| model | group | E2 (frozen) | REC-yr | LAP-hit | calm baseline | n high / n low | frac T>base (high) | frac T>base (low) | diff |
|---|---|---|---|---|---|---|---|---|---|
| llama-3.1-70b-awq | memory-without-trigger | -0.047 | 18.3% | 67.6% | -0.033 | 166 / 74 | 50.6% | 54.1% | -3.5% |
| qwen3-30b-a3b-fp8dyn | memory-without-trigger | +0.063 | 17.5% | 67.4% | -0.017 | 163 / 77 | 58.3% | 50.6% | +7.6% |
| gemini-2.5-flash | triggered | +0.256 | 80.4% | 94.3% | -0.119 | 227 / 13 | 59.0% | 84.6% | -25.6% |
| qwen3.6-27b-fp8 | triggered | +0.193 | 9.2% | 72.3% | -0.068 | 178 / 62 | 70.8% | 69.4% | +1.4% |

## Quadrant counts (high/low recall x above/below calm baseline)

| model | HH | HL | LH | LL | mean T high | mean T low | mean Wprim high | mean Wprim low |
|---|---|---|---|---|---|---|---|---|
| llama-3.1-70b-awq | 84 | 82 | 40 | 34 | -0.039 | -0.019 | -0.021 | +0.046 |
| qwen3-30b-a3b-fp8dyn | 95 | 68 | 39 | 38 | +0.011 | -0.019 | -0.011 | +0.010 |
| gemini-2.5-flash | 134 | 93 | 11 | 2 | -0.055 | -0.016 | +0.016 | -0.064 |
| qwen3.6-27b-fp8 | 126 | 52 | 43 | 19 | -0.034 | -0.019 | +0.000 | +0.036 |

## Crisis stratum (where the frozen E2 lives at date grain)

| model | crisis dates high-recall | mean T crisis | mean T high-recall non-crisis | calm baseline |
|---|---|---|---|---|
| llama-3.1-70b-awq | 10/11 | -0.080 | -0.036 | -0.033 |
| qwen3-30b-a3b-fp8dyn | 8/11 | +0.045 | +0.005 | -0.017 |
| gemini-2.5-flash | 10/11 | +0.136 | -0.062 | -0.119 |
| qwen3.6-27b-fp8 | 10/11 | +0.125 | -0.044 | -0.068 |

## Group contrast (computed above, read jointly)

- **memory-without-trigger** (llama-70b-awq, qwen3-30b-a3b): per-date
  recall exists (REC-yr ~18%, LAP-hit ~67%) but high-recall dates show
  no trigger elevation (frac-diff -3.5% / +7.6%), and mean T on the crisis
  dates themselves stays near the calm baseline (-0.080 / +0.045).
  Recall identified per-date does not translate into date-triggered
  bearishness anywhere for these models.
- **triggered** (gemini-2.5-flash, qwen3.6-27b-fp8): the trigger is
  crisis-concentrated, not recall-general — mean T on crisis dates (+0.136 / +0.125)
  sits far above both the calm baseline and the mean over high-recall
  *non-crisis* dates (-0.062 / -0.044). Generic per-date recall alone is not
  sufficient; the elevation appears where recall coincides with crisis
  semantics (gemini: 10/11 crisis dates are high-recall).
- The raw high-vs-low frac-diff is not interpretable for
  gemini-2.5-flash: its low-recall cell has only 13 dates and its calm
  baseline is deeply negative (D less bearish than M on calm dates), so
  'above baseline' is a low bar met by most dates in both strata.

## Caveats

- **qwen3-30b-a3b-fp8dyn is single-rep (1 arm rep, 10 LAP reps):** its
  per-date trigger primitive is a difference of two 8-sketch shares, so
  date-level values are quantized to eighths and noisy; treat its
  quadrant fractions as indicative only. All other models pool 2-3 reps.
- Ties / all-unknown LAP dates drop from the recall-hit metric per the
  frozen recipe: recall_n 222/240 (llama-70b), 224/240 (qwen3-30b),
  211/240 (gemini-2.5-flash), 235/240 (qwen3.6-27b) — expected, matches
  the frozen row jsons exactly (asserted in-script). Dropped dates can
  still qualify as high-recall via REC year-hit.
- Per-date REC is a single probe call per date (frozen design); the
  year-hit indicator at date grain is therefore itself a 1-draw sample.
- Exploratory, post-freeze: no preregistered hypothesis at date grain;
  windows (11 crisis / 36 calm dates) and all recipes are frozen ones.
