# BM-2c note: serving record for the addendum-J rungs (started 2026-09-24, written during the run)

Addendum J (3f0e61d8) fixed rungs, channels and readings. Same box and stack as T3/F3: 4 x A100-SXM4-40GB,
TP=4, vLLM 0.29.0, CONC 16, max_model_len 24576, gpu util 0.92, arm_max_tokens 8192.

## Weight downloads (before any J cell)

- T3's and F3's weights had been deleted after their rows (driver default), so both were re-downloaded at
  the frozen revisions (782516fd, cfc1d855; the driver now refuses any other revision).
- The first J1 attempt failed on shard 1 (aria2); a separate J1 retry loop was started while the original
  prefetch loop moved on to J2. When that loop's second pass reached J1, **two aria2 processes wrote shard 2
  of the AWQ weights at the same time** (22:47 CST). Both loops were stopped by PID, shard 2 and its control
  file were deleted, and one download loop per weight set was restarted (23:15 CST).
- The driver checks byte sizes only, which cannot detect an interleaved write. `scripts/verify_weights_sha.py`
  (added then, an operational check outside the frozen analysis) compares every shard with the sha256 the HF
  API lists. **AWQ weights: 9/9 shards match (SHA_VERIFY_PASS, 00:06 CST 09-25)**, before J1's first call.
  The BF16 weights for J2 are verified the same way when their download ends.

## Rungs

- **J1 (AWQ weights, bf16 activations)**: `--quantization awq_marlin --dtype bfloat16` accepted. Engine config
  dtype=torch.bfloat16, quantization auto_awq, "Using MarlinLinearKernel for AutoAWQMarlinLinearMethod" -- the
  same method and kernel as F3, whose engine ran dtype=torch.float16. Activation dtype is the only difference.
  Server healthy 00:06:59 CST, auto smoke 8/8 cells, full run from 00:07; about 790 generation tokens/s at
  16 running requests.
  Finished 01:01 CST (RUNG_DONE J1): 1032/1032 cells, every cell 8 valid sketches, no CELL_ERROR, no
  truncation; no resume pass needed.
- **J3 (F3 second run, AWQ fp16)**: same weights directory as J1 (verified 9/9). Engine dtype=torch.float16,
  quantization auto_awq, MarlinLinearKernel for AutoAWQMarlinLinearMethod (identical to F3). Full run from
  00:52 CST, RUNG_DONE ~01:37 CST: 1032/1032 cells, every cell 8 valid sketches; no resume pass needed.
- **J2 (T3 second run)**: BF16 weights re-downloaded (one aria2 failure on shard 15, retried by the single
  loop); **sha256 30/30 shards match (SHA_VERIFY_PASS, ~01:19 CST)** before J2's first call. Engine
  dtype=torch.bfloat16, quantization fp8, MarlinFP8ScaledMMLinearKernel for Fp8PerTensorOnlineLinearMethod
  (identical to T3). Auto smoke passed 01:37:57 CST; full run from then, about 650 generation tokens/s at 16
  running requests.
  RUNG_DONE J2 02:29:23 CST 09-25: 1032/1032 cells, every cell 8 valid sketches, no CELL_ERROR, no
  truncation; no resume pass needed (the chain's resume step found no rung below 1,032 cells).

## Rows and frozen readings

All three rows were pulled with tar over ssh (J1, J3 on 09-25 early CST; J2 after RUNG_DONE) and recounted
locally: 1032 cells with exactly 8 valid sketches and zero `99_*` files in each. The frozen script
(`analyze_tier_split.py` a62b272a, importing `analyze_dose_response.py` bc8a600f; hashes re-checked before
the run) was run once; output verbatim in `outputs/bench/TIER_SPLIT_J.txt`:
- floors: E2 21.5 (J3-F3), DATE 6.8; BASE UNSTABLE (J3-F3 BASE -3.9 [-6.3, -1.5] is itself significant, so
  no BASE reading is made).
- R1: the AWQ-fp16 minus FP8 E2 contrast does not replicate (J3-J2 E2 +0.8 [-18.8, +21.3]).
- R2 DTYPE and R3 WEIGHTS: neither is beyond the floor against both reference runs.
- Frozen conclusion: the +29.7pp tier contrast neither replicates nor is attributable to dtype or weights.
