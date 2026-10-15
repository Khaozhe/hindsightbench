# BM-2c note: transport failure on the 32B rungs and the correction (2026-09-14 12:20)

B0 (Olmo-3-1125-32B base, guided) finished its matrix with 932 of 1,024 cells
written and **92 cells lost to client-side timeouts** (runner counts
`{'OK': 932, 'PARSE_ERR': 0, 'ERR': 92}`; the exception text is empty, which is
httpx's ReadTimeout). Cause, from the vLLM log: at `--max-model-len 24576` and
92% memory utilisation the 32B BF16 weights leave ~9 GB of KV cache, so the
server runs only 12-15 requests and queues the rest of the client's 32 in-flight
requests (`Running: 12-15, Waiting: 17-20`, KV usage 98-99%); aggregate
generation throughput was 266 tok/s, so a queued 8,192-token generation can
exceed the 900 s client timeout. No model output was discarded: the lost cells
have no file at all, and the sample-parity gate voids B0's E2/E3 on the partial
matrix (D and M cover different dates), as it should.

Correction (transport only; prompts, sampling, weights, dtype and max_tokens
unchanged):
1. client timeout for arm generations 900 s -> 3,600 s in both runners
   (`run_bm2b_stage2.py`, `run_bench_model.py`);
2. client concurrency for the 32B rungs 32 -> 16 (`CONC=16`), matching what the
   server actually runs, so requests do not wait in the server queue.
3. B0 gets the standard idempotent resume for interrupted runs (regenerate only
   the 92 missing cells, re-run the row) after B1-B3x, since its weights were
   deleted at rung end and must be re-downloaded (61 GB). This is the BM-1
   interrupted-run mechanism, not the parse-failure resume pass of
   `BM2c_note_retry.md`; both are one pass.

B1 was stopped after its 8 smoke cells (2 dates x 4 arms, written under the
old transport without any timeout) and before its full matrix started; it
restarts under the corrected transport, so every B1 full-matrix cell is
generated under one configuration. Recorded before any B1 full-matrix cell
existed (12:30).
