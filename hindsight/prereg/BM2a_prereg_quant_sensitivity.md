# BM-2a: Quantization sensitivity of the hindsight profile (prereg)

Frozen before any run. Closes the caveat promised in paper 1 (§8.3 / Appendix D:
"quantization varies, sensitivity checks a benchmark-track item").

## Question

Are the BM-1 hindsight metrics (E2 date-trigger, E3 transplantation, empirical
LAP cutoff) properties of the weights, or artifacts of the serving quantization?

## Design

- **Model**: `qwen3.6-27b` — the triggering dense open-weight row (frozen FP8 row:
  E2 +0.193 [0.11, 0.28], E3 +0.181 [0.11, 0.25], cutoff 2024-11).
- **Tiers**: (a) official FP8 = the existing frozen row (no re-run); (b) **BF16**
  (original release precision); (c) **INT4** (official/community AWQ if available,
  else GPTQ, else self-quantized with autoawq default recipe — source recorded in
  run_meta and disclosed).
- **Protocol per new tier**: full 258 dates × 4 arms (R/D/M/W) × 1 rep, 8 sketches,
  temperature 0.2, ARM_MAX_TOKENS per BM-1 → 1,032 cells/tier. LAP probe 258 × 10
  reps (temp 1.0). No REC probe (cost; REC is not a quantization-sensitive claim
  we make).
- **Infra**: single H800 80GB, vLLM, serial model loads, idempotent per-cell resume
  (BM-1 discipline). Sizes: BF16 ≈ 54 GB, INT4 ≈ 15 GB — both fit one card.
- **Analysis**: frozen `analyze_bench_row.py` unchanged (B = 10,000, seed 2026);
  one row JSON per tier.

## Estimands and decision rule

Per tier: E2, E3 (bootstrap 95% CI), empirical cutoff, VALID.

**Descriptive robustness check, no GO/KILL**: "stable" is declared iff each new
tier's E2 and E3 point estimates fall inside the frozen FP8 row's 95% CIs (and
conversely), and the empirical cutoff is within ±1 month of 2024-11. Any
instability is reported as a finding about serving-stack dependence of behavioral
audits (a protocol requirement, not a failure).

## Descoped (disclosed)

- `llama-3.1-70b` extra tiers: BF16 needs 2×80 GB (140 GB weights); the model is
  the null-trigger case, so sensitivity evidence rests on the *triggering* 27B.
  If reviewers require the null side, a 70B GPTQ-INT4 (vs the frozen AWQ-INT4)
  single-card contrast is the designated follow-up.
- No 2-rep replication (cost); CI width carries the uncertainty statement.

## Reporting

Both tiers reported regardless of outcome; goes to paper 2 protocol-invariance
section. Deviations from this plan follow the standing disclosure policy.
