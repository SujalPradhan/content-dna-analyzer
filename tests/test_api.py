"""API tests against the analysed corpus on disk. No analysis jobs are started, so no API cost."""
import json
import math
import time

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


def test_parameters_catalogue_is_sourced():
    ps = client.get("/api/parameters").json()["parameters"]
    assert len(ps) >= 10
    for p in ps:
        assert p["goal"] in ("retention", "virality", "both") and p["genres"] and p["sources"]


def test_scorecard_filters_by_goal_and_genre():
    vid = "s83EB_OtaEo"
    if not (ingest.VIDEOS / vid / "features.json").exists():
        pytest.skip("demo video not analysed")
    sc = client.get(f"/api/videos/{vid}/scorecard?genre=explainer&goal=virality").json()
    assert sc["genre"] == "explainer"
    assert all(p["goal"] in ("virality", "both") for p in sc["parameters"])
    assert all(p["id"] != "brand_timing" for p in sc["parameters"])  # ads only
    assert sum(sc["counts"].values()) == len(sc["parameters"])
    assert all(f["t"] >= 0 for f in sc["pain_points"])
    assert client.get(f"/api/videos/{vid}/scorecard?params=nope").status_code == 400


def test_frames_mark_pain_points_per_shot():
    vid = "Ml9Ojbl2uaw"
    if not (ingest.VIDEOS / vid / "visual.json").exists():
        pytest.skip("demo video not analysed")
    shots = client.get(f"/api/videos/{vid}/frames?genre=explainer").json()["shots"]
    assert shots and shots[0]["start"] == 0
    assert all(s["end"] > s["start"] for s in shots)


def test_spending_endpoints_need_the_access_code(monkeypatch):
    from content_dna import server
    monkeypatch.setattr(server, "ACCESS_CODE", "secret")
    assert client.post("/api/videos/s83EB_OtaEo/rerun", json={"critique": True}).status_code == 401
    assert client.post("/api/videos/s83EB_OtaEo/rerun", json={"critique": False}).status_code == 202  # re-scoring is free
    assert client.post("/api/analyze", json={"url": "https://youtu.be/jNQXAC9IVRw"}).status_code == 401


def test_public_demo_caps_spending_per_visitor_and_per_day(monkeypatch, tmp_path):
    from content_dna import quota, server
    monkeypatch.setattr(server, "ACCESS_CODE", None)
    monkeypatch.setattr(quota, "LOCAL", tmp_path / "quota.json")
    monkeypatch.setattr(server, "PAID_PER_IP_HOUR", 1)
    monkeypatch.setitem(server._paid_hits, "testclient", [time.time()])  # this visitor already ran one this hour
    assert client.post("/api/videos/s83EB_OtaEo/rerun", json={"critique": True}).status_code == 429
    assert client.post("/api/videos/s83EB_OtaEo/rerun", json={"critique": False}).status_code == 202  # free
    monkeypatch.setattr(server, "PAID_PER_IP_HOUR", 0)
    monkeypatch.setattr(quota, "DAILY_VIDEOS", 5)
    monkeypatch.setattr(quota, "DAILY_BUDGET_USD", 1.0)
    monkeypatch.setattr(quota, "EST_RUN_USD", 0.2)
    days = [quota.admit() for _ in range(5)]  # five worst-case runs fit the dollar budget exactly
    r = client.post("/api/analyze", json={"url": "https://youtu.be/jNQXAC9IVRw"})
    assert r.status_code == 429 and "5 free video analyses" in r.json()["detail"]
    quota.settle(days[0], 0.0, refund=True)  # a run that failed before spending gives its slot back
    assert quota.status()["videos_left_today"] == 1


def test_quota_reserves_worst_case_cost_up_front(monkeypatch, tmp_path):
    from content_dna import quota
    monkeypatch.setattr(quota, "LOCAL", tmp_path / "quota.json")
    monkeypatch.setattr(quota, "DAILY_VIDEOS", 0)
    monkeypatch.setattr(quota, "DAILY_BUDGET_USD", 0.5)
    monkeypatch.setattr(quota, "EST_RUN_USD", 0.2)
    a, b = quota.admit(), quota.admit()  # 0.4 reserved
    with pytest.raises(quota.QuotaExceeded):
        quota.admit()  # a third could overrun mid-way, so it is refused before it starts
    quota.settle(a, 0.05)  # real cost far below the reservation frees room
    quota.admit()
