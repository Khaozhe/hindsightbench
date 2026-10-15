#!/usr/bin/env python
"""ST-1 analysis per frozen prereg f0284181: (date, location) key decomposition.

Estimands (Gap = bearish '-' share(crisis) - share(calm), true-city sets):
  E2   = Gap(D)  - Gap(M)        time trigger
  E2L  = Gap(L)  - Gap(M)        place trigger
  E2DL = Gap(DL) - Gap(M)        joint key
  INT  = E2DL - E2 - E2L         super-additivity
  E3L  = Gap_fake(S) - Gap_true(S)   spatial transplant (same S generations, fake- vs true-city crisis sets)
Probes: LAP-ST per city (recall rate, hit vs realized, majority-class gate 0.629); REC-ST (date +-3mo, city, joint).
Bootstrap: node-level paired (primary) + city-cluster (sensitivity), B=10,000, seed 2026.

Usage: python analyze_st1.py --tag gemini-2.5-flash [--selftest]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

from hindsight_paths import REPO
from build_st_panel import REGIONS, FAKE_CITY, ONSETS

OUT_ROOT = REPO / "hindsight/outputs/st1"
PANEL = OUT_ROOT / "panel/nodes.jsonl"
B, SEED = 10_000, 2026
MAJORITY_GATE = None  # filled from panel: realized '+' share

CITY_ALIASES = {
    "nyc": ["new york", "manhattan", "nyc"], "milan": ["milan", "lombardy", "lombardia"],
    "london": ["london"], "madrid": ["madrid"], "tokyo": ["tokyo"],
    "melbourne": ["melbourne", "victoria"], "sydney": ["sydney", "new south wales", "nsw"],
    "delhi": ["delhi"], "hongkong": ["hong kong", "hongkong"], "singapore": ["singapore"],
}


def load_panel() -> dict[str, dict]:
    return {json.loads(l)["node_id"]: json.loads(l) for l in PANEL.read_text().splitlines() if l.strip()}


def load_arm(row_dir: Path, arm: str) -> dict[str, list[str]]:
    by_node = defaultdict(list)
    for node in (row_dir / arm).glob("rep*/*"):   # pools every replicate directory present
        f = node / "01_sketches_valid.json"
        if f.exists():
            for s in json.loads(f.read_text()):
                if s.get("direction") in ("+", "-"):
                    by_node[node.name].append(s["direction"])
    return by_node


def share(by_node, ids) -> float:
    xs = [x for i in ids for x in by_node.get(i, [])]
    return sum(1 for x in xs if x == "-") / len(xs) if xs else float("nan")


def gap(by_node, crisis, calm) -> float:
    return share(by_node, crisis) - share(by_node, calm)


def boot_node(fn, crisis, calm, rng):
    """fn(crisis_ids, calm_ids) -> float; node-level paired resampling of both sets."""
    c, q = np.array(crisis), np.array(calm)
    out = np.empty(B)
    for b in range(B):
        out[b] = fn(list(rng.choice(c, len(c), replace=True)), list(rng.choice(q, len(q), replace=True)))
    return float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5))


def boot_city(fn, crisis, calm, rng):
    """city-cluster resampling: resample cities with replacement, keep each city's nodes."""
    cities = sorted({i.split("_")[0] for i in crisis + calm})
    by_c = {c: ([i for i in crisis if i.startswith(c + "_")], [i for i in calm if i.startswith(c + "_")]) for c in cities}
    out = np.empty(B)
    for b in range(B):
        pick = rng.choice(cities, len(cities), replace=True)
        cs = [i for c in pick for i in by_c[c][0]]
        qs = [i for c in pick for i in by_c[c][1]]
        out[b] = fn(cs, qs)
    return float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5))


def fake_sets(panel: dict) -> tuple[list[str], list[str]]:
    """crisis/calm membership of each node scored under its FAKE city's onset months."""
    crisis, calm = [], []
    for nid, n in panel.items():
        fm = {o[:7] for o in ONSETS[n["fake_city"]]}
        if n["decision_date"][:7] in fm:
            crisis.append(nid)
        if n["is_calm"]:
            calm.append(nid)
    return crisis, calm


def lap_stats(row_dir: Path, panel: dict):
    f = row_dir / "lap_results.jsonl"
    if not f.exists():
        return None
    cnt = defaultdict(lambda: defaultdict(int))
    for l in f.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            cnt[r["node_id"]][r["answer"]] += 1
    per_city = defaultdict(lambda: {"n": 0, "recall": [], "hit_k": 0, "hit_n": 0})
    for nid, c in cnt.items():
        n = sum(c.values())
        if not n:
            continue
        city = panel[nid]["city"]
        rec = (c["higher"] + c["lower"]) / n
        net = (c["higher"] - c["lower"]) / n
        d = per_city[city]
        d["n"] += 1
        d["recall"].append(rec)
        if abs(net) > 1e-9:
            d["hit_n"] += 1
            d["hit_k"] += int(("+" if net > 0 else "-") == panel[nid]["realized_retail"])
    rows = {}
    for city, d in per_city.items():
        rows[city] = {"nodes": d["n"], "recall": float(np.mean(d["recall"])),
                      "hit": d["hit_k"] / d["hit_n"] if d["hit_n"] else float("nan"), "hit_n": d["hit_n"]}
    tot_k = sum(d["hit_k"] for d in per_city.values())
    tot_n = sum(d["hit_n"] for d in per_city.values())
    rows["ALL"] = {"nodes": sum(d["n"] for d in per_city.values()),
                   "recall": float(np.mean([r for d in per_city.values() for r in d["recall"]])),
                   "hit": tot_k / tot_n if tot_n else float("nan"), "hit_n": tot_n}
    return rows


def rec_stats(row_dir: Path, panel: dict):
    f = row_dir / "rec_results.jsonl"
    if not f.exists():
        return None
    per_city = defaultdict(lambda: {"n": 0, "date3": 0, "city": 0, "joint": 0})
    for l in f.read_text().splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        n = panel[r["node_id"]]
        d = per_city[n["city"]]
        d["n"] += 1
        ok_d = ok_c = False
        m = re.match(r"(\d{4})-(\d{2})", r.get("estimated_date", "") or "")
        if m:
            est = int(m.group(1)) * 12 + int(m.group(2))
            tru = int(n["decision_date"][:4]) * 12 + int(n["decision_date"][5:7])
            ok_d = abs(est - tru) <= 3
        ec = (r.get("estimated_city") or "").lower()
        ok_c = any(a in ec for a in CITY_ALIASES[n["city"]])
        d["date3"] += ok_d; d["city"] += ok_c; d["joint"] += (ok_d and ok_c)
    rows = {c: {k: (v / d["n"] if k != "n" else v) for k, v in d.items()} for c, d in per_city.items()}
    tot = {"n": sum(d["n"] for d in per_city.values())}
    for k in ("date3", "city", "joint"):
        tot[k] = sum(d[k] for d in per_city.values()) / tot["n"] if tot["n"] else float("nan")
    rows["ALL"] = tot
    return rows


ROWJ: dict = {}


def analyze(row_dir: Path, panel: dict) -> str:
    rng = np.random.default_rng(SEED)
    ROWJ.clear(); ROWJ["tag"] = row_dir.name
    crisis = [i for i, n in panel.items() if n["is_crisis"]]
    calm = [i for i, n in panel.items() if n["is_calm"]]
    arms = {a: load_arm(row_dir, a) for a in ("M", "D", "L", "DL", "S")}
    cov = {a: len(v) for a, v in arms.items()}
    plus_share = sum(1 for n in panel.values() if n["realized_retail"] == "+") / len(panel)
    L = [f"# ST-1 results: {row_dir.name} (prereg f0284181)", "",
         f"coverage (nodes with >=1 valid sketch): {cov}", f"crisis nodes {len(crisis)}, calm nodes {len(calm)}", ""]
    g = {a: gap(arms[a], crisis, calm) for a in ("M", "D", "L", "DL")}
    ROWJ["coverage"] = cov; ROWJ["plus_share"] = plus_share; ROWJ["n_crisis"] = len(crisis); ROWJ["n_calm"] = len(calm)
    ROWJ["gaps"] = {a: {"crisis": share(arms[a], crisis), "calm": share(arms[a], calm), "gap": g[a]} for a in g}
    ROWJ["S_gap_true"] = gap(arms["S"], crisis, calm)
    L.append("| arm | share(crisis) | share(calm) | Gap |")
    L.append("|---|---|---|---|")
    for a in ("M", "D", "L", "DL"):
        L.append(f"| {a} | {share(arms[a], crisis):.3f} | {share(arms[a], calm):.3f} | {g[a]:+.3f} |")
    L.append("")

    def est(name, fn):
        pt = fn(crisis, calm)
        lo, hi = boot_node(fn, crisis, calm, rng)
        clo, chi = boot_city(fn, crisis, calm, rng)
        sig = "excl0" if (lo > 0 or hi < 0) else "incl0"
        L.append(f"- **{name} = {pt:+.3f}** node-CI [{lo:+.3f}, {hi:+.3f}] ({sig}); city-cluster CI [{clo:+.3f}, {chi:+.3f}]")
        ROWJ[name.split(" ")[0]] = {"pt": pt, "lo": lo, "hi": hi, "clo": clo, "chi": chi}
        return pt, lo, hi

    M, D, Lm, DL, S = (arms[a] for a in ("M", "D", "L", "DL", "S"))
    e2 = est("E2 (time trigger, S1)", lambda c, q: gap(D, c, q) - gap(M, c, q))
    e2l = est("E2L (place trigger, S2)", lambda c, q: gap(Lm, c, q) - gap(M, c, q))
    e2dl = est("E2DL (joint key, S3)", lambda c, q: gap(DL, c, q) - gap(M, c, q))
    est("INT = E2DL - E2 - E2L (S3)", lambda c, q: (gap(DL, c, q) - gap(M, c, q)) - (gap(D, c, q) - gap(M, c, q)) - (gap(Lm, c, q) - gap(M, c, q)))

    # E3L: same S generations, fake-city vs true-city crisis membership
    fcrisis, fcalm = fake_sets(panel)
    L.append("")
    L.append(f"S arm: Gap_true = {gap(S, crisis, calm):+.3f}, Gap_fake = {gap(S, fcrisis, fcalm):+.3f} "
             f"(fake-crisis nodes {len(fcrisis)})")
    # prereg-faithful bootstrap: fake and true crisis sets resampled independently, calm shared
    fc, tc, qq = np.array(fcrisis), np.array(crisis), np.array(calm)
    out = np.empty(B)
    for b in range(B):
        qs = list(rng.choice(qq, len(qq), replace=True))
        out[b] = gap(S, list(rng.choice(fc, len(fc), replace=True)), qs) - gap(S, list(rng.choice(tc, len(tc), replace=True)), qs)
    pt = gap(S, fcrisis, fcalm) - gap(S, crisis, calm)
    lo, hi = float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5))
    L.append(f"- **E3L (spatial transplant, S4) = {pt:+.3f}** CI [{lo:+.3f}, {hi:+.3f}] ({'excl0' if lo > 0 or hi < 0 else 'incl0'})")
    ROWJ["E3L"] = {"pt": pt, "lo": lo, "hi": hi}
    # POST-FREEZE REFINEMENT (disclosed): the prereg E3L null is not 0 when the data itself carries the
    # true city's crisis (M gap > 0): under "asserted place ignored", E3L equals the D arm's own fake-minus-true
    # gap. The D-referenced contrasts below isolate what the fake-city assertion adds (relocation) or removes
    # (interference) relative to date-only.
    d_ref = gap(D, fcrisis, calm) - gap(D, crisis, calm)
    L.append(f"  - post-freeze reference: D-arm fake-minus-true = {d_ref:+.3f} (the E3L value 'place ignored' predicts)")
    ROWJ["E3L_ref_D"] = d_ref
    est_f = lambda name, fn, c, q: None
    def est2(name, fn, c, q):
        p0 = fn(c, q); l0, h0 = boot_node(fn, c, q, rng)
        L.append(f"  - **{name} = {p0:+.3f}** node-CI [{l0:+.3f}, {h0:+.3f}] ({'excl0' if l0 > 0 or h0 < 0 else 'incl0'})")
        ROWJ[name.split(":")[0]] = {"pt": p0, "lo": l0, "hi": h0}
    est2("relocation: Gap_fake(S) - Gap_fake(D)", lambda c, q: gap(S, c, q) - gap(D, c, q), fcrisis, calm)
    est2("interference: Gap_true(S) - Gap_true(D)", lambda c, q: gap(S, c, q) - gap(D, c, q), crisis, calm)

    # per-city descriptive E2 (within-city crisis vs calm)
    L += ["", "| city | n_crisis | Gap(M) | Gap(D) | E2_city | Gap(L) | Gap(DL) |", "|---|---|---|---|---|---|---|"]
    for city in REGIONS:
        c = [i for i in crisis if i.startswith(city + "_")]
        q = [i for i in calm if i.startswith(city + "_")]
        if not c:
            continue
        L.append(f"| {city} | {len(c)} | {gap(M, c, q):+.2f} | {gap(D, c, q):+.2f} | {gap(D, c, q) - gap(M, c, q):+.2f} "
                 f"| {gap(Lm, c, q):+.2f} | {gap(DL, c, q):+.2f} |")

    lap = lap_stats(row_dir, panel)
    L += ["", f"## LAP-ST (memory gate S5: hit > majority-class {plus_share:.3f})"]
    if lap:
        L += ["| city | nodes | recall rate | hit | hit_n |", "|---|---|---|---|---|"]
        for city in list(REGIONS) + ["ALL"]:
            if city in lap:
                r = lap[city]
                L.append(f"| {city} | {r['nodes']} | {r['recall']:.3f} | {r['hit']:.3f} | {r['hit_n']} |")
        L.append(f"- memory gate: {'PASS' if lap['ALL']['hit'] > plus_share else 'FAIL'}")
        ROWJ["lap"] = lap; ROWJ["memory_gate"] = lap['ALL']['hit'] > plus_share
    else:
        L.append("(no lap_results.jsonl)")
    rec = rec_stats(row_dir, panel)
    L += ["", "## REC-ST (spatio-temporal recoverability, S6)"]
    ROWJ["rec"] = rec
    if rec:
        L += ["| city | n | date +-3mo | city exact | joint |", "|---|---|---|---|---|"]
        for city in list(REGIONS) + ["ALL"]:
            if city in rec:
                r = rec[city]
                L.append(f"| {city} | {r['n']} | {r['date3']:.3f} | {r['city']:.3f} | {r['joint']:.3f} |")
    else:
        L.append("(no rec_results.jsonl)")
    return "\n".join(L) + "\n"


def selftest(panel: dict) -> None:
    """Synthetic row: D/DL/S bearish on crisis-by-asserted-key, M/L flat. Expect E2>0, E2L~0, E3L>0."""
    import shutil, tempfile
    rng = np.random.default_rng(0)
    tmp = Path(tempfile.mkdtemp()) / "selftest"
    for a in ("M", "D", "L", "DL", "S"):
        for nid, n in panel.items():
            d = tmp / a / "rep1" / nid
            d.mkdir(parents=True)
            fm = {o[:7] for o in ONSETS[n["fake_city"]]}
            key_crisis = {"M": False, "L": False, "D": n["is_crisis"], "DL": n["is_crisis"],
                          "S": n["decision_date"][:7] in fm}[a]
            p = 0.8 if key_crisis else 0.3
            dirs = ["-" if rng.random() < p else "+" for _ in range(8)]
            (d / "01_sketches_valid.json").write_text(json.dumps([{"direction": x} for x in dirs]))
    print(analyze(tmp, panel))
    shutil.rmtree(tmp.parent)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="gemini-2.5-flash")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    panel = load_panel()
    if args.selftest:
        selftest(panel)
        return
    row_dir = OUT_ROOT / args.tag
    txt = analyze(row_dir, panel)
    (row_dir / "ST1_RESULTS.md").write_text(txt)
    (row_dir / f"{row_dir.name}_st1_row.json").write_text(json.dumps(ROWJ, indent=2))
    print(txt)


if __name__ == "__main__":
    main()
