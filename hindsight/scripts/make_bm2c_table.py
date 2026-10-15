#!/usr/bin/env python
"""BM-2c ladder table (paper 2): one row per rung, regenerated from the frozen
row jsons — no hand-typed numbers.

Reads   outputs/bench/<key>/<key>_row.json          (analyze_bench_row.py, unchanged)
        outputs/bench/<key>/lap_probe_results.jsonl  (answer distribution -> LAP flags)
        outputs/bench/<key>/hf_revision.json         (weights sha, when present)
Writes  outputs/bench/BM2C_ROWS.md                          (whole file)
        paper2/latex/sections/tab_bm2c_ladder.tex            (rows between markers;
                                                             the table shell + caption
                                                             are hand-maintained)
Usage:  make_bm2c_table.py [--check]     --check = fail if any file would change.

Display rules (all derived from data, none hand-flagged):
  * = 95% date-level bootstrap CI excludes zero (E2/E3).
  k = sample-parity gate (paper 1 E.12) voids the contrast.
  g = recall hit rate at or below the panel's 65.5% positive-day base rate:
      cutoff undefined (same convention as the leaderboard's Llama 3.2 rows).
  u = LAP answers degenerate (>99% one direction): pre/post shares carry no
      information; the guided regime's schema admits up/down/unknown, so a
      constant answer is the model's, not the grammar's.
Missing rungs print a placeholder line and never fail the check.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from analyze_bm2c import CONTROL_C, CONTROL_D, CONTROL_E, LADDER_A, LADDER_B, PANEL_F, CONTROL_H, CONTROL_I, ci_excludes_zero  # noqa: E402
from analyze_fm1 import all_dates, build_covariates  # noqa: E402
from analyze_wholepanel import g2, WINDOW_END, MIN_DATES, T_CRIT  # noqa: E402
from hindsight_paths import REPO  # noqa: E402
from make_bench_rows import EMDASH, pct, texify  # noqa: E402

BENCH = REPO / "hindsight/outputs/bench"
MD = BENCH / "BM2C_ROWS.md"
TEX = REPO / "hindsight/paper2/latex/sections/tab_bm2c_ladder.tex"
TEX_B = "% BEGIN GENERATED ROWS (make_bm2c_table.py — do not hand-edit)"
TEX_E = "% END GENERATED ROWS"
BASE_RATE = 0.655  # panel positive-day base rate (paper 1 §3.2)
EXPECTED_CELLS = 258 * 4  # full tier, 1 rep

# (corpus cutoff, post-training recipe date) per lineage — from the model cards /
# HF repo creation dates; display metadata only, no number depends on it.
LINEAGE = {
    "olmo3-7b": ("2024-12", "2025-11"), "olmo3-32b": ("2024-12", "2025-11"),
    "olmo3.1-32b": ("2024-12", "2025-12"),
    "llama-3.3-70b-awq": ("2023-12", "2024-12"), "llama-3.1-70b-awq": ("2023-12", "2024-07"),
    "llama-3.3-70b-fp8dyn": ("2023-12", "2024-12"), "llama-3.1-70b-fp8dyn": ("2023-12", "2024-07"),
    # Qwen does not disclose a corpus cutoff; "2024-04*" is row 15's measured LAP cutoff (addendum D)
    "qwen3-30b-a3b-instruct-2507": ("2024-04*", "2025-07"), "qwen3-30b-a3b-thinking-2507": ("2024-04*", "2025-07"),
    "qwen3-30b-a3b-fp8dyn": ("2024-04*", "2025-04"),
    "llama-3.1-nemotron-70b-awq": ("2023-12", "2024-10"),
    # addendum F: Tulu 3 (2024-11), R1-Distill (2025-01, on Llama 3.3), Hermes 3 (2024-08)
    "tulu3-70b": ("2023-12", "2024-11"), "r1-distill-llama-70b-awq": ("2023-12", "2025-01"), "hermes3-70b-fp8": ("2023-12", "2024-08"),
}


# Serving tier and box per row (display metadata, verified 2026-09-23 against the ladder driver's QUANT
# flags, prereg/BM2c_note_F_serving.md (A100 rungs) and the H800 run history; the H800 FP8 path is W8A8,
# the A100 one Marlin W8A16 -- different tiers). Rows are comparable only within a tier (paper 2 sec. 7.1).
# Activation dtype is shown for AWQ rows: every AWQ row outside addendum I was served --dtype float16
# (ladder driver QUANT=awq; H800 control C/E1 per BM2c_note_E1_inspection.md), and addendum I reading 7
# (DTYPE) fired, so those rows are dtype-confounded. I4/I6 ran at TP=2 (BM2c_note_I_deviation_tp.md).
SERVING = {
    "olmo3": "BF16 / H800", "llama-3.3-70b-awq": "AWQ-4 fp16-act / H800", "llama-3.1-70b-awq": "AWQ-4 fp16-act / H800",
    "qwen3-30b-a3b-instruct-2507-fp8dyn": "FP8 W8A8 / H800", "qwen3-30b-a3b-thinking-2507-fp8dyn": "FP8 W8A8 / H800",
    "qwen3-30b-a3b-fp8dyn": "FP8 W8A8 / H800", "llama-3.1-nemotron-70b-awq": "AWQ-4 fp16-act / H800",
    "tulu3-70b-sft-fp8dyn": "FP8 W8A16 / A100", "tulu3-70b-dpo-fp8dyn": "FP8 W8A16 / A100",
    "tulu3-70b-rlvr-fp8dyn": "FP8 W8A16 / A100", "r1-distill-llama-70b-awq": "AWQ-4 fp16-act / A100",
    "hermes3-70b-fp8": "FP8 W8A16 / A100", "tulu3-70b-rlvr-awq": "AWQ-4 fp16-act / A100",
    "llama-3.3-70b-fp8dyn": "FP8 W8A16 / A100", "llama-3.1-70b-fp8dyn": "FP8 W8A16 / A100",
    "qwen3-30b-a3b-thinking-2507-bf16-fp16act": "BF16 w, FP16 act / A100",
    "qwen3-30b-a3b-thinking-2507-bf16": "BF16 / A100", "qwen3-30b-a3b-thinking-2507-awq": "AWQ-4 bf16-act / A100",
    "qwen3-30b-a3b-thinking-2507-gptq-w4a16": "GPTQ-4 w4a16 / A100, TP=2", "qwen3-30b-a3b-thinking-2507-int8-w8a8": "INT8 W8A8 / A100",
    "qwen3-30b-a3b-thinking-2507-fp8block": "FP8 block / A100, TP=2",
}
# shorter table labels where analyze_bm2c's label carries serving text now shown in the Serving column
TEX_LABEL = {
    "A0": "base (pretrain + midtrain + long context)",
    "T1": "Tulu 3 70B SFT (Ai2, on the Llama 3.1 70B base)", "F1": "R1-Distill-Llama-70B (reasoning SFT on Llama 3.3 Instruct)",
    "F2": "Hermes 3 70B (Nous SFT+DPO on the base)", "F3": "Tulu 3 70B RLVR = T3, AWQ tier",
    "H1": "Llama 3.3 70B Instruct = C, FP8 tier", "H2": "Llama 3.1 70B Instruct = C-ref, FP8 tier",
}
_COV = None


def serving(key: str) -> str:
    if key in SERVING:
        return SERVING[key]
    for pfx, v in SERVING.items():
        if key.startswith(pfx):
            return v
    raise KeyError(key)


def cell_g2(key: str, md: bool) -> str:
    """addendum G whole-panel t (HAC 6); bold = |t| >= 1.96 (either sign, as for E2/E3)."""
    global _COV
    if _COV is None:
        _COV = build_covariates([d for d in all_dates() if d <= WINDOW_END])
    g = g2(key, _COV)
    if g["n_dates"] < MIN_DATES:
        return "—ᶜ" if md else r"---\textsuperscript{c}"
    v = f"{g['t']:+.2f}"
    if not md:
        v = v.replace("-", "$-$")  # keep the leading zero: a t statistic, not a share
    if abs(g["t"]) >= T_CRIT:
        return f"**{v}**" if md else rf"\textbf{{{v}}}"
    return v


def lineage(key: str) -> tuple[str, str]:
    for pfx, v in LINEAGE.items():
        if key.startswith(pfx):
            return v
    raise KeyError(key)


def load(key: str) -> dict | None:
    f = BENCH / key / f"{key}_row.json"
    if not f.exists():
        return None
    r = json.loads(f.read_text())
    ans = collections.Counter()
    lp = BENCH / key / "lap_probe_results.jsonl"
    if lp.exists():
        for line in lp.read_text().splitlines():
            if line.strip():
                ans[json.loads(line)["answer"]] += 1
    n = sum(ans.values())
    directional = {a: c for a, c in ans.items() if a in ("up", "down")}
    r["_lap_degenerate"] = bool(n) and max(directional.values(), default=0) / n > 0.99
    r["_lap_unknown_share"] = ans.get("unknown", 0) / n if n else None
    rev = BENCH / key / "hf_revision.json"
    r["_sha"] = json.loads(rev.read_text()).get("hf_commit_sha", "")[:7] if rev.exists() else ""
    return r


def est_ci(e: dict, md: bool) -> str:
    if e.get("gated"):
        return "—ᵏ" if md else r"---\textsuperscript{k}"
    s = f"{e['est']:+.3f} [{e['ci95'][0]:.2f},{e['ci95'][1]:.2f}]"
    star = ci_excludes_zero(e)
    if md:
        return f"**{s}**" if star else s
    est, ci = s.split(" ", 1)
    est = texify(est)
    if star:
        est = rf"\textbf{{{est}}}"
    return f"{est} {texify(ci)}"


def cell_p1(r: dict, md: bool) -> str:
    d = r.get("P1_placebo_detail") or {}
    if d.get("gated"):
        return "—ᵏ" if md else r"---\textsuperscript{k}"
    v = f"{r['P1_placebo_postcutoff']:+.3f}"
    return v if md else texify(v)


def cell_rec(r: dict, md: bool) -> str:
    rec = r.get("REC") or {}
    if not (rec.get("pre") or {}).get("n") and not (rec.get("post") or {}).get("n"):
        return "-/-ⁿ" if md else r"---\textsuperscript{n}"  # probe not run (leaderboard convention)
    f = (lambda v: EMDASH if v is None else f"{pct(v)}%") if md else \
        (lambda v: "---" if v is None else f"{pct(v)}\\%")
    return f"{f((rec.get('pre') or {}).get('year'))}/{f((rec.get('post') or {}).get('year'))}"


def cell_lap(r: dict, md: bool) -> tuple[str, str]:
    lap = r["LAP"]
    hit = lap["recall_hit_rate"]
    chance = hit is not None and hit <= BASE_RATE
    pre, post = f"{lap['pre_mean']:.3f}", f"{lap['post_mean']:.3f}"
    if not md:  # leaderboard convention: .702/.667
        pre, post = texify(pre), texify(post)
    h = f"{pct(hit)}%" if md else f"{pct(hit)}\\%"
    s = f"{pre}/{post} ({h})"
    sup = ("u" if r["_lap_degenerate"] else "") + ("g" if chance else "")
    if sup:
        s += ("".join({"u": "ᵘ", "g": "ᵍ"}[c] for c in sup)) if md else rf"\textsuperscript{{{sup}}}"
    if chance:
        cut = "—ᵍ" if md else r"---\textsuperscript{g}"
    else:
        cut = str(lap["empirical_cutoff"])
    return s, cut


def row(rung: str, key: str, label: str, regime: str, md: bool) -> str:
    r = load(key)
    corpus, recipe = lineage(key)
    if r is None:
        return (f"| {rung} | {label} | {regime} | {serving(key)} | {corpus} | {recipe} | (no row yet) |" + " |" * 8) if md else \
               [rung, label, regime, serving(key), corpus, recipe] + ["(no row yet)"] + [""] * 8
    lap_s, cut = cell_lap(r, md)
    valid = f"{pct(r['VALID']['sketch_rate'])}%" if md else f"{pct(r['VALID']['sketch_rate'])}\\%"
    # sketch_rate is computed over cells that exist; cells lost to transport errors
    # (no file at all) are shown as coverage so a 100% never hides an incomplete matrix
    if r["VALID"]["cells"] < EXPECTED_CELLS:
        valid += f" ({r['VALID']['cells']}/{EXPECTED_CELLS})"
    if not md:
        label = TEX_LABEL.get(rung, label)
    cells = [rung, label, regime, serving(key), corpus, recipe,
             est_ci(r["E2_date_trigger"], md), cell_g2(key, md), est_ci(r["E3_transplant"], md), cell_p1(r, md),
             cell_rec(r, md), lap_s, cut, valid]
    if not md:  # 14: recall hit rate alone, for the body table
        hit = r["LAP"]["recall_hit_rate"]
        hit_s = f"{pct(hit)}\\%" + ("" if hit is None or hit > BASE_RATE else r"\textsuperscript{g}")
        cells.append(hit_s)
    if md:
        cells.append(r["_sha"] or "—")
        return "| " + " | ".join(cells) + " |"
    cells[1] = cells[1].replace("+", "$+$")
    return cells


def md_doc() -> str:
    hdr = "| Rung | Model / stage | Regime | Serving | Corpus | Recipe | E2 | G2 t | E3 | P1 | REC pre/post | LAP pre/post (hit) | Cutoff | VALID | sha |\n" \
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    out = ["# BM-2c ladder rows (generated by make_bm2c_table.py — do not hand-edit)", "",
           "E2/E3: bearish-share contrasts, 95% date-level bootstrap; **bold** = CI excludes zero. "
           "ᵏ sample-parity gate; ᵍ recall hit rate ≤ 65.5% base rate (cutoff undefined); "
           "ᵘ LAP answers >99% one direction (shares uninformative); ⁿ recovery probe not run. Corpus = pretraining cutoff, "
           "Recipe = post-training release (display metadata). G2 t = addendum-G whole-panel t (HAC 6), **bold** = |t| >= 1.96; "
           "ᶜ fewer than 200 window dates. Serving = weight/activation precision and box: rows are comparable only within a tier.", ""]
    for title, ladder in (("Ladder A — Olmo 3 7B", LADDER_A), ("Ladder B — Olmo 3(.1) 32B", LADDER_B),
                          ("Control C — Llama 70B, fixed corpus", CONTROL_C),
                          ("Control D — Qwen3-30B-A3B → 2507 recipe", CONTROL_D),
                          ("Control E — one RLHF stage on Llama 3.1 70B Instruct", CONTROL_E),
                          ("Addendum F — Tülu-3 stage ladder and recipe panel on the Llama 3.1 70B base", PANEL_F),
                          ("Control H — control C re-measured in the FP8 tier", CONTROL_H),
                          ("Control I — precision dose-response, one checkpoint, one box (addendum I)", CONTROL_I)):
        out += [f"## {title}", "", hdr] + [row(*x, md=True) for x in ladder] + [""]
    return "\n".join(out)


# Column indices into the 14-cell row: 0 Rung, 1 Model/stage, 2 Regime, 3 Serving,
# 4 Corpus, 5 Recipe, 6 E2, 7 G2 t, 8 E3, 9 P1, 10 REC, 11 LAP (hit), 12 Cutoff, 13 VALID.
COLS_BODY = [0, 1, 3, 4, 5, 6, 7, 14, 12]
COLS_FULL = list(range(14))
BLOCKS = (("Ladder A: Olmo 3 7B", LADDER_A), ("Ladder B: Olmo 3(.1) 32B", LADDER_B),
          ("Control C: Llama 70B, one corpus, two recipes", CONTROL_C),
          ("Control D: Qwen3-30B-A3B, 2025-04 vs 2025-07 recipe", CONTROL_D),
          ("Control E: one RLHF stage on Llama 3.1 70B Instruct", CONTROL_E),
          (r'Panel F: T\"ulu-3 stages and other recipes on the Llama 3.1 70B base', PANEL_F),
          ("Control H: control C in the FP8 tier", CONTROL_H),
          ("Control I: one checkpoint, seven serving configurations, one A100 box", CONTROL_I))
BLOCKS_BODY = BLOCKS[:-1]
BLOCKS_DOSE = BLOCKS[-1:]


def tex_rows(cols=COLS_FULL, blocks=BLOCKS) -> str:
    parts = []
    for title, ladder in blocks:
        if not any(load(k) is not None for _, k, _, _ in ladder):
            continue  # a block with no finished row stays out of the paper table
        parts.append(rf"\multicolumn{{{len(cols)}}}{{@{{}}l}}{{\emph{{{title}}}}} \\")
        for x in ladder:
            cells = row(*x, md=False)
            parts.append(" & ".join(cells[c] for c in cols) + r" \\")
        parts.append(r"\addlinespace")
    return "\n".join(parts[:-1])


TEX_DOSE = REPO / "hindsight/paper2/latex/sections/tab_bm2c_dose.tex"
TEX_FULL = REPO / "hindsight/paper2/latex/sections/tab_bm2c_full.tex"
HDR_BODY = r"Rung & Model / stage & Serving & Corpus & Recipe & E2 & G2 $t$ & Hit & Cutoff \\"
HDR_FULL = r"Rung & Model / stage & Regime & Serving & Corpus & Recipe & E2 & G2 $t$ & E3 & P1 & REC pre/post & LAP pre/post (hit) & Cutoff & VALID \\"

SHELL_DOSE = r"""% BM-2c dose-response rows (Control I). Rows between the markers are regenerated by
% scripts/make_bm2c_table.py; the shell and caption are hand-maintained.
\begin{table}[tbp]
\centering
\footnotesize
\setlength{\tabcolsep}{4pt}
\resizebox{\linewidth}{!}{%
\begin{tabular}{@{}lllllllll@{}}
\toprule
""" + HDR_BODY + """
\midrule
""" + TEX_B + "\n" + TEX_E + r"""
\bottomrule
\end{tabular}}
\caption{Seven serving configurations of Qwen3-30B-A3B-Thinking-2507 on one 4$\times$A100 box (\S\ref{sec:quant}); columns as in Table~\ref{tab:bm2c}, full columns in Table~\ref{tab:bm2cfull}. I4 and I6 ran at tensor parallelism 2, the other rows at 4.}
\label{tab:bm2cdose}
\end{table}
"""

SHELL_FULL = r"""% BM-2c full ladder (all columns). Rows between the markers are regenerated by
% scripts/make_bm2c_table.py; the shell and caption are hand-maintained.
\begin{sidewaystable}
\centering
\scriptsize
\setlength{\tabcolsep}{3pt}
\resizebox{\linewidth}{!}{%
\begin{tabular}{@{}llllllllllllll@{}}
\toprule
""" + HDR_FULL + """
\midrule
""" + TEX_B + "\n" + TEX_E + r"""
\bottomrule
\end{tabular}}
\caption{Every post-training ladder row with every column (Tables~\ref{tab:bm2c} and \ref{tab:bm2cdose} show the subset the text reads). E2/E3 as in Table~\ref{tab:rows} (95\% date-level bootstrap; bold = CI excludes zero, either sign). G2 $t$ = whole-panel estimand (HAC(6); bold = $|t| \geq 1.96$). Serving = weight/activation precision and machine. \textsuperscript{k}~sample-parity gate; \textsuperscript{g}~recall hit rate at or below the 65.5\% base rate, cutoff undefined; \textsuperscript{u}~LAP answers $>$99\% one direction; \textsuperscript{n}~recovery probe not run.}
\label{tab:bm2cfull}
\end{sidewaystable}
"""


TEX_SHELL = r"""% BM-2c ladder table. Rows between the markers are regenerated by
% scripts/make_bm2c_table.py; the shell and caption are hand-maintained.
\begin{sidewaystable}
\centering
\scriptsize
\setlength{\tabcolsep}{3pt}
\resizebox{\linewidth}{!}{%
\begin{tabular}{@{}llllllllllllll@{}}
\toprule
Rung & Model / stage & Regime & Serving & Corpus & Recipe & E2 & G2 $t$ & E3 & P1 & REC pre/post & LAP pre/post (hit) & Cutoff & VALID \\
\midrule
""" + TEX_B + "\n" + TEX_E + r"""
\bottomrule
\end{tabular}}
\caption{CAPTION TBD (hand-maintained). \textsuperscript{k}~sample-parity gate; \textsuperscript{g}~recall hit rate at or below the 65.5\% base rate, cutoff undefined; \textsuperscript{u}~LAP answers $>$99\% one direction; \textsuperscript{n}~recovery probe not run.}
\label{tab:bm2c}
\end{sidewaystable}
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    drift = []
    new_md = md_doc()
    if (MD.read_text() if MD.exists() else None) != new_md:
        drift.append(MD.name)
        if not args.check:
            MD.write_text(new_md)
    for path, default_shell, cols, blocks in ((TEX, TEX_SHELL, COLS_BODY, BLOCKS_BODY),
                                             (TEX_DOSE, SHELL_DOSE, COLS_BODY, BLOCKS_DOSE),
                                             (TEX_FULL, SHELL_FULL, COLS_FULL, BLOCKS)):
        shell = path.read_text() if path.exists() else default_shell
        b, e = shell.index(TEX_B) + len(TEX_B), shell.index(TEX_E)
        new_tex = shell[:b] + "\n" + tex_rows(cols, blocks) + "\n" + shell[e:]
        if new_tex != (path.read_text() if path.exists() else None):
            drift.append(path.name)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(new_tex)
    if args.check:
        if drift:
            sys.exit(f"CHECK FAIL: would rewrite {drift}")
        print("check OK: BM-2c table matches the frozen row jsons")
    else:
        print(f"wrote {len(drift)} changed file(s): {drift or 'none'}")


if __name__ == "__main__":
    main()
