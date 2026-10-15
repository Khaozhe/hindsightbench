# BM-2c note: post-hoc manual inspection of the I7 smoke cells (Qwen3-30B-A3B-Thinking-2507, BF16 weights served --dtype float16, TP=4 on A100)

Written 2026-09-24 after the resume pass finished and the row was pulled (addendum I d62eb2e0).
Serving details in BM2c_note_I_serving.md (first pass 1029/1032; one resume pass regenerated the three failed cells).
Cells read: R/D/M/W x {2008-10-15, 2014-04-15}, rep 1.
- Every cell has a closed reasoning trace (`</think>` present) and parses to 8 schema-valid sketches; raw
  responses 26.6-34.7k characters, final answers 5.8-7.0k.
- One year in a final answer (R 2008-10-15: "2017"), a unit echo of the prompt's series definitions; no named
  crisis event (same term list as I6) in any final answer.
- Directions (+/-): R 1/7 and 3/5, D 3/5 and 4/4, M 3/5 and 3/5, W 3/5 and 3/5 (2008-10 and 2014-04).
- **Row-level facts**: after the resume pass 1032/1032 cells with a valid-sketch file, every cell exactly 8
  valid sketches; the three first-pass failures (M 2013-01, M 2013-02, W 2013-02; empty CELL_ERROR, not
  truncation) regenerated. The parity gate no longer fires.
- Verdict: PASS (manual). No exclusion.
