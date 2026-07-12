# FM-1c Preregistration: Post-Cutoff Placebo, LAP Bridge, and W-Arm Seasonality Robustness

Status: **FROZEN**（先于任何 FM-1c API 调用；sha256 见 `FM1c_prereg_freeze.json`）
动机：三篇最近范式深读（Fake Date Tests arXiv:2601.07992 / Gao-Jiang-Yan arXiv:2512.23847 / Glasserman-Lin arXiv:2309.17322 + Lopez-Lira arXiv:2504.14765）后确认的三个必补项与一个已算口径披露。设计定稿于结果未见时；FM-1 主结果已见（并已发表于 FM1_RESULTS.md），FM-1c 各组件的假设均于本文件冻结。

## C1. Post-cutoff placebo（领域标准识别，FM-1 缺失项）

- **面板扩展**：决策日 2025-01-15 … 2026-06-15（18 个），vintage 快照来自 ALFRED（`outputs/fm1c/postcutoff_snapshots.json`，已拉取）。R 臂 prompt 以 2024-12-15 存档请求为模板，仅替换日期行、快照块、decision_date_used 行；D/M/W 变换规则与 FM-1 逐字一致。
- **Cutoff 界定**：gemini-2.5-flash 官方知识截止 2025-01；主 placebo 窗 = 2025-02 … 2026-06（17 日期），2025-01 报告但标注 boundary。
- **W 臂假日期（确定性，冻结）**：按索引 i（0 起）交替指派——偶数 i → `CRISIS[(i//2) % 11]`（FM-1 危机窗清单），奇数 i → `CALM_ANCHORS[(i//2) % 9]`，其中 CALM_ANCHORS = [2013-02-15, 2013-06-15, 2013-10-15, 2014-02-15, 2014-06-15, 2014-10-15, 2017-02-15, 2017-06-15, 2017-10-15]。
- **生成**：flash，每臂 3 reps（18×4×3 = 216 cells）。
- **预注册预测**：
  - P1：placebo 窗内 D−M 看空率差 ≈ 0（bootstrap CI 含 0；对照 pre-cutoff E2=+25.6pp）。
  - P2：W 臂 crisis-fake vs calm-fake 看空率差 > 0（pre-cutoff 日期 token 在 post-cutoff 数据上仍触发——触发持久性）。
  - P3：日期恢复探针在 placebo 窗崩塌（对齐口径下日历年命中率显著低于 pre-cutoff 的 80.4%；Lopez-Lira post-cutoff 基准 28.8%）。
  - P4：LAP（见 C2）在 placebo 窗崩塌（Gao 基准：post-cutoff LAP≈0）。
- **定位声明**（按 Lopez-Lira Proposition 2）：post-cutoff 窗仅 17 个月、无历史危机月，本组件为低功效 descriptive control；主识别仍是 W 臂移植（训练期内合成 placebo）。2025-04 关税回撤等 post-cutoff 市场事件的看空反应只能来自数据通道，作 P1 的解释背景。

## C2. LAP 桥接探针（Gao-Jiang-Yan 附录 C 程序的宏观适配）

- **措辞（冻结）**：`Between {t} and {t_plus_20td}, did the S&P 500 index go up or down? Answer based only on what you recall about the U.S. stock market in that specific period. If you do not recall, answer unknown. Respond with exactly one word: up, down, or unknown.` 其中 t_plus_20td 为 t 后第 20 个交易日的日历日期（自 spx_target_new.parquet 交易日历计算；2026-04 之后的窗口按 +28 日历日近似并标注）。
- **估计**：Gemini 不暴露 logprobs（已实测 400），按其附录 C 授权用**正温度重复采样频率近似**：每日期 20 reps，temperature=1.0。LAP_t = freq(up)+freq(down)；(U−D)_t = freq(up)−freq(down)。引用原文 "approximated, more coarsely, by answer frequencies" 为方案背书。
- **覆盖**：240 个 pre-cutoff + 18 个 post-cutoff 决策日（5,160 次调用）。LAP_fake(t) ≡ LAP_true(fake(t))，不另生成。
- **预注册分析**：
  - A1 验证：pre-cutoff 高 LAP（中位以上）子样本中 (U−D) 与实现方向的一致率 > 低 LAP 子样本。
  - A2 检测回归（映射 Gao β₃）：hit_t = φ·signal_t + η·LAP_t + δ·(signal_t×LAP_t) + ε，signal_t 取 R 臂多数票方向，HAC(lag 6)，单边检验 δ>0。
  - A3 移植第三重证据：W 臂逐日期看空率对 (U−D)_{fake(t)} 回归，系数应显著为负（fake 日期记忆的下行信号 → W 臂看空），对 (U−D)_{true(t)} 回归系数 ≈ 0。
  - A4 placebo：post-cutoff LAP 分布（预期 ≈0 / unknown 占优）。

## C3. W 臂季节性稳健（Fake Date Tests 自曝混淆的对应）

- 66 个月移位使月份翻转 6 个月，与 Fake Date Tests §4.3 的季节性警告直接相关。
- **W′ 臂**：72 个月移位（72 mod 12 = 0，月份保持），flash 3 reps × 240 = 720 cells，其余与 W 完全一致。
- **预注册预测**：E3′（W′ 按假日期归窗的 Gap_fake）与 E3 同向且同量级（差 < 10pp）→ 季节性不驱动移植效应。若 E3′ 显著弱于 E3，如实报告并将季节性列为 W 臂效应的部分解释。
- 附加检查（既有数据，无新调用）：W 臂内 calm-fake 日期间看空率的月份方差分析（A2-style 一致性）。

## C4. 已算口径披露（Lopez-Lira Table 3 对齐）

日期恢复探针（KT-1，masked 宏观快照输入）按 B 同定义重算：日历年命中 80.4%、月+年命中 37.1%、平均绝对月差 5.96（中位 1）。论文中与 B 的 98.45%/90.38%/9.52 天**分行并置 + 三重差异脚注**（输入信息量：8 值宏观快照 vs 每日约 9 条 WSJ 头版；容差定义；模型），±12 月口径（92.5%）单独报告，绝不与 98.5% 同列。

## 纪律与报告规范（吸收自三文）

- 各臂报告 refusal/无效输出计数与温度设定（仿 Lopez-Lira 每表 Refusals 列）。
- R/D/M/W 在相同决策月上做配对对比（仿 Glasserman-Lin 同日配对逻辑）。
- E5 措辞：+7.0pp CI 下界 = 0.000，行文用 "directionally positive, borderline"，不写 significant（Prop 2 精神）。
- 术语（冻结）：E2 类效应称 functional lookahead bias（参数通道，随 Lopez-Lira），E1 类称 prompt-level training leakage（随 Ludwig et al.）；不使用 Glasserman-Lin 的 distraction 指代 E1。
- M 臂 Gap≈0 的解释边界：引 Lopez-Lira Remark 1，明示其为污染下界证据；核心表述为 "elicitable ≠ behaviorally active"，不主张 masking 为通用解。
