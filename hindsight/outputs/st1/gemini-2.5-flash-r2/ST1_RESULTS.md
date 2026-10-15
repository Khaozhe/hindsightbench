# ST-1 results: gemini-2.5-flash-r2 (prereg f0284181)

coverage (nodes with >=1 valid sketch): {'M': 309, 'D': 308, 'L': 308, 'DL': 308, 'S': 310}
crisis nodes 28, calm nodes 50

| arm | share(crisis) | share(calm) | Gap |
|---|---|---|---|
| M | 0.701 | 0.450 | +0.251 |
| D | 0.728 | 0.425 | +0.303 |
| L | 0.728 | 0.510 | +0.218 |
| DL | 0.795 | 0.417 | +0.378 |

- **E2 (time trigger, S1) = +0.052** node-CI [-0.067, +0.177] (incl0); city-cluster CI [-0.060, +0.173]
- **E2L (place trigger, S2) = -0.033** node-CI [-0.141, +0.067] (incl0); city-cluster CI [-0.176, +0.080]
- **E2DL (joint key, S3) = +0.127** node-CI [+0.032, +0.225] (excl0); city-cluster CI [+0.021, +0.221]
- **INT = E2DL - E2 - E2L (S3) = +0.109** node-CI [-0.033, +0.253] (incl0); city-cluster CI [-0.023, +0.263]

S arm: Gap_true = +0.256, Gap_fake = +0.095 (fake-crisis nodes 28)
- **E3L (spatial transplant, S4) = -0.161** CI [-0.344, +0.022] (incl0)
  - post-freeze reference: D-arm fake-minus-true = -0.192 (the E3L value 'place ignored' predicts)
  - **relocation: Gap_fake(S) - Gap_fake(D) = -0.016** node-CI [-0.111, +0.083] (incl0)
  - **interference: Gap_true(S) - Gap_true(D) = -0.047** node-CI [-0.131, +0.034] (incl0)

| city | n_crisis | Gap(M) | Gap(D) | E2_city | Gap(L) | Gap(DL) |
|---|---|---|---|---|---|---|
| nyc | 1 | +0.62 | +0.82 | +0.20 | +0.38 | +0.75 |
| milan | 2 | +0.61 | +0.68 | +0.06 | +0.05 | +0.78 |
| london | 3 | +0.64 | +0.37 | -0.27 | +0.53 | +0.49 |
| madrid | 2 | -0.14 | +0.43 | +0.56 | +0.06 | +0.25 |
| tokyo | 4 | +0.19 | +0.14 | -0.04 | +0.09 | +0.10 |
| melbourne | 6 | +0.12 | +0.34 | +0.22 | +0.30 | +0.40 |
| sydney | 2 | +0.53 | +0.59 | +0.06 | +0.42 | +0.65 |
| delhi | 2 | +0.18 | +0.26 | +0.09 | +0.32 | +0.45 |
| hongkong | 3 | -0.20 | -0.11 | +0.09 | -0.05 | +0.03 |
| singapore | 3 | +0.13 | -0.01 | -0.14 | +0.06 | +0.19 |

## LAP-ST (memory gate S5: hit > majority-class 0.629)
| city | nodes | recall rate | hit | hit_n |
|---|---|---|---|---|
| nyc | 31 | 0.940 | 0.839 | 31 |
| milan | 31 | 0.919 | 0.700 | 30 |
| london | 31 | 0.979 | 0.871 | 31 |
| madrid | 31 | 0.947 | 0.774 | 31 |
| tokyo | 31 | 0.956 | 0.903 | 31 |
| melbourne | 31 | 0.984 | 0.774 | 31 |
| sydney | 31 | 0.979 | 0.742 | 31 |
| delhi | 31 | 0.955 | 0.806 | 31 |
| hongkong | 31 | 0.985 | 0.867 | 30 |
| singapore | 31 | 0.976 | 0.871 | 31 |
| ALL | 310 | 0.962 | 0.815 | 308 |
- memory gate: PASS

## REC-ST (spatio-temporal recoverability, S6)
| city | n | date +-3mo | city exact | joint |
|---|---|---|---|---|
| nyc | 31 | 0.161 | 0.290 | 0.129 |
| milan | 31 | 0.194 | 0.000 | 0.000 |
| london | 31 | 0.161 | 0.097 | 0.000 |
| madrid | 31 | 0.161 | 0.032 | 0.032 |
| tokyo | 31 | 0.290 | 0.065 | 0.032 |
| melbourne | 31 | 0.129 | 0.000 | 0.000 |
| sydney | 31 | 0.258 | 0.000 | 0.000 |
| delhi | 31 | 0.194 | 0.000 | 0.000 |
| hongkong | 31 | 0.129 | 0.000 | 0.000 |
| singapore | 31 | 0.226 | 0.000 | 0.000 |
| ALL | 310 | 0.190 | 0.048 | 0.019 |
