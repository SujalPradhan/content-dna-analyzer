"""Daily quota for paid analyses (new videos and critiques), decided when a job is admitted so a run never stops halfway.

A job is admitted only if today's count is under DNA_DAILY_VIDEOS and today's spend plus what running jobs may still
spend plus this job's worst-case estimate (DNA_EST_RUN_USD) fits DNA_DAILY_BUDGET_USD (and the overall DNA_BUDGET_USD).
Once admitted it runs to the end; its real cost is settled afterwards, and a job that failed before spending anything
is refunded. State lives in a GCS object when DNA_STATE_BUCKET is set (Cloud Run scales to zero and loses its disk),
otherwise in data/quota.json.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "data" / "quota.json"
BUCKET = os.environ.get("DNA_STATE_BUCKET")
OBJECT = "quota.json"
DAILY_VIDEOS = int(os.environ.get("DNA_DAILY_VIDEOS", "0"))  # 0 = no daily count limit
DAILY_BUDGET_USD = float(os.environ.get("DNA_DAILY_BUDGET_USD", "0"))  # 0 = no daily spend limit
TOTAL_BUDGET_USD = float(os.environ.get("DNA_BUDGET_USD", "10"))
EST_RUN_USD = float(os.environ.get("DNA_EST_RUN_USD", "0.20"))  # worst case for one ≤15 min video incl. critique (~$0.17)

_lock = threading.Lock()
EPS = 1e-9  # dollar sums like 1.0 - 0.8 are not exact in floating point


class QuotaExceeded(RuntimeError):
    pass


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _token() -> str:
    r = requests.get("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
                     headers={"Metadata-Flavor": "Google"}, timeout=5)
    r.raise_for_status()
    return r.json()["access_token"]


def _load() -> tuple[dict, int]:
    """State and its GCS generation (0 = no object yet) for a conditional write."""
    if not BUCKET:
        return (json.loads(LOCAL.read_text()) if LOCAL.exists() else {}), 0
    r = requests.get(f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{OBJECT}", params={"alt": "media"},
                     headers={"Authorization": f"Bearer {_token()}"}, timeout=10)
    if r.status_code == 404:
        return {}, 0
    r.raise_for_status()
    return r.json(), int(r.headers.get("x-goog-generation", "0"))


def _save(state: dict, generation: int) -> bool:
    if not BUCKET:
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(json.dumps(state))
        return True
    r = requests.post(f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o",
                      params={"uploadType": "media", "name": OBJECT, "ifGenerationMatch": generation},
                      headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
                      data=json.dumps(state), timeout=10)
    if r.status_code == 412:  # someone else wrote first: reload and retry
        return False
    r.raise_for_status()
    return True


def _update(fn):
    with _lock:
        for _ in range(5):
            state, gen = _load()
            out = fn(state)
            if _save(state, gen):
                return out
        raise RuntimeError("quota state is busy; try again")


def _day(state: dict) -> dict:
    days = state.setdefault("days", {})
    for k in [k for k in days if k < time.strftime("%Y-%m-%d", time.gmtime(time.time() - 14 * 86400))]:
        del days[k]  # keep two weeks
    return days.setdefault(_today(), {"videos": 0, "usd": 0.0, "reserved": 0.0})


def admit() -> str:
    """Reserve one paid run for today, or raise QuotaExceeded with a message for the visitor. Returns the day key."""
    def fn(state):
        d = _day(state)
        if DAILY_VIDEOS and d["videos"] >= DAILY_VIDEOS:
            raise QuotaExceeded(f"Today's {DAILY_VIDEOS} free video analyses are used up. The demos still work; try again tomorrow.")
        if DAILY_BUDGET_USD and d["usd"] + d["reserved"] + EST_RUN_USD > DAILY_BUDGET_USD + EPS:
            raise QuotaExceeded("Today's analysis budget is used up. The demos still work; try again tomorrow.")
        if state.get("total_usd", 0.0) + d["reserved"] + EST_RUN_USD > TOTAL_BUDGET_USD + EPS:
            raise QuotaExceeded("The demo's overall analysis budget is used up. The demos still work.")
        d["videos"] += 1
        d["reserved"] = round(d["reserved"] + EST_RUN_USD, 6)
        return _today()
    return _update(fn)


def settle(day: str, usd: float, refund: bool = False) -> None:
    """Replace a run's reservation with what it actually cost; refund the slot if it failed before spending."""
    def fn(state):
        d = state.setdefault("days", {}).setdefault(day, {"videos": 0, "usd": 0.0, "reserved": 0.0})
        d["reserved"] = round(max(0.0, d["reserved"] - EST_RUN_USD), 6)
        d["usd"] = round(d["usd"] + usd, 6)
        state["total_usd"] = round(state.get("total_usd", 0.0) + usd, 6)
        if refund:
            d["videos"] = max(0, d["videos"] - 1)
    _update(fn)


def status() -> dict:
    try:
        state, _ = _load()
    except Exception:
        return {"videos_left_today": None}
    d = state.get("days", {}).get(_today(), {"videos": 0, "usd": 0.0, "reserved": 0.0})
    left = DAILY_VIDEOS - d["videos"] if DAILY_VIDEOS else None
    if DAILY_BUDGET_USD:  # a slot only counts if the budget can also cover it
        by_budget = int((max(0.0, DAILY_BUDGET_USD - d["usd"] - d["reserved"]) + EPS) // EST_RUN_USD)
        left = by_budget if left is None else min(left, by_budget)
    return {"videos_left_today": max(0, left) if left is not None else None, "daily_videos": DAILY_VIDEOS or None}
