#!/bin/bash
# Paper 2 (HindsightBench) build + compliance gate. Mirrors the paper-1 gate
# philosophy: every check is an external anchor, not a self-assessment.
# Exits non-zero on any failure. Run from anywhere.
set -euo pipefail

LATEX_DIR="$(cd "$(dirname "$0")/../paper2/latex" && pwd)"
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${HINDSIGHT_PY:-python3}"
cd "$LATEX_DIR"

pdflatex -interaction=nonstopmode main.tex > /dev/null
bibtex main > /dev/null
pdflatex -interaction=nonstopmode main.tex > /dev/null
pdflatex -interaction=nonstopmode main.tex > /dev/null

echo "--- paper-2 compliance checks ---"

# 1. zero latex errors
errs=$(grep -c "^!" main.log || true)
[ "$errs" -eq 0 ] || { echo "FAIL: main.log has $errs errors"; exit 1; }
echo "OK: 0 latex errors ($(pdfinfo main.pdf | awk '/^Pages/{print $2}') pages)"

# 2. citations: none undefined, none uncited
if grep -q "Warning: Citation.*undefined" main.log; then
  echo "FAIL: undefined citations"; grep "Warning: Citation" main.log | head; exit 1
fi
$PY - <<'PY'
import re, pathlib, sys
used = set()
for f in pathlib.Path("sections").glob("*.tex"):
    for m in re.finditer(r"\\cite[pt]?\*?(?:\[[^]]*\])?\{([^}]*)\}", f.read_text()):
        used.update(k.strip() for k in m.group(1).split(","))
defined = set(re.findall(r"@\w+\{([^,]+),", pathlib.Path("references.bib").read_text()))
if used - defined: sys.exit(f"FAIL: cited but not in bib: {sorted(used-defined)}")
if defined - used: sys.exit(f"FAIL: bib entries never cited: {sorted(defined-used)}")
print(f"OK: citations complete ({len(used)} keys)")
PY

# 3. no Type 3 fonts
pdffonts main.pdf | grep -q "Type 3" && { echo "FAIL: Type 3 font"; exit 1; }
echo "OK: no Type 3 fonts"

# 4. leaderboard rows must match the frozen row jsons (drift gate)
$PY "$SCRIPTS_DIR/make_bench_rows.py" --check
echo "OK: generated table blocks match frozen row jsons"

# 5. unresolved refs
if grep -q "Warning: Reference.*undefined" main.log; then
  echo "FAIL: undefined \\ref"; exit 1
fi
echo "OK: no undefined references"

# 6. upload blockers: placeholders must be gone before arXiv (warn-only for drafts)
if grep -q "to be set before arXiv upload" main.tex; then
  echo "WARN: author-line placeholder still present (blocker for arXiv upload, fine for drafts)"
fi
if grep -q "set before arXiv upload" ../../LICENSE; then
  echo "WARN: LICENSE copyright holder placeholder still present"
fi

echo "--- all paper-2 checks passed; main.pdf in $LATEX_DIR ---"
