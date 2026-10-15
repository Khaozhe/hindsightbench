# BM-2c addendum D: a second fixed-corpus recipe contrast (Qwen3-30B-A3B -> 2507)

Frozen before any call on either model. Extends BM2c_prereg_olmo_ladder.md
(afa19e6d) control C with a second lineage; nothing in ladders A/B or control C
changes.

## Why (2026-09-14 17:30, after ladders A and B1-B2 were read)

Ladder A (Olmo-3 7B, six conditions) is null at every stage, and ladder B is
tracking it. The reason is now visible in the rows: every Olmo rung's recall hit
rate sits at or below the panel's 65.5% base rate (37-64%) and its REC is ~5%,
so the lineage has no behaviorally effective outcome memory at any
post-training stage. A trigger cannot show where there is nothing to trigger,
so the Olmo ladder cannot localise the installation stage; it is a no-memory
baseline. That leaves control C (Llama 3.1 -> 3.3 70B, E2 +16.0 [+1.9, +31.2]
vs -4.7) as the only fixed-corpus recipe contrast, n = 1. This addendum adds a
second one where the comparator row is already frozen in the benchmark.

## Design

Comparator (frozen, unchanged): benchmark row 15, `qwen3-30b-a3b-fp8dyn`
(`Qwen/Qwen3-30B-A3B`, released 2025-04, default chat template = thinking on,
vLLM dynamic FP8, temperature 0.2, 1 rep, arm_max_tokens 8192): E2 +6.3
[-9.7, +23.6] (null), LAP .807/.000, empirical cutoff **2024-04**, hit 67%,
REC 18%/0%.

New rungs (same serving stack, same prompts, same analysis; `bm2c_ladder.sh`):

| rung | checkpoint | mode | arm_max_tokens |
|---|---|---|---|
| D1 | `Qwen/Qwen3-30B-A3B-Instruct-2507` (sha 0d7cf239) | non-thinking only | 8192 |
| D2 | `Qwen/Qwen3-30B-A3B-Thinking-2507` (sha 144afc2f) | thinking only | 16384 (as A4; disclosed) |

Qwen describes both as "the updated version of the Qwen3-30B-A3B
non-thinking / thinking mode" with "Training Stage: Pretraining & Post-training"
and claims "substantial gains in long-tail knowledge coverage"; the vendor does
not state whether the pretraining corpus changed. The fixed-corpus premise is
therefore **tested, not assumed**, by the benchmark's own locator:

**Identification condition (frozen).** A 2507 row counts as a fixed-corpus
contrast against row 15 only if its empirical LAP cutoff falls in
[2024-03, 2024-05] (row 15: 2024-04) and its recall hit rate exceeds 65.5%.
If the cutoff moves later than 2024-05, the update changed the corpus and the
row is reported as a mixed (corpus + recipe) contrast, which does not count
toward the recipe reading. If the hit rate is at chance, the row is reported
as a no-memory row (cutoff undefined) and does not count either.

Estimands, gates (sample-parity, chance-recall), bootstrap (B = 10,000, seed
2026), smoke gate (automatic pre-screen >= 6/8 schema-valid, manual inspection
post hoc per BM2c_note_unattended.md) and the one-pass resume rule
(BM2c_note_retry.md) are inherited unchanged. Transport: the corrected settings
of BM2c_note_B_transport.md (3,600 s client timeout; concurrency 32 for this
3B-active MoE, whose KV footprint is small).

## Readings (frozen)

- D1 identified as fixed-corpus and E2 CI excludes zero (positive), while row
  15 is null -> **second lineage on which the post-training recipe alone
  installs the reflex** (with C: n = 2).
- D1 identified as fixed-corpus and E2 null -> on this lineage the 2507 recipe
  does not install it; C stays n = 1 and is reported as such.
- D1 not identified (cutoff moved or recall at chance) -> no recipe reading
  from this lineage; reported as measured.
- D2 vs D1 is the thinking-regime datum (as A4 vs A3); it does not enter the
  count unless D1 is unidentified and D2 is identified, in which case D2 takes
  D1's role above (the mode difference is then disclosed as a confound).

## Cost

Two 61 GB downloads (prefetched during ladder B), ~1-2 GPU-hours on the H800
(3B-active MoE), ~CNY 15. No API spend.
