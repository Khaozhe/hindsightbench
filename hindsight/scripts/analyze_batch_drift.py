#!/usr/bin/env python
"""POST-FREEZE EXPLORATORY (2026-07-25, design-review response).

Establishes the provenance of the 31.8 -> 28.1 -> 21.3pp "R-arm gap drift"
disclosed in sections/07_exp4_pipeline.tex:7, and tests the accompanying
defense "both arms regenerate together, so within-stage contrasts are
unaffected".

Reads only frozen artifacts; writes only to hindsight/outputs/review/.

Gap definition is copied verbatim from the frozen analyzers
(scripts/analyze_fm1.py::gap, scripts/analyze_fm2.py::gap_from_jsonl):
    Gap = bearish_share(CRISIS dates) - bearish_share(CALM dates)
pooled over sketches, CRISIS = 11 listed dates, CALM = all dates in
{2013,2014,2017}.

Outputs:
  hindsight/outputs/review/batch_drift.json
  hindsight/outputs/review/batch_drift.md
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np

from hindsight_paths import REPO

V1_PANEL = REPO / "macrochain/data/processed/sketches_panel.jsonl"
V1_NODES = REPO / "macrochain/data/processed/sketch_panel_nodes"
V1_BATCH_REQ = REPO / "macrochain/data/processed/sketch_batch_requests.jsonl"
FM1_FLASH = REPO / "hindsight/outputs/fm1/gemini-2.5-flash"
FM1_PRO = REPO / "hindsight/outputs/fm1/gemini-2.5-pro"
FM2 = REPO / "hindsight/outputs/fm2"
KT1_NODES = REPO / "hindsight/outputs/kt1/masked_nodes"
OUT_JSON = REPO / "hindsight/outputs/review/batch_drift.json"
OUT_MD = REPO / "hindsight/outputs/review/batch_drift.md"

# verbatim from analyze_fm1.py / analyze_fm2.py
CRISIS = [
    "2008-09-15", "2008-10-15", "2008-11-15", "2008-12-15", "2009-01-15",
    "2009-02-15", "2020-03-15", "2020-04-15", "2022-06-15", "2022-09-15",
    "2022-10-15",
]
CALM_YEARS = {"2013", "2014", "2017"}
B = 10_000
SEED = 2026


# ---------------------------------------------------------------- loaders
def dirs_from_nodes(root: Path) -> dict[str, list[str]]:
    """date -> [directions], from a tree of <date>/01_sketches_valid.json."""
    by_date: dict[str, list[str]] = defaultdict(list)
    if not root.exists():
        return by_date
    for node in sorted(root.iterdir()):
        f = node / "01_sketches_valid.json"
        if not f.exists():
            continue
        for s in json.loads(f.read_text()):
            if s.get("direction") in ("+", "-"):
                by_date[node.name].append(s["direction"])
    return by_date


def dirs_from_jsonl(path: Path) -> dict[str, list[str]]:
    by_date: dict[str, list[str]] = defaultdict(list)
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("direction") in ("+", "-"):
            by_date[d["decision_date"]].append(d["direction"])
    return by_date


def pool(*maps: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for m in maps:
        for k, v in m.items():
            out[k].extend(v)
    return out


# ---------------------------------------------------------------- metrics
def shares(by_date, dates):
    b = t = 0
    for d in dates:
        xs = by_date.get(d, [])
        b += sum(1 for x in xs if x == "-")
        t += len(xs)
    return b, t


def gap(by_date, crisis, calm) -> float:
    cb, ct = shares(by_date, crisis)
    qb, qt = shares(by_date, calm)
    return cb / ct - qb / qt if ct and qt else float("nan")


def gap_detail(by_date, crisis, calm) -> dict:
    cb, ct = shares(by_date, crisis)
    qb, qt = shares(by_date, calm)
    return {
        "gap": (cb / ct - qb / qt) if ct and qt else None,
        "crisis_bearish_share": cb / ct if ct else None,
        "calm_bearish_share": qb / qt if qt else None,
        "n_crisis_sketches": ct, "n_calm_sketches": qt,
        "n_dates_covered": len(by_date),
        "n_sketches_total": sum(len(v) for v in by_date.values()),
    }


def boot_ci(fn, crisis, calm, rng, B=B):
    """Date-level paired bootstrap, same resampling scheme as analyze_fm1.boot_diff."""
    ca, qa = np.array(crisis), np.array(calm)
    out = np.empty(B)
    for i in range(B):
        cs = list(rng.choice(ca, len(ca), replace=True))
        qs = list(rng.choice(qa, len(qa), replace=True))
        out[i] = fn(cs, qs)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


# ---------------------------------------------------------------- meta scans
def scan_metas(root: Path) -> dict:
    """Collect model strings + generated_at over a node tree."""
    models, versions, arms, stamps = set(), set(), set(), []
    n = 0
    if not root.exists():
        return {}
    for node in sorted(root.iterdir()):
        f = node / "03_run_meta.json"
        if not f.exists():
            continue
        m = json.loads(f.read_text())
        n += 1
        models.add(m.get("model"))
        versions.add(m.get("model_version_reported"))
        arms.add(m.get("arm"))
        if m.get("generated_at"):
            stamps.append(m["generated_at"])
    stamps.sort()
    return {
        "n_nodes": n,
        "model_strings": sorted(x for x in models if x is not None),
        "model_version_reported": sorted(str(x) for x in versions),
        "arm_labels": sorted(str(x) for x in arms),
        "generated_at_min": stamps[0] if stamps else None,
        "generated_at_max": stamps[-1] if stamps else None,
        "generated_at_recorded": bool(stamps),
    }


def mtime_range(root: Path, pattern: str) -> dict:
    fs = list(root.glob(pattern))
    if not fs:
        return {}
    ts = sorted(os.path.getmtime(f) for f in fs)
    return {
        "n_files": len(fs),
        "mtime_min": dt.datetime.fromtimestamp(ts[0]).isoformat(timespec="seconds"),
        "mtime_max": dt.datetime.fromtimestamp(ts[-1]).isoformat(timespec="seconds"),
    }


def sha_of_dirs(by_date: dict[str, list[str]]) -> str:
    """Order-stable fingerprint of the direction content."""
    h = hashlib.sha256()
    for d in sorted(by_date):
        h.update(d.encode())
        h.update("".join(by_date[d]).encode())
    return h.hexdigest()


def prompt_hash_audit() -> dict:
    """Per-date: archived V1 node user_sha256 vs the prompt FM-1 R replayed."""
    rows, mismatch, checked = [], 0, 0
    v1_req_sha = {}
    if V1_BATCH_REQ.exists():
        for line in V1_BATCH_REQ.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            txt = d["request"]["contents"][0]["parts"][0]["text"]
            key = d.get("key", "")
            date = key.split("_")[-1] if "_" in key else None
            if date and len(date) == 8:
                date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
            v1_req_sha[date] = hashlib.sha256(txt.encode()).hexdigest()
    for node in sorted(V1_NODES.iterdir()):
        d = node.name
        f = node / "03_run_meta.json"
        g = FM1_FLASH / "R/rep1" / d / "03_run_meta.json"
        if not (f.exists() and g.exists()):
            continue
        a = json.loads(f.read_text()).get("user_sha256")
        b = json.loads(g.read_text()).get("user_sha256")
        c = v1_req_sha.get(d)
        checked += 1
        same = (a == b)
        if not same:
            mismatch += 1
        rows.append({"date": d, "v1_archived_node_user_sha256": a,
                     "fm1_R_rep1_user_sha256": b,
                     "v1_batch_request_user_sha256": c,
                     "archived_eq_fm1R": same,
                     "batchreq_eq_fm1R": (c == b) if c else None})
    return {
        "n_dates_checked": checked,
        "n_archived_vs_fm1R_prompt_hash_mismatch": mismatch,
        "n_batchrequest_vs_fm1R_prompt_hash_match": sum(
            1 for r in rows if r["batchreq_eq_fm1R"] is True),
        "sample_rows": rows[:5],
    }


def prompt_reconstruction() -> dict:
    """Rebuild the archived V1 user prompt with the V1 code path and diff it
    against the prompt FM-1 R replayed (macrochain sketch_batch_requests.jsonl).

    Returns the exact, per-date-invariant diff signature. Best-effort: if the
    macrochain imports fail the caller still gets the hash-level audit."""
    import difflib
    try:
        sys_paths = [str(REPO / "macrochain"), str(REPO / "macrochain/scripts"),
                     str(REPO / "macrochain/visualizer")]
        import sys
        for p in sys_paths:
            if p not in sys.path:
                sys.path.insert(0, p)
        import run_async_sketch_panel as V1RUN          # noqa: N806
        vs = V1RUN.visualizer_server
        from src.phase2.sketch import build_prompt
        catalog, schema = vs._load_catalog(), vs._load_schema()
        tsb = vs._target_summary()
    except Exception as exc:                            # pragma: no cover
        return {"status": f"IMPORT_FAILED: {type(exc).__name__}: {exc}"}

    reqs = {}
    for line in V1_BATCH_REQ.read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        k = o["key"].split("_")[-1]
        reqs[f"{k[:4]}-{k[4:6]}-{k[6:]}"] = o["request"]["contents"][0]["parts"][0]["text"]

    match = mismatch = 0
    sigs: dict[tuple, int] = {}
    for node in sorted(V1_NODES.iterdir()):
        d = node.name
        ts = dict(tsb)
        ts["macro_runtime"] = vs._macro_runtime_summary(d)
        _, up = build_prompt(catalog, ts, schema, n_sketches=8, decision_date=d)
        arch = json.loads((node / "03_run_meta.json").read_text())["user_sha256"]
        ok = hashlib.sha256(up.encode()).hexdigest() == arch
        match += ok
        mismatch += (not ok)
        dl = tuple(l for l in difflib.unified_diff(
            reqs[d].splitlines(), up.splitlines(), lineterm="", n=0)
            if l[:1] in "+-" and l[:3] not in ("---", "+++"))
        sigs[dl] = sigs.get(dl, 0) + 1
    top = max(sigs.items(), key=lambda x: x[1])
    return {
        "status": "OK",
        "archived_V1_prompt_reproducible_from_current_code": f"{match}/{match + mismatch}",
        "n_distinct_diff_signatures_vs_fm1_replay_prompt": len(sigs),
        "diff_signature_count": top[1],
        "diff_lines_archived_minus_fm1replay": list(top[0]),
        "interpretation": "'+' lines are present in the 2026-04 ARCHIVED prompt and "
                          "absent from the prompt FM-1 R replayed in 2026-07.",
    }


# ---------------------------------------------------------------- main
def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    dates_all = sorted(dirs_from_jsonl(V1_PANEL).keys())
    calm = [d for d in dates_all if d[:4] in CALM_YEARS]
    rng = np.random.default_rng(SEED)

    # ---- load every batch/rep
    v1 = dirs_from_jsonl(V1_PANEL)
    kt1 = dirs_from_nodes(KT1_NODES)
    fm1: dict[str, dict[int, dict]] = {}
    for arm in ("R", "D", "M", "W"):
        fm1[arm] = {}
        for rep in (1, 2, 3):
            fm1[arm][rep] = dirs_from_nodes(FM1_FLASH / arm / f"rep{rep}")
    fm2_R = dirs_from_jsonl(FM2 / "R/sketches_panel.jsonl")
    fm2_M = dirs_from_jsonl(FM2 / "M/sketches_panel.jsonl")

    # ---- identity checks
    identity = {
        "fm2_R_S0_sketches_equal_fm1_R_rep1": sha_of_dirs(fm2_R) == sha_of_dirs(fm1["R"][1]),
        "fm2_M_S0_sketches_equal_fm1_M_rep1": sha_of_dirs(fm2_M) == sha_of_dirs(fm1["M"][1]),
        "fm1_M_rep1_equal_kt1_masked": sha_of_dirs(fm1["M"][1]) == sha_of_dirs(kt1),
        "fm1_M_rep1_bytes_equal_kt1_masked": all(
            hashlib.md5((FM1_FLASH / "M/rep1" / d / "01_sketches_valid.json").read_bytes()).hexdigest()
            == hashlib.md5((KT1_NODES / d / "01_sketches_valid.json").read_bytes()).hexdigest()
            for d in dates_all
            if (FM1_FLASH / "M/rep1" / d / "01_sketches_valid.json").exists()
            and (KT1_NODES / d / "01_sketches_valid.json").exists()),
        "v1_panel_equal_concat_of_v1_nodes": sha_of_dirs(v1) == sha_of_dirs(dirs_from_nodes(V1_NODES)),
        "fingerprints": {
            "v1_panel": sha_of_dirs(v1)[:16],
            "fm1_R_rep1": sha_of_dirs(fm1["R"][1])[:16],
            "fm2_R_S0": sha_of_dirs(fm2_R)[:16],
            "fm1_M_rep1": sha_of_dirs(fm1["M"][1])[:16],
            "kt1_masked": sha_of_dirs(kt1)[:16],
            "fm2_M_S0": sha_of_dirs(fm2_M)[:16],
        },
    }

    # ---- the three headline numbers, per batch
    headline = {
        "31.8pp_V1_archived_R": gap_detail(v1, CRISIS, calm),
        "28.1pp_FM1_R_pooled_rep1-3": gap_detail(
            pool(fm1["R"][1], fm1["R"][2], fm1["R"][3]), CRISIS, calm),
        "21.3pp_FM2_S0_R": gap_detail(fm2_R, CRISIS, calm),
    }

    # ---- per-rep, per-arm gaps (the monotone-in-time question)
    per_rep = {}
    for arm in ("R", "D", "M", "W"):
        for rep in (1, 2, 3):
            m = scan_metas(FM1_FLASH / arm / f"rep{rep}")
            per_rep[f"FM1_{arm}_rep{rep}"] = {
                **gap_detail(fm1[arm][rep], CRISIS, calm),
                "generated_at_min": m.get("generated_at_min"),
                "generated_at_max": m.get("generated_at_max"),
                "model_strings": m.get("model_strings"),
                "model_version_reported": m.get("model_version_reported"),
            }
        per_rep[f"FM1_{arm}_pooled"] = gap_detail(
            pool(*[fm1[arm][r] for r in (1, 2, 3)]), CRISIS, calm)

    # ---- Q3: does the masked arm drift too? Gap(R)-Gap(M) per batch
    both_arms = {}
    for rep in (1, 2, 3):
        gr = gap(fm1["R"][rep], CRISIS, calm)
        gm = gap(fm1["M"][rep], CRISIS, calm)
        both_arms[f"FM1_rep{rep}"] = {"gap_R": gr, "gap_M": gm, "gap_R_minus_M": gr - gm}
    gr = gap(pool(*[fm1["R"][r] for r in (1, 2, 3)]), CRISIS, calm)
    gm = gap(pool(*[fm1["M"][r] for r in (1, 2, 3)]), CRISIS, calm)
    both_arms["FM1_pooled_3reps"] = {"gap_R": gr, "gap_M": gm, "gap_R_minus_M": gr - gm}
    both_arms["FM2_S0"] = {"gap_R": gap(fm2_R, CRISIS, calm),
                           "gap_M": gap(fm2_M, CRISIS, calm),
                           "gap_R_minus_M": gap(fm2_R, CRISIS, calm) - gap(fm2_M, CRISIS, calm)}
    both_arms["V1_archived_R_vs_KT1_M"] = {
        "gap_R": gap(v1, CRISIS, calm), "gap_M": gap(kt1, CRISIS, calm),
        "gap_R_minus_M": gap(v1, CRISIS, calm) - gap(kt1, CRISIS, calm),
        "note": "cross-batch pairing: R from 2026-04-16 archive, M from 2026-07-02 KT-1; "
                "the V1 archive contains NO masked arm",
    }

    # ---- bootstrap CIs on the cross-batch differences of R-M
    fm1R = pool(*[fm1["R"][r] for r in (1, 2, 3)])
    fm1M = pool(*[fm1["M"][r] for r in (1, 2, 3)])
    ci = {}
    ci["V1archived_R_minus_FM1pooled_R"] = {
        "est": gap(v1, CRISIS, calm) - gap(fm1R, CRISIS, calm),
        "ci95": boot_ci(lambda c, q: gap(v1, c, q) - gap(fm1R, c, q), CRISIS, calm,
                        np.random.default_rng(SEED)),
    }
    ci["FM1pooled_R_minus_FM2S0_R"] = {
        "est": gap(fm1R, CRISIS, calm) - gap(fm2_R, CRISIS, calm),
        "ci95": boot_ci(lambda c, q: gap(fm1R, c, q) - gap(fm2_R, c, q), CRISIS, calm,
                        np.random.default_rng(SEED)),
    }
    d_arch = gap(v1, CRISIS, calm) - gap(kt1, CRISIS, calm)
    d_fm1 = gap(fm1R, CRISIS, calm) - gap(fm1M, CRISIS, calm)
    d_fm2 = gap(fm2_R, CRISIS, calm) - gap(fm2_M, CRISIS, calm)
    ci["RminusM_archived_minus_RminusM_FM1"] = {
        "est": d_arch - d_fm1,
        "ci95": boot_ci(lambda c, q: (gap(v1, c, q) - gap(kt1, c, q))
                        - (gap(fm1R, c, q) - gap(fm1M, c, q)), CRISIS, calm,
                        np.random.default_rng(SEED)),
    }
    ci["RminusM_archived_minus_RminusM_FM2S0"] = {
        "est": d_arch - d_fm2,
        "ci95": boot_ci(lambda c, q: (gap(v1, c, q) - gap(kt1, c, q))
                        - (gap(fm2_R, c, q) - gap(fm2_M, c, q)), CRISIS, calm,
                        np.random.default_rng(SEED)),
    }
    ci["RminusM_FM1_minus_RminusM_FM2S0"] = {
        "est": d_fm1 - d_fm2,
        "ci95": boot_ci(lambda c, q: (gap(fm1R, c, q) - gap(fm1M, c, q))
                        - (gap(fm2_R, c, q) - gap(fm2_M, c, q)), CRISIS, calm,
                        np.random.default_rng(SEED)),
    }

    # ---- within-batch replicate noise: is 10.5pp larger than rep-to-rep spread?
    rep_noise = {}
    for arm in ("R", "D", "M", "W"):
        gs = [gap(fm1[arm][r], CRISIS, calm) for r in (1, 2, 3)]
        rep_noise[arm] = {
            "gap_rep1": gs[0], "gap_rep2": gs[1], "gap_rep3": gs[2],
            "range_pp": (max(gs) - min(gs)) * 100,
            "sd_pp": float(np.std(gs, ddof=1)) * 100,
        }
        for i, j in ((1, 2), (1, 3), (2, 3)):
            rep_noise[f"{arm}_rep{i}_minus_rep{j}"] = {
                "est": gs[i - 1] - gs[j - 1],
                "ci95": boot_ci(lambda c, q, i=i, j=j: gap(fm1[arm][i], c, q) - gap(fm1[arm][j], c, q),
                                CRISIS, calm, np.random.default_rng(SEED)),
            }
    # single-rep gap CIs (the width the drift must be judged against)
    rep_ci = {}
    for arm in ("R", "M"):
        for r in (1, 2, 3):
            rep_ci[f"FM1_{arm}_rep{r}"] = {
                "est": gap(fm1[arm][r], CRISIS, calm),
                "ci95": boot_ci(lambda c, q, a=arm, rr=r: gap(fm1[a][rr], c, q),
                                CRISIS, calm, np.random.default_rng(SEED)),
            }
    rep_ci["V1_archived_R"] = {
        "est": gap(v1, CRISIS, calm),
        "ci95": boot_ci(lambda c, q: gap(v1, c, q), CRISIS, calm, np.random.default_rng(SEED)),
    }
    rep_ci["FM1_R_pooled"] = {
        "est": gap(fm1R, CRISIS, calm),
        "ci95": boot_ci(lambda c, q: gap(fm1R, c, q), CRISIS, calm, np.random.default_rng(SEED)),
    }

    # ---- time-ordered sequence of R-arm gaps (the monotonicity question)
    time_ordered = [
        {"label": "V1 archived panel (R)", "gap": gap(v1, CRISIS, calm),
         "when": "2026-04-16 16:42..17:00 local (file mtimes; no generated_at recorded)"},
        {"label": "FM-1 R rep1", "gap": gap(fm1["R"][1], CRISIS, calm),
         "when": "2026-07-02T13:11:53..13:13:08"},
        {"label": "FM-1 R rep2", "gap": gap(fm1["R"][2], CRISIS, calm),
         "when": "2026-07-02T13:13:00..13:14:20"},
        {"label": "FM-1 R rep3", "gap": gap(fm1["R"][3], CRISIS, calm),
         "when": "2026-07-02T13:14:20..13:15:43"},
    ]

    # ---- provenance / endpoint-version evidence
    provenance = {
        "V1_archived_panel": {
            "path": str(V1_PANEL),
            "panel_mtime": dt.datetime.fromtimestamp(
                os.path.getmtime(V1_PANEL)).isoformat(timespec="seconds"),
            "node_meta": scan_metas(V1_NODES),
            "node_meta_mtimes": mtime_range(V1_NODES, "*/03_run_meta.json"),
            "manifest": json.loads(
                (REPO / "macrochain/data/processed/sketch_panel_manifest.json").read_text()),
        },
        "KT1_masked": {
            "path": str(KT1_NODES),
            "node_meta": scan_metas(KT1_NODES),
        },
        "FM1_flash": {
            arm: {f"rep{r}": scan_metas(FM1_FLASH / arm / f"rep{r}") for r in (1, 2, 3)}
            for arm in ("R", "D", "M", "W")
        },
        "FM2": {
            "sketch_source": "run_fm2_pipeline.py::build_sketch_panel reads "
                             "hindsight/outputs/fm1/gemini-2.5-flash/<arm>/rep1 -- "
                             "no new generation calls in FM-2",
            "R_run_log_mtime": dt.datetime.fromtimestamp(
                os.path.getmtime(FM2 / "R_run.log")).isoformat(timespec="seconds"),
            "M_run_log_mtime": dt.datetime.fromtimestamp(
                os.path.getmtime(FM2 / "M_run.log")).isoformat(timespec="seconds"),
        },
        "prompt_hash_audit": prompt_hash_audit(),
        "prompt_reconstruction": prompt_reconstruction(),
        "gemini_usage_ledger": {
            "path": str(REPO / "hindsight/outputs/gemini_usage_log.jsonl"),
            "fields_recorded": ["ts", "model", "prompt", "output", "thoughts", "total"],
            "distinct_model_values": ["gemini-2.5-flash", "gemini-2.5-pro"],
            "no_version_suffix_no_api_version_no_response_id": True,
            "ts_range": "2026-07-02T19:13:00 .. 2026-07-19T17:39:12 "
                        "(starts AFTER the FM-1 generation window; does not cover it)",
        },
        "generation_parameters_recorded": {
            "V1_run_async_sketch_panel.py": {
                "model": "models/gemini-2.5-flash (node meta)",
                "base_url": "https://generativelanguage.googleapis.com/v1beta (L50)",
                "temperature_default": 0.2,
                "max_tokens_default": 16384,
                "max_tokens_actually_used": "NOT RECORDED in sketch_panel_manifest.json",
                "model_version_reported_field": "absent from V1 node metas",
            },
            "KT1_run_kt1_masked_arm.py": {
                "model": "models/gemini-2.5-flash (L38)",
                "base_url": "https://generativelanguage.googleapis.com/v1beta (L37)",
                "temperature": 0.2, "max_tokens": 8192,
                "disclosed_deviation": "L254-256 comment: deviation from prereg "
                                       "'V1-identical 4096' because 37 nodes hit MAX_TOKENS "
                                       "-- 'the current endpoint spends thinking tokens "
                                       "inside the cap'",
            },
            "FM1_run_fm1_arms.py": {
                "temperature": 0.2, "max_tokens": 8192, "line": "L122",
            },
        },
    }

    out = {
        "note": "POST-FREEZE EXPLORATORY 2026-07-25; frozen dirs read-only",
        "gap_definition": "bearish_share(CRISIS) - bearish_share(CALM), pooled over "
                          "sketches; CRISIS = 11 dates, CALM = all dates in 2013/2014/2017",
        "n_crisis_dates": len(CRISIS), "n_calm_dates": len(calm),
        "headline_three_numbers": headline,
        "identity_checks": identity,
        "per_rep_gaps": per_rep,
        "both_arms_per_batch": both_arms,
        "within_batch_replicate_noise": rep_noise,
        "single_run_gap_cis": rep_ci,
        "time_ordered_R_gaps": time_ordered,
        "bootstrap_cross_batch": ci,
        "provenance": provenance,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, default=float))

    # ---- markdown
    L = ["# Batch-drift provenance audit (POST-FREEZE EXPLORATORY, 2026-07-25)", "",
         f"Gap = bearish share(crisis, n={len(CRISIS)} dates) - bearish share(calm, "
         f"n={len(calm)} dates), pooled over sketches.", "",
         "## 1. The three headline numbers", "",
         "| label | gap | crisis share | calm share | n sketches | n dates |",
         "|---|---|---|---|---|---|"]
    for k, v in headline.items():
        L.append(f"| {k} | {v['gap']*100:+.1f}pp | {v['crisis_bearish_share']:.3f} | "
                 f"{v['calm_bearish_share']:.3f} | {v['n_sketches_total']} | {v['n_dates_covered']} |")
    L += ["", "## 2. Identity checks", ""]
    for k, v in identity.items():
        if k != "fingerprints":
            L.append(f"- `{k}` = **{v}**")
    L += ["", "## 3. Per-rep gaps with generation timestamps", "",
          "| run | gap | n sketches | generated_at min | generated_at max |",
          "|---|---|---|---|---|"]
    for k, v in per_rep.items():
        L.append(f"| {k} | {v['gap']*100:+.1f}pp | {v['n_sketches_total']} | "
                 f"{v.get('generated_at_min')} | {v.get('generated_at_max')} |")
    L += ["", "## 4. Both-arms test: Gap(R), Gap(M), Gap(R)-Gap(M) per batch", "",
          "| batch | Gap(R) | Gap(M) | Gap(R)-Gap(M) |", "|---|---|---|---|"]
    for k, v in both_arms.items():
        L.append(f"| {k} | {v['gap_R']*100:+.1f}pp | {v['gap_M']*100:+.1f}pp | "
                 f"{v['gap_R_minus_M']*100:+.1f}pp |")
    L += ["", "## 4b. Time-ordered R-arm gaps (generation order, not pooling order)", "",
          "| when | run | Gap(R) |", "|---|---|---|"]
    for row in time_ordered:
        L.append(f"| {row['when']} | {row['label']} | {row['gap']*100:+.1f}pp |")
    L += ["", "## 4c. Within-batch replicate noise (FM-1, all 3 reps same day, minutes apart)", "",
          "| arm | rep1 | rep2 | rep3 | range | sd |", "|---|---|---|---|---|---|"]
    for arm in ("R", "D", "M", "W"):
        v = rep_noise[arm]
        L.append(f"| {arm} | {v['gap_rep1']*100:+.1f}pp | {v['gap_rep2']*100:+.1f}pp | "
                 f"{v['gap_rep3']*100:+.1f}pp | {v['range_pp']:.1f}pp | {v['sd_pp']:.1f}pp |")
    L += ["", "Rep-to-rep differences with date-level bootstrap CIs:", "",
          "| contrast | estimate | 95% CI |", "|---|---|---|"]
    for k, v in rep_noise.items():
        if "_minus_" in k:
            lo, hi = v["ci95"]
            L.append(f"| {k} | {v['est']*100:+.1f}pp | [{lo*100:+.1f}, {hi*100:+.1f}] |")
    L += ["", "Single-run gap CIs (the width any drift claim must clear):", "",
          "| run | gap | 95% CI |", "|---|---|---|"]
    for k, v in rep_ci.items():
        lo, hi = v["ci95"]
        L.append(f"| {k} | {v['est']*100:+.1f}pp | [{lo*100:+.1f}, {hi*100:+.1f}] |")
    L += ["", "## 5. Bootstrap CIs on cross-batch differences (date-level, B=10000)", "",
          "| contrast | estimate | 95% CI |", "|---|---|---|"]
    for k, v in ci.items():
        lo, hi = v["ci95"]
        L.append(f"| {k} | {v['est']*100:+.1f}pp | [{lo*100:+.1f}, {hi*100:+.1f}] |")
    L += ["", "## 6. Prompt-hash audit (V1 archive vs what FM-1 R replayed)", ""]
    pa = provenance["prompt_hash_audit"]
    L += [f"- dates checked: {pa['n_dates_checked']}",
          f"- archived V1 node `user_sha256` != FM-1 R rep1 `user_sha256`: "
          f"**{pa['n_archived_vs_fm1R_prompt_hash_mismatch']}** dates",
          f"- V1 `sketch_batch_requests.jsonl` prompt == FM-1 R rep1 prompt: "
          f"**{pa['n_batchrequest_vs_fm1R_prompt_hash_match']}** dates", ""]
    pr = provenance["prompt_reconstruction"]
    if pr.get("status") == "OK":
        L += [f"- archived V1 prompt rebuilt from current V1 code path: "
              f"**{pr['archived_V1_prompt_reproducible_from_current_code']}** exact sha256 matches",
              f"- distinct diff signatures across 240 dates: "
              f"**{pr['n_distinct_diff_signatures_vs_fm1_replay_prompt']}** "
              f"(one signature, {pr['diff_signature_count']} dates)",
              "- lines present in the 2026-04 ARCHIVED prompt but absent from the "
              "prompt FM-1 R replayed:", "", "```"]
        L += list(pr["diff_lines_archived_minus_fm1replay"])
        L += ["```", ""]
    else:
        L += [f"- prompt reconstruction: {pr.get('status')}", ""]
    L += ["## 7. Recorded model / endpoint strings", ""]
    L.append(f"- V1 archived nodes: {provenance['V1_archived_panel']['node_meta']}")
    L.append(f"- KT-1 masked nodes: {provenance['KT1_masked']['node_meta']}")
    for arm in ("R", "D", "M", "W"):
        for r in (1, 2, 3):
            m = provenance["FM1_flash"][arm][f"rep{r}"]
            if m:
                L.append(f"- FM-1 {arm} rep{r}: models={m['model_strings']} "
                         f"version_reported={m['model_version_reported']} "
                         f"[{m['generated_at_min']} .. {m['generated_at_max']}]")
    OUT_MD.write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
