#!/usr/bin/env python3
"""BM-2c addendum I: precision dose-response on Qwen3-30B-A3B-Thinking-2507 (frozen readings).

Channels per rung: E2 (row json), G2 (addendum G), DATE = recession slope of the D arm's bearish share
(HAC 6, dates <= 2023-12), BASE = mean bearish share of the M arm over all panel dates.
Each quantized/dtype rung is contrasted with I1 (BF16). The same-box noise floor per channel is the
I3 (BF16, second independent run) minus I1 difference; for E2 the floor is max(that, 16.2 pp).
A contrast is BEYOND the floor iff its test excludes zero (E2/BASE: 95% date-bootstrap CI; DATE:
|t| >= 1.96, HAC 6) AND its magnitude exceeds the floor."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from analyze_fm1 import CRISIS, CALM_YEARS, all_dates, gap, build_covariates  # noqa: E402
from analyze_wholepanel import g2, bearish_share, WINDOW_END  # noqa: E402
import statsmodels.api as sm  # noqa: E402

BENCH = Path(__file__).resolve().parents[1] / "outputs/bench"
P = "qwen3-30b-a3b-thinking-2507-"
RUNGS = [("I1", P + "bf16", "BF16 (reference)", 16), ("I2", P + "awq", "AWQ INT4 g128 (QuantTrio), bf16 act", 4),
         ("I3", P + "bf16-r2", "BF16, second run (noise floor)", 16), ("I4", P + "gptq-w4a16", "GPTQ INT4 w4a16 g128 (RedHatAI)", 4),
         ("I5", P + "int8-w8a8", "INT8 w8a8 (RedHatAI)", 8), ("I6", P + "fp8block", "FP8 block-128 (Qwen official)", 8),
         ("I7", P + "bf16-fp16act", "BF16 weights, fp16 activations (dtype control)", 16)]
E2_FLOOR_MIN = 16.2
B, SEED = 10_000, 2026
dates = all_dates(); crisis = [d for d in dates if d in CRISIS]; calm = [d for d in dates if d[:4] in CALM_YEARS]
cov = build_covariates([d for d in dates if d <= WINDOW_END])


def row(k):
    f = BENCH / k / f"{k}_row.json"
    return json.loads(f.read_text()) if f.exists() else None


def by_date(k, arm):
    o = {}
    for n in (BENCH / k / arm).glob("rep*/*"):
        f = n / "01_sketches_valid.json"
        if f.exists():
            o.setdefault(n.name, []).extend(s["direction"] for s in json.loads(f.read_text()) if s.get("direction") in ("+", "-"))
    return o


def hac(y: dict) -> tuple[float, float]:
    df = cov.copy(); df["y"] = [y.get(d, np.nan) for d in df.index]; df = df.dropna(subset=["y", "usrec"])
    f = sm.OLS(df["y"].values, sm.add_constant(df[["usrec"]].values)).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    return float(f.params[1] * 100), float(f.tvalues[1])


def channels(k):
    D, M = by_date(k, "D"), by_date(k, "M")
    e = row(k)["E2_date_trigger"]   # the row file's value, as the addendum specifies; None when the parity gate fires
    e2 = None if e.get("gated") else e["est"] * 100
    ds = bearish_share(k, "D"); ms = bearish_share(k, "M")
    slope, t = hac(ds)
    return {"E2": e2, "G2t": g2(k, cov)["t"], "DATE": slope, "DATE_t": t, "BASE": float(np.mean(list(ms.values()))) * 100}


def e2_gated(k):
    return bool(row(k)["E2_date_trigger"].get("gated"))


def contrast(ka, kb):
    """ka minus kb on each channel, same dates. E2 is None when either row's E2 is gated (parity gate)."""
    A = {a: by_date(ka, a) for a in "DM"}; Bb = {a: by_date(kb, a) for a in "DM"}
    rng = np.random.default_rng(SEED); c, q = np.array(crisis), np.array(calm); out = np.empty(B)
    e2 = lambda X, cs, qs: gap(X["D"], cs, qs) - gap(X["M"], cs, qs)
    for i in range(B):
        cs, qs = list(rng.choice(c, len(c))), list(rng.choice(q, len(q))); out[i] = e2(A, cs, qs) - e2(Bb, cs, qs)
    dE2 = (e2(A, crisis, calm) - e2(Bb, crisis, calm)) * 100
    Da, Db = bearish_share(ka, "D"), bearish_share(kb, "D")
    dDATE, tDATE = hac({d: Da[d] - Db[d] for d in Da if d in Db})
    Ma, Mb = bearish_share(ka, "M"), bearish_share(kb, "M"); common = sorted(set(Ma) & set(Mb))
    diffs = np.array([Ma[d] - Mb[d] for d in common]); rng2 = np.random.default_rng(SEED)
    boots = [diffs[rng2.integers(0, len(diffs), len(diffs))].mean() for _ in range(B)]
    e2c = None if (e2_gated(ka) or e2_gated(kb)) else (dE2, np.percentile(out, 2.5) * 100, np.percentile(out, 97.5) * 100)
    return {"E2": e2c, "DATE": (dDATE, tDATE),
            "BASE": (diffs.mean() * 100, np.percentile(boots, 2.5) * 100, np.percentile(boots, 97.5) * 100)}


def main():
    have = {tag: k for tag, k, _, _ in RUNGS if row(k) is not None}
    print("BM-2c addendum I — precision dose-response, Qwen3-30B-A3B-Thinking-2507, 4 x A100-40G TP=4\n")
    print(f"{'rung':4s} {'tier':44s} {'E2 pp':>7s} {'G2 t':>6s} {'DATE pp (t)':>14s} {'BASE %':>7s}  memory (hit, n, post-LAP)")
    ch = {}
    for tag, k, lab, bits in RUNGS:
        r = row(k)
        if r is None:
            print(f"{tag:4s} {lab:44s} pending"); continue
        c = ch[tag] = channels(k); lap = r["LAP"]
        e2s = "  gated" if c["E2"] is None else f"{c['E2']:+7.1f}"
        print(f"{tag:4s} {lab:44s} {e2s} {c['G2t']:+6.2f} {c['DATE']:+7.1f} ({c['DATE_t']:+5.2f}) {c['BASE']:7.1f}  "
              f"{(lap.get('recall_hit_rate') or 0)*100:.1f}%, {lap.get('recall_n')}, {lap.get('post_mean')}")
    if "I1" not in have or "I3" not in have:
        print("\nreadings wait for I1 and I3 (the same-box noise floor)"); return
    fl = contrast(have["I3"], have["I1"])
    if fl["E2"] is None:
        print("\nI1 or I3 E2 is gated -> no E2 noise floor, no E2 tier reading"); fl["E2"] = (float("nan"), 0.0, 0.0)
    floor = {"E2": max(abs(fl["E2"][0]), E2_FLOOR_MIN), "DATE": abs(fl["DATE"][0]), "BASE": abs(fl["BASE"][0])}
    print(f"\nsame-box noise floor (I3 minus I1): E2 {fl['E2'][0]:+.1f} [{fl['E2'][1]:+.1f}, {fl['E2'][2]:+.1f}] -> floor {floor['E2']:.1f} pp; "
          f"DATE {fl['DATE'][0]:+.1f} (t {fl['DATE'][1]:+.2f}) -> floor {floor['DATE']:.1f}; BASE {fl['BASE'][0]:+.1f} -> floor {floor['BASE']:.1f}")
    unstable = {"E2": fl["E2"][1] > 0 or fl["E2"][2] < 0, "DATE": abs(fl["DATE"][1]) >= 1.96, "BASE": fl["BASE"][1] > 0 or fl["BASE"][2] < 0}
    for x, u in unstable.items():
        if u: print(f"  {x}: I3 minus I1 is itself significant -> channel UNSTABLE on this box, no tier reading on it")
    beyond = {}
    for tag, k, lab, bits in RUNGS:
        if tag in ("I1", "I3") or tag not in have:
            continue
        c = contrast(have[tag], have["I1"])
        bE2 = c["E2"] is not None and (c["E2"][1] > 0 or c["E2"][2] < 0) and abs(c["E2"][0]) > floor["E2"]
        bD = abs(c["DATE"][1]) >= 1.96 and abs(c["DATE"][0]) > floor["DATE"]
        bB = (c["BASE"][1] > 0 or c["BASE"][2] < 0) and abs(c["BASE"][0]) > floor["BASE"]
        bE2, bD, bB = bE2 and not unstable["E2"], bD and not unstable["DATE"], bB and not unstable["BASE"]
        beyond[tag] = {"E2": bE2, "DATE": bD, "BASE": bB, "dDATE": c["DATE"][0]}
        e2s = "gated (parity gate, no E2 contrast)" if c["E2"] is None else f"{c['E2'][0]:+.1f} [{c['E2'][1]:+.1f}, {c['E2'][2]:+.1f}]{' BEYOND' if bE2 else ''}"
        print(f"  {tag} minus I1: E2 {e2s} | "
              f"DATE {c['DATE'][0]:+.1f} (t {c['DATE'][1]:+.2f}){' BEYOND' if bD else ''} | BASE {c['BASE'][0]:+.1f} [{c['BASE'][1]:+.1f}, {c['BASE'][2]:+.1f}]{' BEYOND' if bB else ''}")
    print("\nreadings (frozen, addendum I):")
    quant = [t for t in ("I2", "I4", "I5", "I6") if t in beyond]
    if quant and not any(any(beyond[t][x] for x in ("E2", "DATE", "BASE")) for t in quant):
        print("  ROBUST: no quantized tier moves any channel beyond the same-box noise floor on this checkpoint")
    d4 = {t: beyond[t]["DATE"] or beyond[t]["E2"] for t in ("I2", "I4") if t in beyond}
    d8 = {t: beyond[t]["DATE"] or beyond[t]["E2"] for t in ("I5", "I6") if t in beyond}
    if len(d4) == 2:
        if d4["I2"] and not d4["I4"]: print("  AWQ-SPECIFIC: AWQ moves the date route beyond the floor, GPTQ at the same bits/group does not")
        elif d4["I2"] and d4["I4"]: print("  4-BIT: both 4-bit methods move the date route beyond the floor" + (" and no 8-bit tier does" if len(d8) == 2 and not any(d8.values()) else ""))
        elif d4["I4"] and not d4["I2"]: print("  GPTQ-SPECIFIC: GPTQ moves the date route beyond the floor, AWQ does not")
    if len(d4) == 2 and len(d8) == 2 and (any(d4.values())):
        m4 = np.mean([abs(beyond[t]["dDATE"]) for t in ("I2", "I4")]); m8 = np.mean([abs(beyond[t]["dDATE"]) for t in ("I5", "I6")])
        print(f"  dose ordering on DATE: |d| 4-bit {m4:.1f} vs 8-bit {m8:.1f} pp -> " + ("DOSE-RESPONSE (more precision loss, larger shift)" if m4 > m8 else "not ordered by bits"))
    for t in quant:
        if beyond[t]["BASE"]: print(f"  {t}: BASELINE SHIFT beyond the floor (level change, reported separately from the date route)")
    if "I7" in beyond:
        print("  I7 dtype control: " + ("activation dtype alone moves the measurement beyond the floor -> fp16-served AWQ rows elsewhere are dtype-confounded"
                                        if any(beyond["I7"][x] for x in ("E2", "DATE", "BASE")) else "activation dtype alone does not move the measurement beyond the floor"))


if __name__ == "__main__":
    main()
