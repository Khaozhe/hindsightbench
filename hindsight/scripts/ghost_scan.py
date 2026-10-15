#!/usr/bin/env python
"""Meta-commentary ("ghost") scan for paper prose: sentences that argue with an earlier draft,
a reviewer, or the authors' own past choices instead of stating the result.
Usage: python ghost_scan.py sections/*.tex   (prints file:line and the matched phrase)
"""
import re, sys

GHOSTS = [
    r"\bwe (do not|don't|did not|had not|have not) (report|claim|read|count|interpret|state)\b",
    r"\bnot because\b", r"\bhonest(ly)? reading\b", r"\bwe state (this|both|the other|plainly)\b",
    r"\bearlier (version|draft|rounds?)\b", r"\binitially frozen\b", r"\bpredated\b",
    r"\bhad to (retract|correct|withdraw)\b", r"\bwe learned\b|\bby getting it wrong\b",
    r"\bwhich we (had not|did not|do not)\b", r"\boverstates?\b", r"\bnot (inconvenient|cherry)",
    r"\bby construction, not\b", r"\bso the level is not\b", r"\brather than silently\b",
    r"\bdisclosed (as|rather)\b", r"\bwe (concede|admit|acknowledge)\b", r"\bto be clear\b",
    r"\bwe (do|did) not (set out|claim otherwise)\b", r"\bthis is not a\b", r"\bis not (a|an) (claim|criticism|mechanism claim)\b",
]
RX = [re.compile(g, re.I) for g in GHOSTS]
n = 0
for path in sys.argv[1:]:
    for i, line in enumerate(open(path), 1):
        for rx in RX:
            m = rx.search(line)
            if m:
                n += 1
                print(f"{path}:{i}: [{m.group(0)}] {line.strip()[:110]}")
                break
print(f"-- {n} ghost lines")
