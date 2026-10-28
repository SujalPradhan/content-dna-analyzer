"""Genre inference for videos submitted without one: nearest centroid on standardised fingerprint features,
fitted on the analysed corpus. Free (no API call) and honest about its accuracy (leave-one-out, see evaluate())."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FEATURES = ["duration_s", "shots_per_min", "median_shot_s", "wpm", "speech_coverage", "nonspeech_audio_share",
            "time_to_first_word_s", "talking_head_share", "broll_share", "screen_share", "face_share",
            "text_overlay_share", "cta_count", "motion_mean"]
LOG = {"duration_s", "shots_per_min", "median_shot_s"}
GENRES = ["ad", "cooking", "explainer", "shorts", "tech_review", "vlog"]


def _vec(fp: dict) -> np.ndarray:
    out = []
    for f in FEATURES:
        v = fp.get(f)
        v = float("nan") if v is None else float(v)
        out.append(math.log1p(max(v, 0)) if f in LOG and v == v else v)
    return np.array(out)


def _corpus(exclude: str | None = None):
    from .pipeline import load_all_features
    X, y = [], []
    for f in load_all_features():
        if f["category"] in GENRES and f["video_id"] != exclude:
            X.append(_vec(f["fingerprint"]))
            y.append(f["category"])
    return np.array(X), np.array(y)


def _fit(X, y):
    med = np.nanmedian(X, axis=0)
    X = np.where(np.isnan(X), med, X)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd
    cents = {g: Z[y == g].mean(0) for g in GENRES if (y == g).any()}
    return med, mu, sd, cents


def predict(fp: dict, is_short: bool | None = None, exclude: str | None = None) -> dict:
    """Return {genre, confidence, scores, method}. Vertical videos <= 60 s are 'shorts' by platform format."""
    if is_short:
        return {"genre": "shorts", "confidence": 1.0, "method": "rule: vertical video <= 60 s", "scores": {}}
    X, y = _corpus(exclude)
    if len(X) < 6:
        return {"genre": "uncategorised", "confidence": 0.0, "method": "corpus too small", "scores": {}}
    med, mu, sd, cents = _fit(X, y)
    v = _vec(fp)
    v = np.where(np.isnan(v), med, v)
    z = (v - mu) / sd
    d = {g: float(np.linalg.norm(z - c)) for g, c in cents.items()}
    w = {g: math.exp(-dist) for g, dist in d.items()}
    tot = sum(w.values())
    scores = {g: round(x / tot, 3) for g, x in sorted(w.items(), key=lambda kv: -kv[1])}
    best = next(iter(scores))
    return {"genre": best, "confidence": scores[best], "method": "nearest centroid over corpus fingerprints",
            "scores": scores}


def evaluate() -> dict:
    """Leave-one-out accuracy of predict() on the corpus (Shorts rule excluded so the classifier is tested)."""
    from .pipeline import load_all_features
    rows = []
    for f in load_all_features():
        if f["category"] not in GENRES:
            continue
        r = predict(f["fingerprint"], is_short=False, exclude=f["video_id"])
        rows.append({"video_id": f["video_id"], "true": f["category"], "pred": r["genre"], "conf": r["confidence"]})
    acc = sum(r["true"] == r["pred"] for r in rows) / len(rows)
    per = {g: round(sum(1 for r in rows if r["true"] == g and r["pred"] == g) / max(1, sum(r["true"] == g for r in rows)), 2)
           for g in GENRES}
    return {"n": len(rows), "loo_accuracy": round(acc, 3), "chance": round(1 / len(GENRES), 3), "per_genre_recall": per,
            "rows": rows}
