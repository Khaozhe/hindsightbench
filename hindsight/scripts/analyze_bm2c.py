#!/usr/bin/env python
"""BM-2c ladder summary: one line per rung from the frozen row JSONs, plus the
preregistered readings (BM2c_prereg_olmo_ladder.md afa19e6d; base-contrast
readings per BM2c_addendum_base_guided.md 17f9c668).

  python analyze_bm2c.py            # table + readings for whatever rungs have rows
  python analyze_bm2c.py --json out.json

Rows are produced by analyze_bench_row.py (unchanged); this script only reads
<key>_row.json files and applies the frozen decision rules. Missing rungs print
as "(no row yet)" and never block the readings that do not need them.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hindsight_paths import REPO

BENCH = REPO / "hindsight/outputs/bench"

# rung -> (row key, stage label, regime)
LADDER_A = [
    ("A0", "olmo3-7b-base-guided", "base (pretrain+midtrain+longctx)", "guided"),
    ("A1", "olmo3-7b-sft", "+SFT", "chat"),
    ("A2", "olmo3-7b-dpo", "+DPO", "chat"),
    ("A3", "olmo3-7b-instruct", "+RLVR (released Instruct)", "chat"),
    ("A3x", "olmo3-7b-instruct-guided", "released Instruct, guided regime", "guided"),
    ("A4", "olmo3-7b-think", "Think flow endpoint", "chat"),
]
LADDER_B = [
    ("B0", "olmo3-32b-base-guided", "32B base", "guided"),
    ("B1", "olmo3.1-32b-sft", "32B +SFT", "chat"),
    ("B2", "olmo3.1-32b-dpo", "32B +DPO", "chat"),
    ("B3", "olmo3.1-32b-instruct", "32B released Instruct", "chat"),
    ("B3x", "olmo3.1-32b-instruct-guided", "32B released Instruct, guided regime", "guided"),
]
CONTROL_C = [
    ("C", "llama-3.3-70b-awq", "Llama 3.3 70B (2023-12 corpus, 2024-12 recipe)", "chat"),
    ("C-ref", "llama-3.1-70b-awq", "Llama 3.1 70B (benchmark row, paired null)", "chat"),
]
CONTROL_D = [
    ("D1", "qwen3-30b-a3b-instruct-2507-fp8dyn", "Qwen3-30B-A3B-Instruct-2507 (non-thinking)", "chat"),
    ("D2", "qwen3-30b-a3b-thinking-2507-fp8dyn", "Qwen3-30B-A3B-Thinking-2507 (thinking)", "chat"),
    ("D-ref", "qwen3-30b-a3b-fp8dyn", "Qwen3-30B-A3B (benchmark row 15, paired null)", "chat"),
]
CONTROL_E = [
    ("E1", "llama-3.1-nemotron-70b-awq", "Nemotron-70B: Llama 3.1 70B Instruct + one RLHF stage", "chat"),
]
# Addendum F (BM2c_addendum_F_llama_recipe_panel.md): Tulu-3 stage ladder T1-T3 and recipe panel F1-F3
# on the Llama 3.1 70B base. One memory clause set for every row: post-LAP <= .1 and hit > 65.5% on >= 100 probes.
PANEL_F = [
    ("T1", "tulu3-70b-sft-fp8dyn", "Tulu 3 70B SFT (Ai2, on Llama 3.1 70B base; FP8 W8A16, TP=4 on A100)", "chat"),
    ("T2", "tulu3-70b-dpo-fp8dyn", "Tulu 3 70B DPO", "chat"),
    ("T3", "tulu3-70b-rlvr-fp8dyn", "Tulu 3 70B (RLVR, released)", "chat"),
    ("F1", "r1-distill-llama-70b-awq", "R1-Distill-Llama-70B (reasoning SFT on Llama 3.3 Instruct; AWQ)", "chat"),
    ("F2", "hermes3-70b-fp8", "Hermes 3 70B (Nous SFT+DPO on the base; official FP8 W8A16, TP=4 on A100)", "chat"),
    ("F3", "tulu3-70b-rlvr-awq", "Tulu 3 70B in the AWQ tier (cross-tier check of T3)", "chat"),
]

# Addendum H (BM2c_addendum_H_tier.md, 7ce2f785): control C re-measured in the FP8 tier (W8A16, TP=4, A100)
CONTROL_H = [
    ("H1", "llama-3.3-70b-fp8dyn", "Llama 3.3 70B Instruct, FP8 W8A16 tier (control C in another tier)", "chat"),
    ("H2", "llama-3.1-70b-fp8dyn", "Llama 3.1 70B Instruct, FP8 W8A16 tier (C-ref in another tier)", "chat"),
]
# addendum I (precision dose-response, frozen d62eb2e0): one checkpoint, seven serving configurations on the
# same A100 box; the frozen readings are computed by analyze_dose_response.py, this list only feeds the table
CONTROL_I = [
    ("I1", "qwen3-30b-a3b-thinking-2507-bf16", "Qwen3-30B-A3B-Thinking-2507, BF16 (reference)", "chat"),
    ("I3", "qwen3-30b-a3b-thinking-2507-bf16-r2", "same, BF16 second run (noise floor)", "chat"),
    ("I7", "qwen3-30b-a3b-thinking-2507-bf16-fp16act", "same, BF16 weights with fp16 activations", "chat"),
    ("I6", "qwen3-30b-a3b-thinking-2507-fp8block", "same, official FP8 block-128", "chat"),
    ("I5", "qwen3-30b-a3b-thinking-2507-int8-w8a8", "same, INT8 w8a8 (RedHatAI)", "chat"),
    ("I4", "qwen3-30b-a3b-thinking-2507-gptq-w4a16", "same, INT4 w4a16 GPTQ (RedHatAI)", "chat"),
    ("I2", "qwen3-30b-a3b-thinking-2507-awq", "same, INT4 AWQ (QuantTrio)", "chat"),
]
NOISE_FLOOR_PP = 16.2   # largest same-model replicate-pair E2 difference observed (addendum H)


def load_row(key: str) -> dict | None:
    f = BENCH / key / f"{key}_row.json"
    return json.loads(f.read_text()) if f.exists() else None


def ci_excludes_zero(m: dict) -> bool | None:
    if m is None or m.get("gated"):
        return None
    lo, hi = m["ci95"]
    if lo != lo or hi != hi:  # NaN
        return None
    return lo > 0 or hi < 0


def fmt(m: dict | None) -> str:
    if m is None:
        return "—"
    if m.get("gated"):
        return f"gated({m.get('gate_reason')})"
    lo, hi = m["ci95"]
    star = "*" if ci_excludes_zero(m) else " "
    return f"{m['est']*100:+5.1f} [{lo*100:+5.1f},{hi*100:+5.1f}]{star}"


def trigger(row: dict | None) -> bool | None:
    """Preregistered trigger status: E2 95% CI excludes zero (positive)."""
    if row is None:
        return None
    m = row["E2_date_trigger"]
    x = ci_excludes_zero(m)
    if x is None:
        return None
    return bool(x and m["est"] > 0)


def table(ladder, out_lines):
    out_lines.append(f"{'rung':5s} {'key':30s} {'E2 (pp)':26s} {'E3 (pp)':26s} {'VALID':6s} {'LAP pre/post (hit)':20s} {'cutoff':8s} {'trigger'}")
    for rung, key, label, regime in ladder:
        r = load_row(key)
        if r is None:
            out_lines.append(f"{rung:5s} {key:30s} (no row yet)   — {label}")
            continue
        lap = r["LAP"]
        hit = lap.get("recall_hit_rate")
        lap_s = f"{(lap.get('pre_mean') or 0):.2f}/{(lap.get('post_mean') or 0):.2f} ({hit*100:.0f}%)" if hit is not None else "—"
        t = trigger(r)
        # cutoff is defined only where recall beats the panel's 65.5% positive-day base rate
        # (paper 1 §8.3 / E.12); the flag itself lives in bench_registry.py, so this is a display
        # rule for the ladder summary, not the frozen gate
        cutoff = lap.get("empirical_cutoff") if (hit is not None and hit > 0.655) else "n/a"
        out_lines.append(
            f"{rung:5s} {key:30s} {fmt(r['E2_date_trigger']):26s} {fmt(r['E3_transplant']):26s} "
            f"{r['VALID']['sketch_rate']*100:5.0f}% {lap_s:20s} {str(cutoff):8s} "
            f"{'YES' if t else ('NEG*' if (t is False and ci_excludes_zero(r['E2_date_trigger'])) else ('no' if t is False else 'n/a'))}   {label}")


def readings(out_lines):
    A = {rung: load_row(key) for rung, key, _, _ in LADDER_A}
    tA = {k: trigger(v) for k, v in A.items()}
    out_lines.append("\nPreregistered readings — ladder A")
    # base contrast (addendum): A0-guided vs A3-guided
    a0, a3x, a3 = tA["A0"], tA["A3x"], tA["A3"]
    if a0 is None or a3x is None:
        out_lines.append("  base contrast: pending (needs A0 and A3x rows)")
    elif a0 and a3x:
        out_lines.append("  (i)  A0-guided AND A3-guided trigger -> CORPUS-BORNE; post-training not required")
    elif (not a0) and a3x:
        out_lines.append("  (ii) A3-guided triggers, A0-guided null -> INSTALLED BY POST-TRAINING (stage from chat ladder below)")
    elif (not a3x) and a3:
        out_lines.append("  (iii) A3-guided null although A3-chat triggers -> guided regime suppresses the trigger; base contrast NOT IDENTIFIED")
    else:
        out_lines.append("  neither A3-guided nor A3-chat triggers -> see reading (v) below")
    # chat ladder A1..A3: installation stage
    chat = [("A1", "SFT"), ("A2", "preference tuning (DPO)"), ("A3", "RLVR")]
    known = [(r, s, tA[r]) for r, s in chat if tA[r] is not None]
    if len(known) < 3:
        out_lines.append(f"  chat ladder: pending ({len(known)}/3 rows)")
    else:
        flags = [t for _, _, t in known]
        if not any(flags):
            out_lines.append("  (v)  no chat rung triggers -> Olmo 3 joins the no-trigger set despite a 2024-12 corpus cutoff (contradicts a pure corpus-period account)")
        else:
            first = next(i for i, t in enumerate(flags) if t)
            if all(flags[first:]):
                out_lines.append(f"  installation stage (lowest triggering rung with non-triggering predecessor): {known[first][0]} = {known[first][1]}"
                                 + ("" if first > 0 else "  [A1 is the lowest chat rung; base status comes from the guided contrast]"))
            else:
                out_lines.append("  (iv) non-monotone ladder -> reported as measured; no stage named")
    a4 = tA["A4"]
    if a4 is not None:
        out_lines.append(f"  A4 Think vs A3 (reasoning-regime datum, not part of the ordering): Think {'triggers' if a4 else 'null'}, Instruct {'triggers' if a3 else 'null'}")
    # ladder B: the prereg calls it a replication of A at scale, so the same readings apply
    Bm = {rung: load_row(key) for rung, key, _, _ in LADDER_B}
    tB = {k: trigger(v) for k, v in Bm.items()}
    neg = {k: bool(v is not None and not v.get("E2_date_trigger", {}).get("gated") and ci_excludes_zero(v["E2_date_trigger"]) and v["E2_date_trigger"]["est"] < 0) for k, v in Bm.items()}
    out_lines.append("\nPreregistered readings — ladder B (replication at 32B)")
    b0, b3x, b3 = tB["B0"], tB["B3x"], tB["B3"]
    if b0 is None or b3x is None:
        out_lines.append("  base contrast: pending (needs B0 and B3x rows)")
    elif b0 and b3x:
        out_lines.append("  (i)  B0-guided AND B3-guided trigger -> CORPUS-BORNE")
    elif (not b0) and b3x:
        out_lines.append("  (ii) B3-guided triggers, B0-guided null -> INSTALLED BY POST-TRAINING")
    elif (not b3x) and b3:
        out_lines.append("  (iii) B3-guided null although B3-chat triggers -> guided regime suppresses; base contrast NOT IDENTIFIED")
    else:
        out_lines.append("  neither B3-guided nor B3-chat triggers (positive) -> no positive trigger at 32B"
                         + ("; B3-chat E2 is significantly NEGATIVE (chat regime only; B3x-guided null) — reported as measured" if neg["B3"] else ""))
    chatB = [(r, s_) for r, s_ in (("B1", "SFT"), ("B2", "preference tuning (DPO)"), ("B3", "RLVR")) if tB[r] is not None]
    if len(chatB) < 3:
        out_lines.append(f"  chat ladder: pending ({len(chatB)}/3 rows)")
    else:
        flags = [tB[r] for r, _ in chatB]
        if not any(flags):
            out_lines.append("  (v)  no chat rung triggers (positive) -> Olmo 3(.1) 32B joins the no-trigger set despite a 2024-12 corpus cutoff"
                             + ("; the SFT -> DPO -> RLVR sequence is non-monotone in sign (DPO borderline positive, RLVR significantly negative) -> (iv) reported as measured, no stage named" if neg["B3"] else ""))
        else:
            out_lines.append("  chat ladder: at least one positive trigger — see table")
    out_lines.append("  memory precondition: every Olmo rung's recall hit rate is at or below the 65.5% base rate, so neither ladder can localise an installation stage (no-memory baseline; see addenda D/E)")
    # control C
    c, cref = load_row("llama-3.3-70b-awq"), load_row("llama-3.1-70b-awq")
    out_lines.append("\nControl C — same corpus, new recipe")
    if c is None:
        out_lines.append("  pending (no llama-3.3-70b-awq row)")
    else:
        tc = trigger(c)
        out_lines.append(f"  Llama 3.3 70B E2 {fmt(c['E2_date_trigger'])} vs Llama 3.1 70B E2 {fmt(cref['E2_date_trigger']) if cref else '—'}")
        out_lines.append("  -> " + ("RECIPE INSTALLS THE REFLEX on a fixed 2023-12 corpus" if tc else
                                    ("consistent with corpus period; not decisive (one lineage)" if tc is False else "not identified")))
    # control D (addendum D): identification condition = cutoff in [2024-03, 2024-05] and hit > 65.5%
    d1, d2, dref = load_row("qwen3-30b-a3b-instruct-2507-fp8dyn"), load_row("qwen3-30b-a3b-thinking-2507-fp8dyn"), load_row("qwen3-30b-a3b-fp8dyn")
    out_lines.append("\nControl D — Qwen3-30B-A3B -> 2507 recipe (addendum D; fixed corpus is tested by the cutoff)")
    if d1 is None and d2 is None:
        out_lines.append("  pending (no 2507 rows)")
    for tag, r in (("D1 Instruct-2507", d1), ("D2 Thinking-2507", d2)):
        if r is None:
            continue
        lap = r["LAP"]; hit = lap.get("recall_hit_rate") or 0; cut = str(lap.get("empirical_cutoff")); n = lap.get("recall_n") or 0
        cut_ok = "2024-03" <= cut <= "2024-05"; hit_ok = hit > 0.655
        pre_m, post_m = lap.get("pre_mean"), lap.get("post_mean")  # post_mean can be exactly 0.0, so no `or` defaults here
        collapse = pre_m is not None and post_m is not None and pre_m >= 0.5 and post_m <= 0.1  # addendum-E memory criterion, shown for disclosure only
        ident = hit_ok and cut_ok
        clauses = f"cutoff {cut} ({'in' if cut_ok else 'outside'} [2024-03, 2024-05]); hit {hit*100:.2f}% = {round(hit*n)}/{n} ({'>' if hit_ok else '<='} 65.5%)"
        t = trigger(r)
        verdict = ("IDENTIFIED as fixed-corpus -> " + ("RECIPE INSTALLS THE REFLEX (second lineage)" if t else ("recipe does not install on this lineage" if t is False else "E2 unidentified"))) if ident else \
                  ("NOT IDENTIFIED under the frozen clause(s): " + ", ".join(c for c, ok in (("hit rate", hit_ok), ("cutoff", cut_ok)) if not ok) + " -> no recipe reading (frozen)")
        out_lines.append(f"  {tag}: E2 {fmt(r['E2_date_trigger'])} | {clauses} -> {verdict}")
        if not ident and cut_ok and collapse:
            out_lines.append(f"      disclosure: LAP collapses {lap['pre_mean']:.3f} -> {lap['post_mean']:.3f} at {cut}; under the addendum-E collapse criterion this row would be identified"
                             + (" and E2 excludes zero" if t else "") + " — reported as a post-freeze alternative reading, not the headline")
    if dref is not None:
        out_lines.append(f"  row 15 comparator: E2 {fmt(dref['E2_date_trigger'])} cutoff {dref['LAP'].get('empirical_cutoff')} hit {dref['LAP'].get('recall_hit_rate')*100:.0f}%")
    # control E (addendum E): identification = LAP collapse at the base cutoff (pre >= .5, post <= .1, cutoff in [2023-11, 2024-01])
    e1 = load_row("llama-3.1-nemotron-70b-awq")
    out_lines.append("\nControl E — one RLHF stage on Llama 3.1 70B Instruct (addendum E)")
    if e1 is None:
        out_lines.append("  pending (no Nemotron row)")
    else:
        lap = e1["LAP"]; pre, post, cut = lap.get("pre_mean") or 0, lap.get("post_mean") or 0, str(lap.get("empirical_cutoff"))
        hit, n = lap.get("recall_hit_rate") or 0, lap.get("recall_n") or 0
        pre_ok, post_ok, cut_ok = pre >= 0.5, post <= 0.1, "2023-11" <= cut <= "2024-01"
        ident = pre_ok and post_ok and cut_ok
        t = trigger(e1)
        clauses = f"LAP pre {pre:.3f} ({'>=' if pre_ok else '<'} .5), post {post:.3f} ({'<=' if post_ok else '>'} .1), cutoff {cut} ({'in' if cut_ok else 'outside'} [2023-11, 2024-01]); hit {hit*100:.1f}% = {round(hit*n)}/{n}"
        verdict = ("IDENTIFIED -> " + ("ONE RLHF PREFERENCE STAGE INSTALLS THE REFLEX (stage localised)" if t else ("this preference stage does not install it (recipe-specific, stage not localised)" if t is False else "E2 unidentified"))) if ident else \
                  ("NOT IDENTIFIED under the frozen clause(s): " + ", ".join(c for c, ok in (("pre-cutoff LAP", pre_ok), ("post-cutoff LAP", post_ok), ("cutoff", cut_ok)) if not ok) + " -> no stage reading (frozen)")
        out_lines.append(f"  E1 Nemotron-70B: E2 {fmt(e1['E2_date_trigger'])} | {clauses} -> {verdict}")
        if not ident and post_ok and hit > 0.655:
            out_lines.append(f"      disclosure: the model abstains on {(1-pre)*100:.0f}% of pre-cutoff probes (pre-LAP {pre:.2f}) but answers at {hit*100:.1f}% accuracy (> 65.5% base rate) and collapses to {post:.2f} post-cutoff; under the leaderboard's own chance rule (hit rate) memory is present"
                             + (" and E2 excludes zero" if t else "") + f" — the low-willingness model also drags the 0.1-threshold locator to {cut}; reported as a post-freeze alternative reading, not the headline")
        out_lines.append("  start point Llama 3.1 70B E2 -4.7 [-12.0, +3.0]; recipe comparator Llama 3.3 70B E2 +16.0 [+1.9, +31.2]")
    # addendum F: one clause set for every row (post-LAP <= .1, hit > 65.5% on >= 100 probes); Tulu ladder + recipe panel
    out_lines.append("\nAddendum F — Tulu-3 stage ladder and recipe panel on the Llama 3.1 70B base")
    rows_f = {tag: load_row(key) for tag, key, _, _ in PANEL_F}
    if all(r is None for r in rows_f.values()):
        out_lines.append("  pending (no addendum-F row)")
    else:
        def f_ident(r):
            lap = r["LAP"]; post = lap.get("post_mean"); hit = lap.get("recall_hit_rate"); n = lap.get("recall_n") or 0
            post_ok = post is not None and post <= 0.1; hit_ok = hit is not None and hit > 0.655 and n >= 100
            return post_ok and hit_ok, f"post-LAP {post if post is None else f'{post:.3f}'} ({'<=' if post_ok else '>'} .1), hit {(hit or 0)*100:.1f}% = {round((hit or 0)*n)}/{n} ({'>' if hit_ok else 'not >'} 65.5% on >=100)"
        status = {}
        for tag, key, label, _ in PANEL_F:
            r = rows_f[tag]
            if r is None:
                out_lines.append(f"  {tag} {label}: pending"); status[tag] = None; continue
            ident, clauses = f_ident(r); t = trigger(r); status[tag] = (ident, t)
            out_lines.append(f"  {tag} {label}: E2 {fmt(r['E2_date_trigger'])} | {clauses} -> " + ("identified; " + ("TRIGGERS" if t else ("no trigger" if t is False else "E2 unidentified")) if ident else "NOT IDENTIFIED (frozen clause set) -> reported as measured, no reading"))
        tl = [status.get(t) for t in ("T1", "T2", "T3")]
        if all(x is not None for x in tl):
            if not all(x[0] for x in tl):
                out_lines.append("  Tulu ladder: at least one stage fails the memory condition -> no stage reading (frozen)")
            else:
                trig = [x[1] for x in tl]
                if not any(trig):
                    out_lines.append("  Tulu ladder: no stage triggers -> the Ai2 recipe does not install the reflex on a memory-bearing base; installation recipe-specific, stage not localised")
                else:
                    first = next(i for i, v in enumerate(trig) if v)
                    mono = all(trig[first:]) and not any(trig[:first])
                    out_lines.append(f"  Tulu ladder: lowest triggering rung T{first+1}" + (" with every later rung triggering -> INSTALLATION STAGE LOCALISED within the Ai2 recipe" if mono else "; non-monotone -> reported as measured, no stage named"))
        else:
            out_lines.append("  Tulu ladder: incomplete")
        installed = [tag for tag in ("T3", "F2") if status.get(tag) and status[tag][0] and status[tag][1]]
        measured = [tag for tag in ("T3", "F2") if status.get(tag) and status[tag][0]]
        out_lines.append(f"  panel count (this addendum's identified endpoints): {len(installed)}/{len(measured)} recipes trigger ({', '.join(installed) or 'none'}); frozen rows on the same base: Meta 3.1 Instruct null, Nemotron +9.8*, Meta 3.3 +16.0*")
        if status.get("F1"):
            ident, t = status["F1"]; r = rows_f["F1"]; m = r["E2_date_trigger"]
            if ident and not m.get("gated"):
                lo, hi = (100 * x for x in m["ci95"])   # row JSON stores fractions; the frozen comparator is +16.0 pp
                read = "amplified (CI above +16.0)" if lo > 16.0 else ("removed (null)" if t is False else "retained (CI overlaps +16.0)")
                out_lines.append(f"  F1 vs its start point Llama 3.3 (+16.0): {read}")
        # addendum G (c7e04919): the same readings with the whole-panel trigger G2, side by side with E2
        try:
            from analyze_wholepanel import g2 as _g2, WINDOW_END as _WE, T_CRIT as _TC, MIN_DATES as _MD
            from analyze_fm1 import all_dates as _ad, build_covariates as _bc
            _cov = _bc([d for d in _ad() if d <= _WE])
            out_lines.append("  addendum G (G2 = USREC coefficient on D-M, HAC 6; prospective for T1-T3, F2, F3):")
            gstat = {}
            for tag, key, _, _ in PANEL_F:
                if rows_f[tag] is None:
                    continue
                g = _g2(key, _cov); ident = status[tag][0]
                gt = None if g["n_dates"] < _MD else (g["t"] >= _TC)
                gstat[tag] = (ident, gt)
                e2t = status[tag][1]
                agree = "" if e2t is None or gt is None else ("  [agrees with E2]" if bool(e2t) == bool(gt) else "  [DISAGREES with E2 -> reported as the finding]")
                out_lines.append(f"    {tag}: G2 {g['coef']*100:+.1f} [{g['ci95'][0]*100:+.1f}, {g['ci95'][1]*100:+.1f}] t={g['t']:+.2f} -> {g['reading']} ({g['status']}){agree}")
            tg = [gstat.get(t) for t in ("T1", "T2", "T3")]
            if all(x is not None for x in tg) and all(x[0] for x in tg):
                trig = [bool(x[1]) for x in tg]
                if not any(trig):
                    out_lines.append("    Tulu ladder under G2: no stage triggers")
                else:
                    first = trig.index(True); mono = all(trig[first:])
                    out_lines.append(f"    Tulu ladder under G2: lowest triggering rung T{first+1}" + (" with every later rung triggering -> STAGE LOCALISED (G2)" if mono else "; non-monotone -> no stage named (G2)"))
        except Exception as exc:  # the E2 readings above never depend on this block
            out_lines.append(f"  addendum G block failed: {exc!r}")
        if status.get("F3") and status.get("T3") and rows_f["F3"] and rows_f["T3"]:
            out_lines.append(f"  cross-tier check on T3: FP8 dyn {fmt(rows_f['T3']['E2_date_trigger'])} vs AWQ {fmt(rows_f['F3']['E2_date_trigger'])} (disclosed, never corrected)")


def readings_h(out_lines: list[str]) -> None:
    """addendum H readings: control C in the FP8 tier, E2 and G2 side by side, plus per-checkpoint tier contrasts."""
    out_lines.append("\nAddendum H — control C re-measured in the FP8 tier")
    h1, h2 = load_row("llama-3.3-70b-fp8dyn"), load_row("llama-3.1-70b-fp8dyn")
    if h1 is None and h2 is None:
        out_lines.append("  H1/H2 pending (no addendum-H row); tier contrasts available so far:")
    import numpy as np, json as _json
    import statsmodels.api as sm
    from analyze_wholepanel import g2 as _g2, bearish_share as _bs, WINDOW_END as _WE, T_CRIT as _TC, MIN_DATES as _MD
    from analyze_fm1 import all_dates as _ad, build_covariates as _bc, CRISIS as _CR, CALM_YEARS as _CY, gap as _gap
    cov = _bc([d for d in _ad() if d <= _WE])
    def ident(r):
        lap = r["LAP"]; post = lap.get("post_mean"); hit = lap.get("recall_hit_rate"); n = lap.get("recall_n") or 0
        return post is not None and post <= 0.1 and hit is not None and hit > 0.655 and n >= 100, f"post-LAP {post}, hit {(hit or 0)*100:.1f}% on {n}"
    st = {}
    for tag, key, label, _ in CONTROL_H:
        r = load_row(key)
        if r is None:
            out_lines.append(f"  {tag}: pending"); continue
        ok, cl = ident(r); e2t = trigger(r); g = _g2(key, cov); g2t = None if g["n_dates"] < _MD else g["t"] >= _TC
        st[tag] = (ok, e2t, g2t)
        out_lines.append(f"  {tag} {label}: E2 {fmt(r['E2_date_trigger'])} (trigger {e2t}) | G2 {g['coef']*100:+.1f} t={g['t']:+.2f} (trigger {g2t}) | {cl} -> {'identified' if ok else 'NOT IDENTIFIED (reported as measured)'}")
    if "H1" in st and "H2" in st:
        for name, idx in (("E2", 1), ("G2", 2)):
            if not (st["H1"][0] and st["H2"][0]):
                out_lines.append(f"  control C in FP8 tier ({name}): a row fails the memory clause -> no reading (frozen)"); break
            a, b = bool(st["H1"][idx]), bool(st["H2"][idx])
            read = "CONTROL C SURVIVES THE TIER CHANGE" if a and not b else ("CONTROL C IS TIER-DEPENDENT (Llama 3.3 trigger not reproduced in FP8)" if not a else "both trigger: recipe contrast not reproduced in this tier")
            out_lines.append(f"  control C in FP8 tier ({name}): {read}")
    # tier contrasts, AWQ minus FP8, same checkpoint
    dates = _ad(); crisis = [d for d in dates if d in _CR]; calm = [d for d in dates if d[:4] in _CY]
    def arms(k):
        o = {}
        for arm in "DM":
            bd = {}
            for n in (BENCH / k / arm).glob("rep*/*"):
                f = n / "01_sketches_valid.json"
                if f.exists():
                    bd.setdefault(n.name, []).extend(s["direction"] for s in _json.loads(f.read_text()) if s.get("direction") in ("+", "-"))
            o[arm] = bd
        return o
    e2f = lambda A, c, q: _gap(A["D"], c, q) - _gap(A["M"], c, q)
    for lab, ka, kb in (("Llama 3.3", "llama-3.3-70b-awq", "llama-3.3-70b-fp8dyn"), ("Llama 3.1", "llama-3.1-70b-awq", "llama-3.1-70b-fp8dyn"),
                        ("Tulu 3 RLVR", "tulu3-70b-rlvr-awq", "tulu3-70b-rlvr-fp8dyn")):
        if load_row(ka) is None or load_row(kb) is None:
            continue
        A, B = arms(ka), arms(kb); rng = np.random.default_rng(2026); c, q = np.array(crisis), np.array(calm); out = []
        for _ in range(10_000):
            cs, qs = list(rng.choice(c, len(c))), list(rng.choice(q, len(q))); out.append(e2f(A, cs, qs) - e2f(B, cs, qs))
        d = (e2f(A, crisis, calm) - e2f(B, crisis, calm)) * 100; lo, hi = np.percentile(out, 2.5) * 100, np.percentile(out, 97.5) * 100
        Da, Ma, Db, Mb = _bs(ka, "D"), _bs(ka, "M"), _bs(kb, "D"), _bs(kb, "M")
        df = cov.copy(); df["y"] = [(Da.get(x, np.nan) - Ma.get(x, np.nan)) - (Db.get(x, np.nan) - Mb.get(x, np.nan)) for x in df.index]; df = df.dropna(subset=["y", "usrec"])
        t = sm.OLS(df["y"].values, sm.add_constant(df[["usrec"]].values)).fit(cov_type="HAC", cov_kwds={"maxlags": 6}).tvalues[1]
        beyond = (lo > 0 or hi < 0) and abs(d) > NOISE_FLOOR_PP
        out_lines.append(f"  tier contrast {lab} (AWQ minus FP8): E2 {d:+.1f} [{lo:+.1f}, {hi:+.1f}], G2-diff t={t:+.2f} -> " + ("BEYOND the observed noise floor" if beyond else "within the observed noise floor"))
    out_lines.append("  disclosed: the Llama AWQ rows ran on the H800, the FP8 rows on the A100 (tier and hardware confounded); the Tulu pair is same-box")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    lines: list[str] = ["BM-2c ladder (E2/E3 in pp, 95% date-level bootstrap; * = CI excludes zero; trigger NEG* = E2 significantly NEGATIVE, not a trigger under the frozen definition)\n"]
    table(LADDER_A, lines)
    lines.append("")
    table(LADDER_B, lines)
    lines.append("")
    table(CONTROL_C, lines)
    lines.append("")
    table(CONTROL_D, lines)
    lines.append("")
    table(CONTROL_E, lines)
    lines.append("")
    table(PANEL_F, lines)
    lines.append("")
    table(CONTROL_H, lines)
    readings(lines)
    readings_h(lines)
    print("\n".join(lines))
    if args.json:
        args.json.write_text(json.dumps({key: load_row(key) for _, key, _, _ in LADDER_A + LADDER_B + CONTROL_C + CONTROL_D + CONTROL_E + PANEL_F + CONTROL_H}, indent=2))


if __name__ == "__main__":
    main()
