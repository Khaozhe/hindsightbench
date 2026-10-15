# BM-2c note: serving record for the addendum-I rungs (started 2026-09-24, written during the run)

Addendum I (d62eb2e0) fixed checkpoints, channels and readings. This note records what the serving stack
actually did, rung by rung, as each rung starts. Same box and stack as addenda F/H: 4 x A100-SXM4-40GB,
TP=4, vLLM 0.29.0, max_model_len 24576, concurrency 32, arm_max_tokens 16384.

- **I1 (BF16)**: 04:46-06:19 CST, 1032/1032 cells, auto smoke passed (8/8). Generation throughput
  roughly 1,200-2,700 tokens/s at 14-32 running requests.
- **I2 (AWQ, QuantTrio)**: `--quantization awq_marlin --dtype bfloat16` accepted (no fp16 fallback needed).
  Dense linear layers use MarlinLinearKernel. **The MoE expert layers are not supported by
  AutoAWQMoEMarlin in vLLM 0.29 for this checkpoint; vLLM falls back to the MoE WNA16 kernels** (log:
  "Layer 'model.layers.0.mlp.experts' is not supported by AutoAWQMoEMarlin. Falling back to Moe WNA16
  kernels."). The weights and their 4-bit group-128 zero-point format are unchanged; only the matmul
  kernel for the experts differs. Consequence: generation throughput about 650 tokens/s at 32 running
  requests, about a third of I1; the rung takes about 5 h instead of 1.5 h. Recorded as a serving detail
  of the AWQ tier on this checkpoint; no reading is conditioned on it. Chat template: reference repo's
  template copied in before serving (TEMPLATE_NOTE.txt in the model dir), per the addendum.
- **I3 (BF16 second run)**: 1032/1032, no truncation.
- **I4 (GPTQ w4a16)**: failed to start at TP=4 (group-size divisibility; see BM2c_note_I_deviation_tp.md,
  bfe0a729); re-run at **TP=2** from 16:04 CST: "Using 'MARLIN' WNA16 MoE backend", smoke passed,
  about 1,650 tokens/s at 32 running requests.
- **I5 (INT8 w8a8)**: TP=4, CutlassInt8ScaledMMLinearKernel, 1032/1032 (13:25-14:39 CST).
- **I7 (BF16 weights, --dtype float16)**: TP=4, 1029/1032: three cells failed with empty CELL_ERROR messages
  (not truncation): M 2013-01, M 2013-02, W 2013-02, all calm-window dates. The row's sample-parity gate
  therefore voids E2 and E3. Per BM2c_note_retry.md (one resume pass for any rung below 100% compliance),
  I7 and I2 get one resume pass at their original TP=4 after I4/I6 finish
  (scripts/bm2c_chainI_resume.sh; weights re-downloaded on the login node).
- **I6 (FP8 block-128)**: TP=2 (same divisibility constraint as I4; deviation note bfe0a729): "Using 'MARLIN' Fp8
  MoE backend" (A100 has no native FP8 matmul, so the block-FP8 weights run through Marlin W8A16), smoke
  passed, about 1,440 tokens/s at 32 running requests, 1032/1032 cells.
- **Resume passes (2026-09-24, ended 20:56 CST; ladder.progress: RETRIED-OK I7, RETRIED-OK I2)**: TP=4, same
  flags as the first pass. I7: the three failed cells regenerated, 1032/1032, so the row's parity gate no
  longer fires and E2/E3 are identified. I2: the resume pass regenerates every cell without a valid-sketch
  file, which mechanically includes the 8 cells truncated in the first pass; all 8 completed (1032/1032).
  This departs from the I2 inspection note's "not retried, per protocol" (the within-run rule does not
  retry truncation; the one-pass resume rule, BM2c_note_retry.md, regenerates any missing cell). None of
  the 8 is in an E2 window; I2's DATE t moved 2.44 -> 2.43 and BASE 59.9 -> 60.0. Recorded, not reverted.
