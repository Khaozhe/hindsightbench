# Per-replicate E2 (design-review response, 2026-07-25)

POST-FREEZE EXPLORATORY (2026-07-25). Frozen FM-1 flash arms, zero new API calls. Estimator: analyze_fm1.boot_diff, paired date-level bootstrap, B=10000, seed 2026.

| replicate | Gap(R) | Gap(D) | Gap(M) | E2 | E2 CI95 | E2 excl 0 | E1 | E1 CI95 |
|---|---|---|---|---|---|---|---|---|
| rep1 | 21.3 | 35.6 | 6.4 | 29.2 | [17.1, 41.4] | yes | -14.3 | [-24.7, -4.9] |
| rep2 | 44.2 | 35.8 | 4.0 | 31.8 | [17.6, 45.1] | yes | +8.4 | [-7.7, 25.6] |
| rep3 | 18.9 | 23.1 | 7.4 | 15.7 | [0.3, 32.0] | yes | -4.2 | [-17.4, 9.1] |

E1 across replicates: [-14.27, 8.4, -4.23] (sum -10.1 = 3 x pooled -3.4); only rep1's negative excludes zero; no replicate shows a significantly positive increment.
Anti-correlation: corr(Gap R, Gap M) = -0.98 across replicates (descriptive, n=3); rent spread 28.8pp exceeds Gap(R)'s 25.3 and Gap(M)'s 3.5.
M crisis share: rep1 47.727% = pooled 47.727% (the 47.7% coincidence is real; the calm side is what differs between the archived and pooled M).

All three replicates individually exclude zero: YES.

Between-replicate SD: E2 8.7pp, Gap(R) 14.0, Gap(D) 7.3, Gap(M) 1.8. SE of the three-replicate mean: 5.0pp.

Pooled E2 25.6pp, date-level CI [14.5, 36.8]. Replicate component on df=2: t(2) half-width 21.5pp (normal would give 9.8pp and is too narrow). Combined t(2): [1.3, 49.8] — excludes zero. Replicate-mean-only t(2): [4.0, 47.1].

Same-batch kill test (FM-1, all three replicates pooled): Gap(R) 28.1 -> Gap(M) 5.9, delta 22.2pp [13.6, 31.3]; masking removes 78.9% of the gap (residual 21.1%).
