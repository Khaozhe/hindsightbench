# ST-1 results: claude-haiku-4-5 (prereg f0284181)

coverage (nodes with >=1 valid sketch): {'M': 310, 'D': 310, 'L': 310, 'DL': 310, 'S': 310}
crisis nodes 28, calm nodes 50

| arm | share(crisis) | share(calm) | Gap |
|---|---|---|---|
| M | 0.719 | 0.620 | +0.099 |
| D | 0.754 | 0.593 | +0.162 |
| L | 0.746 | 0.625 | +0.121 |
| DL | 0.661 | 0.647 | +0.013 |

- **E2 (time trigger, S1) = +0.063** node-CI [-0.032, +0.158] (incl0); city-cluster CI [-0.013, +0.152]
- **E2L (place trigger, S2) = +0.022** node-CI [-0.083, +0.125] (incl0); city-cluster CI [-0.039, +0.117]
- **E2DL (joint key, S3) = -0.086** node-CI [-0.211, +0.034] (incl0); city-cluster CI [-0.186, +0.034]
- **INT = E2DL - E2 - E2L (S3) = -0.171** node-CI [-0.328, -0.016] (excl0); city-cluster CI [-0.353, -0.038]

S arm: Gap_true = +0.057, Gap_fake = -0.076 (fake-crisis nodes 28)
- **E3L (spatial transplant, S4) = -0.134** CI [-0.272, +0.009] (incl0)
  - post-freeze reference: D-arm fake-minus-true = -0.112 (the E3L value 'place ignored' predicts)
  - **relocation: Gap_fake(S) - Gap_fake(D) = -0.127** node-CI [-0.248, -0.001] (excl0)
  - **interference: Gap_true(S) - Gap_true(D) = -0.104** node-CI [-0.206, -0.003] (excl0)

| city | n_crisis | Gap(M) | Gap(D) | E2_city | Gap(L) | Gap(DL) |
|---|---|---|---|---|---|---|
| nyc | 1 | +0.30 | +0.32 | +0.02 | +0.28 | +0.43 |
| milan | 2 | +0.01 | +0.10 | +0.09 | +0.38 | +0.43 |
| london | 3 | +0.14 | +0.08 | -0.06 | +0.12 | +0.00 |
| madrid | 2 | +0.12 | +0.32 | +0.20 | +0.05 | +0.00 |
| tokyo | 4 | +0.07 | +0.24 | +0.17 | +0.01 | -0.15 |
| melbourne | 6 | +0.21 | +0.16 | -0.05 | +0.21 | +0.23 |
| sydney | 2 | +0.06 | +0.07 | +0.01 | +0.14 | -0.01 |
| delhi | 2 | +0.09 | +0.44 | +0.35 | +0.38 | -0.20 |
| hongkong | 3 | -0.01 | +0.14 | +0.15 | +0.00 | -0.19 |
| singapore | 3 | +0.06 | -0.08 | -0.14 | -0.03 | -0.19 |

## LAP-ST (memory gate S5: hit > majority-class 0.629)
| city | nodes | recall rate | hit | hit_n |
|---|---|---|---|---|
| nyc | 31 | 0.385 | 0.583 | 24 |
| milan | 31 | 0.411 | 0.308 | 26 |
| london | 31 | 0.185 | 0.556 | 18 |
| madrid | 31 | 0.171 | 0.316 | 19 |
| tokyo | 31 | 0.090 | 0.643 | 14 |
| melbourne | 31 | 0.477 | 0.423 | 26 |
| sydney | 31 | 0.445 | 0.414 | 29 |
| delhi | 31 | 0.074 | 0.545 | 11 |
| hongkong | 31 | 0.116 | 0.444 | 18 |
| singapore | 31 | 0.208 | 0.300 | 20 |
| ALL | 310 | 0.256 | 0.439 | 205 |
- memory gate: FAIL

## REC-ST (spatio-temporal recoverability, S6)
| city | n | date +-3mo | city exact | joint |
|---|---|---|---|---|
| nyc | 31 | 0.161 | 0.194 | 0.097 |
| milan | 31 | 0.161 | 0.000 | 0.000 |
| london | 31 | 0.161 | 0.000 | 0.000 |
| madrid | 31 | 0.161 | 0.000 | 0.000 |
| tokyo | 31 | 0.161 | 0.000 | 0.000 |
| melbourne | 31 | 0.161 | 0.000 | 0.000 |
| sydney | 31 | 0.161 | 0.000 | 0.000 |
| delhi | 31 | 0.161 | 0.000 | 0.000 |
| hongkong | 31 | 0.129 | 0.000 | 0.000 |
| singapore | 31 | 0.161 | 0.000 | 0.000 |
| ALL | 310 | 0.158 | 0.019 | 0.010 |
