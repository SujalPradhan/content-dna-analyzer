"""Resolve a YouTube URL or local file into a working directory with video, audio and metadata."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIDEOS = ROOT / "data" / "videos"
RAW = ROOT / "data" / "raw"
MAX_ANALYSIS_S = 15 * 60  # analyse at most the first 15 minutes

YT_RE = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/|live/)|youtu\.be/)([\w-]{11})")


@dataclass
class Source:
    video_id: str
    workdir: Path
    video_path: Path
    audio_path: Path
    meta: dict
    youtube_url: str | None


def youtube_id(src: str) -> str | None:
    m = YT_RE.search(src)
    return m.group(1) if m else None


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def _probe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def _download_youtube(vid: str, url: str, workdir: Path) -> tuple[Path, dict]:
    import yt_dlp

    RAW.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480]/bv*[height<=480]+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(RAW / f"{vid}.%(ext)s"),
        "quiet": True, "no_warnings": True, "noprogress": True,
        "js_runtimes": {"node": {}},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    path = next(RAW.glob(f"{vid}.*mp4"), None) or Path(ydl.prepare_filename(info))
    keep = ["id", "title", "channel", "channel_id", "channel_follower_count", "uploader", "upload_date", "duration",
            "view_count", "like_count", "comment_count", "categories", "tags", "description", "width", "height",
            "fps", "language", "chapters", "webpage_url"]
    meta = {k: info.get(k) for k in keep}
    meta["description"] = (meta.get("description") or "")[:2000]
    meta["is_short"] = "/shorts/" in url or (info.get("duration") or 999) <= 60 and (info.get("height") or 0) > (info.get("width") or 1)
    return path, meta


def resolve(src: str, start: float = 0.0, seconds: float | None = None) -> Source:
    """Download / copy the input, cut the analysis window [start, start+seconds) (default: first 15 min),
    extract mono 16 kHz audio and write meta.json. Idempotent. Times in all outputs are relative to `start`."""
    start, seconds = max(0.0, float(start or 0)), min(float(seconds or MAX_ANALYSIS_S), MAX_ANALYSIS_S)
    vid = youtube_id(src)
    if vid:
        url = f"https://www.youtube.com/watch?v={vid}"
    else:
        p = Path(src).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(src)
        vid = re.sub(r"[^\w-]", "_", p.stem)[:40] + "_" + hashlib.sha1(str(p).encode()).hexdigest()[:6]
        url = None
    if start > 0 or seconds < MAX_ANALYSIS_S:  # a custom window is its own analysis
        vid = f"{vid}@{int(start)}-{int(start + seconds)}"
    workdir = VIDEOS / vid
    workdir.mkdir(parents=True, exist_ok=True)
    meta_path = workdir / "meta.json"
    audio = workdir / "audio.mp3"
    video = workdir / "video.mp4"

    # Skip work if already ingested (the video may have been deleted after feature extraction to save disk).
    if not (meta_path.exists() and audio.exists() and (video.exists() or (workdir / "visual.json").exists())):
        if url:
            raw, meta = _download_youtube(vid, url, workdir)
            if "/shorts/" in src:
                meta["is_short"] = True
        else:
            raw, meta = Path(src).expanduser().resolve(), {"id": vid, "title": Path(src).stem}
        # Normalise to <=480p, constant 25 fps-friendly mp4 limited to the analysis window.
        _ffmpeg("-ss", str(start), "-i", str(raw), "-t", str(seconds), "-vf", "scale=-2:'min(480,ih)'", "-c:v", "libx264",
                "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", str(video))
        _ffmpeg("-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(audio))
        if not url:  # uploads have no online player: keep a small copy of the excerpt for in-app playback
            _ffmpeg("-i", str(video), "-vf", "scale=-2:'min(360,ih)'", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "31", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(workdir / "playback.mp4"))
        if url and raw.exists():
            raw.unlink()
        meta["analysed_duration"] = _probe_duration(video)
        meta["start_offset"] = start
        meta["source"] = src
        meta_path.write_text(json.dumps(meta, indent=1))
    meta = json.loads(meta_path.read_text())
    return Source(vid, workdir, video, audio, meta, url)


def load(video_id: str) -> Source:
    """Reopen an already-ingested analysis by id (works for custom windows and uploads)."""
    workdir = VIDEOS / video_id
    meta = json.loads((workdir / "meta.json").read_text())
    src = meta.get("source") or ""
    yid = youtube_id(src)
    return Source(video_id, workdir, workdir / "video.mp4", workdir / "audio.mp3", meta,
                  f"https://www.youtube.com/watch?v={yid}" if yid else None)
