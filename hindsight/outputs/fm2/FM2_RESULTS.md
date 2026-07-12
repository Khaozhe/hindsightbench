# FM-2 Results (per frozen prereg deb018b9)

## T1 租金衰减曲线（危机窗−平静窗 bearish gap）

| Stage | R 臂 | M 臂 | R−M |
|---|---|---|---|
| S0 sketch | +0.213 | +0.064 | +0.149 |
| S1 compiled | +0.221 | +0.054 | +0.167 |
| S2 L1 | +0.221 | +0.054 | +0.167 |
| S3 top-K | +0.221 | +0.054 | +0.167 |
| S4 production | +0.091 | +0.000 | +0.091 |

元素计数 R: sketch/compiled/L1 = [1920, 4758, 4758], M: [1920, 4765, 4765]

## T2 生产租金 (2019+ OOS)

- Acc: R=0.7042 vs M=0.7183 vs always-long=0.7042 (n=71)
- Acc_R − Acc_M = -0.0141, 95% CI [-0.0423, +0.0000] (paired bootstrap B=10000)
- 危机窗(OOS内) Acc: R=0.800 vs M=0.800
- neg calls: R=0 vs M=1
- sign-only Sharpe: R=0.695 vs M=0.794
