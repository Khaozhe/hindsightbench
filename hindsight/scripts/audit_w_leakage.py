#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API calls.

W/M-arm leakage audit, all model dirs under outputs/bench/ (ICLR plan P0-1).

Fixes the 07-21 ad-hoc grep session into a reproducible script. Per model,
over W- and M-arm 04_raw_response.txt files:
  (a) year-mention rate         \\b(2008|2009|2020|2023|2024|2025)\\b
  (b) event-lexicon rate        original 7 terms AND expanded 18 terms (both)
  (c) month-year string rate    MonthName YYYY
  (d) W only, joined on fake date (03_run_meta.json, with a bench-wide
      decision_date->fake_date mapping as fallback where meta stores null):
      fake-year rate, true-year rate (cells with true year != fake year),
      anachronism rate (any year strictly after the asserted fake year,
      unit echoes like '2017 Dollars' / '1982-1984=100' excluded)
  (e) qwen3.6-27b-bf16 date-doubt join: explicit date-questioning cells
      ('look(s) (more) like 20XX') x per-cell bearish sketch share
  (f) analyze_w_questioning.py tier1/tier2 scan, regexes EXTENDED with the
      qwen phrasing, re-run over the whole bench W corpus (original script
      and its committed FM-1 output are left untouched)

Row handling: every model dir is included; smoke rows (2 dates), 65-date
rows and quantization-variant rows carry an explicit tier label so they are
not misread as full leaderboard rows.

External anchors (07-21 spot counts) are asserted at runtime:
  gemini-2.5-pro W event7 90/240, year 99/240; qwen3.6-27b-bf16 W year
  180/515; month-year over the 4 spot-checked M arms 0/2268.

Reads frozen data only; writes outputs/review/w_leakage_audit.{json,md}.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hindsight_paths import REPO
from bench_registry import MODELS as REGISTRY_MODELS

BENCH = REPO / "hindsight/outputs/bench"
OUT = REPO / "hindsight/outputs/review"

# ---------------------------------------------------------------- lexicons
YEAR_RX = re.compile(r"\b(2008|2009|2020|2023|2024|2025)\b")

EVENT7 = ["Lehman", "COVID", "pandemic", "financial crisis", "GFC", "SVB",
          "subprime"]
EVENT18 = EVENT7 + [
    "taper", "Brexit", r"dot-?com", "quantitative easing", r"\bQE\b",
    "ZIRP", "Volcker", "stagflation", "oil shock", "oil embargo",
    r"euro(zone)?( debt| sovereign( debt)?)? crisis",
]
EVENT7_RX = re.compile("|".join(EVENT7), re.I)
EVENT18_RX = re.compile("|".join(EVENT18), re.I)

MONTHYEAR_RX = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(19|20)\d{2}\b")

YEAR_TOKEN_RX = re.compile(r"\b((?:19|20)\d{2})\b")
# unit/data echoes: 'Chained 2017 Dollars', 'Index 1982-1984=100',
# '2015=100', plus prompt snapshot VALUES that lexically look like years
# ('HOUST=2014.0' -- housing starts in the 1900-2099 thousand range;
# verified false-positive class in the 07-21 eyeball pass)
UNIT_ECHO_RXS = [
    re.compile(r"(?:19|20)\d{2}\s*(?:[-–]\s*(?:19|20)\d{2}\s*)?=\s*100"),
    re.compile(r"(?:19|20)\d{2}\s+(?:chained\s+)?dollars", re.I),
    re.compile(r"=\s*(?:19|20)\d{2}(?:\.\d+)?"),   # series value assignment
    re.compile(r"(?:19|20)\d{2}\.\d"),             # decimal with year-like int
]

# (e) qwen explicit date-doubt phrasing ('These look more like 2023/2024
# values', 'This looks like 2020-2021 data, not 2006')
DATE_DOUBT_RX = re.compile(r"look(s)?( more)? like (19|20)\d\d", re.I)

# (f) tier regexes: copied verbatim from analyze_w_questioning.py (frozen),
# plus the qwen-derived extension patterns.
TIER1 = [
    r"date\b.{0,60}\b(wrong|incorrect|inconsistent|implausible|mismatch|mislabel|erroneous|suspect)",
    r"\b(wrong|incorrect|inconsistent|implausible|mismatch|mislabel|erroneous|suspect)\w*\b.{0,60}\bdate",
    r"anachron",
    r"date\b.{0,40}\b(discrepan|conflict|does not match|doesn't match|not consistent)",
    r"\b(discrepan|conflict)\w*\b.{0,40}\bdate",
    r"data\b.{0,60}\b(suggests?|indicates?|implies|resembles?)\b.{0,60}\b(a different|an earlier|a later)\b.{0,20}\b(date|year|period|era)",
    r"(cannot|can't|hard to)\b.{0,30}\breconcile\b.{0,40}\bdate",
]
TIER1_EXT = [
    r"look(s)?( more)? like (19|20)\d\d",                # qwen phrasing
    r"(data|values|snapshot)\b.{0,40}, not (19|20)\d\d", # '... data, not 2006'
]
TIER2 = [
    r"if the date is (accurate|correct)",
    r"assuming th(e|is)\b.{0,20}\bdate",
    r"despite the (stated|given|asserted) date",
    r"unusual(ly)? for (this|the) (stated )?(period|year|date|era)",
    r"atypical for (this|the) (period|year|date|era)",
    r"given the (stated|asserted) date",
]
RX1 = [re.compile(p, re.I) for p in TIER1]
RX1E = [re.compile(p, re.I) for p in TIER1_EXT]
RX2 = [re.compile(p, re.I) for p in TIER2]

INJECTED = {"decision_date", "hypothesis_id"}  # caller-added, not model text

TIER_LABEL = {
    "gpt-5-mini": "smoke-2date",
    "gpt-5.1": "smoke-2date",
    "llama3.1:8b": "smoke-2date",
    "llama3.2:1b": "reduced-65date",
    "llama3.2:3b": "reduced-65date",
    "qwen3.6-27b-awq": "quant-variant",
    "qwen3.6-27b-bf16": "quant-variant",
}
REGISTRY_ORDER = [m["key"] for m in REGISTRY_MODELS]


def iter_cells(model_dir: Path, arm: str):
    """Yield (cell_path, rep_name, date_str) for every completed cell.

    Cell dirs resolve through SYMLINKS into outputs/fm1/ for the Gemini
    rows: os.walk MUST use followlinks=True (plain walk finds 0 cells).
    """
    root = model_dir / arm
    if not root.exists():
        return
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=True):
        if "04_raw_response.txt" not in filenames:
            continue
        p = Path(dirpath)
        rep = next((q.name for q in p.parents if q.name.startswith("rep")),
                   None)
        yield p, rep, p.name


def anachronism_years(text: str, fake_year: int) -> list[int]:
    """Years strictly after fake_year, unit-echo spans excluded."""
    excl = []
    for rx in UNIT_ECHO_RXS:
        excl += [m.span() for m in rx.finditer(text)]
    out = set()
    for m in YEAR_TOKEN_RX.finditer(text):
        if any(a <= m.start() and m.end() <= b for a, b in excl):
            continue
        y = int(m.group(1))
        if y > fake_year:
            out.add(y)
    return sorted(out)


def build_fake_map() -> dict[str, str]:
    """Bench-wide decision_date -> fake_date from every non-null W meta.

    Anthropic/OpenAI batch runners stored fake_date=null in run meta; the
    mapping is a deterministic circular shift shared by all runs
    (run_bench_model.py all_bench_nodes), so metas from the models that did
    record it reconstruct the join. Consistency is asserted.
    """
    fake_map: dict[str, str] = {}
    for d in sorted(BENCH.iterdir()):
        if not (d.is_dir() and (d / "W").exists()):
            continue
        for cell, _rep, dd in iter_cells(d, "W"):
            mp = cell / "03_run_meta.json"
            if not mp.exists():
                continue
            meta = json.loads(mp.read_text())
            fd = meta.get("fake_date")
            key = meta.get("decision_date") or dd
            if fd is None:
                continue
            if key in fake_map:
                assert fake_map[key] == fd, \
                    f"fake_date conflict for {key}: {fake_map[key]} vs {fd} ({cell})"
            else:
                fake_map[key] = fd
    return fake_map


def rate(count: int, denom: int) -> dict:
    return {"count": count, "denom": denom,
            "rate": round(count / denom, 4) if denom else None}


def scan_model_arm(model_dir: Path, arm: str, fake_map: dict) -> dict:
    n = 0
    hits = {"year": 0, "event7": 0, "event18": 0, "monthyear": 0}
    dates, reps = set(), set()
    # (d) W-only accumulators
    fake_src = {"meta": 0, "mapping": 0, "unknown": 0}
    fy_hit = 0
    ty_hit = ty_denom = 0
    ana_hit = ana_denom = 0
    for cell, rep, dd in iter_cells(model_dir, arm):
        n += 1
        dates.add(dd)
        reps.add(rep)
        text = (cell / "04_raw_response.txt").read_text(errors="replace")
        if YEAR_RX.search(text):
            hits["year"] += 1
        if EVENT7_RX.search(text):
            hits["event7"] += 1
        if EVENT18_RX.search(text):
            hits["event18"] += 1
        if MONTHYEAR_RX.search(text):
            hits["monthyear"] += 1
        if arm != "W":
            continue
        mp = cell / "03_run_meta.json"
        meta = json.loads(mp.read_text()) if mp.exists() else {}
        dd = meta.get("decision_date") or dd
        fd = meta.get("fake_date")
        if fd is not None:
            fake_src["meta"] += 1
        elif dd in fake_map:
            fd = fake_map[dd]
            fake_src["mapping"] += 1
        else:
            fake_src["unknown"] += 1
            continue
        fake_year, true_year = int(fd[:4]), int(dd[:4])
        ana_denom += 1
        if re.search(rf"\b{fake_year}\b", text):
            fy_hit += 1
        if true_year != fake_year:
            ty_denom += 1
            if re.search(rf"\b{true_year}\b", text):
                ty_hit += 1
        if anachronism_years(text, fake_year):
            ana_hit += 1
    out = {"n_files": n, "n_dates": len(dates), "n_reps": len(reps - {None}),
           "year_hit": rate(hits["year"], n),
           "event7_hit": rate(hits["event7"], n),
           "event18_hit": rate(hits["event18"], n),
           "monthyear_hit": rate(hits["monthyear"], n)}
    if arm == "W":
        out["fake_date_source"] = fake_src
        out["fake_year_hit"] = rate(fy_hit, n - fake_src["unknown"])
        out["true_year_hit"] = rate(ty_hit, ty_denom)
        out["anachronism"] = rate(ana_hit, ana_denom)
    return out


# ------------------------------------------------- (e) qwen date-doubt join
def qwen_date_doubt(fake_map: dict) -> dict:
    model_dir = BENCH / "qwen3.6-27b-bf16"

    def bearish_share(cell: Path):
        fj = cell / "01_sketches_valid.json"
        if not fj.exists():
            return None, 0
        sketches = json.loads(fj.read_text())
        dirs = [s.get("direction") for s in sketches
                if s.get("direction") in ("+", "-")]
        if not dirs:
            return None, len(sketches)
        return dirs.count("-") / len(dirs), len(sketches)

    all_shares, hit_rows = [], []
    n_cells = 0
    for cell, rep, dd in iter_cells(model_dir, "W"):
        n_cells += 1
        share, nsk = bearish_share(cell)
        if share is not None:
            all_shares.append(share)
        text = (cell / "04_raw_response.txt").read_text(errors="replace")
        if DATE_DOUBT_RX.search(text):
            meta_p = cell / "03_run_meta.json"
            meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
            fd = meta.get("fake_date") or fake_map.get(dd)
            hit_rows.append({"rep": rep, "true_date": dd, "fake_date": fd,
                             "n_valid_sketches": nsk,
                             "bearish_share": None if share is None
                             else round(share, 4)})
    mean_all = sum(all_shares) / len(all_shares)
    hit_shares = [r["bearish_share"] for r in hit_rows
                  if r["bearish_share"] is not None]
    for r in hit_rows:
        if r["bearish_share"] is not None:
            r["delta_vs_w_mean"] = round(r["bearish_share"] - mean_all, 4)
    return {
        "model": "qwen3.6-27b-bf16",
        "doubt_regex": DATE_DOUBT_RX.pattern,
        "n_w_cells": n_cells,
        "n_hit_cells": len(hit_rows),
        "n_hit_cells_with_valid_sketches": len(hit_shares),
        "w_arm_mean_bearish_share": round(mean_all, 4),
        "hit_cells_mean_bearish_share":
            round(sum(hit_shares) / len(hit_shares), 4) if hit_shares else None,
        "hit_cells": sorted(hit_rows,
                            key=lambda r: (r["rep"] or "", r["true_date"])),
    }


# --------------------------- (f) extended tier1/tier2 questioning scan
def sketch_text(s: dict) -> str:
    parts = []
    for k, v in s.items():
        if k in INJECTED:
            continue
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts += [x for x in v if isinstance(x, str)]
    return " | ".join(parts)


def questioning_scan(model_dir: Path) -> dict:
    """analyze_w_questioning.py logic (sketch fields + raw text outside the
    JSON block), tier1 extended with the qwen phrasing patterns."""
    n_sk = n_raw = 0
    t1_orig = t1_ext_only = t2_only = 0
    for cell, _rep, _dd in iter_cells(model_dir, "W"):
        units = []
        fj = cell / "01_sketches_valid.json"
        if fj.exists():
            for s in json.loads(fj.read_text()):
                n_sk += 1
                units.append(sketch_text(s))
        t = (cell / "04_raw_response.txt").read_text(errors="replace")
        i, j = t.find("["), t.rfind("]")
        n_raw += 1
        units.append((t[:i] + t[j + 1:]) if 0 <= i < j else t)
        for u in units:
            m1 = any(rx.search(u) for rx in RX1)
            m1e = any(rx.search(u) for rx in RX1E)
            m2 = any(rx.search(u) for rx in RX2)
            if m1:
                t1_orig += 1
            elif m1e:
                t1_ext_only += 1
            elif m2:
                t2_only += 1
    return {"n_sketches": n_sk, "n_raw_responses": n_raw,
            "tier1_original": t1_orig, "tier1_ext_only": t1_ext_only,
            "tier1_total": t1_orig + t1_ext_only, "tier2_only": t2_only}


# ----------------------------------------------------------------- report
def pct(r: dict) -> str:
    return "--" if r["rate"] is None else f"{100 * r['rate']:.1f}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    model_dirs = sorted(
        (d for d in BENCH.iterdir()
         if d.is_dir() and any((d / a).exists() for a in "DMRW")),
        key=lambda d: (REGISTRY_ORDER.index(d.name)
                       if d.name in REGISTRY_ORDER else 99, d.name))
    fake_map = build_fake_map()
    assert len(fake_map) == 258, f"fake map covers {len(fake_map)} dates"

    rows = []
    for d in model_dirs:
        row = {"model": d.name,
               "tier": TIER_LABEL.get(d.name, "full"),
               "in_registry": d.name in REGISTRY_ORDER,
               "W": scan_model_arm(d, "W", fake_map),
               "M": scan_model_arm(d, "M", fake_map)}
        row["questioning_extended"] = questioning_scan(d)
        rows.append(row)
    by = {r["model"]: r for r in rows}

    # ---- external anchors (07-21 spot counts) -- hard gates
    gp, qb = by["gemini-2.5-pro"], by["qwen3.6-27b-bf16"]
    anchors = {
        "gemini-2.5-pro_W_event7": f"{gp['W']['event7_hit']['count']}/{gp['W']['n_files']}",
        "gemini-2.5-pro_W_year": f"{gp['W']['year_hit']['count']}/{gp['W']['n_files']}",
        "qwen3.6-27b-bf16_W_year": f"{qb['W']['year_hit']['count']}/{qb['W']['n_files']}",
    }
    assert anchors["gemini-2.5-pro_W_event7"] == "90/240", anchors
    assert anchors["gemini-2.5-pro_W_year"] == "99/240", anchors
    assert anchors["qwen3.6-27b-bf16_W_year"] == "180/515", anchors
    m4 = ["gemini-2.5-pro", "deepseek-v4-flash", "qwen3.6-27b-bf16",
          "kimi-k2.6"]
    my_c = sum(by[m]["M"]["monthyear_hit"]["count"] for m in m4)
    my_n = sum(by[m]["M"]["n_files"] for m in m4)
    anchors["M_monthyear_4models"] = f"{my_c}/{my_n}"
    assert anchors["M_monthyear_4models"] == "0/2268", anchors

    doubt = qwen_date_doubt(fake_map)

    result = {
        "status": "POST-FREEZE EXPLORATORY (review-response, 2026-07-21)",
        "generated": date.today().isoformat(),
        "script": "hindsight/scripts/audit_w_leakage.py",
        "external_anchors_passed": anchors,
        "definitions": {
            "year_regex": YEAR_RX.pattern,
            "event_lexicon_original7": EVENT7,
            "event_lexicon_expanded18": EVENT18,
            "monthyear_regex": MONTHYEAR_RX.pattern,
            "anachronism": "any year token strictly after the asserted fake "
                           "year; unit echoes and snapshot-value echoes "
                           "(HOUST=2014.0) excluded",
            "unit_echo_regexes": [rx.pattern for rx in UNIT_ECHO_RXS],
            "fake_year_hit_denom": "W cells with known fake date",
            "true_year_hit_denom": "W cells with true year != fake year",
            "rate_unit": "files with >=1 match / files",
            "tier1_extension": TIER1_EXT,
            "questioning_unit": "valid sketches + raw-outside-JSON blocks "
                                "(same corpus as analyze_w_questioning.py)",
        },
        "models": rows,
        "qwen_date_doubt_join": doubt,
    }
    (OUT / "w_leakage_audit.json").write_text(json.dumps(result, indent=2))

    # ---- markdown
    L = ["# W/M-arm leakage audit (P0-1)", "",
         "POST-FREEZE EXPLORATORY (review-response, 2026-07-21). Zero API "
         "calls. Regenerate: `python hindsight/scripts/audit_w_leakage.py`.",
         "",
         "Rates = % of 04_raw_response.txt files with >=1 match. ev7 = "
         "original 7-term event lexicon, ev18 = expanded 18-term. mo-yr = "
         "'MonthName YYYY'. fakeY/trueY/anachr are W-only joins on the "
         "asserted fake date (anachr = any year strictly after the fake "
         "year; unit echoes like '2017 Dollars'/'1982-1984=100' and "
         "snapshot-value echoes like 'HOUST=2014.0' excluded; "
         "the W fake date is a circular shift, so for late true dates the "
         "fake year precedes the true year and true-period mentions count "
         "as anachronisms). trueY denominator = cells with true year != "
         "fake year.", "",
         "| model | tier | W n | yr% | ev7% | ev18% | mo-yr% | fakeY% | "
         "trueY% | anachr% | M n | yr% | ev7% | ev18% | mo-yr% |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        W, M = r["W"], r["M"]
        L.append(
            f"| {r['model']} | {r['tier']} | {W['n_files']} | "
            f"{pct(W['year_hit'])} | {pct(W['event7_hit'])} | "
            f"{pct(W['event18_hit'])} | {pct(W['monthyear_hit'])} | "
            f"{pct(W['fake_year_hit'])} | {pct(W['true_year_hit'])} | "
            f"{pct(W['anachronism'])} | {M['n_files']} | "
            f"{pct(M['year_hit'])} | {pct(M['event7_hit'])} | "
            f"{pct(M['event18_hit'])} | {pct(M['monthyear_hit'])} |")
    L += ["",
          "External anchors reproduced: " + "; ".join(
              f"{k}={v}" for k, v in anchors.items()), "",
          "## qwen3.6-27b-bf16 date-doubt join (e)", "",
          f"Doubt regex `{doubt['doubt_regex']}`: "
          f"{doubt['n_hit_cells']}/{doubt['n_w_cells']} W cells, "
          f"{doubt['n_hit_cells_with_valid_sketches']} of them with >=1 "
          "valid sketch. Mean bearish share in doubt cells "
          f"{doubt['hit_cells_mean_bearish_share']:.3f} vs W-arm mean "
          f"{doubt['w_arm_mean_bearish_share']:.3f}.", "",
          "| rep | true date | fake date | n sk | bearish | d vs W mean |",
          "|---|---|---|---|---|---|"]
    for h in doubt["hit_cells"]:
        b = "--" if h["bearish_share"] is None else f"{h['bearish_share']:.3f}"
        dv = ("--" if h.get("delta_vs_w_mean") is None
              else f"{h['delta_vs_w_mean']:+.3f}")
        L.append(f"| {h['rep']} | {h['true_date']} | {h['fake_date']} | "
                 f"{h['n_valid_sketches']} | {b} | {dv} |")
    L += ["", "## Extended date-questioning scan, bench W corpus (f)", "",
          "analyze_w_questioning.py corpus/logic, tier1 + qwen extension "
          f"patterns {TIER1_EXT} (original script and FM-1 output "
          "untouched). Units = valid sketches + raw-outside-JSON blocks.", "",
          "| model | tier | n sketches | n raw | tier1 orig | tier1 ext-only "
          "| tier1 total | tier2 only |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        q = r["questioning_extended"]
        L.append(f"| {r['model']} | {r['tier']} | {q['n_sketches']} | "
                 f"{q['n_raw_responses']} | {q['tier1_original']} | "
                 f"{q['tier1_ext_only']} | {q['tier1_total']} | "
                 f"{q['tier2_only']} |")
    (OUT / "w_leakage_audit.md").write_text("\n".join(L) + "\n")

    print(f"models={len(rows)}  anchors={anchors}")
    print(f"qwen doubt cells={doubt['n_hit_cells']} "
          f"(valid-sketch {doubt['n_hit_cells_with_valid_sketches']}), "
          f"bearish {doubt['hit_cells_mean_bearish_share']} vs "
          f"W mean {doubt['w_arm_mean_bearish_share']}")
    print(f"wrote {OUT / 'w_leakage_audit.json'}")
    print(f"wrote {OUT / 'w_leakage_audit.md'}")


if __name__ == "__main__":
    main()
