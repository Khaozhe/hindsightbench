#!/usr/bin/env bash
# Pack paper 2 for arXiv upload. Reproducible replacement for the by-hand
# packing used for v1/v2.
#
# The trap this script exists to prevent: main.tex points \graphicspath at
# ../../paper/figures/, which does not exist in a flat arXiv tarball. Locally
# that still compiles -- LaTeX silently falls back to the working directory --
# so a bad tarball builds clean on this machine and loses every figure on
# arXiv. The script rewrites graphicspath to {{./}}, then *verifies* by
# compiling in the staging dir and failing on any missing-file warning.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../paper2/latex"
FIGS="$HERE/../paper/figures"
STAGE="${1:-$(mktemp -d)}/arxiv_p2"
OUT="${2:-$HOME/Downloads/hindsight_arxiv_v2.tar.gz}"

rm -rf "$STAGE"; mkdir -p "$STAGE/sections"

cp "$SRC/main.tex" "$STAGE/"
cp "$SRC"/sections/*.tex "$STAGE/sections/"
[ -f "$SRC/main.bbl" ] || { echo "FAIL: main.bbl missing; build the paper first"; exit 1; }
cp "$SRC/main.bbl" "$STAGE/"

# figures actually referenced, copied flat
# (macOS ships bash 3.2 -- no mapfile)
USED=$(grep -ho '\\includegraphics\[[^]]*\]{[^}]*}' "$STAGE"/sections/*.tex "$STAGE/main.tex" \
       | sed 's/.*{\(.*\)}/\1/' | sort -u)
[ -n "$USED" ] || { echo "FAIL: no \\includegraphics found"; exit 1; }
for f in $USED; do
  cp "$FIGS/$f.pdf" "$STAGE/$f.pdf" || { echo "FAIL: figure $f.pdf not found"; exit 1; }
done
echo "figures staged: $(echo $USED | tr '\n' ' ')"

# flat tarball => graphicspath must be the working directory
perl -pi -e 's|\\graphicspath\{\{[^}]*\}\}|\\graphicspath{{./}}|' "$STAGE/main.tex"
grep -q '\\graphicspath{{./}}' "$STAGE/main.tex" || { echo "FAIL: graphicspath not rewritten"; exit 1; }

# verify in the staging dir: this is what arXiv will see
( cd "$STAGE" && pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || true
  pdflatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || true )
if grep -qi "File .* not found\|Missing figure\|LaTeX Warning: File" "$STAGE/main.log"; then
  echo "FAIL: missing-file warning in staging build:"; grep -i "not found\|LaTeX Warning: File" "$STAGE/main.log" | head; exit 1
fi
[ -f "$STAGE/main.log" ] || { echo "FAIL: no staging main.log -- the verify step did not run"; exit 1; }
[ -f "$STAGE/main.pdf" ] || { echo "FAIL: staging build produced no PDF"; exit 1; }
# unresolved cross-refs / citations would ship silently otherwise
# NB: grep exits 1 on zero matches; under `set -e -o pipefail` that would kill
# the script silently at exactly the "everything is fine" case. Hence || true.
qq=$(pdftotext "$STAGE/main.pdf" - | { grep -o '??' || true; } | wc -l | tr -d ' ')
cq=$(pdftotext "$STAGE/main.pdf" - | { grep -o '\[?\]' || true; } | wc -l | tr -d ' ')
[ "$qq" = "0" ] || { echo "FAIL: $qq unresolved cross-references (??) in staging build"; exit 1; }
[ "$cq" = "0" ] || { echo "FAIL: $cq unresolved citations ([?]) -- main.bbl is stale"; exit 1; }
pages=$(pdfinfo "$STAGE/main.pdf" | awk '/^Pages/{print $2}')
imgs=$(pdfimages -list "$STAGE/main.pdf" 2>/dev/null | tail -n +3 | wc -l | tr -d ' ')
echo "staging build OK: $pages pages, $imgs embedded images"
[ "$pages" -gt 0 ] || { echo "FAIL: no pages"; exit 1; }

# arXiv wants no wrapper dir and no AppleDouble junk
( cd "$STAGE" && rm -f main.aux main.log main.out main.pdf main.fls main.fdb_latexmk \
  && COPYFILE_DISABLE=1 tar czf "$OUT" ./ )
echo "wrote $OUT"
echo "sha256: $(shasum -a 256 "$OUT" | cut -c1-8)  size: $(du -h "$OUT" | cut -f1)"
tar tzf "$OUT" | grep -c . | xargs echo "entries:"
tar tzf "$OUT" | grep -E "^\./[^/]+/" | grep -v "^\./sections/" && { echo "FAIL: unexpected wrapper dir"; exit 1; } || true
