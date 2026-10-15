# ST-1 Prereg: 时空面板（city × month），key 从 date 推广到 (date, location)

**日期**: 2026-10-13（冻结于任何 API 调用前；panel sha256 见 §2）
**状态**: BM-1 协议（sha fbcdffc1）的 domain-transfer addendum，不修改 BM-1 任何冻结量。
**动机**: BM-1 / GD-1 / GD-2 的全部证据都在单一地点（美国）的 time-indexed 任务上。ST-1 用一个 sensing 类
spatio-temporal 面板检验两件事：(a) 协议是否迁移到 (space, time)-indexed decision task；(b) parametric
hindsight 的 key 是时间、地点，还是二者的联合——即 "the date is the trigger" 在有空间坐标时是否仍成立、
以及地点坐标是否独立触发。

## 1. 数据与面板

- **源**: Google COVID-19 Community Mobility Reports，`Region_Mobility_Report_CSVs.zip`
  （https://www.gstatic.com/covid19/mobility/，Google 于 2022-10-15 停更，归档仍在线）。
  zip sha256 记录于 `outputs/st1/raw/SOURCE.json`。
- **传感器类数据不被修订**：vintage-correct 退化为 as-of 截断（节点 t 只看 date ≤ t 的行）。
- **地区（10）**: nyc（New York County）、milan（Lombardy）、london（Greater London）、madrid（Community of
  Madrid）、tokyo（Tokyo）、melbourne（Victoria）、sydney（New South Wales）、delhi（Delhi）、hongkong、singapore。
  选择标准：Google 覆盖、2020-02-15..2022-10-15 全程无缺（madrid grocery 2020-05-03 单格缺失，线性插值，已披露）、
  lockdown onset 日期在 2020-03 到 2022-02 之间**分散**（这是 S 臂可识别的前提）。
- **节点**: 每城每月 15 日，2020-03-15..2022-09-15，31 × 10 = 310 节点。快照 = 截至 t 的 4 个周均值 × 6 类
  （retail_and_recreation, grocery_and_pharmacy, parks, transit_stations, workplaces, residential）。
- **Realized label**: `direction_4w = sign(mean(RETAIL_REC, (t, t+28d]) − mean(RETAIL_REC, (t−28d, t]))`；
  "−" = 下行。transit_stations 作为次要 label 一并存盘，不做 headline。
- **Crisis set（ex-ante 政策事件表，非任何指标输出）**: 节点 (c, m) 属 crisis 当且仅当城市 c 的某次限制措施
  onset 落在月 m。onset 列表硬编码于 `build_st_panel.py::ONSETS`（28 个 crisis 节点）。
- **Calm set**: 2022-05..2022-09 五个月，所有城市相同（50 个 calm 节点）。
- **面板 sha256**: `463b2a9b8bb4b78083f716c70cd4050c7d3374fe94dd9d3cdf3ce9cf471d4a89`（`outputs/st1/panel/nodes.jsonl`）。

## 2. 臂（最小识别集 5 臂，1 rep，temp 0.2）

只操纵 prompt 首行的两个坐标，其余逐字相同：

| 臂 | 日期 | 地点 | 测什么 |
|---|---|---|---|
| M | [undisclosed] | [undisclosed] | baseline |
| D | 真 | [undisclosed] | 时间 trigger |
| L | [undisclosed] | 真 | 地点 trigger |
| DL | 真 | 真 | 联合 key |
| S | 真 | **假**（FAKE_CITY 置换） | 空间移植 |

- FAKE_CITY 是一个 derangement，约束为"任一城市与其假城市在 2020-05 之后无共同 onset 月"（脚本 assert）：
  nyc→milan, milan→melbourne, melbourne→madrid, madrid→tokyo, tokyo→sydney, sydney→delhi, delhi→hongkong,
  hongkong→singapore, singapore→london, london→nyc。
- W 臂（假日期）**不在最小集**：date transplant 已在 BM-1 主面板建立；若后续补跑，位移 = 城内循环 +16 节点，单独 addendum。
- Fail-closed 泄漏检查：M 臂 prompt 中不得出现任何 4 位年份、城市名、国家名；D 臂只允许真日期串；L 臂只允许真城市名；
  S 臂只允许真日期 + 假城市名。任一违反即 RuntimeError，不发请求。
- 已知且接受的信息集限制：mobility 六类 schema 本身暗示数据来自 2020-02..2022-10 的 Google 报告，M 臂的
  "undisclosed" 只能把时间信息集压缩到这个 32 个月窗口、空间信息集压缩到 Google 覆盖区。REC-ST 探针（§3）
  量化这一残余可恢复性；这是结果，不是缺陷。

## 3. 探针

- **LAP-ST（结果召回）**: 按 (city, t) 问 "retail-and-recreation 指数在 t 后四周相对 t 前四周是 higher 还是 lower"，
  20 reps，temp 1.0，答案 ∈ {higher, lower, unknown}。给出 per-city recall rate 与 hit rate。
- **REC-ST（时空可恢复性）**: 给 M 臂快照，temp 0，要求 JSON `{"estimated_date": "YYYY-MM", "estimated_city": "..."}`。
  评分：日期 ±3 个月命中率、城市精确命中率（别名表归一）、二者联合命中率。
- **P1 placebo 在本面板无定义**：所有节点早于所有受测模型的 cutoff。placebo 留在 BM-1 主面板。

## 4. 估计量与预注册假设

Gap(arm) = bearish("−") share(crisis) − bearish share(calm)，crisis/calm 用**真城市**的集合。

- **E2 = Gap(D) − Gap(M)**（时间 trigger）
- **E2ℓ = Gap(L) − Gap(M)**（地点 trigger）
- **E2dl = Gap(DL) − Gap(M)**（联合 key）
- **INT = E2dl − E2 − E2ℓ**（超可加性）
- **E3ℓ = Gap_fake(S) − Gap_true(S)**：同一批 S 臂生成，分别按假城市的 crisis 集与真城市的 crisis 集评分。

假设（方向性，冻结）：
- **S1（协议迁移）**: E2 > 0 且 CI 排零。
- **S2（地点单独触发）**: 不预设方向；报 E2ℓ 与 CI。若 E2ℓ 的 CI 含零而 E2 排零 → "time, not place, is the key"。
- **S3（联合 key）**: E2dl ≥ max(E2, E2ℓ)；INT 报点估计与 CI，不预设方向。
- **S4（空间移植）**: E3ℓ > 0 且 CI 排零 → 危机叙事跟着被断言的地点走。若 E3ℓ ≈ 0 而 E2 > 0 → 日期主导、地点被忽略。
- **S5（记忆门）**: LAP-ST hit rate > 多数类基线 0.629（realized "+" share），否则 S1–S4 的读数标为 "memory gate failed"，
  如实报不解释。
- **S6（空间异质性，描述性）**: per-city LAP recall rate 与 REC-ST 城市命中率的跨城分布；不做显著性声明。

## 5. 统计

- 主：节点层 paired bootstrap，B = 10,000，seed 2026，crisis 节点集与 calm 节点集分别重抽（与 BM-1 同构）。
- 敏感性：city-cluster bootstrap（重抽城市，B = 10,000）——因 crisis 节点在城内聚集（melbourne 6 个）。
- 同 BM-1：bootstrap 不覆盖 run-to-run 噪声；单 rep 行之间 < 16.2pp 的差异不解释。

## 6. 模型与执行门

- 第一行：gemini-2.5-flash（与 GD-1 同端点、同生成参数）。
- 后续行：自托管开源权重（Qwen3.6-27B FP8、Llama 3.3 70B），pin 量化与 thinking regime，单独 addendum 记 tier。
- **执行门（llm_batch_ops 铁律）**：冻结后先跑 smoke（2 节点 × 5 臂 + 2 LAP + 2 REC），从 usage log 实测单价 →
  外推全量报价 → 用户批准 → 全量。调用量：310 × 5 = 1,550 臂 + 6,200 LAP + 310 REC = 8,060 次。

## 7. 不做 / 限制（冻结时已知）

- 中国大陆城市不在 Google 覆盖内（武汉、上海缺席）；空间覆盖偏向 Google 可用市场，如实写进 limitation。
- 单一 episode 家族（COVID）；识别力来自 onset 日期的空间分散（2020-03 到 2022-02），不来自多 episode。
- 本面板不能定义 effective cutoff（全部 pre-cutoff）；"cutoff 的空间异质性" 不在 ST-1 范围内。
