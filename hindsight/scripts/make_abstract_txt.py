#!/usr/bin/env python3
"""Regenerate paper/abstract_openreview.txt from paper/latex/sections/00_abstract.tex.

The OpenReview form takes plain text; the tex file is the single source. Conventions
match the 2026-07-26 hand-made file: one line, em dash for ---, en dash for --,
straight quotes, trailing newline.

    python scripts/make_abstract_txt.py          # write
    python scripts/make_abstract_txt.py --check  # exit 1 if txt drifted from tex
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "paper" / "latex" / "sections" / "00_abstract.tex"
TXT = ROOT / "paper" / "abstract_openreview.txt"


def tex_to_text(src: str) -> str:
    s = src
    s = re.sub(r"(?<!\\)%.*", "", s)                       # comments
    s = re.sub(r"\\(emph|textbf|textit|texttt)\{([^{}]*)\}", r"\2", s)
    s = s.replace("{[}", "[").replace("{]}", "]")
    s = s.replace("\\textasciitilde{}", "~").replace("\\textasciitilde", "~")
    s = s.replace("---", "\u2014").replace("--", "\u2013")
    s = s.replace("``", '"').replace("''", '"')
    s = s.replace("\\&", "&").replace("\\%", "%").replace("\\$", "$").replace("\\_", "_")
    s = s.replace("~", " ")
    s = re.sub(r"\\ldots\{\}|\\ldots", "\u2026", s)
    s = re.sub(r"\$([^$]*)\$", r"\1", s)                    # bare inline math
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)                    # single line
    s = re.sub(r"  +", " ", s).strip()
    leftovers = re.findall(r"\\[A-Za-z]+", s)
    if leftovers:
        sys.exit(f"unhandled LaTeX commands: {sorted(set(leftovers))}")
    if "{" in s or "}" in s:
        sys.exit("unhandled braces remain")
    return s + "\n"


def main() -> None:
    out = tex_to_text(TEX.read_text(encoding="utf-8"))
    if "--check" in sys.argv:
        cur = TXT.read_text(encoding="utf-8") if TXT.exists() else ""
        if cur != out:
            sys.exit(f"DRIFT: {TXT} differs from {TEX}")
        print(f"OK: {TXT.name} matches {TEX.name} ({len(out.split())} words)")
        return
    TXT.write_text(out, encoding="utf-8")
    print(f"wrote {TXT} ({len(out.split())} words, {len(out)} chars)")


if __name__ == "__main__":
    main()
