# GD-1b: VIX micro-arm — sharp sign identification for G3 (prereg addendum)

Frozen before any API call. Complements GD-1 (394c9ad4), whose G3 sign test
cannot separate "structured asset-aware crisis narrative" from "crisis →
undifferentiated bearish output": on the 10Y target both predict the same
sign (yield down). The CBOE VIX flips the sign: **in a crisis the VIX
rises**. A structured narrative transplanted onto a fake crisis date should
predict VIX **up** (+); an undifferentiated bearish/pessimism reflex should
predict **down** (−) or show no crisis-fake elevation of "+".

## Design (micro scope, disclosed)

- **Arm**: W only (wrong-date transplant, masked context, fake date asserted),
  the identification-carrying arm. No D/M arms (cost decision; E2_VIX is not
  an estimand here).
- **Dates**: the subset of the 240-date panel whose FAKE label (66-month
  cyclic shift, frozen `fake_map`) falls in the crisis windows (11 preregistered
  crisis months) or the calm windows (all 2013/2014/2017 months). Expected n:
  ~11 fake-crisis + ~36 fake-calm.
- **Model / protocol**: gemini-2.5-flash, temperature 0.2, 1 rep, 8 sketches
  per call, ARM_MAX_TOKENS 8192 — identical to GD-1 arms.
- **Target sentence swap**: "S&P 500 forward returns" → "the direction of the
  CBOE Volatility Index (VIX) over the next 20 trading days". All other
  transforms (masking, cleaning, transplant) are the frozen GD-1 code paths.

## Estimand and decision rule

- **Primary**: ΔVIX⁺ = share(direction = "+" | fake-crisis) −
  share(direction = "+" | fake-calm), at sketch level.
- **Prediction (structured narrative)**: ΔVIX⁺ ≥ +15pp, Fisher exact
  two-sided p < 0.05.
- **Alternative (bearish reflex)**: ΔVIX⁺ ≤ 0 (crisis-fake pushes "−"
  regardless of asset semantics).
- Realized VIX outcomes are not required: the estimand is about predicted
  direction under fake labels, not accuracy.

## Reporting

Result goes to §5.2 as the sharp companion to the exploratory text check
(31.8% vs 9.4% safe-haven language); GD1_RESULTS.md gains a GD-1b section.
Whatever the outcome, it is reported (a failed prediction would demote the
"structured narrative" reading to the text-level evidence only).

## Addendum v2 (pre-crisis-arm, 2026-07-06 21:35)

Implementation-stage discovery, disclosed before any fake-crisis generation
existed (2 fake-calm dates generated; both inspected): the `direction` field
is semantically unstable for a volatility target — one call used "+" as
market-positive (narrative says "lower VIX", field says "+"), the other used
"−" as VIX-down (consistent). The frozen estimand is unreliable without
pinning the mapping. Amendment: the user prompt gains one clarifying line —
"For this target, direction '+' means the VIX rises (volatility increases);
'−' means it falls." This pins field semantics for the structured path and
does not prevent a field-level bearish reflex (the alternative hypothesis is
a habit of emitting '−' on crisis dates regardless of semantics). The two
ambiguous fake-calm generations are discarded; all 47 dates regenerate under
the amended prompt. Estimand, decision rule, and windows unchanged.
