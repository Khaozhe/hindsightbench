# BM-2c addendum E: one preference-optimisation stage on a memory-bearing base (Nemotron-70B)

Frozen before any call on the model. Extends BM2c_prereg_olmo_ladder.md
(afa19e6d) and addendum D with a single-stage localisation test; nothing
already frozen changes.

## Why (2026-09-14, after the Olmo ladders and addendum D were queued)

Stage localisation needs a lineage with recallable outcome memory, public
intermediate checkpoints, and a triggering endpoint. Olmo 3 has the checkpoints
but no memory and no trigger; Llama 3.3 has the trigger but no intermediate
checkpoints. `nvidia/Llama-3.1-Nemotron-70B-Instruct-HF` is exactly one
post-training stage (HelpSteer2 reward model + REINFORCE RLHF) applied on top
of `meta-llama/Llama-3.1-70B-Instruct`, which is the benchmark's paired null
(E2 -4.7 [-12.0, +3.0], LAP .854/.000, cutoff 2023-12) on the same corpus on
which Llama 3.3's recipe installs the reflex (control C, E2 +16.0 [+1.9, +31.2]).
It therefore tests whether a single preference-optimisation stage, holding the
corpus and the Instruct starting point fixed, installs the reflex.

## Design

| rung | checkpoint | quant | pairing |
|---|---|---|---|
| E1 | `ibnzterrell/Nvidia-Llama-3.1-Nemotron-70B-Instruct-HF-AWQ-INT4` (sha 4639aa61; AWQ 4-bit, group 128, GEMM, zero-point — the same quantisation configuration as the casperhansen 3.3 checkpoint of control C and the hugging-quants 3.1 row) | AWQ-INT4, `awq_marlin`, fp16 | start point: benchmark row `llama-3.1-70b-awq`; recipe comparator: control C `llama-3.3-70b-awq` |

Chosen among three community AWQ conversions with identical quantisation
configs by download count (248 vs 37 vs 5); the quantiser differs from both
70B rows' (three quantisers across four 70B rows) and is disclosed, not
corrected, as in control C. Serving, prompts, sampling (temperature 0.2, 1 rep,
arm_max_tokens 8192), REC/LAP probes, estimands, gates, bootstrap and the
one-pass resume rule are the control-C protocol unchanged; transport as in
BM2c_note_B_transport.md (3,600 s, concurrency 16 for a 70B); smoke: automatic
pre-screen with post-hoc manual inspection (BM2c_note_unattended.md).

**Identification condition (frozen).** E1 counts as a same-corpus, same-start
stage test only if its LAP collapses at the base's cutoff: pre-cutoff LAP
>= .5, post-cutoff LAP <= .1, empirical cutoff in [2023-11, 2024-01] (the
frozen 70B rows sit at 2023-12 with hit 68-69%, at the base rate; paper 1 §8.3
uses the collapse, not the hit rate, as the memory evidence for this lineage,
and the same rule is applied here). If the collapse is absent the row is
reported as a no-memory row and gives no stage reading.

## Readings (frozen)

- E1 identified and E2 CI excludes zero (positive) -> **a single RLHF
  preference stage on a fixed corpus and a fixed Instruct start installs the
  reflex**: the first stage-level localisation on a memory-bearing base.
- E1 identified and E2 null -> this preference stage does not install it; the
  installation remains recipe-specific (Meta 2024-12 yes; Meta 2024-07,
  NVIDIA RLHF no), stage not localised.
- E1 not identified -> reported as measured, no reading.
E3 and P1 are reported alongside as in every row; E3 excluding zero with E2
null is reported as measured (no reading was frozen for that pattern).

## Cost

One 40 GB download, ~3 GPU-hours on the H800 (as control C), ~CNY 30. No API spend.
