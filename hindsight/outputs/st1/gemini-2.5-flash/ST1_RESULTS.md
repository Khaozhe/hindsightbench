# ST-1 results: gemini-2.5-flash (prereg f0284181)

coverage (nodes with >=1 valid sketch): {'M': 308, 'D': 310, 'L': 310, 'DL': 309, 'S': 310}
crisis nodes 28, calm nodes 50

| arm | share(crisis) | share(calm) | Gap |
|---|---|---|---|
| M | 0.661 | 0.480 | +0.181 |
| D | 0.746 | 0.465 | +0.281 |
| L | 0.732 | 0.465 | +0.267 |
| DL | 0.795 | 0.485 | +0.310 |

- **E2 (time trigger, S1) = +0.100** node-CI [+0.012, +0.188] (excl0); city-cluster CI [+0.053, +0.156]
- **E2L (place trigger, S2) = +0.086** node-CI [-0.006, +0.180] (incl0); city-cluster CI [-0.016, +0.195]
- **E2DL (joint key, S3) = +0.129** node-CI [+0.051, +0.211] (excl0); city-cluster CI [+0.029, +0.242]
- **INT = E2DL - E2 - E2L (S3) = -0.057** node-CI [-0.169, +0.056] (incl0); city-cluster CI [-0.136, +0.022]

S arm: Gap_true = +0.341, Gap_fake = +0.127 (fake-crisis nodes 28)
- **E3L (spatial transplant, S4) = -0.214** CI [-0.397, -0.031] (excl0)
  - post-freeze reference: D-arm fake-minus-true = -0.232 (the E3L value 'place ignored' predicts)
  - **relocation: Gap_fake(S) - Gap_fake(D) = +0.078** node-CI [-0.010, +0.168] (incl0)
  - **interference: Gap_true(S) - Gap_true(D) = +0.061** node-CI [-0.034, +0.156] (incl0)

| city | n_crisis | Gap(M) | Gap(D) | E2_city | Gap(L) | Gap(DL) |
|---|---|---|---|---|---|---|
| nyc | 1 | +0.42 | +0.60 | +0.17 | +0.57 | +0.78 |
| milan | 2 | +0.39 | +0.61 | +0.23 | +0.66 | +0.62 |
| london | 3 | +0.32 | +0.45 | +0.13 | +0.52 | +0.57 |
| madrid | 2 | +0.03 | +0.28 | +0.25 | -0.07 | +0.30 |
| tokyo | 4 | +0.19 | +0.18 | -0.01 | +0.18 | +0.06 |
| melbourne | 6 | +0.39 | +0.42 | +0.03 | +0.22 | +0.28 |
| sydney | 2 | +0.44 | +0.64 | +0.20 | +0.59 | +0.57 |
| delhi | 2 | +0.03 | +0.06 | +0.04 | +0.12 | +0.32 |
| hongkong | 3 | -0.18 | -0.15 | +0.03 | +0.07 | -0.07 |
| singapore | 3 | -0.19 | -0.07 | +0.13 | +0.07 | +0.08 |

## LAP-ST (memory gate S5: hit > majority-class 0.629)
| city | nodes | recall rate | hit | hit_n |
|---|---|---|---|---|
| nyc | 31 | 0.944 | 0.833 | 30 |
| milan | 31 | 0.919 | 0.645 | 31 |
| london | 31 | 0.985 | 0.871 | 31 |
| madrid | 31 | 0.931 | 0.742 | 31 |
| tokyo | 31 | 0.950 | 0.900 | 30 |
| melbourne | 31 | 0.971 | 0.833 | 30 |
| sydney | 31 | 0.974 | 0.742 | 31 |
| delhi | 31 | 0.958 | 0.828 | 29 |
| hongkong | 31 | 0.985 | 0.867 | 30 |
| singapore | 31 | 0.976 | 0.871 | 31 |
| ALL | 310 | 0.959 | 0.812 | 304 |
- memory gate: PASS

## REC-ST (spatio-temporal recoverability, S6)
| city | n | date +-3mo | city exact | joint |
|---|---|---|---|---|
| nyc | 31 | 0.161 | 0.258 | 0.129 |
| milan | 31 | 0.194 | 0.000 | 0.000 |
| london | 31 | 0.194 | 0.097 | 0.000 |
| madrid | 31 | 0.258 | 0.032 | 0.032 |
| tokyo | 31 | 0.290 | 0.097 | 0.032 |
| melbourne | 31 | 0.097 | 0.000 | 0.000 |
| sydney | 31 | 0.226 | 0.000 | 0.000 |
| delhi | 31 | 0.258 | 0.000 | 0.000 |
| hongkong | 31 | 0.097 | 0.000 | 0.000 |
| singapore | 31 | 0.226 | 0.000 | 0.000 |
| ALL | 310 | 0.200 | 0.048 | 0.019 |
