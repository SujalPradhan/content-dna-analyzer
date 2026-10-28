"""Critique evaluation.

1. Ablation: transcript-only baseline (same model, same output schema, no measured signals / frames / benchmarks)
   vs the full Content DNA critique, scored by the same automatic evidence validator.
2. Blind pairwise judge (claude-opus-4-8): for each video, which critique is more specific, actionable and
   verifiable? Order randomised; judge sees the measured data to check claims.
3. Stability: re-run the full critique with the cache bypassed on a subset and compare structure-role agreement,
   recommendation timing overlap and tag overlap.
Writes results/eval/critique_eval.json.
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from content_dna import critique, ingest, llm, pipeline  # noqa: E402

VID = ROOT / "data" / "videos"
OUT = ROOT / "results" / "eval" / "critique_eval.json"

BASELINE_SYSTEM = """You are a video content consultant. You receive a video's title and its timestamped transcript.
Explain how the video is constructed and what could be improved. Ground every point in the transcript; cite timestamps in
seconds. Never claim a change will increase views or retention. Evidence items: use kind 'quote' with verbatim words; you may
use kind 'metric' or 'visual' only if you have such data (you do not). 3-6 recommendations, 2-4 strengths, structure segments
covering the full runtime, 3-6 dna_tags, a 2-3 sentence summary of construction."""

JUDGE_SYSTEM = """You are an expert video editor and creative strategist auditing two AI critiques of the same video.
You get the video's measured data (cuts, speech, loudness, visual-format timeline, transcript) and two critiques, A and B.
Score each critique 1-5 on:
- specificity: points name concrete moments and concrete changes, not generic advice
- accuracy: claims are consistent with the measured data (check numbers, timestamps, quotes)
- actionability: an editor could act on it directly
- insight: explains WHY the video's construction works or not, beyond what a summary gives
Then pick the overall better critique (A, B or tie). Be strict; generic advice that could apply to any video scores low."""

JUDGE_SCHEMA = critique._strict({"type": "object", "properties": {
    "A": {"type": "object", "properties": {k: {"type": "integer"} for k in ["specificity", "accuracy", "actionability", "insight"]}},
    "B": {"type": "object", "properties": {k: {"type": "integer"} for k in ["specificity", "accuracy", "actionability", "insight"]}},
    "winner": {"type": "string", "enum": ["A", "B", "tie"]},
    "reason": {"type": "string"}}})


def load(vid):
    wd = VID / vid
    j = lambda n: json.loads((wd / n).read_text())
    return wd, j("features.json"), j("visual.json"), j("audio.json"), j("perception.json")


def baseline(vid):
    wd, feats, vis, aud, per = load(vid)
    cache = wd / "critique_baseline.json"
    if cache.exists():
        return json.loads(cache.read_text())
    text = (f"TITLE: {feats['title']}\nDURATION: {feats['fingerprint']['duration_s']} s\n\nTRANSCRIPT\n"
            + critique._fmt_segments(aud["transcript"]["segments"]))
    res = llm.claude_json(BASELINE_SYSTEM, text, critique.SCHEMA, max_tokens=12000, effort="medium",
                            stage="eval_baseline", video_id=vid)
    res["grounding"] = critique.validate(res, feats["fingerprint"], feats["bins"], aud, per, vis)
    cache.write_text(json.dumps(res, indent=1))
    return res


def strip(c):
    return {k: c[k] for k in ("summary", "structure", "hook", "strengths", "recommendations")} | {
        "recommendations": [{k: r[k] for k in ("title", "t_start_s", "t_end_s", "observation", "evidence", "recommendation")}
                            for r in c["recommendations"]]}


def judge(vid, full, base, seed):
    wd, feats, vis, aud, per = load(vid)
    cache = wd / "critique_judge.json"
    if cache.exists():
        return json.loads(cache.read_text())
    flip = random.Random(seed).random() < 0.5
    A, B = (base, full) if flip else (full, base)
    data = {"fingerprint": feats["fingerprint"], "timeline_bins": feats["bins"],
            "visual_format_timeline": [{k: s[k] for k in ("start_s", "end_s", "format", "on_screen_text")} for s in per["segments"]]}
    text = (f"VIDEO: {feats['title']} ({feats['category']})\nMEASURED DATA\n{json.dumps(data)}\n\nTRANSCRIPT\n"
            f"{critique._fmt_segments(aud['transcript']['segments'], 16000)}\n\nCRITIQUE A\n{json.dumps(strip(A))}\n\n"
            f"CRITIQUE B\n{json.dumps(strip(B))}")
    res = llm.claude_json(JUDGE_SYSTEM, text, JUDGE_SCHEMA, model="claude-opus-4-8", max_tokens=8000, effort="medium",
                          stage="eval_judge", video_id=vid)
    full_key, base_key = ("B", "A") if flip else ("A", "B")
    out = {"full": res[full_key], "baseline": res[base_key],
           "winner": {"tie": "tie", full_key: "full", base_key: "baseline"}[res["winner"]], "reason": res["reason"],
           "full_was": full_key}
    cache.write_text(json.dumps(out, indent=1))
    return out


def role_agreement(a, b, dur):
    def at(struct, t):
        for s in struct:
            if s["start_s"] <= t < s["end_s"]:
                return s["role"]
        return None
    ts = np.arange(0, dur, 1.0)
    return float(np.mean([at(a, t) == at(b, t) for t in ts]))


def stability(vid):
    wd = VID / vid
    a = json.loads((wd / "critique.json").read_text())
    b_path = wd / "critique_rerun_claude-sonnet-5.json"
    b = json.loads(b_path.read_text()) if b_path.exists() else pipeline.run_critique(vid, use_cache=False)
    dur = json.loads((wd / "features.json").read_text())["fingerprint"]["duration_s"]
    ta = [r["t_snapped_s"] for r in a["recommendations"]]
    tb = [r["t_snapped_s"] for r in b["recommendations"]]
    tol = max(10.0, 0.05 * dur)
    overlap = np.mean([any(abs(x - y) <= tol for y in ta) for x in tb]) if tb else 0
    tags_a, tags_b = {t.lower() for t in a["dna_tags"]}, {t.lower() for t in b["dna_tags"]}
    return {"video_id": vid, "role_agreement": round(role_agreement(a["structure"], b["structure"], dur), 3),
            "rec_time_overlap": round(float(overlap), 3), "tag_jaccard": round(len(tags_a & tags_b) / len(tags_a | tags_b), 3),
            "grounding_a": a["grounding"]["evidence_rate"], "grounding_b": b["grounding"]["evidence_rate"]}


def summarize_grounding(cs):
    items = sum(c["grounding"]["evidence_items"] for c in cs)
    ver = sum(c["grounding"]["evidence_verified"] for c in cs)
    recs = sum(c["grounding"]["recs"] for c in cs)
    rg = sum(c["grounding"]["recs_grounded"] for c in cs)
    kinds = {k: [sum(c["grounding"]["by_kind"][k][0] for c in cs), sum(c["grounding"]["by_kind"][k][1] for c in cs)]
             for k in ("metric", "quote", "visual")}
    return {"evidence_items": items, "evidence_verified": ver, "evidence_rate": round(ver / items, 3) if items else None,
            "evidence_per_rec": round(items / recs, 2) if recs else None, "recs": recs, "recs_grounded": rg,
            "rec_grounded_rate": round(rg / recs, 3) if recs else None, "by_kind": kinds}


def main(n_ablation=12, n_stability=5):
    corpus = pipeline.read_corpus(ROOT / "data" / "corpus.csv")
    vids = [ingest.youtube_id(r["url"]) for r in corpus]
    vids = [v for v in vids if (VID / v / "critique.json").exists()]
    # stratified pick: 2 per category for ablation/judge
    by_cat = {}
    for r in corpus:
        v = ingest.youtube_id(r["url"])
        if v in vids:
            by_cat.setdefault(r["category"], []).append(v)
    rnd = random.Random(1)
    abl = [v for c in sorted(by_cat) for v in rnd.sample(by_cat[c], min(2, len(by_cat[c])))][:n_ablation]
    stab = [v for c in sorted(by_cat) for v in by_cat[c][:1]][:n_stability]

    fulls = [json.loads((VID / v / "critique.json").read_text()) for v in vids]
    out = {"all_full": summarize_grounding(fulls)}
    base_res = {v: baseline(v) for v in abl}
    out["ablation_videos"] = abl
    out["ablation_full"] = summarize_grounding([json.loads((VID / v / "critique.json").read_text()) for v in abl])
    out["ablation_baseline"] = summarize_grounding(list(base_res.values()))
    judges = [judge(v, json.loads((VID / v / "critique.json").read_text()), base_res[v], i) for i, v in enumerate(abl)]
    out["judge"] = {"wins_full": sum(j["winner"] == "full" for j in judges),
                    "wins_baseline": sum(j["winner"] == "baseline" for j in judges),
                    "ties": sum(j["winner"] == "tie" for j in judges),
                    "mean_scores": {side: {k: round(float(np.mean([j[side][k] for j in judges])), 2)
                                           for k in ["specificity", "accuracy", "actionability", "insight"]}
                                    for side in ["full", "baseline"]},
                    "per_video": [{"video_id": v, **j} for v, j in zip(abl, judges)]}
    out["stability"] = [stability(v) for v in stab]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("judge",)}, indent=1)[:3000])
    print("judge", {k: v for k, v in out["judge"].items() if k != "per_video"})
    print(f"spend ${llm.spent_usd():.3f}")


if __name__ == "__main__":
    main()
