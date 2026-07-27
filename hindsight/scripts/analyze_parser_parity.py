#!/usr/bin/env python
"""Re-derive LAP and delta under BOTH probe-answer parsers (paper 1 E.4, paper 2 §7).

Why this exists. Two probe-answer parsers coexist in the panel: the runner used
for the two Gemini rows takes the FIRST whitespace token (strict), the runner
used for the other thirteen takes the LAST standalone up/down/unknown token
(permissive). The strict rule voids schema-adjacent replies such as
{"answer": "unknown"}, and voided answers sit in LAP's denominator, so it biases
those two rows' LAP down. Both papers disclose the gap and deliberately do NOT
restate the affected cells; the disclosure quotes a sensitivity result
(LAP_pre .337 -> .430, delta -0.266 -> -0.250) that until now existed only in a
commit message and in prose. Nothing regenerated it. This script does.

Self-validation, not self-report: the strict path here must reproduce the frozen
<model>_row.json values exactly (LAP pre/post, empirical cutoff, delta, t) before
any permissive number is emitted. A mismatch exits non-zero -- there is no
fallback and no approximate compare.

Usage:
  python analyze_parser_parity.py            # report + write outputs/review/parser_parity.json
  python analyze_parser_parity.py --check    # additionally fail if the paper-quoted
                                             # permissive values drift from the re-derivation
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import all_dates, CALM_YEARS  # noqa: E402,F401
from analyze_bench_row import load_arm  # noqa: E402
from hindsight_paths import REPO  # noqa: E402

BENCH = REPO / "hindsight/outputs/bench"
SPX_NEW = REPO / "macrochain/data/processed/spx_target_new.parquet"
OUT = REPO / "hindsight/outputs/review/parser_parity.json"

# The two rows probed under the strict rule. The other thirteen were probed
# under the permissive rule already, so re-parsing them is a no-op by
# construction and they are not in scope here.
STRICT_ROWS = ["gemini-2.5-flash", "gemini-2.5-pro"]

# What the papers currently print for the permissive variant (E.4 / §7).
QUOTED = {
    "gemini-2.5-flash": {"lap_pre": 0.430, "delta": -0.250, "t": -2.09, "cutoff": "2024-06"},
    "gemini-2.5-pro": {"lap_pre": 0.954, "cutoff": "2024-05"},
}

CUTOFF_THETA = 0.1


def parse_strict(raw: str) -> str:
    """run_fm1c.py:274 / run_pro_probes.py:102 -- first whitespace token."""
    ans = raw.strip().lower().split()[0].strip('."\'') if raw.strip() else ""
    return ans if ans in ("up", "down", "unknown") else "invalid"


def parse_permissive(raw: str) -> str:
    """run_bench_model.py:204 -- last standalone up/down/unknown token."""
    words = re.findall(r"\b(up|down|unknown)\b", raw.lower())
    return words[-1] if words else "invalid"


def lap_series(rows: list[dict], answers: list[str]) -> tuple[dict, dict]:
    """LAP[d] = (up+down)/n with n INCLUDING invalid (analyze_bench_row.py:226-229)."""
    cnt: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r, a in zip(rows, answers):
        cnt[r["decision_date"]][a] += 1
    LAP, UD = {}, {}
    for d, c in cnt.items():
        n = sum(c.values())
        LAP[d] = (c["up"] + c["down"]) / n if n else np.nan
        UD[d] = (c["up"] - c["down"]) / n if n else np.nan
    return LAP, UD


def cutoff_at(LAP: dict, theta: float) -> str | None:
    above = [d for d in sorted(LAP) if LAP[d] > theta]
    return above[-1][:7] if above else None


def delta_fit(root: Path, pre: list[str], LAP: dict) -> tuple[float | None, float | None, int]:
    """Detection regression, identical to analyze_bench_row.py:238-276."""
    spx = pd.read_parquet(SPX_NEW).reset_index()
    dcol = "date" if "date" in spx.columns else spx.columns[0]
    spx[dcol] = pd.to_datetime(spx[dcol])
    spx = spx.sort_values(dcol)

    def realized(d: str):
        after = spx[spx[dcol] >= pd.Timestamp(d)]
        if not len(after) or pd.isna(after.iloc[0]["forward_return_20d"]):
            return None
        return 1.0 if after.iloc[0]["forward_return_20d"] >= 0 else -1.0

    real = {d: realized(d) for d in pre}
    R, _ = load_arm(root, "R")
    R_pre = {d: v for d, v in R.items() if d in set(pre)}
    sig, hit, lap_v = [], [], []
    for d in pre:
        xs = R_pre.get(d, [])
        if not xs or real.get(d) is None or d not in LAP:
            continue
        net = sum(1 if x == "+" else -1 for x in xs)
        if net == 0:
            continue
        s = 1.0 if net > 0 else -1.0
        sig.append(s)
        hit.append(int(s == real[d]))
        lap_v.append(LAP[d])
    if not (len(sig) > 30 and float(np.var(lap_v)) > 1e-4):
        return None, None, len(sig)
    X = pd.DataFrame({"signal": sig, "lap": lap_v})
    X["inter"] = X.signal * X.lap
    ols = sm.OLS(np.array(hit, float), sm.add_constant(X)).fit(
        cov_type="HAC", cov_kwds={"maxlags": 6})
    return float(ols.params["inter"]), float(ols.tvalues["inter"]), len(sig)


def run(model: str, pre: list[str]) -> dict:
    root = BENCH / model
    rows = [json.loads(l) for l in (root / "lap_probe_results.jsonl").read_text().splitlines()
            if l.strip()]
    stored = [r["answer"] for r in rows]
    strict = [parse_strict(r.get("raw", "")) for r in rows]
    perm = [parse_permissive(r.get("raw", "")) for r in rows]

    # The stored answers were produced by the strict rule on the FULL response;
    # `raw` is truncated to 80 chars. Strict reads only the first token, so a
    # re-parse must agree exactly -- if it does not, the truncation is eating a
    # first token and every number below is untrustworthy.
    disagree_strict = [i for i in range(len(rows)) if strict[i] != stored[i]]
    if disagree_strict:
        sys.exit(f"FAIL {model}: strict re-parse disagrees with the stored answer on "
                 f"{len(disagree_strict)} of {len(rows)} records (first: "
                 f"{rows[disagree_strict[0]]!r}) -- `raw` truncation is not safe here")

    # Superset property: the permissive rule must never overturn an answer the
    # strict rule already accepted; it may only rescue an "invalid".
    overturned = [(stored[i], perm[i], rows[i].get("raw", ""))
                  for i in range(len(rows)) if stored[i] != "invalid" and perm[i] != stored[i]]
    accepted_strict = sum(1 for a in stored if a != "invalid")
    rescued = sum(1 for i in range(len(rows)) if stored[i] == "invalid" and perm[i] != "invalid")

    # Truncation exposure: the permissive rule reads the LAST match, so a
    # response longer than the stored 80 chars could in principle parse
    # differently on the full text. Report the exposure rather than hide it.
    truncated_invalid = sum(1 for i, r in enumerate(rows)
                            if stored[i] == "invalid" and len(r.get("raw", "")) >= 80)

    out: dict = {
        "model": model,
        "n_probe_answers": len(rows),
        "accepted_strict": accepted_strict,
        "void_rate_strict": 1 - accepted_strict / len(rows),
        "rescued_by_permissive": rescued,
        "overturned_by_permissive": len(overturned),
        "truncated_invalid_records": truncated_invalid,
    }
    for tag, answers in (("strict", strict), ("permissive", perm)):
        LAP, _ = lap_series(rows, answers)
        vals_pre = [LAP[d] for d in pre if d in LAP]
        post = sorted(d for d in LAP if d >= "2025-01")
        d_, t_, n_ = delta_fit(root, pre, LAP)
        out[tag] = {
            "lap_pre": float(np.mean(vals_pre)) if vals_pre else None,
            "lap_post": float(np.mean([LAP[d] for d in post])) if post else None,
            "cutoff": cutoff_at(LAP, CUTOFF_THETA),
            "cutoff_sensitivity": {str(th): cutoff_at(LAP, th)
                                   for th in (0.05, 0.075, 0.1, 0.15, 0.2)},
            "delta": d_, "t": t_, "n_dates": n_,
        }

    # Self-validation against the frozen row.
    frozen = json.loads((root / f"{model}_row.json").read_text())
    checks = [
        ("LAP.pre_mean", frozen["LAP"]["pre_mean"], out["strict"]["lap_pre"]),
        ("LAP.post_mean", frozen["LAP"]["post_mean"], out["strict"]["lap_post"]),
        ("LAP.empirical_cutoff", frozen["LAP"]["empirical_cutoff"], out["strict"]["cutoff"]),
        ("delta", frozen["delta_dissociation"]["delta"], out["strict"]["delta"]),
        ("delta.t", frozen["delta_dissociation"]["t"], out["strict"]["t"]),
    ]
    for name, want, got in checks:
        same = (want == got) if isinstance(want, (str, type(None))) \
            else (got is not None and abs(want - got) < 1e-9)
        if not same:
            sys.exit(f"FAIL {model}: strict re-derivation does not reproduce the frozen row "
                     f"on {name}: frozen={want!r} re-derived={got!r}")
    out["reproduces_frozen_row"] = True
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the values the papers quote drift from the re-derivation")
    a = ap.parse_args()

    pre = all_dates()
    res = {m: run(m, pre) for m in STRICT_ROWS}

    fails = []
    for m, q in QUOTED.items():
        r = res[m]["permissive"]
        for k, want in q.items():
            got = r["cutoff"] if k == "cutoff" else r[{"lap_pre": "lap_pre",
                                                       "delta": "delta", "t": "t"}[k]]
            ok = (want == got) if k == "cutoff" else (got is not None and abs(want - got) < 0.0005)
            if not ok:
                fails.append(f"{m}.{k}: papers print {want!r}, re-derivation gives {got!r}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"rows": res, "quoted_in_papers": QUOTED,
                               "drift": fails}, indent=2))

    for m, r in res.items():
        s, p = r["strict"], r["permissive"]
        print(f"{m}: n={r['n_probe_answers']} void_strict={r['void_rate_strict']:.4f} "
              f"rescued={r['rescued_by_permissive']} overturned={r['overturned_by_permissive']} "
              f"truncated_invalid={r['truncated_invalid_records']}")
        print(f"  LAP_pre  {s['lap_pre']:.4f} -> {p['lap_pre']:.4f}   "
              f"cutoff(θ={CUTOFF_THETA}) {s['cutoff']} -> {p['cutoff']}")
        if s["delta"] is not None:
            print(f"  delta    {s['delta']:.4f} (t {s['t']:.3f}) -> "
                  f"{p['delta']:.4f} (t {p['t']:.3f})   n={p['n_dates']}")
        print(f"  cutoff by θ (permissive): {p['cutoff_sensitivity']}")
    print(f"wrote {OUT}")

    if fails:
        print("PARSER-PARITY DRIFT:")
        for f in fails:
            print("  FAIL:", f)
        sys.exit(1 if a.check else 0)
    print("strict path reproduces both frozen rows; quoted permissive values match")


if __name__ == "__main__":
    main()
