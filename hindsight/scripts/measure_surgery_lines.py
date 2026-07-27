"""POST-FREEZE EXPLORATORY (2026-07-25, design-review response).

Measure the printed extent (lines / points / column-fraction) of three
candidate-surgery regions in hindsight/paper/latex/main_submission.pdf:

  (a) subsection 8.3  "The trigger tracks training generation, not scale"
  (b) the VIX micro-arm sentences inside 5.2
  (c) subsection 7.3  (prose + the aggregator ablation table + its caption/note)

Method: pdftotext -bbox-layout gives every word's bounding box in PDF points.
Words are bucketed into text lines by their yMin (rounded), and into left /
right column by the line's xMin (page is 612pt wide; the two-column body
runs 54..292.5 (left) and 319.5..558 (right)).  A region is delimited by an
anchor word-sequence at its start and at its end; the measurement is the set
of lines whose (column, y) falls inside that span, plus the leading/trailing
partial-line fractions computed from x-extents.

READ-ONLY: parses the built PDF, writes nothing except stdout.
"""
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

PDF = Path("REPO_ROOT/hindsight/paper/latex/main_submission.pdf")
NS = "{http://www.w3.org/1999/xhtml}"

LEFT_X0, LEFT_X1 = 54.0, 292.5
RIGHT_X0, RIGHT_X1 = 319.5, 558.0
COLW = LEFT_X1 - LEFT_X0  # 238.5pt


def load(page):
    out = subprocess.run(
        ["pdftotext", "-bbox-layout", "-f", str(page), "-l", str(page), str(PDF), "-"],
        capture_output=True, text=True, check=True).stdout
    root = ET.fromstring(out)
    lines = []
    for ln in root.iter(NS + "line"):
        words = [(float(w.get("xMin")), float(w.get("xMax")), w.text or "")
                 for w in ln.findall(NS + "word")]
        if not words:
            continue
        y0, y1 = float(ln.get("yMin")), float(ln.get("yMax"))
        x0, x1 = float(ln.get("xMin")), float(ln.get("xMax"))
        col = "L" if x0 < 300 else "R"
        lines.append(dict(page=page, col=col, y0=y0, y1=y1, x0=x0, x1=x1,
                          text=" ".join(w[2] for w in words), words=words))
    lines.sort(key=lambda d: (0 if d["col"] == "L" else 1, d["y0"]))
    return lines


def show(page):
    for i, ln in enumerate(load(page)):
        print(f"p{page} {ln['col']} i={i:3d} y=[{ln['y0']:7.2f},{ln['y1']:7.2f}] "
              f"x=[{ln['x0']:6.1f},{ln['x1']:6.1f}] {ln['text'][:95]}")


def baseline_stats(page, col):
    ys = [ln["y0"] for ln in load(page) if ln["col"] == col]
    ys.sort()
    d = [round(b - a, 3) for a, b in zip(ys, ys[1:])]
    from collections import Counter
    return Counter(d).most_common(6), min(ys), max(ys)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "dump":
        show(int(sys.argv[2]))
    elif cmd == "skip":
        for p in (5, 6, 7):
            for c in ("L", "R"):
                print(p, c, baseline_stats(p, c))
