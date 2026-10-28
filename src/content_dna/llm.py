"""LLM access through LLM Foundry, with a disk cache, usage ledger and budget guard.

Token-saving rules applied everywhere:
- Requests are canonicalised (sorted keys) and cached on disk; a cache hit costs nothing.
- Claude: stable instructions go in a cached system block; per-video data comes after it.
- Gemini: static instruction text first, media + per-video text last (implicit prefix caching),
  thinking budget kept low for perception calls, low media resolution for long videos.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

BASE = "https://llmfoundry.straivedemo.com"
PROJECT = "content-dna"
CACHE_DIR = ROOT / "data" / "cache" / "llm"
LEDGER = ROOT / "results" / "usage.csv"

# USD per 1M tokens. Claude prices from Anthropic's published rates; Gemini figures are
# estimates (LLM Foundry does not publish prices) and are only used for the budget guard.
PRICES = {
    "claude-sonnet-5": {"in": 2.0, "out": 10.0, "cache_read": 0.20, "cache_write": 2.50},
    "claude-opus-5-5": {"in": 4.0, "out": 20.0, "cache_read": 0.40, "cache_write": 5.00},
    "claude-opus-4-8": {"in": 5.0, "out": 25.0, "cache_read": 0.50, "cache_write": 6.25},
    "gemini-3.5-flash": {"in": 0.50, "out": 3.0, "cache_read": 0.05, "cache_write": 0.50},
    "gemini-3.8-flash": {"in": 0.50, "out": 3.0, "cache_read": 0.05, "cache_write": 0.50},
    "whisper-1": {"per_min": 0.006},
}

BUDGET_USD = float(os.environ.get("DNA_BUDGET_USD", "10"))


class BudgetExceeded(RuntimeError):
    pass


_lock = threading.Lock()


def _token() -> str:
    tok = os.environ.get("API_KEY")
    if not tok:
        raise RuntimeError("API_KEY (LLM Foundry token) missing from .env")
    return f"{tok}:{PROJECT}"


def _key(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else json.dumps(p, sort_keys=True).encode())
    return h.hexdigest()


def _cache_get(key: str):
    p = CACHE_DIR / f"{key}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _cache_put(key: str, value) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(value))


def spent_usd() -> float:
    if not LEDGER.exists():
        return 0.0
    with LEDGER.open() as f:
        return sum(float(r["usd"]) for r in csv.DictReader(f))


def _record(stage: str, model: str, usage: dict, usd: float, video_id: str = "") -> None:
    with _lock:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        new = not LEDGER.exists()
        with LEDGER.open("a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["ts", "video_id", "stage", "model", "in", "out", "cache_read", "cache_write", "usd"])
            w.writerow([int(time.time()), video_id, stage, model, usage.get("in", 0), usage.get("out", 0),
                        usage.get("cache_read", 0), usage.get("cache_write", 0), f"{usd:.6f}"])


def _guard() -> None:
    if spent_usd() >= BUDGET_USD:
        raise BudgetExceeded(f"Estimated spend {spent_usd():.2f} >= budget {BUDGET_USD:.2f} USD")


def _cost(model: str, u: dict) -> float:
    p = PRICES.get(model, {"in": 5, "out": 25, "cache_read": 0.5, "cache_write": 6})
    return (u.get("in", 0) * p["in"] + u.get("out", 0) * p["out"] + u.get("cache_read", 0) * p["cache_read"]
            + u.get("cache_write", 0) * p["cache_write"]) / 1e6


# ---------------------------------------------------------------- Claude

_claude = None


def _claude_client() -> anthropic.Anthropic:
    global _claude
    if _claude is None:
        _claude = anthropic.Anthropic(api_key=_token(), base_url=f"{BASE}/anthropic/", max_retries=3, timeout=300)
    return _claude


def claude_json(system: str, content: list | str, schema: dict, *, model: str = "claude-sonnet-5",
                max_tokens: int = 8000, stage: str = "claude", video_id: str = "", use_cache: bool = True,
                effort: str | None = None) -> dict:
    """One Claude call returning JSON that matches `schema` (structured output).

    `system` must be stable across videos so the prompt cache is reused.
    """
    req = {"model": model, "max_tokens": max_tokens,
           "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
           "messages": [{"role": "user", "content": content}],
           "output_config": {"format": {"type": "json_schema", "schema": schema}}}
    if effort:
        req["output_config"]["effort"] = effort
    key = _key("claude", req)
    if use_cache and (hit := _cache_get(key)) is not None:
        return hit
    _guard()
    # Stream: long structured outputs over a proxy can stall as one blocking request.
    # use_cache=False must also bypass LLM Foundry's server-side response cache, or a "rerun" replays bytes.
    headers = {} if use_cache else {"Cache-Control": "no-cache"}
    with _claude_client().messages.stream(**req, extra_headers=headers) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"Claude refused: {msg.stop_details}")
    text = next(b.text for b in msg.content if b.type == "text")
    out = json.loads(text)
    u = msg.usage
    usage = {"in": u.input_tokens, "out": u.output_tokens, "cache_read": u.cache_read_input_tokens or 0,
             "cache_write": u.cache_creation_input_tokens or 0}
    _record(stage, model, usage, _cost(model, usage), video_id)
    _cache_put(key, out)
    return out


def image_block(path: Path, media_type: str = "image/jpeg") -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.standard_b64encode(path.read_bytes()).decode()}}


# ---------------------------------------------------------------- Gemini

def gemini_json(parts: list, schema: dict | None = None, *, model: str = "gemini-3.5-flash",
                thinking_budget: int = 256, media_resolution: str | None = None, stage: str = "gemini",
                video_id: str = "", use_cache: bool = True) -> dict:
    """generateContent with JSON output. Put static instructions first in `parts`, media last."""
    gen = {"responseMimeType": "application/json", "thinkingConfig": {"thinkingBudget": thinking_budget}}
    if schema:
        gen["responseJsonSchema"] = schema
    if media_resolution:
        gen["mediaResolution"] = media_resolution
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen}
    key = _key("gemini", model, body)
    if use_cache and (hit := _cache_get(key)) is not None:
        return hit
    _guard()
    for attempt in range(4):
        r = requests.post(f"{BASE}/gemini/v1beta/models/{model}:generateContent",
                          headers={"Authorization": f"Bearer {_token()}"}, json=body, timeout=600)
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
            time.sleep(5 * 2 ** attempt)
            continue
        break
    if r.status_code != 200:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:500]}")
    data = r.json()
    cand = data["candidates"][0]
    text = "".join(p.get("text", "") for p in cand["content"]["parts"] if not p.get("thought"))
    out = json.loads(text)
    um = data.get("usageMetadata", {})
    cached = um.get("cachedContentTokenCount", 0)
    usage = {"in": um.get("promptTokenCount", 0) - cached, "cache_read": cached,
             "out": um.get("candidatesTokenCount", 0) + um.get("thoughtsTokenCount", 0)}
    _record(stage, model, usage, _cost(model, usage), video_id)
    _cache_put(key, out)
    return out


# ---------------------------------------------------------------- Whisper

def whisper_words(audio_path: Path, *, stage: str = "whisper", video_id: str = "") -> dict:
    """Transcribe with word + segment timestamps (whisper-1 verbose_json). File must be <25 MB."""
    data = audio_path.read_bytes()
    key = _key("whisper", data)
    if (hit := _cache_get(key)) is not None:
        return hit
    _guard()
    r = requests.post(f"{BASE}/openai/v1/audio/transcriptions", headers={"Authorization": f"Bearer {_token()}"},
                      files={"file": (audio_path.name, data, "audio/mpeg")},
                      data={"model": "whisper-1", "response_format": "verbose_json",
                            "timestamp_granularities[]": ["word", "segment"]}, timeout=600)
    if r.status_code != 200:
        raise RuntimeError(f"Whisper {r.status_code}: {r.text[:300]}")
    out = r.json()
    minutes = float(out.get("duration", 0)) / 60
    _record(stage, "whisper-1", {}, minutes * PRICES["whisper-1"]["per_min"], video_id)
    _cache_put(key, out)
    return out
