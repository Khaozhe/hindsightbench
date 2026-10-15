#!/usr/bin/env python
"""ST-1 spatio-temporal panel runner (prereg: prereg/ST1_prereg_spatiotemporal.md, f0284181).

Arms M / D / L / DL / S x 310 (city, month) nodes x 1 rep, temp 0.2;
LAP-ST (310 x 20 reps, temp 1.0); REC-ST (310 x 1, temp 0).
Reuses call_gemini / validate_sketches / usage ledger from run_kt1_masked_arm.

Usage:
  python run_st1.py --job dry   [--n 2]           # print prompts + leak checks, no API
  python run_st1.py --job smoke                   # 2 nodes x 5 arms + 2 LAP + 2 REC -> per-call usage
  python run_st1.py --job arms  [--arms M,D,L,DL,S] [--concurrency 64]
  python run_st1.py --job lap   [--concurrency 100]
  python run_st1.py --job rec   [--concurrency 64]
  --model models/gemini-2.5-flash (default)   --tag <row dir name> (default: model short name)
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import run_kt1_masked_arm as kt1  # noqa: E402
from run_kt1_masked_arm import call_gemini, load_api_key, validate_sketches  # noqa: E402
from llm_adapters import call_openai_compat, call_anthropic_messages, load_key, ANTHROPIC_KEY_FILE, strip_fences  # noqa: E402
from build_st_panel import REGIONS, FAKE_CITY, CATS  # noqa: E402
from hindsight_paths import REPO  # noqa: E402

OUT_ROOT = REPO / "hindsight/outputs/st1"
PANEL = OUT_ROOT / "panel/nodes.jsonl"
PREREG = "ST1_prereg_spatiotemporal.md f0284181"
ARMS = ("M", "D", "L", "DL", "S")
ARM_MAX_TOKENS, LAP_MAX_TOKENS, REC_MAX_TOKENS = 8192, 2048, 2048
# reasoning APIs burn the budget before answering (BM-1 convention: LAP 8192, REC 16384)
REASONING_BUDGETS = {"deepseek": (16384, 8192, 16384), "openai": (16384, 8192, 16384), "kimi": (16384, 8192, 16384),
                     "anthropic": (16384, 2048, 2048)}  # arm, lap, rec (Sonnet 5 writes 3-8k tokens per arm call)
LAP_REPS = 20
BUDGET = None   # seconds; set by --budget (sandboxed shells cap wall time)
import time as _time
_T0 = _time.time()


def over_budget() -> bool:
    return BUDGET is not None and (_time.time() - _T0) > BUDGET

COL = {"retail_and_recreation": "RETAIL_REC", "grocery_and_pharmacy": "GROCERY_PHARM",
       "parks": "PARKS", "transit_stations": "TRANSIT", "workplaces": "WORKPLACES",
       "residential": "RESIDENTIAL"}

SYSTEM = """You are an urban-mobility analyst. Given a point-in-time snapshot of community
mobility indices for one metropolitan area (percent change from a pre-period baseline,
six place categories, four weekly means), you propose structured mechanism hypotheses
explaining how recent mobility patterns drive the direction of retail-and-recreation
mobility over the next four weeks.

Each hypothesis must be a concrete, falsifiable causal claim - not a vague narrative.
It must specify which observable series drive the mechanism, in what direction,
over what horizon, and under what conditions it would fail.

OUTPUT FORMAT: A single JSON array of hypothesis objects. Nothing else - no prose,
no markdown fences, no commentary. Every field in the provided schema is required.
candidate_proxies must use exact series IDs from the observable catalog.
candidate_interactions must be a JSON boolean (true/false), not a string.
direction must be "+" or "-" only."""

SCHEMA = {
    "required_fields": ["hypothesis_id", "dominant_domain", "mechanism_narrative", "direction",
                        "candidate_proxies", "candidate_horizon_hint", "candidate_trigger",
                        "candidate_interactions", "evidence_refs", "regime_hint", "failure_condition"],
    "field_constraints": {
        "hypothesis_id": {"type": "string", "pattern": "^H_[0-9]{3,}$"},
        "dominant_domain": {"type": "string", "enum": ["activity", "policy", "behavioral", "seasonal"],
                            "description": "Primary driver class of the mechanism."},
        "mechanism_narrative": {"type": "string", "minLength": 40, "maxLength": 400,
                                "description": "Plain-language falsifiable mechanism. No hedged language."},
        "direction": {"type": "string", "enum": ["+", "-"],
                      "description": "Predicted direction of RETAIL_REC over the next 4 weeks relative to the last 4 weeks. '+' = higher, '-' = lower."},
        "candidate_proxies": {"type": "array", "minItems": 1, "maxItems": 4,
                              "description": "Series IDs drawn exclusively from [AVAILABLE_COLUMNS]."},
        "candidate_horizon_hint": {"type": "integer", "enum": [1, 2, 4],
                                   "description": "Horizon in weeks over which the mechanism acts."},
        "candidate_trigger": {"type": "string", "minLength": 4,
                              "description": "'none' if always-on; otherwise the threshold/regime condition (e.g. 'TRANSIT falls > 20 points week-on-week')."},
        "candidate_interactions": {"type": "boolean"},
        "evidence_refs": {"type": "array", "minItems": 1,
                          "description": "'series:<ID>' or 'fact:<description>' visible in this snapshot."},
        "regime_hint": {"type": "string", "minLength": 4,
                        "description": "Regime in which the mechanism is active (e.g. 'tightening restrictions', 'reopening', 'steady state', 'any regime')."},
        "failure_condition": {"type": "string", "minLength": 20,
                              "description": "Observable outcome that would reject the hypothesis."},
    },
}

USER_TMPL = """        Decision time point: {date_line} Location: {loc_line} Only information contained in this snapshot is admissible as evidence.

        ## Observable Catalog (closed vocabulary - proxies MUST come from this list)

        [AVAILABLE_COLUMNS] = [RETAIL_REC, GROCERY_PHARM, PARKS, TRANSIT, WORKPLACES, RESIDENTIAL]

        Binding rule: candidate_proxies may only copy exact tokens from [AVAILABLE_COLUMNS].

        Series ID     | Place category          | Unit
----------------------------------------------------------------------
RETAIL_REC    | retail and recreation   | percent change from baseline
GROCERY_PHARM | grocery and pharmacy    | percent change from baseline
PARKS         | parks                   | percent change from baseline
TRANSIT       | transit stations        | percent change from baseline
WORKPLACES    | workplaces              | percent change from baseline
RESIDENTIAL   | residential             | percent change from baseline

        ## Mobility Snapshot (four weekly means ending at the decision time point)

{snapshot}

        ## Target

          Target : direction_4w = sign(mean(RETAIL_REC over the next 28 days) - mean(RETAIL_REC over the last 28 days))

        ## Sketch Schema (JSON Schema - all sketches must conform)

        ```json
{schema}
        ```

        ## Task

        Generate exactly 8 hypothesis sketches as a JSON array.
        Assign hypothesis_id values as H_001, H_002, ..., H_008.

        Requirements:
        - Cover at least 3 different dominant_domains across the 8 sketches.
        - Include at least 1 sketch per mechanism type:
            * Always-on trend signal (candidate_trigger = "none", candidate_interactions = false)
            * Threshold-triggered signal (candidate_trigger describes a crossing condition)
            * Interaction-driven signal (candidate_interactions = true, >= 2 proxies)
            * Regime-conditional signal (regime_hint is specific, not "any regime")
        - Vary candidate_horizon_hint across 1, 2, and 4.
        - Use correct JSON types: booleans must be true/false (not "true"/"false").

        Output ONLY the JSON array - nothing else.

        ## Few-shot Example (do NOT copy H_000 - it is a format reference only)

        [
          {{
            "hypothesis_id": "H_000",
            "dominant_domain": "activity",
            "mechanism_narrative": "A sustained two-week rise in WORKPLACES mobility signals a return of commuting routines that lifts weekday retail footfall, producing higher RETAIL_REC over the next four weeks.",
            "direction": "+",
            "candidate_proxies": ["WORKPLACES"],
            "candidate_horizon_hint": 4,
            "candidate_trigger": "none",
            "candidate_interactions": false,
            "evidence_refs": ["series:WORKPLACES"],
            "regime_hint": "reopening",
            "failure_condition": "RETAIL_REC over the next 28 days is lower than over the last 28 days in more than 50% of instances where WORKPLACES rose for two consecutive weeks."
          }}
        ]"""

LAP_SYSTEM = ("You answer questions about historical community-mobility outcomes. "
              "Answer with exactly one word (if JSON output is required, use {\"answer\": \"<word>\"}).")
LAP_PROMPT = ("In {city}, was Google's retail-and-recreation mobility index (percent change from the "
              "January-February 2020 baseline) in the four weeks after {t} higher or lower than in the "
              "four weeks before {t}? Answer with exactly one word: higher, lower, or unknown.")
REC_SYSTEM = ("You are an expert on community-mobility data history. "
              "Respond with a single JSON object and nothing else.")
REC_PROMPT = """Below is a snapshot of Google community-mobility indices (percent change from a
pre-period baseline) for an undisclosed metropolitan area at an undisclosed reference date.
Each row is a weekly mean; the last row ends at the reference date.

{snapshot}

Based only on these values, what is the most likely calendar year-month of the reference
date, and which metropolitan area is this? Respond with JSON:
{{"estimated_date": "YYYY-MM", "estimated_city": "<city or region name>"}}"""

# ---------- provider dispatch ----------
PROVIDER, MODEL = "gemini", "models/gemini-2.5-flash"


PROBE_THINKING = "default"   # "off": send {"thinking": {"type": "disabled"}} on LAP/REC (disclosed regime)


async def call_llm(client, system: str, user: str, *, temperature: float, max_tokens: int,
                   json_mode: bool = True, probe: bool = False) -> tuple[str, str]:
    if PROVIDER == "gemini":
        return await call_gemini(client, load_api_key(), system, user, temperature=temperature, max_tokens=max_tokens)
    if PROVIDER == "anthropic":
        return await call_anthropic_messages(client, MODEL, system, user, temperature=temperature, max_tokens=max_tokens)
    # probes run with json_mode=False on OpenAI-compatible reasoning endpoints: response_format
    # json_object makes deepseek-v4-flash reason past the 8192 cap (57% truncation, 2026-10-13);
    # free text converges (BM-1 convention: parse the last standalone answer word)
    extra = {"thinking": {"type": "disabled"}} if (probe and PROBE_THINKING == "off") else None
    return await call_openai_compat(client, PROVIDER, MODEL, system, user,
                                    temperature=temperature, max_tokens=max_tokens, json_mode=json_mode,
                                    extra_payload=extra)


# ---------- leak checks (fail-closed) ----------
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
CITY_WORDS = sorted({w for k, v in REGIONS.items() for w in re.findall(r"[A-Za-z]{4,}", v[3] + " " + v[4])
                     if w.lower() not in {"city", "community", "greater", "south", "wales", "county", "united"}}
                    | {"York", "Manhattan", "Kong", "Wales"})
CITY_RE = re.compile(r"\b(" + "|".join(map(re.escape, CITY_WORDS)) + r")\b")


def snapshot_block(node: dict) -> str:
    hdr = "          week  | " + " | ".join(f"{COL[c]:>13s}" for c in CATS)
    rows = [hdr]
    for r in node["snapshot"]:
        rows.append(f"          {r['week']:5s} | " + " | ".join(f"{r[c]:>13.1f}" for c in CATS))
    return "\n".join(rows)


def user_prompt(node: dict, arm: str) -> str:
    assert arm in ARMS
    true_city = REGIONS[node["city"]][3]
    fake_city = REGIONS[node["fake_city"]][3]
    date_line = f"{node['decision_date']} - only information available on or before this date is admissible." \
        if arm in ("D", "DL", "S") else "[undisclosed]."
    loc_line = {"M": "[undisclosed].", "D": "[undisclosed].", "L": f"{true_city}.",
                "DL": f"{true_city}.", "S": f"{fake_city}."}[arm]
    u = USER_TMPL.format(date_line=date_line, loc_line=loc_line, snapshot=snapshot_block(node),
                         schema=json.dumps(SCHEMA, indent=2))
    # fail-closed: the only year string allowed is the decision date (D/DL/S); the only
    # place names allowed are the asserted city's (L/DL true, S fake).
    years = {m.group(0) for m in YEAR_RE.finditer(u)}
    allowed_year = {node["decision_date"][:4]} if arm in ("D", "DL", "S") else set()
    if years - allowed_year:
        raise RuntimeError(f"[fail-closed] year leak {years - allowed_year} in {arm} arm for {node['node_id']}")
    allowed_city = {"M": "", "D": "", "L": true_city, "DL": true_city, "S": fake_city}[arm]
    body = u.replace(allowed_city, "") if allowed_city else u
    hit = CITY_RE.search(body)
    if hit:
        raise RuntimeError(f"[fail-closed] place leak {hit.group(0)!r} in {arm} arm for {node['node_id']}")
    return u


def load_panel() -> list[dict]:
    return [json.loads(l) for l in PANEL.read_text().splitlines() if l.strip()]


def smoke_nodes(nodes: list[dict]) -> list[dict]:
    want = {"nyc_2020-03", "melbourne_2022-07"}   # one crisis onset, one calm
    return [n for n in nodes if n["node_id"] in want]


async def run_arms(nodes, arms, concurrency, out_dir: Path, api_key: str) -> None:
    sem = asyncio.Semaphore(concurrency)
    jobs = [(n, a) for n in nodes for a in arms
            if not (out_dir / a / "rep1" / n["node_id"] / "01_sketches_valid.json").exists()]
    print(f"st1 arms: {len(jobs)} cells")

    async def one(n, a):
        u = user_prompt(n, a)
        async with sem:
            if over_budget():
                return "skip"
            # BM-1 convention for OpenAI reasoning endpoints: free-text arms (json_object mode
            # returns a single object instead of the 8-sketch array)
            raw, mv = await call_llm(client, SYSTEM, u, temperature=0.2, max_tokens=ARM_MAX_TOKENS,
                                     json_mode=(PROVIDER != "openai"))
        d = out_dir / a / "rep1" / n["node_id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "04_raw_response.txt").write_text(raw)
        try:
            valid, invalid = validate_sketches(strip_fences(raw), n["decision_date"])  # BM-1 parser convention (fences)
        except (json.JSONDecodeError, ValueError) as exc:
            (d / "99_parse_error.txt").write_text(str(exc))
            return "perr"
        (d / "01_sketches_valid.json").write_text(json.dumps(valid, indent=2))
        (d / "03_run_meta.json").write_text(json.dumps({
            "node_id": n["node_id"], "city": n["city"], "decision_date": n["decision_date"],
            "arm": a, "rep": 1, "asserted_city": (n["fake_city"] if a == "S" else n["city"] if a in ("L", "DL") else None),
            "model_reported": mv, "valid_count": len(valid), "invalid_count": invalid,
            "target": "RETAIL_REC-4w", "prereg": PREREG,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds")}, indent=2))
        return "ok"

    global client
    async with httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=concurrency + 2)) as client:
        rs = await asyncio.gather(*(one(*j) for j in jobs), return_exceptions=True)
    print(f"st1 arms: {sum(r=='ok' for r in rs)} ok, {sum(r=='perr' for r in rs)} parse_err, "
          f"{sum(isinstance(r, Exception) for r in rs)} err, {sum(r=='skip' for r in rs)} skipped (budget)")
    for r in rs:
        if isinstance(r, Exception):
            print("ARM_ERROR:", r, file=sys.stderr)


async def run_lap(nodes, concurrency, out_dir: Path, api_key: str, reps: int) -> None:
    out_f = out_dir / "lap_results.jsonl"
    done: dict[str, int] = {}
    if out_f.exists():
        for l in out_f.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done[r["node_id"]] = done.get(r["node_id"], 0) + 1
    jobs = [(n, k) for n in nodes for k in range(reps) if k >= done.get(n["node_id"], 0)]
    print(f"st1 lap: {len(jobs)} calls")
    sem = asyncio.Semaphore(concurrency)

    async def one(n, k):
        async with sem:
            if over_budget():
                return None
            raw, mv = await call_llm(client, LAP_SYSTEM,
                                     LAP_PROMPT.format(city=REGIONS[n["city"]][3], t=n["decision_date"]),
                                     temperature=1.0, max_tokens=LAP_MAX_TOKENS, json_mode=False, probe=True)
        txt = raw.strip().lower()
        words = [w for w in re.findall(r"[a-z]+", txt) if w in ("higher", "lower", "unknown")]
        ans = words[-1] if words else ""   # last standalone occurrence (reasoning preambles precede the answer)
        if ans not in ("higher", "lower", "unknown"):
            ans = "invalid"
        return {"node_id": n["node_id"], "city": n["city"], "decision_date": n["decision_date"],
                "rep": k, "answer": ans, "raw": raw[-80:], "model_reported": mv}

    global client
    async with httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=concurrency + 2)) as client:
        rs = await asyncio.gather(*(one(*j) for j in jobs), return_exceptions=True)
    n_err = n_skip = 0
    with out_f.open("a") as f:
        for r in rs:
            if isinstance(r, Exception):
                n_err += 1; print("LAP_ERROR:", r, file=sys.stderr)
            elif r is None:
                n_skip += 1
            else:
                f.write(json.dumps(r) + "\n")
    print(f"st1 lap: {len(rs)-n_err-n_skip} ok, {n_err} err, {n_skip} skipped (budget)")


async def run_rec(nodes, concurrency, out_dir: Path, api_key: str) -> None:
    out_f = out_dir / "rec_results.jsonl"
    done = set()
    if out_f.exists():
        done = {json.loads(l)["node_id"] for l in out_f.read_text().splitlines() if l.strip()}
    jobs = [n for n in nodes if n["node_id"] not in done]
    print(f"st1 rec: {len(jobs)} calls")
    sem = asyncio.Semaphore(concurrency)

    async def one(n):
        snap = snapshot_block(n)
        assert not YEAR_RE.search(snap) and not CITY_RE.search(snap)
        async with sem:
            if over_budget():
                return None
            raw, mv = await call_llm(client, REC_SYSTEM, REC_PROMPT.format(snapshot=snap),
                                     temperature=0.0, max_tokens=REC_MAX_TOKENS, json_mode=False, probe=True)
        est_d = est_c = ""
        for m in re.finditer(r"\{[^{}]*\}", raw):      # last JSON object in the text
            try:
                j = json.loads(m.group(0))
                est_d, est_c = str(j.get("estimated_date", est_d)), str(j.get("estimated_city", est_c))
            except json.JSONDecodeError:
                continue
        return {"node_id": n["node_id"], "city": n["city"], "decision_date": n["decision_date"],
                "estimated_date": est_d, "estimated_city": est_c, "raw": raw[:200], "model_reported": mv}

    global client
    async with httpx.AsyncClient(timeout=300.0, limits=httpx.Limits(max_connections=concurrency + 2)) as client:
        rs = await asyncio.gather(*(one(n) for n in jobs), return_exceptions=True)
    n_err = n_skip = 0
    with out_f.open("a") as f:
        for r in rs:
            if isinstance(r, Exception):
                n_err += 1; print("REC_ERROR:", r, file=sys.stderr)
            elif r is None:
                n_skip += 1
            else:
                f.write(json.dumps(r) + "\n")
    print(f"st1 rec: {len(rs)-n_err-n_skip} ok, {n_err} err, {n_skip} skipped (budget)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=["dry", "smoke", "arms", "lap", "rec"], required=True)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--provider", default="gemini", choices=["gemini", "deepseek", "remote", "openai", "qwen", "kimi", "anthropic"])
    ap.add_argument("--model", default="models/gemini-2.5-flash")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--budget", type=float, default=None, help="stop launching new calls after N seconds")
    ap.add_argument("--probe-thinking", choices=["default", "off"], default="default")
    args = ap.parse_args()
    global PROVIDER, MODEL, ARM_MAX_TOKENS, LAP_MAX_TOKENS, REC_MAX_TOKENS, BUDGET, PROBE_THINKING
    BUDGET = args.budget
    PROBE_THINKING = args.probe_thinking
    PROVIDER, MODEL = args.provider, args.model
    if PROVIDER in REASONING_BUDGETS:
        ARM_MAX_TOKENS, LAP_MAX_TOKENS, REC_MAX_TOKENS = REASONING_BUDGETS[PROVIDER]
    kt1.MODEL = args.model
    tag = args.tag or args.model.split("/")[-1]
    out_dir = OUT_ROOT / tag
    nodes = load_panel()
    arms = tuple(a.strip() for a in args.arms.split(","))

    if args.job == "dry":
        for n in nodes[:args.n]:
            for a in arms:
                u = user_prompt(n, a)
                print(f"===== {n['node_id']} arm {a} ({len(SYSTEM)+len(u)} chars) =====")
                print(u.splitlines()[0])
        # full leak sweep over every node x arm, no API
        for n in nodes:
            for a in ARMS:
                user_prompt(n, a)
        print(f"leak sweep OK: {len(nodes)} nodes x {len(ARMS)} arms")
        print("--- full M-arm prompt of first node ---")
        print(user_prompt(nodes[0], "M"))
        print("--- LAP / REC prompts ---")
        print(LAP_PROMPT.format(city=REGIONS[nodes[0]['city']][3], t=nodes[0]['decision_date']))
        print(REC_PROMPT.format(snapshot=snapshot_block(nodes[0])))
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    api_key = (load_api_key() if PROVIDER == "gemini" else ANTHROPIC_KEY_FILE.read_text().strip()
               if PROVIDER == "anthropic" else load_key(PROVIDER))  # fail early if key missing
    (out_dir / "ROW_CONFIG.json").write_text(json.dumps({"provider": PROVIDER, "model": MODEL,
        "prereg": PREREG, "arm_temp": 0.2, "lap_temp": 1.0, "lap_reps": LAP_REPS,
        "arm_max_tokens": ARM_MAX_TOKENS, "probe_thinking": PROBE_THINKING,
        "probe_thinking_note": "off = LAP/REC sent with thinking disabled; arms keep the endpoint default regime. "
                               "Reason (2026-10-13): deepseek-v4-flash reasoning on LAP-ST truncates at 8192 in 63% of calls."},
        indent=2))
    if args.job == "smoke":
        sn = smoke_nodes(nodes)
        asyncio.run(run_arms(sn, ARMS, 5, out_dir / "smoke", api_key))
        asyncio.run(run_lap(sn, 2, out_dir / "smoke", api_key, reps=1))
        asyncio.run(run_rec(sn, 2, out_dir / "smoke", api_key))
        print("smoke done -> inspect outputs/st1/<tag>/smoke and run quote_st1.py")
    elif args.job == "arms":
        asyncio.run(run_arms(nodes, arms, args.concurrency, out_dir, api_key))
    elif args.job == "lap":
        asyncio.run(run_lap(nodes, args.concurrency, out_dir, api_key, reps=LAP_REPS))
    else:
        asyncio.run(run_rec(nodes, args.concurrency, out_dir, api_key))


if __name__ == "__main__":
    main()
