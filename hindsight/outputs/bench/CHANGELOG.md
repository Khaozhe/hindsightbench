# Leaderboard changelog (corrections that changed a published cell)

Per the maintenance protocol (paper 2 §8): corrections regenerate all derived
tables via `make_bench_rows.py` (drift-gated) and are logged here with a date.

## 2026-07-26/27 — Llama 3.2 3B E2/E3/placebo and 1B E3: estimates → unidentified (---^k)

A sample-parity audit of all four arms found that under partial schema
compliance the two sides of a contrast return usable generations on
*different* dates, so the surviving intersection is selected by attrition
rather than by design. `analyze_bench_row.py` now reports a contrast only
when both sides cover the full preregistered windows. Four cells change:
Llama 3.2 3B (52% compliance) E2, E3 and the post-cutoff placebo, and
Llama 3.2 1B (79%) E3. Superseded values, kept in paper 1's E.12 with their
date-matched counterparts: 1B E3 `-.160 [-.35, +.01]`; the 3B cells are
printed there too, including the fact that date-matching 3B's E2 yields a
significantly *positive* estimate, i.e. the correction runs against the
companion paper's claim. No other cell moves, on any metric. The scope claim
these cells supported is narrowed from "the 2024 generation from 1B to 70B"
to the rows where the effect is measurable. Commits `41baa34e` (E2),
`09797c04` (E3), `cc7bb920` (placebo + attrition re-grounding).

## 2026-07-21 — GPT-5.5 delta cell: +.065 (t = 2.96) → undefined (---^v)

The detection regression needs genuine LAP variation: with LAP (near-)saturated
the interaction column is collinear with the signal column and the fit is
degenerate. `analyze_bench_row.py` gained a variance gate (LAP variance
<= 1e-4 on the regression's estimation dates) after this row was frozen. On
GPT-5.5's 152 estimation dates LAP is exactly saturated -- the one
sub-saturation month is excluded by the regression's own sample rule -- so the
gated pipeline voids the cell. Disclosed as a post-freeze correction rather
than silently regenerated. Commit `bdc38c63`.

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
