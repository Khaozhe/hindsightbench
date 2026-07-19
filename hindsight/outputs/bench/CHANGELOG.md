# Leaderboard changelog (corrections that changed a published cell)

Per the maintenance protocol (paper 2 §8): corrections regenerate all derived
tables via `make_bench_rows.py` (drift-gated) and are logged here with a date.

## 2026-07-19 — Llama 3.2 1B REC post-cutoff cell: 0% → unmeasured (—)

The REC n ≥ 10 convergence gate (added to `analyze_bench_row.py` 2026-07-07
for the Kimi-K2.6 non-convergence case) post-dated the frozen 1B row JSON,
which was never re-derived. The 1B probe yields 0 convergent pre-cutoff and
1 convergent post-cutoff answer; the frozen row carried `post.year = 0.0`
(n = 1) and the table printed `---/0%`, violating the stated gate — a 0%
rate from a single answer is an artifact, not a measurement. Re-running
`analyze_bench_row.py --model llama3.2:1b` under the frozen code changed
exactly three fields (`REC.post.{year,ym,med_off}` → null); E2, E3, P1,
LAP, δ, and VALID are byte-identical. Cell now renders `---/---`.
