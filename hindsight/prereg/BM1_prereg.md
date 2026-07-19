# BM-1 Preregistration: HindsightBench Multi-Model Protocol

Status: **FROZEN**（先于任何非 Gemini 模型调用；sha256 见 `BM1_prereg_freeze.json`）

## 协议（对每个进场模型 m 完全一致）

1. **生成矩阵**：四臂（R/D/M/W，变换规则 = FM-1 冻结版，66 月移位）× 2 reps × 240 pre-cutoff 决策日 + 四臂 × 2 reps × 18 post-cutoff 决策日（FM-1c C1 扩展面板）。temperature=0.2，输出预算按模型放宽至完成（内容中性）。
2. **探针**：日期恢复探针（258 日期 × 1，temp=0）；LAP 探针（258 日期 × 20 reps，temp=1.0，措辞 = FM-1c C2 冻结版）。
3. **benchmark 行指标**（每模型一行，全部按 FM-1/FM-1c 冻结定义）：
   - E2_m 日期触发强度 = Gap(D)−Gap(M)
   - E3_m 移植效应 = Gap_fake(W)−Gap_true(W)
   - REC_m 日期可恢复性（日历年命中 / ±12月 / 平均月差三口径）
   - LAP_m 记忆召回率（pre-cutoff 均值）与 **empirical cutoff**（LAP 按月序列的崩塌点，定义为最后一个 LAP>0.1 的月份）
   - DISS_m 解离系数 = A2 检测回归 δ（signal×LAP 交互，HAC lag 6）
   - VALID_m 任务服从率（schema 有效 sketch 比例、refusal/解析失败计数——小模型预期低，如实报告，撑不起任务的模型带记录退场）
4. **适配**：OpenAI 兼容端点统一走 `llm_adapters.py`（base_url/model 参数化，json_object 模式优先，解析容错：markdown 围栏剥离 + 数组截取）；Anthropic 单独适配。每模型冒烟 2 日期 × 4 臂人工检查后才准全量。
5. **推断纪律**：模型行之间只做描述性排行与规模/家族分组对比，不做逐对显著性检验森林；效应量 CI 用与 FM-1 相同的 bootstrap。主论文（AAAI）只承诺 Gemini 双档结果，其余模型进扩展表/benchmark 论文，滚动并入不重开分析口径。
6. **进场顺序**（按 key 到位）：deepseek-v4-flash（本次）→ Kimi/Qwen/OpenAI/Anthropic → ollama 本地开源小模型（Llama-3.1-8B、Llama-3.2-3B）。每模型产物 `hindsight/outputs/bench/<model>/`，结构与 FM-1 一致。
