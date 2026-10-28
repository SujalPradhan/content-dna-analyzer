"""Offline tests: deterministic extractors on a synthetic clip with known ground truth, and the grounding validator.
No API calls are made."""
import subprocess

import pytest

from content_dna import audio, critique, fingerprint, visual


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    """9 s clip: three visually distinct 3 s shots (cuts at 3.0 and 6.0); tone for 0-4 s, silence 4-9 s."""
    d = tmp_path_factory.mktemp("clip")
    out = d / "clip.mp4"
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=3",
        "-f", "lavfi", "-i", "color=c=red:size=320x240:rate=25:duration=3",
        "-f", "lavfi", "-i", "mandelbrot=size=320x240:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-filter_complex",
        "[2:v]trim=duration=3,setpts=PTS-STARTPTS[m];[0:v][1:v][m]concat=n=3:v=1[v];"
        "[4:a]atrim=duration=5[s];[3:a][s]concat=n=2:v=0:a=1[a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)], check=True)
    mp3 = d / "clip.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(out), "-ac", "1", "-ar", "16000", str(mp3)], check=True)
    return out, mp3


def test_shot_detection_finds_known_cuts(clip):
    shots = visual.detect_shots(clip[0])
    cuts = [s for s, _ in shots[1:]]
    assert len(cuts) == 2
    assert cuts[0] == pytest.approx(3.0, abs=0.2)
    assert cuts[1] == pytest.approx(6.0, abs=0.2)


def test_frame_curves_sampling(clip):
    c = visual.frame_curves(clip[0])
    assert len(c["t"]) == pytest.approx(9 * visual.SAMPLE_FPS, abs=2)
    red = [cf for t, cf in zip(c["t"], c["colorfulness"]) if 3.5 < t < 5.5]
    assert min(red) > 50  # a solid red frame is very colourful


def test_loudness_detects_silence(clip):
    L = audio.loudness(clip[1])
    tone = [d for t, d in zip(L["t"], L["db"]) if 0.5 < t < 3.5]
    silent = [d for t, d in zip(L["t"], L["db"]) if 5 < t < 8.5]
    assert min(tone) > -30 and max(silent) < -60


def _fake_inputs(clip):
    vis = {"shots": [[0, 3], [3, 6], [6, 9]], "curves": visual.frame_curves(clip[0])}
    words = [{"w": w, "s": 0.5 + i * 0.4, "e": 0.8 + i * 0.4} for i, w in
             enumerate("welcome back today we test three cameras do you know why".split())]
    aud = {"loudness": audio.loudness(clip[1]),
           "transcript": {"text": "welcome back today we test three cameras do you know why?", "words": words,
                          "segments": [{"s": 0.5, "e": 4.8, "text": "welcome back today we test three cameras do you know why?"}]}}
    per = {"segments": [{"start_s": 0, "end_s": 3, "format": "talking_head", "face_visible": True, "on_screen_text": "HI",
                         "description": ""},
                        {"start_s": 3, "end_s": 9, "format": "b_roll", "face_visible": False, "on_screen_text": "",
                         "description": ""}],
           "hook": {"text_overlay_first_3s": True}, "overall": {"cta_moments": [{"t_s": 7.0, "kind": "subscribe_like", "text": ""}]}}
    meta = {"analysed_duration": 9.0}
    return meta, vis, aud, per


def test_fingerprint_values(clip):
    meta, vis, aud, per = _fake_inputs(clip)
    fp = fingerprint.compute(meta, vis, aud, per)
    assert list(fp) == list(fingerprint.FIELDS)
    assert fp["shots_per_min"] == pytest.approx(2 / 0.15, rel=0.01)
    assert fp["hook_cuts"] == 2
    assert fp["time_to_first_word_s"] == 0.5
    assert fp["talking_head_share"] == pytest.approx(1 / 3, abs=0.01)
    assert fp["face_share"] == pytest.approx(1 / 3, abs=0.01)
    assert fp["questions_per_min"] == pytest.approx(1 / 0.15, rel=0.01)
    assert fp["cta_count"] == 1 and fp["first_cta_pos"] == pytest.approx(7 / 9, abs=0.01)


def test_validator_accepts_true_and_rejects_fabricated_evidence(clip):
    meta, vis, aud, per = _fake_inputs(clip)
    fp = fingerprint.compute(meta, vis, aud, per)
    bins = fingerprint.timeline_bins(vis, aud, 9.0, 5.0)
    result = {"strengths": [], "recommendations": [
        {"t_start_s": 0.6, "t_end_s": 2.0, "evidence": [
            {"kind": "metric", "ref": "hook_cuts", "value": "2"},
            {"kind": "quote", "ref": "", "value": "today we test three cameras"},
            {"kind": "visual", "ref": "3", "value": "b-roll"}]},
        {"t_start_s": 4.0, "t_end_s": 5.0, "evidence": [
            {"kind": "metric", "ref": "hook_cuts", "value": "7"},
            {"kind": "quote", "ref": "", "value": "smash that like button right now"},
            {"kind": "metric", "ref": "made_up_metric", "value": "1"}]},
        {"t_start_s": 99.0, "t_end_s": 100.0, "evidence": [{"kind": "metric", "ref": "hook_cuts", "value": "2"}]}]}
    g = critique.validate(result, fp, bins, aud, per, vis)
    verdicts = [c["verified"] for c in g["checks"]]
    assert verdicts == [True, True, True, False, False, False, True]
    assert g["recs_grounded"] == 1  # rec 3 has true evidence but an out-of-range timestamp
    assert result["recommendations"][0]["t_snapped_s"] == 0.5  # snapped to first word onset


def test_schema_is_strict():
    def walk(s):
        if isinstance(s, dict):
            if s.get("type") == "object":
                assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
            for v in s.values():
                walk(v)
        elif isinstance(s, list):
            for v in s:
                walk(v)
    walk(critique.SCHEMA)


def test_validator_parsing_fixes(clip):
    meta, vis, aud, per = _fake_inputs(clip)
    aud["transcript"]["words"] += [{"w": w, "s": 5.0 + i * 0.3, "e": 5.2 + i * 0.3} for i, w in
                                   enumerate("दो दिन पहले मैंने कैशीफाई से लेप्टॉप ऑर्डर किया".split())]
    fp = fingerprint.compute(meta, vis, aud, per)
    bins = fingerprint.timeline_bins(vis, aud, 9.0, 5.0)
    b0 = bins[0]
    result = {"strengths": [], "recommendations": [{"t_start_s": 5.0, "t_end_s": 8.0, "evidence": [
        {"kind": "quote", "ref": "", "value": "दो दिन पहले मैंने कैशीफाई"},                       # Devanagari with combining marks
        {"kind": "metric", "ref": "bin:0.0", "value": f"cuts {b0['cuts']}, wpm {b0['wpm']:g}"},  # labelled pairs
        {"kind": "metric", "ref": "bin:0", "value": f"cuts {b0['cuts'] + 5}, wpm {b0['wpm']:g}"},  # one pair wrong
        {"kind": "metric", "ref": "bin:0", "value": f"loud_db {b0['loud_db']}"},                 # negative value
        {"kind": "quote", "ref": "", "value": "today we test... do you know why"},                # ellipsis fragments
        {"kind": "quote", "ref": "", "value": "today we test... buy our course now please"}]}]}
    g = critique.validate(result, fp, bins, aud, per, vis)
    assert [c["verified"] for c in g["checks"]] == [True, True, False, True, True, False]


def test_transcript_quality_rejects_hallucinations():
    from content_dna.audio import transcript_quality
    assert transcript_quality("ლ ლლლი ლელილი მლყგოი ოველემეოი რიტსვ", "javanese")[0] == "rejected"
    assert transcript_quality("Thank you for watching!", "english")[0] == "rejected"
    assert transcript_quality("दो दिन पहले मैंने कैशीफाई से एक लेप्टॉप ओडर किया", "hindi")[0] == "ok"
    assert transcript_quality("Welcome back, today we test three cameras.", "english")[0] == "ok"
    assert transcript_quality("AI magic friends se apnader shagatam", "bengali")[0] == "ok"  # romanised is fine
