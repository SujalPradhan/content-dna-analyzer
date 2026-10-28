"""HTTP API + web app for Content DNA Analyzer.

    uv run dna serve            # http://127.0.0.1:8001  (docs at /docs)

POST /api/analyze          {"url", "genre": "auto"|<genre>, "start": 0, "seconds": 900, "critique": true} -> 202 job
POST /api/analyze/upload   multipart file (<= 256 MiB) + genre + start + seconds + critique            -> 202 job
GET  /api/jobs/{id}        status, stage, result (report JSON when done)
GET  /api/videos           analysed library
GET  /api/videos/{id}      full report for one video (fingerprint, timelines, critique)
GET  /api/genres           genres + how well 'auto' works (leave-one-out accuracy)
GET  /                     analyzer app;  /story  data story;  /reports/{id}  per-video HTML report
"""
from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import audio, fingerprint, genre, ingest, llm, perception, pipeline, report, visual

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
UPLOADS = ROOT / "data" / "uploads"
JOBS = ROOT / "data" / "jobs"
MAX_UPLOAD = 256 * 1024 * 1024
MAX_ACTIVE = 4
Genre = Literal["auto", "ad", "cooking", "explainer", "shorts", "tech_review", "vlog"]

app = FastAPI(title="Content DNA Analyzer", version="0.2.0",
              description="Creative fingerprint + evidence-checked, timestamped critique for a video. "
                          "Recommendations are hypotheses to test, not performance predictions.")
app.mount("/assets", StaticFiles(directory=WEB), name="assets")

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=2)


class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="YouTube URL (watch, shorts, youtu.be) or a local file path on the server")
    genre: Genre = Field("auto", description="Genre for benchmarking; 'auto' infers it from the fingerprint")
    start: float = Field(0, ge=0, description="Excerpt start in seconds (all report times are relative to it)")
    seconds: float = Field(900, gt=0, le=900, description="Excerpt length in seconds (max 15 min)")
    critique: bool = Field(True, description="Run the Claude critique (≈$0.04–0.10). False = fingerprint only")


def _save(job_id: str) -> None:
    JOBS.mkdir(parents=True, exist_ok=True)
    (JOBS / f"{job_id}.json").write_text(json.dumps({k: v for k, v in _jobs[job_id].items() if k != "result"}))


def _set(job_id: str, **kw):
    with _lock:
        _jobs[job_id].update(kw, updated=time.time())
        _save(job_id)


def _run(job_id: str, source: str, genre_in: str, do_critique: bool, start: float = 0, seconds: float = 900):
    try:
        _set(job_id, status="running", stage="download")
        src = ingest.resolve(source, start, seconds)
        _set(job_id, video_id=src.video_id, title=src.meta.get("title"))
        _set(job_id, stage="visual signals")
        vis = visual.analyse(src.video_path, src.workdir)
        _set(job_id, stage="audio + transcript")
        aud = audio.analyse(src.audio_path, src.workdir, src.video_id)
        _set(job_id, stage="vision timeline")
        per = perception.analyse(src, src.workdir)
        _set(job_id, stage="fingerprint")
        fp = fingerprint.compute(src.meta, vis, aud, per)
        g = {"genre": genre_in, "confidence": None, "method": "given by caller", "scores": {}}
        if genre_in == "auto":
            g = genre.predict(fp, is_short=bool(src.meta.get("is_short")), exclude=src.video_id)
        bins = fingerprint.timeline_bins(vis, aud, fp["duration_s"], pipeline.bin_size(fp["duration_s"]))
        m = src.meta
        feats = {"video_id": src.video_id, "category": g["genre"], "genre_inference": g, "title": m.get("title"),
                 "channel": m.get("channel"), "url": src.youtube_url, "views": m.get("view_count"),
                 "likes": m.get("like_count"), "comments": m.get("comment_count"),
                 "subscribers": m.get("channel_follower_count"), "upload_date": m.get("upload_date"),
                 "full_duration": m.get("duration"), "is_short": bool(m.get("is_short")), "fingerprint": fp,
                 "bins": bins, "perception_done": True}
        (src.workdir / "features.json").write_text(json.dumps(feats, indent=1))
        if src.video_path.exists():
            src.video_path.unlink()
        if not src.youtube_url and Path(source).parent == UPLOADS:
            Path(source).unlink(missing_ok=True)  # the analysed excerpt (playback.mp4) is all we keep
        if do_critique:
            _set(job_id, stage="critique")
            pipeline.run_critique(src.video_id)
        report.render(src.workdir)
        _set(job_id, status="done", stage="done", result=video_report(src.video_id))
    except llm.BudgetExceeded as e:
        _set(job_id, status="error", error=f"budget: {e}")
    except Exception as e:  # surface the failure to the caller
        _set(job_id, status="error", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])


def _new_job(source: str, genre_in: str, do_critique: bool, start: float, seconds: float, title: str | None = None) -> dict:
    with _lock:
        if sum(j["status"] in ("queued", "running") for j in _jobs.values()) >= MAX_ACTIVE:
            raise HTTPException(429, f"{MAX_ACTIVE} analyses are already queued or running; try again when one finishes")
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {"job_id": job_id, "status": "queued", "stage": "queued", "source": source, "title": title,
                         "genre": genre_in, "start": start, "seconds": seconds, "critique": do_critique,
                         "created": time.time(), "updated": time.time()}
        _save(job_id)
    _pool.submit(_run, job_id, source, genre_in, do_critique, start, seconds)
    return {"job_id": job_id, "status": "queued", "poll": f"/api/jobs/{job_id}"}


@app.post("/api/analyze", status_code=202, summary="Analyze a YouTube URL (or a file path on the server)")
def analyze(req: AnalyzeRequest):
    if not ingest.youtube_id(req.url) and not Path(req.url).expanduser().exists():
        raise HTTPException(400, "url must be a YouTube URL or an existing local file path")
    return _new_job(req.url, req.genre, req.critique, req.start, req.seconds)


@app.post("/api/analyze/upload", status_code=202, summary="Analyze an uploaded video file (max 256 MiB)")
async def analyze_upload(file: Annotated[UploadFile, File()], genre: Annotated[Genre, Form()] = "auto",
                         start: Annotated[float, Form(ge=0)] = 0, seconds: Annotated[float, Form(gt=0, le=900)] = 900,
                         critique: Annotated[bool, Form()] = True):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in (file.filename or "upload.mp4"))[-80:]
    dest = UPLOADS / f"{uuid.uuid4().hex[:8]}_{safe}"
    size = 0
    try:
        with dest.open("wb") as fh:  # stream to disk, refusing anything over the cap
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, "Upload exceeds 256 MiB")
                fh.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return _new_job(str(dest), genre, critique, start, seconds, title=Path(file.filename or "upload").stem)


@app.get("/api/jobs/{job_id}", summary="Job status and, when done, the report")
def get_job(job_id: str):
    if not job_id.isalnum():
        raise HTTPException(404, "unknown job")
    job = _jobs.get(job_id)
    if job:
        return job
    p = JOBS / f"{job_id}.json"  # survives server restarts
    if not p.exists():
        raise HTTPException(404, "unknown job")
    job = json.loads(p.read_text())
    if job["status"] in ("queued", "running"):
        job.update(status="error", error="The server restarted before this analysis finished. Submit it again.")
    elif job["status"] == "done" and job.get("video_id"):
        job["result"] = video_report(job["video_id"])
    return job


def _j(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def _clean(o):
    """NaN/inf are not valid JSON: send them as null."""
    if isinstance(o, float):
        return None if o != o or o in (float("inf"), float("-inf")) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def video_report(video_id: str) -> dict:
    """Everything the explorer needs for one video, compact (loudness at 1 s, transcript segments)."""
    wd = ingest.VIDEOS / video_id
    feats = _j(wd / "features.json")
    if not feats:
        raise HTTPException(404, "unknown video")
    vis, aud, per, crit = _j(wd / "visual.json"), _j(wd / "audio.json"), _j(wd / "perception.json"), _j(wd / "critique.json")
    L = aud["loudness"]
    step = max(1, int(round(1.0 / (L["t"][1] - L["t"][0]))) if len(L["t"]) > 1 else 1)
    meta = _j(wd / "meta.json") or {}
    out = {"video_id": video_id, "title": feats.get("title"), "channel": feats.get("channel"), "url": feats.get("url"),
           "youtube_id": ingest.youtube_id(feats.get("url") or ""), "genre": feats["category"],
           "start_offset": float(meta.get("start_offset") or 0),
           "media_url": f"/media/{video_id}/playback.mp4" if (wd / "playback.mp4").exists() else None,
           "genre_inference": feats.get("genre_inference"), "duration": feats["fingerprint"]["duration_s"],
           "views": feats.get("views"), "likes": feats.get("likes"), "fingerprint": feats["fingerprint"],
           "bins": feats["bins"], "cuts": [round(s, 2) for s, _ in vis["shots"][1:]],
           "loudness": {"t": L["t"][::step], "db": L["db"][::step]},
           "transcript": aud["transcript"]["segments"],
           "formats": [{k: s[k] for k in ("start_s", "end_s", "format", "face_visible", "on_screen_text")}
                       for s in (per or {}).get("segments", [])],
           "ctas": ((per or {}).get("overall") or {}).get("cta_moments", []),
           "hook_type": ((per or {}).get("hook") or {}).get("hook_type")}
    if crit:
        g = crit["grounding"]
        recs = []
        for i, r in enumerate(crit["recommendations"]):
            ch = [c for c in g["checks"] if c["owner"] == f"rec{i}"]
            recs.append({**{k: r[k] for k in ("title", "observation", "recommendation", "basis", "priority", "t_end_s")},
                         "t": r.get("t_snapped_s", r["t_start_s"]),
                         "evidence": [{k: c[k] for k in ("kind", "ref", "value", "verified")} for c in ch]})
        out["critique"] = {"summary": crit["summary"], "tags": crit["dna_tags"], "structure": crit["structure"],
                           "hook": crit["hook"], "strengths": crit["strengths"], "recommendations": recs,
                           "grounding": {k: g[k] for k in ("evidence_items", "evidence_verified", "recs", "recs_grounded")}}
    return _clean(out)


@app.get("/api/videos", summary="Analysed video library")
def list_videos():
    rows = []
    for p in sorted(ingest.VIDEOS.glob("*/features.json")):
        f = _j(p)
        rows.append({"video_id": f["video_id"], "title": f["title"], "channel": f.get("channel"), "genre": f["category"],
                     "duration": f["fingerprint"]["duration_s"], "has_critique": (p.parent / "critique.json").exists()})
    return sorted(rows, key=lambda r: (r["genre"], r["title"] or ""))


def _safe_id(video_id: str) -> str:
    if not video_id or not all(c.isalnum() or c in "-_@" for c in video_id):
        raise HTTPException(404, "unknown video")
    return video_id


@app.get("/api/videos/{video_id}", summary="Full report for one video")
def get_video(video_id: str):
    return video_report(_safe_id(video_id))


@app.get("/media/{video_id}/playback.mp4", include_in_schema=False)
def playback(video_id: str):
    p = ingest.VIDEOS / _safe_id(video_id) / "playback.mp4"
    if not p.exists():
        raise HTTPException(404, "no local playback for this video")
    return FileResponse(p, media_type="video/mp4")


_genre_eval = None


@app.get("/api/genres", summary="Genres and how reliable genre='auto' is")
def genres():
    global _genre_eval
    if _genre_eval is None:
        e = genre.evaluate()
        _genre_eval = {k: v for k, v in e.items() if k != "rows"}
    return {"genres": genre.GENRES, "auto": _genre_eval,
            "note": "auto uses fingerprint structure only; pass the genre when you know it"}


@app.get("/api/spend", summary="Estimated LLM spend so far")
def spend():
    return {"usd": round(llm.spent_usd(), 4), "budget_usd": llm.BUDGET_USD}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html")


@app.get("/story", response_class=HTMLResponse, include_in_schema=False)
def story():
    p = ROOT / "story" / "standalone.html"
    if not p.exists():
        raise HTTPException(404, "run analysis/build_standalone.py first")
    return HTMLResponse("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,"
                        "initial-scale=1'></head><body style='margin:0'>" + p.read_text() + "</body></html>")


@app.get("/reports/{video_id}", response_class=HTMLResponse, include_in_schema=False)
def html_report(video_id: str):
    p = ingest.VIDEOS / _safe_id(video_id) / "report.html"
    if not p.exists():
        raise HTTPException(404, "no report")
    return FileResponse(p)


def serve(host: str = "127.0.0.1", port: int = 8001):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
