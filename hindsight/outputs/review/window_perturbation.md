# Crisis/calm window perturbation ablation (P0-2)

POST-FREEZE EXPLORATORY (review-response, 2026-07-21); zero API calls.
All numbers recomputed from frozen bench arms; windows are analysis-time constructs (prompts partition-independent).

## Reconciliation (perturbation = none vs frozen row json)

| model | frozen E2 | recomputed E2 | frozen E3 | recomputed E3 | bit-exact |
|---|---|---|---|---|---|
| gpt-5.5 | +21.5 | +21.5 | +16.1 | +16.1 | YES |
| claude-sonnet-5 | +32.6 | +32.6 | +45.0 | +45.0 | YES |
| kimi-k2.6 | +33.2 | +33.2 | +38.5 | +38.5 | YES |
| qwen3.6-35b-a3b-fp8 | +23.7 | +23.7 | +34.6 | +34.6 | YES |
| qwen3.6-27b-fp8 | +19.3 | +19.3 | +18.1 | +18.1 | YES |
| gpt-5.4-mini | +14.4 | +14.4 | +18.7 | +18.7 | YES |
| claude-haiku-4-5 | +38.3 | +38.3 | +49.5 | +49.5 | YES |
| deepseek-v4-flash | +41.6 | +41.6 | +30.9 | +30.9 | YES |
| gemini-2.5-flash | +25.6 | +25.6 | +31.1 | +31.1 | YES |
| gemini-2.5-pro | +16.7 | +16.7 | +24.2 | +24.2 | YES |
| qwen3-30b-a3b-fp8dyn | +6.3 | +6.3 | +1.6 | +1.6 | YES |
| llama-3.1-70b-awq | -4.7 | -4.7 | +0.8 | +0.8 | YES |
| llama-3.1-8b | +5.6 | +5.6 | +7.6 | +7.6 | YES |

## Excluded rows

- **llama3.2:1b**: reduced 65-date tier (plan P0-2 边界): crisis/calm blocks only partially sampled, re-partition leaves empty cells
- **llama3.2:3b**: reduced 65-date tier (plan P0-2 边界): same as llama3.2:1b
- **gpt-5-mini**: smoke-test dir (<=2 dates), never a leaderboard row, no frozen row json
- **gpt-5.1**: smoke-test dir (<=2 dates), never a leaderboard row, no frozen row json
- **llama3.1:8b**: smoke-test dir (<=2 dates; the leaderboard row is llama-3.1-8b), no frozen row json
- **qwen3.6-27b-awq**: BM2a serving-config variant of qwen3.6-27b-fp8, not a leaderboard row, no frozen row json
- **qwen3.6-27b-bf16**: BM2a serving-config variant of qwen3.6-27b-fp8, not a leaderboard row, no frozen row json

## Per model x perturbation (E2 / E3, pp; sign-held vs frozen)

CIs (B=10k, frozen util/seed) computed for none + leave-one-event-out only, per plan.

| model | perturbation | E2 | E2 CI95 | E2 sign held | E2 CI excl 0 | E3 | E3 CI95 | E3 sign held | E3 CI excl 0 |
|---|---|---|---|---|---|---|---|---|---|
| gpt-5.5 | none | +21.5 | [+9.8,+32.8] | True | yes | +16.1 | [+9.3,+22.9] | True | yes |
| gpt-5.5 | drop_GFC | +8.5 | [-5.1,+25.0] | True | no | +12.4 | [+3.9,+21.4] | True | yes |
| gpt-5.5 | drop_COVID | +27.4 | [+16.7,+37.8] | True | yes | +16.3 | [+8.3,+24.3] | True | yes |
| gpt-5.5 | drop_inflation | +22.9 | [+8.5,+36.5] | True | yes | +18.1 | [+11.3,+24.7] | True | yes |
| gpt-5.5 | calm_2013_2014 | +22.0 | - | True | - | +13.1 | - | True | - |
| gpt-5.5 | calm_2014_2017 | +18.9 | - | True | - | +19.9 | - | True | - |
| gpt-5.5 | calm_2013_2017 | +23.6 | - | True | - | +15.2 | - | True | - |
| gpt-5.5 | calm_2006_2013_2014_2017 | +19.9 | - | True | - | +15.5 | - | True | - |
| gpt-5.5 | balanced_n11 | +25.0 | - | True | - | +12.5 | - | True | - |
| claude-sonnet-5 | none | +32.6 | [+18.7,+45.9] | True | yes | +45.0 | [+26.5,+63.5] | True | yes |
| claude-sonnet-5 | drop_GFC | +24.2 | [+3.1,+44.4] | True | yes | +25.2 | [+9.0,+43.5] | True | yes |
| claude-sonnet-5 | drop_COVID | +36.1 | [+22.9,+49.3] | True | yes | +48.3 | [+28.8,+67.7] | True | yes |
| claude-sonnet-5 | drop_inflation | +33.9 | [+17.7,+49.3] | True | yes | +53.6 | [+32.6,+73.3] | True | yes |
| claude-sonnet-5 | calm_2013_2014 | +34.7 | - | True | - | +38.7 | - | True | - |
| claude-sonnet-5 | calm_2014_2017 | +33.1 | - | True | - | +55.4 | - | True | - |
| claude-sonnet-5 | calm_2013_2017 | +30.0 | - | True | - | +40.8 | - | True | - |
| claude-sonnet-5 | calm_2006_2013_2014_2017 | +31.5 | - | True | - | +40.3 | - | True | - |
| claude-sonnet-5 | balanced_n11 | +28.4 | - | True | - | +36.4 | - | True | - |
| kimi-k2.6 | none | +33.2 | [+24.6,+41.3] | True | yes | +38.5 | [+26.4,+50.9] | True | yes |
| kimi-k2.6 | drop_GFC | +36.1 | [+28.5,+44.4] | True | yes | +24.8 | [+13.2,+39.4] | True | yes |
| kimi-k2.6 | drop_COVID | +32.1 | [+22.9,+41.0] | True | yes | +39.4 | [+26.4,+51.7] | True | yes |
| kimi-k2.6 | drop_inflation | +32.6 | [+22.0,+42.1] | True | yes | +45.9 | [+33.9,+56.9] | True | yes |
| kimi-k2.6 | calm_2013_2014 | +36.6 | - | True | - | +29.0 | - | True | - |
| kimi-k2.6 | calm_2014_2017 | +33.2 | - | True | - | +48.5 | - | True | - |
| kimi-k2.6 | calm_2013_2017 | +29.8 | - | True | - | +37.9 | - | True | - |
| kimi-k2.6 | calm_2006_2013_2014_2017 | +30.1 | - | True | - | +31.9 | - | True | - |
| kimi-k2.6 | balanced_n11 | +26.1 | - | True | - | +37.5 | - | True | - |
| qwen3.6-35b-a3b-fp8 | none | +23.7 | [+11.7,+35.5] | True | yes | +34.6 | [+23.7,+45.6] | True | yes |
| qwen3.6-35b-a3b-fp8 | drop_GFC | +23.8 | [+8.3,+38.2] | True | yes | +37.3 | [+25.3,+52.0] | True | yes |
| qwen3.6-35b-a3b-fp8 | drop_COVID | +26.7 | [+13.2,+39.4] | True | yes | +36.5 | [+24.0,+49.1] | True | yes |
| qwen3.6-35b-a3b-fp8 | drop_inflation | +20.2 | [+5.6,+34.7] | True | yes | +30.7 | [+19.3,+43.1] | True | yes |
| qwen3.6-35b-a3b-fp8 | calm_2013_2014 | +28.2 | - | True | - | +31.7 | - | True | - |
| qwen3.6-35b-a3b-fp8 | calm_2014_2017 | +19.1 | - | True | - | +35.6 | - | True | - |
| qwen3.6-35b-a3b-fp8 | calm_2013_2017 | +23.8 | - | True | - | +36.4 | - | True | - |
| qwen3.6-35b-a3b-fp8 | calm_2006_2013_2014_2017 | +19.0 | - | True | - | +24.5 | - | True | - |
| qwen3.6-35b-a3b-fp8 | balanced_n11 | +27.3 | - | True | - | +36.4 | - | True | - |
| qwen3.6-27b-fp8 | none | +19.3 | [+10.8,+28.5] | True | yes | +18.1 | [+11.4,+25.1] | True | yes |
| qwen3.6-27b-fp8 | drop_GFC | +24.3 | [+9.4,+39.4] | True | yes | +21.8 | [+12.6,+30.3] | True | yes |
| qwen3.6-27b-fp8 | drop_COVID | +20.7 | [+10.8,+31.1] | True | yes | +17.9 | [+10.9,+25.0] | True | yes |
| qwen3.6-27b-fp8 | drop_inflation | +14.6 | [+7.9,+20.9] | True | yes | +16.1 | [+8.3,+24.7] | True | yes |
| qwen3.6-27b-fp8 | calm_2013_2014 | +18.2 | - | True | - | +15.0 | - | True | - |
| qwen3.6-27b-fp8 | calm_2014_2017 | +20.3 | - | True | - | +18.1 | - | True | - |
| qwen3.6-27b-fp8 | calm_2013_2017 | +19.3 | - | True | - | +21.3 | - | True | - |
| qwen3.6-27b-fp8 | calm_2006_2013_2014_2017 | +17.3 | - | True | - | +17.7 | - | True | - |
| qwen3.6-27b-fp8 | balanced_n11 | +22.7 | - | True | - | +22.2 | - | True | - |
| gpt-5.4-mini | none | +14.4 | [+6.6,+22.4] | True | yes | +18.7 | [+7.9,+29.3] | True | yes |
| gpt-5.4-mini | drop_GFC | +23.4 | [+15.6,+31.7] | True | yes | +5.7 | [-4.9,+15.1] | True | no |
| gpt-5.4-mini | drop_COVID | +12.8 | [+4.0,+22.0] | True | yes | +19.6 | [+6.5,+32.2] | True | yes |
| gpt-5.4-mini | drop_inflation | +10.6 | [+2.1,+18.7] | True | yes | +26.0 | [+15.9,+35.8] | True | yes |
| gpt-5.4-mini | calm_2013_2014 | +16.9 | - | True | - | +16.2 | - | True | - |
| gpt-5.4-mini | calm_2014_2017 | +11.4 | - | True | - | +21.6 | - | True | - |
| gpt-5.4-mini | calm_2013_2017 | +15.0 | - | True | - | +18.5 | - | True | - |
| gpt-5.4-mini | calm_2006_2013_2014_2017 | +12.7 | - | True | - | +17.1 | - | True | - |
| gpt-5.4-mini | balanced_n11 | +17.0 | - | True | - | +14.8 | - | True | - |
| claude-haiku-4-5 | none | +38.3 | [+30.4,+46.6] | True | yes | +49.5 | [+34.2,+64.3] | True | yes |
| claude-haiku-4-5 | drop_GFC | +36.9 | [+27.2,+47.3] | True | yes | +29.2 | [+14.2,+46.7] | True | yes |
| claude-haiku-4-5 | drop_COVID | +38.0 | [+29.9,+46.7] | True | yes | +50.2 | [+32.3,+66.7] | True | yes |
| claude-haiku-4-5 | drop_inflation | +39.4 | [+30.1,+48.7] | True | yes | +61.5 | [+49.9,+72.7] | True | yes |
| claude-haiku-4-5 | calm_2013_2014 | +43.4 | - | True | - | +54.1 | - | True | - |
| claude-haiku-4-5 | calm_2014_2017 | +34.8 | - | True | - | +48.2 | - | True | - |
| claude-haiku-4-5 | calm_2013_2017 | +36.6 | - | True | - | +46.3 | - | True | - |
| claude-haiku-4-5 | calm_2006_2013_2014_2017 | +32.1 | - | True | - | +47.5 | - | True | - |
| claude-haiku-4-5 | balanced_n11 | +37.5 | - | True | - | +38.6 | - | True | - |
| deepseek-v4-flash | none | +41.6 | [+29.9,+53.5] | True | yes | +30.9 | [+14.0,+47.5] | True | yes |
| deepseek-v4-flash | drop_GFC | +31.5 | [+21.8,+40.8] | True | yes | +13.4 | [-6.5,+35.1] | True | no |
| deepseek-v4-flash | drop_COVID | +46.2 | [+34.0,+58.3] | True | yes | +33.0 | [+15.6,+49.7] | True | yes |
| deepseek-v4-flash | drop_inflation | +42.7 | [+27.5,+58.0] | True | yes | +39.5 | [+21.7,+56.2] | True | yes |
| deepseek-v4-flash | calm_2013_2014 | +47.6 | - | True | - | +24.7 | - | True | - |
| deepseek-v4-flash | calm_2014_2017 | +38.2 | - | True | - | +37.2 | - | True | - |
| deepseek-v4-flash | calm_2013_2017 | +39.0 | - | True | - | +30.7 | - | True | - |
| deepseek-v4-flash | calm_2006_2013_2014_2017 | +36.5 | - | True | - | +28.4 | - | True | - |
| deepseek-v4-flash | balanced_n11 | +40.9 | - | True | - | +28.4 | - | True | - |
| gemini-2.5-flash | none | +25.6 | [+14.5,+36.8] | True | yes | +31.1 | [+19.6,+42.6] | True | yes |
| gemini-2.5-flash | drop_GFC | +22.8 | [+15.0,+30.4] | True | yes | +13.2 | [+7.5,+19.7] | True | yes |
| gemini-2.5-flash | drop_COVID | +26.7 | [+13.7,+40.4] | True | yes | +35.3 | [+23.0,+47.2] | True | yes |
| gemini-2.5-flash | drop_inflation | +26.0 | [+11.6,+40.7] | True | yes | +37.4 | [+24.4,+49.2] | True | yes |
| gemini-2.5-flash | calm_2013_2014 | +27.4 | - | True | - | +27.8 | - | True | - |
| gemini-2.5-flash | calm_2014_2017 | +23.4 | - | True | - | +35.1 | - | True | - |
| gemini-2.5-flash | calm_2013_2017 | +26.0 | - | True | - | +30.2 | - | True | - |
| gemini-2.5-flash | calm_2006_2013_2014_2017 | +24.0 | - | True | - | +26.8 | - | True | - |
| gemini-2.5-flash | balanced_n11 | +28.4 | - | True | - | +25.8 | - | True | - |
| gemini-2.5-pro | none | +16.7 | [+9.9,+23.6] | True | yes | +24.2 | [+13.1,+35.6] | True | yes |
| gemini-2.5-pro | drop_GFC | +14.3 | [+8.3,+20.5] | True | yes | +10.3 | [+0.8,+19.9] | True | yes |
| gemini-2.5-pro | drop_COVID | +17.5 | [+9.8,+25.5] | True | yes | +28.1 | [+16.0,+39.9] | True | yes |
| gemini-2.5-pro | drop_inflation | +17.2 | [+8.8,+25.7] | True | yes | +28.5 | [+15.5,+41.3] | True | yes |
| gemini-2.5-pro | calm_2013_2014 | +18.0 | - | True | - | +23.3 | - | True | - |
| gemini-2.5-pro | calm_2014_2017 | +14.5 | - | True | - | +25.9 | - | True | - |
| gemini-2.5-pro | calm_2013_2017 | +17.5 | - | True | - | +23.3 | - | True | - |
| gemini-2.5-pro | calm_2006_2013_2014_2017 | +15.7 | - | True | - | +19.4 | - | True | - |
| gemini-2.5-pro | balanced_n11 | +19.7 | - | True | - | +22.7 | - | True | - |
| qwen3-30b-a3b-fp8dyn | none | +6.3 | [-9.7,+23.6] | True | no | +1.6 | [-14.1,+17.5] | True | no |
| qwen3-30b-a3b-fp8dyn | drop_GFC | -5.8 | [-21.9,+13.1] | False | no | -2.2 | [-30.1,+28.8] | False | no |
| qwen3-30b-a3b-fp8dyn | drop_COVID | +4.5 | [-13.5,+25.3] | True | no | +4.2 | [-11.8,+21.2] | True | no |
| qwen3-30b-a3b-fp8dyn | drop_inflation | +15.8 | [-2.1,+34.0] | True | no | +1.2 | [-13.0,+14.1] | True | no |
| qwen3-30b-a3b-fp8dyn | calm_2013_2014 | +4.0 | - | True | - | -1.7 | - | False | - |
| qwen3-30b-a3b-fp8dyn | calm_2014_2017 | +7.7 | - | True | - | +4.1 | - | True | - |
| qwen3-30b-a3b-fp8dyn | calm_2013_2017 | +7.1 | - | True | - | +2.5 | - | True | - |
| qwen3-30b-a3b-fp8dyn | calm_2006_2013_2014_2017 | +6.6 | - | True | - | +1.5 | - | True | - |
| qwen3-30b-a3b-fp8dyn | balanced_n11 | +4.5 | - | True | - | +6.8 | - | True | - |
| llama-3.1-70b-awq | none | -4.7 | [-12.0,+3.0] | True | no | +0.8 | [-9.7,+10.8] | True | no |
| llama-3.1-70b-awq | drop_GFC | -3.0 | [-15.6,+9.9] | True | no | +1.6 | [-15.3,+17.3] | True | no |
| llama-3.1-70b-awq | drop_COVID | -7.8 | [-14.6,-0.9] | True | yes | +5.4 | [-5.4,+14.4] | True | no |
| llama-3.1-70b-awq | drop_inflation | -2.2 | [-9.5,+5.8] | True | no | -4.8 | [-16.2,+6.5] | False | no |
| llama-3.1-70b-awq | calm_2013_2014 | -3.8 | - | True | - | -1.9 | - | False | - |
| llama-3.1-70b-awq | calm_2014_2017 | -6.9 | - | True | - | +2.5 | - | True | - |
| llama-3.1-70b-awq | calm_2013_2017 | -3.3 | - | True | - | +2.0 | - | True | - |
| llama-3.1-70b-awq | calm_2006_2013_2014_2017 | -4.3 | - | True | - | +0.8 | - | True | - |
| llama-3.1-70b-awq | balanced_n11 | -3.4 | - | True | - | +0.0 | - | False | - |
| llama-3.1-8b | none | +5.6 | [-9.7,+20.3] | True | no | +7.6 | [-2.4,+17.8] | True | no |
| llama-3.1-8b | drop_GFC | +13.0 | [+4.0,+24.1] | True | yes | +9.4 | [-0.8,+20.3] | True | no |
| llama-3.1-8b | drop_COVID | +1.9 | [-15.1,+18.8] | True | no | +5.4 | [-5.2,+16.8] | True | no |
| llama-3.1-8b | drop_inflation | +5.2 | [-14.8,+24.3] | True | no | +8.9 | [-3.8,+21.4] | True | no |
| llama-3.1-8b | calm_2013_2014 | +10.1 | - | True | - | +4.9 | - | True | - |
| llama-3.1-8b | calm_2014_2017 | +2.2 | - | True | - | +8.3 | - | True | - |
| llama-3.1-8b | calm_2013_2017 | +4.6 | - | True | - | +9.6 | - | True | - |
| llama-3.1-8b | calm_2006_2013_2014_2017 | +6.3 | - | True | - | +4.6 | - | True | - |
| llama-3.1-8b | balanced_n11 | +1.7 | - | True | - | +13.1 | - | True | - |

## Drop-1-crisis-date jackknife (11 variants per model)

| model | E2 min..max (pp) | E2 sign flips | E3 min..max (pp) | E3 sign flips |
|---|---|---|---|---|
| gpt-5.5 | +18.5..+24.8 | 0/11 | +14.9..+17.4 | 0/11 |
| claude-sonnet-5 | +29.2..+36.7 | 0/11 | +40.2..+49.0 | 0/11 |
| kimi-k2.6 | +31.8..+35.5 | 0/11 | +36.1..+40.5 | 0/11 |
| qwen3.6-35b-a3b-fp8 | +20.7..+26.9 | 0/11 | +31.7..+36.7 | 0/11 |
| qwen3.6-27b-fp8 | +16.8..+21.1 | 0/11 | +16.8..+19.3 | 0/11 |
| gpt-5.4-mini | +12.2..+16.5 | 0/11 | +16.3..+21.9 | 0/11 |
| claude-haiku-4-5 | +36.3..+39.4 | 0/11 | +46.1..+53.6 | 0/11 |
| deepseek-v4-flash | +38.3..+44.0 | 0/11 | +27.2..+35.3 | 0/11 |
| gemini-2.5-flash | +22.3..+28.6 | 0/11 | +28.6..+33.2 | 0/11 |
| gemini-2.5-pro | +14.7..+18.5 | 0/11 | +21.6..+26.6 | 0/11 |
| qwen3-30b-a3b-fp8dyn | +1.7..+9.2 | 0/11 | -3.5..+5.3 | 1/11 |
| llama-3.1-70b-awq | -6.7..-3.0 | 0/11 | -0.9..+3.5 | 5/11 |
| llama-3.1-8b | +1.8..+10.5 | 0/11 | +5.0..+10.0 | 0/11 |

## Sign-flip summary

- non-jackknife cells (model x perturbation x endpoint): 6 flips / 208 cells
- of those, flips where the frozen E2 CI excluded zero: 0; frozen E3 CI excluded zero: 0
- of the non-jackknife flips, exact-zero boundaries (estimate exactly 0, i.e. gap_fake == gap_true — not a reversal): 1
- jackknife variant flips (all models, both endpoints): 6 / 286

- calm-year substitute: 2004 not in universe (2005..2024); used 2006 (mean VIX 12.81)
- balanced-n11 calm dates: 2013-01-15, 2013-02-15, 2013-03-15, 2013-04-15, 2013-05-15, 2013-06-15, 2017-12-15, 2017-11-15, 2017-10-15, 2017-09-15, 2017-08-15
