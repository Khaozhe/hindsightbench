# BM-1c: Anthropic 行的适配披露（先于 Anthropic 调用冻结）

1. **接入方式**：Message Batches API（50% 折扣），export→submit→watch→materialize 四步，产物目录结构与其他模型完全一致。
2. **模型与 rep 档**：claude-haiku-4-5 = 2 reps 全协议（BM-1 标准档）；claude-sonnet-5 = 1 rep arms + 全探针（旗舰减档，同 gemini-2.5-pro 初始档）。
3. **Deviation（Sonnet 5）**：该模型拒绝非默认 temperature（API 400），arms 与 LAP 探针均省略 temperature 参数，记 sampling="provider-default"；adaptive thinking 默认开启（与 gemini 思考型行为对齐），max_tokens 统一 16000（含思考预算，内容中性）。
4. **Deviation（Haiku 4.5）**：temperature=0.2 正常传（该模型接受）；thinking 不开启（该模型默认关）。
5. LAP 探针 20 reps 频率近似口径不变（Batch 内 temperature：haiku=1.0 显式，sonnet-5=默认采样并披露）。
