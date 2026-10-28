"""Semantic visual timeline from Gemini (video understanding). Timestamps here are approximate (~±1 s);
cut timing always comes from visual.py, never from this stage."""
from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

from . import llm

FORMATS = ["talking_head", "b_roll", "screen_recording", "product_closeup", "graphics_text", "gameplay",
           "performance_music", "slides", "animation", "interview_multi_person", "other"]

SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {"type": "array", "items": {"type": "object", "properties": {
            "start": {"type": "string", "description": "timestamp as MM:SS.s from video start"}, "end": {"type": "string", "description": "timestamp as MM:SS.s from video start"},
            "format": {"type": "string", "enum": FORMATS},
            "face_visible": {"type": "boolean"},
            "on_screen_text": {"type": "string", "description": "verbatim overlay text, '' if none"},
            "description": {"type": "string"}},
            "required": ["start", "end", "format", "face_visible", "on_screen_text", "description"]}},
        "hook": {"type": "object", "properties": {
            "opening_visual": {"type": "string"},
            "opening_line": {"type": "string"},
            "hook_type": {"type": "string", "enum": ["question", "bold_claim", "preview_of_payoff", "story_cold_open",
                                                       "problem_statement", "greeting_intro", "brand_logo", "action_visual", "other"]},
            "text_overlay_first_3s": {"type": "boolean"},
            "notes": {"type": "string"}},
            "required": ["opening_visual", "opening_line", "hook_type", "text_overlay_first_3s", "notes"]},
        "overall": {"type": "object", "properties": {
            "production_style": {"type": "string", "enum": ["studio", "home_selfshot", "outdoor_vlog", "cinematic",
                                                              "screencast", "animated", "mixed"]},
            "music_presence": {"type": "string", "enum": ["none", "background", "prominent"]},
            "branding_visible": {"type": "boolean"},
            "cta_moments": {"type": "array", "items": {"type": "object", "properties": {
                "t": {"type": "string", "description": "timestamp as MM:SS.s from video start"}, "kind": {"type": "string", "enum": ["subscribe_like", "link_product", "comment",
                                                                                 "watch_next", "purchase", "other"]},
                "text": {"type": "string"}}, "required": ["t", "kind", "text"]}}},
            "required": ["production_style", "music_presence", "branding_visible", "cta_moments"]},
    },
    "required": ["segments", "hook", "overall"],
}

# Static instruction text goes first so Gemini's implicit prefix cache can reuse it across videos.
INSTRUCTIONS = """You are annotating a video for a creative-structure analysis tool. Watch the entire video (visuals and audio).
Return JSON matching the schema:
- segments: a contiguous timeline covering the whole video, split whenever the dominant visual FORMAT changes.
  Merge consecutive shots of the same format; each segment >= 3 s unless the video is very short; at most 45 segments.
  All times are strings in MM:SS.s format measured from the start of the video (e.g. 01:05.5 = 65.5 s). on_screen_text: verbatim overlay/caption text (shorten to 80 chars), '' if none.
- hook: describe ONLY the first ~5 seconds. opening_line = the first spoken words verbatim ('' if none).
- overall.cta_moments: every explicit call to action (subscribe, like, link, buy, comment, watch next) with time.
Be literal and observational; do not judge quality. If unsure, choose 'other' rather than guessing."""


def _parse_ts(v) -> float:
    """'MM:SS.s' or 'H:MM:SS' -> seconds."""
    parts = [float(x) for x in str(v).strip().split(":")]
    sec = 0.0
    for x in parts:
        sec = sec * 60 + x
    return sec


def normalise(raw: dict, dur: float, offset: float = 0.0) -> dict:
    """Convert string timestamps to *_s seconds relative to the excerpt, clamp to the runtime and flag
    implausible timelines. `offset`: source time of the excerpt start, if the model reported source times."""
    out = json.loads(json.dumps(raw))
    for s in out["segments"]:
        s["start_s"], s["end_s"] = _parse_ts(s.pop("start")), _parse_ts(s.pop("end"))
        if offset and s["start_s"] >= offset - 1:
            s["start_s"], s["end_s"] = max(0.0, s["start_s"] - offset), max(0.0, s["end_s"] - offset)
    for c in out["overall"]["cta_moments"]:
        c["t_s"] = _parse_ts(c.pop("t"))
        if offset and c["t_s"] >= offset - 1:
            c["t_s"] -= offset
    max_t = max([s["end_s"] for s in out["segments"]] + [c["t_s"] for c in out["overall"]["cta_moments"]] + [0])
    out["timeline_overrun_ratio"] = round(max_t / dur, 3) if dur else None
    for s in out["segments"]:
        s["start_s"], s["end_s"] = min(s["start_s"], dur), min(s["end_s"], dur)
    out["segments"] = [s for s in out["segments"] if s["end_s"] > s["start_s"]]
    out["overall"]["cta_moments"] = [c for c in out["overall"]["cta_moments"] if c["t_s"] <= dur + 1]
    return out


def _local_proxy(video: Path, workdir: Path) -> Path:
    proxy = workdir / "proxy_1fps.mp4"
    if not proxy.exists():
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-vf", "fps=1,scale=-2:240",
                        "-c:v", "libx264", "-crf", "32", "-c:a", "aac", "-b:a", "32k", "-ac", "1", str(proxy)], check=True)
    return proxy


def analyse(src, workdir: Path) -> dict:
    cache = workdir / "perception.json"
    if cache.exists():
        return json.loads(cache.read_text())
    dur = src.meta.get("analysed_duration") or 0
    fps = 1.0 if dur <= 600 else 0.5
    if src.youtube_url:
        off = float(src.meta.get("start_offset") or 0)
        vm = {"fps": fps, "end_offset": f"{int(off + dur)}s"}
        if off:
            vm["start_offset"] = f"{int(off)}s"  # timestamps come back relative to the source; shifted below
        media = {"file_data": {"file_uri": src.youtube_url, "mime_type": "video/*"}, "video_metadata": vm}
    else:
        proxy = _local_proxy(src.video_path, workdir)
        media = {"inline_data": {"mime_type": "video/mp4", "data": base64.b64encode(proxy.read_bytes()).decode()},
                 "video_metadata": {"fps": fps}}
    out = llm.gemini_json([{"text": INSTRUCTIONS}, media, {"text": f"Video duration: {dur:.1f} s."}], SCHEMA,
                          media_resolution="MEDIA_RESOLUTION_LOW", thinking_budget=512, stage="perception",
                          video_id=src.video_id)
    off = float(src.meta.get("start_offset") or 0) if src.youtube_url else 0.0
    out = normalise(out, dur, off)
    cache.write_text(json.dumps(out))
    return out
