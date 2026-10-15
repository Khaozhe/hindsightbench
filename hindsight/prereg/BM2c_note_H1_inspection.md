# BM-2c note: post-hoc manual inspection of the H1 smoke cells (Llama 3.3 70B Instruct, FP8 W8A16, TP=4 on A100)

Written 2026-09-24 after the row finished. Cells read: R/D/M/W x {2008-10-15, 2014-04-15}, rep 1.
- Every cell parses to 8 schema-valid sketches (row VALID 100%, 0 parse-error cells of 1032); 5.5-6.1k characters.
- No named crisis, institution or year; the only crisis-adjacent word is one generic "recession" regime hint in the
  leaky R arm. Regime hints are the Llama cycle vocabulary (early-/late-cycle expansion, easing/tightening cycle).
- Directions bullish-heavy in every arm and date (1-3 of 8 bearish), as in the AWQ control-C row.
- Verdict: PASS (manual). No exclusion.
