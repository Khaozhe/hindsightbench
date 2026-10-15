#!/usr/bin/env python3
"""BM-2c addendum J: split the Tulu 3 70B RLVR tier contrast (AWQ fp16-act minus FP8 = +29.7 pp) into
activation dtype and AWQ weights, with a same-box replicate of each original tier (frozen readings).

Rows (all Tulu 3 70B RLVR, 4 x A100-40G, TP=4, vLLM 0.29, CONC 16, temp 0.2):
  T3 FP8 W8A16 / bf16 act (addendum F)      J2 = T3, second independent run
  F3 AWQ INT4 / fp16 act  (addendum F)      J3 = F3, second independent run
  J1 AWQ INT4 (F3's weights) / bf16 act
Estimators are addendum I's (analyze_dose_response.contrast/channels, imported unchanged): E2 from the row
file with its parity gate and a date bootstrap (B=10,000, seed 2026); DATE = USREC slope of the per-date
D-arm difference, HAC 6; BASE = mean per-date M-arm difference with a date-bootstrap CI.
Noise floor per channel = max over the two replicate pairs (J2-T3, J3-F3) of |difference|; E2 floor also
>= 16.2 pp. BEYOND = test excludes zero (CI; |t| >= 1.96 for DATE) AND |difference| > floor. A channel on
which either replicate pair is itself significant is UNSTABLE: no reading on it.

    python scripts/analyze_tier_split.py
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import analyze_dose_response as dr  # noqa: E402  (addendum I estimators, frozen there)

K = {"T3": "tulu3-70b-rlvr-fp8dyn", "J2": "tulu3-70b-rlvr-fp8dyn-r2",
     "F3": "tulu3-70b-rlvr-awq", "J3": "tulu3-70b-rlvr-awq-r2", "J1": "tulu3-70b-rlvr-awq-bf16act"}
LAB = {"T3": "FP8 W8A16, bf16 act", "J2": "FP8 W8A16, bf16 act (second run)", "F3": "AWQ INT4, fp16 act",
       "J3": "AWQ INT4, fp16 act (second run)", "J1": "AWQ INT4, bf16 act"}
E2_FLOOR_MIN = 16.2


def sig(c, x):
    if x == "DATE":
        return abs(c["DATE"][1]) >= 1.96
    return c[x] is not None and (c[x][1] > 0 or c[x][2] < 0)


def val(c, x):
    return None if c[x] is None else c[x][0]


def fmt(c, x):
    if x == "E2" and c["E2"] is None:
        return "gated"
    if x == "DATE":
        return "%+.1f (t %+.2f)" % c["DATE"]
    return "%+.1f [%+.1f, %+.1f]" % c[x]


def main():
    have = {t: k for t, k in K.items() if dr.row(k) is not None}
    print("BM-2c addendum J — Tulu 3 70B RLVR tier split, 4 x A100-40G TP=4\n")
    for t in ("T3", "J2", "F3", "J3", "J1"):
        if t not in have:
            print(f"{t:3s} {LAB[t]:34s} pending"); continue
        c = dr.channels(have[t])
        e2 = "  gated" if c["E2"] is None else f"{c['E2']:+7.1f}"
        print(f"{t:3s} {LAB[t]:34s} E2 {e2} | G2 t {c['G2t']:+.2f} | DATE {c['DATE']:+.1f} (t {c['DATE_t']:+.2f}) | BASE {c['BASE']:.1f}")
    if not all(t in have for t in K):
        print("\nreadings wait for all five rows"); return
    C = lambda a, b: dr.contrast(have[a], have[b])
    reps = {"J2-T3": C("J2", "T3"), "J3-F3": C("J3", "F3")}
    floor, unstable = {}, {}
    for x in ("E2", "DATE", "BASE"):
        mags = [abs(val(c, x)) for c in reps.values() if val(c, x) is not None]
        floor[x] = (max(mags + [E2_FLOOR_MIN]) if x == "E2" else max(mags)) if mags else float("nan")
        unstable[x] = any(sig(c, x) for c in reps.values())
    print("\nreplicate pairs (same tier, same box):")
    for n, c in reps.items():
        print(f"  {n}: E2 {fmt(c, 'E2')} | DATE {fmt(c, 'DATE')} | BASE {fmt(c, 'BASE')}")
    print("  floors: " + ", ".join(f"{x} {floor[x]:.1f}" + (" UNSTABLE" if unstable[x] else "") for x in floor))

    def beyond(c, x):
        v = val(c, x)
        return (not unstable[x]) and v is not None and sig(c, x) and abs(v) > floor[x]

    pairs = {"R1 replication (J3-J2)": [("J3", "J2")], "R2 dtype (F3-J1, J3-J1)": [("F3", "J1"), ("J3", "J1")],
             "R3 AWQ weights (J1-T3, J1-J2)": [("J1", "T3"), ("J1", "J2")]}
    res = {}
    print("\ncontrasts:")
    for name, prs in pairs.items():
        res[name] = []
        for a, b in prs:
            c = C(a, b); res[name].append(c)
            print(f"  {a} minus {b}: E2 {fmt(c, 'E2')}{' BEYOND' if beyond(c, 'E2') else ''} | "
                  f"DATE {fmt(c, 'DATE')}{' BEYOND' if beyond(c, 'DATE') else ''} | BASE {fmt(c, 'BASE')}{' BEYOND' if beyond(c, 'BASE') else ''}")

    def both(cs, x):   # beyond against both references, same sign
        return all(beyond(c, x) for c in cs) and len({val(c, x) > 0 for c in cs}) == 1

    print("\nreadings (frozen, addendum J):")
    r1 = res["R1 replication (J3-J2)"][0]
    rep_ok = r1["E2"] is not None and r1["E2"][1] > 0
    print("  R1: the AWQ-fp16 minus FP8 E2 contrast " + ("REPLICATES (second-run CI above zero)" if rep_ok else "DOES NOT REPLICATE (second-run CI includes or lies below zero)"))
    r2 = {x: both(res["R2 dtype (F3-J1, J3-J1)"], x) for x in ("E2", "DATE")}
    r3 = {x: both(res["R3 AWQ weights (J1-T3, J1-J2)"], x) for x in ("E2", "DATE")}
    print("  R2 DTYPE: " + ("activation dtype moves the date route on this checkpoint (" + ", ".join(x for x in r2 if r2[x]) + ")" if any(r2.values()) else "not beyond the floor against both fp16 runs"))
    print("  R3 WEIGHTS: " + ("AWQ weights move the date route at bf16 activations (" + ", ".join(x for x in r3 if r3[x]) + ")" if any(r3.values()) else "not beyond the floor against both FP8 runs"))
    if not any(r2.values()) and not any(r3.values()):
        print("  -> " + ("tier effect replicates but neither component alone clears the floor against both references" if rep_ok
                          else "the +29.7 pp contrast neither replicates nor is attributable to dtype or weights"))
    for name, cs in res.items():
        if name.startswith("R1"):
            continue
        if both(cs, "BASE"):
            print(f"  BASELINE SHIFT ({name}): level change beyond the floor against both references, reported separately")


if __name__ == "__main__":
    main()
