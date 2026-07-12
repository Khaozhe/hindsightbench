# BM1d: OpenAI Batch 适配器注记（BM1 prereg 附录）

**日期**: 2026-07-03（冻结于提交前）

## 模型与协议档位
- **gpt-5.5**（2026-04-23 版）：减窗协议（65 日期 = CRISIS + 平静年 + post-cutoff，1 rep，LAP 10 reps）——成本决策（$30/M 输出），与 BM1b 本地档同口径
- **gpt-5.4-mini**（2026-03-17 版）：全协议（258 日期，2 reps，LAP 20 reps）

## 已披露 deviation（推理模型约束）
1. 不接受自定义 temperature → 供应商默认采样（同 BM1c 的 sonnet-5 处理，逐 cell 记录于 03_run_meta.json）
2. `max_completion_tokens` 替代 `max_tokens`（纯参数名映射，上限值不变）
3. 通道：OpenAI Batch API（/v1/batches，五折，24h 窗口）；请求体与直连逐字段一致
4. LAP/恢复解析沿用 2026-07-03 的 reasoning-tolerant 规则（末位关键词/末位日期，向后兼容单词答案）

## 成本控制
提交前冒烟实测单价外推报价（llm_batch_ops 铁律）；usage 逐行落账 openai_compat_usage_log.jsonl。
