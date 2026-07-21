# W/M-arm leakage audit (P0-1)

POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls. Regenerate: `python hindsight/scripts/audit_w_leakage.py`.

Rates = % of 04_raw_response.txt files with >=1 match. ev7 = original 7-term event lexicon, ev18 = expanded 18-term. mo-yr = 'MonthName YYYY'. fakeY/trueY/anachr are W-only joins on the asserted fake date (anachr = any year strictly after the fake year; unit echoes like '2017 Dollars'/'1982-1984=100' and snapshot-value echoes like 'HOUST=2014.0' excluded; the W fake date is a circular shift, so for late true dates the fake year precedes the true year and true-period mentions count as anachronisms). trueY denominator = cells with true year != fake year.

| model | tier | W n | yr% | ev7% | ev18% | mo-yr% | fakeY% | trueY% | anachr% | M n | yr% | ev7% | ev18% | mo-yr% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-5.5 | full | 258 | 4.7 | 0.0 | 10.8 | 1.9 | 6.6 | 0.0 | 1.2 | 258 | 0.8 | 0.0 | 5.0 | 0.0 |
| claude-sonnet-5 | full | 258 | 15.9 | 11.6 | 23.3 | 5.8 | 24.8 | 0.8 | 1.9 | 258 | 0.0 | 1.6 | 10.8 | 0.0 |
| kimi-k2.6 | full | 516 | 3.5 | 1.2 | 22.9 | 3.5 | 7.8 | 0.4 | 0.4 | 516 | 0.0 | 0.4 | 23.8 | 0.0 |
| qwen3.6-35b-a3b-fp8 | full | 516 | 29.8 | 4.3 | 30.2 | 2.1 | 89.9 | 6.0 | 13.6 | 516 | 4.8 | 3.7 | 36.2 | 0.0 |
| qwen3.6-27b-fp8 | full | 516 | 33.3 | 8.9 | 23.3 | 5.6 | 99.8 | 3.9 | 11.6 | 516 | 1.2 | 0.0 | 29.6 | 0.2 |
| gpt-5.4-mini | full | 516 | 1.4 | 0.0 | 2.7 | 0.0 | 1.4 | 0.2 | 0.2 | 516 | 0.0 | 0.0 | 4.7 | 0.0 |
| claude-haiku-4-5 | full | 516 | 27.9 | 12.6 | 43.0 | 37.4 | 85.9 | 2.1 | 6.0 | 516 | 0.8 | 0.8 | 49.2 | 0.0 |
| deepseek-v4-flash | full | 516 | 9.7 | 7.2 | 21.1 | 6.0 | 10.5 | 1.7 | 2.9 | 516 | 1.7 | 1.7 | 20.3 | 0.0 |
| gemini-2.5-flash | full | 774 | 2.7 | 1.6 | 15.8 | 0.8 | 5.0 | 0.0 | 0.7 | 774 | 0.0 | 0.0 | 14.5 | 0.0 |
| gemini-2.5-pro | full | 240 | 41.2 | 37.5 | 77.5 | 14.2 | 37.5 | 3.8 | 5.0 | 720 | 0.6 | 1.0 | 63.5 | 0.0 |
| qwen3-30b-a3b-fp8dyn | full | 258 | 3.1 | 1.6 | 22.9 | 0.0 | 10.1 | 0.0 | 1.6 | 258 | 0.0 | 0.4 | 23.3 | 0.0 |
| llama-3.1-70b-awq | full | 516 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 516 | 0.0 | 0.0 | 0.0 | 0.0 |
| llama-3.1-8b | full | 516 | 0.4 | 0.4 | 0.4 | 0.0 | 0.4 | 0.0 | 0.2 | 516 | 0.0 | 0.0 | 0.0 | 0.0 |
| llama3.2:3b | reduced-65date | 65 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 65 | 0.0 | 0.0 | 0.0 | 0.0 |
| llama3.2:1b | reduced-65date | 65 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 65 | 0.0 | 0.0 | 0.0 | 0.0 |
| gpt-5-mini | smoke-2date | 2 | 0.0 | 0.0 | 50.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| gpt-5.1 | smoke-2date | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | 0.0 | 2 | 0.0 | 0.0 | 0.0 | 0.0 |
| llama3.1:8b | smoke-2date | 2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 2 | 0.0 | 0.0 | 0.0 | 0.0 |
| qwen3.6-27b-awq | quant-variant | 258 | 31.4 | 14.3 | 34.5 | 14.0 | 95.3 | 3.5 | 10.1 | 258 | 5.0 | 1.6 | 36.0 | 0.0 |
| qwen3.6-27b-bf16 | quant-variant | 515 | 34.9 | 8.0 | 21.6 | 7.4 | 100.0 | 4.3 | 10.7 | 516 | 0.8 | 0.2 | 20.9 | 0.0 |

External anchors reproduced: gemini-2.5-pro_W_event7=90/240; gemini-2.5-pro_W_year=99/240; qwen3.6-27b-bf16_W_year=180/515; M_monthyear_4models=0/2268

## qwen3.6-27b-bf16 date-doubt join (e)

Doubt regex `look(s)?( more)? like (19|20)\d\d`: 39/515 W cells, 39 of them with >=1 valid sketch. Mean bearish share in doubt cells 0.458 vs W-arm mean 0.460.

| rep | true date | fake date | n sk | bearish | d vs W mean |
|---|---|---|---|---|---|
| rep1 | 2006-08-15 | 2012-02-15 | 8 | 0.500 | +0.040 |
| rep1 | 2006-10-15 | 2012-04-15 | 8 | 0.500 | +0.040 |
| rep1 | 2006-11-15 | 2012-05-15 | 8 | 0.500 | +0.040 |
| rep1 | 2007-03-15 | 2012-09-15 | 8 | 0.500 | +0.040 |
| rep1 | 2007-04-15 | 2012-10-15 | 8 | 0.500 | +0.040 |
| rep1 | 2007-06-15 | 2012-12-15 | 8 | 0.500 | +0.040 |
| rep1 | 2007-07-15 | 2013-01-15 | 8 | 0.375 | -0.085 |
| rep1 | 2020-07-15 | 2006-01-15 | 8 | 0.625 | +0.165 |
| rep1 | 2020-08-15 | 2006-02-15 | 8 | 0.250 | -0.210 |
| rep1 | 2020-10-15 | 2006-04-15 | 8 | 0.375 | -0.085 |
| rep1 | 2023-07-15 | 2009-01-15 | 8 | 0.375 | -0.085 |
| rep1 | 2023-11-15 | 2009-05-15 | 8 | 0.500 | +0.040 |
| rep1 | 2024-01-15 | 2009-07-15 | 8 | 0.500 | +0.040 |
| rep1 | 2024-05-15 | 2009-11-15 | 8 | 0.375 | -0.085 |
| rep1 | 2024-06-15 | 2009-12-15 | 8 | 0.375 | -0.085 |
| rep1 | 2024-07-15 | 2010-01-15 | 8 | 0.500 | +0.040 |
| rep1 | 2024-10-15 | 2010-04-15 | 8 | 0.500 | +0.040 |
| rep2 | 2006-08-15 | 2012-02-15 | 8 | 0.500 | +0.040 |
| rep2 | 2006-11-15 | 2012-05-15 | 8 | 0.500 | +0.040 |
| rep2 | 2007-01-15 | 2012-07-15 | 8 | 0.375 | -0.085 |
| rep2 | 2007-03-15 | 2012-09-15 | 8 | 0.625 | +0.165 |
| rep2 | 2007-11-15 | 2013-05-15 | 8 | 0.375 | -0.085 |
| rep2 | 2008-01-15 | 2013-07-15 | 8 | 0.375 | -0.085 |
| rep2 | 2012-12-15 | 2018-06-15 | 8 | 0.500 | +0.040 |
| rep2 | 2013-03-15 | 2018-09-15 | 8 | 0.500 | +0.040 |
| rep2 | 2013-05-15 | 2018-11-15 | 8 | 0.375 | -0.085 |
| rep2 | 2020-09-15 | 2006-03-15 | 8 | 0.375 | -0.085 |
| rep2 | 2023-08-15 | 2009-02-15 | 8 | 0.500 | +0.040 |
| rep2 | 2023-10-15 | 2009-04-15 | 8 | 0.500 | +0.040 |
| rep2 | 2023-11-15 | 2009-05-15 | 8 | 0.500 | +0.040 |
| rep2 | 2023-12-15 | 2009-06-15 | 8 | 0.500 | +0.040 |
| rep2 | 2024-01-15 | 2009-07-15 | 8 | 0.500 | +0.040 |
| rep2 | 2024-02-15 | 2009-08-15 | 8 | 0.375 | -0.085 |
| rep2 | 2024-03-15 | 2009-09-15 | 8 | 0.500 | +0.040 |
| rep2 | 2024-04-15 | 2009-10-15 | 8 | 0.500 | +0.040 |
| rep2 | 2024-06-15 | 2009-12-15 | 8 | 0.375 | -0.085 |
| rep2 | 2024-07-15 | 2010-01-15 | 8 | 0.375 | -0.085 |
| rep2 | 2024-09-15 | 2010-03-15 | 8 | 0.625 | +0.165 |
| rep2 | 2024-10-15 | 2010-04-15 | 8 | 0.375 | -0.085 |

## Extended date-questioning scan, bench W corpus (f)

analyze_w_questioning.py corpus/logic, tier1 + qwen extension patterns ['look(s)?( more)? like (19|20)\\d\\d', '(data|values|snapshot)\\b.{0,40}, not (19|20)\\d\\d'] (original script and FM-1 output untouched). Units = valid sketches + raw-outside-JSON blocks.

| model | tier | n sketches | n raw | tier1 orig | tier1 ext-only | tier1 total | tier2 only |
|---|---|---|---|---|---|---|---|
| gpt-5.5 | full | 2064 | 258 | 0 | 0 | 0 | 0 |
| claude-sonnet-5 | full | 2064 | 258 | 0 | 0 | 0 | 0 |
| kimi-k2.6 | full | 4128 | 516 | 0 | 0 | 0 | 0 |
| qwen3.6-35b-a3b-fp8 | full | 4128 | 516 | 24 | 30 | 54 | 0 |
| qwen3.6-27b-fp8 | full | 4121 | 516 | 32 | 12 | 44 | 0 |
| gpt-5.4-mini | full | 4120 | 516 | 0 | 0 | 0 | 0 |
| claude-haiku-4-5 | full | 4128 | 516 | 0 | 0 | 0 | 0 |
| deepseek-v4-flash | full | 4128 | 516 | 0 | 0 | 0 | 0 |
| gemini-2.5-flash | full | 6192 | 774 | 0 | 0 | 0 | 0 |
| gemini-2.5-pro | full | 1920 | 240 | 0 | 0 | 0 | 0 |
| qwen3-30b-a3b-fp8dyn | full | 2064 | 258 | 1 | 0 | 1 | 0 |
| llama-3.1-70b-awq | full | 4128 | 516 | 0 | 0 | 0 | 0 |
| llama-3.1-8b | full | 4127 | 516 | 0 | 0 | 0 | 0 |
| llama3.2:3b | reduced-65date | 304 | 65 | 0 | 0 | 0 | 0 |
| llama3.2:1b | reduced-65date | 452 | 65 | 0 | 0 | 0 | 0 |
| gpt-5-mini | smoke-2date | 16 | 2 | 0 | 0 | 0 | 0 |
| gpt-5.1 | smoke-2date | 16 | 2 | 0 | 0 | 0 | 0 |
| llama3.1:8b | smoke-2date | 16 | 2 | 0 | 0 | 0 | 0 |
| qwen3.6-27b-awq | quant-variant | 2064 | 258 | 3 | 3 | 6 | 0 |
| qwen3.6-27b-bf16 | quant-variant | 4120 | 515 | 30 | 17 | 47 | 0 |
