# BM-2c addendum I: precision dose-response on one checkpoint

Frozen 2026-09-23 before any call on the rungs below and before any of their weights were downloaded.
Extends BM2c_prereg_olmo_ladder.md (afa19e6d) and addenda D-H (G: c7e04919, H: 7ce2f785). Nothing
already frozen changes. The analysis script `scripts/analyze_dose_response.py` is frozen with this
document (sha in the freeze JSON).

## Why

Addendum F put one checkpoint (Tulu 3 70B RLVR) in two serving tiers on the same box and found a
paired E2 difference of +29.7 [+14.3, +45.3] pp (AWQ minus FP8), beyond the 16.2 pp same-model
replicate noise floor. Addendum H found the Llama 3.3 / 3.1 control-C pair tier-dependent, but with
tier contrasts inside the floor. The exploratory mechanism pass (not preregistered) located the shift
in the D arm (date string present) rather than in the M arm, and showed it on Qwen3.6 as well
(BF16 1.32 / FP8 0.69 / AWQ 2.42 D-arm recession t) but not on the Llama pair. Those observations
are post hoc and span boxes and checkpoints. This addendum asks the question once, prospectively, on
one checkpoint, one box, one serving stack: does quantization move the date-trigger measurement,
is the movement specific to AWQ or to 4 bits, and is it ordered by precision?

## Checkpoint

Qwen3-30B-A3B-Thinking-2507 (MoE, 3B active). It is the one Qwen row that triggers G2 (D2 on the
H800, W8A8 fp8-dynamic: E2 +36.6, G2 t = 2.26), it is small enough to serve at BF16 on 4 x A100-40G,
and official or first-party-tooling quantizations exist at every tier below.

## Design (4 x A100-40G, TP=4, vLLM 0.29, same box and stack as addenda F/H)

| rung | repo (sha) | weights / activations |
|---|---|---|
| I1 | Qwen/Qwen3-30B-A3B-Thinking-2507 (144afc2f) | BF16 / BF16 (reference) |
| I2 | QuantTrio/Qwen3-30B-A3B-Thinking-2507-AWQ (3723ded1) | AWQ INT4 g128 zero-point, awq_marlin / BF16 |
| I3 | = I1 | BF16 / BF16, independent second run (same-box noise floor) |
| I4 | RedHatAI/...-quantized.w4a16 (98ffbaed) | INT4 g128 symmetric (GPTQ-style) / BF16 |
| I5 | RedHatAI/...-quantized.w8a8 (fb485fe2) | INT8 per-channel / dynamic INT8 |
| I6 | Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 (60d80c83) | FP8 block-128 / as the kernel serves it on sm80 |
| I7 | = I1 | BF16 weights served with `--dtype float16` (dtype control) |

Chat template: all repos carry template 3802169b except QuantTrio (40c21f34), which lacks the forced
`<think>\n` prefix; I2 is served with the reference repo's template copied in (original kept, noted
in TEMPLATE_NOTE.txt). Generation config is identical across repos. Prompts, sampling (temperature
0.2, 1 replicate, arm_max_tokens 16384 as D2), probes, gates, bootstrap and the one-pass resume rule
are the control protocol unchanged. No sampling seed is set, so I3 is an independent draw.
Smoke: I1 and I2 get the manual post-hoc inspection note; I3-I7 the automatic pre-screen.

If a rung cannot be served as specified on sm80 (e.g. the block-FP8 or awq_marlin-with-BF16 kernel is
unavailable), the fallback is: I2 with `--dtype float16`, I6 with vLLM's default kernel choice. Any
fallback is recorded in the serving note and the rung's reading carries it; no rung is dropped
silently. A rung that cannot be served at all is reported as missing.

## Channels (per rung) and contrasts (vs I1)

- **E2** = Gap(D) - Gap(M), 11 crisis / 36 calm dates (the row file's value).
- **G2** = addendum G's whole-panel t (reported, not re-thresholded here).
- **DATE** = OLS slope of the D arm's per-date bearish share on USREC, dates <= 2023-12, HAC 6.
- **BASE** = mean bearish share of the M arm over all panel dates (a level, not a trigger).

Contrast of rung X against I1 on the same dates: E2 difference with the date-bootstrap CI (B = 10,000,
seed 2026); DATE = the USREC slope of the per-date D-arm difference, HAC 6; BASE = mean per-date
M-arm difference with a date-bootstrap CI.

**Noise floor.** The I3 minus I1 contrast, per channel. For E2 the floor is max(|I3 - I1|, 16.2 pp).
A contrast is BEYOND the floor iff (i) its test excludes zero (CI for E2 and BASE, |t| >= 1.96 for
DATE) and (ii) its magnitude exceeds the floor. If I3 minus I1 itself is significant on a channel,
that channel is reported as unstable on this box and no tier reading is made on it.

## Frozen readings

1. **ROBUST**: no quantized rung (I2, I4, I5, I6) is beyond the floor on any channel.
2. **AWQ-SPECIFIC**: I2 beyond on E2 or DATE, I4 not.
3. **4-BIT**: I2 and I4 both beyond on E2 or DATE (strengthened to "4-bit only" if neither I5 nor I6 is).
4. **GPTQ-SPECIFIC**: I4 beyond, I2 not.
5. **DOSE ORDERING** (made only if a 4-bit rung is beyond): mean |DATE shift| of the 4-bit rungs larger
   than that of the 8-bit rungs.
6. **BASELINE SHIFT**: any quantized rung beyond on BASE, reported separately from the date route.
7. **DTYPE**: I7 beyond on any channel means activation dtype alone moves the measurement; then every
   fp16-served AWQ row elsewhere in BM-2c is dtype-confounded and is labelled so.

The memory clause (post-LAP <= .1, hit > 65.5% on >= 100 answered probes) is reported per rung but does
not gate the contrasts: the question is measurement invariance of one checkpoint, not a new row's
reading. Rows enter the leaderboard/ladder table only as a labelled precision block.

## What this does not settle

One checkpoint, one box. A ROBUST reading does not undo the Tulu contrast (a different checkpoint and
AWQ build); an AWQ-SPECIFIC reading does not tell which AWQ builds are affected. The H800 D2 row
(W8A8 fp8-dynamic) is a cross-box reference only and is not in any contrast.

## Cost

About 12-14 GPU-hours on the existing wbx allocation (job 12832), no API spend.
