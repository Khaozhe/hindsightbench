# FM-2b Prereg: Synthetic Aggregator Ablation（管线防火墙的架构归因）

**日期**: 2026-07-02（冻结于任何分析运行前）
**动机**: FM-2 表明生产管线（IC 门控 + 乘法聚合）把 sketch 层 +14.9pp 的污染租金压到生产层 −1.4pp。单管线 n=1 是审稿最大攻击面。本消融不新增任何 LLM 生成——用**已有的** FM-2 R/M 两臂全量中间产物，把同一批假说推过一族合成聚合架构，回答：**租金的存活由聚合层的哪个设计元件决定？**

## 数据（全部既有，零新增 API 调用）
- `hindsight/outputs/fm2/{R,M}/` 各阶段产物（compiled / L1 / top-K / 生产聚合输入表，含 U_disc_ic_V、Rate_fals_V、cmplx_norm、Sens_bait_V、Sens_rev_V、R_h、dir_sign 字段）
- 评估窗与 FM-2 T2 完全一致：OOS 2019+（n=71 月），指标 = 方向准确率 + sign-only Sharpe；T1 口径 = 危机−平静 bearish gap（S4 层）

## 消融架构族（固定 5 个，禁止事后增删）
| # | 架构 | 定义 |
|---|---|---|
| A1 | 等权多数票（无门控） | 对 top-K 假说的 dir_sign 取简单多数，平票 → 弃权（沿用生产弃权规则） |
| A2 | 等权加权和 | sum(dir_sign)/K 的符号作为决策，无任何质量权重 |
| A3 | IC 门控 + 加法 | w_h = mult_w(row)（与生产同参 α=γ=0.2, β=1.0），决策 = sign(Σ w_h·dir_sign)——保留门控、去掉乘法结构 |
| A4 | IC 门控 + 乘法（=生产 S4，复算对照） | analyze_fm2.py 的 mult_w/predict_mult 原样 |
| A5 | 样本内拟合 top-1 | 每月只取 R_h 最大的单一假说方向（过拟合敏感型） |

## 预注册假设
- H1（门控是关键）: A1/A2（无门控）的 R−M 租金 ≥ sketch 层租金的一半（≥+7.5pp）；A3/A4（有门控）租金 |·| < 5pp。
- H2（乘法非关键）: A3 与 A4 的租金差 < 3pp。
- H3（过拟合放大）: A5 租金 > A4 租金（方向预测，不设幅度）。

## 判读表
| 结果模式 | 结论写法 |
|---|---|
| H1+H2 成立 | "防火墙 = IC 门控"，乘法只是载体——§7.3 主张升级为架构归因 |
| H1 成立 H2 反 | 门控与乘法共同必要，写交互 |
| H1 反 | FM-2 结论限定性大幅收紧，§7 改写为单架构观察——如实报 |

## 统计
- 每架构 × 两臂：T2 准确率差的 paired bootstrap CI（B=10,000, seed=2026，同 FM-2）
- T1 gap 用同一 CRISIS/CALM 窗定义
- 多重比较：5 架构预注册族，报告全部，不做选择性呈现

## 交付
`analyze_fm2b.py`（读 FM-2 既有产物）→ `outputs/fm2b/FM2B_RESULTS.md` + 论文 §7 消融表。任何 deviation 在 RESULTS 头部披露。
