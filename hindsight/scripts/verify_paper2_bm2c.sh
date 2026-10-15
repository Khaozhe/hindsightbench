#!/usr/bin/env bash
# Gate for paper 2's BM-2c / G2 / noise-floor material: every generated table matches the frozen rows,
# frozen preregistrations and scripts still hash to their freeze records, the paper compiles cleanly,
# and open TODO markers are counted (they must be zero before submission).
set -uo pipefail
H="$(cd "$(dirname "$0")/.." && pwd)"; cd "$H"
PY="${PY:-/opt/homebrew/Caskroom/miniconda/base/envs/macrochain/bin/python}"; fail=0
step() { echo "== $1"; }
step "generated tables"
"$PY" scripts/make_bench_rows.py --check 2>/dev/null | tail -1 || fail=1
"$PY" scripts/make_bm2c_table.py --check 2>/dev/null | tail -1 || fail=1
"$PY" scripts/make_g2_table.py --check 2>/dev/null && echo "check OK: tab_g2_wholepanel.tex" || { echo "CHECK FAIL: tab_g2_wholepanel.tex"; fail=1; }
step "freeze hashes (document and, where frozen, script)"
for f in prereg/BM2c_freeze.json prereg/BM2c_*_freeze.json; do
  "$PY" - "$f" <<'PYF' || fail=1
import json, sys, hashlib
from pathlib import Path
f = Path(sys.argv[1]); d = json.loads(f.read_text()); ok = True
doc = f.parent / d["file"]
h = hashlib.sha256(doc.read_bytes()).hexdigest()
ok &= h == d["sha256"]
msg = f"{f.name}: doc {'ok' if h == d['sha256'] else 'MISMATCH'}"
impl = (d["script"], d.get("script_sha256")) if d.get("script") else \
       ((d["implementation"]["file"], d["implementation"]["sha256"]) if isinstance(d.get("implementation"), dict) else (None, None))
if impl[0] and impl[1]:
    sp = f.parent.parent / impl[0]
    hs = hashlib.sha256(sp.read_bytes()).hexdigest(); ok &= hs == impl[1]
    msg += f", script {impl[0].split('/')[-1]} {'ok' if hs == impl[1] else 'MISMATCH'}"
print(msg); sys.exit(0 if ok else 1)
PYF
done
step "compile"
cd paper2/latex
pdflatex -interaction=nonstopmode main.tex >/dev/null; bibtex main >/dev/null; pdflatex -interaction=nonstopmode main.tex >/dev/null; pdflatex -interaction=nonstopmode main.tex >/dev/null
e=$(grep -c "^!" main.log); u=$(grep -c "undefined" main.log)
echo "errors=$e undefined-refs=$u pages=$(pdfinfo main.pdf | awk '/^Pages/{print $2}')"; [ "$e" -eq 0 ] && [ "$u" -eq 0 ] || fail=1
refs=$(for i in $(seq 1 "$(pdfinfo main.pdf | awk '/^Pages/{print $2}')"); do pdftotext -f $i -l $i main.pdf - | grep -q "^References$" && echo $i; done | head -1)
late=$(for i in $(seq "$refs" "$(pdfinfo main.pdf | awk '/^Pages/{print $2}')"); do pdftotext -f $i -l $i main.pdf - | grep -o "^Table [0-9]*:\|^Figure [0-9]*:"; done | tr '\n' ' ')
echo "references start p$refs; floats after references: ${late:-none}"; [ -z "$late" ] || fail=1
step "open TODO markers in sections (must be 0 before submission)"
grep -n "TODO" sections/*.tex || echo "none"
echo; [ $fail -eq 0 ] && echo "VERIFY: gates pass (TODO count above is reported, not gated)" || { echo "VERIFY: FAILED"; exit 1; }
