# ST-1 results: gemini-2.5-flash-pooled (prereg f0284181)

coverage (nodes with >=1 valid sketch): {'M': 310, 'D': 310, 'L': 310, 'DL': 310, 'S': 310}
crisis nodes 28, calm nodes 50

| arm | share(crisis) | share(calm) | Gap |
|---|---|---|---|
| M | 0.681 | 0.465 | +0.216 |
| D | 0.737 | 0.445 | +0.292 |
| L | 0.730 | 0.487 | +0.242 |
| DL | 0.795 | 0.452 | +0.343 |

- **E2 (time trigger, S1) = +0.076** node-CI [-0.010, +0.164] (incl0); city-cluster CI [+0.018, +0.152]
- **E2L (place trigger, S2) = +0.027** node-CI [-0.042, +0.094] (incl0); city-cluster CI [-0.023, +0.081]
- **E2DL (joint key, S3) = +0.127** node-CI [+0.060, +0.198] (excl0); city-cluster CI [+0.054, +0.203]
- **INT = E2DL - E2 - E2L (S3) = +0.025** node-CI [-0.070, +0.123] (incl0); city-cluster CI [-0.025, +0.082]

S arm: Gap_true = +0.298, Gap_fake = +0.111 (fake-crisis nodes 28)
- **E3L (spatial transplant, S4) = -0.188** CI [-0.366, -0.009] (excl0)
  - post-freeze reference: D-arm fake-minus-true = -0.212 (the E3L value 'place ignored' predicts)
  - **relocation: Gap_fake(S) - Gap_fake(D) = +0.031** node-CI [-0.040, +0.109] (incl0)
  - **interference: Gap_true(S) - Gap_true(D) = +0.007** node-CI [-0.061, +0.074] (incl0)

| city | n_crisis | Gap(M) | Gap(D) | E2_city | Gap(L) | Gap(DL) |
|---|---|---|---|---|---|---|
| nyc | 1 | +0.53 | +0.71 | +0.19 | +0.47 | +0.76 |
| milan | 2 | +0.50 | +0.64 | +0.14 | +0.36 | +0.70 |
| london | 3 | +0.48 | +0.41 | -0.07 | +0.52 | +0.53 |
| madrid | 2 | -0.06 | +0.35 | +0.41 | -0.01 | +0.27 |
| tokyo | 4 | +0.19 | +0.16 | -0.03 | +0.13 | +0.08 |
| melbourne | 6 | +0.26 | +0.38 | +0.12 | +0.26 | +0.34 |
| sydney | 2 | +0.48 | +0.61 | +0.13 | +0.51 | +0.61 |
| delhi | 2 | +0.10 | +0.16 | +0.06 | +0.22 | +0.39 |
| hongkong | 3 | -0.19 | -0.13 | +0.06 | +0.01 | -0.02 |
| singapore | 3 | -0.03 | -0.04 | -0.01 | +0.06 | +0.13 |

## LAP-ST (memory gate S5: hit > majority-class 0.629)
| city | nodes | recall rate | hit | hit_n |
|---|---|---|---|---|
| nyc | 31 | 0.942 | 0.806 | 31 |
| milan | 31 | 0.919 | 0.667 | 30 |
| london | 31 | 0.982 | 0.871 | 31 |
| madrid | 31 | 0.939 | 0.774 | 31 |
| tokyo | 31 | 0.953 | 0.903 | 31 |
| melbourne | 31 | 0.977 | 0.800 | 30 |
| sydney | 31 | 0.977 | 0.774 | 31 |
| delhi | 31 | 0.956 | 0.806 | 31 |
| hongkong | 31 | 0.985 | 0.867 | 30 |
| singapore | 31 | 0.976 | 0.903 | 31 |
| ALL | 310 | 0.961 | 0.818 | 307 |
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
