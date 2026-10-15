# BM-2c note: serving environment for the addendum-F rungs (written 2026-09-22, before any call)

Addendum F (6517a57b) fixed the checkpoints, estimands and memory clauses. This note records the
serving environment actually used, which differs from the H800 rows in three disclosed ways.

- **Machine**: a Slurm allocation of 4 x A100-SXM4-40GB (NVLink NV12 mesh, driver 595.58.03,
  CUDA 13.2) on the wbx cluster; login node sn02 has internet (hf-mirror), the compute node does
  not; home is a shared parallel filesystem (/data). Weights are downloaded on the login node and
  served from the shared filesystem. vLLM 0.29.0 in a dedicated venv (~/vllm029), the same
  version as every H800 row.
- **Tensor parallelism TP=4** for every rung (the addendum said TP=2 for the Tulu/Hermes rungs on
  80 GB cards; on 40 GB cards all six rungs need four cards). A serving detail; recorded per row.
- **FP8 kernel path**: A100 has no native FP8 tensor cores, so vLLM's `--quantization fp8` runs the
  Marlin weight-only path (W8A16: 8-bit weights, bf16 activations) instead of the W8A8 path used
  for the row-15 tier on the H800. The Hermes official FP8 checkpoint is served the same way.
  This is numerically closer to BF16 than the H800 FP8 tier. Tier labels in the table stay
  `fp8dyn` / `fp8` with this note referenced; no correction is applied. AWQ rungs (F1, F3) use
  awq_marlin exactly as controls C and E did.
- **Order**: F1 first (smallest download, GPU starts earliest), then T1 T2 T3 F2 F3.

## Incidents before the first valid F1 call (2026-09-22, all before any counted cell)

1. torch.compile failed with `PermissionError: 'nvcc'` (inductor needs the CUDA toolkit on PATH; the
   node has none by default) -> launcher exports the cluster's cuda/13.0 toolkit.
2. Four TP workers racing on one Triton cache on the shared filesystem -> `cuda_utils.so: cannot open
   shared object file`; caches moved to node-local /tmp.
3. **Tokenizer**: the AWQ repo's tokenizer_config names `LlamaTokenizer`; under transformers 5.17 that
   class applied to this byte-level BPE tokenizer.json drops spaces on encode and emits raw byte-level
   symbols (Ġ/Ċ) on decode. The first smoke produced 8/8 unparseable cells from mangled prompts; those
   cells were discarded. Fix: `tokenizer_class` -> `PreTrainedTokenizerFast` (generic fast tokenizer on
   the unchanged tokenizer.json; round-trip verified). Weights, tokenizer.json and the repo's chat
   template are untouched; the upstream DeepSeek template differs only by a forced `<think>` prefix and
   is not used. Note kept next to the weights (TOKENIZER_NOTE.txt) and the original config in
   `_awq_tokenizer/`. Second smoke: 8/8 cells, 8 valid sketches each.

## FP8 kernel on the A100s (2026-09-23, before the first T1 call)

vLLM 0.29 selected `CutlassFP8ScaledMMLinearKernel` for the online-FP8 rungs even on sm80 and died at
profiling (`cutlass_scaled_mm_sm80_epilogue`); with torch.compile on, the failure surfaced earlier as
`AssertionError: auto_functionalized was not removed`. Setting `VLLM_DISABLED_KERNELS=CutlassFP8ScaledMMLinearKernel`
makes it select `MarlinFP8ScaledMMLinearKernel` (weight-only FP8, bf16 activations), which compiles and
serves (health check and a test completion verified). So the T1-T3 and F2 rows are **W8A16** FP8, as
anticipated above; the per-tensor dynamic weight quantisation is the same as the H800 rows', the
activation precision is higher. KV cache 17.6 GiB across 4 x 40 GB at util 0.92 (9.4 concurrent
24k-token requests); client concurrency 16 with the 3,600 s timeout.
