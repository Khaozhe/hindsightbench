# Corpus salience, sampled-window instrument (Infini-gram search_docs, Dolma 1.7; post-freeze exploratory)

months covered: 240/240, median windows per month: 100. S_T = share of sampled 'Month YYYY' windows (+-200 tokens) containing crisis vocabulary.

Top months by S_T: 2020-03 0.38, 2020-04 0.27, 2020-06 0.24, 2020-07 0.21, 2020-02 0.18, 2020-05 0.16, 2020-08 0.16, 2021-02 0.16, 2021-04 0.16, 2021-03 0.15

Crisis-set months: 2008-09 0.08, 2008-10 0.06, 2008-11 0.08, 2008-12 0.11, 2009-01 0.10, 2009-02 0.07, 2020-03 0.38, 2020-04 0.27, 2022-06 0.08, 2022-09 0.07, 2022-10 0.04

mean S_T crisis set 0.122 vs calm set 0.031 vs all other months 0.057

| row | rho(h_t, S_T) all dates | p | rho outside crisis set | p | rho(h_t, S_fin) |
|---|---|---|---|---|---|
| claude-haiku-4-5 | +0.114 | 0.078 | +0.056 | 0.4 | +0.053 |
| claude-sonnet-5 | +0.054 | 0.4 | +0.004 | 0.95 | +0.009 |
| deepseek-v4-flash | +0.132 | 0.041 | +0.082 | 0.22 | +0.095 |
| gemini-2.5-flash | +0.205 | 0.0014 | +0.168 | 0.011 | +0.103 |
| gemini-2.5-pro | -0.012 | 0.86 | -0.073 | 0.27 | +0.024 |
| gpt-5.4-mini | +0.189 | 0.0032 | +0.166 | 0.012 | +0.016 |
| gpt-5.5 | +0.081 | 0.21 | +0.046 | 0.49 | +0.171 |
| hermes3-70b-fp8 | +0.009 | 0.89 | +0.005 | 0.93 | +0.009 |
| kimi-k2.6 | +0.028 | 0.66 | -0.039 | 0.55 | +0.093 |
| llama-3.1-70b-awq | +0.046 | 0.48 | +0.055 | 0.41 | -0.020 |
| llama-3.1-70b-fp8dyn | -0.035 | 0.59 | -0.036 | 0.59 | -0.101 |
| llama-3.1-8b | +0.176 | 0.0063 | +0.168 | 0.011 | -0.018 |
| llama-3.1-nemotron-70b-awq | -0.041 | 0.52 | -0.068 | 0.31 | -0.038 |
| llama-3.3-70b-awq | -0.011 | 0.87 | -0.025 | 0.7 | -0.004 |
| llama-3.3-70b-fp8dyn | +0.096 | 0.14 | +0.105 | 0.11 | -0.090 |
| olmo3-32b-base-guided | -0.066 | 0.31 | -0.076 | 0.25 | +0.011 |
| olmo3-7b-base-guided | -0.076 | 0.24 | -0.074 | 0.27 | -0.096 |
| olmo3-7b-dpo | +0.020 | 0.76 | +0.018 | 0.79 | +0.115 |
| olmo3-7b-instruct | +0.007 | 0.92 | +0.023 | 0.73 | -0.050 |
| olmo3-7b-instruct-guided | +0.011 | 0.87 | +0.033 | 0.62 | -0.040 |
| olmo3-7b-sft | -0.018 | 0.78 | -0.011 | 0.87 | -0.166 |
| olmo3-7b-think | -0.015 | 0.82 | -0.014 | 0.83 | +0.055 |
| olmo3.1-32b-dpo | +0.095 | 0.14 | +0.092 | 0.17 | -0.123 |
| olmo3.1-32b-instruct | -0.055 | 0.4 | -0.017 | 0.8 | -0.015 |
| olmo3.1-32b-instruct-guided | -0.117 | 0.071 | -0.135 | 0.041 | -0.080 |
| olmo3.1-32b-sft | +0.082 | 0.21 | +0.098 | 0.14 | +0.123 |
| qwen3-30b-a3b-fp8dyn | -0.004 | 0.95 | -0.017 | 0.8 | -0.029 |
| qwen3-30b-a3b-instruct-2507-fp8dyn | +0.119 | 0.066 | +0.090 | 0.17 | -0.014 |
| qwen3-30b-a3b-thinking-2507-awq | -0.079 | 0.22 | -0.099 | 0.14 | -0.182 |
| qwen3-30b-a3b-thinking-2507-bf16 | +0.111 | 0.087 | +0.095 | 0.15 | -0.038 |
| qwen3-30b-a3b-thinking-2507-bf16-fp16act | -0.063 | 0.33 | -0.061 | 0.36 | +0.165 |
| qwen3-30b-a3b-thinking-2507-bf16-r2 | +0.000 | 1 | +0.007 | 0.92 | -0.035 |
| qwen3-30b-a3b-thinking-2507-fp8block | -0.011 | 0.87 | -0.033 | 0.62 | +0.004 |
| qwen3-30b-a3b-thinking-2507-fp8dyn | +0.083 | 0.2 | +0.034 | 0.61 | -0.024 |
| qwen3-30b-a3b-thinking-2507-gptq-w4a16 | +0.033 | 0.62 | +0.019 | 0.77 | -0.128 |
| qwen3-30b-a3b-thinking-2507-int8-w8a8 | -0.009 | 0.89 | -0.029 | 0.67 | +0.043 |
| qwen3.6-27b-awq | +0.085 | 0.19 | +0.061 | 0.36 | +0.137 |
| qwen3.6-27b-bf16 | +0.065 | 0.32 | +0.054 | 0.41 | +0.001 |
| qwen3.6-27b-fp8 | +0.057 | 0.38 | +0.008 | 0.9 | +0.123 |
| qwen3.6-35b-a3b-fp8 | +0.228 | 0.00036 | +0.215 | 0.0011 | -0.027 |
| r1-distill-llama-70b-awq | -0.031 | 0.63 | -0.024 | 0.72 | -0.063 |
| tulu3-70b-dpo-fp8dyn | -0.018 | 0.78 | -0.016 | 0.81 | +0.045 |
| tulu3-70b-rlvr-awq | +0.029 | 0.66 | -0.012 | 0.85 | +0.112 |
| tulu3-70b-rlvr-awq-bf16act | +0.006 | 0.93 | +0.016 | 0.81 | -0.043 |
| tulu3-70b-rlvr-awq-r2 | +0.026 | 0.69 | +0.026 | 0.7 | -0.074 |
| tulu3-70b-rlvr-fp8dyn | +0.082 | 0.21 | +0.091 | 0.17 | -0.033 |
| tulu3-70b-rlvr-fp8dyn-r2 | -0.051 | 0.43 | -0.054 | 0.42 | -0.017 |
| tulu3-70b-sft-fp8dyn | +0.005 | 0.94 | +0.027 | 0.69 | -0.075 |

**48 rows:** median rho(h_t,S_T) = +0.016; positive with p<0.05 on 5/48; outside the crisis set: median +0.012, positive with p<0.05 on 4/48.

## Spatial: pandemic association of the region name

| region | n | share of windows with pandemic vocabulary |
|---|---|---|
| nyc | 200 | 0.040 |
| milan | 200 | 0.030 |
| london | 200 | 0.020 |
| madrid | 200 | 0.020 |
| tokyo | 200 | 0.070 |
| melbourne | 200 | 0.045 |
| sydney | 200 | 0.035 |
| delhi | 200 | 0.045 |
| hongkong | 200 | 0.055 |
| singapore | 200 | 0.045 |

deepseek-v4-flash: rho(pandemic association, LAP recall) = -0.44 (p=0.20); rho(., LAP hit) = +0.29 (p=0.41); n=10

gemini-2.5-flash-pooled: rho(pandemic association, LAP recall) = +0.28 (p=0.43); rho(., LAP hit) = +0.56 (p=0.10); n=10
