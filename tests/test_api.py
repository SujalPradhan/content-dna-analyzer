"""API tests against the analysed corpus on disk. No analysis jobs are started, so no API cost."""
import json
import math

import pytest
from fastapi.testclient import TestClient

from content_dna import ingest
from content_dna.server import app

pytestmark = pytest.mark.skipif(not any(ingest.VIDEOS.glob("*/features.json")), reason="no analysed videos on disk")
client = TestClient(app)


def test_genres_reports_auto_accuracy():
    r = client.get("/api/genres").json()
    assert set(r["genres"]) == {"ad", "cooking", "explainer", "shorts", "tech_review", "vlog"}
    assert 0 <= r["auto"]["loo_accuracy"] <= 1 and r["auto"]["n"] >= 6


def test_video_report_is_strict_json_and_complete():
    vid = client.get("/api/videos").json()[0]["video_id"]
    r = client.get(f"/api/videos/{vid}")
    assert r.status_code == 200
    body = json.loads(r.text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))  # NaN/Infinity rejected
    for k in ("fingerprint", "cuts", "loudness", "transcript", "formats", "bins"):
        assert k in body
    assert all(not (isinstance(v, float) and math.isnan(v)) for v in body["fingerprint"].values())


def test_rejects_non_youtube_url():
    r = client.post("/api/analyze", json={"url": "https://example.com/video.mp4"})
    assert r.status_code == 400


def test_rejects_unknown_genre():
    r = client.post("/api/analyze", json={"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "genre": "opera"})
    assert r.status_code == 422


def test_unknown_job_and_video_404():
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/videos/nope").status_code == 404
