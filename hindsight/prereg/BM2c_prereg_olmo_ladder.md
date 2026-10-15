# BM-2c: Where in the training pipeline is the date reflex installed? (prereg)

Frozen before any download, serve, or call. Succeeds BM-2b (51e03b53), whose
Stage 2 was cancelled because the only open base/instruct pair available then
(Qwen3-30B-A3B) did not trigger in Stage 1. Olmo 3 removes the blocker: Ai2
releases every post-training checkpoint of one flow from one base, with a
pretraining corpus (Dolma 3) whose data cutoff (2024-12) lies *after* the
measured trigger boundary of the 15-row benchmark (2024-04/05, paper 1 E.5).

## Question

The 15-row benchmark shows trigger status stepping once when rows are ordered
by measured cutoff, and switching on within the Qwen3 -> Qwen3.6 lineage.
Neither separates corpus period from training recipe. BM-2c measures E2/E3 on
a ladder of checkpoints that share one pretraining corpus and differ only in
how much post-training they have received.

## Models (exact repository ids, HF revision `main`, commit sha recorded at
download in each run_meta)

Ladder A — Olmo 3 7B Instruct flow, one base, three post-training stages:

| rung | repo | stage |
|---|---|---|
| A0 | `allenai/Olmo-3-1025-7B` | pretrained base (Dolma 3, midtrain + long-context included) |
| A1 | `allenai/Olmo-3-7B-Instruct-SFT` | + SFT (Dolci-Instruct-SFT) |
| A2 | `allenai/Olmo-3-7B-Instruct-DPO` | + DPO |
| A3 | `allenai/Olmo-3-7B-Instruct` | + RLVR (released Instruct) |
| A4 | `allenai/Olmo-3-7B-Think` | Think flow endpoint (reasoning regime; same base) |

Ladder B (conditional on disk >= 80 GB free on the serving machine; otherwise
deferred, not silently dropped): `allenai/Olmo-3-1125-32B` -> 
`allenai/Olmo-3.1-32B-Instruct-SFT` -> `-DPO` -> `allenai/Olmo-3.1-32B-Instruct`.

Lineage control C — same corpus, new recipe:
`casperhansen/llama-3.3-70b-instruct-awq` (Llama 3.3 70B Instruct, AWQ-INT4).
Meta reports the same 2023-12 knowledge cutoff as Llama 3.1 70B (benchmark
row: no trigger, cutoff-aligned recall, measured cutoff 2023-12) and a
2024-12 post-training with ~25M synthetic examples. Corpus fixed, recipe moved.

## Serving (pinned; BM-2a: E2 is not quantization-invariant)

- Ladders A/B: vLLM, **BF16 for every rung** (no rung may be served at a
  different precision from its siblings), `--served-model-name` = the
  models.yaml key, `max_model_len 24576`, temperature 0.2, `arm_max_tokens
  8192` (A0-A3, B) / 16384 (A4 Think: reasoning tokens count against the cap;
  answers are parsed after the reasoning block by the existing decode-scan in
  `strip_fences`). Retrieval/tools: none (plain completions).
- C: vLLM `awq_marlin`, same settings as the llama-3.1-70b-awq row. The
  quantizer differs from that row's (casperhansen vs hugging-quants); AWQ-INT4
  was the STABLE tier in BM-2a and this is disclosed, not corrected.

## Conditions and prompting regime (inherited from BM-2b verbatim)

1. **instruct-chat** (A1-A4, B1-B3, C): frozen BM-1 chat prompts via
   `run_bench_model.py --provider remote`, full 258 dates x 4 arms x 1 rep,
   REC 258 x 1 (temperature 0), LAP 258 x 10 (temperature 1.0). Identical to
   the row-15 (Qwen3-30B-A3B) protocol.
2. **base-2shot** (A0, B0): raw completion format, system+user concatenated,
   prefixed by the two frozen calm-year masked-arm exemplars
   (`BM2b_exemplars.json`, sha256 fb0e0c14; direction fields balanced 4/4), stop
   sequence `\n---`, via `run_bm2b_stage2.py`. LAP zero-shot completion.
3. **instruct-2shot** (A3, B3 only): the released Instruct model under the
   identical base-2shot prompt bytes — the controlled comparator that separates
   "base does not trigger" from "the completion format suppresses the trigger".

Smoke gate (BM-1 prereg): 2 dates x 4 arms with manual inspection **for A0
base-2shot and A1 instruct-chat before their full runs**. A2-A4 share A1's
prompt bytes and serving stack; their smokes are inspected automatically
(>= 6 of 8 smoke cells schema-valid) and the raw responses are archived for
post-hoc inspection; any automatic-smoke failure halts the chain. B and C get
manual smoke inspection (new size / new family).

## Estimands and gates (frozen BM-1 analysis, B = 10,000, seed 2026)

Per rung: E2 = Gap(D) - Gap(M), E3 = Gap_fake(W) - Gap_true(W), P1, REC, LAP,
measured cutoff, delta, VALID — the BM-1 row, produced by
`analyze_bench_row.py` unchanged. Gates inherited: VALID < 50% -> rung
unmeasurable (reported, no inference); recall hit rate at chance -> cutoff and
delta undefined; sample-parity rule (paper 1 E.12) for every contrast.

**Installation stage** := the lowest rung whose E2 95% CI excludes zero *and*
whose next-lower rung's CI includes zero, under one prompting regime. The
base rung enters this ordering only through the base-2shot vs instruct-2shot
pair (condition 3 must trigger for the base null to be interpretable).

Preregistered readings (ladder A; B is a replication at scale):

- (i) A0 base-2shot triggers -> **corpus-borne**; post-training not required.
- (ii) A0 null, A3 instruct-2shot triggers, and the first triggering rung in
  chat is A1 -> **installed by SFT**; first at A2 -> **by preference tuning**;
  first at A3 -> **by RLVR**.
- (iii) A0 unmeasurable (VALID < 50%) or A3 instruct-2shot null -> the
  base/post-training split is **not identified** in the completion regime;
  the chat ladder A1-A3 is still reported as the within-recipe dose reading.
- (iv) Non-monotone ladder (a rung triggers and a higher rung does not) ->
  reported as measured; no stage is named.
- (v) No rung triggers -> Olmo 3 joins the no-trigger set; combined with its
  2024-12 corpus cutoff this contradicts the pure corpus-period account
  (a model trained past the boundary without the reflex) and is reported as
  such.

Control C readings: E2 CI excludes zero -> **recipe installs the reflex on a
fixed 2023-12 corpus** (the Llama 3.1 70B row is the paired null);
CI includes zero -> consistent with corpus period, not decisive (one lineage).

A4 (Think) is a reasoning-regime datum for paper 2 §7.2, not part of the
installation ordering: its comparison of record is A4 vs A3.

## Not preregistered / disclosed in advance

- Rung-level CIs are date-level bootstraps at 1 rep (as row 15); the ladder is
  a within-family ordering, not a cross-model significance forest.
- Corpus density measurement on Dolma 3 (paper 1 §6.3 salience proxy) is a
  separate follow-up, not part of BM-2c.
- If ladder B is deferred for disk, the paper reports ladder A alone and says
  so.

## Cost envelope

GPU rental only, no API spend. Ladder A + C on one H800: ~2 nights
(A: 5 x ~1-2 h serve+run; C: ~1 night as the 3.1-70B row). Envelope
CNY 300-600. Ladder B: one additional night on a machine with >= 80 GB disk.
