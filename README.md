# HindsightBench

A black-box behavioral audit protocol for **parametric hindsight** in
time-indexed LLM decision tasks. One audit row per model: date-trigger
strength (E2), transplantation effect (E3), post-cutoff placebo (P1), date
recoverability (REC), outcome-recall propensity with the behaviorally
effective knowledge cutoff (LAP), recall–accuracy dissociation (δ), and
schema compliance (VALID) — each with identifiability gates. Probe-level
cost: a full audit row for a mid-tier commercial model runs $19–30 at 2026
list prices. Protocol frozen by hash before any non-development model was
called (`hindsight/prereg/BM1_prereg.md`, sha256 `fbcdffc1…`; English
companion `BM1_prereg_EN.md`; the two legacy Gemini rows derive from the
pre-freeze core experiments that seeded the protocol, as noted below).

**Papers.** Protocol/benchmark paper: *HindsightBench: A Black-Box
Behavioral Audit Protocol for Parametric Hindsight in Time-Indexed LLM
Decision Tasks* (arXiv:2607.18867, https://arxiv.org/abs/2607.18867). The companion
findings paper is under double-blind review and is not distributed from
this repository.

## Repository layout

```
hindsight/
  models.yaml            runner registry (provider / tier / sampling / quantization)
  run_bench.sh           top-level driver: model key -> audit row -> leaderboard
  scripts/               runners, probes, analyzers, table/figure generators
    hindsight_paths.py   repo-root autodetect ($HINDSIGHT_ROOT overrides)
    bench_registry.py    display metadata (names, generation, disclosure marks)
  prereg/                16 hash-frozen preregistrations + freeze manifests
  outputs/bench/<key>/   per-model transcripts, probe results, <key>_row.json
  outputs/*.jsonl        per-call usage ledgers (cost attribution)
macrochain/data/processed/   vintage-correct panel inputs (decision nodes,
                             prompts, conservative direction labels)
```

## Quickstart — regenerate everything (no API calls)

Python ≥ 3.11 with `hindsight/requirements.txt` (pinned to the environment
that produced the frozen rows).

```bash
python hindsight/scripts/make_bench_rows.py --check   # leaderboard drift gate
python hindsight/scripts/make_figures.py              # figures from frozen outputs
python hindsight/scripts/make_cost_table.py           # cost table from ledgers
python hindsight/scripts/analyze_bench_row.py --model <key>   # re-derive any row
```

Every published number regenerates from the frozen per-model row JSONs;
`--check` fails if any table drifts. Verify any preregistration against its
freeze manifest: `shasum -a 256 hindsight/prereg/<doc>.md`.

## Auditing a new model

1. Add an entry to `hindsight/models.yaml` (provider must exist in
   `hindsight/scripts/llm_adapters.py`; keys live in gitignored
   `<Vendor>_API_KEY.env` files at the repo root).
2. `hindsight/run_bench.sh <key> smoke` — then **manually inspect** the
   2-date output (preregistration gate).
3. `hindsight/run_bench.sh <key> all` — arms → probes → row JSON → tables.
4. Add display metadata to `hindsight/scripts/bench_registry.py`.

**Operational requirements** (measured, not folklore — paper §7): pin the
serving quantization (E2 broke mutual-CI stability under BF16 vs the FP8
reference; AWQ-INT4 held), pin the thinking regime (one vendor's locked
reasoning makes the REC probe non-convergent), disable and record
retrieval/tools (all fifteen rows are plain completions), report the parser
version, and give batch runs independent output-budget headroom.

## Notes

- Gemini rows are legacy: their arm cells symlink (relative links) into
  `hindsight/outputs/fm1/`, the core experiments that seeded the protocol;
  not re-runnable via the driver. Anthropic rows use a dedicated runner.
- `outputs/bench/qwen3.6-27b-{bf16,awq}/` are quantization-sensitivity
  tiers (no row JSON by design; see `analyze_bm2a.py`).
- Cost ledger and its explicit gap list: `hindsight/outputs/COST_TABLE.md`.

## Citation

```bibtex
@misc{jia2026hindsightbench,
  title  = {HindsightBench: A Black-Box Behavioral Audit Protocol for
            Parametric Hindsight in Time-Indexed LLM Decision Tasks},
  author = {Jia, Haozhe},
  year   = {2026},
  note   = {arXiv:2607.18867}
}
```

Code: MIT (`hindsight/LICENSE`). Panel: derived from public-domain U.S.
federal statistical releases (ALFRED vintages); market-derived labels
released in conservative aggregate form.
