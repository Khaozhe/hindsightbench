#!/bin/bash
# AAAI-27 submission builder + compliance gate.
#
# Produces, in hindsight/paper/latex/:
#   main_submission.pdf          main paper (7pp content + references = 8pp)
#   supplementary.pdf            technical appendix A-D
#   ReproducibilityChecklist.pdf filled AAAI checklist (standalone build)
#   main.pdf                     combined working document (not for submission)
#
# Metadata: SOURCE_DATE_EPOCH pins CreationDate/ModDate to a UTC timestamp, so
# no local timezone (+08 = geographic clue) leaks into the double-blind PDFs.
#
# Exits non-zero if any compliance check fails. Run from anywhere.
set -euo pipefail

LATEX_DIR="$(cd "$(dirname "$0")/../paper/latex" && pwd)"
cd "$LATEX_DIR"

# 2026-07-21 00:00:00 UTC (abstract deadline day; any fixed UTC instant works).
# TZ=UTC is required too: pdfTeX formats the epoch in the LOCAL zone, which would
# re-introduce the +08 geographic clue.
export SOURCE_DATE_EPOCH=$(python3 -c "import calendar; print(calendar.timegm((2026,7,21,0,0,0)))")
export FORCE_SOURCE_DATE=1
export TZ=UTC

build () {  # build <jobname> <runs-bibtex: yes|no>
  pdflatex -interaction=nonstopmode "$1.tex" > /dev/null
  if [ "$2" = yes ]; then bibtex "$1" > /dev/null; fi
  pdflatex -interaction=nonstopmode "$1.tex" > /dev/null
  pdflatex -interaction=nonstopmode "$1.tex" > /dev/null
  local errs
  errs=$(grep -c "^!" "$1.log" || true)
  [ "$errs" -eq 0 ] || { echo "FAIL: $1.log has $errs errors"; exit 1; }
  echo "built $1.pdf ($(pdfinfo "$1.pdf" | awk '/^Pages/{print $2}') pages, 0 errors)"
}

build main_submission yes
build supplementary yes
build ReproducibilityChecklist no
build main yes   # keep the combined working PDF in sync

echo "--- compliance checks ---"

# 1. page budget: content ends on p7, references start on p8, total 8 pages
total=$(pdfinfo main_submission.pdf | awk '/^Pages/{print $2}')
[ "$total" -le 9 ] || { echo "FAIL: main_submission.pdf has $total pages (>9)"; exit 1; }
p7=$(pdftotext -f 7 -l 7 main_submission.pdf - | tr '\n' ' ')
p8=$(pdftotext -f 8 -l 8 main_submission.pdf - 2>/dev/null | tr '\n' ' ' || true)
# Two compliant layouts: (a) content ends p7, refs start p8; (b) content ends on
# p7 and refs flow directly after on the same page (AAAI camera-ready style),
# continuing on p8. Either way: marker on p7, refs heading on p7-after-marker or
# p8-top, and p8 carries no technical content.
python3 - <<'PY'
import subprocess, re, sys
def page(n):
    return subprocess.run(["pdftotext","-f",str(n),"-l",str(n),"main_submission.pdf","-"],
                          capture_output=True, text=True).stdout
p7, p8 = page(7), page(8)
MARK = "one-command regeneration"
if MARK not in p7.replace("\n", " "):
    sys.exit("FAIL: content does not end on p7")
flat7 = p7.replace("\n", " ")
if "References" in flat7:
    if flat7.index("References") < flat7.index(MARK):
        sys.exit("FAIL: References heading precedes end of content on p7")
elif not p8.strip().startswith("References"):
    sys.exit("FAIL: References heading found on neither p7 (after content) nor p8 top")
if MARK in p8.replace("\n", " "):
    sys.exit("FAIL: content marker also on p8")
# section headings are single-digit ("9. Limitations..."); reference lines can
# start with a wrapped 4-digit year ("2025. Total Recall...") - don't match those
if re.search(r"(?m)^\d\.\s+[A-Z]", p8) or "Reproducibility." in p8:
    sys.exit("FAIL: technical content on p8")
print("OK: content ends p7; references flow legally; p8 is references-only")
PY
[ $? -eq 0 ] || exit 1
echo "OK: page budget ($total pages total)"

# 2. no Type 3 fonts (AAAI hard reject)
for f in main_submission.pdf supplementary.pdf ReproducibilityChecklist.pdf; do
  if pdffonts "$f" | grep -q "Type 3"; then echo "FAIL: Type 3 font in $f"; exit 1; fi
done
echo "OK: no Type 3 fonts"

# 3. metadata: no local timezone in CreationDate/ModDate
for f in main_submission.pdf supplementary.pdf ReproducibilityChecklist.pdf; do
  if pdfinfo "$f" | grep -E "^(Creation|Mod)Date" | grep -qE "\+0[0-9]|\+1[0-9]"; then
    echo "FAIL: local timezone in $f metadata"; pdfinfo "$f" | grep Date; exit 1
  fi
done
echo "OK: PDF dates carry no local timezone"

# 4. forbidden packages / commands (AAAI kit tables 1-2, common offenders)
if grep -nE '\\usepackage(\[[^]]*\])?\{(geometry|fullpage|times|helvet|courier|hyperref|navigator|pgfplots|authblk|balance|savetrees|setspace|titlesec|tocbibind|ulem|CJK)\}' \
     main_submission.tex supplementary.tex sections/*.tex; then
  echo "FAIL: forbidden package"; exit 1
fi
if grep -nE '\\(vspace|vskip)\{?-' sections/*.tex main_submission.tex supplementary.tex; then
  echo "FAIL: negative vspace/vskip"; exit 1
fi
echo "OK: no forbidden packages, no negative vspace"

# 5. preamble sync: the three entry files copy the same preamble by hand;
#    catch divergence (documentclass .. last unicode declare must be identical)
python3 - <<'PY'
import re, sys
def region(path):
    s = open(path).read()
    a = s.index(r"\documentclass")
    b = s.rindex(r"\DeclareUnicodeCharacter")
    b = s.index("\n", b)
    return s[a:b]
r0 = region("main.tex")
for f in ("main_submission.tex", "supplementary.tex"):
    if region(f) != r0:
        sys.exit(f"FAIL: preamble of {f} diverged from main.tex")
print("OK: preambles of main/main_submission/supplementary identical")
PY

# 6. literal cross-document figure number: section 7.1 says "Figure 4" for the
#    appendix rent figure; both builds must still number it 4 (a new main-text
#    figure would silently break this)
for f in supplementary.pdf main.pdf; do
  pdftotext "$f" - | tr '\n' ' ' | grep -q "Figure 4: Contamination rent" \
    || { echo "FAIL: rent figure is not 'Figure 4' in $f (literal ref in 07_exp4 now wrong)"; exit 1; }
done
grep -q "Figure~4, Appendix~D" sections/07_exp4_pipeline.tex \
  || { echo "FAIL: literal appendix figure reference missing in 07_exp4"; exit 1; }
echo "OK: literal 'Figure 4' cross-document reference consistent"

# 7. citation completeness: every \cite key defined, no unused bib entries
python3 - <<'PY'
import re, pathlib, sys
used = set()
for f in pathlib.Path("sections").glob("*.tex"):
    for m in re.finditer(r"\\cite[pt]?\*?(?:\[[^]]*\])?\{([^}]*)\}|\\citealp\{([^}]*)\}", f.read_text()):
        for g in m.groups():
            if g: used.update(k.strip() for k in g.split(","))
defined = set(re.findall(r"@\w+\{([^,]+),", pathlib.Path("../references.bib").read_text()))
if used - defined: sys.exit(f"FAIL: cited but not in bib: {sorted(used-defined)}")
if defined - used: sys.exit(f"FAIL: bib entries never cited: {sorted(defined-used)}")
print(f"OK: citations complete ({len(used)} keys, no missing, no unused)")
PY

# 8. anonymity: no author-identifying strings in sources or rendered PDFs
if grep -rniE "haozhe|khaozhe" sections/ main_submission.tex supplementary.tex; then
  echo "FAIL: identifying string in sources"; exit 1
fi
for f in main_submission.pdf supplementary.pdf; do
  if pdftotext "$f" - | grep -qiE "haozhe"; then echo "FAIL: identifying string in $f"; exit 1; fi
done
echo "OK: anonymity scan clean"

echo "--- all submission checks passed; artifacts in $LATEX_DIR ---"
