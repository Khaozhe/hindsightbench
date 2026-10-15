# ST-1 results: gpt-5.4-mini (prereg f0284181)

coverage (nodes with >=1 valid sketch): {'M': 310, 'D': 310, 'L': 310, 'DL': 310, 'S': 310}
crisis nodes 28, calm nodes 50

| arm | share(crisis) | share(calm) | Gap |
|---|---|---|---|
| M | 0.741 | 0.583 | +0.159 |
| D | 0.759 | 0.578 | +0.181 |
| L | 0.741 | 0.585 | +0.156 |
| DL | 0.719 | 0.608 | +0.111 |

- **E2 (time trigger, S1) = +0.023** node-CI [-0.073, +0.124] (incl0); city-cluster CI [-0.082, +0.132]
- **E2L (place trigger, S2) = -0.002** node-CI [-0.089, +0.084] (incl0); city-cluster CI [-0.092, +0.077]
- **E2DL (joint key, S3) = -0.047** node-CI [-0.142, +0.048] (incl0); city-cluster CI [-0.147, +0.036]
- **INT = E2DL - E2 - E2L (S3) = -0.068** node-CI [-0.193, +0.057] (incl0); city-cluster CI [-0.212, +0.089]

S arm: Gap_true = +0.186, Gap_fake = +0.079 (fake-crisis nodes 28)
- **E3L (spatial transplant, S4) = -0.107** CI [-0.219, +0.000] (incl0)
  - post-freeze reference: D-arm fake-minus-true = -0.067 (the E3L value 'place ignored' predicts)
  - **relocation: Gap_fake(S) - Gap_fake(D) = -0.036** node-CI [-0.117, +0.047] (incl0)
  - **interference: Gap_true(S) - Gap_true(D) = +0.005** node-CI [-0.096, +0.105] (incl0)

| city | n_crisis | Gap(M) | Gap(D) | E2_city | Gap(L) | Gap(DL) |
|---|---|---|---|---|---|---|
| nyc | 1 | +0.25 | +0.38 | +0.12 | +0.40 | +0.40 |
| milan | 2 | +0.40 | +0.22 | -0.18 | +0.11 | +0.09 |
| london | 3 | +0.27 | +0.24 | -0.03 | +0.16 | +0.28 |
| madrid | 2 | +0.01 | +0.22 | +0.21 | +0.15 | -0.01 |
| tokyo | 4 | +0.12 | +0.12 | +0.01 | +0.01 | -0.17 |
| melbourne | 6 | -0.00 | +0.32 | +0.32 | +0.16 | +0.07 |
| sydney | 2 | +0.36 | +0.11 | -0.25 | +0.29 | +0.22 |
| delhi | 2 | +0.09 | +0.12 | +0.04 | +0.25 | +0.24 |
| hongkong | 3 | +0.05 | -0.03 | -0.08 | +0.16 | +0.11 |
| singapore | 3 | +0.14 | +0.07 | -0.07 | +0.07 | +0.22 |

## LAP-ST (memory gate S5: hit > majority-class 0.629)
| city | nodes | recall rate | hit | hit_n |
|---|---|---|---|---|
| nyc | 31 | 1.000 | 0.742 | 31 |
| milan | 31 | 1.000 | 0.690 | 29 |
| london | 31 | 1.000 | 0.862 | 29 |
| madrid | 31 | 1.000 | 0.645 | 31 |
| tokyo | 31 | 1.000 | 0.700 | 30 |
| melbourne | 31 | 1.000 | 0.733 | 30 |
| sydney | 31 | 1.000 | 0.700 | 30 |
| delhi | 31 | 1.000 | 0.667 | 30 |
| hongkong | 31 | 1.000 | 0.800 | 30 |
| singapore | 31 | 1.000 | 0.767 | 30 |
| ALL | 310 | 1.000 | 0.730 | 300 |
- memory gate: PASS

## REC-ST (spatio-temporal recoverability, S6)
| city | n | date +-3mo | city exact | joint |
|---|---|---|---|---|
| nyc | 31 | 0.226 | 0.194 | 0.000 |
| milan | 31 | 0.226 | 0.000 | 0.000 |
| london | 31 | 0.194 | 0.032 | 0.000 |
| madrid | 31 | 0.226 | 0.000 | 0.000 |
| tokyo | 31 | 0.226 | 0.000 | 0.000 |
| melbourne | 31 | 0.290 | 0.226 | 0.065 |
| sydney | 31 | 0.129 | 0.129 | 0.032 |
| delhi | 31 | 0.323 | 0.000 | 0.000 |
| hongkong | 31 | 0.032 | 0.000 | 0.000 |
| singapore | 31 | 0.355 | 0.000 | 0.000 |
| ALL | 310 | 0.223 | 0.058 | 0.010 |
