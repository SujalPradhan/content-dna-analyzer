"""End-to-end orchestration: ingest -> local signals -> perception -> fingerprint -> critique -> report."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

from . import audio, critique, fingerprint, ingest, perception, visual

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
BENCH = RESULTS / "benchmarks.json"


def bin_size(dur: float) -> float:
    return 5.0 if dur <= 180 else 10.0 if dur <= 600 else 20.0


def extract(src_str: str, category: str = "uncategorised", keep_video: bool = False, use_llm: bool = True) -> dict:
    """Everything except the critique. Writes <workdir>/features.json and returns it."""
    src = ingest.resolve(src_str)
    feat_path = src.workdir / "features.json"
    if feat_path.exists():
        feats = json.loads(feat_path.read_text())
        if feats.get("perception_done") or not use_llm:
            return feats
    vis = visual.analyse(src.video_path, src.workdir)
    aud = audio.analyse(src.audio_path, src.workdir, src.video_id)
    per = perception.analyse(src, src.workdir) if use_llm else None
    fp = fingerprint.compute(src.meta, vis, aud, per)
    bins = fingerprint.timeline_bins(vis, aud, fp["duration_s"], bin_size(fp["duration_s"]))
    m = src.meta
    feats = {"video_id": src.video_id, "category": category, "title": m.get("title"), "channel": m.get("channel"),
             "url": src.youtube_url, "views": m.get("view_count"), "likes": m.get("like_count"),
             "comments": m.get("comment_count"), "subscribers": m.get("channel_follower_count"),
             "upload_date": m.get("upload_date"), "full_duration": m.get("duration"), "is_short": bool(m.get("is_short")),
             "fingerprint": fp, "bins": bins, "perception_done": per is not None}
    feat_path.write_text(json.dumps(feats, indent=1))
    if not keep_video and src.video_path.exists() and (src.workdir / "visual.json").exists():
        src.video_path.unlink()  # disk budget: keyframes + features are all we need afterwards
    return feats


def corpus_ids() -> set[str]:
    """Video ids of the study corpus (data/corpus.csv). Videos analysed ad hoc (API, CLI) are not in it."""
    path = ROOT / "data" / "corpus.csv"
    return {ingest.youtube_id(r["url"]) for r in read_corpus(path)} if path.exists() else set()


def load_all_features() -> list[dict]:
    """Features of corpus videos only, so ad-hoc analyses never change benchmarks or statistics."""
    ids = corpus_ids()
    out = [json.loads(p.read_text()) for p in sorted((ROOT / "data" / "videos").glob("*/features.json"))]
    return [f for f in out if not ids or f["video_id"] in ids]


def compute_benchmarks() -> dict:
    feats = load_all_features()
    out = {}
    groups = {"_all": feats}
    for f in feats:
        groups.setdefault(f["category"], []).append(f)
    for g, items in groups.items():
        out[g] = {"n": len(items)}
        for k in fingerprint.FIELDS:
            vals = [f["fingerprint"][k] for f in items if isinstance(f["fingerprint"].get(k), (int, float))
                    and not math.isnan(f["fingerprint"][k])]
            if len(vals) >= 3:
                p25, p50, p75 = np.percentile(vals, [25, 50, 75])
                out[g][k] = [round(float(p25), 3), round(float(p50), 3), round(float(p75), 3)]
    RESULTS.mkdir(exist_ok=True)
    BENCH.write_text(json.dumps(out, indent=1))
    return out


def percentiles_for(fp: dict, category: str) -> dict:
    """Percentile rank (0-100) of each field within the video's category (falls back to the whole corpus)."""
    feats = load_all_features()
    peers = [f for f in feats if f["category"] == category]
    if len(peers) < 4:
        peers = feats
    out = {}
    for k, v in fp.items():
        if not isinstance(v, (int, float)) or math.isnan(v):
            continue
        vals = [p["fingerprint"][k] for p in peers if isinstance(p["fingerprint"].get(k), (int, float))
                and not math.isnan(p["fingerprint"][k])]
        if len(vals) >= 4:
            out[k] = round(100 * (sum(x < v for x in vals) + 0.5 * sum(x == v for x in vals)) / len(vals))
    return out


def run_critique(video_id: str, use_cache: bool = True, model: str = "claude-sonnet-5", focus: str | None = None,
                 category: str | None = None) -> dict:
    workdir = ingest.VIDEOS / video_id
    feats = json.loads((workdir / "features.json").read_text())
    src = ingest.load(video_id)
    vis = json.loads((workdir / "visual.json").read_text())
    aud = json.loads((workdir / "audio.json").read_text())
    per = json.loads((workdir / "perception.json").read_text())
    bench = json.loads(BENCH.read_text()) if BENCH.exists() else None
    cat = category or feats["category"]
    pct = percentiles_for(feats["fingerprint"], cat)
    res = critique.analyse(src, feats["fingerprint"], feats["bins"], aud, per, vis, cat, bench, pct,
                           model=model, use_cache=use_cache, focus=focus)
    # a goal-focused critique never overwrites the corpus critique the evaluation was run on
    name = "critique_focus.json" if focus else "critique.json" if use_cache else f"critique_rerun_{model}.json"
    (workdir / name).write_text(json.dumps(res, indent=1))
    return res


def read_corpus(path: Path) -> list[dict]:
    with path.open() as f:
        return [r for r in csv.DictReader(f) if r.get("url") and not r["url"].startswith("#")]


def revalidate_all() -> dict:
    """Re-run the evidence validator over every saved critique (no API calls). The first score is kept as grounding_v1."""
    counts = {"files": 0, "v1_verified": 0, "v2_verified": 0, "items": 0}
    for wd in sorted(ingest.VIDEOS.iterdir()):
        if not (wd / "features.json").exists():
            continue
        feats = json.loads((wd / "features.json").read_text())
        vis = json.loads((wd / "visual.json").read_text())
        aud = json.loads((wd / "audio.json").read_text())
        per = json.loads((wd / "perception.json").read_text())
        for p in wd.glob("critique*.json"):
            c = json.loads(p.read_text())
            if "grounding" not in c:
                continue
            c.setdefault("grounding_v1", {k: v for k, v in c["grounding"].items() if k != "checks"})
            c["grounding"] = critique.validate(c, feats["fingerprint"], feats["bins"], aud, per, vis)
            p.write_text(json.dumps(c, indent=1))
            if p.name == "critique.json":
                counts["files"] += 1
                counts["v1_verified"] += c["grounding_v1"]["evidence_verified"]
                counts["v2_verified"] += c["grounding"]["evidence_verified"]
                counts["items"] += c["grounding"]["evidence_items"]
    return counts


def refingerprint_all() -> int:
    """Recompute fingerprints and bins from cached signals (no API calls) after a fingerprint code change."""
    n = 0
    for wd in sorted(ingest.VIDEOS.iterdir()):
        fp_path = wd / "features.json"
        if not fp_path.exists():
            continue
        feats = json.loads(fp_path.read_text())
        meta = json.loads((wd / "meta.json").read_text())
        vis = json.loads((wd / "visual.json").read_text())
        aud = json.loads((wd / "audio.json").read_text())
        per = json.loads((wd / "perception.json").read_text())
        feats["fingerprint"] = fingerprint.compute(meta, vis, aud, per)
        feats["bins"] = fingerprint.timeline_bins(vis, aud, feats["fingerprint"]["duration_s"], bin_size(feats["fingerprint"]["duration_s"]))
        fp_path.write_text(json.dumps(feats, indent=1))
        n += 1
    return n
