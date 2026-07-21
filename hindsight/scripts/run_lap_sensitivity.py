#!/usr/bin/env python
"""BM-1c LAP sensitivity runner (prereg: BM1c_lap_sensitivity_addendum.md, frozen 2026-07-21).

Three arms per model, prompt wording identical to the frozen LAP probe
(LAP_PROMPT/LAP_SYSTEM imported from run_fm1c, never retyped):
  ext   t=1.0 (frozen regime), reps 20-39 -> lap_ext_t1.0_reps20-39.jsonl
  t0.3  t=0.3, reps 0-19                  -> lap_t0.3_probe.jsonl
  t0.7  t=0.7, reps 0-19                  -> lap_t0.7_probe.jsonl

Data isolation (addendum s2, hard): outputs/bench/** is READ-ONLY here — the
frozen lap_probe_results.jsonl files are opened only to derive each model's
258-date universe. All new lines go to outputs/review/lap_sensitivity_runs/.

Ops discipline (addendum s3, frozen, inherited from llm_batch_ops):
  - ledger-first: usage jsonl appended BEFORE any classification of the response
    (openai_compat_usage_log.jsonl via llm_adapters._log_openai_usage;
     anthropic_usage_log.jsonl in the existing {ts,model,input,output,tag} shape)
  - finish_reason=length -> terminal (answer "invalid"), never retried
  - empty content on 200 -> terminal (answer "invalid"), never retried
  - retryable only 429/5xx/timeout/transport, exponential backoff (2s base, x2)
  - non-429 4xx -> fatal, no retry, no output line; 3 consecutive fatals with
    zero successes trips a per-(model,arm) circuit breaker (loud, never silent)
  - idempotent resume: done-set scanned per (model, arm, date, rep)
  - cumulative hard cap $10 across the whole study (cost_accum.json persists)

Frozen per-model regimes (copied from the BM-1 invocations that produced the
frozen lap_probe_results.jsonl; thinking/reasoning regime pinned identically):
  gpt-5.4-mini      openai batch body(): NO temperature key (reasoning model,
                    provider default), max_completion_tokens=4096, json_mode
                    off, regex-last-word parse   [run_bench_openai_batch.py]
  claude-haiku-4-5  anthropic batch/direct params(): temperature=1.0,
                    max_tokens=2048, no thinking block, first-word parse
                                                 [run_bench_anthropic_batch.py]
  deepseek-v4-flash run_bench_model --job probes: temperature=1.0,
                    max_tokens=8192, json_mode off, regex-last-word parse

Temperature arms deviation note (explicit, not silent): the frozen gpt-5.4-mini
invocation never sent a temperature key, and llm_adapters.call_openai_compat
silently POPS temperature for gpt-5* — reusing it verbatim would fabricate the
gpt temperature arms. This runner therefore owns the HTTP call (mirroring the
adapter's retry/ledger discipline) and sends the literal temperature on the
t0.3/t0.7 arms for all models; if the API rejects it (4xx), the circuit breaker
records the arm as infeasible and the gate/report discloses it.

Usage (macrochain env only):
  conda run -n macrochain python run_lap_sensitivity.py --smoke   # 132-call gate
  conda run -n macrochain python run_lap_sensitivity.py --full
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
from run_fm1c import LAP_PROMPT, LAP_SYSTEM, trading_day_end  # frozen wording, by import
from llm_adapters import PROVIDERS, load_key, _log_openai_usage, USAGE_LOG_OAI

import anthropic

from hindsight_paths import REPO

BENCH = REPO / "hindsight/outputs/bench"  # READ-ONLY (frozen); never written here
OUT = REPO / "hindsight/outputs/review/lap_sensitivity_runs"
ANTHROPIC_KEY_FILE = REPO / "Anthropic_API_KEY.env"
ANTHROPIC_USAGE_LOG = REPO / "hindsight/outputs/anthropic_usage_log.jsonl"
PRICE_TABLE = REPO / "hindsight/outputs/price_table.json"
COST_ACCUM = OUT / "cost_accum.json"
PREREG = "BM1c_lap_sensitivity_addendum.md"

HARD_CAP_USD = 10.0
GATE_USD = 7.0
CALLS_PER_ARM = 258 * 20          # 5,160
ARMS_PER_MODEL = 3
SMOKE_DATES = ("2008-10-15", "2014-04-15")  # same pair as run_bench_model --smoke
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0
LEDGER_TAG = "lap_sens"

MODELS = {
    "gpt-5.4-mini": dict(kind="oai", provider="openai", frozen_temp=None,
                         max_tokens=4096, tok_field="max_completion_tokens",
                         parse="regex_last"),
    "claude-haiku-4-5": dict(kind="anthropic", frozen_temp=1.0,
                             max_tokens=2048, parse="first_word"),
    "deepseek-v4-flash": dict(kind="oai", provider="deepseek", frozen_temp=1.0,
                              max_tokens=8192, tok_field="max_tokens",
                              parse="regex_last"),
}

# (arm_key, filename, nominal_temp, explicit_temp?, reps)
# ext arm: explicit_temp=False -> send the model's FROZEN temperature config
#          (haiku/deepseek: temperature=1.0 explicit, exactly as frozen;
#           gpt-5.4-mini: key omitted = provider default, exactly as frozen)
ARMS = [
    ("ext",  "lap_ext_t1.0_reps20-39.jsonl", 1.0, False, tuple(range(20, 40))),
    ("t0.3", "lap_t0.3_probe.jsonl",         0.3, True,  tuple(range(0, 20))),
    ("t0.7", "lap_t0.7_probe.jsonl",         0.7, True,  tuple(range(0, 20))),
]

WORD_RE = re.compile(r"\b(up|down|unknown)\b")


class FatalCallError(Exception):
    """Non-retryable API rejection (4xx != 429): unbilled, no output line."""


def parse_answer(text: str, mode: str) -> str:
    if mode == "regex_last":  # frozen gpt/deepseek materializers
        words = WORD_RE.findall(text.lower())
        return words[-1] if words else "invalid"
    ans = text.strip().lower().split()[0].strip('."\'') if text.strip() else ""
    return ans if ans in ("up", "down", "unknown") else "invalid"


def frozen_dates(model: str) -> list[str]:
    """258-date universe = decision_date set of the model's frozen LAP file (read-only)."""
    f = BENCH / model / "lap_probe_results.jsonl"
    ds = {json.loads(l)["decision_date"] for l in f.read_text().splitlines() if l.strip()}
    if len(ds) != 258:
        raise RuntimeError(f"{model}: frozen LAP universe has {len(ds)} dates, expected 258")
    return sorted(ds)


def anthropic_key() -> str:
    for line in ANTHROPIC_KEY_FILE.read_text().splitlines():
        if "=" in line and line.split("=", 1)[1].strip():
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"no key in {ANTHROPIC_KEY_FILE}")


def log_anthropic_usage(model: str, usage) -> None:
    """Same shape as run_bench_anthropic_direct.log_usage + tag (gd2 precedent)."""
    try:
        with ANTHROPIC_USAGE_LOG.open("a") as f:
            f.write(json.dumps({
                "ts": dt.datetime.now().isoformat(timespec="seconds"),
                "model": model,
                "input": usage.input_tokens,
                "output": usage.output_tokens,
                "tag": LEDGER_TAG,
            }) + "\n")
    except Exception:
        pass  # accounting must never break a run (adapter convention)


# ---------------------------------------------------------------- cost cap ---

PRICES = json.loads(PRICE_TABLE.read_text())


def call_cost(model: str, tok_in: int, tok_out: int) -> float:
    p = PRICES[model]
    return (tok_in * p["in"] + tok_out * p["out"]) / 1e6


class CostMeter:
    def __init__(self) -> None:
        self.spent = 0.0
        if COST_ACCUM.exists():
            self.spent = json.loads(COST_ACCUM.read_text()).get("spent_usd", 0.0)
        self.tripped = False

    def add(self, usd: float) -> None:
        self.spent += usd
        COST_ACCUM.write_text(json.dumps({
            "spent_usd": round(self.spent, 6), "hard_cap_usd": HARD_CAP_USD,
            "updated": dt.datetime.now().isoformat(timespec="seconds")}))
        if self.spent > HARD_CAP_USD:
            self.tripped = True


METER = CostMeter()
ABORT = False  # set when the hard cap trips; all pending jobs short-circuit


# ------------------------------------------------------------------- calls ---

async def call_oai(client: httpx.AsyncClient, provider: str, model: str,
                   temp: float | None, tok_field: str, max_tokens: int,
                   user: str) -> tuple[str, str, int, int]:
    """Returns (status, text, tok_in, tok_out); status OK|TRUNC|EMPTY.

    Mirrors llm_adapters.call_openai_compat exactly EXCEPT: temperature is
    passed through literally (never popped) and non-429 4xx is fatal-no-retry.
    Ledger-first: _log_openai_usage runs before length/empty classification.
    """
    url = PROVIDERS[provider]["base_url"] + "/chat/completions"
    headers = {"Authorization": f"Bearer {load_key(provider)}"}
    payload: dict = {
        "model": model,
        "messages": [{"role": "system", "content": LAP_SYSTEM},
                     {"role": "user", "content": user}],
        tok_field: max_tokens,
    }
    if temp is not None:
        payload["temperature"] = temp
    delay = RETRY_BASE_DELAY
    last: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
            if r.status_code >= 400:  # unbilled rejection: fatal, never retried
                raise FatalCallError(f"HTTP {r.status_code}: {r.text[:300]}")
            d = r.json()
            choice = d["choices"][0]
            txt = (choice["message"]["content"] or "").strip()
            u = d.get("usage", {}) or {}
            _log_openai_usage(provider, d)  # ledger BEFORE classification (frozen s3)
            if choice.get("finish_reason") == "length":
                return "TRUNC", txt, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
            if not txt:
                return "EMPTY", txt, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
            return "OK", txt, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.TransportError,
                ValueError, KeyError) as exc:
            last = exc
            if attempt < MAX_RETRIES:
                await asyncio.sleep(delay)
                delay *= 2
    raise RuntimeError(f"{provider}/{model} failed after {MAX_RETRIES+1} attempts: {last}")


async def call_anthropic(client: anthropic.AsyncAnthropic, model: str,
                         temp: float, max_tokens: int,
                         user: str) -> tuple[str, str, int, int]:
    """SDK max_retries handles 429/5xx/timeout backoff (frozen direct-runner
    config); 400 raises BadRequestError -> FatalCallError. Ledger-first."""
    try:
        msg = await client.messages.create(
            model=model, max_tokens=max_tokens, system=LAP_SYSTEM,
            messages=[{"role": "user", "content": user}], temperature=temp)
    except anthropic.BadRequestError as exc:
        raise FatalCallError(str(exc)[:300]) from exc
    log_anthropic_usage(model, msg.usage)  # ledger BEFORE classification (frozen s3)
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if msg.stop_reason == "max_tokens":
        return "TRUNC", text, msg.usage.input_tokens, msg.usage.output_tokens
    if not text:
        return "EMPTY", text, msg.usage.input_tokens, msg.usage.output_tokens
    return "OK", text, msg.usage.input_tokens, msg.usage.output_tokens


# --------------------------------------------------------------- run logic ---

def scan_done(path: Path) -> set[tuple[str, int]]:
    done: set[tuple[str, int]] = set()
    if path.exists():
        for l in path.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done.add((r["decision_date"], r["rep"]))
    return done


async def run_model(model: str, cfg: dict, ends: dict[str, str], dates: list[str],
                    concurrency: int, smoke: bool, oai_client, ant_client,
                    dead_arms: set[tuple[str, str]]) -> dict:
    global ABORT
    mdir = OUT / model
    mdir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(concurrency)
    wlock = asyncio.Lock()
    counts = {"OK": 0, "TRUNC": 0, "EMPTY": 0, "ERR": 0, "FATAL": 0, "SKIP": 0, "ABORT": 0}
    fatal_streak: dict[str, int] = {}
    arm_success: dict[str, int] = {}
    outs = {}
    jobs: list[tuple[str, str, int]] = []
    for arm, fname, _nom, _exp, reps in ARMS:
        f = mdir / fname
        done = scan_done(f)
        counts["SKIP"] += sum(1 for t in (SMOKE_DATES if smoke else dates)
                              for k in (reps[:1] if smoke and arm != "ext" else reps)
                              if (t, k) in done)
        for t in (SMOKE_DATES if smoke else dates):
            # smoke = 2 dates x [ext all 20 reps + 1 rep per temperature arm]
            # = 44 calls/model, 132 total (addendum s3 "~132")
            for k in (reps[:1] if smoke and arm != "ext" else reps):
                if (t, k) not in done:
                    jobs.append((arm, t, k))
        outs[arm] = f.open("a")
    arm_cfg = {a: (nom, exp) for a, _f, nom, exp, _r in ARMS}
    files = {a: mdir / fn for a, fn, *_ in ARMS}
    written = 0
    print(f"{model}: {len(jobs)} calls to run ({counts['SKIP']} already done)", flush=True)

    async def one(arm: str, t: str, k: int) -> str:
        global ABORT
        nominal, explicit = arm_cfg[arm]
        async with sem:
            if ABORT:
                return "ABORT"
            if (model, arm) in dead_arms:
                return "FATAL"
            user = LAP_PROMPT.format(t=t, t_end=ends[t])
            temp = nominal if explicit else cfg["frozen_temp"]
            try:
                if cfg["kind"] == "oai":
                    status, text, ti, to = await call_oai(
                        oai_client, cfg["provider"], model, temp,
                        cfg["tok_field"], cfg["max_tokens"], user)
                else:
                    status, text, ti, to = await call_anthropic(
                        ant_client, model, temp, cfg["max_tokens"], user)
            except FatalCallError as exc:
                fatal_streak[arm] = fatal_streak.get(arm, 0) + 1
                if fatal_streak[arm] >= 3 and arm_success.get(arm, 0) == 0:
                    dead_arms.add((model, arm))
                    print(f"CIRCUIT_BREAKER {model}/{arm}: 3 consecutive fatal "
                          f"rejections, zero successes — arm marked infeasible. "
                          f"Last error: {exc}", file=sys.stderr, flush=True)
                else:
                    print(f"FATAL {model}/{arm}/{t}/rep{k}: {exc}",
                          file=sys.stderr, flush=True)
                return "FATAL"
            except Exception as exc:
                print(f"ERR {model}/{arm}/{t}/rep{k}: {exc}", file=sys.stderr, flush=True)
                return "ERR"
        fatal_streak[arm] = 0
        arm_success[arm] = arm_success.get(arm, 0) + 1
        METER.add(call_cost(model, ti, to))
        if METER.tripped and not ABORT:
            ABORT = True
            print(f"HARD_CAP: cumulative study spend ${METER.spent:.4f} > "
                  f"${HARD_CAP_USD} — aborting all pending calls (addendum s1)",
                  file=sys.stderr, flush=True)
        # TRUNC/EMPTY are terminal per s3 (recorded, never retried): the line is
        # written with answer "invalid" so resume cannot re-burn the call.
        ans = parse_answer(text, cfg["parse"]) if status == "OK" else "invalid"
        line = {"decision_date": t, "rep": k, "answer": ans,
                "raw": text[-60:], "temp": nominal}
        nonlocal written
        async with wlock:
            outs[arm].write(json.dumps(line) + "\n")
            outs[arm].flush()
            written += 1
            if written % 100 == 0:
                print(f"{model}: {written} written this run, "
                      f"${METER.spent:.4f} cumulative", flush=True)
        return status

    rs = await asyncio.gather(*(one(a, t, k) for a, t, k in jobs), return_exceptions=True)
    for r in rs:
        if isinstance(r, Exception):
            counts["ERR"] += 1
            print(f"CELL_ERROR {model}: {r}", file=sys.stderr, flush=True)
        else:
            counts[r] = counts.get(r, 0) + 1
    for f in outs.values():
        f.close()
    lines = {a: sum(1 for l in files[a].read_text().splitlines() if l.strip())
             if files[a].exists() else 0 for a in files}
    print(f"{model} done: {counts} | file lines: {lines}", flush=True)
    return counts


# -------------------------------------------------------------- smoke gate ---

def gate_report(start_iso: str, dead_arms: set[tuple[str, str]]) -> None:
    stats: dict[str, list] = {m: [0, 0, 0] for m in MODELS}  # n, tok_in, tok_out
    if USAGE_LOG_OAI.exists():
        for l in USAGE_LOG_OAI.read_text().splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            if r.get("ts", "") < start_iso:
                continue
            if r.get("provider") == "openai" and str(r.get("model", "")).startswith("gpt-5.4-mini"):
                key = "gpt-5.4-mini"
            elif r.get("provider") == "deepseek" and "deepseek" in str(r.get("model", "")):
                key = "deepseek-v4-flash"
            else:
                continue
            stats[key][0] += 1
            stats[key][1] += r.get("prompt", 0)
            stats[key][2] += r.get("completion", 0)
    if ANTHROPIC_USAGE_LOG.exists():
        for l in ANTHROPIC_USAGE_LOG.read_text().splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            if (r.get("ts", "") >= start_iso and r.get("tag") == LEDGER_TAG
                    and r.get("model") == "claude-haiku-4-5"):
                stats["claude-haiku-4-5"][0] += 1
                stats["claude-haiku-4-5"][1] += r.get("input", 0)
                stats["claude-haiku-4-5"][2] += r.get("output", 0)
    report: dict = {"prereg": PREREG, "run_start": start_iso, "per_model": {},
                    "dead_arms": sorted(f"{m}/{a}" for m, a in dead_arms)}
    total = 0.0
    print("\n===== SMOKE GATE (ledger-measured, frozen price_table.json rates) =====",
          flush=True)
    for m in MODELS:
        n, ti, to = stats[m]
        if n == 0:
            print(f"{m}: NO LEDGER ROWS — cannot extrapolate; gate FAILS OPEN "
                  f"TO STOP", flush=True)
            report["per_model"][m] = {"ledger_rows": 0}
            total = float("inf")
            continue
        mean_cost = call_cost(m, ti / n, to / n)
        feasible_arms = ARMS_PER_MODEL - sum(1 for mm, _a in dead_arms if mm == m)
        feasible_calls = CALLS_PER_ARM * feasible_arms
        ext_cost = mean_cost * feasible_calls
        total += ext_cost
        print(f"{m}: rows={n} mean_in={ti/n:.1f} mean_out={to/n:.1f} "
              f"cost/call=${mean_cost*1e3:.4f}e-3 feasible_calls={feasible_calls} "
              f"-> extrapolated ${ext_cost:.3f}", flush=True)
        report["per_model"][m] = {
            "ledger_rows": n, "mean_tok_in": round(ti / n, 1),
            "mean_tok_out": round(to / n, 1),
            "mean_cost_per_call_usd": round(mean_cost, 8),
            "feasible_calls": feasible_calls,
            "extrapolated_usd": round(ext_cost, 4)}
    decision = "PROCEED" if total <= GATE_USD else "STOP"
    print(f"TOTAL extrapolated: ${total:.3f} vs gate ${GATE_USD} "
          f"(frozen quote ~$3.60) -> GATE: {decision}", flush=True)
    report["total_extrapolated_usd"] = (round(total, 4)
                                        if total != float("inf") else None)
    report["gate_usd"] = GATE_USD
    report["decision"] = decision
    (OUT / "smoke_gate_report.json").write_text(json.dumps(report, indent=2))


# -------------------------------------------------------------------- main ---

async def amain(args) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    start_iso = dt.datetime.now().isoformat(timespec="seconds")
    print(f"run_lap_sensitivity start={start_iso} mode="
          f"{'smoke' if args.smoke else 'full'} prereg={PREREG} "
          f"spent_so_far=${METER.spent:.4f}", flush=True)
    per_model_dates = {m: frozen_dates(m) for m in MODELS}
    universe = sorted(set().union(*per_model_dates.values()))
    for m, ds in per_model_dates.items():
        if ds != universe:
            raise RuntimeError(f"{m}: frozen date universe differs from union")
    print(f"date universe: {len(universe)} dates; computing trading-day ends "
          f"(frozen trading_day_end)...", flush=True)
    ends = {t: trading_day_end(t) for t in universe}
    dead_arms: set[tuple[str, str]] = set()
    limits = httpx.Limits(max_connections=args.concurrency * 2 + 4,
                          max_keepalive_connections=args.concurrency * 2)
    # 600s: probes-runner precedent (client-side abort still bills the server)
    async with httpx.AsyncClient(timeout=600.0, limits=limits) as oai_client:
        ant_client = anthropic.AsyncAnthropic(api_key=anthropic_key(), max_retries=8)
        await asyncio.gather(*(
            run_model(m, cfg, ends, per_model_dates[m], args.concurrency,
                      args.smoke, oai_client, ant_client, dead_arms)
            for m, cfg in MODELS.items()))
        await ant_client.close()
    print(f"cumulative study spend: ${METER.spent:.4f} (hard cap ${HARD_CAP_USD})",
          flush=True)
    if dead_arms:
        print(f"INFEASIBLE ARMS: {sorted(dead_arms)}", flush=True)
    if args.smoke:
        gate_report(start_iso, dead_arms)
    if ABORT:
        print("RUN ABORTED BY HARD CAP", flush=True)
        sys.exit(2)


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true",
                   help="2 dates x 3 models x [ext 20 reps + 1 rep/temp arm] = 132 calls + gate")
    g.add_argument("--full", action="store_true")
    ap.add_argument("--concurrency", type=int, default=10,
                    help="per-provider worker cap (addendum: modest, 8-12)")
    args = ap.parse_args()
    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
