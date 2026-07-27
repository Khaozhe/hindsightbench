#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (2026-07-24, Kimi review response)

Extended-vocabulary integrity audit of masked-arm (M) sketches.

Background: paper 1 (04_exp1_channels.tex line 24) reports "era-specific proper
nouns in 14 of 1,920 sketches (0.73%)". That number was produced by
scripts/analyze_kt1.py (ERA_TERMS, 14 substrings) over the KT-1 masked run
(outputs/kt1/masked_nodes/, 240 dates x 8 sketches x 1 run, gemini-2.5-flash).
A reviewer objects that the crisis-node zero-instance claim rests on only 4
strings ("financial crisis", "Lehman", "COVID", "pandemic") and that e.g.
"bailout", "subprime", "lockdown" were unscanned for that claim.

This script re-audits with a 20-term extended vocabulary, case-insensitively,
over BOTH:
  (a) the FM-1 frozen Flash masked arm, ALL reps:
      outputs/fm1/gemini-2.5-flash/M/rep{1,2,3}/<date>/01_sketches_valid.json
  (b) the KT-1 masked run (the corpus the paper's 14/1,920 actually refers to):
      outputs/kt1/masked_nodes/<date>/01_sketches_valid.json

Matching: per sketch, every string value in the sketch dict (recursive) is
joined and matched with case-insensitive word-boundary regex per term.
Substring counts (no word boundary, the analyze_kt1.py convention) are also
reported when they differ.

READ-ONLY over frozen dirs. Output goes ONLY to outputs/review/:
  m_vocab_extended.json, m_vocab_extended.md
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path("REPO_ROOT")
FM1_M = REPO / "hindsight/outputs/fm1/gemini-2.5-flash/M"
KT1_M = REPO / "hindsight/outputs/kt1/masked_nodes"
OUT_DIR = REPO / "hindsight/outputs/review"
OUT_JSON = OUT_DIR / "m_vocab_extended.json"
OUT_MD = OUT_DIR / "m_vocab_extended.md"

TERMS = [
    "financial crisis", "global financial crisis", "gfc", "lehman",
    "bear stearns", "subprime", "bailout", "tarp", "credit crunch",
    "mortgage crisis", "housing crash", "great recession",
    "quantitative easing", "covid", "pandemic", "lockdown", "coronavirus",
    "svb", "silicon valley bank", "stimulus",
]

# The full preregistered crisis set (11 dates, section 3.4). Earlier runs of
# this scan listed only the 6 GFC + 2 COVID nodes, silently omitting the three
# 2022 inflation-shock nodes, so "zero hits on the crisis nodes" was scoped to
# 8 of 11 while the paper's crisis set is 11. Extending it changes no result
# (the 2022 nodes are also clean) but makes the reported scope the true one.
CRISIS_NODES = [
    "2008-09-15", "2008-10-15", "2008-11-15", "2008-12-15",
    "2009-01-15", "2009-02-15", "2020-03-15", "2020-04-15",
    "2022-06-15", "2022-09-15", "2022-10-15",
]

WB_RE = {t: re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE) for t in TERMS}


def iter_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_strings(v)


def snippet(text: str, m: re.Match, max_words: int = 15) -> str:
    words_before = text[: m.start()].split()
    words_after = text[m.end():].split()
    term_words = m.group(0).split()
    k = max((max_words - len(term_words)) // 2, 2)
    out = words_before[-k:] + term_words + words_after[:k]
    return " ".join(out[:max_words])


def scan_corpus(name: str, files: list[tuple[str, str, Path]]):
    """files: list of (rep_label, date, path)."""
    n_sketches = 0
    n_files = 0
    term_sketch_hits = defaultdict(int)        # term -> n sketches containing it (word-boundary)
    term_occurrences = defaultdict(int)        # term -> raw regex occurrence count
    term_substring_sketch_hits = defaultdict(int)  # term -> n sketches (plain substring, analyze_kt1 convention)
    crisis_hits = []                            # list of dicts (word-boundary hits on crisis nodes)
    examples = []                               # up to 5 overall
    per_rep_counts = defaultdict(int)

    for rep, date, path in files:
        sketches = json.loads(path.read_text())
        n_files += 1
        for idx, sk in enumerate(sketches):
            n_sketches += 1
            per_rep_counts[rep] += 1
            text = " ".join(iter_strings(sk))
            low = text.lower()
            for t in TERMS:
                ms = list(WB_RE[t].finditer(text))
                if t in low:
                    term_substring_sketch_hits[t] += 1
                if not ms:
                    continue
                term_sketch_hits[t] += 1
                term_occurrences[t] += len(ms)
                hit = {
                    "rep": rep, "date": date, "term": t,
                    "sketch_index": idx,
                    "hypothesis_id": sk.get("hypothesis_id"),
                    "snippet": snippet(text, ms[0]),
                }
                if date in CRISIS_NODES:
                    crisis_hits.append(hit)
                if len(examples) < 5:
                    examples.append(hit)

    # crisis hits take priority in the example list
    if crisis_hits:
        seen = set()
        prioritized = []
        for h in crisis_hits + examples:
            key = (h["rep"], h["date"], h["term"], h["sketch_index"])
            if key not in seen:
                seen.add(key)
                prioritized.append(h)
        examples = prioritized[:5]

    return {
        "corpus": name,
        "n_files": n_files,
        "n_sketches_scanned": n_sketches,
        "per_rep_sketch_counts": dict(per_rep_counts),
        "term_sketch_hits_word_boundary": {t: term_sketch_hits.get(t, 0) for t in TERMS},
        "term_occurrences_word_boundary": {t: term_occurrences.get(t, 0) for t in TERMS},
        "term_sketch_hits_substring": {t: term_substring_sketch_hits.get(t, 0) for t in TERMS},
        "crisis_node_hits": crisis_hits,
        "n_crisis_node_hits": len(crisis_hits),
        "examples": examples,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fm1_files = []
    for rep_dir in sorted(FM1_M.iterdir()):
        if not rep_dir.is_dir():
            continue
        for date_dir in sorted(rep_dir.iterdir()):
            f = date_dir / "01_sketches_valid.json"
            if f.exists():
                fm1_files.append((rep_dir.name, date_dir.name, f))

    kt1_files = []
    for date_dir in sorted(KT1_M.iterdir()):
        f = date_dir / "01_sketches_valid.json"
        if f.exists():
            kt1_files.append(("kt1", date_dir.name, f))

    fm1 = scan_corpus("fm1_flash_M_all_reps", fm1_files)
    kt1 = scan_corpus("kt1_masked_nodes", kt1_files)

    result = {
        "generated": "2026-07-24",
        "script": "hindsight/scripts/audit_m_vocab_extended.py",
        "note": (
            "POST-FREEZE EXPLORATORY (Kimi review response). Paper's 14/1,920 was "
            "computed by analyze_kt1.py over outputs/kt1/masked_nodes (KT-1 masked "
            "run, 240 dates x 8 sketches x 1 run, gemini-2.5-flash), scanning only "
            "mechanism_narrative+regime_hint+failure_condition with 14 substrings. "
            "This audit scans ALL string fields of every sketch with a 20-term "
            "vocabulary over both the FM-1 flash M arm (all 3 reps) and KT-1."
        ),
        "vocabulary": TERMS,
        "crisis_nodes": CRISIS_NODES,
        "corpora": [fm1, kt1],
    }
    OUT_JSON.write_text(json.dumps(result, indent=2))

    lines = [
        "# Extended-vocabulary masked-arm audit (POST-FREEZE EXPLORATORY, 2026-07-24)",
        "",
        "Review objection: paper's crisis-node zero-instance claim used only 4 strings.",
        "Extended vocabulary (20 terms, case-insensitive word-boundary regex, all string",
        "fields of each sketch):",
        "",
        "```", ", ".join(TERMS), "```",
        "",
        f"Crisis nodes: {', '.join(CRISIS_NODES)}",
        "",
    ]
    for c in (fm1, kt1):
        lines += [
            f"## Corpus: {c['corpus']}",
            "",
            f"- files scanned: {c['n_files']}",
            f"- sketches scanned: {c['n_sketches_scanned']} (per rep: {c['per_rep_sketch_counts']})",
            f"- crisis-node hits (any term): {c['n_crisis_node_hits']}",
            "",
            "| term | sketches w/ hit (word-boundary) | occurrences | sketches w/ hit (substring) |",
            "|---|---|---|---|",
        ]
        for t in TERMS:
            wb = c["term_sketch_hits_word_boundary"][t]
            oc = c["term_occurrences_word_boundary"][t]
            ss = c["term_sketch_hits_substring"][t]
            if wb or ss:
                lines.append(f"| {t} | {wb} | {oc} | {ss} |")
        if not any(c["term_sketch_hits_word_boundary"][t] or c["term_sketch_hits_substring"][t] for t in TERMS):
            lines.append("| (no term hit anywhere) | 0 | 0 | 0 |")
        lines.append("")
        if c["crisis_node_hits"]:
            lines.append("### CRISIS-NODE HITS (contradicts paper claim if any)")
            for h in c["crisis_node_hits"]:
                lines.append(f"- {h['rep']} {h['date']} [{h['term']}] \"{h['snippet']}\"")
        else:
            lines.append("### Crisis-node hits: NONE")
        lines.append("")
        if c["examples"]:
            lines.append("### Examples (up to 5)")
            for h in c["examples"]:
                lines.append(f"- {h['rep']} {h['date']} [{h['term']}] \"{h['snippet']}\"")
            lines.append("")

    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"written: {OUT_JSON}\n         {OUT_MD}")
    for c in (fm1, kt1):
        print(f"{c['corpus']}: n={c['n_sketches_scanned']}, crisis hits={c['n_crisis_node_hits']}, "
              f"total term-hit sketches={sum(c['term_sketch_hits_word_boundary'].values())}")


if __name__ == "__main__":
    main()
