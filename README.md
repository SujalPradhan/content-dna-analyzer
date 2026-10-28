# Content DNA Analyzer

Give it a YouTube URL or a video file. It measures how the video is **built**: pacing, hook, speech, sound, visual formats and narrative structure. From those measurements it produces a **creative fingerprint** and a critique. Every claim in the critique is timestamped, cites evidence, and is **checked against the measured data**.

```
uv sync
echo "API_KEY=<llm-foundry token>" > .env
uv run dna analyze "https://www.youtube.com/watch?v=jNQXAC9IVRw" --category vlog
open data/videos/jNQXAC9IVRw/report.html
```

## The product flow

1. **Video**: a ready-made demo, your own file, or a YouTube link.
2. **Target**: the genre you are making it for, and the goal (retention, reach and sharing, or both).
3. **Parameters**: pick from 16 researched drivers of retention and reach (`data/parameters.json`, written up with sources in `docs/parameters.md`), e.g. hook visual change, time to first voice, dead air, pacing, on-screen text, CTA timing, length fit, loop ending.

The three **demos are static**: `scripts/build_static_demos.py` bakes their reports, per-genre scorecards, frames and pre-generated fixes into `web/demo/`, so the demo flow needs no server, API call or compute (rerun it after changing the scorecard or critique). Uploads and YouTube links use the API.

The result is a **scorecard** (each parameter: problem / watch / good, with the measured value, the target, and whether that target is *sourced*, a *heuristic*, or the target genre's *corpus range*), **pain points pinned to the timeline**, a **frame-by-frame** strip (one keyframe per shot, red where a pain point falls) and, optionally, **fixes written by Claude** that focus on your goal and parameters and cite measured evidence. Checks are guidance to test, not predicted performance.

```
uv run dna serve            # http://127.0.0.1:8001 — analyzer app at /, data story at /story, OpenAPI docs at /docs
open "http://127.0.0.1:8001/#demo=s83EB_OtaEo&goal=both"   # deep link: opens a demo's results (its fixes are pre-generated)
```

| Method | Path | Body / result |
|---|---|---|
| POST | `/api/analyze` | `{"url", "genre": "auto" \| "ad" \| "cooking" \| "explainer" \| "shorts" \| "tech_review" \| "vlog", "goal": "retention" \| "virality" \| "both", "parameters": [ids], "start": 0, "seconds": 900, "critique": true}` → `202 {"job_id", "poll"}` |
| POST | `/api/analyze/upload` | multipart: `file`, `genre`, `goal`, `parameters` (comma-separated), `start`, `seconds`, `critique` → `202` |
| POST | `/api/videos/{id}/rerun` | re-score an analysed video for another genre / goal / parameters; `critique: true` adds focused fixes (~$0.05) |
| GET | `/api/jobs/{job_id}` | `status`, `stage`, and when done `result` = report + `scorecard` |
| GET | `/api/parameters` | the researched parameters, goals, evidence strength, genres, sources |
| GET | `/api/videos/{id}/scorecard?genre=&goal=&params=` | parameter checks + timestamped pain points (free, instant) |
| GET | `/api/videos/{id}/frames` | one keyframe per shot with the pain points inside it |
| GET | `/api/demos` · `/api/videos` · `/api/videos/{id}` | demo videos · library · full report |
| GET | `/api/genres` | genres and how reliable `"auto"` is |

New analyses and critiques spend LLM credit. The public demo caps that per day (`DNA_DAILY_BUDGET_USD`) and per visitor (`DNA_PAID_PER_IP_HOUR`, counting only runs that actually spent); the demo videos' fixes ship pre-generated in the LLM cache, so presenting them is free and instant. A private deployment can set `DNA_ACCESS_CODE` to require the header `X-Access-Code` instead.

```
curl -s -X POST localhost:8001/api/analyze -H 'Content-Type: application/json' \
     -d '{"url":"https://www.youtube.com/watch?v=Ml9Ojbl2uaw","genre":"auto"}'
curl -s localhost:8001/api/jobs/<job_id>
```

Jobs are saved to `data/jobs/` (a restarted server reports interrupted jobs instead of losing them); at most 4 run or wait at once (`429` beyond that); invalid windows return `422`. Report times are relative to the excerpt; `start_offset` locates it in the source, and the explorer adds it back when seeking YouTube. Uploads keep a 360p copy of the analysed excerpt for in-app playback.

**Genre.** Pass it when you know it; it sets which peers the critique compares against. With `"auto"`, vertical videos ≤ 60 s are Shorts. Everything else is matched to the nearest genre centroid of the 35-video corpus fingerprints, and the response includes the confidence and all scores. Leave-one-out accuracy is **69%** (chance 17%); see `results/eval/genre_eval.json` for per-genre recall. Ad-hoc analyses never change the corpus statistics or benchmarks.

**Explorer.** The app (and the story at `/story`) syncs a player (YouTube IFrame API for YouTube sources, HTML5 video for uploads) with the analysis lanes: story beats, visual format, cuts, speech, loudness and numbered recommendation pins. Click the timeline or any timestamp to jump the video. On claude.ai the YouTube embed is blocked, so the published story falls back to timestamp links.

## Deploy

- **API + app** on Google Cloud Run: `./scripts/deploy_cloudrun.sh` stores `API_KEY` (from `.env`) in Secret Manager, builds with Cloud Build and deploys one instance that scales to zero, with a $1/day and 3-runs-per-visitor-per-hour cap (override with `DAILY_BUDGET=` / `PER_HOUR=`).
- **Front end + data story** on GitHub Pages: `.github/workflows/pages.yml` publishes `/` (analyzer) and `/story/` on every push, pointing the front end at the repository variable `DNA_API_URL`.

Deployed limits: uploads ≤ 30 MB (Cloud Run request cap), the daily and per-visitor caps above, a $15 overall budget guard, and new analyses live on the instance's disk until it is recycled. YouTube may refuse downloads from cloud IPs; the demos and uploads do not depend on it.

## How it works

```
input (URL / file)
  │  ingest.py      yt-dlp → ≤480p mp4 (first 15 min) + 16 kHz mono audio + metadata
  ├─ visual.py      PySceneDetect AdaptiveDetector → shots; OpenCV @2 fps → brightness / colourfulness / motion     [local, free]
  ├─ audio.py       librosa → loudness, spectral flatness, onsets; whisper-1 → word-timestamped transcript          [~$0.006/min]
  ├─ perception.py  gemini-3.5-flash watches the video (YouTube URL passthrough, low media-res) → visual-format
  │                 timeline, on-screen text, faces, hook type, CTA moments  (times approximate, never used for cut timing)
  ├─ fingerprint.py 30 interpretable features (pacing, hook, speech, audio, visual, format, structure) + per-bin table
  ├─ critique.py    claude-sonnet-5 → structure segmentation, hook analysis, devices, strengths, 3-6 recommendations,
  │                 each with timestamp + evidence[metric|quote|visual] + basis label; then a VALIDATOR checks every
  │                 cited number / quote / visual against the measurements and snaps timestamps to measured events
  └─ report.py      self-contained HTML report
```

Design rules (from [docs/research.md](docs/research.md)):
- **Measure first, interpret second.** Cuts, loudness, speech rate and pauses are computed by signal processing; LLMs only interpret.
- **Every claim is checkable.** Each claim carries structured evidence; anything unverified is shown as ✗ in the report.
- **No performance claims.** Each recommendation's basis is labelled `measured_outlier_vs_corpus`, `internal_inconsistency` or `craft_heuristic`, and is framed as something to test.
- **No local ML models.** All neural inference goes through LLM Foundry APIs; local code is classical DSP only.

## Cost controls
Each video costs about $0.05–0.12 end to end (extraction about $0.03–0.10, critique about $0.04). The controls:
- A disk cache keyed by the canonical request, plus LLM Foundry's own response cache, so no call is paid for twice.
- Claude prompt caching: the stable system prompt (rubric, field definitions, corpus benchmarks) is cached, and critiques run sequentially so the cache stays warm.
- Gemini: static instructions go first (implicit prefix caching), with `MEDIA_RESOLUTION_LOW`, ≤1 fps sampling and a capped thinking budget.
- Compact inputs: the LLM sees per-bin tables, not raw curves.
- A ledger at `results/usage.csv` and a hard budget stop (`DNA_BUDGET_USD`, default $10). `uv run dna spend` shows the running total.

## Commands
| command | what it does |
|---|---|
| `dna analyze <url\|file> [--category c]` | full pipeline and HTML report for one video |
| `dna batch data/corpus.csv --stage extract\|critique\|all` | run the corpus (extraction runs in parallel; critique runs sequentially to keep the cache warm) |
| `dna benchmarks` | recompute corpus percentiles (used by the critique) |
| `python scripts/build_corpus.py` | rebuild the corpus reproducibly from YouTube search |
| `python analysis/analyze_corpus.py` | hypothesis tests, archetypes, energy arcs → `results/stats.json` |
| `python analysis/eval_shots.py` | shot-detector precision/recall vs manual labels |
| `python analysis/eval_critique.py` | grounding, ablation vs transcript-only baseline, blind judge, stability |
| `uv run pytest` | offline tests (synthetic clip with known cuts and silence; validator; API) |
| `python analysis/build_standalone.py` | rebuild the story page (`story/standalone.html`, `story/index.built.html`) |

## Results (35 public YouTube videos, 6 genres, 3.6 hours)

All numbers come from `results/` and are regenerated by the `analysis/` scripts. The data story is served live at `/story` by `dna serve` (with the synced YouTube player), and published as a private artifact: https://claude.ai/artifact/6zRu41y9sHAf588B821pda (`story/standalone.html`, data embedded, rebuilt by `analysis/build_standalone.py`). The same page with editable data sources is published as a Dashboard artifact: https://claude.ai/artifact/C6rJYdUi7WoNyLm4ocYGRe

**Findings (observational, n = 35, one video per channel, sampled from YouTube search across view tiers)**
1. **Each genre has its own editing grammar.** 7 of 19 features differ by genre after FDR correction (Kruskal-Wallis, BH q < 0.05). Median cuts per minute: ads 32.9 vs cooking 5.0. Median words per minute: tech reviews 176 vs vlogs 55.
2. **Openings also follow genre rules.** A median vlog waits 16.7 s before the first voice. Ads and Shorts open about 5 dB quieter than the rest of their runtime and then build; cooking videos open louder and settle.
3. **Archetypes cut across genres, but only loosely.** k-means gives 3 archetypes (speech-led, screen-and-graphics, ambient montage; silhouette 0.23, ARI vs genre 0.13); none is single-genre. The best k changed (4 → 3) when three hallucinated transcripts were removed, so treat them as tendencies.
4. **One engagement association survives, and it is not causal.** Talking-head share vs like rate, ranked within genre: ρ 0.64 (permutation p 0.001). It weakens to 0.46 after controlling for views and subscribers. It is confounded by creator-led audiences, and the analyzer never recommends it.

**Evaluation**
| Check | Result |
|---|---|
| Cut detector vs hand labels (4 clips, 85 cuts, ±1 s) | precision 0.83, recall 0.80; weak on morphs and motion graphics |
| Gemini timeline vs measured cuts | 14/35 timelines stretched by ~1.64× (MM:SS written as a decimal). After the fix: 0/35, and the boundary hit rate rose from 0.57 to 0.875 |
| Critique evidence verified by validator | 584/616 items (95%); 174/174 recommendations have ≥1 verified item |
| Ablation vs transcript-only baseline (12 videos) | verified evidence 96% vs 82%; 3.5 vs 2.0 evidence items per recommendation |
| Blind judge (Claude Opus 4.8, 12 videos) | preferred Content DNA 12–0. The judge saw the measured data, so treat this as weak support |
| Whisper transcripts vs. hallucination screen | 3/35 flagged: 2 music-only videos produced wrong-script gibberish or a stock \"Thank you for watching!\" (rejected), 1 vlog had 3 invented segments (dropped); critiques re-run on clean transcripts |
| Stability on re-run (5 videos, proxy cache bypassed) | structure labels agree on 69% of seconds; recommendation moments recur (within 10 s / 5%); free-text tags rarely repeat |

**Limitations:** no retention data (like rate is a weak proxy); the corpus is small and not representative; sung lyrics count as voice; 98 of 174 recommendations are "outlier vs corpus", which pulls videos toward their genre's middle; a single annotator made the cut labels; the vision model's format labels are approximate. Full list in the story.

**Cost:** about $0.12 per video for one full pass; $6.77 for the whole project, including evaluation, re-runs after each fix and API testing.
