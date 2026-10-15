# BM-2c addendum: base-rung elicitation replaced after a degenerate smoke (pre-run)

Frozen before any call under the new regime. Amends BM2c_prereg_olmo_ladder.md
(afa19e6d) condition 2 (base-2shot) and condition 3 (instruct-2shot).

## What the smoke showed (2026-09-14 00:26, `outputs/bench/olmo3-7b-base-2shot/`)

The preregistered base-2shot regime (BM-2b, exemplars fb0e0c14) is degenerate on
`allenai/Olmo-3-1025-7B`: all 8 smoke cells (2 dates x 4 arms) return the two
exemplars' sketches nearly verbatim — direction pattern `+-+-+-+-` in every cell
(the exemplars' balanced 4/4 layout), only 4 distinct response hashes across
the 8 cells, identical byte length (6405) in 7 of 8. VALID is 100%, so the
BM-1b compliance gate (VALID < 50%) does not fire, but the direction field is
copied from the prompt rather than produced by the model, and every arm
contrast on it would be identically zero by construction. The smoke cells are
kept on disk as the record; no full run was made under this regime. (BM-2b
never reached its base condition — Stage 1 was KILL — so this failure mode was
not observed before.)

## Replacement regime: guided zero-shot completion

- Prompt bytes: `system + "\n\n" + user + "\n\nOutput:\n"` — the frozen BM-1 arm
  prompt with **no exemplars** (nothing in the prompt can be copied).
- Decoding: vLLM structured outputs (`structured_outputs.json`) constrained to
  a JSON array of exactly 8 sketch objects carrying the fields the frozen system
  prompt already demands (`SKETCH_SCHEMA` in `run_bm2b_stage2.py`); `direction`
  is grammar-restricted to `+`/`-`, `candidate_proxies` to the eight series IDs.
  The grammar is a superset of `validate_sketches` (never relaxes it) and does
  not touch the scoring path. Temperature 0.2, max_tokens 8192, `/v1/completions`.
- LAP probe under this regime: the frozen LAP prompt with the answer
  grammar-restricted to `up`/`down`/`unknown` (20-sample frequency estimate
  unchanged in construction; 10 reps at the 1-rep tier as in row 15).
- Applied to **A0 (base)** and, as the controlled comparator, to **the released
  Instruct A3 under the identical prompt bytes and grammar ("A3x", output dir
  `olmo3-7b-instruct-guided`)**. The instruct-2shot condition is dropped; the
  chat conditions A1–A4 are unchanged.

## Readings (replace prereg readings (i)–(iii) for the base contrast)

The contrast of record is A0-guided vs A3-guided (same regime):
- (i) both trigger, CIs overlap -> corpus-borne;
- (ii) A3-guided triggers, A0-guided CI includes 0 -> installed by post-training
  (stage located by the chat ladder A1–A3);
- (iii) A3-guided does not trigger although A3-chat does -> the guided
  completion regime suppresses the trigger and the base contrast is **not
  identified**; reported as such, chat ladder still reported;
- (iv) as before (non-monotone -> no stage named).

Degeneracy gate for the new regime, decided on the smoke before the full run:
at least 5 distinct direction patterns across the 8 smoke cells **and** at
least one cell whose bearish share differs from 4/8. Failing it, the base rung
is reported as unmeasurable under both regimes and no third regime is tried.

## Ladder B

The same replacement applies to B0 (`allenai/Olmo-3-1125-32B`) if ladder B runs.
