# KT-1 Preregistration: Date/Context-Masked Kill Test for Parametric Hindsight

Status: **FROZEN** (frozen before any KT-1 API call; freeze timestamp and sha256 in `KT1_prereg_freeze.json`)
Project: hindsight (方向 A — LLM 参数化后见之明量化)
Author: Claude (session ba31a806), authorized by user 2026-07-02

## 1. 研究问题

V1 生产 sketch 面板（`macrochain/data/processed/sketches_panel.jsonl`，1,920 条 = 240 决策日 × 8，gemini-2.5-flash，2026-04 生成）表现出危机月看空偏置：

- 危机窗合并 bearish 率 57/88 = 64.8%，平静年 95/288 = 33.0%，Gap_R = 31.8pp（两比例 z = 5.32）。

该偏置可能来自三个通道：
- **C1 显式日期**：prompt 第 1 行 "Decision time point: YYYY-MM-DD" 触发参数记忆；
- **C2 泄漏上下文**：全样本目标摘要（2005→2024 正类基率 65.5%）、每序列 revised_value、vintage_date 绝对日期；
- **C3 数据本身**：vintage 值的合法信息内容（如 2008-10 的 UNRATE 水平与走势本身就支持看空）。

KT-1 回答一个 gate 问题：**移除 C1+C2（保留 C3）后，危机月看空偏置是否消失？**

## 2. 干预设计

**Masked 臂**（本次新生成）：对 240 条 V1 原始请求（`sketch_batch_requests.jsonl`）逐条施加如下确定性变换，其余逐字不动：

1. 首行 `Decision time point: YYYY-MM-DD - only information available on or before this date is admissible as evidence.` → `Decision time point: [undisclosed]. Only information contained in this snapshot is admissible as evidence.`
2. Target Panel Summary 块中删除以下行：`Date range`、`Total sessions`、`Positive days`、`Negative days`、`Pos/Neg ratio`（保留 Ticker、Data mode、Source、Target 定义行——任务定义，非泄漏）。
3. 删除 `decision_date_used:` 与 `model_ready_panel_rows:` 两行。
4. 每序列行 `- <ID>: vintage_date=YYYY-MM-DD, vintage_value=<v>, revised_value=<r>` → `- <ID>: asof=t-<k>mo, value=<v>`，其中 k = 决策日与 vintage_date 的整月差（保留新近度结构，消除绝对日期与修订值）。

**Fail-closed 断言**：变换后 user prompt 若仍匹配 `\d{4}-\d{2}`、包含 `revised` 或 `65.5`，脚本必须拒绝发送该请求并报错退出。

**生成参数与 V1 严格同参**：model=`models/gemini-2.5-flash`，temperature=0.2，maxOutputTokens=4096，responseMimeType=application/json，system prompt 逐字不变，每日期请求 8 条 sketch，schema 同 V1。

**日期恢复探针**（同轮执行，每日期 1 次，temperature=0）：仅提供 masked 臂变换后的宏观快照块（8 行 `- <ID>: asof=t-<k>mo, value=<v>`），提问该快照最可能对应的日历年月，要求输出 JSON `{"estimated_date": "YYYY-MM"}`。度量 C3 值对日期的隐式可恢复性（Lopez-Lira 重构威胁的一阶段测量）。

## 3. 终点与判据

**主终点（唯一）**：Gap_M = bearish 率(危机窗) − bearish 率(平静窗)，masked 臂，与冻结的 Gap_R = 31.8pp 对比。

窗口定义（与侦察口径一致，冻结）：
- 危机窗（11 个决策日）：2008-09-15、2008-10-15、2008-11-15、2008-12-15、2009-01-15、2009-02-15、2020-03-15、2020-04-15、2022-06-15、2022-09-15、2022-10-15。
- 平静窗（36 个决策日）：2013、2014、2017 三个整年的全部月度决策日。

bearish 定义：sketch 的 `direction == "-"`。分母为该窗内 schema 有效 sketch 数（非固定 88/288，以实际 valid 数为准，V1 臂按相同规则重算）。

**推断**：paired-by-date bootstrap（重抽 240 个决策日，B = 10,000，seed = 2026），对 Δ = Gap_R − Gap_M 报 95% CI。

**判定规则（冻结）**：
| 条件 | 判定 |
|---|---|
| Δ ≥ 10pp 且 CI 排除 0 | **GO** — C1/C2 通道显著驱动，headline 成立 |
| Gap_M ≥ Gap_R − 5pp 且日期恢复率低（估计月份落入真实月份 ±12 个月的比例 < 25%） | **KILL** — C3 数据通道解释偏置，无参数化 hindsight 故事 |
| Gap_M ≥ Gap_R − 5pp 且日期恢复率高（≥ 25%） | **GO-pivot** — 偏置经由值→日期的隐式召回，转向 wrong-date 臂为主的设计 |
| 其余 | **GO-reframe** — 通道混合，论文重心放在分解本身 |

**次要终点（纯描述，不参与判定）**：逐年 bearish 率曲线（两臂对比）；2023 年均 bearish 率；2020-03/2020-04 的 bearish 计数；日期恢复误差分布；机制叙述中时代专名（如 "financial crisis"、"pandemic"）出现率。

## 4. 纪律约束

- 本 prereg 冻结先于任何 KT-1 API 调用；变换规则、窗口、判据不得事后修改，如修改必须在结果文档中显式披露为 deviation。
- KT-1 结果仅用于 GO/KILL 决策与描述性报告，不用于任何模型/超参选择。
- V1 臂数据只读；本项目不修改 `macrochain/` 下任何文件。
- 全部产物落 `hindsight/outputs/kt1/`：`masked_nodes/<date>/{01_sketches_valid.json,03_run_meta.json,04_raw_response.txt}`（对齐 V1 节点结构）、`date_probe_results.jsonl`、`KT1_DECISION.md`。
- 已知局限（预先声明）：masked 臂无法阻止模型从值反推日期（由探针量化）；V1 臂与 masked 臂生成相隔约 11 周，模型端点若有静默更新会混入版本效应（记录 modelVersion 响应字段以监控；若 KT-1 判 GO，全矩阵将在同一时段重生成 revealed 臂消除该混杂）。
