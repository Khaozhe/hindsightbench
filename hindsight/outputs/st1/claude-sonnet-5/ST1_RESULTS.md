# ST-1 results: claude-sonnet-5 (prereg f0284181)

coverage (nodes with >=1 valid sketch): {'M': 310, 'D': 310, 'L': 310, 'DL': 310, 'S': 310}
crisis nodes 28, calm nodes 50

| arm | share(crisis) | share(calm) | Gap |
|---|---|---|---|
| M | 0.719 | 0.502 | +0.216 |
| D | 0.728 | 0.470 | +0.258 |
| L | 0.763 | 0.583 | +0.181 |
| DL | 0.781 | 0.490 | +0.291 |

- **E2 (time trigger, S1) = +0.041** node-CI [-0.044, +0.125] (incl0); city-cluster CI [-0.029, +0.115]
- **E2L (place trigger, S2) = -0.035** node-CI [-0.116, +0.042] (incl0); city-cluster CI [-0.108, +0.032]
- **E2DL (joint key, S3) = +0.075** node-CI [-0.008, +0.158] (incl0); city-cluster CI [+0.025, +0.133]
- **INT = E2DL - E2 - E2L (S3) = +0.069** node-CI [-0.063, +0.198] (incl0); city-cluster CI [-0.071, +0.205]

S arm: Gap_true = +0.253, Gap_fake = +0.195 (fake-crisis nodes 28)
- **E3L (spatial transplant, S4) = -0.058** CI [-0.201, +0.085] (incl0)
  - post-freeze reference: D-arm fake-minus-true = -0.143 (the E3L value 'place ignored' predicts)
  - **relocation: Gap_fake(S) - Gap_fake(D) = +0.080** node-CI [+0.005, +0.160] (excl0)
  - **interference: Gap_true(S) - Gap_true(D) = -0.005** node-CI [-0.079, +0.071] (incl0)

| city | n_crisis | Gap(M) | Gap(D) | E2_city | Gap(L) | Gap(DL) |
|---|---|---|---|---|---|---|
| nyc | 1 | +0.65 | +0.70 | +0.05 | +0.60 | +0.62 |
| milan | 2 | +0.26 | +0.18 | -0.09 | +0.24 | +0.44 |
| london | 3 | +0.28 | +0.26 | -0.03 | +0.13 | +0.47 |
| madrid | 2 | +0.15 | +0.22 | +0.07 | +0.11 | +0.34 |
| tokyo | 4 | +0.19 | +0.16 | -0.03 | -0.01 | +0.14 |
| melbourne | 6 | +0.22 | +0.33 | +0.11 | +0.25 | +0.27 |
| sydney | 2 | +0.41 | +0.38 | -0.04 | +0.41 | +0.59 |
| delhi | 2 | +0.22 | +0.26 | +0.04 | +0.24 | +0.24 |
| hongkong | 3 | +0.00 | +0.28 | +0.28 | +0.16 | +0.08 |
| singapore | 3 | +0.02 | +0.08 | +0.07 | -0.04 | +0.09 |

## LAP-ST (memory gate S5: hit > majority-class 0.629)
| city | nodes | recall rate | hit | hit_n |
|---|---|---|---|---|
| nyc | 31 | 1.000 | 0.677 | 31 |
| milan | 31 | 1.000 | 0.645 | 31 |
| london | 31 | 1.000 | 0.677 | 31 |
| madrid | 31 | 1.000 | 0.677 | 31 |
| tokyo | 31 | 1.000 | 0.935 | 31 |
| melbourne | 31 | 1.000 | 0.548 | 31 |
| sydney | 31 | 1.000 | 0.581 | 31 |
| delhi | 31 | 0.992 | 0.774 | 31 |
| hongkong | 31 | 1.000 | 0.871 | 31 |
| singapore | 31 | 1.000 | 0.742 | 31 |
| ALL | 310 | 0.999 | 0.713 | 310 |
- memory gate: PASS

## REC-ST (spatio-temporal recoverability, S6)
| city | n | date +-3mo | city exact | joint |
|---|---|---|---|---|
| nyc | 31 | 0.161 | 0.710 | 0.065 |
| milan | 31 | 0.226 | 0.000 | 0.000 |
| london | 31 | 0.129 | 0.097 | 0.000 |
| madrid | 31 | 0.129 | 0.000 | 0.000 |
| tokyo | 31 | 0.258 | 0.000 | 0.000 |
| melbourne | 31 | 0.129 | 0.000 | 0.000 |
| sydney | 31 | 0.194 | 0.000 | 0.000 |
| delhi | 31 | 0.226 | 0.000 | 0.000 |
| hongkong | 31 | 0.290 | 0.000 | 0.000 |
| singapore | 31 | 0.355 | 0.000 | 0.000 |
| ALL | 310 | 0.210 | 0.081 | 0.006 |
