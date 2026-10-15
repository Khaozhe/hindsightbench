#!/usr/bin/env python
"""ST-1 via the Gemini Batch API (50% list price; async, typically < 24 h).

Same prompts / generation configs as run_st1.py's online Gemini path (call_gemini):
arms temp 0.2 / 8192 / JSON mime; LAP temp 1.0 / 2048 / JSON mime; REC temp 0 / 2048 / JSON mime;
thinking left at the endpoint default (as in GD-1 and the BM-1 flash row).

  python run_st1_batch.py export                     # -> outputs/st1/<tag>/batch/{arms,lap,rec}_requests.jsonl
  python run_st1_batch.py submit  --job arms|lap|rec # upload + create batch job -> <job>_submission.json
  python run_st1_batch.py status  [--job ...]        # poll; downloads results when SUCCEEDED
  python run_st1_batch.py materialize [--job ...]    # results -> standard row layout (+ usage ledger)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import run_st1 as st1  # noqa: E402
from run_kt1_masked_arm import load_api_key, validate_sketches, _log_usage  # noqa: E402
from build_st_panel import REGIONS  # noqa: E402

BASE = "https://generativelanguage.googleapis.com"
MODEL = "models/gemini-2.5-flash"
import os
TAG = os.environ.get("ST1_TAG", "gemini-2.5-flash")   # e.g. ST1_TAG=gemini-2.5-flash-r2 for a replicate row
ROW = st1.OUT_ROOT / TAG
BDIR = ROW / "batch"
JOBS = ("arms", "lap", "rec")


def gen_cfg(temperature: float, max_tokens: int) -> dict:
    return {"temperature": temperature, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"}


def req(system: str, user: str, cfg: dict) -> dict:
    return {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": cfg}


def export() -> None:
    BDIR.mkdir(parents=True, exist_ok=True)
    nodes = st1.load_panel()
    done_arm = lambda a, n: (ROW / a / "rep1" / n["node_id"] / "01_sketches_valid.json").exists()
    counts = {}
    with (BDIR / "arms_requests.jsonl").open("w") as f:
        k = 0
        for n in nodes:
            for a in st1.ARMS:
                if done_arm(a, n):
                    continue
                f.write(json.dumps({"key": f"arm|{a}|{n['node_id']}",
                                    "request": req(st1.SYSTEM, st1.user_prompt(n, a), gen_cfg(0.2, st1.ARM_MAX_TOKENS))}) + "\n")
                k += 1
        counts["arms"] = k
    with (BDIR / "lap_requests.jsonl").open("w") as f:
        k = 0
        for n in nodes:
            u = st1.LAP_PROMPT.format(city=REGIONS[n["city"]][3], t=n["decision_date"])
            for r in range(st1.LAP_REPS):
                f.write(json.dumps({"key": f"lap|{n['node_id']}|{r}",
                                    "request": req(st1.LAP_SYSTEM, u, gen_cfg(1.0, st1.LAP_MAX_TOKENS))}) + "\n")
                k += 1
        counts["lap"] = k
    with (BDIR / "rec_requests.jsonl").open("w") as f:
        k = 0
        for n in nodes:
            snap = st1.snapshot_block(n)
            assert not st1.YEAR_RE.search(snap) and not st1.CITY_RE.search(snap)
            f.write(json.dumps({"key": f"rec|{n['node_id']}",
                                "request": req(st1.REC_SYSTEM, st1.REC_PROMPT.format(snapshot=snap), gen_cfg(0.0, st1.REC_MAX_TOKENS))}) + "\n")
            k += 1
        counts["rec"] = k
    (BDIR / "EXPORT_MANIFEST.json").write_text(json.dumps({
        "model": MODEL, "exported_at": dt.datetime.now().isoformat(timespec="seconds"), "counts": counts,
        "prereg": st1.PREREG, "thinking": "endpoint default (GD-1 / BM-1 flash convention)"}, indent=2))
    print("exported:", counts)


def upload(api_key: str, path: Path, display: str) -> str:
    s = requests.Session(); s.trust_env = False
    h = {"x-goog-api-key": api_key, "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
         "X-Goog-Upload-Header-Content-Type": "application/jsonl",
         "X-Goog-Upload-Header-Content-Length": str(path.stat().st_size), "Content-Type": "application/json"}
    r = s.post(f"{BASE}/upload/v1beta/files", headers=h, json={"file": {"display_name": display}}, timeout=180)
    r.raise_for_status()
    url = r.headers["X-Goog-Upload-URL"]
    r = s.post(url, headers={"x-goog-api-key": api_key, "X-Goog-Upload-Command": "upload, finalize",
                             "X-Goog-Upload-Offset": "0", "Content-Type": "application/jsonl"},
               data=path.read_bytes(), timeout=1800)
    r.raise_for_status()
    j = r.json()
    return j.get("file", {}).get("name") or j["name"]


def submit(job: str) -> None:
    api_key = load_api_key()
    path = BDIR / f"{job}_requests.jsonl"
    n = sum(1 for _ in path.open())
    if n == 0:
        print(f"{job}: nothing to submit"); return
    fname = upload(api_key, path, f"st1-{job}-{TAG}")
    s = requests.Session(); s.trust_env = False
    r = s.post(f"{BASE}/v1beta/{MODEL}:batchGenerateContent",
               headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
               json={"batch": {"display_name": f"st1-{job}-{TAG}", "input_config": {"file_name": fname}}}, timeout=180)
    r.raise_for_status()
    j = r.json()
    (BDIR / f"{job}_submission.json").write_text(json.dumps({"job": job, "n_requests": n, "uploaded_file": fname,
        "batch": j, "submitted_at": dt.datetime.now().isoformat(timespec="seconds")}, indent=2))
    print(f"{job}: {n} requests -> {j.get('name')} state={j.get('metadata', {}).get('state')}")


def status(job: str) -> str | None:
    sub = BDIR / f"{job}_submission.json"
    if not sub.exists():
        print(f"{job}: not submitted"); return None
    api_key = load_api_key()
    name = json.loads(sub.read_text())["batch"]["name"]
    s = requests.Session(); s.trust_env = False
    j = s.get(f"{BASE}/v1beta/{name}", headers={"x-goog-api-key": api_key}, timeout=180).json()
    (BDIR / f"{job}_status.json").write_text(json.dumps(j, indent=2))
    st = (j.get("metadata") or {}).get("state") or j.get("state")
    stats = (j.get("metadata") or {}).get("batchStats") or {}
    print(f"{job}: {st} {stats}")
    out = BDIR / f"{job}_results.jsonl"
    if st and st.endswith("SUCCEEDED") and not out.exists():
        rf = None
        for pk in ("response", "dest"):
            p = j.get(pk) or {}
            rf = p.get("responsesFile") or p.get("fileName") or rf
        if rf:
            r = s.get(f"{BASE}/download/v1beta/{rf}:download?alt=media", headers={"x-goog-api-key": api_key}, timeout=1800)
            r.raise_for_status(); out.write_bytes(r.content)
            print(f"{job}: downloaded {out.stat().st_size} bytes")
        else:  # inlined responses
            inl = (j.get("response") or {}).get("inlinedResponses") or []
            if inl:
                with out.open("w") as f:
                    for x in inl:
                        f.write(json.dumps(x) + "\n")
                print(f"{job}: {len(inl)} inlined responses saved")
    return st


def _text(resp: dict) -> tuple[str, str, str]:
    """-> (text, finishReason, modelVersion); logs usage to the shared gemini ledger."""
    _log_usage(resp)
    c = (resp.get("candidates") or [{}])[0]
    parts = (c.get("content") or {}).get("parts") or []
    txt = "\n".join(p["text"] for p in parts if isinstance(p.get("text"), str)).strip()
    return txt, c.get("finishReason", ""), resp.get("modelVersion", "unknown")


def materialize(job: str) -> None:
    path = BDIR / f"{job}_results.jsonl"
    if not path.exists():
        print(f"{job}: no results yet"); return
    panel = {n["node_id"]: n for n in st1.load_panel()}
    ok = bad = 0
    lap_f = (ROW / "lap_results.jsonl").open("a") if job == "lap" else None
    rec_f = (ROW / "rec_results.jsonl").open("a") if job == "rec" else None
    seen_lap = set()
    if job == "lap" and (ROW / "lap_results.jsonl").exists():
        seen_lap = {(json.loads(l)["node_id"], json.loads(l)["rep"]) for l in (ROW / "lap_results.jsonl").read_text().splitlines() if l.strip()}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        key = d.get("key") or (d.get("metadata") or {}).get("key") or ""
        resp = d.get("response")
        if not resp or d.get("error"):
            bad += 1; continue
        txt, fr, mv = _text(resp)
        parts = key.split("|")
        if parts[0] == "arm":
            _, a, nid = parts
            n = panel[nid]
            dd = ROW / a / "rep1" / nid
            if (dd / "01_sketches_valid.json").exists():
                continue
            dd.mkdir(parents=True, exist_ok=True)
            (dd / "04_raw_response.txt").write_text(txt)
            if fr == "MAX_TOKENS" or not txt:
                (dd / "99_parse_error.txt").write_text(f"finishReason={fr}"); bad += 1; continue
            try:
                valid, invalid = validate_sketches(txt, n["decision_date"])
            except (json.JSONDecodeError, ValueError) as exc:
                (dd / "99_parse_error.txt").write_text(str(exc)); bad += 1; continue
            (dd / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
            (dd / "03_run_meta.json").write_text(json.dumps({
                "node_id": nid, "city": n["city"], "decision_date": n["decision_date"], "arm": a, "rep": 1,
                "asserted_city": (n["fake_city"] if a == "S" else n["city"] if a in ("L", "DL") else None),
                "model_reported": mv, "valid_count": len(valid), "invalid_count": invalid, "target": "RETAIL_REC-4w",
                "prereg": st1.PREREG, "via": "gemini-batch", "generated_at": dt.datetime.now().isoformat(timespec="seconds")}, indent=2))
            ok += 1
        elif parts[0] == "lap":
            _, nid, rep = parts
            if (nid, int(rep)) in seen_lap:
                continue
            t = txt.lower()
            if t.startswith("{"):
                try:
                    t = " ".join(str(v) for v in json.loads(t).values())
                except json.JSONDecodeError:
                    pass
            words = [w for w in re.findall(r"[a-z]+", t) if w in ("higher", "lower", "unknown")]
            ans = words[-1] if words else "invalid"
            n = panel[nid]
            lap_f.write(json.dumps({"node_id": nid, "city": n["city"], "decision_date": n["decision_date"], "rep": int(rep),
                                    "answer": ans, "raw": txt[-80:], "model_reported": mv, "via": "gemini-batch"}) + "\n")
            ok += 1
        elif parts[0] == "rec":
            _, nid = parts
            est_d = est_c = ""
            for m in re.finditer(r"\{[^{}]*\}", txt):
                try:
                    j = json.loads(m.group(0)); est_d = str(j.get("estimated_date", est_d)); est_c = str(j.get("estimated_city", est_c))
                except json.JSONDecodeError:
                    continue
            n = panel[nid]
            rec_f.write(json.dumps({"node_id": nid, "city": n["city"], "decision_date": n["decision_date"], "estimated_date": est_d,
                                    "estimated_city": est_c, "raw": txt[:200], "model_reported": mv, "via": "gemini-batch"}) + "\n")
            ok += 1
    for f in (lap_f, rec_f):
        if f: f.close()
    print(f"{job}: materialized {ok} ok, {bad} failed/skipped")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "submit", "status", "materialize"])
    ap.add_argument("--job", choices=JOBS, default=None)
    args = ap.parse_args()
    jobs = [args.job] if args.job else list(JOBS)
    if args.cmd == "export":
        export()
    elif args.cmd == "submit":
        for j in jobs: submit(j)
    elif args.cmd == "status":
        for j in jobs: status(j)
    else:
        for j in jobs: materialize(j)


if __name__ == "__main__":
    main()
