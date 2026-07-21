# W-arm displacement-family split + post-cutoff anchor transplant (reviewer Q5)

POST-FREEZE EXPLORATORY (review-response, 2026-07-21); zero API calls.
All numbers recomputed from the frozen W arms; the fake-date map is an
analysis-time constant of the frozen design (`(i+66) % 240`), verified
against stored run meta (zero mismatches; counts in the json).

The single frozen map contains two displacement families: **fwd66**
(source cells i<174, +66 months) and **bwd174** (source cells i>=174,
wrap to -174 months). Both share seasonal phase (+6 mod 12). Units: pp.

## Reconciliation gate (union of families vs frozen row json)

| model | frozen E3 [CI] | recomputed E3 [CI] | bit-exact |
|---|---|---|---|
| gpt-5.5 | +16.1 [+9.3,+22.9] | +16.1 [+9.3,+22.9] | yes |
| claude-sonnet-5 | +45.0 [+26.5,+63.5] | +45.0 [+26.5,+63.5] | yes |
| kimi-k2.6 | +38.5 [+26.4,+50.9] | +38.5 [+26.4,+50.9] | yes |
| qwen3.6-35b-a3b-fp8 | +34.6 [+23.7,+45.6] | +34.6 [+23.7,+45.6] | yes |
| qwen3.6-27b-fp8 | +18.1 [+11.4,+25.1] | +18.1 [+11.4,+25.1] | yes |
| gpt-5.4-mini | +18.7 [+7.9,+29.3] | +18.7 [+7.9,+29.3] | yes |
| claude-haiku-4-5 | +49.5 [+34.2,+64.3] | +49.5 [+34.2,+64.3] | yes |
| deepseek-v4-flash | +30.9 [+14.0,+47.5] | +30.9 [+14.0,+47.5] | yes |
| gemini-2.5-flash | +31.1 [+19.6,+42.6] | +31.1 [+19.6,+42.6] | yes |
| gemini-2.5-pro | +24.2 [+13.1,+35.6] | +24.2 [+13.1,+35.6] | yes |
| qwen3-30b-a3b-fp8dyn | +1.6 [-14.1,+17.5] | +1.6 [-14.1,+17.5] | yes |
| llama-3.1-70b-awq | +0.8 [-9.7,+10.8] | +0.8 [-9.7,+10.8] | yes |
| llama-3.1-8b | +7.6 [-2.4,+17.8] | +7.6 [-2.4,+17.8] | yes |

## Strict frozen windows per family

fwd66 windows: fake crisis n=5 (COVID+inflation) / fake calm n=36 /
true crisis n=6 (GFC) / true calm n=36. bwd174 windows: fake crisis
n=6 (GFC) / true crisis n=5 (COVID+inflation), but **calm n=0 under
both labelings** (calm years 2013/14/17 are all in fwd66's true side
and outside bwd174's fake image 2005-01..2010-06) — E3_bwd174 is not
computable under the frozen windows and is rendered '-', not imputed.

| model | E3_full | E3_fwd66 [CI] | excl.0 | sign=full? | E3_bwd174 | gapf_bwd | gapt_bwd |
|---|---|---|---|---|---|---|---|
| gpt-5.5 | +16.1 | +10.8 [+2.8,+19.1] | yes | yes | - | - | - |
| claude-sonnet-5 | +45.0 | +63.5 [+40.6,+84.2] | yes | yes | - | - | - |
| kimi-k2.6 | +38.5 | +50.2 [+35.9,+64.3] | yes | yes | - | - | - |
| qwen3.6-35b-a3b-fp8 | +34.6 | +47.9 [+29.7,+63.5] | yes | yes | - | - | - |
| qwen3.6-27b-fp8 | +18.1 | +25.1 [+11.8,+37.2] | yes | yes | - | - | - |
| gpt-5.4-mini | +18.7 | +20.5 [+11.2,+29.6] | yes | yes | - | - | - |
| claude-haiku-4-5 | +49.5 | +54.6 [+44.3,+64.0] | yes | yes | - | - | - |
| deepseek-v4-flash | +30.9 | +37.2 [+17.6,+55.7] | yes | yes | - | - | - |
| gemini-2.5-flash | +31.1 | +39.8 [+26.2,+53.0] | yes | yes | - | - | - |
| gemini-2.5-pro | +24.2 | +33.3 [+15.1,+49.9] | yes | yes | - | - | - |
| qwen3-30b-a3b-fp8dyn | +1.6 | +5.3 [-17.1,+26.7] | NO | yes | - | - | - |
| llama-3.1-70b-awq | +0.8 | +0.6 [-15.5,+15.5] | NO | yes | - | - | - |
| llama-3.1-8b | +7.6 | +2.1 [-14.8,+17.9] | NO | yes | - | - | - |

## POST-HOC rest-baseline supplement (both families computable)

Baseline = family complement of the crisis window under the same
labeling (fwd66: 169/168 dates; bwd174: 60/61) — NOT the frozen calm
set. `rest_full` = same construction on all 240 dates (reference for
the baseline swap).

| model | E3rest_full [CI] | E3rest_fwd66 [CI] | sign=full? | E3rest_bwd174 [CI] | sign=full? |
|---|---|---|---|---|---|
| gpt-5.5 | +14.3 [+6.3,+22.6] | +8.6 [+1.3,+16.8] | yes | +20.1 [+7.2,+33.0] | yes |
| claude-sonnet-5 | +28.6 [+10.4,+46.5] | +47.3 [+25.9,+66.8] | yes | +6.1 [-13.1,+26.4] | yes |
| kimi-k2.6 | +27.4 [+13.9,+40.5] | +39.1 [+26.7,+51.7] | yes | +13.3 [-4.4,+32.3] | yes |
| qwen3.6-35b-a3b-fp8 | +15.5 [+2.3,+28.3] | +29.0 [+10.8,+43.8] | yes | +2.1 [-15.9,+20.7] | yes |
| qwen3.6-27b-fp8 | +11.9 [+3.6,+20.2] | +18.9 [+5.5,+30.6] | yes | +5.4 [-5.1,+15.9] | yes |
| gpt-5.4-mini | +13.7 [+6.0,+21.4] | +15.3 [+6.3,+23.9] | yes | +10.1 [+2.2,+17.4] | yes |
| claude-haiku-4-5 | +35.7 [+23.6,+46.8] | +40.4 [+31.0,+48.3] | yes | +28.2 [+13.6,+45.1] | yes |
| deepseek-v4-flash | +26.2 [+12.8,+39.4] | +32.2 [+14.1,+49.1] | yes | +17.4 [+4.2,+31.5] | yes |
| gemini-2.5-flash | +17.9 [+6.2,+29.2] | +26.7 [+13.5,+39.5] | yes | +6.0 [-5.9,+17.4] | yes |
| gemini-2.5-pro | +11.9 [+0.1,+24.1] | +21.1 [+3.5,+37.5] | yes | +0.2 [-11.1,+11.4] | yes |
| qwen3-30b-a3b-fp8dyn | -1.2 [-15.9,+12.9] | +2.6 [-18.9,+23.2] | yes | -5.9 [-27.4,+15.8] | NO |
| llama-3.1-70b-awq | +1.8 [-7.8,+10.8] | +1.5 [-13.9,+16.1] | yes | +2.2 [-8.9,+13.3] | yes |
| llama-3.1-8b | +6.0 [-6.2,+18.4] | +0.2 [-16.3,+15.7] | yes | +12.6 [-4.2,+30.8] | yes |

## Post-cutoff anchor transplant (shift-free, descriptive)

18 post-cutoff W cells; fake dates alternate crisis anchors (9 dates)
vs calm anchors (9 dates) by design. Diff = pooled bearish share
(crisis-anchor) - (calm-anchor). Not the frozen P1 (which starts
2025-02).

| model | share crisis-anchor | share calm-anchor | diff [CI] | n sketches (c/q) | sign=full E3? |
|---|---|---|---|---|---|
| gpt-5.5 | +66.7 | +59.7 | +6.9 [+0.0,+15.3] | 72/72 | yes |
| claude-sonnet-5 | +70.8 | +58.3 | +12.5 [+1.4,+23.6] | 72/72 | yes |
| kimi-k2.6 | +68.8 | +54.9 | +13.9 [+2.1,+26.4] | 144/144 | yes |
| qwen3.6-35b-a3b-fp8 | +50.0 | +29.9 | +20.1 [+6.9,+33.3] | 144/144 | yes |
| qwen3.6-27b-fp8 | +49.3 | +47.9 | +1.4 [-6.9,+9.7] | 144/144 | yes |
| gpt-5.4-mini | +56.2 | +42.4 | +13.9 [+7.6,+20.1] | 144/144 | yes |
| claude-haiku-4-5 | +83.3 | +54.2 | +29.2 [+20.1,+38.2] | 144/144 | yes |
| deepseek-v4-flash | +64.6 | +50.7 | +13.9 [-0.7,+27.8] | 144/144 | yes |
| gemini-2.5-flash | +56.0 | +41.7 | +14.4 [+6.0,+22.2] | 216/216 | yes |
| gemini-2.5-pro | - | - | - (post-cutoff W arms absent for this row (bench_registry p1='absent')) | - | - |
| qwen3-30b-a3b-fp8dyn | +37.5 | +34.7 | +2.8 [-15.3,+20.8] | 72/72 | yes |
| llama-3.1-70b-awq | +27.1 | +28.5 | -1.4 [-10.4,+7.6] | 144/144 | NO |
| llama-3.1-8b | +41.0 | +41.0 | +0.0 [-12.5,+13.2] | 144/144 | - |

## Sign agreement summary (n = 13 full-tier models)

- fwd66 strict: same sign as frozen full E3 13/13 (opposite 0, undefined 0)
- bwd174 strict: same sign as frozen full E3 0/13 (opposite 0, undefined 13)
- fwd66 rest-baseline: same sign as frozen full E3 13/13 (opposite 0, undefined 0)
- bwd174 rest-baseline: same sign as frozen full E3 12/13 (opposite 1, undefined 0)
- full-data rest-baseline: same sign as frozen full E3 12/13 (opposite 1, undefined 0)
- post-cutoff anchor: same sign as frozen full E3 10/13 (opposite 1, undefined 2)
- fwd66 strict CI excludes zero: 10/13
- anchor CI excludes zero: 6/13

## Design caveats

1. Same seasonal phase for both families (+66 = -174 = +6 mod 12): this split tests displacement magnitude/direction robustness, NOT seasonal-phase variation — the Wp72 month-preserving 72-month arm (FM-1c C3) covers phase.
2. Asymmetric event composition across families: fwd66 contrasts fake-COVID/inflation (5 dates) against true-GFC (6 dates); bwd174 is mirrored. Family differences therefore confound offset with event era — a fwd66-vs-bwd174 gap is NOT evidence of offset sensitivity per se.
3. E3_bwd174 under the strict frozen windows is not computable: the calm years {2013,2014,2017} lie entirely in fwd66's true side, and bwd174's fake image (2005-01..2010-06) contains no calm date — calm n=0 under BOTH labelings; rendered '-', never imputed.
4. The rest-baseline supplement (crisis vs family complement) is a POST-HOC analytic choice forced by the empty calm windows; its baseline includes non-calm, non-crisis dates and is NOT the frozen calm definition. The full-data rest-baseline reference column shows how the baseline swap moves the full-sample number.
5. Anchor readout uses all 18 post-cutoff design dates (9/9); the frozen P1 placebo starts at 2025-02 and 2026-generation models' vendor cutoffs overlap early post dates — descriptive only.
6. Single-rep rows (gpt-5.5, claude-sonnet-5, gemini-2.5-pro, qwen3-30b-a3b-fp8dyn) carry per-date n of ~8 sketches; family windows of 5-6 dates make these CIs very wide by construction.

## Excluded rows

- `llama3.2:1b`: reduced 65-date tier (windows-only sampling): the fwd66/bwd174 re-partition leaves near-empty windows and the frozen row is already e3_sparse-flagged in bench_registry
- `llama3.2:3b`: reduced 65-date tier: same as llama3.2:1b
- `gpt-5-mini`: smoke-test dir (<=2 dates), never a leaderboard row, no frozen row json
- `gpt-5.1`: smoke-test dir (<=2 dates), never a leaderboard row, no frozen row json
- `llama3.1:8b`: smoke-test dir (<=2 dates; the leaderboard row is llama-3.1-8b), no frozen row json
- `qwen3.6-27b-awq`: BM2a serving-config variant of qwen3.6-27b-fp8, not a leaderboard row, no frozen row json
- `qwen3.6-27b-bf16`: BM2a serving-config variant of qwen3.6-27b-fp8, not a leaderboard row, no frozen row json

Regenerate: `python hindsight/scripts/analyze_w_offset_split.py` (no arguments; deterministic, seed 2026).
