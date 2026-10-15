# deepseek-v4-flash ST-1 row: disclosed deviations (2026-10-13)

1. **Probe thinking regime.** Arms: endpoint default (reasoning on, max_tokens 16384). LAP-ST and REC-ST:
   `thinking: {"type": "disabled"}`. Reason: with reasoning on, LAP-ST truncated at 8192 in 63% of calls
   (267 truncated / 460 attempted, two chunks), i.e. the probe was non-convergent in that regime; the July 2026
   BM-1 run of the same alias averaged 258 reasoning tokens on the macro LAP. 243 reasoning-on LAP answers
   collected before the switch are kept in `lap_results_reasoning_on_partial_DISCARDED.jsonl` and not used.
   Endpoint reports model id `deepseek-flash` (platform banner: V4.1-Flash released); alias drift is possible.
2. **Account switch mid-row** (`KEY_SWITCH_NOTE.json`): arm cells 1-1466 billed to one DeepSeek account,
   the remaining 84 arm cells + all probes to another. Same endpoint, model alias and generation config.
3. **One parse error** (S arm, singapore_2021-12): malformed JSON from the model; cell absent (S coverage 309/310).
4. **max_tokens for arms raised 8192 -> 16384** after 5 truncations in the first chunk (BM-1 convention for
   reasoning APIs); the 5 cells were regenerated under 16384.
