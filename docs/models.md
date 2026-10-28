# Model choices (probed 2026-10-27)

All neural inference goes through **LLM Foundry** (`llmfoundry.straivedemo.com`), which proxies Anthropic, Gemini and OpenAI behind one token. The AI Pipe token works too, but it carries a $1 per 7 days limit, so it is a fallback only. No model runs locally.

Each candidate was tested with one tiny call before any pipeline code was written:

| Stage | Model | Probe result | Notes |
|---|---|---|---|
| Word-timestamped transcript | `whisper-1` (`verbose_json`, word + segment granularity) | ✅ word timings, 1.1 s for 7 s of audio | about $0.006/min. `gemini-3.5-transcribe` returned text only (no timestamps, no JSON mode). |
| Video understanding | `gemini-3.5-flash` | ✅ inline mp4 · ✅ YouTube URL `file_data` passthrough (19 s video = 1,676 tokens) | Cut times on a synthetic clip were 0.2–0.3 s early, so cut timing comes from PySceneDetect instead. |
| Critique | `claude-sonnet-5`, effort `medium` | ✅ vision, structured output, **prompt caching** (8,229 tokens read from cache on the 2nd call) | At effort `high` a critique emitted about 9k output tokens ($0.10). At `medium` it emitted about 4.5k ($0.076) with similar specificity on a spot check. |
| Blind judge | `claude-opus-4-8`, effort `medium` | ✅ | `claude-opus-5-5`, `claude-opus-5` and `claude-fable-5-1` appear in `/models` but return "not enabled on LLM Foundry". |

## Issues found and fixed

1. **Non-streaming long outputs stalled through the proxy.** A 12k-max-token structured request hung for more than 4 minutes. Switching to `messages.stream(...).get_final_message()` fixed it.
2. **Gemini numeric timestamps.** With `start_s: number` in the schema, Gemini wrote 11:43.6 as `1143.6` in 14 of 35 videos, so those timelines ran about 1.64× longer than the video. Asking for `"MM:SS.s"` strings and parsing them locally fixed every case. After the fix, the median share of Gemini segment boundaries within 1 s of a measured cut went from 0.57 to 0.875 (`analysis/eval_perception.py`).
3. **Validator parsing bugs** (our own code, not the models'):
   - bin evidence written as `"cuts 3, wpm 150"` was not parsed;
   - Devanagari quotes lost their combining vowel marks during tokenisation;
   - quotes containing "…" were matched as one string;
   - a falsy-zero bug made the 0 s bin unreachable.

   All four are fixed and covered by tests. Scores from before the fix are kept as `grounding_v1` in each critique file.
