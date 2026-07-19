# FM-1g 预注册：自诱发日期两段式实验（Self-Elicited Date, Two-Stage Prompt）

冻结时间：见 FM1g_freeze.json（本文件 sha256 冻结于任何 API 调用之前，含 smoke）。

## 动机（评审 Q1 / elicitable≠active 的边界条件）

论文一的核心解离：模型能从脱敏数据 92.5% 重构决策日期（elicitable），但被脱敏
时行为上零激活（not behaviorally active），除非 prompt 显式给出日期 token。
评审问题：若一个两段式 prompt 先让模型自己推断日期、再生成假设——模型**自己写
进上下文**的日期 token 是否重新点燃触发？两个结果都有解释价值：
- 重燃 → "操作性的是上下文中的 token，与断言来源无关"（与 FM-1e 裸日期结论
  同构）；masking 的行为学效力是 prompt-policy 相关的（§6.1 的 lower-bound
  措辞已预留此空间）。
- 不燃 → masking 在 elicit-then-generate 政策下依然行为有效，解离更强。

## 设计

**基底**：冻结 M 变换逐字保留（date line = "[undisclosed]" 版 M_LINE 不变——
不存在任何用户断言的日期）。在 user prompt 末尾追加一段前置任务指令。

**两个变体**（隔离"日期语义" vs "任何前置任务"）：
- **GDATE**：先从快照推断最可能的决策日期，单独一行输出
  `INFERRED DATE: YYYY-MM`，然后按原规格生成 8 个 sketches。
  （不指示"利用该日期"——测的是纯粹的 elicitation-into-context；
  instructed-use 变体显式排除在本预注册范围外。）
- **GNEUT**（中性预热对照）：先识别近期变化最大的单一系列，单独一行输出
  `SALIENT SERIES: NAME`，然后按原规格生成 8 个 sketches。
  （结构、长度与 GDATE 匹配，无日期语义。）

**执行**：47 窗口日期（11 危机 + 36 平静，与 FM-1e 相同）× 2 变体 × 1 rep，
gemini-2.5-flash，temperature 0.2，max_tokens 8192，与 FM-1/FM-1e 同一 serving。
共 94 个生成调用 + smoke 4 调用（2008-10-15 / 2014-04-15 × 2 变体）。

## 估计量与判定规则（先于数据固定）

以冻结 M 臂（rep1-3）为参照，paired date-level bootstrap B=10,000 seed=2026：

- **主估计量** E2_gdate = Gap(GDATE) − Gap(M)（按真实日期窗口评分）。
- **对照** E2_gneut = Gap(GNEUT) − Gap(M)（预期 ≈ 0；若其 CI 排零，说明前置
  任务本身扰动生成，主结论解释须加 caveat，如实报）。
- **参照带** E2_win = Gap(D) − Gap(M)（同 47 日期，冻结臂，FM-1e 已算 +25.6pp）。
- **次级（描述性）**：(a) GDATE 每次生成解析 `INFERRED DATE` 行，报告推断
  准确率（对齐 REC 探针口径：年内/±12月）；(b) 按各生成自己的推断日期重评分
  的 gap（W 臂双评分的类比）。解析失败的生成计入缺失并披露条数。

**判定规则**：
- SELF-TRIGGER：E2_gdate CI 排零 且 est ≥ E2_win − 10pp。
- NO-SELF-TRIGGER：E2_gdate CI 含零 且 est < 10pp。
- PARTIAL：其余情形（如实报点估计与区间，不强行归类）。
- GNEUT 判定不改变上述归类，只决定是否附加 caveat。

## 披露与预算

- 1 rep / 变体（与 FM-1e 相同的已披露局限）。
- 本实验在外部评审后设计（时间戳见 freeze），非论文冻结核心的一部分；
  入稿位置为补充材料 Appendix E.7，标注 review-prompted。
- 成本信封：≤ $3（gemini 账本逐条落账；smoke 实测后向用户报价，批准后跑全量）。
- 幂等断点续跑：per-cell 落盘，重跑跳过已完成 cell。
