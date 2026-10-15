# BM-2c addendum F: recipe panel and a stage ladder on one memory-bearing base (Llama 3.1 70B)

Frozen before any call on any of the models below. Extends BM2c_prereg_olmo_ladder.md
(afa19e6d) and addenda D/E; nothing already frozen changes.

## Why (2026-09-15, after all 15 BM-2c rungs were read)

Stage localisation failed on Olmo 3 because the lineage has no recallable outcome
memory (every rung's recall hit rate at or below the 65.5% base rate). The
Llama 3.1 70B base does have it (cutoff 2023-12 on every derivative measured:
Meta 3.1 Instruct 68%, Llama 3.3 69%, Nemotron 72.9%), and it carries a set of
public post-training recipes from different labs, one of them (Tülu 3) with its
SFT, DPO and RLVR checkpoints released. So the design moves from "one lineage,
stage checkpoints, no memory" to "one memory-bearing base, several recipes, stage
checkpoints inside one of them".

Already measured on this base (frozen rows): Meta 3.1 Instruct (2024-07) E2 -4.7
[-12.0, +3.0]; Nemotron (3.1 Instruct + one RLHF stage) E2 +9.8 [+0.4, +19.2],
memory clause borderline (addendum E); Meta 3.3 (2024-12) E2 +16.0 [+1.9, +31.2].

## Design

| rung | checkpoint (HF sha) | what it is on the base | serving |
|---|---|---|---|
| T1 | `allenai/Llama-3.1-Tulu-3-70B-SFT` (f8ef3414, 141 GB BF16) | Ai2 SFT | BF16 -> vLLM dynamic FP8, TP=2 |
| T2 | `allenai/Llama-3.1-Tulu-3-70B-DPO` (2dab5183) | + DPO | same |
| T3 | `allenai/Llama-3.1-Tulu-3-70B` (cfc1d855) | + RLVR (released) | same |
| F1 | `casperhansen/deepseek-r1-distill-llama-70b-awq` (a1ab7653; AWQ 4-bit g128 GEMM, as control C) | reasoning SFT on top of Llama 3.3 Instruct (the triggering endpoint) | AWQ, awq_marlin, TP=1 |
| F2 | `NousResearch/Hermes-3-Llama-3.1-70B-FP8` (official FP8) | Nous SFT + DPO on the base | official FP8, TP=2 |
| F3 (optional, cross-tier check) | `Valdemardi/Llama-3.1-Tulu-3-70B-AWQ` (782516fd; same AWQ config) | T3 in the AWQ tier | AWQ, TP=1 |

Prompts, sampling (temperature 0.2, 1 rep, arm_max_tokens 8192; F1 16384 as for
the other reasoning rungs), REC/LAP probes, estimands, gates, bootstrap, smoke
(automatic pre-screen + post-hoc manual inspection) and the one-pass resume rule
are the control-C protocol unchanged. Transport as BM2c_note_B_transport.md
(3,600 s; concurrency 16). Serving tiers: the three Tülu stages and Hermes share
one tier (FP8, TP=2; FP8 was the STABLE tier in BM-2a); F1 uses the AWQ tier of
the 3.3 and Nemotron rows; F3, if run, puts T3 in that tier so the two tiers are
compared on one checkpoint. Tier differences are disclosed, never corrected.
Tensor parallelism is a serving detail (the checkpoints do not fit one 80 GB card
in FP8); it is recorded per row.

**Memory condition (frozen, one clause set for every row here).** A row counts
only if its post-cutoff LAP <= .1 and its pre-cutoff recall hit rate > 65.5% on
at least 100 answered probes. (Addenda D and E used different clause sets and
each of their rows failed one clause by a hair; this addendum fixes one set in
advance and applies it to all six rows.) A row failing it is reported as measured
with no reading.

## Readings (frozen)

Tülu ladder T1 -> T2 -> T3 (all identified):
- lowest triggering rung whose predecessor does not trigger, with every later
  rung triggering -> **installation stage localised** within this recipe;
- no rung triggers -> the Ai2 recipe does not install it on a memory-bearing
  base; installation stays recipe-specific, stage not localised;
- non-monotone -> reported as measured, no stage named.

Panel reading (all identified rows on this base, including the three frozen
ones): the number of recipes that trigger out of those measured is reported as
the headline count; "recipe installs the reflex" is claimed only for recipes
whose E2 CI excludes zero positively. F1 is a datum about what a further
reasoning-SFT stage does to a triggering endpoint (E2 vs 3.3's +16.0): retained
(CI overlaps), amplified (CI above), or removed (null); it does not enter the
installation count.

## Cost

Two machines in parallel (GPU time is cheap relative to the deadline): a 2 x 80 GB
box for T1-T3 and F2 (~423 + 70 GB of downloads, ~4 GPU-hours), a 1 x 80 GB box
for F1 (+ F3) (~40-80 GB, ~1-2 GPU-hours). About CNY 250 in total including
download idle time. No API spend.
