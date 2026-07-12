# FM-1e Preregistration: Trigger Decomposition — Bare Date vs Retrospective Framing

Status: FROZEN before any API call (sha256 in `FM1e_freeze.json`).

## Motivation (design-level review, 2026-07-10)

The frozen D arm carries the date inside a temporal-admissibility clause
("Decision time point: YYYY-MM-DD - only information available on or before
this date is admissible as evidence"), while M carries a source-admissibility
clause ("[undisclosed]. Only information contained in this snapshot is
admissible as evidence"). E2 = Gap(D) − Gap(M) therefore identifies the
effect of {date token + temporal-retrospective phrasing}, not the date token
alone. This ablation decomposes the trigger.

## Design

Base prompt: the frozen M transform of each node (identical masking code
path). Two new variants replace M's date line:

- **D-bare**: `Decision time point: {true_date}.` (no admissibility tail)
- **D-snap**: `Decision time point: {true_date}. Only information contained
  in this snapshot is admissible as evidence.` (M's own source clause +
  date — isolates the date token holding the clause family fixed)

Window: the 47 preregistered window dates (11 crisis + 36 calm 2013/14/17).
1 rep × 8 sketches, temperature 0.2, max 8,192 tokens,
`models/gemini-2.5-flash` (identical to FM-1), FM-1 validator, parser v2
conventions. Reference quantities from the FROZEN FM-1 arms restricted to
the same 47 dates: Gap(D), Gap(M).

## Estimands

- E2_bare = Gap(D-bare) − Gap(M);  E2_snap = Gap(D-snap) − Gap(M)
- Reference: E2_win = Gap(D) − Gap(M) on the same 47 dates
- Paired date-level bootstrap, B = 10,000, seed = 2026.

## Decision rule (frozen before data)

- If E2_snap's 95% CI excludes 0 **and** E2_snap ≥ E2_win − 10pp
  (the FM-1c equivalence-band convention): the date token alone triggers;
  the "date token as unauthenticated pointer" mechanism wording stands.
- If E2_snap's CI includes 0 (or falls > 10pp below E2_win): the trigger is
  conditioned as *date-under-retrospective-framing*; §5's mechanism sentence
  and the abstract's wording are qualified accordingly.
- E2_bare is reported either way (secondary: clause-free floor). All three
  numbers are published regardless of outcome.

## Execution gates

Smoke = 2 dates × 2 variants with manual inspection, ledger-based cost
extrapolation against the approved ~$5 envelope before full volume
(llm_batch_ops discipline). Outputs under `outputs/fm1e/`, idempotent
per-cell resume, usage to the gemini ledger.
