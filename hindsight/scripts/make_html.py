#!/usr/bin/env python
"""Build a self-contained reading HTML for each paper, into ~/Downloads.

Not a submission artifact -- a screen-readable rendering of exactly the .tex
sources that produced the PDFs, for review and sharing.

Fidelity notes (why this is not a bare `pandoc main.tex`):
  * Cross-references are resolved from the BUILT .aux files, so \\ref{fig:...}
    and \\ref{tab:...} print the same numbers as the PDF instead of "[?]".
    The script fails loudly if a referenced label is missing from the .aux,
    which would mean the HTML and the PDF disagree.
  * Figures are included as the .png siblings of the .pdf figures and inlined
    as data URIs (--embed-resources), so the file is one portable artifact.
  * Citations render through citeproc against the same references.bib the
    paper uses.
  * A handful of LaTeX constructs pandoc does not model (\\resizebox,
    \\captionof, custom macros) are normalized first.

Usage: python make_html.py [--out ~/Downloads]
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hindsight_paths import REPO  # noqa: E402

PAPERS = [
    {"key": "P1", "root": REPO / "hindsight/paper/latex", "entry": "main",
     "bib": REPO / "hindsight/paper/references.bib",
     "title": "The Date Is the Trigger: A Causal Anatomy of Parametric Hindsight "
              "in LLM Macro Hypothesis Generation",
     "sub": "Full paper with appendices A–E (AAAI-27 submission build)",
     "out": "P1_the_date_is_the_trigger.html"},
    {"key": "P2", "root": REPO / "hindsight/paper2/latex", "entry": "main",
     "bib": REPO / "hindsight/paper2/latex/references.bib",
     "title": "HindsightBench: A Black-Box Behavioral Audit Protocol for "
              "Parametric Hindsight in Time-Indexed LLM Decision Tasks",
     "sub": "arXiv:2607.18867 — v2 working copy",
     "out": "P2_hindsightbench.html"},
]

FIGDIR = REPO / "hindsight/paper/figures"

CSS = """
:root { --fg:#1a1a1a; --mut:#5c5c5c; --line:#e2e0dc; --bg:#fdfdfc; --acc:#8a5a2b; }
@media (prefers-color-scheme: dark) {
  :root { --fg:#e8e6e3; --mut:#a3a09b; --line:#33312e; --bg:#16150f; --acc:#d9a066; }
}
html { -webkit-text-size-adjust:100%; }
body { max-width:46rem; margin:0 auto; padding:2.5rem 1.25rem 6rem;
  background:var(--bg); color:var(--fg); font-size:17px; line-height:1.62;
  font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif; }
h1 { font-size:1.65rem; line-height:1.25; margin:0 0 .35rem; }
.sub { color:var(--mut); font-size:.95rem; margin:0 0 .4rem; }
.meta { color:var(--mut); font-size:.8rem; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  border-bottom:1px solid var(--line); padding-bottom:1.4rem; margin-bottom:2rem; }
h2 { font-size:1.22rem; margin:2.6rem 0 .7rem; padding-top:.5rem; border-top:1px solid var(--line); }
h3 { font-size:1.04rem; margin:1.8rem 0 .5rem; color:var(--acc); }
h4 { font-size:.98rem; margin:1.3rem 0 .4rem; }
p { margin:0 0 .95rem; }
a { color:var(--acc); }
figure { margin:1.8rem 0; text-align:center; }
figure img { max-width:100%; height:auto; }
figcaption { font-size:.85rem; color:var(--mut); text-align:left; margin-top:.6rem; line-height:1.5; }
.tbl-wrap, div.table, table { overflow-x:auto; }
table { display:block; max-width:100%; border-collapse:collapse; font-size:.82rem;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace; margin:1.4rem 0; }
th,td { border-bottom:1px solid var(--line); padding:.32rem .55rem; text-align:left; white-space:nowrap; }
th { font-weight:600; }
p.tbl-cap { font-size:.82rem; color:var(--mut); line-height:1.55;
  margin:-.6rem 0 1.8rem; }
caption { caption-side:bottom; font-size:.82rem; color:var(--mut); text-align:left;
  padding-top:.7rem; line-height:1.5; white-space:normal; }
code { font-size:.88em; background:color-mix(in srgb, var(--fg) 7%, transparent);
  padding:.08em .3em; border-radius:3px; }
blockquote { border-left:2px solid var(--line); margin:1.2rem 0; padding-left:1rem; color:var(--mut); }
#refs { font-size:.88rem; }
#refs div[id^="ref-"] { margin-bottom:.55rem; padding-left:1.4rem; text-indent:-1.4rem; }
nav#TOC { border:1px solid var(--line); border-radius:6px; padding:1rem 1.2rem;
  margin:0 0 2.5rem; font-size:.86rem; line-height:1.5; }
nav#TOC::before { content:"Contents"; display:block; font-weight:600;
  font-size:.8rem; letter-spacing:.06em; text-transform:uppercase;
  color:var(--mut); margin-bottom:.6rem; }
nav#TOC ul { list-style:none; margin:0; padding-left:0; }
nav#TOC ul ul { padding-left:1.1rem; }
nav#TOC li { margin:.15rem 0; }
nav#TOC a { text-decoration:none; }
nav#TOC a:hover { text-decoration:underline; }
"""


TABLE_RE = re.compile(r"<table\b.*?</table>", re.S)
CAP_RE = re.compile(r"<caption>(.*?)</caption>\s*", re.S)


def lift_captions(page: str) -> str:
    """Move each <caption> out of its own table and place it right after it.

    The wide audit tables need `overflow-x:auto`, but a caption inside a
    horizontally scrolling box is clipped at the right edge -- and these
    captions carry the footnote legend, i.e. the disclosure.

    Each table is processed IN PLACE. The first version of this function
    collected every caption and re-attached them to </table> tags in document
    order -- but a table with no <caption> (the four-arms table arrives via
    \captionof and has none) shifts the pairing, and the preregistration
    registry's caption ended up printed under the four-arms table.
    """
    def one(m):
        block = m.group(0)
        cm = CAP_RE.search(block)
        if not cm:
            return block
        return CAP_RE.sub("", block, count=1) + f'\n<p class="tbl-cap">{cm.group(1)}</p>'

    return TABLE_RE.sub(one, page)


def labels_from_aux(aux: Path) -> dict[str, str]:
    """label -> printed number, read from the BUILT aux (same numbers as the PDF)."""
    if not aux.exists():
        sys.exit(f"FAIL: {aux} not found -- build the paper before rendering HTML")
    out = {}
    for m in re.finditer(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}", aux.read_text(errors="replace")):
        out[m.group(1)] = m.group(2)
    return out


def _balanced_end(tex: str, start: int) -> int:
    """Index just past the '}' closing the group that opens at tex[start-1]=='{'."""
    depth, j = 1, start
    while j < len(tex) and depth:
        if tex[j] == "{" and tex[j - 1] != "\\":
            depth += 1
        elif tex[j] == "}" and tex[j - 1] != "\\":
            depth -= 1
        j += 1
    return j


def unwrap_balanced(tex: str, opener: str) -> str:
    r"""Delete a wrapper macro but keep its argument, e.g. \resizebox{..}{..}{X} -> X.

    Blanket-replacing the closing brace instead (\end{tabular}} -> \end{tabular})
    also eats the brace of an unrelated group such as {\small ... }, which
    unbalances the enclosing environment.
    """
    out, i, pat = [], 0, re.compile(opener)
    while True:
        m = pat.search(tex, i)
        if not m:
            out.append(tex[i:])
            return "".join(out)
        out.append(tex[i:m.start()])
        j = _balanced_end(tex, m.end())
        out.append(tex[m.end():j - 1])
        i = j


def strip_captionof(tex: str) -> str:
    r"""\captionof{table}{...} -> a bold lead-in, consuming the BALANCED group.

    A naive regex that drops only the opening brace leaves a stray '}' that
    unbalances the enclosing environment (pandoc then fails at \end{center}).
    """
    out, i = [], 0
    while True:
        m = re.compile(r"\\captionof\{(table|figure)\}\{").search(tex, i)
        if not m:
            out.append(tex[i:])
            return "".join(out)
        out.append(tex[i:m.start()])
        depth, j = 1, m.end()
        while j < len(tex) and depth:
            if tex[j] == "{" and tex[j - 1] != "\\":
                depth += 1
            elif tex[j] == "}" and tex[j - 1] != "\\":
                depth -= 1
            j += 1
        label = m.group(1).capitalize()
        out.append(f"\n\n\\noindent\\textbf{{{label}.}} " + tex[m.end():j - 1] + "\n\n")
        i = j


def normalize(tex: str, labels: dict[str, str], missing: set[str]) -> str:
    # $-$ is a LaTeX typographic minus; as math it renders with a trailing gap
    # ("$-$.047" -> "- .047" in every table cell). Use the Unicode minus.
    tex = tex.replace("$-$", "\u2212")
    # pandoc treats the {abstract} environment as metadata and DROPS its body
    # from the output (paper 2 wraps its abstract file in one; paper 1's is
    # bare text, which is why only paper 2's HTML lost its abstract).
    tex = tex.replace("\\begin{abstract}", "\\subsection*{Abstract}\n")
    tex = tex.replace("\\end{abstract}", "")
    # custom macros
    tex = tex.replace(r"\benchrows{}", "15").replace(r"\benchrows", "15")
    tex = tex.replace(r"\pp{}", "pp").replace(r"\pp", "pp")
    # cross-references -> the numbers the PDF prints
    def ref(m):
        k = m.group(1)
        if k not in labels:
            missing.add(k)
            return "??"
        return labels[k]
    tex = re.sub(r"\\ref\{([^}]+)\}", ref, tex)
    # figures: use the png siblings so the browser can render them
    tex = re.sub(r"\\includegraphics(\[[^\]]*\])?\{([A-Za-z0-9_\-]+)\}",
                 lambda m: r"\includegraphics{%s.png}" % m.group(2), tex)
    # pandoc models neither \resizebox nor \captionof
    tex = unwrap_balanced(tex, r"\\resizebox\{[^{}]*\}\{[^{}]*\}\{%?")
    tex = strip_captionof(tex)
    # figure* / table* behave as their unstarred forms here
    tex = tex.replace(r"\begin{figure*}", r"\begin{figure}").replace(r"\end{figure*}", r"\end{figure}")
    tex = tex.replace(r"\begin{table*}", r"\begin{table}").replace(r"\end{table*}", r"\end{table}")
    return tex


def build(paper: dict, outdir: Path) -> Path:
    root: Path = paper["root"]
    labels = labels_from_aux(root / f"{paper['entry']}.aux")
    order = re.findall(r"\\input\{sections/([^}]+)\}", (root / f"{paper['entry']}.tex").read_text())
    if not order:
        sys.exit(f"FAIL: no \\input{{sections/...}} found in {paper['entry']}.tex")

    missing: set[str] = set()
    body = "\n\n".join(normalize((root / "sections" / f"{n}.tex").read_text(), labels, missing)
                       for n in order)
    if missing:
        sys.exit(f"FAIL: {paper['key']} references labels absent from the aux "
                 f"(HTML would disagree with the PDF): {sorted(missing)}")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "body.tex").write_text(body)
        for png in FIGDIR.glob("*.png"):
            shutil.copy(png, td / png.name)
        (td / "style.css").write_text(CSS)
        header = (f'<h1>{html.escape(paper["title"])}</h1>\n'
                  f'<p class="sub">{html.escape(paper["sub"])}</p>\n'
                  f'<p class="meta">Rendered from the built LaTeX sources by '
                  f'scripts/make_html.py. Cross-reference numbers are read from '
                  f'{paper["entry"]}.aux, so they match the PDF.</p>')
        (td / "header.html").write_text(header)
        cmd = ["pandoc", "body.tex", "--from", "latex", "--to", "html5",
               "--standalone", "--embed-resources", "--mathml",
               "--citeproc", "--bibliography", str(paper["bib"]),
               "--css", "style.css", "--include-before-body", "header.html",
               "--shift-heading-level-by", "1",
               "--toc", "--toc-depth", "2",
               # pagetitle (not title): sets <title> without emitting a second
               # visible <h1> on top of the one in header.html
               "--metadata", f"pagetitle={paper['title']}",
               "--metadata", "lang=en",
               "-o", "out.html"]
        r = subprocess.run(cmd, cwd=td, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"FAIL: pandoc on {paper['key']}\n{r.stderr[:3000]}")
        if r.stderr.strip():
            for line in r.stderr.strip().splitlines()[:8]:
                print(f"   pandoc: {line}")
        dest = outdir / paper["out"]
        dest.write_text(lift_captions((td / "out.html").read_text()))
        return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path.home() / "Downloads"))
    a = ap.parse_args()
    outdir = Path(a.out).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    for paper in PAPERS:
        dest = build(paper, outdir)
        n = len(dest.read_bytes())
        txt = re.sub(r"<[^>]+>", " ", dest.read_text())
        print(f"{paper['key']}: {dest}  ({n/1024:.0f} KB, ~{len(txt.split()):,} words, "
              f"{dest.read_text().count('<img ')} figures, "
              f"{dest.read_text().count('<table')} tables)")
        if "??" in txt:
            print(f"   WARNING: '??' present in {dest.name} -- an unresolved reference survived")


if __name__ == "__main__":
    main()
