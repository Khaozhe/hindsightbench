# BM-2c addendum J: splitting the Tulu tier contrast into activation dtype and AWQ weights

Frozen 2026-09-24 before any J weight was downloaded and before any J call. Extends
BM2c_prereg_olmo_ladder.md (afa19e6d) and addenda D-I; nothing already frozen changes. The analysis
script `scripts/analyze_tier_split.py` is frozen with this document; it imports addendum I's estimators
from `scripts/analyze_dose_response.py` unchanged (both hashes in the freeze JSON).

## Why

Addendum F measured one checkpoint, Tulu 3 70B RLVR, in two serving configurations on one A100 box:
T3 (FP8 W8A16 Marlin, bf16 activations) E2 -3.2 pp, F3 (AWQ INT4 awq_marlin, **fp16** activations) E2
+26.5 pp; paired difference +29.7 [+14.3, +45.3], the only tier contrast in the study beyond the 16.2 pp
replicate floor. Addendum I (Qwen3-30B-A3B-Thinking-2507) then found no weight-quantization rung beyond
its same-box floor, while its dtype control (BF16 weights, fp16 activations) was beyond the floor against
the single BF16 reference, and not against the second BF16 run (post hoc). So the Tulu contrast confounds
two changes (4-bit AWQ weights; fp16 activations), and neither original tier has a replicate on this box.
Seen at freeze: the T3 and F3 rows, all addendum I rows and the post hoc I3-referenced contrasts.

## Design (4 x A100-40G, TP=4, vLLM 0.29, CONC 16, max_model_len 24576, gpu util 0.92, arm_max_tokens 8192,
temperature 0.2, one replicate, 258 dates; the T3/F3 serving configuration, BM2c_note_F_serving.md)

| rung | weights (revision) | activations | role |
|---|---|---|---|
| J1 | Valdemardi/Llama-3.1-Tulu-3-70B-AWQ (782516fd), = F3 weights | bf16 (`awq_marlin --dtype bfloat16`) | AWQ weights without fp16 |
| J2 | allenai/Llama-3.1-Tulu-3-70B (cfc1d855), = T3 | bf16, FP8 W8A16 (Marlin) | second run of T3 |
| J3 | = F3 weights | fp16 (`awq_marlin --dtype float16`) | second run of F3 |

Both repos carry tokenizer class PreTrainedTokenizerFast and chat template ac7498a3 (checked at freeze);
no template or tokenizer edit. The driver refuses to download any revision other than the two above.
Order J1, J3, J2 (J2's 141 GB download runs on the login node meanwhile).

## Channels and contrasts

Addendum I's estimators, unchanged: E2 from the row file with its parity gate, contrast CI by date
bootstrap (B = 10,000, seed 2026); DATE = USREC slope of the per-date D-arm difference, HAC 6, dates
<= 2023-12; BASE = mean per-date M-arm difference with a date-bootstrap CI. G2 t reported per row.

**Noise floor**, per channel: the larger |difference| of the two replicate pairs J2 - T3 and J3 - F3; for
E2 at least 16.2 pp. **BEYOND** iff the test excludes zero (CI; |t| >= 1.96 for DATE) and |difference|
exceeds the floor. **UNSTABLE**: if either replicate pair is itself significant on a channel, no reading
is made on that channel.

**Two-reference rule** (the lesson of addendum I, whose readings rested on one reference run): a
component reading fires only if the contrast is BEYOND against **both** runs of the reference tier, with
the same sign.

## Frozen readings

- **R1 replication**: J3 - J2 (the tier contrast re-measured on second runs only). REPLICATES iff its E2
  CI lies above zero; otherwise DOES NOT REPLICATE.
- **R2 DTYPE**: F3 - J1 and J3 - J1 both BEYOND on E2 or on DATE, same sign: activation dtype moves the
  date route on this checkpoint.
- **R3 WEIGHTS**: J1 - T3 and J1 - J2 both BEYOND on E2 or on DATE, same sign: AWQ weights move the date
  route at bf16 activations.
- Neither R2 nor R3: with R1 REPLICATES, "the tier effect replicates but no single component clears the
  floor against both references"; with R1 failing, "the +29.7 pp contrast neither replicates nor is
  attributable".
- **BASELINE SHIFT**: a component contrast BEYOND on BASE against both references, reported separately.

The memory clause is reported per row and gates nothing (measurement invariance of one checkpoint).

## Deviations fixed in advance

- If vLLM refuses AWQ with bf16 activations for J1, J1 is reported missing and R2/R3 are not made; there is
  no fp16 fallback (that would be F3 again).
- Any rung below 1,032 valid cells gets the one resume pass of BM2c_note_retry.md; a gated E2 enters no
  contrast and no floor.
- A rung that cannot be served is reported missing; the others run.

## What this does not settle

One checkpoint, one box. R2/R3 on Tulu do not transfer to other AWQ builds or checkpoints; a
non-replication (R1) says the original contrast was within run-to-run variation on this box, not that
tier effects do not exist elsewhere.

## Cost

About 3-4 GPU-hours on the existing wbx allocation (job 12832) plus ~181 GB of downloads; no API spend.
