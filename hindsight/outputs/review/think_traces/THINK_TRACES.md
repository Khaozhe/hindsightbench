# Reasoning traces and the date (post-freeze exploratory; zero API cost)

Rows whose raw responses keep the <think> block. selfloc: M-arm trace names a calendar year (unit echoes removed); year hit: the named year is within +-1 of the node's true year; vocab on crisis dates: the trace names THAT date's episode (Lehman/subprime; pandemic/COVID/lockdown; inflation surge/Fed hikes), on calm dates: any episode; D other-years: D-arm trace names a year beyond the stated one (+-1). c = crisis dates, q = calm dates.

| model | cells D/M | len D/M (chars) | M selfloc c/q | M year hit (n) | M guess c/q | M vocab c/q | D vocab c/q | D other-years c/q | M bearish selfloc vs not |
|---|---|---|---|---|---|---|---|---|---|
| olmo3-7b-think | 258/257 | 26843/26140 | 0.09/0.00 | 0.07 (14) | 0.00/0.00 | 0.00/0.03 | 0.00/0.06 | 0.00/0.03 | 0.33 vs 0.28 |
| qwen3-30b-a3b-fp8dyn | 258/258 | 4898/5154 | 0.00/0.03 | 0.25 (8) | 0.00/0.03 | 0.00/0.00 | 0.09/0.00 | 0.00/0.00 | 0.34 vs 0.41 |
| qwen3-30b-a3b-thinking-2507-awq | 258/258 | 37326/38106 | 0.36/0.08 | 0.22 (46) | 0.27/0.22 | 0.00/0.06 | 0.27/0.06 | 0.09/0.19 | 0.63 vs 0.59 |
| qwen3-30b-a3b-thinking-2507-bf16 | 258/258 | 22656/22309 | 0.09/0.14 | 0.23 (22) | 0.27/0.11 | 0.09/0.03 | 0.73/0.11 | 0.27/0.17 | 0.60 vs 0.59 |
| qwen3-30b-a3b-thinking-2507-bf16-fp16act | 258/258 | 22587/21589 | 0.09/0.14 | 0.25 (28) | 0.18/0.11 | 0.09/0.03 | 0.55/0.11 | 0.18/0.17 | 0.57 vs 0.57 |
| qwen3-30b-a3b-thinking-2507-bf16-r2 | 258/258 | 22628/21016 | 0.00/0.03 | 0.12 (24) | 0.27/0.08 | 0.00/0.03 | 0.36/0.08 | 0.45/0.11 | 0.58 vs 0.58 |
| qwen3-30b-a3b-thinking-2507-fp8block | 258/258 | 20997/20223 | 0.00/0.14 | 0.16 (25) | 0.09/0.17 | 0.00/0.03 | 0.18/0.03 | 0.18/0.08 | 0.62 vs 0.57 |
| qwen3-30b-a3b-thinking-2507-fp8dyn | 258/258 | 24127/23230 | 0.09/0.08 | 0.04 (24) | 0.18/0.22 | 0.00/0.03 | 0.36/0.14 | 0.27/0.17 | 0.57 vs 0.54 |
| qwen3-30b-a3b-thinking-2507-gptq-w4a16 | 258/258 | 22226/22545 | 0.09/0.03 | 0.29 (21) | 0.09/0.11 | 0.09/0.11 | 0.36/0.08 | 0.09/0.08 | 0.50 vs 0.51 |
| qwen3-30b-a3b-thinking-2507-int8-w8a8 | 258/258 | 24885/21901 | 0.09/0.06 | 0.20 (20) | 0.27/0.17 | 0.00/0.03 | 0.55/0.06 | 0.27/0.11 | 0.64 vs 0.58 |
| qwen3.6-27b-awq | 258/258 | 17980/17177 | 0.27/0.06 | 0.16 (25) | 0.18/0.03 | 0.00/0.08 | 0.64/0.33 | 0.36/0.14 | 0.45 vs 0.49 |
| qwen3.6-27b-bf16 | 258/258 | 16699/16123 | 0.09/0.03 | 0.12 (8) | 0.00/0.00 | 0.00/0.00 | 0.36/0.19 | 0.18/0.14 | 0.45 vs 0.49 |
| qwen3.6-27b-fp8 | 258/258 | 15872/15710 | 0.00/0.00 | 0.11 (9) | 0.00/0.00 | 0.00/0.08 | 0.73/0.22 | 0.00/0.03 | 0.53 vs 0.50 |
| qwen3.6-35b-a3b-fp8 | 258/258 | 18408/18355 | 0.00/0.00 | 0.47 (15) | 0.09/0.03 | 0.00/0.08 | 0.18/0.03 | 0.00/0.08 | 0.48 vs 0.50 |
| r1-distill-llama-70b-awq | 258/258 | 3140/3144 | 0.00/0.00 | nan (0) | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 | 0.00/0.00 | nan vs 0.43 |
