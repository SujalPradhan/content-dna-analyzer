"""Bake the demo videos into static files so the demo flow needs no API, LLM call or compute.

    uv run python scripts/build_static_demos.py

Writes web/demo/index.json (demo list + parameter catalogue) and, per demo, web/demo/<id>.json: the full report
(with the goal-focused fixes from critique_focus.json), the scorecard for every target genre with all parameters
(the page filters by goal and selection in the browser, since each parameter is scored independently) and the shot
list, plus the keyframes in web/demo/<id>/. Rerun after changing the scorecard, critique or demo list.
"""
import json
import shutil
from pathlib import Path

from content_dna import ingest, scorecard
from content_dna.server import _clean, demos, parameters, video_report

OUT = Path(__file__).resolve().parents[1] / "web" / "demo"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ds = demos()
    (OUT / "index.json").write_text(json.dumps({"demos": ds, "parameters": parameters()["parameters"]}))
    for d in ds:
        vid = d["video_id"]
        wd = ingest.VIDEOS / vid
        if not (wd / "critique_focus.json").exists():
            raise SystemExit(f"{vid}: run the demo once with fixes on (POST /api/videos/{vid}/rerun, critique=true) first")
        vis = json.loads((wd / "visual.json").read_text())
        frames = OUT / vid
        shutil.rmtree(frames, ignore_errors=True)
        frames.mkdir()
        shots = []
        for i, (s, e) in enumerate(vis["shots"]):
            name = vis["keyframes"][i] if i < len(vis["keyframes"]) else None
            if name and (wd / "keyframes" / name).exists():
                shutil.copy(wd / "keyframes" / name, frames / name)
            shots.append({"shot": i, "start": round(s, 2), "end": round(e, 2), "length": round(e - s, 2),
                          "image": f"assets/demo/{vid}/{name}" if name else None})
        cards = {g: scorecard.evaluate(vid, g, None, "both") for g in scorecard.GENRES}
        body = {"report": video_report(vid, focus=True), "scorecards": cards, "shots": shots,
                "fixes_for": {"genre": d["genre"], "goal": "both"}}
        (OUT / f"{vid}.json").write_text(json.dumps(_clean(body), allow_nan=False))
        print(vid, len(shots), "shots", sum(len(c["parameters"]) for c in cards.values()), "parameter scores")


if __name__ == "__main__":
    main()
