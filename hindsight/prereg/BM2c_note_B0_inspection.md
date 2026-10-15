# BM-2c note: post-hoc manual inspection of the B0 smoke cells (2026-09-14 10:40)

Per `BM2c_note_unattended.md`, B0 (Olmo-3-1125-32B base, guided zero-shot
completion, output dir `olmo3-32b-base-guided`) was pre-screened automatically
(8/8 smoke cells schema-valid, gate >= 6) and its full run started at 10:34
unattended. This is the manual inspection of the archived smoke cells, done
before any number from the rung is used.

Addendum degeneracy gate (`BM2c_addendum_base_guided.md` 17f9c668):
- distinct direction patterns across the 8 cells: **5** (gate >= 5) — passes at the bound;
- cells with bearish count != 4/8: **7** (gate >= 1).
Patterns: R `----++++`, `--------`; D `++++++++`, `++++++++`; M `-+---++-`, `-+---+--`;
W `++++++++`, `++++++++`. All 8 cells 8 valid / 0 invalid sketches. Content is
on-task (macro mechanisms over the eight admissible proxies; no exemplar exists
under this regime, so no copying is possible).

**Observation not covered by any preregistered gate (disclosed, not acted on):**
the base model repeats one sketch within a cell. Unique mechanism narratives per
cell: R 8/8 and 4/8; D 1/8 and 1/8; M 7/8 and 8/8; W 1/8 and 1/8. The same
pathology exists on the finished A0 row (7B base, 1,032 cells: mean unique share
0.45; 164 cells with <= 2 unique sketches) and is absent on every instruct rung
and on Llama 3.3 (unique share 1.00). Consequence: a base cell's bearish share is
often a single draw rather than eight, so base-row estimates are coarser per
date; the date-level bootstrap remains valid, and E2/E3 are reported as measured
with this disclosed. Whether the repetition is arm-dependent is checked on the A0
full run (same session) and reported alongside.

Verdict: the preregistered gate passes; the run continues; the repetition is a
disclosed limitation of the base-regime rows, not a discard criterion.

Addendum (10:42, A0 full run, 258 dates x 4 arms): unique-narrative share is
arm-independent on the 7B base — R 0.44, D 0.46, M 0.45, W 0.44; no 7B cell is
fully repeated (1/8 unique), against 4 of 8 on the 32B smoke cells, so the 32B
base repeats more than the 7B base. Bearish share sits at exactly 0 or 1 in
26-34% of 7B base cells across arms (instruct-guided: 0%). Because the
repetition does not differ by arm, it adds noise to the base-row contrasts
without a directional bias between D and M; reported as such.
