# BM-1 Preregistration: HindsightBench Multi-Model Protocol (English companion)

> **Companion translation** (2026-07-08) of the frozen Chinese original
> `BM1_prereg.md` (sha256 `fbcdffc158c3e4d7676ab7b4250c5568c2666bbd680ae437ee29d5daa8acc9a4`,
> frozen 2026-07-02T15:00:29, **before any non-Gemini model call** — see
> `BM1_prereg_freeze.json`). The Chinese original is authoritative; in case of
> any divergence, the original governs. This file carries its own hash in
> `BM1_prereg_EN_freeze.json` for artifact integrity only — it is a
> translation, not a new preregistration.

Status of the original: **FROZEN** (prior to any non-Gemini model call; sha256
in `BM1_prereg_freeze.json`)

## Protocol (identical for every entering model m)

1. **Generation matrix**: four arms (R/D/M/W; transformation rules = the
   frozen FM-1 version, 66-month shift) × 2 reps × 240 pre-cutoff decision
   dates, plus four arms × 2 reps × 18 post-cutoff decision dates (the FM-1c
   C1 extension panel). temperature = 0.2; the output budget is relaxed per
   model until completion (content-neutral).
2. **Probes**: date-recovery probe (258 dates × 1, temp = 0); LAP probe
   (258 dates × 20 reps, temp = 1.0, wording = the frozen FM-1c C2 version).
3. **Benchmark-row metrics** (one row per model, all under the frozen
   FM-1/FM-1c definitions):
   - E2_m date-trigger strength = Gap(D) − Gap(M)
   - E3_m transplantation effect = Gap_fake(W) − Gap_true(W)
   - REC_m date recoverability (three readings: calendar-year hit / ±12
     months / mean month offset)
   - LAP_m memory recall rate (pre-cutoff mean) and **empirical cutoff**
     (the collapse point of the monthly LAP series, defined as the last
     month with LAP > 0.1)
   - DISS_m dissociation coefficient = the A2 detection-regression δ
     (signal × LAP interaction, HAC lag 6)
   - VALID_m task-compliance rate (share of schema-valid sketches;
     refusal/parse-failure counts — expected low for small models, reported
     as-is; models that cannot carry the task exit with the record kept)
4. **Adapters**: OpenAI-compatible endpoints go uniformly through
   `llm_adapters.py` (base_url/model parameterized; json_object mode
   preferred; parsing tolerance: markdown-fence stripping + array
   extraction). Anthropic gets its own adapter. Every model requires a
   2-date × 4-arm smoke run with manual inspection before full volume.
5. **Inference discipline**: across model rows we only do descriptive
   ranking and scale/family group comparisons — no forest of pairwise
   significance tests; effect-size CIs use the same bootstrap as FM-1. The
   main (AAAI) paper commits only to the two Gemini tiers; all other models
   go to the extended table / benchmark paper, merged on a rolling basis
   without reopening the analysis conventions.
6. **Entry order** (as keys arrive): deepseek-v4-flash (this round) →
   Kimi/Qwen/OpenAI/Anthropic → local open-weight small models via ollama
   (Llama-3.1-8B, Llama-3.2-3B). Per-model outputs live in
   `hindsight/outputs/bench/<model>/`, structured identically to FM-1.
