#!/usr/bin/env python3
"""RV-1 (review response 1): rule-based pre-shock and control decision dates, from market data ONLY.

No model output is read. For every panel decision date t <= 2023-12-15 outside the preregistered crisis set:
  d0      = first S&P 500 trading day on/after t
  FDD(t)  = min(Close[d0 .. d0+63 trading days]) / Close[d0] - 1        (forward drawdown, ~3 months)
  TR(t)   = Close[d0] / Close[d0-63] - 1                                 (trailing ~3-month return)
  VIX(t)  = last daily VIXCLS close on or before t (no information after t)
  calm-looking at t:  TR >= 0  and  VIX(t) <= median daily VIX over 2005-01-01..2023-12-31
  SHOCK   = calm-looking and FDD <= -10%     (a large decline that the tape at t did not show)
  CONTROL = calm-looking and FDD >  -5%      (calm before calm)
Sensitivity sets (reported, never primary): thresholds (-7%/-4%, 42 days) and (-15%/-5%, 84 days).
Writes prereg/RV1_preshock_dates.json.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import CRISIS, all_dates, SPX, COV  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "prereg/RV1_preshock_dates.json"
LAST = "2023-12-15"


def build(fdd_shock, fdd_ctrl, h):
    spx = pd.read_parquet(SPX).reset_index().rename(columns={"index": "date"})
    spx["date"] = pd.to_datetime(spx["date"]); spx = spx.sort_values("date").reset_index(drop=True)
    vix = pd.Series({pd.Timestamp(o["date"]): float(o["value"]) for o in json.load(open(COV / "VIXCLS.json"))["observations"] if o["value"] != "."}).sort_index()
    vmed = float(vix[(vix.index >= "2005-01-01") & (vix.index <= "2023-12-31")].median())
    rows = []
    for t in all_dates():
        if t > LAST or t in CRISIS:
            continue
        i0 = int(spx.index[spx["date"] >= pd.Timestamp(t)][0])
        if i0 < h:
            continue
        c0 = spx.loc[i0, "Close"]
        fdd = float(spx.loc[i0:i0 + h, "Close"].min() / c0 - 1)
        tr = float(c0 / spx.loc[i0 - h, "Close"] - 1)
        v = float(vix[vix.index <= pd.Timestamp(t)].iloc[-1])
        calm = tr >= 0 and v <= vmed
        rows.append({"date": t, "fdd": round(fdd, 4), "trailing": round(tr, 4), "vix": round(v, 2), "calm_looking": calm,
                     "set": ("SHOCK" if calm and fdd <= fdd_shock else "CONTROL" if calm and fdd > fdd_ctrl else None)})
    return rows, vmed


def main():
    out = {"rule": __doc__.strip().splitlines()[2:10], "last_date": LAST}
    for name, (s, c, h) in {"primary": (-0.10, -0.05, 63), "sens_mild": (-0.07, -0.04, 42), "sens_severe": (-0.15, -0.05, 84)}.items():
        rows, vmed = build(s, c, h)
        out[name] = {"thresholds": {"shock_fdd": s, "control_fdd": c, "horizon_days": h, "vix_median": round(vmed, 2)},
                     "SHOCK": [r for r in rows if r["set"] == "SHOCK"], "CONTROL": [r["date"] for r in rows if r["set"] == "CONTROL"]}
    OUT.write_text(json.dumps(out, indent=1))
    for name in ("primary", "sens_mild", "sens_severe"):
        o = out[name]; print(name, "SHOCK", len(o["SHOCK"]), "CONTROL", len(o["CONTROL"]))
    print("primary SHOCK dates:"); [print(" ", r["date"], "fdd", r["fdd"], "trail", r["trailing"], "vix", r["vix"]) for r in out["primary"]["SHOCK"]]


if __name__ == "__main__":
    main()
