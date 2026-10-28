"""Content DNA Analyzer CLI."""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main() -> None:
    from . import ingest, llm, pipeline, report

    ap = argparse.ArgumentParser(prog="dna", description="Creative fingerprint + evidence-backed critique for videos")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="analyse one YouTube URL or local video file end to end")
    a.add_argument("source")
    a.add_argument("--category", default="uncategorised")
    a.add_argument("--keep-video", action="store_true")
    a.add_argument("--no-critique", action="store_true")
    b = sub.add_parser("batch", help="run a corpus CSV (columns: url,category,...)")
    b.add_argument("csv", type=Path)
    b.add_argument("--stage", choices=["extract", "critique", "all"], default="all")
    b.add_argument("--limit", type=int)
    b.add_argument("--workers", type=int, default=3)
    sub.add_parser("benchmarks", help="recompute corpus benchmarks")
    sub.add_parser("spend", help="show estimated LLM spend")
    sub.add_parser("revalidate", help="re-run the evidence validator over saved critiques (offline)")
    sv = sub.add_parser("serve", help="run the HTTP API + web app (docs at /docs)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8001)
    args = ap.parse_args()

    if args.cmd == "serve":
        from . import server
        server.serve(args.host, args.port)
    elif args.cmd == "spend":
        print(f"estimated spend: ${llm.spent_usd():.4f} (budget ${llm.BUDGET_USD:.2f})")
    elif args.cmd == "revalidate":
        print(pipeline.revalidate_all())
    elif args.cmd == "benchmarks":
        print(json.dumps(pipeline.compute_benchmarks()["_all"], indent=1))
    elif args.cmd == "analyze":
        feats = pipeline.extract(args.source, args.category, keep_video=args.keep_video)
        print(json.dumps(feats["fingerprint"], indent=1))
        if not args.no_critique:
            res = pipeline.run_critique(feats["video_id"])
            g = res["grounding"]
            print(f"critique: {len(res['recommendations'])} recs, evidence verified {g['evidence_verified']}/{g['evidence_items']}")
        out = report.render(ingest.VIDEOS / feats["video_id"])
        print(f"report: {out}\nspend so far: ${llm.spent_usd():.4f}")
    elif args.cmd == "batch":
        rows = pipeline.read_corpus(args.csv)[: args.limit]
        if args.stage in ("extract", "all"):
            def job(r):
                try:
                    f = pipeline.extract(r["url"], r["category"])
                    return f"ok   {f['video_id']} {f['fingerprint']['duration_s']}s {f['title'][:50]}"
                except llm.BudgetExceeded:
                    raise
                except Exception as ex:  # keep the batch going; report failures
                    return f"FAIL {r['url']} {type(ex).__name__}: {str(ex)[:200]}"
            with ThreadPoolExecutor(args.workers) as ex:
                for msg in ex.map(job, rows):
                    print(msg, flush=True)
            pipeline.compute_benchmarks()
        if args.stage in ("critique", "all"):
            # sequential: keeps the Claude prompt cache warm (same system prefix, 5-min TTL)
            for r in rows:
                vid = ingest.youtube_id(r["url"])
                wd = ingest.VIDEOS / (vid or "")
                if not (wd / "features.json").exists():
                    continue
                try:
                    res = pipeline.run_critique(vid)
                    report.render(wd)
                    g = res["grounding"]
                    print(f"crit {vid} recs={g['recs']} evidence {g['evidence_verified']}/{g['evidence_items']}", flush=True)
                except llm.BudgetExceeded:
                    raise
                except Exception:
                    print(f"FAIL crit {vid}\n{traceback.format_exc()[-600:]}", flush=True)
        print(f"spend so far: ${llm.spent_usd():.4f}")
