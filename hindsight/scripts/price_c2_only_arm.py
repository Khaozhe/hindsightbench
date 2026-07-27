#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (2026-07-25, design-review response).

Price the missing C2-only arm (masked date line + ORIGINAL leaky auxiliary
context + vintage data) for gemini-2.5-flash on the FM-1 240-date panel.

NO API CALLS. Everything here is derived from:
  - frozen prompt sources  macrochain/data/processed/sketch_batch_requests.jsonl
  - frozen ledger          hindsight/outputs/gemini_usage_log.jsonl
  - frozen cell metadata   hindsight/outputs/{fm1,fm1e,gd1}/**/03_run_meta.json
  - frozen price table     hindsight/outputs/price_table.json

Writes hindsight/outputs/review/c2_only_arm_pricing.json
"""

from __future__ import annotations

import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_kt1_masked_arm import DATE_LINE_RE, load_nodes  # noqa: E402
from run_fm1_arms import clean_context  # noqa: E402
from run_fm1e_trigger_decomp import variant_prompt, window_dates  # noqa: E402
from run_gd1 import gd1_system, gd1_user  # noqa: E402
from analyze_fm1 import fake_map  # noqa: E402
from hindsight_paths import REPO  # noqa: E402

OUT = REPO / "hindsight/outputs"
REVIEW = OUT / "review"
LEDGER = OUT / "gemini_usage_log.jsonl"

M_DATE_LINE = ("Decision time point: [undisclosed]. Only information "
               "contained in this snapshot is admissible as evidence.")
DDU_RE = re.compile(r"^\s*decision_date_used:")
C2_MARKERS = ("Positive days :", "Total sessions:", "Date range    :",
              "revised_value=", "vintage_date=")


# ---------------------------------------------------------------- C2-only arm
def c2_only_prompt(orig_user: str, decision_date: str, drop_ddu: bool) -> str:
    """C1 removed (date line -> [undisclosed]); C2 + C3 left verbatim.

    drop_ddu=True also removes the `decision_date_used: YYYY-MM-DD` line, which
    is a *verbatim restatement of C1* inside the context block; leaving it in
    would make the arm C1+C2, not C2-only.
    """
    out: list[str] = []
    for line in orig_user.splitlines():
        m = DATE_LINE_RE.match(line)
        if m:
            out.append(f"{m.group(1)}{M_DATE_LINE}")
            continue
        if drop_ddu and DDU_RE.match(line):
            continue
        out.append(line)
    txt = "\n".join(out)
    # fail-closed, INVERTED relative to clean_context(): C2 must survive,
    # C1 must not. clean_context()'s LEAK_BASE/DATE_PAT check would reject
    # this prompt by construction, so it cannot be reused here.
    assert not any(DATE_LINE_RE.match(l) for l in txt.splitlines()), "C1 survived"
    if drop_ddu:
        assert decision_date not in txt, f"explicit {decision_date} survived"
    for mk in C2_MARKERS:
        assert mk in txt, f"C2 marker {mk!r} lost"
    return txt


# ------------------------------------------------------------------- ledger
def ledger(model_prefix: str, lo: str, hi: str) -> list[dict]:
    return [r for r in (json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip())
            if r["model"].startswith(model_prefix) and lo <= r["ts"] < hi]


def stats(xs: list[float]) -> dict:
    xs = sorted(xs)
    return {"n": len(xs), "mean": round(st.mean(xs), 1), "median": xs[len(xs) // 2],
            "min": xs[0], "max": xs[-1],
            "p95": xs[min(len(xs) - 1, int(0.95 * len(xs)))]}


def main() -> None:
    nodes = load_nodes()
    by_date = {n["decision_date"]: n for n in nodes}
    res: dict = {"_doc": __doc__.splitlines()[0]}

    # ---------- 1. calibration source A: FM-1e (measured flash, FM-1 panel)
    fm1e_recs = ledger("gemini-2.5-flash", "2026-07-10T00:00", "2026-07-11T00:00")
    wdates = window_dates()
    fm1e_chars = []
    for d in wdates:
        for v in ("DBARE", "DSNAP"):
            n = by_date[d]
            fm1e_chars.append(len(n["system"]) + len(variant_prompt(n, v)))
    assert len(fm1e_chars) == len(fm1e_recs), (len(fm1e_chars), len(fm1e_recs))
    ratio_a = sum(fm1e_chars) / sum(r["prompt"] for r in fm1e_recs)

    # ---------- 2. calibration source B: GD-1 arms (measured flash, same template)
    gd1_recs = [r for r in ledger("gemini-2.5-flash", "2026-07-03T00:00", "2026-07-04T00:00")
                if r["prompt"] > 1000]
    fmap = fake_map(sorted(by_date))
    gd1_chars = []
    for n in nodes:
        for mode in ("true", "none", "fake"):
            fake = fmap[n["decision_date"]] if mode == "fake" else None
            gd1_chars.append(len(gd1_system(n["system"])) + len(gd1_user(n, mode, fake)))
    ratio_b = st.mean(gd1_chars) / st.mean([r["prompt"] for r in gd1_recs])

    res["calibration_chars_per_prompt_token"] = {
        "A_fm1e_2026-07-10": {"calls": len(fm1e_recs), "chars_total": sum(fm1e_chars),
                              "prompt_tok_total": sum(r["prompt"] for r in fm1e_recs),
                              "chars_per_tok": round(ratio_a, 4)},
        "B_gd1_arms_2026-07-03": {"ledger_calls_gt1000tok": len(gd1_recs),
                                  "reconstructed_prompts": len(gd1_chars),
                                  "mean_chars": round(st.mean(gd1_chars), 1),
                                  "mean_prompt_tok": round(st.mean(r["prompt"] for r in gd1_recs), 1),
                                  "chars_per_tok": round(ratio_b, 4),
                                  "note": "725 ledger calls vs 720 reconstructed cells "
                                          "(GD-1 smoke overlap); mean-based ratio, <=0.7% slack"},
    }

    # ---------- 3. prompt sizes of every arm, 240 dates
    arms: dict[str, list[int]] = {"R": [], "D": [], "M": [], "C2only_ddu_dropped": [],
                                  "C2only_ddu_kept": []}
    for n in nodes:
        d, s = n["decision_date"], len(n["system"])
        arms["R"].append(s + len(n["orig_user"]))
        arms["D"].append(s + len(clean_context(n["orig_user"], d, "true")))
        arms["M"].append(s + len(clean_context(n["orig_user"], d, "none")))
        arms["C2only_ddu_dropped"].append(s + len(c2_only_prompt(n["orig_user"], d, True)))
        arms["C2only_ddu_kept"].append(s + len(c2_only_prompt(n["orig_user"], d, False)))

    res["prompt_chars_incl_system"] = {k: stats([float(x) for x in v]) for k, v in arms.items()}
    res["projected_input_tokens_per_cell"] = {
        k: {"via_ratio_A": round(st.mean(v) / ratio_a, 1),
            "via_ratio_B": round(st.mean(v) / ratio_b, 1)}
        for k, v in arms.items()
    }

    # ---------- 4. measured output cost anchors (flash, 8-sketch task, 8192 cap)
    res["measured_output_tokens_per_cell"] = {
        "FM1e_flash_fm1panel_n94": {
            "visible_output": stats([float(r["output"]) for r in fm1e_recs]),
            "thoughts": stats([float(r["thoughts"]) for r in fm1e_recs]),
            "billed_output_incl_thoughts": stats([float(r["output"] + r["thoughts"])
                                                  for r in fm1e_recs]),
            "prompt": stats([float(r["prompt"]) for r in fm1e_recs]),
        },
        "GD1_flash_arms_n%d" % len(gd1_recs): {
            "visible_output": stats([float(r["output"]) for r in gd1_recs]),
            "thoughts": stats([float(r["thoughts"]) for r in gd1_recs]),
            "billed_output_incl_thoughts": stats([float(r["output"] + r["thoughts"])
                                                  for r in gd1_recs]),
            "prompt": stats([float(r["prompt"]) for r in gd1_recs]),
        },
    }

    # ---------- 5. response-length cross-check: are FM-1 D/M responses the same size?
    def resp_chars(glob_root: Path) -> list[int]:
        return [len((p / "04_raw_response.txt").read_text())
                for p in sorted(glob_root.iterdir()) if (p / "04_raw_response.txt").exists()]

    fm1e_resp = []
    for v in ("DBARE", "DSNAP"):
        fm1e_resp += resp_chars(OUT / "fm1e" / v / "rep1")
    d_resp = resp_chars(OUT / "fm1/gemini-2.5-flash/D/rep1")
    m_resp = resp_chars(OUT / "fm1/gemini-2.5-flash/M/rep1")
    r_resp = resp_chars(OUT / "fm1/gemini-2.5-flash/R/rep1")
    out_ratio = st.mean(fm1e_resp) / st.mean([r["output"] for r in fm1e_recs])
    res["response_size_crosscheck"] = {
        "fm1e_mean_resp_chars": round(st.mean(fm1e_resp), 1),
        "fm1e_chars_per_visible_output_tok": round(out_ratio, 4),
        "fm1_D_rep1_mean_resp_chars": round(st.mean(d_resp), 1),
        "fm1_M_rep1_mean_resp_chars": round(st.mean(m_resp), 1),
        "fm1_R_rep1_mean_resp_chars": round(st.mean(r_resp), 1),
        "implied_D_visible_output_tok": round(st.mean(d_resp) / out_ratio, 1),
        "implied_M_visible_output_tok": round(st.mean(m_resp) / out_ratio, 1),
        "implied_R_visible_output_tok": round(st.mean(r_resp) / out_ratio, 1),
        "note": "thoughts tokens are NOT recoverable from stored text; only FM-1e/GD-1 "
                "ledger measures them for flash on this task",
    }

    # ---------- 6. projected totals for the three scenarios
    c2_in = st.mean(arms["C2only_ddu_dropped"]) / ratio_a
    out_bill = st.mean([r["output"] + r["thoughts"] for r in fm1e_recs])
    out_bill_gd1 = st.mean([r["output"] + r["thoughts"] for r in gd1_recs])
    scen = {}
    for label, cells in (("i_47dates_x1rep", 47), ("ii_240dates_x1rep", 240),
                         ("iii_240dates_x3reps", 720)):
        scen[label] = {
            "cells": cells,
            "input_tokens": round(cells * c2_in),
            "billed_output_tokens_FM1e_anchor": round(cells * out_bill),
            "billed_output_tokens_GD1_anchor": round(cells * out_bill_gd1),
        }
    res["projected_scenarios"] = scen

    # ---------- 6b. tightest anchor: FM-1e DSNAP prompt is char-identical to M
    #        (differs only "[undisclosed]" 13ch -> "YYYY-MM-DD" 10ch), so the
    #        measured DSNAP cluster IS the M/D arm input cost to within ~1 token.
    ptok = sorted(r["prompt"] for r in fm1e_recs)
    dsnap_tok = st.mean(ptok[len(ptok) // 2:])
    dsnap_chars = st.mean([len(by_date[d]["system"]) + len(variant_prompt(by_date[d], "DSNAP"))
                           for d in wdates])
    def anchored(mean_chars: float) -> float:
        return dsnap_tok + (mean_chars - dsnap_chars) / ratio_a
    res["anchored_input_tokens_per_cell"] = {
        "measured_DSNAP_cluster_tok": dsnap_tok,
        "measured_DBARE_cluster_tok": st.mean(ptok[:len(ptok) // 2]),
        **{k: round(anchored(st.mean(v)), 1) for k, v in arms.items()},
    }

    # ---------- 7. price
    prices = json.loads((OUT / "price_table.json").read_text())
    c2_in_a = anchored(st.mean(arms["C2only_ddu_dropped"]))
    # price_table.json records gemini-2.5-flash as "not on file". The PAPER,
    # sections/A5_appendix_robustness.tex:228, quotes FM-1g's 108 calls at
    # "~$1.87 at public list rates"; with the ledger tokens for that task
    # (265,107 in / 717,253 out, COST_TABLE.md) this back-solves uniquely to
    # 0.30 / 2.50 USD per 1M ($1.8727). Reported as DERIVED, not frozen.
    BS_IN, BS_OUT = 0.30, 2.50
    res["price_lookup"] = {
        "price_table_json_gemini-2.5-flash": prices["gemini-2.5-flash"],
        "backsolved_from_paper": {
            "source": "sections/A5_appendix_robustness.tex:228 (~$1.87) x "
                      "COST_TABLE.md FM-1g row (265,107 in / 717,253 out)",
            "in_usd_per_1M": BS_IN, "out_usd_per_1M": BS_OUT,
            "check_usd": round(265107 / 1e6 * BS_IN + 717253 / 1e6 * BS_OUT, 4),
            "status": "DERIVED, not in price_table.json -> repo convention = TOKENS-ONLY",
        },
    }
    for label, cells in (("i_47dates_x1rep", 47), ("rep_matched_47dates_x3reps", 141),
                         ("ii_240dates_x1rep", 240), ("iii_240dates_x3reps", 720)):
        d = scen.setdefault(label, {"cells": cells})
        d["input_tokens_anchored"] = round(cells * c2_in_a)
        d.setdefault("billed_output_tokens_FM1e_anchor", round(cells * out_bill))
        d.setdefault("billed_output_tokens_GD1_anchor", round(cells * out_bill_gd1))
        d["usd_derived_FM1e_anchor"] = round(
            cells * c2_in_a / 1e6 * BS_IN + cells * out_bill / 1e6 * BS_OUT, 3)
        d["usd_derived_GD1_anchor"] = round(
            cells * c2_in_a / 1e6 * BS_IN + cells * out_bill_gd1 / 1e6 * BS_OUT, 3)
        d["usd_derived_GD1_plus10pct_contingency"] = round(
            cells * c2_in_a / 1e6 * BS_IN + 1.10 * cells * out_bill_gd1 / 1e6 * BS_OUT, 3)

    # ---------- 8. wall clock from frozen run metadata
    def ga_range(root: Path) -> tuple[str, str, int]:
        gs = []
        for p in root.rglob("03_run_meta.json"):
            try:
                g = json.loads(p.read_text()).get("generated_at")
            except Exception:
                continue
            if g:
                gs.append(g)
        gs.sort()
        return gs[0], gs[-1], len(gs)

    import datetime as dt

    def secs(a: str, b: str) -> float:
        return (dt.datetime.fromisoformat(b) - dt.datetime.fromisoformat(a)).total_seconds()

    fm1_flash = OUT / "fm1/gemini-2.5-flash"
    per_arm = {}
    for arm in ("R", "D", "M", "W"):
        for rep in ("rep1", "rep2", "rep3"):
            root = fm1_flash / arm / rep
            if not root.exists():
                continue
            lo, hi, n = ga_range(root)
            per_arm[f"{arm}/{rep}"] = {"n": n, "first": lo, "last": hi,
                                       "span_s": secs(lo, hi),
                                       "cells_per_s": round(n / max(secs(lo, hi), 1e-9), 2)}
    res["wallclock"] = {
        "fm1_flash_per_arm_rep": per_arm,
        "fm1_flash_whole_run_excl_M_rep1_reuse": {
            "first": "2026-07-02T13:11:53", "last": "2026-07-02T13:26:33",
            "cells": 2400, "span_s": secs("2026-07-02T13:11:53", "2026-07-02T13:26:33"),
            "cells_per_s": round(2400 / secs("2026-07-02T13:11:53", "2026-07-02T13:26:33"), 2),
            "concurrency": "run_fm1_arms.py --concurrency default 64",
        },
        "fm1e_ledger_94_calls": {
            "first": min(r["ts"] for r in fm1e_recs), "last": max(r["ts"] for r in fm1e_recs),
            "span_s": secs(min(r["ts"] for r in fm1e_recs), max(r["ts"] for r in fm1e_recs)),
            "cells_per_s": round(94 / secs(min(r["ts"] for r in fm1e_recs),
                                           max(r["ts"] for r in fm1e_recs)), 2),
            "concurrency": "run_fm1e_trigger_decomp.py default 16",
        },
        "gd1_ledger_725_arm_calls": {
            "first": min(r["ts"] for r in gd1_recs), "last": max(r["ts"] for r in gd1_recs),
            "span_s": secs(min(r["ts"] for r in gd1_recs), max(r["ts"] for r in gd1_recs)),
            "cells_per_s": round(len(gd1_recs) / secs(min(r["ts"] for r in gd1_recs),
                                                      max(r["ts"] for r in gd1_recs)), 2),
            "concurrency": "run_gd1.py --job arms default 64",
        },
    }

    REVIEW.mkdir(parents=True, exist_ok=True)
    (REVIEW / "c2_only_arm_pricing.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
