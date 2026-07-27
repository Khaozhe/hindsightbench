# Cross-model E1 = Gap(R) - Gap(D) (2026-07-26 pre-deadline audit)

POST-FREEZE EXPLORATORY (2026-07-26). Frozen bench arms, zero new API calls. Estimator identical to analyze_bench_row (boot_diff, B=10000, seed 2026).

Anchors PASSED: flash E1 = -0.033670 (paper -3.4pp); gpt-5.4-mini gap_D = 0.119476 (frozen row json); rep-matched pro E1 = -0.011679 (paper -1.2pp).

Replicate parity enforced (E1 is a within-batch contrast). Rows restricted to the reps their two arms share: gemini-2.5-pro (R ['rep1'] vs D ['rep1', 'rep2', 'rep3'] -> ['rep1']).

| model | gen | Gap(R) | Gap(D) | E1 (pp) | CI95 (pp) | sig |
|---|---|---|---|---|---|---|
| GPT-5.5 | 2026 | 0.251 | 0.259 | -0.8 | [-10.1, +7.8] |  |
| Claude Sonnet 5 | 2026 | 0.320 | 0.361 | -4.1 | [-11.0, +2.8] |  |
| Kimi-K2.6 | 2026 | 0.347 | 0.459 | -11.2 | [-18.8, -4.2] | YES |
| Qwen3.6-35B-A3B | 2026 | 0.167 | 0.208 | -4.1 | [-15.1, +6.9] |  |
| Qwen3.6-27B | 2026 | 0.197 | 0.158 | +4.0 | [-3.4, +12.0] |  |
| GPT-5.4-mini | 2026 | 0.313 | 0.119 | +19.4 | [+11.3, +27.1] | YES |
| Claude Haiku 4.5 | 2025 | 0.308 | 0.371 | -6.3 | [-13.4, +0.7] |  |
| DeepSeek v4-flash | 2025 | 0.399 | 0.386 | +1.2 | [-7.9, +10.8] |  |
| Gemini 2.5 Flash | 2025 | 0.281 | 0.315 | -3.4 | [-11.6, +4.9] |  |
| Gemini 2.5 Pro | 2025 | 0.196 | 0.208 | -1.2 | [-13.4, +11.5] |  |
| Qwen3-30B-A3B | 2025 | 0.135 | 0.086 | +5.0 | [-7.5, +17.7] |  |
| Llama 3.1 70B | 2024 | 0.036 | -0.037 | +7.3 | [-1.2, +15.3] |  |
| Llama 3.1 8B | 2024 | -0.016 | 0.035 | -5.2 | [-15.0, +5.4] |  |
| Llama 3.2 3B | 2024 | 0.122 | 0.056 | +6.6 | [-16.0, +30.6] |  |
| Llama 3.2 1B | 2024 | -0.024 | 0.007 | -3.0 | [-25.7, +24.0] |  |

Estimated on 15 models; 2 significant; signs 6 positive / 9 negative.
- **Kimi-K2.6**: E1 -11.2pp [-18.8, -4.2], against its own E2 +33.2pp
- **GPT-5.4-mini**: E1 +19.4pp [+11.3, +27.1], against its own E2 +14.4pp
