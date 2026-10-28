"""Cross-modal check of the vision model's timeline against the deterministic shot detector.

A format change in Gemini's timeline should usually coincide with a hard cut. We measure the share of Gemini
segment boundaries that land within 1.0 s of a detected cut, before (numeric timestamps, data/old_perception)
and after (MM:SS strings) the timestamp-format fix, plus the timeline-overrun ratio."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TOL = 1.0


def boundary_hit_rate(segs, cuts, dur):
    b = [s["start_s"] for s in segs[1:] if 0 < s["start_s"] < dur]
    if not b or not len(cuts):
        return None, len(b)
    cuts = np.array(cuts)
    return float(np.mean([np.abs(cuts - x).min() <= TOL for x in b])), len(b)


def main():
    rows = []
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from content_dna.pipeline import corpus_ids
    ids = corpus_ids()
    for d in sorted((ROOT / "data/videos").iterdir()):
        if not (d / "features.json").exists() or d.name not in ids:
            continue
        f = json.loads((d / "features.json").read_text())
        dur = f["fingerprint"]["duration_s"]
        cuts = [s for s, _ in json.loads((d / "visual.json").read_text())["shots"][1:]]
        new = json.loads((d / "perception.json").read_text())
        r = {"video_id": d.name, "category": f["category"], "n_cuts": len(cuts)}
        r["hit_after"], r["n_bounds_after"] = boundary_hit_rate(new["segments"], cuts, dur)
        r["overrun_after"] = new["timeline_overrun_ratio"]
        old_p = ROOT / "data/old_perception" / d.name / "perception.json"
        if old_p.exists():
            old = json.loads(old_p.read_text())
            mx = max([s["end_s"] for s in old["segments"]] + [0])
            r["overrun_before"] = round(mx / dur, 3)
            r["hit_before"], _ = boundary_hit_rate(old["segments"], cuts, dur)
        rows.append(r)
    def agg(key):
        v = [r[key] for r in rows if r.get(key) is not None]
        return round(float(np.median(v)), 3) if v else None
    out = {"tolerance_s": TOL, "n": len(rows),
           "overrun_gt_5pct_before": sum(1 for r in rows if (r.get("overrun_before") or 1) > 1.05),
           "overrun_gt_5pct_after": sum(1 for r in rows if (r.get("overrun_after") or 1) > 1.05),
           "median_boundary_hit_before": agg("hit_before"), "median_boundary_hit_after": agg("hit_after"),
           "rows": rows}
    (ROOT / "results/eval/perception_eval.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "rows"})
    by = {}
    for r in rows:
        if r["hit_after"] is not None:
            by.setdefault(r["category"], []).append(r["hit_after"])
    print({c: round(float(np.median(v)), 2) for c, v in by.items()})


if __name__ == "__main__":
    main()
