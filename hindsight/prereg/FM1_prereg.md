# FM-1 Preregistration: Four-Arm Channel Decomposition of Parametric Hindsight

Status: **FROZEN**（冻结先于任何 FM-1 API 调用；时间戳与 sha256 见 `FM1_prereg_freeze.json`）
前置：KT-1 判 GO（`outputs/kt1/KT1_DECISION.md`，Δ=25.4pp CI[12.5,38.0]）。
项目：hindsight（方向 A）。作者：Claude（session ba31a806），用户 2026-07-02 授权。

## 1. 设计

**四臂**，每臂 240 个决策日（2005-01-15…2024-12-15），每次调用请求 8 条 sketch，schema/system prompt/温度（0.2）与 V1 一致，maxOutputTokens=8192（KT-1 deviation 的延续，对全部臂统一）：

| 臂 | 显式日期行 | 上下文 | 定义 |
|---|---|---|---|
| **R** | 真日期 | 泄漏版（V1 原文：vintage_date 绝对日期 + revised_value + 全样本目标摘要） | V1 prompt 逐字重放（今日重生成，消除 2026-04 端点版本混杂；存档 V1 面板另作稳健性对照，不进主分析） |
| **D** | 真日期 | 干净版（KT-1 变换：asof=t-k 相对标签，无 revised，无全样本摘要） | 分离 C1（日期字符串）与 C2（泄漏上下文） |
| **M** | 无（[undisclosed]） | 干净版 | = KT-1 masked 臂（replicate 1 复用今日 KT-1 产物；新增 replicates 今日生成） |
| **W** | **假日期** | 干净版 | 日期移植：第 i 个决策日标注第 (i+66) mod 240 个决策日的日期（确定性 66 个月移位，破坏商业周期相位；无随机数） |

**Replicates**：主模型 gemini-2.5-flash 每臂 3 个 replicate（M 臂含 KT-1 已有 1 个 + 新增 2 个；R/D/W 各 3 个）。副模型 gemini-2.5-pro 每臂 1 个 replicate。合计新增 sketch 调用 = flash 240×(3+3+2+3)=2,640 + pro 240×4=960 = 3,600。

**产物结构**：`outputs/fm1/<model>/<arm>/rep<k>/<date>/{01_sketches_valid.json,02_prompt.txt,03_run_meta.json,04_raw_response.txt}`。fail-closed 泄漏断言按臂定制（D/M/W 沿用 KT-1 规则并针对臂放行对应日期行；R 臂跳过断言）。

## 2. 预注册终点

窗口与 bearish 定义沿用 KT-1（冻结不变）。Gap(arm) = 危机窗看空率 − 平静窗看空率（flash 臂用 3 个 replicate 合并计数；pro 臂单 replicate）。

**E1 泄漏上下文效应（C2）**：Gap(R) − Gap(D)，paired bootstrap（同 KT-1 方案，B=10000, seed=2026）95% CI。
**E2 日期字符串效应（C1）**：Gap(D) − Gap(M)，同上。
**E3 日期移植检验（主检验）**：W 臂中，按**假**日期归窗计算 Gap_fake(W)，按**真**日期归窗计算 Gap_true(W)。假设：Gap_fake(W) > 0 且 Gap_true(W) ≈ Gap(M)。推断：对 Gap_fake(W) 与 Gap_true(W) 各报 bootstrap CI，并报 Gap_fake(W) − Gap_true(W) 的 CI。
**E4 salience 梯度**：逐日期 hindsight 强度 h_t = bearish_R(t) − bearish_M(t)（flash，3 replicates 合并），OLS 回归于冻结协变量集：(a) 当月已实现 20 日前向收益 fwd_ret_t（数据通道对照）；(b) 当月 SPX 回撤深度 drawdown_t（月内最低收盘/月初收盘−1，来自 spx_target.parquet，salience 代理 1）；(c) NBER 衰退指示 usrec_t（FRED USREC，salience 代理 2）；(d) VIX 月均 vix_t（FRED VIXCLS，salience 代理 3）。HAC(Newey-West, lag=6) 标准误。假设：salience 代理系数显著而 fwd_ret_t 不显著。协变量集冻结为以上四个；媒体叙事量代理（新闻计数）声明为 FM-2 扩展，不进本回归。
**E5 hindsight≠accuracy**：各臂 sketch 方向对 realized direction_20d 的命中率（多数票与逐 sketch 两种口径），全窗与分窗报告。假设：R 臂危机窗命中率高于 M 臂，但全窗 R ≈ M（净准确率优势 ≈ 0）。报 paired bootstrap CI。

**多重性**：E1–E5 全部报告，无选择性省略；E3 为主检验。

## 3. 纪律

- 本文件冻结先于任何 FM-1 生成调用；变更须作为 deviation 披露。
- KT-1 的 M 臂数据复用为 M/rep1，不重算不筛选。
- 分析代码在生成完成前写完并冻结 sha256（`analyze_fm1.py`）；先跑 flash 主分析，pro 为稳健性。
- V1 存档面板（2026-04 生成）只作"端点版本稳健性"对照表，不进主分析。
- 外部数据（USREC、VIXCLS）经 FRED API 拉取后落盘 `outputs/fm1/covariates/`，含拉取时间戳与 series 版本信息。
- 已知局限（预声明）：W 臂假日期与快照数据不一致可能被模型察觉（对 2008 数据标 2014 日期，模型可能"怀疑"日期）——sketch 文本中出现日期质疑的比例作为描述性指标报告；Gemini API 无 seed 参数，replicate 为独立采样非种子复现；多厂商复制（OpenAI/Anthropic/DeepSeek）为 FM-2，取决于用户提供 key。
