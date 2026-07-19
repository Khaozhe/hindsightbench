# GD-1 Results (prereg 394c9ad4)

覆盖: D=240 M=240 W=240 日期

指标口径: yield-down share 的危机−平静 gap（+ = 危机窗更多'收益率降'）

- Gap_down(D) = +0.551, Gap_down(M) = -0.017
- **G1 E2_10Y = +0.567, CI [+0.362, +0.757]** (判定: PASS)
- **G2 移植: Gap_down_fake(W) = +0.397 / Gap_down_true(W) = -0.221, fake−true CI [+0.334, +0.876]**
- **G3 叙事内容: E2_10Y 符号 = + (危机→收益率降，flight-to-quality，与 SPX 反号) PASS**
- **G4 LAP-10Y: pre 均值 0.957, hit 92.2% (n=232)** (判定: PASS)

## 探索性补充（G3 识别缺陷的文本级补救，post-hoc 披露）

冻结的 G3 符号检验在 10Y 上无法区分"结构化避险叙事"与"危机→无脑输出 −"（编码巧合，两者同号——缺陷在实现时发现并预先记录于 DRAFT_AUDIT_TODO #11）。文本级证据：W 臂叙事中显式避险语义（flight to quality / safe haven / risk-off）出现率——**危机假日期 28/88 = 31.8% vs 平静假日期 27/288 = 9.4%（3.4×）**。模型在假危机日期下书面陈述避险经济学机制，支持结构化叙事假设而非 token 反射。

## 一句话总结

"Date is the trigger" 是跨任务性质：债券任务上日期触发效应（+56.7pp）约为股票任务（+25.6pp）的两倍，移植效应同样成立（fake−true CI [+33.4, +87.6]），LAP-10Y 记忆更强（答题率 0.957 / 命中 92.2%）。触发的是有内容的危机叙事（避险语义 3.4×），且方向随资产类别正确分化（股跌/债涨）。

## GD-1b：VIX micro-arm（G3 锐利识别，prereg 7bfb50e7 + v2 addendum）

W 臂 only、假标签∈危机∪平静的 47 日期、flash 1 rep、direction 语义钉死（v2 加成，在零个 fake-crisis 生成前冻结）。**结果：fake-crisis VIX-up 份额 92.1% (81/88) vs fake-calm 55.6% (160/288)，Δ = +36.5pp，Fisher 双侧 p = 2.5e-11——预注册预测（≥+15pp）通过**。假危机日期下模型对 VIX 说涨、对 SPX 说跌（GD-1 对 10Y 说降）：移植的叙事在唯一要求符号翻转的资产上翻转了符号，"危机→无脑输出 −"反射假说被排除。G3 从符号检验缺陷升级为三资产符号三角识别。数据：hindsight/outputs/gd1b/（GD1B_RESULTS.json + 全 W 臂原始响应）。实付 ~$1.3（51 次调用）。
