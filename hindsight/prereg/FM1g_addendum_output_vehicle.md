# FM-1g Addendum：诱发输出载体修订（smoke 阶段，全量运行之前）

原预注册（FM1g_prereg_self_elicited.md，sha256 10643458）规定 GDATE/GNEUT 在
sketches 之前单独一行输出 `INFERRED DATE: YYYY-MM` / `SALIENT SERIES: NAME`。

**Smoke v1 发现（2026-07-19，4 调用）**：冻结 V1 系统提示的输出契约（"A single
JSON array ... Nothing else - no prose"）压制了 user prompt 末尾的前置行指令——
模型 4/4 直接输出纯 JSON 数组，零诱发输出。（这本身是指令层级的一个观察：系统
级格式契约 > 用户级前置任务。）v1 smoke 细胞已隔离至
`outputs/fm1g/_smoke_v1_ignored_preamble/`，不进入任何分析。

**修订（仅改输出载体，估计量与判定规则逐字不变）**：
- GDATE：要求单一 JSON 数组，**首元素**为
  `{"inferred_decision_date": "YYYY-MM"}`，其后为 8 个 sketch 对象。
- GNEUT：首元素为 `{"salient_series": "NAME"}`，其后为 8 个 sketch 对象。
- 首元素在 sketch 校验器中按既有规则计为 invalid（非 sketch），8 个 sketch
  照常进入方向读出；诱发值从原始响应的首元素解析。解析失败照常计缺失披露。

判定规则、参照带、bootstrap 约定、成本信封均沿用原预注册。
