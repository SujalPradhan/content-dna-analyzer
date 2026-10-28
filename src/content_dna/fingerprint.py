"""Turn raw signals into a compact, interpretable creative fingerprint (one flat dict per video).

Every field is measured (deterministic) unless its name ends in a perception-derived share, which comes
from Gemini's segment timeline and is therefore approximate.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np

HOOK_S = 15.0

# Field -> (group, human label, unit). Order defines the fingerprint vector.
FIELDS = {
    "duration_s": ("shape", "Duration", "s"),
    "shots_per_min": ("pacing", "Cuts per minute", "/min"),
    "median_shot_s": ("pacing", "Median shot length", "s"),
    "shot_len_cv": ("pacing", "Shot-length variability (CV)", ""),
    "pacing_trend": ("pacing", "Pacing trend (2nd half vs 1st half cut rate)", "ratio"),
    "hook_cuts": ("hook", f"Cuts in first {HOOK_S:.0f}s", "count"),
    "time_to_first_word_s": ("hook", "Time to first spoken word", "s"),
    "hook_wpm": ("hook", f"Words/min in first {HOOK_S:.0f}s", "wpm"),
    "hook_text_overlay": ("hook", "On-screen text in first 3s", "bool"),
    "hook_motion": ("hook", f"Motion in first {HOOK_S:.0f}s vs video avg", "ratio"),
    "wpm": ("speech", "Speaking rate", "wpm"),
    "speech_coverage": ("speech", "Share of runtime with speech", "share"),
    "long_pauses_per_min": ("speech", "Pauses >1.5s per minute", "/min"),
    "questions_per_min": ("speech", "Questions asked per minute", "/min"),
    "you_rate": ("speech", "'you/your' per 100 words", "per100"),
    "loudness_db": ("audio", "Mean loudness", "dBFS"),
    "loudness_range_db": ("audio", "Loudness range (p95-p5)", "dB"),
    "energy_slope": ("audio", "Energy trend over runtime", "dB/runtime"),
    "nonspeech_audio_share": ("audio", "Sound without speech (music/SFX proxy)", "share"),
    "motion_mean": ("visual", "Mean frame-to-frame motion", "0-1"),
    "brightness_mean": ("visual", "Mean brightness", "0-1"),
    "colorfulness_mean": ("visual", "Colourfulness (Hasler-Süsstrunk)", ""),
    "talking_head_share": ("format", "Talking-head share", "share"),
    "broll_share": ("format", "B-roll / product share", "share"),
    "screen_share": ("format", "Screen / slides / graphics share", "share"),
    "face_share": ("format", "Face-on-screen share", "share"),
    "text_overlay_share": ("format", "Runtime with on-screen text", "share"),
    "format_switches_per_min": ("format", "Visual format switches per minute", "/min"),
    "cta_count": ("structure", "Explicit calls to action", "count"),
    "first_cta_pos": ("structure", "First CTA position", "share of runtime"),
}


def spoken_words(aud: dict) -> list[dict]:
    """Whisper words minus symbol-only tokens (e.g. '♪' for sung lyrics/music), which are not speech."""
    return [w for w in aud["transcript"]["words"] if any(unicodedata.category(c)[0] in "LN" for c in w["w"])]


def _share(segments, dur, pred) -> float:
    if not segments or not dur:
        return float("nan")
    tot = sum(max(0.0, min(s["end_s"], dur) - max(0.0, s["start_s"])) for s in segments if pred(s))
    return round(min(1.0, tot / dur), 3)


def compute(meta: dict, vis: dict, aud: dict, per: dict | None) -> dict:
    dur = float(meta.get("analysed_duration") or aud["loudness"]["duration"])
    mins = dur / 60
    shots = vis["shots"]
    lens = np.array([e - s for s, e in shots]) if shots else np.array([dur])
    cuts = [s for s, _ in shots[1:]]
    half = dur / 2
    c1, c2 = sum(c < half for c in cuts), sum(c >= half for c in cuts)

    words = spoken_words(aud)
    n_words = len(words)
    text = aud["transcript"]["text"] or ""
    hook_words = [w for w in words if w["s"] < HOOK_S]

    # speech coverage: union of word spans, with <0.6 s gaps bridged
    covered, pauses, last_end = 0.0, 0, None
    for w in words:
        if last_end is not None:
            gap = w["s"] - last_end
            if gap > 1.5:
                pauses += 1
            if gap < 0.6:
                covered += max(0.0, gap)
        covered += max(0.0, w["e"] - w["s"])
        last_end = w["e"]
    speech_cov = min(1.0, covered / dur) if dur else 0.0

    L = aud["loudness"]
    db = np.array(L["db"])
    t = np.array(L["t"])
    active = db > -45
    # non-speech audio: active-audio bins that contain no spoken word
    speech_mask = np.zeros(len(t), bool)
    for w in words:
        speech_mask[(t >= w["s"] - 0.25) & (t <= w["e"] + 0.25)] = True
    nonspeech = float((active & ~speech_mask).sum() / max(1, len(t)))
    slope = float(np.polyfit(t / max(dur, 1e-6), db, 1)[0]) if len(t) > 3 and active.any() else float("nan")

    C = vis["curves"]
    mot = np.array(C["motion"])
    ct = np.array(C["t"])
    hook_mot = mot[ct < HOOK_S].mean() / mot.mean() if mot.size and mot.mean() > 0 else float("nan")

    segs = (per or {}).get("segments") or []
    hook = (per or {}).get("hook") or {}
    ctas = sorted(((per or {}).get("overall") or {}).get("cta_moments") or [], key=lambda c: c["t_s"])
    switches = sum(1 for a, b in zip(segs, segs[1:]) if a["format"] != b["format"])

    fp = {
        "duration_s": round(dur, 1),
        "shots_per_min": round(len(cuts) / mins, 2) if mins else 0,
        "median_shot_s": round(float(np.median(lens)), 2),
        "shot_len_cv": round(float(lens.std() / lens.mean()), 2) if lens.mean() else 0,
        "pacing_trend": round((c2 + 1) / (c1 + 1), 2),
        "hook_cuts": sum(c < HOOK_S for c in cuts),
        "time_to_first_word_s": round(words[0]["s"], 2) if words else float("nan"),
        "hook_wpm": round(len(hook_words) / (min(HOOK_S, dur) / 60), 1) if dur else 0,
        "hook_text_overlay": float(bool(hook.get("text_overlay_first_3s"))) if per else float("nan"),
        "hook_motion": round(float(hook_mot), 2),
        "wpm": round(n_words / mins, 1) if mins else 0,
        "speech_coverage": round(speech_cov, 3),
        "long_pauses_per_min": round(pauses / mins, 2) if mins else 0,
        "questions_per_min": round(text.count("?") / mins, 2) if mins else 0,
        "you_rate": round(100 * len(re.findall(r"\byou(?:r|'re|rs)?\b", text, re.I)) / max(1, n_words), 2),
        "loudness_db": round(float(db[active].mean()), 1) if active.any() else float("nan"),
        "loudness_range_db": round(float(np.percentile(db[active], 95) - np.percentile(db[active], 5)), 1) if active.any() else float("nan"),
        "energy_slope": round(slope, 2),
        "nonspeech_audio_share": round(nonspeech, 3),
        "motion_mean": round(float(mot.mean()), 4) if mot.size else float("nan"),
        "brightness_mean": round(float(np.mean(C["brightness"])), 3),
        "colorfulness_mean": round(float(np.mean(C["colorfulness"])), 1),
        "talking_head_share": _share(segs, dur, lambda s: s["format"] in ("talking_head", "interview_multi_person")),
        "broll_share": _share(segs, dur, lambda s: s["format"] in ("b_roll", "product_closeup")),
        "screen_share": _share(segs, dur, lambda s: s["format"] in ("screen_recording", "slides", "graphics_text", "animation")),
        "face_share": _share(segs, dur, lambda s: s["face_visible"]),
        "text_overlay_share": _share(segs, dur, lambda s: bool(s["on_screen_text"].strip())),
        "format_switches_per_min": round(switches / mins, 2) if mins and per else float("nan"),
        "cta_count": len(ctas) if per else float("nan"),
        "first_cta_pos": round(ctas[0]["t_s"] / dur, 3) if ctas and dur else float("nan"),
    }
    return {k: fp[k] for k in FIELDS}


def timeline_bins(vis: dict, aud: dict, dur: float, bin_s: float) -> list[dict]:
    """Compact per-bin table (cuts, words, loudness, motion) — what the critique model sees instead of raw curves."""
    n = max(1, int(np.ceil(dur / bin_s)))
    cuts = np.array([s for s, _ in vis["shots"][1:]])
    words = np.array([w["s"] for w in spoken_words(aud)])
    lt, ldb = np.array(aud["loudness"]["t"]), np.array(aud["loudness"]["db"])
    ct, mot = np.array(vis["curves"]["t"]), np.array(vis["curves"]["motion"])
    rows = []
    for i in range(n):
        a, b = i * bin_s, min(dur, (i + 1) * bin_s)
        m_l = (lt >= a) & (lt < b)
        m_c = (ct >= a) & (ct < b)
        rows.append({"start": round(a, 1), "end": round(b, 1),
                     "cuts": int(((cuts >= a) & (cuts < b)).sum()) if cuts.size else 0,
                     "wpm": round(((words >= a) & (words < b)).sum() / ((b - a) / 60), 0) if b > a else 0,
                     "loud_db": round(float(ldb[m_l].mean()), 1) if m_l.any() else None,
                     "motion": round(float(mot[m_c].mean()), 3) if m_c.any() else None})
    return rows
