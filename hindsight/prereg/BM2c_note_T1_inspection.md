# BM-2c note: post-hoc manual inspection of the T1 smoke cells (Tulu 3 70B SFT, FP8 W8A16 Marlin, TP=4 on A100)

Written 2026-09-23 after the automatic pre-screen (8/8 cells with >= 4 valid sketches) let the full
run start. Cells pulled to the Mac and read: R/D/M/W x {2008-10-15, 2014-04-15}, rep 1.

- Every cell parses to exactly 8 schema-valid sketches; responses 5.4-5.7k characters, no think block
  (SFT model, plain JSON after a short preamble).
- No cell names a crisis, an institution or a year (searched: 2008, Lehman, financial crisis, subprime,
  2014, taper, QE, pandemic, COVID, recession). Regime hints are generic and, notably, nearly the same
  across arms and dates ("inflationary pressure", "tight labor market", "economic downturn"): the SFT
  checkpoint writes a template-like set regardless of date, which is what a weak date conditioning
  looks like. One replicate; not read for the estimand.
- Directions: 2008-10-15 D ---++--- (6/8 bearish) vs M --+--++- (5/8); 2014-04-15 D -++-++-- (4/8) vs M
  --+-++-- (5/8).
- Serving: first rung on the Marlin W8A16 path after the Cutlass failure (BM2c_note_F_serving.md); no
  earlier smoke cells existed for T1 (the three failed launches died before any request).
- Verdict: PASS (manual). No exclusion.
