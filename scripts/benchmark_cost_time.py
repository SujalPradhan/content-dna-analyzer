"""Measure what one analysis costs and how long it takes, for the Cost & time tab.

    uv run python scripts/benchmark_cost_time.py            # cost from the ledger + fresh timed runs
    uv run python scripts/benchmark_cost_time.py --no-runs  # cost from the ledger only (free)

Two sources, both real:
1. Cost per video from results/usage.csv for every corpus video (Whisper + Gemini vision + Claude critique),
   joined with the analysed duration, then a least-squares line per stage (cost = a + b * minutes).
2. Fresh end-to-end runs of the API's own job runner (server._run, fixes on) on 30 s, 1, 5 and 10 min windows of
   one YouTube video, never analysed at those windows before, so no cache helps. Wall time per stage comes from
   the job's `timings`, cost per stage from the ledger rows the run wrote.
Writes web/cost.json.
"""
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from content_dna import ingest, llm, server

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "cost.json"
SOURCE = "https://www.youtube.com/watch?v=3B3B9eSgMV0"  # 11.7 min tech review from the corpus
WINDOWS = [30, 60, 300, 600]
STAGES = {"whisper": "Transcript (whisper-1)", "perception": "Vision timeline (gemini-3.5-flash)",
          "critique": "Fixes (claude-sonnet-5)"}


def ledger() -> list[dict]:
    with open(llm.LEDGER) as f:
        return list(csv.DictReader(f))


def corpus_points(rows: list[dict]) -> list[dict]:
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["video_id"] and r["stage"] in STAGES:
            by[r["video_id"]][r["stage"]].append(float(r["usd"]))
    pts = []
    for vid, st in by.items():
        meta = ingest.VIDEOS / vid / "meta.json"
        if "@" in vid or not meta.exists() or not all(k in st for k in STAGES):
            continue  # only full corpus videos that went through all three paid stages
        m = json.loads(meta.read_text())
        pts.append({"video_id": vid, "minutes": round(m["analysed_duration"] / 60, 3),
                    **{k: round(sum(v) / len(v), 6) for k, v in st.items()}})  # per call: some were rerun for the evaluation
    return sorted(pts, key=lambda p: p["minutes"])


def fit(xs, ys) -> dict:
    n, mx, my = len(xs), sum(xs) / len(xs), sum(ys) / len(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return {"fixed": round(my - b * mx, 6), "per_min": round(b, 6), "n": n}


def timed_run(seconds: int) -> dict:
    job_id = f"bench{seconds}"
    server._jobs[job_id] = {"job_id": job_id, "status": "queued", "stage": "queued", "created": time.time()}
    t0 = time.time()
    server._run(job_id, SOURCE, "tech_review", True, 0, seconds, "both", None)
    job = server._jobs[job_id]
    if job["status"] != "done":
        raise SystemExit(f"{seconds}s run failed: {job.get('error')}")
    vid = job["video_id"]
    cost = defaultdict(float)
    for r in ledger():
        if r["video_id"] == vid and float(r["ts"]) >= t0:
            cost[r["stage"]] += float(r["usd"])
    print(seconds, "s", round(time.time() - t0, 1), "s wall", dict(cost))
    return {"seconds": seconds, "video_id": vid, "wall_s": round(time.time() - t0, 1), "timings": job["timings"],
            "cost": {k: round(v, 6) for k, v in cost.items()}}


def main():
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    pts = corpus_points(ledger())
    xs = [p["minutes"] for p in pts]
    model = {k: fit(xs, [p[k] for p in pts]) for k in STAGES}
    runs = old.get("runs", [])
    if "--no-runs" not in sys.argv:
        for s in WINDOWS:
            if (ingest.VIDEOS / f"3B3B9eSgMV0@0-{s}").exists():
                raise SystemExit(f"3B3B9eSgMV0@0-{s} was analysed before; its caches would make the timing meaningless")
        runs = [timed_run(s) for s in WINDOWS]
    body = {"generated": time.strftime("%Y-%m-%d"), "source": SOURCE, "stages": STAGES, "prices": llm.PRICES,
            "corpus": pts, "model": model, "runs": runs,
            "machine": "Apple M4 laptop, 16 GB, home broadband (the hosted API is 1 vCPU, so its local stages run slower)"}
    OUT.write_text(json.dumps(body, indent=1))
    print(len(pts), "corpus videos;", {k: (v["fixed"], v["per_min"]) for k, v in model.items()})


if __name__ == "__main__":
    main()
