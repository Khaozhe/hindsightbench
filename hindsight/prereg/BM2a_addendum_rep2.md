# BM-2a addendum: post-hoc second rep at BF16 (DATA-DEPENDENT, disclosed)

Written and frozen BEFORE the rep-2 run starts; decided AFTER observing the
rep-1 outcome. This is a data-dependent extension in the sense of the FM-1b
precedent, and both the 1-rep and (1+2)-rep estimates will be reported.

## What was observed (rep 1, frozen BM2A_RESULTS.json)

BF16 fails the preregistered E2 mutual-CI stability check against the frozen
FP8 row (+4.8pp [−6.9, +18.2] vs +19.3pp [+10.8, +28.5]); AWQ-INT4 passes
(+19.0pp [+8.3, +30.0]). Decomposition localizes the entire BF16 divergence to
the MASKED arm (M crisis−calm gap: BF16 +11.0 vs FP8 −3.5, AWQ +5.6; D-arm
gaps are tier-invariant). Confound checks already passed: chat templates
byte-identical across repos, same no-think output mode, parser v2 everywhere,
temperature 0.2, same vLLM build; arm_max_tokens 8192 anchored to the FP8
row's empirical output ceiling (~7k tokens, zero truncation marks).

## Extension

One additional full rep (rep 2, all four arms R/D/M/W, 258 dates, same
protocol and arm_max_tokens=8192) for `qwen3.6-27b-bf16` ONLY. Rationale for
all-arms rather than M/D-only: no runner modification, rep-parity with the
2-rep FP8 reference row, and W/R gain the same variance reduction. The rep-1
gap cells (5 missing) are filled by the same command (idempotent resume).

## Decision rule for the headline claim

The claim "the masked arm leaks at full precision" is asserted only if the
pooled (1+2)-rep BF16 M-arm crisis−calm gap remains positive with a bootstrap
95% CI excluding 0. Otherwise the finding is reported as: E2 point-estimate
quantization sensitivity with a failed mutual-CI check at BF16, direction
conclusions unchanged — a protocol requirement (pin and report the serving
quantization), not a mechanism claim.

Both outcomes go to paper 2; neither is dropped.
