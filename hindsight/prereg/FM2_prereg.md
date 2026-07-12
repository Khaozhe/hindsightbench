# FM-2 Preregistration: Stage-wise Propagation of Parametric Hindsight through a Production Pipeline

Status: **FROZEN**（先于任何 FM-2 管线运行；sha256 见 `FM2_prereg_freeze.json`）
增量 (iii)：现有文献的污染量化全部是端到端黑箱（Profit Mirage）、信号级过滤（MemGuard）或单次调用 claim 级（Shapley-DCLR）；无人在真实生产假说管线内做过 stage-wise 追踪。

## 1. 设计

**处理**：把 FM-1 的 R 臂与 M 臂 sketch（gemini-2.5-flash，**各取 rep1**，240 日期 × 8 条，与 V1 生产面板结构严格同构）分别灌入冻结的 V1 生产管线（`macrochain/scripts/run_full_pipeline.py`，commit ad4b1ab 状态，K_DEEP=20、N_BAITS=2、BAIT_SEED=42 原参不动），产出两套完整管线工件。V1 生产工件只读，输出重定向至 `hindsight/outputs/fm2/<arm>/`。

**管线阶段与度量点**（每臂）：
- S0 sketch 层：危机窗−平静窗看空份额差（已知：R +31.8pp 口径 / rep1 实际值以本次数据为准；M +6.4pp 同）
- S1 compile 后：编译模板的 direction 份额（同窗口差）
- S2 L1 过滤后：存活模板 direction 份额
- S3 top-K 选择后：每决策日 H*（K_DEEP=20）内 direction 份额
- S4 聚合后：每决策日 multiplicative 预测符号；危机窗 neg-call 计数
- S5 生产指标：2019-2024 OOS 准确率、危机窗准确率、neg-calls、sign-only Sharpe，vs always-long

**主终点**：
- T1 租金衰减曲线：crisis-bearish gap 在 S0→S4 的逐阶段值（两臂各一条曲线），报告每阶段保留率 gap_Sk / gap_S0。
- T2 生产租金：Acc_R(S5) − Acc_M(S5)（全窗与危机窗），paired bootstrap（重抽 OOS 决策日，B=10000, seed=2026）95% CI。
- T3 机制归因：若某阶段 gap 保留率下降 > 50%，对该阶段做组成分析（哪个环节丢弃/降权了带方向的模板：L1 规则、U_disc 门控、还是 top-K 排名）。

**预注册假设**（基于 FM-1 E5 与 V1 生产事实的先验）：hindsight 租金在 sketch 层存在（E5 危机窗 +14pp）但被管线大幅稀释——预计 S4/S5 两臂差 < sketch 层差的一半；最大稀释点预计在 U_disc 门控（多空模板的 IC 门控与方向无关）。若实际相反（租金在管线中放大），如实报告。

## 2. 纪律

- V1 管线代码与超参不动；只重定向输入输出路径（wrapper 注入 8 个路径常量）。
- 不以 FM-2 结果改动 FM-1 任何结论；FM-2 与 FM-1 的窗口/看空定义完全一致。
- 已知披露：V1 管线 L3 为全样本 walk-forward（决策日不截断，V1 论文审计已发现）——FM-2 研究的是"该管线原样"的传播行为，此性质对两臂等同作用，不影响臂间对比的内部效度；论文中作为管线特性披露。
- reps 2-3 的重复运行作为后续稳健性（不进主表）。
- 计算为纯本地 CPU，无新 LLM 调用。
