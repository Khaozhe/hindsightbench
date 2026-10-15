# BM-2c note: post-hoc manual inspection of the I1 smoke cells (Qwen3-30B-A3B-Thinking-2507, BF16, TP=4 on A100)

Written 2026-09-24 after the row finished (addendum I d62eb2e0; auto pre-screen passed 8/8 at run time).
Cells read: R/D/M/W x {2008-10-15, 2014-04-15}, rep 1.
- Every cell has a closed reasoning trace (`</think>` present) and parses to 8 schema-valid sketches; raw
  responses 22-45k characters, final answers 5.8-6.7k. Row: 1032/1032 cells, 0 parse-error cells.
- No calendar year and no named crisis event (Lehman, subprime, GFC, COVID, pandemic, TARP, lockdown,
  Great Recession) in any final answer.
- Directions mixed (1-5 of 8 bullish per cell); no arm or date is degenerate.
- Verdict: PASS (manual). No exclusion.
