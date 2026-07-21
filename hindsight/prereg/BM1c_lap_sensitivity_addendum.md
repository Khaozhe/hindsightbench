# BM-1c Addendum：LAP 探针敏感性研究（预注册，冻结于 2026-07-21）

状态：POST-FREEZE 补充实验（review-response）。BM-1 主 prereg（sha fbcdffc1）
保持冻结不变；本 addendum 只新增测量，不改动任何已冻结指标的定义或数据。
触发源：外部审稿 Q2（"different sample counts, temperatures, collapse thresholds"）。
用户批准记录：2026-07-21，报价 ~$3.60，批准 "addendum 冻结后跑"。

## 1. 设计（冻结）

**模型（3，全部为账本精确费率行）**：gpt-5.4-mini、claude-haiku-4-5、
deepseek-v4-flash。选择理由：三厂商覆盖 + 逐 token 精确费率（价目
`outputs/price_table.json`：0.75/4.50、1.00/5.00、0.14/0.28 USD/M）。
不含 gpt-5.5（输出费率 $30/M，单模型 ≥$58）、kimi（thinking token 不可控
且温度锁死 =1，温度臂物理不可行）、gemini/sonnet（无冻结费率，违反
"精确费率才进敏感性研究" 原则）。

**臂（每模型三组，prompt/系统措辞与冻结 LAP 完全一致，仅采样参数变化）**：
1. **样本扩展臂**：t=1.0（冻结温度），新增 reps 20–39 → +20 reps × 258 日期
   = 5,160 调用。与已存 reps 0–19 合并成 40 样本估计（合并仅在分析期）。
2. **温度臂 A**：t=0.3 × 20 reps × 258 = 5,160 调用。
3. **温度臂 B**：t=0.7 × 20 reps × 258 = 5,160 调用。

温度选点理由：Anthropic API 温度域为 [0,1]，故替代温度必须 ≤1；取 0.3/0.7
对冻结值 1.0 形成下方梯度。thinking/推理制度逐模型钉死为冻结 BM-1 行的
同一配置（llm_batch_ops 教训：思考制度改变会翻转 LAP 答案分布）。

**规模**：15,480 调用/模型 × 3 = 46,440 调用。
**报价**：以冻结费率 × 各自全量 LAP 实测 token（5,160 调用档：$0.52 / $0.60 /
$0.08）× 3 倍量 = **~$3.60 总**。**硬顶 $10**：账本累计超 $10 立即中止。

## 2. 数据隔离（硬约束）

冻结文件 `outputs/bench/<model>/lap_probe_results.jsonl` **只读、绝不追加**
——runner 的原生 resume 逻辑会 append 到冻结文件，故本研究使用独立脚本
`scripts/run_lap_sensitivity.py`，全部新样本写入：
`outputs/review/lap_sensitivity_runs/<model>/lap_ext_t1.0_reps20-39.jsonl`
`outputs/review/lap_sensitivity_runs/<model>/lap_t0.3_probe.jsonl`
`outputs/review/lap_sensitivity_runs/<model>/lap_t0.7_probe.jsonl`
40 样本估计 = 分析期把冻结 20 reps 与扩展 20 reps 合并，冻结盘面零字节变化。

## 3. 运维纪律（继承 llm_batch_ops，冻结）

- 每调用先落账（既有 usage jsonl 账本），后判 finish_reason=length（不重试）、
  再判空内容（不重试）；可重试仅 429/5xx/超时，指数退避。
- 幂等断点续跑：per-(model, arm, date, rep) 原子落盘，启动扫 done-set。
- 日志 `> full.log 2>&1`，禁止 tail 截断。
- **smoke 门**：先跑 2 日期 × 3 模型 × 三臂（~132 调用），从账本实测
  token 外推全量；外推总价 ≤ $7 → 自动继续全量；> $7 → 停下重新报价，
  等用户批准（此规则本身冻结，不允许现场变通）。

## 4. 分析计划（冻结，无选择性报告）

产出全矩阵，不设通过/失败假设（纯测量研究）：
- 逐模型 × 样本量 {20, 40} × 温度 {0.3, 0.7, 1.0} × 阈值 θ {0.05, 0.1, 0.2}
  的 empirical cutoff 月，及相对冻结值（20 样本 / t=1.0 / θ=0.1）的位移月数。
- δ 在各变体 LAP 下重算（门禁 n>30、var>1e-4 原样执行，被门禁的格渲染 '-'）。
- 全矩阵入论文附录（或工件表），不挑格子报告；与 P0-3 的零成本
  jackknife/阈值重扫（同日启动）互为参照。
- 解读边界（预先声明）：温度臂改变的是采样分布本身，cutoff 随温度移动
  不构成协议缺陷，而是"审计契约必须钉死采样参数"论点（§7）的又一实证。

## 5. 完成定义

三模型 × 三臂 jsonl 齐 + 账本对账（调用数 = 落账数）+ 实付写入
COST_TABLE.md + 分析矩阵入 outputs/review/lap_sensitivity_paid.json。
