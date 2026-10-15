# BM-2c note: one resume pass for parse-failed cells (pre-run, 2026-09-14 02:55)

Rung A2 (Olmo-3-7B-Instruct-DPO) finished its single-rep matrix at 97% schema
compliance (34 of 1,032 cells malformed JSON); the parse-failed cells leave the
D/M and W keyings covering different dates, so the sample-parity gate (paper 1
E.12) voids E2 and E3. Before C starts, the chain re-runs A2's `full` phase once
under the identical serving configuration: the runner's idempotent resume
regenerates only cells without a valid-sketch file (parse-failed cells),
touching no completed cell. Cells that fail again stay failed and the gate
decides. This is the same mechanism every BM-1 row used for interrupted runs;
it is recorded here because it is being applied to a rung whose gated result
was already seen. The same rule applies to any later rung below 100%
compliance (one pass, no more).
