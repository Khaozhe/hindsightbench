# BM-2c note: post-hoc manual inspection of the I2 smoke cells (Qwen3-30B-A3B-Thinking-2507, AWQ INT4 QuantTrio, TP=4 on A100)

Written 2026-09-24 after the row finished (addendum I d62eb2e0; auto pre-screen passed 8/8 at run time).
Serving details in BM2c_note_I_serving.md (reference chat template copied in; MoE experts on the WNA16 fallback kernel).
Cells read: R/D/M/W x {2008-10-15, 2014-04-15}, rep 1.
- Every cell has a closed reasoning trace (`</think>` present, so the copied template's forced `<think>` prefix
  is in effect) and parses to 8 schema-valid sketches; raw responses 28-54k characters, final answers 6.1-6.8k.
- Years in final answers occur only as unit echoes of the prompt's series definitions (CPI "1982-1984=100",
  industrial production "2017=100", real GDP "billions of 2017 dollars"); no named crisis event in any answer.
- Directions mixed except D at both dates (1 of 8 bullish); M at the same dates is mixed (4 of 8 at both).
- **Row-level facts found after the run** (whole row, not only smoke cells):
  - 8 cells lost to truncation: the reasoning exhausted arm_max_tokens 16384 (finish_reason=length), a
    deterministic failure logged as CELL_ERROR and not retried, per protocol. Missing: R 2007-09, 2007-11,
    2022-01, 2024-06; D 2011-03, 2019-07; M 2006-09; W 2023-12. None is in the E2 crisis or calm window, so
    E2/E3 coverage is complete and no parity gate fires; G2/DATE use 225 of 228 window dates (>= 200).
    I1 (BF16) lost no cell to truncation.
  - One R-arm cell (2014-08-15) returned 9 schema-valid sketches instead of 8, which is why the row's
    VALID sketch_rate reads 1.0001 (valid / expected). The R arm enters no addendum-I channel.
- Verdict: PASS (manual). No exclusion.
