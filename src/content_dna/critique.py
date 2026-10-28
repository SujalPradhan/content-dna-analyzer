"""Narrative structure + evidence-cited critique (Claude), and a validator that checks every cited piece
of evidence against the measured data and snaps timestamps to measured events."""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from . import llm
from .fingerprint import FIELDS

ROLES = ["hook", "intro_setup", "context", "main_content", "demonstration", "payoff_reveal", "recap", "cta",
         "sponsor_ad_read", "outro"]


def _strict(schema):
    """Claude structured outputs require additionalProperties:false on every object."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            schema["required"] = list(schema["properties"])
        for v in schema.values():
            _strict(v)
    elif isinstance(schema, list):
        for v in schema:
            _strict(v)
    return schema


EVIDENCE = {"type": "object", "properties": {
    "kind": {"type": "string", "enum": ["metric", "quote", "visual"]},
    "ref": {"type": "string", "description": "metric: fingerprint field name or 'bin:<start>' ; quote: '' ; visual: perception segment start time"},
    "value": {"type": "string", "description": "metric: the number exactly as given; quote: verbatim transcript words; visual: what is seen"}}}

SCHEMA = _strict({"type": "object", "properties": {
    "summary": {"type": "string"},
    "dna_tags": {"type": "array", "items": {"type": "string"}},
    "structure": {"type": "array", "items": {"type": "object", "properties": {
        "start_s": {"type": "number"}, "end_s": {"type": "number"},
        "role": {"type": "string", "enum": ROLES}, "label": {"type": "string"}}}},
    "hook": {"type": "object", "properties": {
        "what_happens": {"type": "string"}, "promise": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}}}},
    "devices": {"type": "array", "items": {"type": "object", "properties": {
        "name": {"type": "string"}, "t_s": {"type": "number"}, "quote": {"type": "string"}}}},
    "strengths": {"type": "array", "items": {"type": "object", "properties": {
        "t_s": {"type": "number"}, "point": {"type": "string"}, "evidence": {"type": "array", "items": EVIDENCE}}}},
    "recommendations": {"type": "array", "items": {"type": "object", "properties": {
        "title": {"type": "string"},
        "t_start_s": {"type": "number"}, "t_end_s": {"type": "number"},
        "observation": {"type": "string"},
        "evidence": {"type": "array", "items": EVIDENCE},
        "recommendation": {"type": "string"},
        "basis": {"type": "string", "enum": ["measured_outlier_vs_corpus", "internal_inconsistency", "craft_heuristic"]},
        "priority": {"type": "string", "enum": ["high", "medium", "low"]}}}},
}})


def system_prompt(benchmarks: dict | None) -> str:
    """Stable across every video in a run -> cached once, read cheaply afterwards."""
    fields = "\n".join(f"- {k}: {lbl} ({unit}) [{grp}]" for k, (grp, lbl, unit) in FIELDS.items())
    bench = json.dumps(benchmarks, sort_keys=True) if benchmarks else "(no corpus benchmarks available)"
    return f"""You are Content DNA Analyzer, a video creative-structure analyst for creators, media teams and advertisers.
You receive MEASURED data about one video (deterministic signal processing + a word-timestamped transcript + an approximate
visual-format timeline from a vision model) and a few frames from its opening. Explain how the video is constructed and
what could be improved.

Hard rules:
1. Ground every strength and recommendation in evidence from the provided data. Each evidence item must be one of:
   - metric: ref = an exact fingerprint field name (or 'bin:<start>' for a timeline-bin row), value = the number exactly as given.
   - quote: value = words copied verbatim from the transcript (5-25 words), placed at the time you cite.
   - visual: ref = start time of the perception segment, value = what that segment / frame shows.
   Never invent numbers, quotes or events. If the data does not support a point, do not make it.
2. Timestamps: cite the moment the issue occurs, in seconds, using times present in the data.
3. Never claim or imply a change will increase views, retention, revenue or virality. You may say what a craft
   heuristic suggests and frame it as something to test. Label each recommendation's basis honestly:
   measured_outlier_vs_corpus (value is extreme relative to the benchmarks below), internal_inconsistency (the video
   contradicts itself, e.g. promises X and delivers late), or craft_heuristic (editing/storytelling convention).
4. Respect the genre: a slow, calm cooking video is not wrong for being slow. Compare against the same category when possible.
5. Be specific and actionable (what to cut, move, add, at which timestamp). 3-6 recommendations, 2-4 strengths,
   structure segments covering the full runtime, 3-6 dna_tags (short phrases like 'rapid-cut listicle').
6. summary: 2-3 sentences describing the video's construction, not its topic.

Fingerprint fields:
{fields}

Corpus benchmarks (per category and overall; p25/p50/p75 of each fingerprint field across the analysed corpus):
{bench}
"""


def _fmt_segments(segs, limit_chars=24000):
    lines = [f"[{s['s']:.1f}-{s['e']:.1f}] {s['text']}" for s in segs]
    out, n = [], 0
    for ln in lines:
        n += len(ln)
        if n > limit_chars:
            out.append("[... transcript truncated for length ...]")
            break
        out.append(ln)
    return "\n".join(out)


def build_user_content(src, fp: dict, bins: list, aud: dict, per: dict, category: str, percentiles: dict | None):
    meta = src.meta
    head = {"title": meta.get("title"), "channel": meta.get("channel"), "category": category,
            "analysed_duration_s": fp["duration_s"], "is_short": bool(meta.get("is_short")),
            "chapters": [{"t": c.get("start_time"), "title": c.get("title")} for c in (meta.get("chapters") or [])][:30]}
    fp_view = {k: {"value": (None if isinstance(v, float) and v != v else v), **({"pct_in_category": percentiles.get(k)} if percentiles and k in percentiles else {})}
               for k, v in fp.items()}
    per_view = {"segments": [{k: s[k] for k in ("start_s", "end_s", "format", "face_visible", "on_screen_text")}
                             for s in per.get("segments", [])],
                "hook": per.get("hook"), "overall": per.get("overall")}
    text = (f"VIDEO\n{json.dumps(head)}\n\nFINGERPRINT (value, and percentile within its category where available)\n"
            f"{json.dumps(fp_view)}\n\nTIMELINE BINS (cuts, words/min, loudness dB, motion per bin)\n{json.dumps(bins)}\n\n"
            f"VISUAL FORMAT TIMELINE (vision model, times approximate ±1s)\n{json.dumps(per_view)}\n\n"
            f"TRANSCRIPT (segment timestamps from whisper)\n{_fmt_segments(aud['transcript']['segments'])}\n\n"
            "The images are frames from the first 15 seconds, in order (filename = timestamp).")
    images = []
    for p in sorted((src.workdir / "hook").glob("hook_*.jpg")):
        images += [{"type": "text", "text": p.name}, llm.image_block(p)]
    return images + [{"type": "text", "text": text}]


# ---------------------------------------------------------------- validation / grounding

def _norm(s: str) -> list[str]:
    """Whitespace tokens, lower-cased, punctuation/symbols stripped. Keeps combining marks (Devanagari, Tamil...)."""
    out = []
    for tok in s.split():
        t = "".join(c for c in tok.lower() if not unicodedata.category(c).startswith(("P", "S")))
        if t:
            out.append(t)
    return out


def _quote_match(quote: str, words: list[dict], t0: float, t1: float, slack: float = 12.0):
    """Best fuzzy match of quote within the transcript window [t0-slack, t1+slack]. Returns (score, time)."""
    q = _norm(quote)
    if not q:
        return 0.0, None
    win = [w for w in words if t0 - slack <= w["s"] <= t1 + slack]
    toks = [(_norm(w["w"]) or [""])[0] for w in win]
    best, best_t = 0.0, None
    n = len(q)
    for i in range(max(1, len(toks) - n + 1)):
        cand = toks[i:i + n]
        r = SequenceMatcher(None, q, cand).ratio()
        if r > best:
            best, best_t = r, win[i]["s"] if i < len(win) else None
    return best, best_t


def _num(s: str):
    try:
        return float(str(s).replace("%", "").replace("s", "").replace(",", "").split()[0])
    except (ValueError, IndexError):
        return None


def validate(result: dict, fp: dict, bins: list, aud: dict, per: dict, vis: dict) -> dict:
    dur = fp["duration_s"]
    words = aud["transcript"]["words"]
    events = sorted({0.0, *[s for s, _ in vis["shots"]], *[w["s"] for w in words]})
    ev = np.array(events)
    bin_by_start = {f"bin:{b['start']:g}": b for b in bins}
    seg_starts = [s["start_s"] for s in per.get("segments", [])]
    checks = []

    def check(item_list, t0, t1, owner):
        for e in item_list:
            kind, ref, val = e["kind"], e["ref"], e["value"]
            ok, note = False, ""
            if kind == "metric":
                v = _num(val)
                if ref in fp and v is not None and fp[ref] == fp[ref]:
                    actual = float(fp[ref])
                    ok = abs(actual - v) <= max(0.05 * abs(actual), 0.02)
                    note = f"actual={actual}"
                elif ref.startswith("bin:"):
                    rb = _num(ref[4:])
                    b = bin_by_start.get(ref) or (bin_by_start.get(f"bin:{rb:g}") if rb is not None else None)
                    close = lambda x, y: x is not None and abs(float(x) - y) <= max(0.05 * abs(float(x)), 0.02)
                    pairs = re.findall(r"(cuts|wpm|loud_db|loudness|motion)[\s:=]{0,3}(-?\d+(?:\.\d+)?)", str(val))
                    if b and pairs:  # every labelled number must match its own bin field
                        ok = all(close(b["loud_db" if k == "loudness" else k], float(x)) for k, x in pairs)
                        note = f"bin={b}"
                    elif b and v is not None:  # a bare number must match one of the bin's fields
                        ok = any(close(x, v) for x in (b["cuts"], b["wpm"], b["loud_db"], b["motion"]))
                        note = f"bin={b}"
                    else:
                        note = "unknown bin" if not b else "unparseable value"
                else:
                    note = "unknown metric"
            elif kind == "quote":
                frags = [f for f in re.split(r"\.\.\.|…", val) if len(_norm(f)) >= 2] or [val]
                res = [_quote_match(f, words, t0, t1) for f in frags]
                score = min(r[0] for r in res)
                ok = score >= 0.8
                note = f"match={score:.2f} at {res[0][1]}" + (f" ({len(frags)} fragments)" if len(frags) > 1 else "")
            elif kind == "visual":
                rv = _num(ref)
                ok, note = False, "no segment at ref"
                if rv is not None and -1 <= rv <= dur + 1:
                    if any(abs(rv - s) <= 2.0 for s in seg_starts):
                        ok, note = True, "segment starts at ref"
                    else:
                        cover = [s for s in per.get("segments", []) if s["start_s"] - 1 <= rv <= s["end_s"] + 1]
                        claim = {w for w in _norm(val) if len(w) > 3}
                        seen = set(_norm(" ".join(s["description"] + " " + s["on_screen_text"] for s in cover)))
                        if claim and len(claim & seen) / len(claim) >= 0.5:
                            ok, note = True, "covering segment describes it"
            checks.append({"owner": owner, "kind": kind, "ref": ref, "value": val, "verified": bool(ok), "note": note})

    for i, r in enumerate(result.get("recommendations", [])):
        t0, t1 = float(r["t_start_s"]), float(r["t_end_s"])
        in_range = -0.5 <= t0 <= dur + 0.5
        snap = float(ev[np.abs(ev - t0).argmin()]) if len(ev) else t0
        r["t_snapped_s"] = round(snap, 2) if abs(snap - t0) <= 1.5 else round(t0, 2)
        r["t_in_range"] = in_range
        check(r["evidence"], t0, max(t0, t1), f"rec{i}")
    for i, s in enumerate(result.get("strengths", [])):
        check(s["evidence"], float(s["t_s"]), float(s["t_s"]), f"str{i}")

    n = len(checks)
    v = sum(c["verified"] for c in checks)
    recs = result.get("recommendations", [])
    rec_ok = sum(1 for i, r in enumerate(recs)
                 if r["t_in_range"] and any(c["verified"] for c in checks if c["owner"] == f"rec{i}"))
    return {"evidence_items": n, "evidence_verified": v, "evidence_rate": round(v / n, 3) if n else None,
            "recs": len(recs), "recs_grounded": rec_ok, "rec_grounded_rate": round(rec_ok / len(recs), 3) if recs else None,
            "by_kind": {k: [sum(c["verified"] for c in checks if c["kind"] == k), sum(c["kind"] == k for c in checks)]
                        for k in ("metric", "quote", "visual")},
            "checks": checks}


def analyse(src, fp, bins, aud, per, vis, category, benchmarks=None, percentiles=None, model="claude-sonnet-5",
            use_cache=True) -> dict:
    content = build_user_content(src, fp, bins, aud, per, category, percentiles)
    result = llm.claude_json(system_prompt(benchmarks), content, SCHEMA, model=model, max_tokens=12000,
                             effort="medium", stage="critique", video_id=src.video_id, use_cache=use_cache)
    result["grounding"] = validate(result, fp, bins, aud, per, vis)
    return result
