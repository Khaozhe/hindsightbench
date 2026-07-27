# Batch-drift provenance audit (POST-FREEZE EXPLORATORY, 2026-07-25)

Gap = bearish share(crisis, n=11 dates) - bearish share(calm, n=36 dates), pooled over sketches.

## 1. The three headline numbers

| label | gap | crisis share | calm share | n sketches | n dates |
|---|---|---|---|---|---|
| 31.8pp_V1_archived_R | +31.8pp | 0.648 | 0.330 | 1920 | 240 |
| 28.1pp_FM1_R_pooled_rep1-3 | +28.1pp | 0.640 | 0.359 | 5760 | 240 |
| 21.3pp_FM2_S0_R | +21.3pp | 0.602 | 0.389 | 1920 | 240 |

## 2. Identity checks

- `fm2_R_S0_sketches_equal_fm1_R_rep1` = **True**
- `fm2_M_S0_sketches_equal_fm1_M_rep1` = **True**
- `fm1_M_rep1_equal_kt1_masked` = **True**
- `fm1_M_rep1_bytes_equal_kt1_masked` = **True**
- `v1_panel_equal_concat_of_v1_nodes` = **True**

## 3. Per-rep gaps with generation timestamps

| run | gap | n sketches | generated_at min | generated_at max |
|---|---|---|---|---|
| FM1_R_rep1 | +21.3pp | 1920 | 2026-07-02T13:11:53 | 2026-07-02T13:13:08 |
| FM1_R_rep2 | +44.2pp | 1920 | 2026-07-02T13:13:00 | 2026-07-02T13:14:20 |
| FM1_R_rep3 | +18.9pp | 1920 | 2026-07-02T13:14:20 | 2026-07-02T13:15:43 |
| FM1_R_pooled | +28.1pp | 5760 | None | None |
| FM1_D_rep1 | +35.6pp | 1920 | 2026-07-02T13:15:38 | 2026-07-02T13:17:05 |
| FM1_D_rep2 | +35.8pp | 1920 | 2026-07-02T13:16:58 | 2026-07-02T13:18:25 |
| FM1_D_rep3 | +23.1pp | 1920 | 2026-07-02T13:18:20 | 2026-07-02T13:19:50 |
| FM1_D_pooled | +31.5pp | 5760 | None | None |
| FM1_M_rep1 | +6.4pp | 1920 | 2026-07-02T12:35:55 | 2026-07-02T13:06:21 |
| FM1_M_rep2 | +4.0pp | 1920 | 2026-07-02T13:19:41 | 2026-07-02T13:21:00 |
| FM1_M_rep3 | +7.4pp | 1920 | 2026-07-02T13:20:58 | 2026-07-02T13:22:19 |
| FM1_M_pooled | +5.9pp | 5760 | None | None |
| FM1_W_rep1 | -2.7pp | 1920 | 2026-07-02T13:22:12 | 2026-07-02T13:23:50 |
| FM1_W_rep2 | -1.2pp | 1920 | 2026-07-02T13:23:35 | 2026-07-02T13:25:36 |
| FM1_W_rep3 | -13.2pp | 1920 | 2026-07-02T13:24:57 | 2026-07-02T13:26:33 |
| FM1_W_pooled | -5.7pp | 5760 | None | None |

## 4. Both-arms test: Gap(R), Gap(M), Gap(R)-Gap(M) per batch

| batch | Gap(R) | Gap(M) | Gap(R)-Gap(M) |
|---|---|---|---|
| FM1_rep1 | +21.3pp | +6.4pp | +14.9pp |
| FM1_rep2 | +44.2pp | +4.0pp | +40.2pp |
| FM1_rep3 | +18.9pp | +7.4pp | +11.4pp |
| FM1_pooled_3reps | +28.1pp | +5.9pp | +22.2pp |
| FM2_S0 | +21.3pp | +6.4pp | +14.9pp |
| V1_archived_R_vs_KT1_M | +31.8pp | +6.4pp | +25.4pp |

## 4b. Time-ordered R-arm gaps (generation order, not pooling order)

| when | run | Gap(R) |
|---|---|---|
| 2026-04-16 16:42..17:00 local (file mtimes; no generated_at recorded) | V1 archived panel (R) | +31.8pp |
| 2026-07-02T13:11:53..13:13:08 | FM-1 R rep1 | +21.3pp |
| 2026-07-02T13:13:00..13:14:20 | FM-1 R rep2 | +44.2pp |
| 2026-07-02T13:14:20..13:15:43 | FM-1 R rep3 | +18.9pp |

## 4c. Within-batch replicate noise (FM-1, all 3 reps same day, minutes apart)

| arm | rep1 | rep2 | rep3 | range | sd |
|---|---|---|---|---|---|
| R | +21.3pp | +44.2pp | +18.9pp | 25.3pp | 14.0pp |
| D | +35.6pp | +35.8pp | +23.1pp | 12.7pp | 7.3pp |
| M | +6.4pp | +4.0pp | +7.4pp | 3.5pp | 1.8pp |
| W | -2.7pp | -1.2pp | -13.2pp | 12.0pp | 6.6pp |

Rep-to-rep differences with date-level bootstrap CIs:

| contrast | estimate | 95% CI |
|---|---|---|
| R_rep1_minus_rep2 | -22.9pp | [-39.9, -8.4] |
| R_rep1_minus_rep3 | +2.5pp | [-14.7, +15.7] |
| R_rep2_minus_rep3 | +25.3pp | [+12.4, +38.3] |
| D_rep1_minus_rep2 | -0.2pp | [-11.6, +12.0] |
| D_rep1_minus_rep3 | +12.5pp | [+1.0, +25.1] |
| D_rep2_minus_rep3 | +12.7pp | [+3.4, +22.7] |
| M_rep1_minus_rep2 | +2.4pp | [-6.2, +10.8] |
| M_rep1_minus_rep3 | -1.0pp | [-10.8, +8.2] |
| M_rep2_minus_rep3 | -3.5pp | [-15.0, +7.2] |
| W_rep1_minus_rep2 | -1.4pp | [-13.5, +11.3] |
| W_rep1_minus_rep3 | +10.6pp | [-0.5, +20.5] |
| W_rep2_minus_rep3 | +12.0pp | [-2.9, +24.6] |

Single-run gap CIs (the width any drift claim must clear):

| run | gap | 95% CI |
|---|---|---|
| FM1_R_rep1 | +21.3pp | [+10.8, +32.2] |
| FM1_R_rep2 | +44.2pp | [+31.4, +56.4] |
| FM1_R_rep3 | +18.9pp | [+9.5, +30.5] |
| FM1_M_rep1 | +6.4pp | [+0.1, +12.9] |
| FM1_M_rep2 | +4.0pp | [-3.6, +12.4] |
| FM1_M_rep3 | +7.4pp | [+0.3, +15.5] |
| V1_archived_R | +31.8pp | [+21.1, +41.8] |
| FM1_R_pooled | +28.1pp | [+20.7, +35.6] |

## 5. Bootstrap CIs on cross-batch differences (date-level, B=10000)

| contrast | estimate | 95% CI |
|---|---|---|
| V1archived_R_minus_FM1pooled_R | +3.7pp | [-5.1, +12.6] |
| FM1pooled_R_minus_FM2S0_R | +6.8pp | [-1.4, +17.2] |
| RminusM_archived_minus_RminusM_FM1 | +3.2pp | [-5.9, +12.5] |
| RminusM_archived_minus_RminusM_FM2S0 | +10.4pp | [-0.1, +20.9] |
| RminusM_FM1_minus_RminusM_FM2S0 | +7.3pp | [-1.8, +17.9] |

## 6. Prompt-hash audit (V1 archive vs what FM-1 R replayed)

- dates checked: 240
- archived V1 node `user_sha256` != FM-1 R rep1 `user_sha256`: **240** dates
- V1 `sketch_batch_requests.jsonl` prompt == FM-1 R rep1 prompt: **240** dates

- archived V1 prompt rebuilt from current V1 code path: **240/240** exact sha256 matches
- distinct diff signatures across 240 dates: **1** (one signature, 240 dates)
- lines present in the 2026-04 ARCHIVED prompt but absent from the prompt FM-1 R replayed:

```
+    "decision_date",
+    },
+    "decision_date": {
+      "type": "string",
+      "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
+      "description": "Point-in-time decision date for this sketch. Injected by the caller after LLM parsing; any LLM-supplied value is overwritten. Format: YYYY-MM-DD."
```

## 7. Recorded model / endpoint strings

- V1 archived nodes: {'n_nodes': 240, 'model_strings': ['models/gemini-2.5-flash'], 'model_version_reported': ['None'], 'arm_labels': ['None'], 'generated_at_min': None, 'generated_at_max': None, 'generated_at_recorded': False}
- KT-1 masked nodes: {'n_nodes': 240, 'model_strings': ['models/gemini-2.5-flash'], 'model_version_reported': ['gemini-2.5-flash'], 'arm_labels': ['masked (KT-1)'], 'generated_at_min': '2026-07-02T12:35:55', 'generated_at_max': '2026-07-02T13:06:21', 'generated_at_recorded': True}
- FM-1 R rep1: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:11:53 .. 2026-07-02T13:13:08]
- FM-1 R rep2: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:13:00 .. 2026-07-02T13:14:20]
- FM-1 R rep3: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:14:20 .. 2026-07-02T13:15:43]
- FM-1 D rep1: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:15:38 .. 2026-07-02T13:17:05]
- FM-1 D rep2: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:16:58 .. 2026-07-02T13:18:25]
- FM-1 D rep3: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:18:20 .. 2026-07-02T13:19:50]
- FM-1 M rep1: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T12:35:55 .. 2026-07-02T13:06:21]
- FM-1 M rep2: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:19:41 .. 2026-07-02T13:21:00]
- FM-1 M rep3: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:20:58 .. 2026-07-02T13:22:19]
- FM-1 W rep1: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:22:12 .. 2026-07-02T13:23:50]
- FM-1 W rep2: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:23:35 .. 2026-07-02T13:25:36]
- FM-1 W rep3: models=['models/gemini-2.5-flash'] version_reported=['gemini-2.5-flash'] [2026-07-02T13:24:57 .. 2026-07-02T13:26:33]
