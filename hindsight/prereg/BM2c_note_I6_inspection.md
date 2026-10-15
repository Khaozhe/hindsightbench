# BM-2c note: post-hoc manual inspection of the I6 smoke cells (Qwen3-30B-A3B-Thinking-2507, FP8 block-128 official, TP=2 on A100)

Written 2026-09-24 after the row finished and was pulled (addendum I d62eb2e0; auto pre-screen passed at run time).
Serving details in BM2c_note_I_serving.md (TP=2 per deviation note bfe0a729; Marlin Fp8 MoE backend).
Cells read: R/D/M/W x {2008-10-15, 2014-04-15}, rep 1.
- Every cell has a closed reasoning trace (`</think>` present) and parses to 8 schema-valid sketches; raw
  responses 21.5-36.4k characters, final answers 6.0-6.8k.
- No four-digit year 1980-2029 and no named crisis event (Lehman, Bear Stearns, subprime, financial crisis,
  Great Recession, COVID, pandemic, taper) in any final answer.
- Directions (+/-): R 7/1 and 1/7, D 3/5 and 7/1, M 1/7 and 5/3, W 1/7 and 7/1 (2008-10 and 2014-04).
- **Row-level facts**: 1032/1032 cells with a valid-sketch file, every cell exactly 8 valid sketches, no
  truncation, no CELL_ERROR; no resume pass needed.
- Verdict: PASS (manual). No exclusion.
