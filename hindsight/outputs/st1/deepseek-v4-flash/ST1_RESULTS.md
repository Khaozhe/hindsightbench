# ST-1 results: deepseek-v4-flash (prereg f0284181)

coverage (nodes with >=1 valid sketch): {'M': 310, 'D': 310, 'L': 310, 'DL': 310, 'S': 309}
crisis nodes 28, calm nodes 50

| arm | share(crisis) | share(calm) | Gap |
|---|---|---|---|
| M | 0.629 | 0.487 | +0.142 |
| D | 0.696 | 0.445 | +0.251 |
| L | 0.634 | 0.465 | +0.169 |
| DL | 0.777 | 0.427 | +0.349 |

- **E2 (time trigger, S1) = +0.109** node-CI [+0.027, +0.194] (excl0); city-cluster CI [+0.046, +0.163]
- **E2L (place trigger, S2) = +0.027** node-CI [-0.040, +0.096] (incl0); city-cluster CI [-0.040, +0.080]
- **E2DL (joint key, S3) = +0.207** node-CI [+0.124, +0.294] (excl0); city-cluster CI [+0.138, +0.298]
- **INT = E2DL - E2 - E2L (S3) = +0.071** node-CI [-0.045, +0.182] (incl0); city-cluster CI [-0.022, +0.185]

S arm: Gap_true = +0.251, Gap_fake = +0.189 (fake-crisis nodes 28)
- **E3L (spatial transplant, S4) = -0.062** CI [-0.210, +0.085] (incl0)
  - post-freeze reference: D-arm fake-minus-true = -0.170 (the E3L value 'place ignored' predicts)
  - **relocation: Gap_fake(S) - Gap_fake(D) = +0.107** node-CI [+0.021, +0.195] (excl0)
  - **interference: Gap_true(S) - Gap_true(D) = -0.000** node-CI [-0.085, +0.086] (incl0)

| city | n_crisis | Gap(M) | Gap(D) | E2_city | Gap(L) | Gap(DL) |
|---|---|---|---|---|---|---|
| nyc | 1 | +0.20 | +0.60 | +0.40 | -0.03 | +0.72 |
| milan | 2 | +0.22 | +0.36 | +0.14 | +0.36 | +0.65 |
| london | 3 | +0.22 | +0.37 | +0.15 | +0.29 | +0.39 |
| madrid | 2 | +0.03 | +0.24 | +0.21 | +0.18 | +0.42 |
| tokyo | 4 | +0.09 | +0.19 | +0.10 | +0.04 | +0.22 |
| melbourne | 6 | +0.17 | +0.30 | +0.13 | +0.24 | +0.21 |
| sydney | 2 | +0.53 | +0.34 | -0.19 | +0.45 | +0.59 |
| delhi | 2 | +0.16 | +0.31 | +0.15 | +0.14 | +0.54 |
| hongkong | 3 | -0.12 | +0.03 | +0.14 | -0.07 | +0.03 |
| singapore | 3 | +0.07 | +0.10 | +0.03 | -0.02 | +0.18 |

## LAP-ST (memory gate S5: hit > majority-class 0.629)
| city | nodes | recall rate | hit | hit_n |
|---|---|---|---|---|
| nyc | 31 | 0.858 | 0.800 | 30 |
| milan | 31 | 0.771 | 0.774 | 31 |
| london | 31 | 0.742 | 0.871 | 31 |
| madrid | 31 | 0.724 | 0.645 | 31 |
| tokyo | 31 | 0.613 | 0.793 | 29 |
| melbourne | 31 | 0.919 | 0.774 | 31 |
| sydney | 31 | 0.840 | 0.710 | 31 |
| delhi | 31 | 0.482 | 0.667 | 24 |
| hongkong | 31 | 0.689 | 0.931 | 29 |
| singapore | 31 | 0.713 | 0.774 | 31 |
| ALL | 310 | 0.735 | 0.775 | 298 |
- memory gate: PASS

## REC-ST (spatio-temporal recoverability, S6)
| city | n | date +-3mo | city exact | joint |
|---|---|---|---|---|
| nyc | 31 | 0.161 | 1.000 | 0.161 |
| milan | 31 | 0.161 | 0.000 | 0.000 |
| london | 31 | 0.161 | 0.000 | 0.000 |
| madrid | 31 | 0.161 | 0.000 | 0.000 |
| tokyo | 31 | 0.161 | 0.000 | 0.000 |
| melbourne | 31 | 0.161 | 0.000 | 0.000 |
| sydney | 31 | 0.161 | 0.000 | 0.000 |
| delhi | 31 | 0.194 | 0.000 | 0.000 |
| hongkong | 31 | 0.161 | 0.000 | 0.000 |
| singapore | 31 | 0.194 | 0.000 | 0.000 |
| ALL | 310 | 0.168 | 0.100 | 0.016 |
