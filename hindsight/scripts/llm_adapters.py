#!/usr/bin/env python
"""Async adapters for OpenAI-compatible chat endpoints (BM-1 protocol)."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import httpx

from hindsight_paths import REPO

PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "key_file": REPO / "DeepSeek_API_KEY.env",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "key_file": REPO / "Kimi_API_KEY.env",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_file": REPO / "Qwen_API_KEY.env",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "key_file": REPO / "OpenAI_API_KEY.env",
    },
    # local OpenAI-compatible servers (keyless)
    "lmstudio": {"base_url": "http://localhost:1234/v1", "key_file": None},
    "ollama": {"base_url": "http://localhost:11434/v1", "key_file": None},
    # cloud GPU vLLM: Mac side via SSH tunnel (localhost:8001), server side direct
    # (export REMOTE_VLLM_URL=http://localhost:8000/v1) — env wins, copies stay identical
    "remote": {"base_url": os.environ.get("REMOTE_VLLM_URL", "http://localhost:8001/v1"),
               "key_file": None},
}

MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0


def load_key(provider: str) -> str:
    kf = PROVIDERS[provider]["key_file"]
    if kf is None:
        return "local-no-key"
    for line in kf.read_text().splitlines():
        if "=" in line:
            v = line.split("=", 1)[1].strip()
            if v:
                return v
    raise RuntimeError(f"no key in {kf}")


def strip_fences(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    # if prose surrounds a JSON array, decode-scan every '[' until one parses
    # (reasoning-style models emit untagged thinking text that may itself
    #  contain brackets, so a greedy first-[..last-] regex is not enough)
    if not t.lstrip().startswith(("[", "{")):
        dec = json.JSONDecoder()
        cands: list = []
        i = 0
        while i < len(t):
            if t[i] in "[{":
                try:
                    obj, end = dec.raw_decode(t, i)
                except json.JSONDecodeError:
                    i += 1
                    continue
                if isinstance(obj, (list, dict)):
                    cands.append(obj)
                i = end  # skip past parsed structure (avoids re-parsing nested)
            else:
                i += 1
        # prefer the longest list-of-dicts (sketch arrays), then any dict, then any list
        dict_lists = [c for c in cands if isinstance(c, list) and c and all(isinstance(x, dict) for x in c)]
        if dict_lists:
            return json.dumps(max(dict_lists, key=len))
        dicts = [c for c in cands if isinstance(c, dict)]
        if dicts:
            return json.dumps(dicts[-1])
        if cands:
            return json.dumps(max(cands, key=lambda c: len(json.dumps(c))))
        m = re.search(r"\[.*\]", t, re.S)
        if m:
            t = m.group(0)
    return t


async def call_openai_compat(
    client: httpx.AsyncClient,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool = True,
) -> tuple[str, str]:
    """Returns (text, reported_model). Retries on 429/5xx/timeouts."""
    url = PROVIDERS[provider]["base_url"] + "/chat/completions"
    headers = {"Authorization": f"Bearer {load_key(provider)}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # OpenAI reasoning models (gpt-5*/o*): no custom temperature (provider-default,
    # disclosed deviation like sonnet-5) and max_completion_tokens replaces max_tokens
    if provider == "openai" and (model.startswith("gpt-5") or model.startswith("o")):
        payload.pop("temperature")
        payload["max_completion_tokens"] = payload.pop("max_tokens")
    # kimi-k2.x rejects any temperature except 1 ("only 1 is allowed for this model")
    if provider == "kimi" and model.startswith("kimi-k2"):
        payload.pop("temperature")
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    delay = RETRY_BASE_DELAY
    last: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
            r.raise_for_status()
            d = r.json()
            choice = d["choices"][0]
            txt = choice["message"]["content"] or ""
            # length-truncation MUST precede other checks and never retry:
            # reasoning models re-bill the whole thought budget on identical retries
            if choice.get("finish_reason") == "length":
                _log_openai_usage(provider, d)
                raise RuntimeError(f"{provider}/{model}: truncated (finish_reason=length), not retrying")
            if not txt.strip():
                # empty content on HTTP 200 = thinking already billed (reasoning
                # models); retrying re-bills the full budget — log usage, give up
                _log_openai_usage(provider, d)
                raise RuntimeError(f"{provider}/{model}: empty content on 200 "
                                   f"(finish_reason={choice.get('finish_reason')}), not retrying")
            _log_openai_usage(provider, d)
            return txt.strip(), d.get("model", model)
        except (httpx.HTTPStatusError, httpx.TimeoutException, ValueError, KeyError) as exc:
            last = exc
            if attempt < MAX_RETRIES:
                await asyncio.sleep(delay)
                delay *= 2
    raise RuntimeError(f"{provider}/{model} failed after {MAX_RETRIES+1} attempts: {last}")


USAGE_LOG_OAI = REPO / "hindsight/outputs/openai_compat_usage_log.jsonl"


def _log_openai_usage(provider: str, d: dict) -> None:
    """Exact per-call usage from the API response; accounting must never break a run."""
    try:
        import datetime as _dt
        u = d.get("usage", {}) or {}
        det = u.get("completion_tokens_details", {}) or {}
        with USAGE_LOG_OAI.open("a") as f:
            f.write(json.dumps({
                "ts": _dt.datetime.now().isoformat(timespec="seconds"),
                "provider": provider,
                "model": d.get("model", "unknown"),
                "prompt": u.get("prompt_tokens", 0),
                "completion": u.get("completion_tokens", 0),
                "reasoning": det.get("reasoning_tokens", 0),
            }) + "\n")
    except Exception:
        pass
