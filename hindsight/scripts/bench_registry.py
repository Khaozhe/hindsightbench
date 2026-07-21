#!/usr/bin/env python
"""Single source of model METADATA for the benchmark leaderboard and figures.

Numbers (E2/E3/P1/REC/LAP/delta/VALID) are never stored here — they are read
from outputs/bench/<key>/<key>_row.json and model_relative_placebo.json by the
consumers (make_bench_rows.py, make_figures.py). This module only records what
cannot be derived from data: display names, training-generation assignment,
vendor-claimed cutoffs, per-row disclosure marks, protocol tier, and figure
layout hints. Adding a benchmark row = one dict here + the row json on disk.

Mark semantics (md = BENCH_ROWS.md, tex = A4 table):
  gen_md        generation label in the md table ("2025†" = release-cadence call)
  name_sup      (md, tex) superscript on the model name (row-15 disclosure)
  p1            "calendar" | "model_relative" (read model_relative_placebo.json)
                | "absent" (post-cutoff arms not generated)
  rec           "probe" | "nonconvergent" (kimi: thinking never terminates)
                | "not_run" (row 15: cost decision)
  lap_at_chance hit rate ~ chance: cutoff and delta are undefined (md keeps the
                artifact values with a dagger; tex suppresses to ---^g)
  delta_gate    None | "lowvar" (LAP variance <= 1e-4, regression degenerate)
                | "weakid" (LAP ~ 1 everywhere, few identifying dates)
  e3_sparse     sparse-cell artifact flag of the reduced-window protocol
  valid_sup     (md, tex) superscript on VALID (parser-v2 recovery disclosure)
  bold          per-format emphasis: {"md": {...}, "tex": {...}} with cell names
                E2, E3 (whole cell md / estimate tex), delta, hit
  fig4_claim    vendor-reported cutoff "YYYY-MM" or None (undisclosed); fig4
                membership itself is derived (= not lap_at_chance)
  fig5          panel "open" (x = active params, B) | "api" (slot order)
"""

_D = dict


def _row(key, tex, gen, gen_md=None, name_sup=None, p1="calendar", rec="probe",
         lap_at_chance=False, delta_gate=None, e3_sparse=False, valid_sup=None,
         bold=None, fig4_claim=None, fig5=None):
    return _D(key=key, tex=tex, gen=gen, gen_md=gen_md or str(gen),
              name_sup=name_sup, p1=p1, rec=rec, lap_at_chance=lap_at_chance,
              delta_gate=delta_gate, e3_sparse=e3_sparse, valid_sup=valid_sup,
              bold=bold or {}, fig4_claim=fig4_claim, fig5=fig5)


# Benchmark-table order (by training generation, frozen presentation order).
MODELS = [
    # delta_gate 2026-07-21: "weakid" -> "lowvar". The frozen 07-03 row predated
    # the 07-07 variance gate; regeneration under the gated pipeline voids delta
    # (var(LAP)==0 exactly on the 152-date estimation sample — the one sub-1.0
    # LAP month is excluded by net==0, so the interaction is perfectly collinear).
    _row("gpt-5.5", "GPT-5.5", 2026, p1="model_relative", delta_gate="lowvar",
         fig4_claim="2025-12", fig5=_D(panel="api", slot=4, label="GPT-5.5")),
    _row("claude-sonnet-5", "Claude Sonnet 5", 2026, p1="model_relative",
         delta_gate="lowvar", valid_sup=("◊◊", "p"),
         fig4_claim="2026-01", fig5=_D(panel="api", slot=7, label="Sonnet 5")),
    _row("kimi-k2.6", "Kimi-K2.6", 2026, p1="model_relative",
         rec="nonconvergent",
         fig4_claim=None, fig5=_D(panel="api", slot=5, label="Kimi-K2.6")),
    _row("qwen3.6-35b-a3b-fp8", "Qwen3.6-35B-A3B", 2026,
         fig4_claim=None,
         fig5=_D(panel="open", x=3.9, label="35B-A3B\n(3B act.)")),
    _row("qwen3.6-27b-fp8", "Qwen3.6-27B", 2026,
         fig4_claim=None, fig5=_D(panel="open", x=27, label="27B")),
    _row("gpt-5.4-mini", "GPT-5.4-mini", 2026, p1="model_relative",
         delta_gate="lowvar", valid_sup=(None, "p"),
         fig4_claim="2025-08", fig5=_D(panel="api", slot=3, label="GPT-5.4-mini")),
    _row("claude-haiku-4-5", "Claude Haiku 4.5", 2025,
         bold={"md": {"E3"}, "tex": {"E3"}},
         fig4_claim="2025-02", fig5=_D(panel="api", slot=6, label="Haiku 4.5")),
    _row("deepseek-v4-flash", "DeepSeek v4-flash", 2025, gen_md="2025†",
         p1="model_relative",
         fig4_claim=None, fig5=_D(panel="api", slot=2, label="DeepSeek")),
    _row("gemini-2.5-flash", "Gemini 2.5 Flash", 2025, gen_md="2025†",
         bold={"md": {"delta"}, "tex": {"delta"}},
         fig4_claim="2025-01", fig5=_D(panel="api", slot=0, label="Gemini Flash")),
    _row("gemini-2.5-pro", "Gemini 2.5 Pro", 2025, gen_md="2025†", p1="absent",
         fig4_claim="2025-01", fig5=_D(panel="api", slot=1, label="Gemini Pro")),
    _row("qwen3-30b-a3b-fp8dyn", "Qwen3-30B-A3B", 2025, name_sup=("ⁿ", "n"),
         bold={"md": {"E2", "E3", "hit"}, "tex": set()},
         fig4_claim=None, fig5=_D(panel="open", x=3.2, label="30B-A3B")),
    _row("llama-3.1-70b-awq", "Llama 3.1 70B", 2024,
         bold={"md": {"hit"}, "tex": {"hit"}},
         fig4_claim="2023-12", fig5=_D(panel="open", x=70, label="70B")),
    _row("llama-3.1-8b", "Llama 3.1 8B", 2024, lap_at_chance=True,
         fig5=_D(panel="open", x=8, label="8B")),
    _row("llama3.2:3b", "Llama 3.2 3B", 2024, lap_at_chance=True, e3_sparse=True,
         fig5=_D(panel="open", x=2.7, label="3B")),
    _row("llama3.2:1b", "Llama 3.2 1B", 2024, lap_at_chance=True, e3_sparse=True,
         fig5=_D(panel="open", x=1, label="1B")),
]

BY_KEY = {m["key"]: m for m in MODELS}
