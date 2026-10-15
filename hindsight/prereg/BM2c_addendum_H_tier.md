# BM-2c addendum H: does control C survive a change of serving tier?

Frozen 2026-09-24 before any call on the two checkpoints below. Extends BM2c_prereg_olmo_ladder.md
(afa19e6d) and addenda D-G (G: c7e04919). Nothing already frozen changes.

## Why

Addendum F's preregistered cross-tier check put one checkpoint (Tulu 3 70B RLVR, cfc1d855) in two
serving tiers on the same A100 box: FP8 W8A16 (T3) E2 -3.2 [-11.4, +5.6], G2 t = -0.39; AWQ INT4 (F3)
E2 +26.5 [+11.9, +40.9], G2 t = +2.47. Chat template, source checkpoint and generation defaults were
verified identical. The same-date paired difference is +29.7 [+14.3, +45.3] pp. Every row on the
Llama 3.1 70B base that triggers (Llama 3.3 +16.0, Nemotron +9.8, F3 +26.5) was served AWQ; every FP8
row on that base is null. Control C ("the 2024-12 recipe installs the reflex on a fixed corpus": Llama
3.1 70B Instruct AWQ -4.7 vs Llama 3.3 70B Instruct AWQ +16.0) was measured entirely in the AWQ tier.
This addendum re-measures both control-C checkpoints in the FP8 tier.

## Design

| rung | checkpoint | serving |
|---|---|---|
| H1 | Llama 3.3 70B Instruct: `unsloth/Llama-3.3-70B-Instruct` (99cd0d2c; 30/30 safetensors shards SHA-256-identical to meta-llama/Llama-3.3-70B-Instruct) | BF16 weights, vLLM 0.29 online FP8 (Marlin W8A16, Cutlass FP8 disabled), TP=4, 4 x A100-40G, exactly as T1-T3 |
| H2 | Llama 3.1 70B Instruct: `unsloth/Meta-Llama-3.1-70B-Instruct` (1fdd0a46; 30/30 shards identical to meta-llama/Llama-3.1-70B-Instruct) | same |

Chat template (sha e10ca381) and generation defaults are identical to the AWQ repos behind the frozen
control-C rows. Prompts, sampling (temperature 0.2, 1 replicate, arm_max_tokens 8192), probes, gates,
bootstrap, smoke (automatic pre-screen, post-hoc manual inspection) and the one-pass resume rule are
the control-C protocol unchanged. Memory clause: addendum F's (post-LAP <= .1 and hit > 65.5% on
>= 100 answered probes); a row failing it is reported as measured with no reading.

**Disclosed confound.** The AWQ control-C rows ran on the H800 (vLLM 0.29); H1/H2 run on the A100s
(vLLM 0.29). For the Llama pair, tier and hardware change together; only the Tulu pair (T3/F3, both
A100) isolates the tier.

## Readings (frozen; computed with E2 and with G2 side by side, as addendum G requires)

Control C in the FP8 tier:
- H1 triggers and H2 does not -> **control C survives the tier change** (recipe contrast reproduced).
- H1 does not trigger -> **control C is tier-dependent**: the Llama 3.3 trigger is not reproduced
  outside the AWQ tier; the paper reports control C as a tier-conditional result.
- H1 and H2 both trigger -> the reflex is present on both recipes in this tier; the recipe contrast
  is not reproduced.
- If E2 and G2 disagree, both are reported and the disagreement is the finding.

Tier contrast per checkpoint (AWQ row minus FP8 row, same-date paired bootstrap on E2; G2 difference
by HAC-6 regression of the per-date difference): reported for Llama 3.3 (C minus H1) and Llama 3.1
(C-ref minus H2) alongside the Tulu pair. Because paired tests on same-model replicate pairs flagged
1 of 5 (E2) and 2 of 5 (G2) as significant, a tier difference is called **beyond the observed noise
floor** only if its paired E2 CI excludes zero **and** its magnitude exceeds 16.2 pp, the largest
same-model replicate-pair difference observed (Gemini 2.5 Flash rep2 minus rep3).

## Cost

About 5-6 GPU-hours on the existing allocation (282 GB of downloads on the login node, then two rungs).
No API spend.
