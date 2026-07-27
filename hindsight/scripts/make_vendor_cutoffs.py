"""Emit the vendor-reported-cutoff record that the maintenance policy promises.

Paper 2 section 8 states that vendor-reported cutoffs are stored alongside the
measured ones with retrieval dates. That was true of our working notes
(BENCH_ROWS.md records the 2026-07-07 documentation check) but not of any
machine-readable file in the released artifact, so a reader could not verify
it. This script closes that gap: it writes outputs/bench/vendor_cutoffs.json
pairing, per model, the vendor-reported cutoff held in bench_registry with the
measured cutoff read from the frozen row files, plus the disclosure type and
the date the vendor documentation was checked.

It adds no new measurement: every measured value is read from the frozen row
JSONs and every vendor value from the registry that already drives the
published table. Re-runnable; output is deterministic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "hindsight" / "scripts"))

from bench_registry import MODELS  # noqa: E402

BENCH = REPO / "hindsight" / "outputs" / "bench"

# Date on which every official vendor cutoff below was checked against the
# vendor's own published documentation (recorded in BENCH_ROWS.md at the time).
DOC_CHECK_DATE = "2026-07-07"

# Models whose vendors publish no cutoff at all. Third-party trackers circulate
# estimates for these; those are NOT vendor disclosure and are not recorded as
# such -- the paper compares to them separately and says so.
UNDISCLOSED_NOTE = ("vendor publishes no cutoff; third-party tracker estimates "
                    "exist but are unverified and are not treated as disclosure")

# Anthropic publishes two tiers; fig4_claim holds the conservative
# ("reliable") one, which is the tier the paper compares against.
TWO_TIER = {"claude-sonnet-5", "claude-haiku-4-5"}


def months_between(a: str, b: str) -> int:
    ya, ma = (int(x) for x in a.split("-")[:2])
    yb, mb = (int(x) for x in b.split("-")[:2])
    return (ya - yb) * 12 + (ma - mb)


def main() -> None:
    records = []
    for m in MODELS:
        key = m["key"]
        row_f = BENCH / key / f"{key}_row.json"
        measured = None
        # lap_at_chance lives in bench_registry, NOT in the row json: the raw
        # locator still emits a "cutoff" for a model whose recall is guessing,
        # and both papers print ---^g for exactly those rows. Reading the flag
        # from the row json (where it never exists) silently published three
        # cutoffs the papers declare undefined.
        at_chance = bool(m.get("lap_at_chance"))
        if row_f.exists() and not at_chance:
            measured = json.loads(row_f.read_text()).get("LAP", {}).get("empirical_cutoff")
        vendor = m.get("fig4_claim")
        rec = {
            "model": key,
            "display_name": m["tex"],
            "measured_cutoff": measured,
            "measured_cutoff_gated": at_chance or None,
            "measured_cutoff_gate_reason": (
                "LAP hit rate at chance: the probe measures guessing, not "
                "recall, so no behaviorally effective cutoff is defined "
                "(printed as ---^g in both papers' tables)") if at_chance else None,
            "measured_source": f"outputs/bench/{key}/{key}_row.json :: LAP.empirical_cutoff",
            "vendor_reported_cutoff": vendor,
            "vendor_disclosure": (
                "official (conservative tier of a two-tier disclosure)"
                if vendor and key in TWO_TIER else
                "official" if vendor else "none"),
            "vendor_checked_on": DOC_CHECK_DATE if vendor else None,
            "note": None if vendor else UNDISCLOSED_NOTE,
        }
        if vendor and measured:
            d = months_between(measured, vendor)
            rec["measured_minus_vendor_months"] = d
            rec["direction"] = "early" if d < 0 else ("late" if d > 0 else "exact")
        records.append(rec)

    with_vendor = [r for r in records if r.get("vendor_reported_cutoff")]
    comparable = [r for r in with_vendor if "direction" in r]
    out = {
        "purpose": "Vendor-reported cutoffs stored alongside measured ones with "
                   "the date the vendor documentation was checked, per the "
                   "maintenance policy (paper section 8). Vendor documentation "
                   "changes; this file records what it said when we read it.",
        "vendor_documentation_checked_on": DOC_CHECK_DATE,
        "n_models": len(records),
        "n_with_official_cutoff": len(with_vendor),
        "n_comparable": len(comparable),
        "direction_counts": {
            d: sum(1 for r in comparable if r["direction"] == d)
            for d in ("early", "exact", "late")
        },
        "records": records,
    }
    (BENCH / "vendor_cutoffs.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {BENCH / 'vendor_cutoffs.json'}")
    print(f"{out['n_with_official_cutoff']} official / {len(records)} models; "
          f"directions {out['direction_counts']}")
    for r in comparable:
        print(f"  {r['display_name']:<20} measured {r['measured_cutoff']} "
              f"vs vendor {r['vendor_reported_cutoff']} "
              f"({r['measured_minus_vendor_months']:+d} mo, {r['direction']})")


if __name__ == "__main__":
    main()
