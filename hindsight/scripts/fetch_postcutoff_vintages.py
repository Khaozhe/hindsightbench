#!/usr/bin/env python
"""Fetch ALFRED vintage snapshots for post-cutoff decision dates (FM-1c placebo prep).

For each decision date 2025-01-15..2026-06-15 and each of the 8 V1 series,
retrieves the latest observation *as known on the decision date* (vintage) and
the current revised value, mirroring the fields used in V1 prompts.

Output: hindsight/outputs/fm1c/postcutoff_snapshots.json
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import requests

from hindsight_paths import REPO
OUT = REPO / "hindsight/outputs/fm1c"
SERIES = ["CPIAUCSL", "FEDFUNDS", "GDPC1", "HOUST", "INDPRO", "PAYEMS", "RSAFS", "UNRATE"]
BASE = "https://api.stlouisfed.org/fred/series/observations"


def api_key() -> str:
    for line in (REPO / "FRED_API_KEY.env").read_text().splitlines():
        if "=" in line:
            return line.split("=", 1)[1].strip()
    raise RuntimeError("no FRED key")


def decision_dates() -> list[str]:
    out = []
    y, m = 2025, 1
    while (y, m) <= (2026, 6):
        out.append(f"{y:04d}-{m:02d}-15")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def fetch(series: str, key: str, realtime: str | None, limit_end: str) -> list[dict]:
    """observations known as of `realtime` (vintage) or latest (realtime=None)."""
    params = {
        "series_id": series, "api_key": key, "file_type": "json",
        "observation_start": "2023-01-01", "observation_end": limit_end,
        "sort_order": "desc", "limit": 24,
    }
    if realtime:
        params["realtime_start"] = params["realtime_end"] = realtime
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("observations", [])


def main() -> None:
    key = api_key()
    OUT.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict] = {}
    for dd in decision_dates():
        snap = {}
        for sid in SERIES:
            try:
                vint = fetch(sid, key, dd, dd)
            except requests.HTTPError as e:
                # realtime date beyond ALFRED coverage -> record and skip
                snap[sid] = {"error": str(e)}
                continue
            vint_valid = [o for o in vint if o["value"] != "."]
            if not vint_valid:
                snap[sid] = {"error": "no vintage obs"}
                continue
            v0 = vint_valid[0]  # latest observation known at dd
            rev = fetch(sid, key, None, dd)
            rev_map = {o["date"]: o["value"] for o in rev if o["value"] != "."}
            snap[sid] = {
                "vintage_date": v0["date"],
                "vintage_value": v0["value"],
                "revised_value": rev_map.get(v0["date"], v0["value"]),
            }
            time.sleep(0.15)  # FRED rate courtesy
        result[dd] = snap
        ok = sum(1 for v in snap.values() if "error" not in v)
        print(f"{dd}: {ok}/8 series ok")
    payload = {
        "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
        "note": "vintage = latest obs known at decision date (ALFRED realtime); "
                "revised = value for same obs date as known today",
        "snapshots": result,
    }
    (OUT / "postcutoff_snapshots.json").write_text(json.dumps(payload, indent=2))
    print(f"written {OUT/'postcutoff_snapshots.json'}")


if __name__ == "__main__":
    main()
