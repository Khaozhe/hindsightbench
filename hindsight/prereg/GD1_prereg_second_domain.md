# GD-1 Prereg: 第二域迷你面板（10Y 国债，跨任务通用性检验）

**日期**: 2026-07-03（冻结于任何 API 调用前）
**动机**: 论文一全部证据在单一目标（SPX 方向）上。GD-1 用最小识别集检验 "date is the trigger" 是否为**跨任务性质**：同一批 240 个 vintage 快照、同一 masking/移植变换，目标换成 **10 年期美债收益率方向**（DGS10，未来 20 交易日升/降）。宏观叙事对债券的方向含义与股票**部分相反**（危机 → 股跌但债涨/收益率降），这使 GD-1 同时是通用性检验和叙事内容检验：若触发的是"危机叙事"而非"看空反射"，W 臂危机假日期应产生**收益率下行**预期（flight to quality），而非机械复制 SPX 的看空。

## 设计（最小识别集，Gemini 2.5 flash，temp 0.2）
- **臂**: D / M / W（66 月移位）× 240 日期 × 1 rep（无 R 臂——泄漏上下文效应已在主实验证明 ≈0；无 W′——季节性已排除）
- **Prompt**: 与主实验同构，仅目标句替换（"predicting S&P 500 forward returns" → "predicting the direction of the 10-year U.S. Treasury yield over the next 20 trading days"）；direction 字段语义 = 收益率方向（+ = 升）
- **LAP-10Y**: "Between {t} and {t_end}, did the 10-year U.S. Treasury yield rise or fall?" 240 日期 × 20 reps，temp 1.0
- **实现目标**: DGS10（FRED，日频），realized = 20 交易日后收益率变动符号

## 预注册假设
- **G1（触发通用性）**: E2_10Y = Gap_D − Gap_M ≠ 0，且 |E2_10Y| ≥ 5pp（方向见 G3）
- **G2（移植通用性）**: W 臂按假日期归窗的 gap 显著、按真日期 ≈0（同主实验模式）
- **G3（叙事内容检验，方向性预测）**: 危机窗内 D 臂的"收益率降"份额 > 平静窗（flight-to-quality 叙事）——即 10Y 的 E2 与 SPX 的 E2 **反号**（用 bearish→yield-down 对应）。若同号，则触发的是无差别悲观反射而非结构化叙事，如实报并修正 §5 的解释
- **G4（LAP 通用性）**: LAP-10Y pre-cutoff 均值 > 0.15 且 hit rate > 65%；post-cutoff 崩塌至 <0.05

## 窗口/统计
- 与主实验完全同窗（CRISIS 11 dates / calm 2013+2014+2017），paired bootstrap B=10,000 seed=2026
- 分析脚本 analyze_gd1.py 复用 analyze_fm1 的 gap/boot 函数

## 成本与执行门
- 调用量: 720 arms + 4,800 LAP = 5,520 flash 调用
- **执行门: 冻结后先跑 2 日期 smoke 实测单价 → 外推报价 → 用户批准后全量**（llm_batch_ops 铁律）
