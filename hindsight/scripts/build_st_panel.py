#!/usr/bin/env python
"""ST-1 panel builder: (city x month) decision nodes from Google COVID-19 Community
Mobility Reports (prereg: hindsight/prereg/ST1_prereg_spatiotemporal.md).

Source: https://www.gstatic.com/covid19/mobility/Region_Mobility_Report_CSVs.zip
(Google discontinued the reports 2022-10-15; the archive is still served).
Sensor-type series are not revised after publication, so vintage-correctness
reduces to as-of truncation: node t sees only rows dated <= t.

Usage:
  python build_st_panel.py --zip /path/Region_Mobility_Report_CSVs.zip   # extract + build
  python build_st_panel.py                                               # rebuild from compact CSV
Outputs (hindsight/outputs/st1/):
  raw/st_mobility_regions.csv     compact per-region daily series (10 regions x 974 days)
  panel/nodes.jsonl               one decision node per (city, month)
  panel/PANEL_SUMMARY.md          counts, crisis/calm membership, label base rates
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from hindsight_paths import REPO

OUT = REPO / "hindsight/outputs/st1"
RAW = OUT / "raw/st_mobility_regions.csv"
PANEL = OUT / "panel/nodes.jsonl"

CATS = ["retail_and_recreation", "grocery_and_pharmacy", "parks",
        "transit_stations", "workplaces", "residential"]
COLS = {c: f"{c}_percent_change_from_baseline" for c in CATS}
TARGET_CAT = "retail_and_recreation"      # primary readout / LAP target (prereg S0)
ALT_CAT = "transit_stations"              # secondary label, reported not headlined

# region selection: key -> (country_code, sub_region_1, sub_region_2, display name, country)
REGIONS = {
    "nyc":       ("US", "New York", "New York County", "New York City (Manhattan)", "United States"),
    "milan":     ("IT", "Lombardy", None, "Lombardy (Milan)", "Italy"),
    "london":    ("GB", "Greater London", None, "Greater London", "United Kingdom"),
    "madrid":    ("ES", "Community of Madrid", None, "Community of Madrid", "Spain"),
    "tokyo":     ("JP", "Tokyo", None, "Tokyo", "Japan"),
    "melbourne": ("AU", "Victoria", None, "Victoria (Melbourne)", "Australia"),
    "sydney":    ("AU", "New South Wales", None, "New South Wales (Sydney)", "Australia"),
    "delhi":     ("IN", "Delhi", None, "Delhi", "India"),
    "hongkong":  ("HK", None, None, "Hong Kong", "Hong Kong SAR"),
    "singapore": ("SG", None, None, "Singapore", "Singapore"),
}

# Ex-ante policy onset dates (restriction *announcements/starts*, not outcomes).
# A node (city, YYYY-MM-15) is a CRISIS node iff an onset falls in that calendar month.
# Sources are listed in the prereg; dates are the commonly reported start dates.
ONSETS = {
    "nyc":       ["2020-03-22"],                                   # NY PAUSE
    "milan":     ["2020-03-08", "2020-11-06"],                     # Lombardy lockdown; red zone
    "london":    ["2020-03-23", "2020-11-05", "2021-01-06"],       # three national lockdowns
    "madrid":    ["2020-03-14", "2020-10-09"],                     # state of alarm; perimeter closure
    "tokyo":     ["2020-04-07", "2021-01-08", "2021-04-25", "2021-07-12"],  # states of emergency
    "melbourne": ["2020-03-30", "2020-07-09", "2021-02-13", "2021-05-28", "2021-07-16", "2021-08-05"],
    "sydney":    ["2020-03-31", "2021-06-26"],                     # first lockdown; Delta lockdown
    "delhi":     ["2020-03-25", "2021-04-19"],                     # national lockdown; Delhi lockdown
    "hongkong":  ["2020-03-29", "2020-07-15", "2022-02-10"],       # distancing rules; 3rd wave; 5th wave
    "singapore": ["2020-04-07", "2021-05-16", "2021-07-22"],       # circuit breaker; P2HA x2
}
CALM_MONTHS = ["2022-05", "2022-06", "2022-07", "2022-08", "2022-09"]  # same for every city

# S-arm (spatial transplant) derangement: chosen so that no city shares a
# post-2020-04 onset month with its fake city (checked by --check-smap).
FAKE_CITY = {
    "nyc": "milan", "milan": "melbourne", "melbourne": "madrid", "madrid": "tokyo",
    "tokyo": "sydney", "sydney": "delhi", "delhi": "hongkong", "hongkong": "singapore",
    "singapore": "london", "london": "nyc",
}

FIRST_NODE, LAST_NODE = "2020-03-15", "2022-09-15"   # 31 nodes per city
LOOKBACK_D, HORIZON_D = 28, 28


def extract_compact(zip_path: Path) -> pd.DataFrame:
    zf = zipfile.ZipFile(zip_path)
    frames = []
    for key, (cc, s1, s2, name, country) in REGIONS.items():
        parts = []
        for yr in (2020, 2021, 2022):
            df = pd.read_csv(io.BytesIO(zf.read(f"{yr}_{cc}_Region_Mobility_Report.csv")))
            if s1 is None:
                sel = df[df.sub_region_1.isna() & df.sub_region_2.isna()]
            elif s2 is None:
                sel = df[(df.sub_region_1 == s1) & df.sub_region_2.isna()]
            else:
                sel = df[(df.sub_region_1 == s1) & (df.sub_region_2 == s2)]
            parts.append(sel)
        sel = pd.concat(parts)
        out = pd.DataFrame({"city": key, "date": sel["date"].values})
        for c in CATS:
            out[c] = sel[COLS[c]].values
        frames.append(out)
    df = pd.concat(frames).sort_values(["city", "date"]).reset_index(drop=True)
    assert df.groupby("city").size().eq(974).all(), df.groupby("city").size()
    n_na = int(df[CATS].isna().sum().sum())
    if n_na:
        # disclosed: single missing cell (madrid grocery_and_pharmacy 2020-05-03) in the
        # source; linear interpolation within city. Count is recorded in SOURCE.json.
        df[CATS] = df.groupby("city")[CATS].transform(lambda s: s.interpolate(limit_direction="both"))
        assert df[CATS].isna().sum().sum() == 0
    df.attrs["interpolated_cells"] = n_na
    return df


def weekly_snapshot(sub: pd.DataFrame, t: pd.Timestamp) -> list[dict]:
    """Four weekly means ending at t (as-of truncation: rows <= t only)."""
    win = sub[(sub.date > t - pd.Timedelta(days=LOOKBACK_D)) & (sub.date <= t)]
    assert len(win) == LOOKBACK_D, (t, len(win))
    rows = []
    for w in range(4):
        chunk = win.iloc[w * 7:(w + 1) * 7]
        rows.append({"week": f"t-{3-w}w", **{c: round(float(chunk[c].mean()), 1) for c in CATS}})
    return rows


def realized(sub: pd.DataFrame, t: pd.Timestamp, cat: str) -> tuple[str, float]:
    before = sub[(sub.date > t - pd.Timedelta(days=HORIZON_D)) & (sub.date <= t)][cat].mean()
    after = sub[(sub.date > t) & (sub.date <= t + pd.Timedelta(days=HORIZON_D))][cat].mean()
    delta = float(after - before)
    return ("+" if delta >= 0 else "-"), round(delta, 2)


def build(df: pd.DataFrame) -> list[dict]:
    df = df.assign(date=pd.to_datetime(df.date))
    months = pd.period_range(FIRST_NODE[:7], LAST_NODE[:7], freq="M")
    nodes = []
    for key, (cc, s1, s2, name, country) in REGIONS.items():
        sub = df[df.city == key].sort_values("date")
        onset_months = {o[:7] for o in ONSETS[key]}
        for m in months:
            t = pd.Timestamp(f"{m}-15")
            ym = str(m)
            d_r, delta_r = realized(sub, t, TARGET_CAT)
            d_t, delta_t = realized(sub, t, ALT_CAT)
            nodes.append({
                "node_id": f"{key}_{ym}",
                "city": key, "city_name": name, "country": country, "country_code": cc,
                "decision_date": t.strftime("%Y-%m-%d"),
                "snapshot": weekly_snapshot(sub, t),
                "realized_retail": d_r, "realized_retail_delta": delta_r,
                "realized_transit": d_t, "realized_transit_delta": delta_t,
                "is_crisis": ym in onset_months,
                "is_calm": ym in CALM_MONTHS,
                "onsets_in_month": [o for o in ONSETS[key] if o[:7] == ym],
                "fake_city": FAKE_CITY[key],
            })
    return nodes


def check_smap() -> None:
    for a, b in FAKE_CITY.items():
        assert a != b
        la = {o[:7] for o in ONSETS[a] if o >= "2020-05"}
        lb = {o[:7] for o in ONSETS[b] if o >= "2020-05"}
        assert not (la & lb), f"S-map {a}->{b} shares post-2020-04 onset months {la & lb}"
    assert sorted(FAKE_CITY.values()) == sorted(FAKE_CITY), "not a permutation"
    print("S-map OK: derangement, no shared post-2020-04 onset months")


def summary(nodes: list[dict]) -> str:
    n = len(nodes)
    cr = [x for x in nodes if x["is_crisis"]]
    ca = [x for x in nodes if x["is_calm"]]
    L = ["# ST-1 panel summary", "",
         f"nodes: {n} ({len(REGIONS)} cities x {n // len(REGIONS)} months, {FIRST_NODE}..{LAST_NODE})",
         f"crisis nodes: {len(cr)}; calm nodes: {len(ca)}", "",
         "| city | crisis months | realized '-' share (retail) all / crisis / calm |", "|---|---|---|"]
    for key in REGIONS:
        xs = [x for x in nodes if x["city"] == key]
        f = lambda ys: (sum(1 for y in ys if y["realized_retail"] == "-") / len(ys)) if ys else float("nan")
        L.append(f"| {key} | {', '.join(x['decision_date'][:7] for x in xs if x['is_crisis'])} | "
                 f"{f(xs):.2f} / {f([x for x in xs if x['is_crisis']]):.2f} / {f([x for x in xs if x['is_calm']]):.2f} |")
    L += ["", f"realized '-' base rate (retail, all nodes): {sum(1 for x in nodes if x['realized_retail']=='-')/n:.3f}",
          f"realized '-' base rate (transit, all nodes): {sum(1 for x in nodes if x['realized_transit']=='-')/n:.3f}",
          "", "S-arm fake-city map: " + ", ".join(f"{a}->{b}" for a, b in FAKE_CITY.items())]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, help="Region_Mobility_Report_CSVs.zip (extract compact CSV)")
    ap.add_argument("--check-smap", action="store_true")
    args = ap.parse_args()
    check_smap()
    if args.check_smap:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "raw").mkdir(exist_ok=True)
    (OUT / "panel").mkdir(exist_ok=True)
    if args.zip:
        sha = hashlib.sha256(args.zip.read_bytes()).hexdigest()
        df = extract_compact(args.zip)
        df.to_csv(RAW, index=False)
        (OUT / "raw/SOURCE.json").write_text(json.dumps({
            "url": "https://www.gstatic.com/covid19/mobility/Region_Mobility_Report_CSVs.zip",
            "zip_sha256": sha, "zip_bytes": args.zip.stat().st_size,
            "extracted_at": dt.datetime.now().isoformat(timespec="seconds"),
            "interpolated_cells": df.attrs.get("interpolated_cells", 0),
            "regions": {k: v[:3] for k, v in REGIONS.items()}}, indent=2))
        print(f"compact CSV written: {RAW} ({len(df)} rows), zip sha256 {sha[:12]}")
    df = pd.read_csv(RAW)
    nodes = build(df)
    with PANEL.open("w") as f:
        for x in nodes:
            f.write(json.dumps(x) + "\n")
    s = summary(nodes)
    (OUT / "panel/PANEL_SUMMARY.md").write_text(s)
    ph = hashlib.sha256(PANEL.read_bytes()).hexdigest()
    print(s)
    print(f"panel sha256 {ph}")


if __name__ == "__main__":
    main()
