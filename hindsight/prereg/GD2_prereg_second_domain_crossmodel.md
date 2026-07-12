# GD-2: Second-domain (10Y Treasury) date trigger, cross-model mini panel (prereg)

Frozen before any API call. Extends GD-1 (394c9ad4, flash-only) across models:
the "any time-indexed decision task" claim currently rests on one model's
second-domain evidence.

## Question

Does the date-trigger/transplantation effect port across target assets for
models other than gemini-2.5-flash, with asset-appropriate signs?

## Models (3, chosen ex ante)

- `claude-haiku-4-5` — E3 record holder on SPX (+49.5pp); temp 0.2 (BM-1c);
- `gpt-5.4-mini` — cheapest OpenAI tier; provider-default sampling (BM-1d);
- `deepseek-v4-flash` — third vendor, strongest SPX E2; temp 0.2 (BM-1).

All direct API (no batch: 195 calls/model; avoids queue-scheduling variance).
Max-token settings per each model's BM-1 adapter notes.

## Design

- **Target**: 10-year Treasury yield direction over the next 20 trading days
  (GD-1 frozen target-sentence swap and transforms). One clarifying line pins
  field semantics — "direction '+' means the 10-year yield rises; '−' means it
  falls" — inherited from the GD-1b v2 lesson (semantic instability of the
  direction field on non-equity targets). Disclosed difference vs GD-1 flash,
  which ran unpinned.
- **Window**: the BM-1b reduced 65-date set (all 11 crisis months, all 36
  calm-year months, all 18 post-cutoff months).
- **Arms**: D / M / W × 1 rep × 8 sketches = 195 calls per model. No R arm (E1
  is not an estimand here); no REC/LAP probes (SPX-side probes already
  characterize each model's memory; cost discipline).

## Estimands and decision rule

Sketch-level yield-down share, crisis vs calm windows (pre-cutoff dates):

- **E2_10Y** = [share(down | crisis) − share(down | calm)]_D − [...]_M;
- **E3_10Y** = W-arm crisis−calm contrast under asserted-date vs true-date
  labeling (fake_map inherited frozen);
- paired window bootstrap B = 10,000, seed 2026 (frozen code path).

**Prediction** (from GD-1 + paper 1): all three models show E2_10Y > 0 and
E3_10Y > 0 (crisis → yields down — the flight-to-quality narrative), CI
excluding 0 for at least E3. Any failure is reported as a boundary of the
cross-task claim, not reframed.

**Secondary (disclosed as such)**: post-cutoff subset (18 dates) D−M as a mini
placebo per model, using each model's FROZEN model-relative window from BM-1
where its empirical cutoff intrudes (deepseek 2025-07, mini 2025-09); haiku's
calendar window is valid as-is (cutoff 2024-10).

## Cost (measured-token quote, frozen before spend)

Per-call token means measured from the BM-1 usage ledgers (arms-call stratum):
haiku 2,541 in / 2,278 out → **$2.72**; gpt-5.4-mini 2,209 / 1,647 (incl.
reasoning) → **$1.77**; deepseek (assumed 2.5k/4k, no ledger stratum) →
**$0.29**. Total ≈ **$4.8**; approval envelope with 2× margin: **$11**.
A 2-date smoke per model precedes the full run; if smoke-extrapolated cost
exceeds the envelope, stop and re-quote (standing rule).

## Reporting

Goes to paper 2 (cross-task generality section); per-model GD-2 rows appended
to the artifact. All deviations disclosed per standing policy.
