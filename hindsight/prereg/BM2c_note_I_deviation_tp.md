# BM-2c note: addendum-I serving deviation for I4 and I6 (tensor-parallel degree), written before any I4/I6 cell

Written 2026-09-24, after I1-I3 finished and before any I4, I5, I6 or I7 cell exists. Addendum I (d62eb2e0)
fixed TP=4 for every rung and said any serving fallback is recorded and no rung is dropped silently.

**What failed.** I4 (RedHatAI w4a16, group size 128) did not start at TP=4: vLLM 0.29 raised
"CompressedTensors WNA16 MoE with static group scales requires the MoE intermediate size per tensor-parallel
partition (192) to be divisible by group_size (128)". The checkpoint's moe_intermediate_size is 768; 768/4 = 192.
I6 (Qwen official FP8, weight_block_size [128, 128]) has the same constraint and would fail the same way.
I5 (INT8 per-channel) and I7 (BF16) have no group or block constraint. The chain aborted at I4 as designed;
I5-I7 had not started.

**Deviation (decided before any of these cells exists).**
- I5 and I7 run as frozen: TP=4 on 4 x A100-40G.
- I4 and I6 run at **TP=2** (768/2 = 384 = 3 x 128) on two of the same allocation's A100-40G cards, same vLLM,
  same box, same sampling and token budgets. Both checkpoints fit (about 17 GB and 31 GB of weights on 80 GB).
- Tensor-parallel degree changes only the order of floating-point reductions. The same-box replicate pair
  already measured on this checkpoint (I3 minus I1: E2 -21.5 pp) bounds run-to-run variation of this kind
  from above; TP-induced differences are not separated from it and are not claimed to be.
- Readings are computed exactly as frozen; the I4 and I6 lines carry "TP=2" in every table and in the paper.
  If a rung still cannot be served at TP=2 it is reported as missing.
- Order: I5, I7 (TP=4), then I4, I6 (TP=2).
