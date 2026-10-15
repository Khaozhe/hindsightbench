#!/usr/bin/env python
"""Six-type manuscript lint (from the AAAI-version review taxonomy). Reports by type so each can be
fixed as a batch pass. Usage: paper_lint.py <latex dir> [--pdf main.pdf]
  T1 meta-text leakage   T2 over-defensiveness   T3 narrative inversion (heuristic)
  T4 notation/codename hygiene   T5 inline typos/math   T6 float drift (needs --pdf)
"""
from __future__ import annotations
import re, sys, subprocess
from pathlib import Path

T1 = [r"\breviewer", r"\bearlier (version|draft|rounds?|§|\\S)", r"\bretract", r"\bpublished (E2|E3|cell|value|row)\b",
      r"\binitially frozen\b", r"\bpredated\b", r"\bdisclosed(,| as| rather)", r"\bwhat changed\b", r"\bwe had not\b",
      r"\bcould not be reproduced\b", r"\bnot corrected\b", r"\bsuperseded\b", r"\bcorrection\b", r"\bchangelog\b"]
FORBIDDEN = r"\b(reviewer|earlier (draft|version)|previous version|draft|retract\w*|defect|wrong|deferred|selection|firewall|unversioned|published (E2|E3|cell|value))\b"
GLUED_MATH = r"\$[a-zA-Z0-9]+\$[a-zA-Z]|[a-zA-Z,;:]\$[a-zA-Z0-9]+\$"
T2 = [r"\bnot because\b", r"\bby construction, not\b", r"\bso the level is not\b", r"\bwe do not claim\b",
      r"\bhonest(ly)? reading\b", r"\bwe (concede|admit)\b", r"\bno \w+ was computed and then discarded\b",
      r"\boverstates?\b", r"\bnot (inconvenient|cherry)", r"\bto be clear\b", r"\bwe (do|did) not set out\b"]
HEDGE_IN_PAREN = r"\(([^()]*\b(not|cannot|no |lower bound|only|bound|unidentified|post hoc|disclosed)[^()]*)\)"
CODENAMES = r"\b(BM-[12][a-d]?|GD-[12]|KT-1|FM-1[a-g]?|FM-2|ST-1|addend(um|a) [A-J])\b"
ACRO = r"\b([A-Z]{2,6})\b"
ACRO_IGNORE = {"LLM","LLMS","API","APIS","JSON","GPU","GPUS","CPU","USD","CNY","PDF","URL","DOI","SHA","CSV","MIT","US","UK","NYC","COVID","GB","HK","SG","JP","IT","ES","IN","AU","MOE","PP","CI","CIS","ID","OK","AAAI","ICLR","NBER","FRED","ALFRED","AWQ","INT","FP","BF","HAC","GFC","MAX","DPO","SFT","RLVR","RLHF","RAI","SPX","VIX","IC","NA","AND","OR","THE","II","III"}

def tex_files(d: Path):
    main = (d / "main.tex").read_text()
    order = re.findall(r"\\input\{sections/([^}]+)\}", main)
    # verbatim-prompt and generated-table files carry literal strings, not prose
    order = [f for f in order if not (f.startswith("A2_spec") or f.startswith("A3_tables") or f.startswith("tab_"))]
    return [d / "sections" / (f if f.endswith(".tex") else f + ".tex") for f in order]

def strip(t):
    t = re.sub(r"(?m)(?<!\\)%.*$", "", t)
    return t

def scan(files):
    out = {k: [] for k in ("T1", "T2", "T3", "T4", "T5", "FIRST")}
    defined, used_first = set(), {}
    labels = {}
    for f in files:
        txt = strip(f.read_text())
        name = f.name
        for i, line in enumerate(txt.splitlines(), 1):
            for rx in T1:
                if re.search(rx, line, re.I): out["T1"].append((name, i, re.search(rx, line, re.I).group(0), line.strip()[:100])); break
            for rx in T2:
                if re.search(rx, line, re.I): out["T2"].append((name, i, re.search(rx, line, re.I).group(0), line.strip()[:100])); break
            if name.startswith(("00_", "01_")):
                for m in re.finditer(HEDGE_IN_PAREN, line, re.I):
                    out["T2"].append((name, i, "paren-hedge", m.group(0)[:100]))
            if re.search(FORBIDDEN, line, re.I) and not name.startswith("A1_"):
                out["T1"].append((name, i, "forbidden word: " + re.search(FORBIDDEN, line, re.I).group(0), line.strip()[:100]))
            if re.search(GLUED_MATH, line):
                out["T5"].append((name, i, "glued math variable", line.strip()[:100]))
            # guardrail 3: punctuation cap -- a sentence with a dash pair AND (semicolon or parenthesis), or 2+ parens
            # T5
            if re.search(r"(?<![\\$\w{])[A-Za-z]+_[A-Za-z]", re.sub(r"\$[^$]*\$|\\texttt\{[^}]*\}|\\(label|ref|cite|input|url|href)\{[^}]*\}|\\[a-zA-Z]+", "", line)):
                out["T5"].append((name, i, "bare underscore outside math", line.strip()[:100]))
            if re.search(r"\b(\w+) \1\b", line) and not re.search(r"\b(that that|had had)\b", line):
                out["T5"].append((name, i, "doubled word", line.strip()[:100]))
            if re.search(r"[a-z];[a-z]|[a-z]\)[a-z]|\w\.\w{3,}\b(?!\.)", re.sub(r"\$[^$]*\$|\\[a-zA-Z]+\{[^}]*\}|https?://\S+|\b\w+\.(py|json|jsonl|tex|md|csv)\b", "", line)) and not re.search(r"\d\.\d", line):
                out["T5"].append((name, i, "glued tokens", line.strip()[:100]))
            # T4 codenames in body (outside parentheses and \texttt)
            body = re.sub(r"\([^)]*\)|\\texttt\{[^}]*\}|\\label\{[^}]*\}|\\ref\{[^}]*\}", "", line)
            for m in re.finditer(CODENAMES, body):
                out["T4"].append((name, i, f"codename in body: {m.group(0)}", line.strip()[:100]))
            for m in re.finditer(r"\\label\{([^}]+)\}", line):
                labels.setdefault(m.group(1), []).append(f"{name}:{i}")
            # acronyms
            for m in re.finditer(r"\(([A-Z]{2,6})\)", line):
                defined.add(m.group(1))
            for m in re.finditer(ACRO, re.sub(r"\\[a-zA-Z]+|\\(ref|label|cite)\{[^}]*\}", "", line)):
                a = m.group(1)
                if a not in ACRO_IGNORE and a not in used_first and a not in defined:
                    used_first[a] = (name, i, line.strip()[:80])
        # guardrail 3: sentence punctuation overload -- prose parentheticals (>=3 words, not a CI/number),
        # dash pairs and semicolons in one sentence; table/figure environments skipped
        prose = re.sub(r"\\begin\{(table\*?|figure\*?|tabular)\}.*?\\end\{\1\}", " ", txt, flags=re.S)
        prose = re.sub(r"\\(cite|ref|label|citep|citet|S)\{[^}]*\}|\$[^$]*\$|\[[^\]]*\]", "X", prose)
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z\\])", prose):
            dash = sent.count("---"); semi = sent.count(";")
            ppar = sum(1 for m in re.finditer(r"\(([^()]*)\)", sent) if len(re.findall(r"[A-Za-z]{3,}", m.group(1))) >= 3)
            words = len(sent.split())
            if (dash >= 2 and semi >= 1 and ppar >= 1) or ppar >= 2 or (dash >= 2 and ppar >= 1 and words > 45):
                out["T3"].append((name, 0, f"punctuation overload (dash-pairs {dash//2}, ; {semi}, prose-parens {ppar}, {words}w)", " ".join(sent.split())[:120]))
        # guardrail 5.4: first-sentence audit -- print every section/subsection first sentence for a human read
        for m in re.finditer(r"\\(sub)?section\{([^}]*)\}[^\n]*\n+((?:[^\n]+\n)*?)", txt):
            body_after = txt[m.end(0):m.end(0)+600]
            first = re.split(r"(?<=[.!?])\s", re.sub(r"\\(label|ref)\{[^}]*\}", "", body_after).strip(), 1)[0]
            flag = "NEG" if re.search(r"\b(not|cannot|no|neither|fail|unidentified)\b", first, re.I) else "ok"
            out.setdefault("FIRST", []).append((name, flag, m.group(2), first[:120]))
        # T3 heuristic: \paragraph first sentence negative / exception-first
        for m in re.finditer(r"\\paragraph\{([^}]*)\}\s*([^.]*\.)", txt):
            head, first = m.group(1), m.group(2)
            if re.search(r"\b(not|cannot|no|neither|unidentified|fail)\b", head + " " + first, re.I) or re.match(r"\s*(Because|Although|While|Before|Despite)\b", first):
                out["T3"].append((name, 0, "negative/exception-first paragraph", (head + ": " + first)[:110]))
    for a, (n, i, l) in used_first.items():
        if a not in defined:
            out["T4"].append((n, i, f"acronym never expanded: {a}", l))
    for lab, where in labels.items():
        if len(where) > 1:
            out["T4"].append((where[0].split(":")[0], 0, f"duplicate label {lab}", ", ".join(where)))
    return out

def floats(pdf: Path):
    """T6: caption page vs first reference page, and near-empty pages."""
    txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    pages = txt.split("\f")
    rows = []
    caps, refs = {}, {}
    for p, t in enumerate(pages, 1):
        for m in re.finditer(r"^\s*(Table|Figure) (\d+):", t, re.M):
            caps.setdefault((m.group(1), m.group(2)), p)
        for m in re.finditer(r"(Table|Figure|Fig\.) ?(\d+)\b", t):
            k = ("Figure" if m.group(1).startswith("Fig") else "Table", m.group(2))
            refs.setdefault(k, p)
        words = len(t.split())
        if 0 < words < 120 and p < len(pages) - 1:
            rows.append(("near-empty page", f"page {p}: {words} words"))
    for k, cp in caps.items():
        rp = refs.get(k)
        if rp is not None and abs(cp - rp) >= 2:
            rows.append((f"{k[0]} {k[1]}", f"caption on p.{cp}, first reference on p.{rp} (drift {cp-rp:+d})"))
    return rows

def main():
    d = Path(sys.argv[1])
    pdf = Path(sys.argv[sys.argv.index("--pdf") + 1]) if "--pdf" in sys.argv else None
    files = tex_files(d)
    out = scan(files)
    names = {"T1": "meta-text leakage", "T2": "over-defensiveness", "T3": "narrative inversion (heuristic)",
             "T4": "notation / codename hygiene", "T5": "inline typos / math"}
    for k in ("T1", "T2", "T3", "T4", "T5"):
        print(f"\n== {k} {names[k]}: {len(out[k])}")
        for n, i, what, line in out[k]:
            print(f"  {n}:{i} [{what}] {line}")
    print(f"\n== First-sentence audit (guardrail 5.4): read these in order; NEG = negative/failure-first")
    for n, flag, head, first in out["FIRST"]:
        print(f"  [{flag}] {n} / {head}: {first}")
    neg_ai = sum(1 for n, i, w, l in out["T2"] if n.startswith(("00_", "01_")))
    print(f"\n== Abstract/intro defense quota (guardrail 2): {neg_ai} parenthetical hedges (target 0)")
    if pdf and pdf.exists():
        fl = floats(pdf)
        print(f"\n== T6 float drift / layout: {len(fl)}")
        for a, b in fl:
            print(f"  {a}: {b}")

if __name__ == "__main__":
    main()
