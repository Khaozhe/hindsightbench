#!/usr/bin/env python
"""Regenerate the benchmark leaderboard from frozen row jsons (no hand-typing).

Reads  outputs/bench/<key>/<key>_row.json            (six-metric row, frozen)
       outputs/bench/<key>/model_relative_placebo.json (P1 for ᴹ-marked rows)
       scripts/bench_registry.py                     (display metadata only)
Writes outputs/bench/BENCH_ROWS.md    — table block between BEGIN/END markers
       outputs/bench/bench_rows.csv   — full-precision export (paper-2 infra)
       paper/latex/sections/A4_appendix_benchmark.tex — rows between markers
       paper2/latex/sections/05_leaderboard.tex       — rows between markers
       (papers 1 and 2 carry the identical generated block by construction)

Prose (core patterns, notes, caption) stays hand-maintained outside markers.
Usage: make_bench_rows.py [--check]   --check = fail if files would change.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bench_registry import MODELS

from hindsight_paths import REPO
BENCH = REPO / "hindsight/outputs/bench"
MD = BENCH / "BENCH_ROWS.md"
CSV_OUT = BENCH / "bench_rows.csv"
TEX = REPO / "hindsight/paper/latex/sections/A4_appendix_benchmark.tex"
TEX2 = REPO / "hindsight/paper2/latex/sections/05_leaderboard.tex"

MD_B = "<!-- BEGIN GENERATED TABLE (make_bench_rows.py — do not hand-edit) -->"
MD_E = "<!-- END GENERATED TABLE -->"
TEX_B = "% BEGIN GENERATED ROWS (make_bench_rows.py — do not hand-edit)"
TEX_E = "% END GENERATED ROWS"

EMDASH = "—"


def pct(x: float) -> int:
    """Percent, rounding decimal ties half-even (0.925 -> 92), immune to
    binary float noise (repr gives the shortest round-tripping decimal)."""
    return int((Decimal(repr(x)) * 100).quantize(Decimal("1"), ROUND_HALF_EVEN))


def texify(s: str) -> str:
    """+0.215 -> +.215 ; -0.10 -> $-$.10 ; 1.000 unchanged."""
    s = re.sub(r"(^|[+\-\[,])0\.", lambda m: m.group(1) + ".", s)
    return s.replace("-", "$-$")


def load(m: dict) -> dict:
    key = m["key"]
    r = json.loads((BENCH / key / f"{key}_row.json").read_text())
    out = {
        "e2": r["E2_date_trigger"], "e3": r["E3_transplant"],
        "p1_cal": r.get("P1_placebo_postcutoff"),
        "p1_rel": None,
        "rec": r.get("REC", {}), "lap": r["LAP"],
        "dd": r.get("delta_dissociation") or {},
        "valid": r["VALID"],
    }
    if m["p1"] == "model_relative":
        mr = json.loads((BENCH / key / "model_relative_placebo.json").read_text())
        out["p1_rel"] = mr["model_relative_window"]["D_minus_M"]
    return out


def est_ci(e: dict) -> str:
    return f"{e['est']:+.3f} [{e['ci95'][0]:.2f},{e['ci95'][1]:.2f}]"


def cell_e(m: dict, d: dict, which: str, md: bool) -> str:
    e = d[which]
    s = est_ci(e)
    sparse = which == "e3" and m["e3_sparse"]
    W = which.upper().replace("E", "E")  # "E2"/"E3"
    bold = W in m["bold"].get("md" if md else "tex", set())
    if md:
        if bold and e["ci95"][0] < 0 < e["ci95"][1]:
            s += " ∋0"
        if bold:
            s = f"**{s}**"
        if sparse:
            s += "‖"
        return s
    est, ci = s.split(" ", 1)
    est, ci = texify(est), texify(ci)
    if bold:
        est = rf"\textbf{{{est}}}"
    s = f"{est} {ci}"
    if sparse:
        s += r"\textsuperscript{s}"
    return s


def cell_p1(m: dict, d: dict, md: bool) -> str:
    if m["p1"] == "absent":
        return EMDASH if md else r"---\textsuperscript{c}"
    if m["p1"] == "model_relative":
        v = f"{d['p1_rel']:+.3f}"
        return v + "ᴹ" if md else texify(v) + r"\textsuperscript{m}"
    v = f"{d['p1_cal']:+.3f}"
    return v if md else texify(v)


def cell_rec(m: dict, d: dict, md: bool) -> str:
    if m["rec"] == "nonconvergent":
        return "-/-◊" if md else r"---\textsuperscript{r}"
    if m["rec"] == "not_run":
        return "-/-ⁿ" if md else r"---\textsuperscript{n}"
    pre, post = d["rec"]["pre"]["year"], d["rec"]["post"]["year"]
    f = (lambda v: EMDASH if v is None else f"{pct(v)}%") if md else \
        (lambda v: "---" if v is None else f"{pct(v)}\\%")
    return f"{f(pre)}/{f(post)}"


def cell_lap(m: dict, d: dict, md: bool) -> str:
    lap = d["lap"]
    pre, post = f"{lap['pre_mean']:.3f}", f"{lap['post_mean']:.3f}"
    h = pct(lap["recall_hit_rate"])
    bold_hit = "hit" in m["bold"].get("md" if md else "tex", set())
    if md:
        hit = f"hit {h}%" + ("=随机" if m["lap_at_chance"] else "")
        if bold_hit:
            hit = f"**{hit}**"
        return f"{pre}/{post} ({hit})"
    pre, post = texify(pre), texify(post)
    hit = rf"\textbf{{{h}\%}}" if bold_hit else f"{h}\\%"
    s = f"{pre}/{post} ({hit})"
    if m["lap_at_chance"]:
        s += r"\textsuperscript{g}"
    return s


def cell_cutoff(m: dict, d: dict, md: bool) -> str:
    if m["lap_at_chance"] and not md:
        return r"---\textsuperscript{g}"
    c = d["lap"]["empirical_cutoff"]
    return c + ("††" if m["lap_at_chance"] else "") if md else c


def cell_delta(m: dict, d: dict, md: bool) -> str:
    if m["lap_at_chance"] and not md:
        return r"---\textsuperscript{g}"
    delta, t = d["dd"].get("delta"), d["dd"].get("t")
    if delta is None:
        if m["delta_gate"] == "lowvar":
            return "-ᵛ" if md else r"---\textsuperscript{v}"
        return EMDASH if md else "---"
    bold = "delta" in m["bold"].get("md" if md else "tex", set())
    if md:
        s = f"{delta:+.3f} (t={t:.2f})"
        if m["delta_gate"] == "weakid":
            s += "‡"
        if m["lap_at_chance"]:
            s += "††"
        return f"**{s}**" if bold else s
    # t-values keep their leading zero in the tex table ("(0.13)"); only the
    # estimate drops it ("+.019")
    est, tt = texify(f"{delta:+.3f}"), f"{t:.2f}".replace("-", "$-$")
    if bold:
        est = rf"\textbf{{{est}}}"
    s = f"{est} ({tt})"
    if m["delta_gate"] == "weakid":
        s += r"\textsuperscript{w}"
    return s


def cell_valid(m: dict, d: dict, md: bool) -> str:
    v = f"{pct(d['valid']['sketch_rate'])}"
    sup = m["valid_sup"] or (None, None)
    if md:
        return f"{v}%" + (sup[0] or "")
    return f"{v}\\%" + (rf"\textsuperscript{{{sup[1]}}}" if sup[1] else "")


def md_table() -> str:
    lines = [
        "| model | 世代 | E2 日期触发 | E3 移植 | P1 placebo* | REC year pre/post"
        " | LAP pre/post | emp.cutoff | δ 解离 | VALID |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in MODELS:
        d = load(m)
        name = m["key"] + (m["name_sup"][0] if m["name_sup"] else "")
        lines.append("| " + " | ".join([
            name, m["gen_md"],
            cell_e(m, d, "e2", True), cell_e(m, d, "e3", True),
            cell_p1(m, d, True), cell_rec(m, d, True), cell_lap(m, d, True),
            cell_cutoff(m, d, True), cell_delta(m, d, True),
            cell_valid(m, d, True),
        ]) + " |")
    return "\n".join(lines)


def tex_rows() -> str:
    lines = []
    for m in MODELS:
        d = load(m)
        name = m["tex"] + (rf"\textsuperscript{{{m['name_sup'][1]}}}"
                           if m["name_sup"] else "")
        lines.append(" & ".join([
            name, str(m["gen"]),
            cell_e(m, d, "e2", False), cell_e(m, d, "e3", False),
            cell_p1(m, d, False), cell_rec(m, d, False), cell_lap(m, d, False),
            cell_cutoff(m, d, False), cell_delta(m, d, False),
            cell_valid(m, d, False),
        ]) + r" \\")
    return "\n".join(lines)


def csv_export() -> str:
    import io
    buf = io.StringIO()
    # \n terminator: csv's default \r\n never round-trips through read_text()
    # (universal-newline translation), which would make --check always fail
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([
        "key", "display", "generation", "e2_est", "e2_lo", "e2_hi",
        "e3_est", "e3_lo", "e3_hi", "p1_mode", "p1_calendar",
        "p1_model_relative", "rec_pre_year", "rec_pre_n", "rec_post_year",
        "rec_post_n", "lap_pre", "lap_post", "empirical_cutoff",
        "recall_hit_rate", "recall_n", "delta", "delta_t", "delta_n",
        "valid_sketch_rate", "cells", "lap_at_chance", "delta_gate", "rec_mode",
    ])
    for m in MODELS:
        d = load(m)
        rec, lap, dd = d["rec"], d["lap"], d["dd"]
        w.writerow([
            m["key"], m["tex"], m["gen"],
            d["e2"]["est"], *d["e2"]["ci95"], d["e3"]["est"], *d["e3"]["ci95"],
            m["p1"], d["p1_cal"], d["p1_rel"],
            rec.get("pre", {}).get("year"), rec.get("pre", {}).get("n"),
            rec.get("post", {}).get("year"), rec.get("post", {}).get("n"),
            lap["pre_mean"], lap["post_mean"], lap["empirical_cutoff"],
            lap["recall_hit_rate"], lap.get("recall_n"),
            dd.get("delta"), dd.get("t"), dd.get("n"),
            d["valid"]["sketch_rate"], d["valid"]["cells"],
            m["lap_at_chance"], m["delta_gate"], m["rec"],
        ])
    return buf.getvalue()


def splice(text: str, begin: str, end: str, payload: str) -> str:
    if begin not in text:
        sys.exit(f"FAIL: marker not found: {begin!r}")
    head, rest = text.split(begin, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{begin}\n{payload}\n{end}{tail}"


def main() -> None:
    check = "--check" in sys.argv
    targets = [
        (MD, splice(MD.read_text(), MD_B, MD_E, md_table())),
        (TEX, splice(TEX.read_text(), TEX_B, TEX_E, tex_rows())),
        (CSV_OUT, csv_export()),
        (TEX2, splice(TEX2.read_text(), TEX_B, TEX_E, tex_rows())),
    ]
    drift = []
    for path, new in targets:
        old = path.read_text() if path.exists() else None
        if old != new:
            drift.append(path.name)
            if not check:
                path.write_text(new)
    if check:
        if drift:
            sys.exit(f"CHECK FAIL: would rewrite {drift}")
        print("check OK: all generated blocks match the frozen row jsons")
    else:
        print(f"wrote {len(drift)} changed file(s): {drift or 'none'}")


if __name__ == "__main__":
    main()
