# BM-2b: Base vs. instruct — is the date reflex corpus-borne or installed by post-training? (prereg)

Frozen before any run. The "generation bundles recipe changes that
base-vs-instruct contrasts must separate" caveat (paper 1 §8.3), executed.

## Question

The date→narrative reflex appears in every tested 2025/26-generation model. Is it
present in the pretrained base model (corpus-borne), or installed by
post-training (instruction tuning / preference optimization)?

## Model pair

`Qwen/Qwen3-30B-A3B` (instruct) vs `Qwen/Qwen3-30B-A3B-Base` — the only current
family with an official base release at a size mirroring our benchmark rows
(30.5B total / 3.3B active; mirrors the qwen3.6-35B-A3B row). Qwen3 is the 2025
generation: the instruct model triggering is NOT a known fact, hence Stage 1.
Both models served at identical precision (**FP8**, vLLM dynamic or official,
recorded in run_meta) on a single H800 80GB.

## Stage 1 — GO/KILL (instruct, chat format)

Full 258 dates × 4 arms × 1 rep + LAP 258×10, frozen BM-1 protocol and analysis.
**GO** = E2 95% CI excludes 0. **KILL** = otherwise: reported as a
generation-boundary datum (Qwen3 gen does not trigger); Stage 2 cancelled.

## Stage 2 — three-condition contrast (conditional on GO)

Base models do not follow chat instructions, so prompting regime must be held
fixed across the contrast:

1. **instruct-chat** = Stage 1 run (bridges to the BM-1 leaderboard rows);
2. **instruct-2shot**: instruct model, raw completion format — system+user text
   concatenated, prefixed by two fixed in-context exemplars; the *controlled*
   comparator;
3. **base-2shot**: base model, identical prompt bytes as (2).

Exemplars: two calm-year masked-arm nodes (2013-05-15, 2014-08-15), exemplar
outputs taken from the archived flash M-arm generations for those dates with
direction fields rebalanced to exactly 4 '+' / 4 '−' each (no directional
injection); the exemplar file is hash-frozen as `BM2b_exemplars.json` BEFORE any
Stage-2 call, and its sha256 recorded in an addendum note.

Each condition: 258 dates × 4 arms × 1 rep + LAP 258×10. Schema compliance gate
inherited from BM-1b: **VALID < 50% → the condition is declared unmeasurable and
no inference is drawn from it** (reported as a compliance failure).

## Estimands and preregistered interpretation

E2/E3 per condition (frozen analysis, B = 10,000, seed 2026). The contrast of
record is **base-2shot vs instruct-2shot** (same prompting regime):

- (i) both trigger, CIs overlap → reflex is **corpus-borne**; post-training not
  required;
- (ii) instruct-2shot triggers, base-2shot CI includes 0 → reflex is
  **installed by post-training**;
- (iii) base-2shot unmeasurable (VALID < 50%) → no inference; reported;
- (iv) intermediate (both exclude 0, magnitudes differ beyond CIs) → dose
  reading: corpus seeds it, post-training amplifies; reported as measured.

instruct-chat vs instruct-2shot is the prompting-regime control: if these two
disagree beyond CIs, the 2-shot format itself perturbs the reflex and all
Stage-2 inference carries that caveat explicitly.

## Reporting

All outcomes reported. Goes to paper 2 (leaderboard extension + the
recipe-attribution section); if (ii), flagged for paper 1 camera-ready as the
generation-mechanism follow-up.
