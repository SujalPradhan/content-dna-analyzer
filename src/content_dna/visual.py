"""Deterministic visual signals: shot boundaries, keyframes, brightness/colour/motion curves."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from scenedetect import AdaptiveDetector, detect

SAMPLE_FPS = 2.0


def detect_shots(video: Path) -> list[tuple[float, float]]:
    scenes = detect(str(video), AdaptiveDetector(adaptive_threshold=3.0, min_scene_len=8))
    if not scenes:
        cap = cv2.VideoCapture(str(video))
        dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 25)
        cap.release()
        return [(0.0, dur)]
    return [(s.seconds, e.seconds) for s, e in scenes]


def _colorfulness(img: np.ndarray) -> float:
    # Hasler & Süsstrunk (2003) colourfulness metric
    b, g, r = [c.astype(np.float32) for c in cv2.split(img)]
    rg, yb = r - g, 0.5 * (r + g) - b
    return float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))


def frame_curves(video: Path) -> dict:
    """Sample frames at SAMPLE_FPS: brightness, colourfulness, motion (mean abs diff of greyscale)."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(round(fps / SAMPLE_FPS)))
    t, bright, color, motion = [], [], [], []
    prev, i = None, 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            small = cv2.resize(frame, (160, 90))
            grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
            t.append(round(i / fps, 2))
            bright.append(float(grey.mean() / 255))
            color.append(_colorfulness(small))
            motion.append(float(np.abs(grey - prev).mean() / 255) if prev is not None else 0.0)
            prev = grey
        i += 1
    cap.release()
    return {"t": t, "brightness": bright, "colorfulness": color, "motion": motion}


def save_keyframes(video: Path, shots: list[tuple[float, float]], outdir: Path, width: int = 320) -> list[str]:
    """One JPEG at each shot's midpoint. Returns relative paths."""
    outdir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    paths = []
    for k, (s, e) in enumerate(shots):
        cap.set(cv2.CAP_PROP_POS_MSEC, (s + e) / 2 * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        h = int(frame.shape[0] * width / frame.shape[1])
        p = outdir / f"shot_{k:04d}.jpg"
        cv2.imwrite(str(p), cv2.resize(frame, (width, h)), [cv2.IMWRITE_JPEG_QUALITY, 70])
        paths.append(p.name)
    cap.release()
    return paths


def hook_frames(video: Path, outdir: Path, seconds: float = 15, n: int = 6, width: int = 320) -> list[Path]:
    """Evenly spaced frames from the opening `seconds` (for hook critique)."""
    outdir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    out = []
    for k in range(n):
        ts = (k + 0.5) * seconds / n
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
        ok, frame = cap.read()
        if not ok:
            break
        h = int(frame.shape[0] * width / frame.shape[1])
        p = outdir / f"hook_{ts:05.1f}s.jpg"
        cv2.imwrite(str(p), cv2.resize(frame, (width, h)), [cv2.IMWRITE_JPEG_QUALITY, 70])
        out.append(p)
    cap.release()
    return out


def analyse(video: Path, workdir: Path) -> dict:
    cache = workdir / "visual.json"
    if cache.exists():
        return json.loads(cache.read_text())
    shots = detect_shots(video)
    curves = frame_curves(video)
    keyframes = save_keyframes(video, shots, workdir / "keyframes")
    hook_frames(video, workdir / "hook")
    out = {"shots": [[round(s, 2), round(e, 2)] for s, e in shots], "keyframes": keyframes, "curves": curves}
    cache.write_text(json.dumps(out))
    return out
