# BM-2c note: prediction for addendum H, recorded before any H1/H2 cell exists (2026-09-24)

Not a frozen reading (addendum H's readings, 7ce2f785, govern). A timestamped prediction so the
H result can be read as a test of the mechanism hypothesis rather than fitted after the fact.

Exploratory evidence (scripts/explore_tier_mechanism.py, post hoc on cells already on disk):
- Memory is tier-invariant on the one same-box pair: Tulu 3 RLVR FP8 hit 74% (n=110), AWQ 72% (n=98).
- The data-only arm M is flat for almost every row in the study (recession slope |t| < 1.3), frontier
  models included: no model turns recession-period data into bearishness when the date is masked.
- The date-shown arm D carries the reflex, and INT4 AWQ strengthens it on both checkpoints measured in
  more than one tier: Tulu 3 RLVR D-arm recession slope FP8 -1.6 pp (t -1.06) vs AWQ +11.6 (t +3.14);
  Qwen3.6-27B BF16 +4.9 (t +1.32), FP8 +3.9 (t +0.69), AWQ +11.4 (t +2.42).
- Llama 3.3 AWQ (control C) has a weak D-arm slope (+2.7, t +0.47) and a near-floor bearish level
  (M arm 0.07; 78% of calm M cells unanimous bullish); its E2 +16.0 rests on the calm-date D-M gap.

Hypothesis: INT4 AWQ amplifies the date-token route; FP8/BF16 serving does not.
Prediction for H: H1 (Llama 3.3 FP8) E2 below the AWQ row's +16.0 and G2 null; H2 (Llama 3.1 FP8)
null on both. Under this prediction addendum H reads "control C is tier-dependent". The alternative
(control C real in any tier) predicts H1 triggers on E2.
