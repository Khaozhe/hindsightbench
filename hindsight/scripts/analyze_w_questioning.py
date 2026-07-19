#!/usr/bin/env python
"""W-arm date-questioning rate — committed, reproducible implementation.

The prereg promised this descriptive metric; the original 14/5,760 (0.243%)
was computed inline in-session and only the number was recorded (disclosed
in Appendix A). This script makes the detection criteria explicit and adds
the broader hedging tier a reviewer asked about:

  tier1  explicit date questioning: the sketch text doubts, contests, or
         flags the asserted date itself
  tier2  temporal hedging: conditional/deferential language about the
         stated date or period without contesting it

Scans every string field of every valid W-arm sketch (3 reps x 240 dates
x 8 sketches = 5,760). Hits go to a sidecar jsonl for eyeball audit.
Zero API calls. Writes outputs/fm1/W_QUESTIONING.{json,jsonl}.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hindsight_paths import REPO

W = REPO / "hindsight/outputs/fm1/gemini-2.5-flash/W"
OUT = REPO / "hindsight/outputs/fm1"

TIER1 = [
    r"date\b.{0,60}\b(wrong|incorrect|inconsistent|implausible|mismatch|mislabel|erroneous|suspect)",
    r"\b(wrong|incorrect|inconsistent|implausible|mismatch|mislabel|erroneous|suspect)\w*\b.{0,60}\bdate",
    r"anachron",
    r"date\b.{0,40}\b(discrepan|conflict|does not match|doesn't match|not consistent)",
    r"\b(discrepan|conflict)\w*\b.{0,40}\bdate",
    r"data\b.{0,60}\b(suggests?|indicates?|implies|resembles?)\b.{0,60}\b(a different|an earlier|a later)\b.{0,20}\b(date|year|period|era)",
    r"(cannot|can't|hard to)\b.{0,30}\breconcile\b.{0,40}\bdate",
]
TIER2 = [
    r"if the date is (accurate|correct)",
    r"assuming th(e|is)\b.{0,20}\bdate",
    r"despite the (stated|given|asserted) date",
    r"unusual(ly)? for (this|the) (stated )?(period|year|date|era)",
    r"atypical for (this|the) (period|year|date|era)",
    r"given the (stated|asserted) date",
]

RX1 = [re.compile(p, re.I) for p in TIER1]
RX2 = [re.compile(p, re.I) for p in TIER2]


INJECTED = {"decision_date", "hypothesis_id"}  # caller-added, not model text


def sketch_text(s: dict) -> str:
    parts = []
    for k, v in s.items():
        if k in INJECTED:
            continue
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts += [x for x in v if isinstance(x, str)]
    return " | ".join(parts)


def main() -> None:
    n = 0
    hits = []
    for rep in sorted(W.iterdir()):
        if not rep.name.startswith("rep"):
            continue
        for node in sorted(rep.iterdir()):
            fj = node / "01_sketches_valid.json"
            if not fj.exists():
                continue
            for i, s in enumerate(json.loads(fj.read_text())):
                n += 1
                t = sketch_text(s)
                m1 = [rx.pattern for rx in RX1 if rx.search(t)]
                m2 = [rx.pattern for rx in RX2 if rx.search(t)]
                if m1 or m2:
                    hits.append({"rep": rep.name, "date": node.name,
                                 "sketch": i, "tier1": m1, "tier2": m2,
                                 "text": t[:600]})
    # second corpus: raw responses, commentary OUTSIDE the JSON block
    nresp = 0
    for rep in sorted(W.iterdir()):
        if not rep.name.startswith("rep"):
            continue
        for node in sorted(rep.iterdir()):
            fr = node / "04_raw_response.txt"
            if not fr.exists():
                continue
            nresp += 1
            t = fr.read_text()
            i, j = t.find("["), t.rfind("]")
            outside = (t[:i] + t[j + 1:]) if 0 <= i < j else t
            m1 = [rx.pattern for rx in RX1 if rx.search(outside)]
            m2 = [rx.pattern for rx in RX2 if rx.search(outside)]
            if m1 or m2:
                hits.append({"rep": rep.name, "date": node.name,
                             "sketch": "raw_outside_json", "tier1": m1,
                             "tier2": m2, "text": outside[:600]})

    t1 = sum(1 for h in hits if h["tier1"])
    t2 = sum(1 for h in hits if h["tier2"] and not h["tier1"])
    res = {"n_sketches": n, "n_raw_responses": nresp,
           "tier1_explicit": {"count": t1, "rate": t1 / n},
           "tier2_hedge_only": {"count": t2, "rate": t2 / n},
           "either": {"count": t1 + t2, "rate": (t1 + t2) / n},
           "criteria": {"tier1": TIER1, "tier2": TIER2}}
    (OUT / "W_QUESTIONING.json").write_text(json.dumps(res, indent=2))
    with (OUT / "W_QUESTIONING.jsonl").open("w") as f:
        for h in hits:
            f.write(json.dumps(h) + "\n")
    print(f"n={n}  tier1={t1} ({t1/n:.3%})  tier2-only={t2} ({t2/n:.3%})  "
          f"either={t1+t2} ({(t1+t2)/n:.3%})")


if __name__ == "__main__":
    main()
