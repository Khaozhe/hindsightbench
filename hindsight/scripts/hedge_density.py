"""Qualifier/negation density gate for paper prose (see ~/.claude/CLAUDE.md, no defensive writing).

Counts hedge and negation markers per 1,000 words in LaTeX sections, for a git revision or the
working tree, so a rewrite can be checked against its baseline instead of judged by feel.

Usage:
  python hedge_density.py --files a.tex b.tex [--rev a3c9b8787] [--label NAME]
  python hedge_density.py --compare BASE_REV:path1,path2 NEW:path1,path2 [--max-ratio 1.0]
NEW may be WORKTREE. With --max-ratio the script exits 1 if new density > ratio * base density.
"""
import argparse, re, subprocess, sys

HEDGE = {
    "not": r"\bnot\b", "cannot": r"\bcannot\b", "do(es) not": r"\bdoes not\b|\bdo not\b",
    "bound": r"\bbound(ed|s)?\b", "exploratory/post hoc": r"\bexploratory\b|post[- ]hoc|post-freeze",
    "only": r"\bonly\b", "caveat/caution": r"\bcaveat|\bcaution", "unidentified": r"\bunidentified\b|\bnot identified\b|\bnot isolated\b",
    "consistent with": r"\bconsistent with\b", "may/might/suggest": r"\bmay\b|\bmight\b|\bsuggest",
}


def read(rev, path):
    if rev in (None, "WORKTREE"):
        return open(path).read()
    return subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, text=True, check=True).stdout


def clean(t):
    t = re.sub(r"(?m)(?<!\\)%.*$", "", t)
    t = re.sub(r"\\(cite|ref|label|eqref)\{[^}]*\}", "", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", t)
    return re.sub(r"[{}$]", "", t)


def density(rev, paths):
    body = " ".join(clean(read(rev, p)) for p in paths)
    words = len(body.split())
    counts = {k: len(re.findall(v, body, flags=re.I)) for k, v in HEDGE.items()}
    return words, counts, 1000 * sum(counts.values()) / max(words, 1)


def report(label, words, counts, d):
    print(f"{label:<28} words {words:>6}  hedges/1k {d:5.1f}  " + " ".join(f"{k}={v}" for k, v in counts.items() if v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--rev")
    ap.add_argument("--label", default="")
    ap.add_argument("--compare", nargs=2, metavar=("BASE", "NEW"))
    ap.add_argument("--max-ratio", type=float)
    a = ap.parse_args()
    if a.compare:
        res = []
        for spec in a.compare:
            rev, paths = spec.split(":", 1)
            w, c, d = density(rev, paths.split(","))
            report(rev, w, c, d)
            res.append(d)
        if a.max_ratio is not None and res[1] > a.max_ratio * res[0]:
            print(f"FAIL: new density {res[1]:.1f} > {a.max_ratio} x base {res[0]:.1f}")
            sys.exit(1)
        print("PASS" if a.max_ratio is not None else "")
        return
    w, c, d = density(a.rev, a.files)
    report(a.label or (a.rev or "WORKTREE"), w, c, d)


if __name__ == "__main__":
    main()
