# BM-2c note: post-hoc manual inspection of the F1 smoke cells (R1-Distill-Llama-70B AWQ, TP=4 on A100)

Written 2026-09-22 after the automatic pre-screen (8/8 cells, 8 valid sketches each) let the full run
start; the inspection is post hoc as for D1/D2/E1 (BM2c_note_D1_inspection.md). Cells pulled to the
Mac and read: R/D/M/W x {2008-10-15, 2014-04-15}, rep 1.

- Every cell parses to exactly 8 schema-valid sketches after the tokenizer fix (BM2c_note_F_serving.md);
  the first, discarded smoke had produced byte-level mojibake from mangled prompts, none of it counted.
- Think blocks 2.2-3.4k characters in every arm; the JSON array follows the closing think tag and is the
  last standalone array, which the runner's parser takes (untagged-preamble rule unchanged).
- No cell names a crisis, an institution or a year in the response text (searched: 2008, Lehman,
  financial crisis, subprime, 2014, taper, QE, pandemic, COVID). Regime hints are generic ("economic
  downturn", "monetary easing cycle", "housing market downturn").
- Directions: 2008-10-15 D +---+++- (3/8 bearish) vs M +---+--- (6/8); 2014-04-15 D ++++++++ vs M +-+-+-+-.
  One replicate; not read for the estimand. Sketches are date-conditioned in content (the 2008 R cell
  writes a monetary-easing regime with a housing-downturn narrative) without explicit recall.
- Verdict: PASS (manual). No exclusion. The gate outcome does not change the frozen protocol.
