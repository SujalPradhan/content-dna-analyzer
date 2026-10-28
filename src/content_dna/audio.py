"""Audio signals: loudness curve and pause structure (librosa) + word-timestamped transcript (whisper-1)."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import librosa
import numpy as np

from . import llm

HOP_S = 0.5


def loudness(audio: Path) -> dict:
    y, sr = librosa.load(str(audio), sr=16000, mono=True)
    hop = int(sr * HOP_S)
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop, center=True)[0]
    db = librosa.amplitude_to_db(rms, ref=1.0)
    flat = librosa.feature.spectral_flatness(y=y, n_fft=2048, hop_length=hop)[0]
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    n = min(len(db), len(flat), len(onset))
    try:
        tempo = float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=sr)[0])[0])
    except Exception:
        tempo = float("nan")
    return {"t": [round(i * HOP_S, 2) for i in range(n)], "db": [round(float(v), 2) for v in db[:n]],
            "flatness": [round(float(v), 4) for v in flat[:n]], "onset": [round(float(v), 3) for v in onset[:n]],
            "tempo_bpm": tempo, "duration": len(y) / sr}


# Scripts a transcript may legitimately use, by Whisper's detected language (romanised text is common everywhere).
SCRIPTS = {"hindi": {"DEVANAGARI"}, "marathi": {"DEVANAGARI"}, "nepali": {"DEVANAGARI"}, "tamil": {"TAMIL"},
           "bengali": {"BENGALI"}, "telugu": {"TELUGU"}, "kannada": {"KANNADA"}, "malayalam": {"MALAYALAM"},
           "gujarati": {"GUJARATI"}, "punjabi": {"GURMUKHI"}, "urdu": {"ARABIC"}, "arabic": {"ARABIC"},
           "russian": {"CYRILLIC"}, "ukrainian": {"CYRILLIC"}, "georgian": {"GEORGIAN"}, "japanese": {"CJK", "HIRAGANA", "KATAKANA"},
           "chinese": {"CJK"}, "korean": {"HANGUL"}, "greek": {"GREEK"}, "hebrew": {"HEBREW"}, "thai": {"THAI"}}
STOCK = re.compile(r"^\W*(thank(s| you) (so much )?for watching|please subscribe|subscribe to (my|the) channel|"
                   r"see you (in the )?next (time|video)|bye)\W*$", re.I)


def transcript_quality(text: str, language: str | None, whole: bool = True) -> tuple[str, str]:
    """('ok'|'rejected', reason). Whisper invents speech on music/silence: wrong-script gibberish, or a lone stock
    phrase as the *entire* transcript (whole=True; a real outro inside a longer transcript is kept)."""
    letters = Counter(unicodedata.name(c, "?").split()[0] for c in text if c.isalpha())
    total = sum(letters.values())
    if not total:
        return "ok", ""
    allowed = {"LATIN"} | SCRIPTS.get((language or "").lower(), set())
    foreign = sum(n for sc, n in letters.items() if sc not in allowed)
    if foreign / total > 0.3:
        return "rejected", f"{foreign / total:.0%} of letters are in a script ({letters.most_common(1)[0][0].title()}) inconsistent with the detected language ({language})"
    if whole and len(text.split()) <= 8 and STOCK.match(text.strip()):
        return "rejected", f"only a stock phrase Whisper is known to emit on non-speech audio: {text.strip()!r}"
    return "ok", ""


def transcript(audio: Path, video_id: str) -> dict:
    """whisper-1 verbose_json; files over ~24 MB are split into chunks and re-timed."""
    size_mb = audio.stat().st_size / 1e6
    if size_mb < 24:
        out = llm.whisper_words(audio, video_id=video_id)
        lang = out.get("language")
        status, reason = transcript_quality(out.get("text", ""), lang)
        if status == "rejected":  # keep the raw output for inspection, analyse the video as having no speech
            return {"text": "", "language": lang, "words": [], "segments": [], "quality": status,
                    "quality_reason": reason, "rejected_text": out.get("text", "")[:2000]}
        # Segment level: drop passages Whisper invented on music (wrong-script gibberish) and the words inside them.
        keep, dropped = [], []
        for sg in out.get("segments", []):
            (keep if transcript_quality(sg["text"], lang, whole=False)[0] == "ok" else dropped).append(sg)
        inside = lambda w: any(d["start"] - 0.05 <= w["start"] <= d["end"] + 0.05 for d in dropped)
        res = {"text": " ".join(sg["text"].strip() for sg in keep), "language": lang,
               "quality": "partial" if dropped else "ok",
               "words": [{"w": w["word"], "s": round(w["start"], 2), "e": round(w["end"], 2)}
                         for w in out.get("words", []) if not inside(w)],
               "segments": [{"s": round(sg["start"], 2), "e": round(sg["end"], 2), "text": sg["text"].strip()} for sg in keep]}
        if dropped:
            res["quality_reason"] = f"dropped {len(dropped)} segment(s) in a script inconsistent with the detected language ({lang})"
            res["rejected_text"] = " ".join(d["text"].strip() for d in dropped)[:2000]
        return res
    raise RuntimeError(f"audio too large for single whisper call ({size_mb:.1f} MB); shorten analysis window")


def analyse(audio: Path, workdir: Path, video_id: str) -> dict:
    cache = workdir / "audio.json"
    if cache.exists():
        return json.loads(cache.read_text())
    out = {"loudness": loudness(audio), "transcript": transcript(audio, video_id)}
    cache.write_text(json.dumps(out))
    return out


def refresh_transcripts() -> list[tuple[str, str]]:
    """Re-derive every saved transcript from the cached Whisper response with the quality check (no API cost)."""
    changed = []
    for p in sorted((Path(__file__).resolve().parents[2] / "data" / "videos").glob("*/audio.json")):
        a = json.loads(p.read_text())
        mp3 = p.parent / "audio.mp3"
        if not mp3.exists():
            continue
        new = transcript(mp3, p.parent.name)
        if new.get("quality") != a["transcript"].get("quality") or len(new["words"]) != len(a["transcript"]["words"]):
            changed.append((p.parent.name, new.get("quality_reason") or "ok"))
        a["transcript"] = new
        p.write_text(json.dumps(a))
    return changed
