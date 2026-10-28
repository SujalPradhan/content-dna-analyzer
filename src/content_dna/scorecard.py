"""Scorecard: the researched retention/reach parameters (data/parameters.json) evaluated on one analysed video.

Each parameter gets
  checks  - its rules applied to the measured fingerprint (sourced threshold, heuristic threshold, or the target
            genre's corpus p25-p75 when no source gives a number)
  flags   - timestamped pain points from timeline detectors (one per flag kind in the catalogue we can detect)
  status  - good / watch / problem / unmeasured
Nothing here predicts performance: thresholds are sourced guidance or heuristics, and the corpus ranges describe how
~6 videos per genre are made, not what works.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from . import ingest

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "data" / "parameters.json"
BENCH = ROOT / "results" / "benchmarks.json"
GENRES = ["ad", "cooking", "explainer", "shorts", "tech_review", "vlog"]
SHORT_FORM = {"shorts", "ad"}
QUIET_DB = -45.0
PROMISE_WORDS = {"you'll", "today", "going", "gonna", "how", "why", "what", "show", "learn", "find", "best", "secret",
                 "never", "stop", "need", "must", "watch", "here's", "let's", "minute", "minutes", "ways", "tips"}


def catalogue() -> dict:
    return json.loads(CATALOGUE.read_text())


def _j(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def _applies(rule_or_list, genre: str) -> bool:
    a = rule_or_list if isinstance(rule_or_list, (list, str)) else rule_or_list.get("applies_to", "all")
    return a == "all" or genre in a


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


class Video:
    """Everything the detectors read, on one clock (seconds from the start of the analysed excerpt)."""

    def __init__(self, video_id: str):
        wd = ingest.VIDEOS / video_id
        self.feats = _j(wd / "features.json")
        if not self.feats:
            raise FileNotFoundError(video_id)
        self.fp = self.feats["fingerprint"]
        self.dur = float(self.fp["duration_s"])
        vis, aud = _j(wd / "visual.json"), _j(wd / "audio.json")
        self.per = _j(wd / "perception.json") or {}
        self.crit = _j(wd / "critique.json") or {}
        self.shots = vis["shots"]
        self.cuts = [s for s, _ in self.shots[1:]]
        c = vis["curves"]
        self.ct, self.motion = c["t"], c["motion"]
        L = aud["loudness"]
        self.lt, self.ldb = L["t"], L["db"]
        self.words = aud["transcript"].get("words") or []
        self.segs = self.per.get("segments", [])
        self.beats = self.crit.get("structure", [])
        self.ctas = (self.per.get("overall") or {}).get("cta_moments") or []

    def loud(self, t0, t1):
        return _mean([d for t, d in zip(self.lt, self.ldb) if t0 <= t < t1])

    def mot(self, t0, t1):
        return _mean([m for t, m in zip(self.ct, self.motion) if t0 <= t < t1])

    def text_in(self, t0, t1):
        return any(s.get("on_screen_text") and s["start_s"] < t1 and s["end_s"] > t0 for s in self.segs)

    def words_in(self, t0, t1):
        return [w for w in self.words if t0 <= w["s"] < t1]

    def format_bounds(self):
        out, prev = [], None
        for s in self.segs:
            if prev is not None and s["format"] != prev:
                out.append(s["start_s"])
            prev = s["format"]
        return out

    def beat(self, role):
        return [b for b in self.beats if b["role"] == role]

    @property
    def talk_led(self):
        return (self.fp.get("speech_coverage") or 0) >= 0.3


def _flag(kind, desc, t, t_end=None, detail=""):
    return {"kind": kind, "description": desc, "t": round(max(0.0, t), 1),
            "t_end": round(t_end, 1) if t_end is not None else None, "detail": detail}


# ---------------------------------------------------------------- detectors (one per catalogue flag kind)

def _static_open(v, g, bench):
    if not v.shots:
        return []
    s, e = v.shots[0]
    med = st.median(v.motion) if v.motion else 0
    m = v.mot(s, e)
    if e - s > 5 and m is not None and m < med:
        return [_flag("static_open", "Opening shot runs long with little motion", s, e, f"first shot {e - s:.1f} s, motion below the video's median")]
    return []


def _no_face_open(v, g, bench):
    if (v.fp.get("face_share") or 0) > 0.2 and v.segs and not any(s["face_visible"] and s["start_s"] < 3 for s in v.segs):
        return [_flag("no_face_open", "People appear later but not in the opening", 0, 3, f"faces on screen {v.fp['face_share']:.0%} of runtime, none in 0–3 s")]
    return []


def _no_promise(v, g, bench):
    T = 3 if g in SHORT_FORM else 15
    ws = v.words_in(0, T)
    said = " ".join(w["w"].lower() for w in ws)
    if "?" in said or any(w.strip(".,!?").lower() in PROMISE_WORDS for w in said.split()) or v.text_in(0, T):
        return []
    return [_flag("no_promise", "No question, promise or on-screen title in the opening", 0, T,
                  f"nothing in the first {T} s states what the viewer will get")]


def _long_preamble(v, g, bench):
    setup = v.beat("intro_setup")
    if not setup:
        return []
    end = max(b["end_s"] for b in setup)
    lim = 0.2 * v.dur if g in SHORT_FORM else 30
    if end > lim:
        return [_flag("long_preamble", "Intro/setup runs long before the main content", setup[0]["start_s"], end,
                      f"setup ends at {end:.0f} s (limit {lim:.0f} s)")]
    return []


def _silent_open(v, g, bench):
    ttfw = v.fp.get("time_to_first_word_s")
    thr = 2.0 if g in ("explainer", "tech_review", "ad") else 3.0 if g in ("shorts", "cooking") else None
    if ttfw is None or thr is None or ttfw <= thr or v.text_in(0, ttfw):
        return []
    return [_flag("silent_open", "No voice and no on-screen text at the start", 0, ttfw, f"first word at {ttfw:.1f} s (target ≤ {thr:.0f} s)")]


def _long_shot(v, g, bench):
    gm = (bench.get(g, {}).get("median_shot_s") or [None, 3.0])[1] or 3.0
    lim = max(3 * gm, 8)
    fb = v.format_bounds()
    med = st.median(v.motion) if v.motion else 0
    return [_flag("long_shot", "One shot held a long time", s, e, f"{e - s:.0f} s shot with little motion (limit {lim:.0f} s for {g})")
            for s, e in v.shots if e - s > lim and not any(s < b < e for b in fb) and (v.mot(s, e) or 0) < med][:6]


def _pace_drop(v, g, bench):
    if v.dur < 90 or len(v.cuts) < 6:
        return []
    ts = [t for t in range(15, int(v.dur) - 15, 5)]
    rate = [sum(t - 15 <= c < t + 15 for c in v.cuts) * 2 for t in ts]
    med = st.median(rate)
    out, run = [], None
    for t, r in zip(ts, rate):
        if r < 0.5 * med:
            run = run or t
        elif run is not None:
            if t - run > 30:
                out.append(_flag("pace_drop", "Cutting slows sharply", run, t, f"cut rate under half the video's own median ({med:.0f}/min)"))
            run = None
    if run is not None and ts[-1] - run > 30:
        out.append(_flag("pace_drop", "Cutting slows sharply", run, ts[-1], f"cut rate under half the video's own median ({med:.0f}/min)"))
    return out


def _visual_stall(v, g, bench):
    lim = 3 if g in SHORT_FORM else 8
    ev = sorted({0.0, v.dur, *v.cuts, *v.format_bounds(), *[s["start_s"] for s in v.segs if s.get("on_screen_text")]})
    med = st.median(v.motion) if v.motion else 0
    # camera or animation movement is visual change too: only flag gaps that are also below the video's median motion
    out = [_flag("visual_stall", "Nothing changes on screen", a, b, f"{b - a:.0f} s with no cut, format or text change and little motion (limit {lim} s)")
           for a, b in zip(ev, ev[1:]) if b - a > lim and (v.mot(a, b) or 0) < med]
    return sorted(out, key=lambda f: f["t"] - (f["t_end"] or 0))[:8]


def _single_format_run(v, g, bench):
    if g in SHORT_FORM or not v.segs:
        return []
    out, start, prev = [], v.segs[0]["start_s"], v.segs[0]["format"]
    for s in v.segs[1:] + [{"format": None, "start_s": v.dur}]:
        if s["format"] != prev:
            if s["start_s"] - start > 60:
                out.append(_flag("single_format_run", "Same visual format for over a minute", start, s["start_s"],
                                 f"{prev.replace('_', ' ')} for {s['start_s'] - start:.0f} s"))
            start, prev = s["start_s"], s["format"]
    return out


def _gaps(v, min_gap, t_max=None):
    ws = v.words
    for a, b in zip(ws, ws[1:]):
        if b["s"] - a["e"] > min_gap and (t_max is None or a["e"] < t_max):
            yield a["e"], b["s"]


def _silence_in_hook(v, g, bench):
    out = []
    for a, b in _gaps(v, 2.0, 15):
        if (v.loud(a, b) or 0) < QUIET_DB and not v.text_in(a, b):
            out.append(_flag("silence_in_hook", "Silence in the opening", a, b, f"{b - a:.1f} s near-silent gap before 15 s"))
    return out


def _dead_air(v, g, bench):
    if not v.talk_led:
        return []
    fb = v.format_bounds()
    out = [_flag("dead_air", "Dead air", a, b, f"{b - a:.1f} s of near-silence with nothing changing on screen")
           for a, b in _gaps(v, 1.5) if (v.loud(a, b) or 0) < QUIET_DB and not any(a < c < b for c in v.cuts + fb)]
    return out[:8]


def _slow_stretch(v, g, bench):
    if not v.talk_led or v.dur < 60:
        return []
    out, run = [], None
    for t in range(15, int(v.dur) - 15, 5):
        ws = v.words_in(t - 15, t + 15)
        spoken = sum(w["e"] - w["s"] for w in ws)
        slow = spoken > 12 and len(ws) * 2 < 110
        if slow and run is None:
            run = t
        elif not slow and run is not None:
            if t - run >= 15:
                out.append(_flag("slow_stretch", "Speech slows down", run, t, "under 110 words/min while talking"))
            run = None
    return out[:4]


def _no_hook_text(v, g, bench):
    if g in SHORT_FORM and not v.fp.get("hook_text_overlay"):
        return [_flag("no_hook_text", "No on-screen text in the first 3 s", 0, 3, "short-form guidance: put the hook in text too")]
    return []


def _cta_audio_only(v, g, bench):
    return [_flag("cta_audio_only", "Call to action is only spoken", c["t_s"], None, f"“{(c.get('text') or '')[:70]}” has no on-screen text within 2 s")
            for c in v.ctas if c.get("t_s") is not None and not v.text_in(c["t_s"] - 2, c["t_s"] + 2)][:3]


def _energy_dip(v, g, bench):
    out, run = [], None
    for i, (t, d) in enumerate(zip(v.lt, v.ldb)):
        win = [x for tt, x in zip(v.lt, v.ldb) if t - 15 <= tt < t + 15]
        dip = d < st.median(win) - 6 and v.words_in(t - 5, t + 5)
        if dip and run is None:
            run = t
        elif not dip and run is not None:
            if t - run > 3:
                out.append(_flag("energy_dip", "Audio energy drops", run, t, "over 6 dB below the surrounding 30 s"))
            run = None
    return out[:5]


def _quiet_open(v, g, bench):
    a, m = v.loud(0, 3), _mean(v.ldb)
    if a is not None and m is not None and a < m - 6:
        return [_flag("quiet_open", "Quiet opening", 0, 3, f"first 3 s are {m - a:.0f} dB below the video's average")]
    return []


def _no_address_hook(v, g, bench):
    if not v.talk_led:
        return []
    said = " ".join(w["w"].lower() for w in v.words_in(0, 15))
    if not v.words_in(0, 15) or "?" in said or any(x.strip(".,!?'") in ("you", "your", "you're", "you'll") for x in said.split()):
        return []
    return [_flag("no_address_hook", "The opening doesn't speak to the viewer", 0, 15, "no 'you' and no question in the first 15 s")]


def _beat_gap(v, g, bench):
    if g in SHORT_FORM or v.dur < 240 or not v.beats:
        return []
    ev = sorted({b["start_s"] for b in v.beats} | set(v.format_bounds()) | {0.0, v.dur})
    return [_flag("beat_gap", "Long stretch with no new beat or format change", a, b, f"{b - a:.0f} s (limit 180 s)")
            for a, b in zip(ev, ev[1:]) if b - a > 180]


def _late_payoff(v, g, bench):
    pay = v.beat("payoff_reveal")
    if pay and min(b["start_s"] for b in pay) > 0.7 * v.dur:
        t = min(b["start_s"] for b in pay)
        return [_flag("late_payoff", "The payoff arrives late", t, None, f"first payoff at {t / v.dur:.0%} of runtime")]
    return []


def _flat_affect(v, g, bench):
    if len(v.ldb) < 10 or len(v.motion) < 10:
        return []
    lq = sorted(v.ldb)[int(0.9 * len(v.ldb))]
    mq = sorted(v.motion)[int(0.9 * len(v.motion))]
    for t, m in zip(v.ct, v.motion):
        if m >= mq and (v.loud(t - 0.5, t + 0.5) or -99) >= lq:
            return []
    if v.beat("payoff_reveal"):
        return []
    return [_flag("flat_affect", "No high-energy peak", 0, v.dur, "loudness and motion never peak together, and no reveal beat")]


def _no_cta_ad(v, g, bench):
    if g == "ad" and not v.fp.get("cta_count"):
        return [_flag("no_cta_ad", "The ad has no call to action", v.dur * 0.9, v.dur, "no explicit CTA detected")]
    return []


def _early_ask(v, g, bench):
    if g in SHORT_FORM:
        return []
    return [_flag("early_ask", "Asks for a subscribe/like very early", c["t_s"], None, f"at {c['t_s'] / v.dur:.0%} of runtime")
            for c in v.ctas if c.get("kind") == "subscribe_like" and c.get("t_s") is not None and c["t_s"] < 0.15 * v.dur][:1]


def _over_length(v, g, bench):
    if g == "shorts" and v.dur > 180:
        return [_flag("over_length", "Too long for a Short", 180, v.dur, f"{v.dur:.0f} s; Shorts are capped at 180 s")]
    return []


def _dead_end(v, g, bench):
    if g != "shorts":
        return []
    a, m = v.loud(v.dur - 2, v.dur + 1), v.mot(v.dur - 2, v.dur + 1)
    if (a is not None and a < QUIET_DB) or (m is not None and m < 0.01):
        return [_flag("dead_end", "The Short ends on a dead frame", v.dur - 2, v.dur, "silent or static last 2 s: no loop back")]
    return []


def _long_outro(v, g, bench):
    if g in SHORT_FORM:
        return []
    pay = v.beat("payoff_reveal")
    if pay:
        end = max(b["end_s"] for b in pay)
        if v.dur - end > 20:
            return [_flag("long_outro", "Long tail after the payoff", end, v.dur, f"{v.dur - end:.0f} s after the last payoff")]
    return []


DETECTORS = {f.__name__[1:]: f for f in [
    _static_open, _no_face_open, _no_promise, _long_preamble, _silent_open, _long_shot, _pace_drop, _visual_stall,
    _single_format_run, _silence_in_hook, _dead_air, _slow_stretch, _no_hook_text, _cta_audio_only, _energy_dip,
    _quiet_open, _no_address_hook, _beat_gap, _late_payoff, _flat_affect, _no_cta_ad, _early_ask, _over_length,
    _dead_end, _long_outro]}
NEEDS_CRITIQUE = {"long_preamble", "beat_gap", "late_payoff", "long_outro"}


# ---------------------------------------------------------------- checks on the fingerprint

def _shots_by(v, t):
    return sum(s < t for s, _ in v.shots)


def _check(rule, v: Video, g: str, bench: dict):
    sig, d, thr = rule["signal"], rule["direction"], rule.get("threshold")
    if sig == "timeline":
        if "shots in first 5 s" in (rule.get("unit") or ""):
            val = _shots_by(v, 5)
            return {"signal": "shots_in_first_5s", "label": "Shots in the first 5 s", "value": val,
                    "target": f"≥ {thr}", "ok": val >= thr, "heuristic": rule["heuristic"], "basis": rule.get("note", "")}
        return None  # other timeline rules are expressed through the flag detectors
    val = v.fp.get(sig)
    if val is None or (isinstance(val, float) and val != val):
        return None
    if isinstance(val, bool):
        val = int(val)
    rng = (bench.get(g) or {}).get(sig)
    basis = rule.get("note", "")
    if thr is None and rng and d in ("range", "higher_better", "lower_better"):
        lo, _, hi = rng
        ok = lo <= val <= hi if d == "range" else val >= lo if d == "higher_better" else val <= hi
        target = f"{g} corpus {_fmt(lo)}–{_fmt(hi)}" if d == "range" else f"{g} corpus ≥ {_fmt(lo)}" if d == "higher_better" else f"{g} corpus ≤ {_fmt(hi)}"
        return {"signal": sig, "label": sig, "value": val, "target": target, "ok": ok, "heuristic": True, "corpus": True,
                "basis": "No source gives a number: compared with the middle half of the target genre's videos (n≈6), which describes, not prescribes. " + basis}
    if thr is None:
        return None
    if d == "range":
        lo, hi = thr
        ok, target = lo <= val <= hi, f"{_fmt(lo)}–{_fmt(hi)}"
    elif d == "higher_better":
        ok, target = val >= thr, f"≥ {_fmt(thr)}"
    else:
        ok, target = val <= thr, f"≤ {_fmt(thr)}"
    return {"signal": sig, "label": sig, "value": val, "target": target, "ok": ok, "heuristic": rule["heuristic"], "basis": basis}


def _fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


# ---------------------------------------------------------------- public

def evaluate(video_id: str, genre: str | None = None, params: list[str] | None = None, goal: str = "both") -> dict:
    v = Video(video_id)
    g = genre if genre in GENRES else v.feats.get("category")
    bench = _j(BENCH) or {}
    from .fingerprint import FIELDS
    cat = catalogue()["parameters"]
    chosen = [p for p in cat if (not params or p["id"] in params) and (goal == "both" or p["goal"] in (goal, "both"))
              and any(_applies(r, g) for r in p["rules"])]  # e.g. brand timing only applies to ads
    out = []
    for p in chosen:
        checks = [c for r in p["rules"] if _applies(r, g) for c in [_check(r, v, g, bench)] if c]
        for c in checks:
            c["label"] = FIELDS.get(c["signal"], (None, c["label"]))[1] if c["signal"] in FIELDS else c["label"]
        flags, skipped = [], []
        for f in p["flags"]:
            det = DETECTORS.get(f["kind"])
            if not det or (f["kind"] in NEEDS_CRITIQUE and not v.beats):
                skipped.append(f["kind"])
                continue
            flags += [{**x, "parameter": p["id"]} for x in det(v, g, bench)]
        sourced_fail = any(not c["ok"] and not c["heuristic"] for c in checks)
        any_fail = any(not c["ok"] for c in checks)
        if not checks and not flags and len(skipped) == len(p["flags"]):
            status = "unmeasured"
        elif sourced_fail or len(flags) >= 3:
            status = "problem"
        elif any_fail or flags:
            status = "watch"
        else:
            status = "good"
        out.append({"id": p["id"], "name": p["name"], "goal": p["goal"], "evidence_strength": p["evidence_strength"],
                    "summary": p["summary"], "genre_note": (p.get("genre_notes") or {}).get(g), "status": status,
                    "checks": checks, "flags": flags, "not_detected": skipped,
                    "sources": p.get("sources", [])[:3]})
    order = {"problem": 0, "watch": 1, "good": 2, "unmeasured": 3}
    out.sort(key=lambda r: (order[r["status"]], r["name"]))
    pains = sorted((f for r in out for f in r["flags"]), key=lambda f: f["t"])
    counts = {s: sum(r["status"] == s for r in out) for s in order}
    return {"video_id": video_id, "genre": g, "goal": goal, "counts": counts, "parameters": out, "pain_points": pains,
            "note": "Checks use sourced guidance where it exists and heuristics otherwise (marked). They flag what to "
                    "test, not predicted performance."}


def focus_text(card: dict) -> str:
    """Steer the critique toward the creator's goal, chosen parameters and the detected pain points."""
    lines = [f"CREATOR'S GOAL: optimise this {card['genre']} video for "
             f"{ {'retention': 'audience retention', 'virality': 'reach and sharing', 'both': 'retention and reach'}[card['goal']] }.",
             "PRIORITY PARAMETERS (status from our checks):"]
    for p in card["parameters"]:
        lines.append(f"- {p['name']} [{p['status']}]: {p['summary'][:160]}")
    if card["pain_points"]:
        lines.append("DETECTED PAIN POINTS (heuristic detectors, verify against the data):")
        for f in card["pain_points"][:20]:
            lines.append(f"- {f['t']:.1f}s{'-' + format(f['t_end'], '.1f') + 's' if f['t_end'] else ''} {f['description']}: {f['detail']}")
    lines.append("Prioritise recommendations that address these parameters and pain points, still citing measured evidence.")
    return "\n".join(lines)
