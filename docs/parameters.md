# Content DNA Analyzer: Retention and Reach Parameters

*Compiled 2026-10-28. Machine-readable version: [`data/parameters.json`](../data/parameters.json). This document builds on [`docs/research.md`](research.md).*

## 1. Method

1. **Sources.** I searched for primary sources first: YouTube Help and the YouTube Official Blog, Google's ABCD reference guide, TikTok for Business, and Meta Business Help. I then looked for peer-reviewed studies on attention, pacing, engagement and sharing. Practitioner material (the leaked MrBeast production document) and vendor analytics (Wistia) are used only as supporting evidence and are labelled as such. Wherever a page's wording could not be read directly, the text says so.
2. **Evidence labels.**
   - **platform-official**: published by YouTube, Google, TikTok or Meta. These figures are usually correlational or modelled, and the platforms have a stake in them.
   - **experimental**: controlled or field studies in peer-reviewed venues.
   - **observational**: correlational data, whether academic or from a vendor.
   - **practitioner**: guidance from creators or agencies.
3. **Mapping to signals.** Each parameter is tied to the signals the pipeline already computes (see `src/content_dna/fingerprint.py`) and to the per-second timeline (shots, words, loudness, format, story beats).
4. **Thresholds.** A threshold is marked `heuristic: false` only when a source states that number. Every other number is a heuristic and is marked as one. Where no number is defensible, the rule gives a direction only and points to the genre ranges in `results/benchmarks.json`.
5. **Corpus reference ranges.** `results/benchmarks.json` holds p25/median/p75 for 35 videos, about 6 per genre. These ranges are **descriptive only**. They describe how videos in that genre are typically made. They are not tied to outcomes, and they are not targets.

## 2. Key evidence at a glance

| Finding | Source | Strength |
|---|---|---|
| YouTube's long-form "intro" metric is the share of viewers still watching at **30 s**. YouTube links a weak intro to a mismatch with the title and thumbnail. "Dips" mark skipped or abandoned moments, and YouTube advises moving compelling content earlier because audiences shrink over a video. | [YouTube Help](https://support.google.com/youtube/answer/9314415?hl=en) | platform-official |
| YouTube's recommender uses clicks, watch time, **"valued watchtime"** from satisfaction surveys, **shares**, likes and dislikes. | [YouTube Blog, Goodrow, 2021-09-15](https://blog.youtube/inside-youtube/on-youtubes-recommendation-system/) | platform-official |
| ABCD for ads recommends: surprising visuals early; tightly framed people or product at the start; **"more than two frames in the first five seconds"**; open with people on screen, ideally speaking directly to the viewer; **brand in the first five seconds** (visual or audio); a specific CTA that is both **audible and visible**; urgency ("limited"). Google states that the guidance is "backed by correlational data". | [ABCD reference guide, 2019-11](https://services.google.com/fh/files/misc/youtube_google_abcd_reference_guide_en.pdf) | platform-official |
| Ads following ABCD showed **+30% short-term sales likelihood and +17% long-term brand contribution**. These figures are *modelled* by Kantar LINK AI across 11,000 ads and 180 features, not measured in market. | [Kantar](https://www.kantar.com/industries/technology-and-telecoms/validating-googles-abcd-framework-with-the-power-of-artificial-intelligence) | platform-official (modelled) |
| TikTok advises introducing the content proposition in the **first 3 s** and the hook within **6 s**, and using captions or text overlays at **5–10 words per second**. | [TikTok Ads Help](https://ads.tiktok.com/help/article/creative-best-practices) (reported updated 2025-06; I could not fetch it directly, so the wording comes from search snippets) | platform-official |
| For TikTok ads, the first 6 s capture about **90% of ad-recall impact** and the first 2 s about **50% of impact**. Featuring real people is associated with **+9%** watch time, trend remixing with +14%, and storytelling with +16%. | [Creative Codes PDF, 2023-05](https://www.tiktok.com/business/library/Creative_Codes_May_2023.pdf); [Social Media Today, 2023-09-27](https://www.socialmediatoday.com/news/tiktok-shares-new-notes-on-how-to-maximize-ad-effectiveness-in-the-app/694989/) | platform-official |
| 88% of TikTok users say sound is essential to the experience. This is a platform-funded survey by Kantar (2021). | [TikTok for Business blog](https://ads.tiktok.com/business/tr/blog/kantar-report-how-brands-are-making-noise-and-driving-impact-with-sound-on-tiktok) | platform-official (survey) |
| Shorts may be up to **3 minutes** (since 2024-10-15). Since 2025-03-31 a Shorts view counts on each start or replay, and the old metric is now called "engaged views". | [YouTube Blog](https://blog.youtube/news-and-events/tall-updates-coming-to-shorts/); [TechCrunch](https://techcrunch.com/2025/03/26/youtube-is-changing-how-youtube-shorts-views-are-counted) | platform-official / news |
| Content evoking **high-arousal** emotion (awe, anger, anxiety) is shared more; low-arousal sadness is shared less. | [Berger & Milkman, JMR 2012](https://faculty.wharton.upenn.edu/wp-content/uploads/2011/11/Virality.pdf) | experimental + field |
| In video ads: amusement, excitement, inspiration and warmth increase sharing; information-focused content and **prominent (early, long, persistent) branding reduce sharing**; sharing peaks at **1.2–1.7 min** ad length. | [Tellis et al., J. Marketing 2019 (AMA summary)](https://www.ama.org/2020/06/11/what-drives-virality-sharing-of-online-digital-content-the-critical-role-of-information-emotion-and-brand-prominence/) | observational field + validation |
| **Pulsing** brand exposure (intermittent, same total time) significantly reduced zapping of commercials. | [Teixeira, Wedel & Pieters, Marketing Science 2010](https://econpapers.repec.org/RePEc:inm:ormksc:v:29:y:2010:i:5:p:783-804) | experimental (eye tracking + zapping) |
| Hollywood average shot length fell from about 10 s (1930s–40s) to under 4 s after 2000, with more motion. The authors read this as filmmakers controlling attention. The data are descriptive and come from feature films. | [Cutting et al., i-Perception 2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC3485803/) | observational |
| Across 6.9M MOOC sessions: shorter videos were much more engaging (<6 min recommended); talking head interleaved with slides beat slides alone; engagement usually rose (up to 2×) with speaking rate (range 48–254, mean 156 wpm). | [Guo, Kim & Rubin, L@S 2014](https://www.cs.rochester.edu/hci/pubs/pdfs/edX-MOOC-video-production-and-engagement_LAS-2014.pdf) | observational (large-scale) |
| Curiosity arises from a perceived gap in knowledge, the "information gap". | [Loewenstein, Psych. Bulletin 1994](https://stafforini.com/works/loewenstein-1994-psychology-curiosity-review/) | theory / review |
| "The first minute of each video is the most important minute"; re-engage viewers around minutes 3 and 6 so they don't "get bored ... and click off"; the key metrics are CTR, AVD and AVP. | [MrBeast production doc (leaked 2024-09)](https://www.alexanderjarvis.com/?p=90492); [Tubefilter](https://www.tubefilter.com/2024/09/17/mrbeast-internal-production-guide-leaked-key-points/) | practitioner |
| Early drop-off grows with video length: 4.9% of viewers lost in the first 2% of 1–2 min videos, versus 17.3% for 5–10 min videos. | [Wistia, 2020-01-03](https://wistia.com/library/understanding-audience-retention) | observational (vendor) |

## 3. Parameters

Each parameter below gives: its **goal**, its **evidence strength**, the **signals** it uses, its **rules** (thresholds are heuristics unless marked *sourced*), and the **timeline flags** it raises. The JSON file holds the same content in structured form.

### 3.1 Hook: visual change in the opening seconds (`hook_visual_change`)
- **Goal:** both · **Evidence:** platform-official
- **Evidence:** ABCD recommends "more than two frames in the first five seconds", surprising visuals, tightly framed people or product, and opening with people on screen ([ABCD](https://services.google.com/fh/files/misc/youtube_google_abcd_reference_guide_en.pdf)). TikTok reports that most ad-recall impact lands in the first 2–6 s ([Creative Codes](https://www.tiktok.com/business/library/Creative_Codes_May_2023.pdf), [SMT](https://www.socialmediatoday.com/news/tiktok-shares-new-notes-on-how-to-maximize-ad-effectiveness-in-the-app/694989/)). YouTube's intro checkpoint is 30 s ([Help](https://support.google.com/youtube/answer/9314415?hl=en)).
- **Signals:** `hook_cuts`, `hook_motion`, `face_share`, timeline.
- **Rules:**
  - ≥3 shots in the first 5 s for **ad** (*sourced*, ABCD).
  - The same rule for other genres (heuristic, transferred from ads).
  - `hook_motion` ≥ 1.0 (heuristic).
  - `hook_cuts` within the genre's corpus range.
- **Flags:**
  - `static_open`: the first shot runs longer than 5 s with low motion.
  - `no_face_open`: people appear in the video but not in the first 3 s.

### 3.2 Clear promise early (`clear_promise_early`)
- **Goal:** retention · **Evidence:** platform-official
- **Evidence:** TikTok: "introduce your content proposition in the first 3 seconds" ([TikTok Help](https://ads.tiktok.com/help/article/creative-best-practices)). YouTube links a weak 30 s intro to an opening that doesn't match the title and thumbnail ([Help](https://support.google.com/youtube/answer/9314415?hl=en)). Information-gap theory supports opening with an explicit question ([Loewenstein 1994](https://stafforini.com/works/loewenstein-1994-psychology-curiosity-review/)).
- **Signals:** transcript and on-screen text in the hook beat, `questions_per_min`, `hook_text_overlay`.
- **Rules:**
  - Short-form (shorts, ad): promise stated by 3 s (*sourced*, TikTok).
  - Long-form: promise stated by 15 s. This is a heuristic chosen to land well before the 30 s checkpoint.
- **Flags:**
  - `no_promise`: no question, outcome statement or payoff preview before the deadline.
  - `long_preamble`: the setup beat ends after 30 s (long-form) or after 20% of runtime (short-form).

### 3.3 Time to first voice (`time_to_first_voice`)
- **Goal:** retention · **Evidence:** practitioner (no numeric source)
- **Evidence:** ABCD says on-screen people who speak directly to the audience can help in the opening. No source gives a limit on silence before the first word.
- **Signals:** `time_to_first_word_s`, `hook_wpm`, `nonspeech_audio_share`.
- **Rules (all heuristic):**
  - ≤2 s for explainer, tech_review and ad.
  - ≤3 s for shorts and cooking.
  - **No threshold for vlog.** The corpus median is about 17 s, because music-led cold opens are the norm there.
- **Flags:** `silent_open`: the first word comes after the genre limit and there is no on-screen text.

### 3.4 Pacing (`pacing`)
- **Goal:** retention · **Evidence:** observational
- **Evidence:** Shot lengths in films have shortened over decades, alongside more motion ([Cutting et al. 2011](https://pmc.ncbi.nlm.nih.gov/articles/PMC3485803/)). This is descriptive and does **not** show that faster cutting improves retention. ABCD lists pacing as an opening lever.
- **Signals:** `shots_per_min`, `median_shot_s`, `shot_len_cv`, `pacing_trend`.
- **Rules:**
  - Compare to the genre's corpus range. Medians, in cuts/min: ad 33, shorts 12.7, tech_review 12.6, explainer 10.2, vlog 7.9, cooking 5.0.
  - `pacing_trend` between 0.8 and 1.5 (heuristic).
- **Flags (heuristic):**
  - `long_shot`: a shot longer than max(3 × genre median shot length, 8 s) with nothing else changing.
  - `pace_drop`: the rolling cut rate falls below 50% of the video's own median for more than 30 s.

### 3.5 Visual variety / pattern interrupts (`visual_variety`)
- **Goal:** retention · **Evidence:** observational
- **Evidence:** Talking head interleaved with slides was more engaging than slides alone ([Guo et al. 2014](https://www.cs.rochester.edu/hci/pubs/pdfs/edX-MOOC-video-production-and-engagement_LAS-2014.pdf)). The MrBeast document stresses re-engaging viewers before they get bored (practitioner).
- **Signals:** `format_switches_per_min`, `talking_head_share`, `broll_share`, `screen_share`, `text_overlay_share`, timeline.
- **Flags (heuristic):**
  - `visual_stall`: no cut, format switch or text change for more than **8 s** in long-form, or more than **3 s** in shorts and ads.
  - `single_format_run`: the same on-screen format for more than 60 s in long-form.

### 3.6 Dead air (`dead_air`)
- **Goal:** retention · **Evidence:** observational
- **Evidence:** No platform threshold exists. Faster delivery is associated with higher engagement in educational video ([Guo et al.](https://www.cs.rochester.edu/hci/pubs/pdfs/edX-MOOC-video-production-and-engagement_LAS-2014.pdf)). YouTube's dips report is where creators can check whether pauses line up with drop-off ([Help](https://support.google.com/youtube/answer/9314415?hl=en)).
- **Signals:** `long_pauses_per_min`, `speech_coverage`, `nonspeech_audio_share`, the loudness timeline.
- **Rules (heuristic):**
  - `long_pauses_per_min` ≤ 1 for explainer, tech_review and ad.
  - `speech_coverage` ≥ 0.6 for explainer and tech_review.
  - For vlog, cooking and shorts, flag only pauses that are actually silent.
- **Flags:**
  - `silence_in_hook`: a gap of more than **2 s** between words in the first 15 s, with audio below −45 dBFS and no text on screen.
  - `dead_air`: a gap of more than **1.5 s** between words that is near-silent and has no visual change.

### 3.7 Speaking rate and delivery energy (`speaking_rate`)
- **Goal:** retention · **Evidence:** observational
- **Evidence:** Within each length bucket, engagement usually rose (up to 2×) with speaking rate; the mean was 156 wpm ([Guo et al.](https://www.cs.rochester.edu/hci/pubs/pdfs/edX-MOOC-video-production-and-engagement_LAS-2014.pdf)). This comes from MOOC data.
- **Signals:** `wpm`, `hook_wpm`.
- **Rules:**
  - `wpm` ≥ 150 for explainer and tech_review. This is a heuristic floor based on Guo's mean, not a published cut-off.
  - The hook should not be slower than the body.
  - No target for music-led genres.
- **Flags:** `slow_stretch`: the rolling 30 s wpm in talking sections falls below 110 (heuristic).

### 3.8 On-screen text and captions (`captions_text`)
- **Goal:** both · **Evidence:** platform-official
- **Evidence:** TikTok recommends captions or text overlays, at 5–10 words per second when text is used ([TikTok Help](https://ads.tiktok.com/help/article/creative-best-practices)). ABCD says the CTA and offer should be "audible and visible" ([ABCD](https://services.google.com/fh/files/misc/youtube_google_abcd_reference_guide_en.pdf)). I found Meta's caption guidance only in third-party summaries.
- **Signals:** `hook_text_overlay`, `text_overlay_share`.
- **Rules:**
  - Text in the first 3 s for shorts and ads.
  - The same for long-form, as a heuristic: YouTube feed previews may autoplay muted (third-party reports).
- **Flags:**
  - `no_hook_text`.
  - `key_line_no_text`: the promise, verdict, offer or CTA is spoken but no text appears within ±2 s.

### 3.9 Audio presence and energy arc (`audio_energy`)
- **Goal:** retention · **Evidence:** practitioner
- **Evidence:** TikTok/Kantar survey (2021): 88% of users say sound is essential ([TikTok](https://ads.tiktok.com/business/tr/blog/kantar-report-how-brands-are-making-noise-and-driving-impact-with-sound-on-tiktok)). ABCD names audio as an opening lever. Cutting et al. *speculate* that fast cutting and motion raise arousal. No source gives loudness targets.
- **Signals:** `loudness_db`, `loudness_range_db`, `energy_slope`, `nonspeech_audio_share`.
- **Rules (all heuristic):**
  - `loudness_db` between −26 and −14 dBFS. This is RMS of active audio, **not LUFS**.
  - `energy_slope` ≥ −2.
- **Flags:**
  - `energy_dip`: loudness more than 6 dB below the running median for more than 3 s.
  - `quiet_open`.

### 3.10 People on screen and direct address (`direct_address`)
- **Goal:** both · **Evidence:** platform-official
- **Evidence:** ABCD: "open with them on-screen. Having them speak to the audience directly can also have a positive effect". TikTok: real people are associated with +9% watch time ([SMT](https://www.socialmediatoday.com/news/tiktok-shares-new-notes-on-how-to-maximize-ad-effectiveness-in-the-app/694989/)).
- **Signals:** `face_share`, `talking_head_share`, `you_rate`, `questions_per_min`.
- **Rules:** direction only. No numeric targets are published.
- **Flags:** `no_address_hook`: no "you" and no question in the first 15 s of a talk-led video.

### 3.11 Re-engagement beats (`reengagement_beats`)
- **Goal:** retention · **Evidence:** practitioner
- **Evidence:** YouTube: if top moments come late, move compelling content earlier ([Help](https://support.google.com/youtube/answer/9314415?hl=en)). MrBeast: the first minute matters most; re-engage around minutes 3 and 6 ([doc](https://www.alexanderjarvis.com/?p=90492)).
- **Signals:** story beats on the timeline, `pacing_trend`, `energy_slope`.
- **Flags (heuristic):**
  - `beat_gap`: more than 180 s with no payoff, reveal, question or new segment.
  - `late_payoff`: the first payoff comes after 70% of runtime with no earlier preview.
- **Scope:** long-form only.

### 3.12 Emotional arousal / shareability (`emotional_arousal`)
- **Goal:** virality · **Evidence:** experimental
- **Evidence:** High-arousal emotions drive sharing ([Berger & Milkman 2012](https://faculty.wharton.upenn.edu/wp-content/uploads/2011/11/Virality.pdf)). Amusement, excitement, inspiration and warmth increase ad sharing, while information-led content reduces it ([Tellis et al. 2019](https://www.ama.org/2020/06/11/what-drives-virality-sharing-of-online-digital-content-the-critical-role-of-information-emotion-and-brand-prominence/)). Joy and surprise tracked attention and zapping in internet ads ([Teixeira et al. 2012](https://www.library.hbs.edu/working-knowledge/creating-online-ads-we-want-to-watch)). Shares feed YouTube's recommender ([Goodrow 2021](https://blog.youtube/inside-youtube/on-youtubes-recommendation-system/)).
- **Signals:** we **cannot measure emotion directly**. We use weak proxies: `loudness_range_db`, `motion_mean`, loudness and motion peaks, and perception labels for surprise or reveal moments.
- **Flags:** `flat_affect`: no moment where loudness and motion both exceed their 90th percentile, and no surprise beat. This is a proxy only.

### 3.13 Brand timing and prominence (`brand_timing`, ads only)
- **Goal:** both, with a trade-off · **Evidence:** experimental
- **Evidence:** ABCD says to show the brand in the first 5 s for recall. Tellis found that early, long or persistent branding hurts sharing. Teixeira found that pulsed branding reduces zapping.
- **Signals:** the timeline only, via brand-name matches in the transcript or perception labels. **Logo detection is not implemented.**
- **Flags:**
  - `late_brand`: no brand by 5 s (*sourced*, for recall goals).
  - `persistent_brand`: the brand is on screen for more than 80% of runtime.
- **Before scoring:** ask the user which goal they have, recall or sharing.

### 3.14 Call to action (`cta_timing`)
- **Goal:** both · **Evidence:** platform-official (for ads)
- **Evidence:** ABCD: a CTA should be specific, audible and visible, with urgency. I found **no source on CTA timing in organic videos**.
- **Signals:** `cta_count`, `first_cta_pos`.
- **Flags:**
  - `no_cta_ad` (*sourced*).
  - `cta_audio_only` (*sourced*).
  - `early_ask`: a subscribe request in the first 15% of a long-form video (heuristic).

### 3.15 Length fit (`length_fit`)
- **Goal:** both · **Evidence:** observational
- **Evidence:**
  - Educational video: under 6 min ([Guo](https://www.cs.rochester.edu/hci/pubs/pdfs/edX-MOOC-video-production-and-engagement_LAS-2014.pdf)).
  - Ad sharing peaks at 1.2–1.7 min ([Tellis](https://www.ama.org/2020/06/11/what-drives-virality-sharing-of-online-digital-content-the-critical-role-of-information-emotion-and-brand-prominence/)).
  - Early drop-off grows with length ([Wistia](https://wistia.com/library/understanding-audience-retention), vendor).
  - Shorts are capped at 3 min ([YouTube](https://blog.youtube/news-and-events/tall-updates-coming-to-shorts/)).
- **Signals:** `duration_s`.
- **Rules:**
  - ad 72–102 s (*sourced*, sharing goal only).
  - explainer: segments of 6 min or less (sourced from MOOC data, an extrapolation to YouTube).
  - shorts ≤ 180 s (a platform limit, not an optimum).
  - No sourced target for vlog, tech_review or cooking.

### 3.16 Ending and loop (`loop_ending`, short-form)
- **Goal:** retention · **Evidence:** practitioner
- **Evidence:** Shorts views count each start or replay ([TechCrunch on YouTube's 2025 change](https://techcrunch.com/2025/03/26/youtube-is-changing-how-youtube-shorts-views-are-counted)). Third-party guides note that average percentage viewed exceeds 100% on loops. No official source recommends designing a seamless loop.
- **Signals:** timeline (final seconds of loudness, motion and format), `first_cta_pos`.
- **Flags (heuristic):**
  - `dead_end`: the last 2 s of a Short are silent, static or an end card.
  - `long_outro`: more than 20 s after the payoff in long-form.

## 4. Genre notes (summary)

| Genre | What the sources support most directly | Notes |
|---|---|---|
| **ad** | ABCD: >2 shots in first 5 s, brand by 5 s (recall), people on screen early, specific audible and visible CTA. TikTok: proposition by 3 s, hook by 6 s, captions. Tellis: 1.2–1.7 min and lighter branding if sharing is the goal. | The strongest evidence base, though most of it is correlational or modelled. |
| **shorts** | TikTok: 3 s proposition, captions, sound. YouTube: 3 min cap, replays count. | Loop design is practitioner advice only. |
| **explainer** | Guo et al.: chunks under 6 min, mix talking head with visuals, faster and enthusiastic delivery. Loewenstein: open with a question. | The MOOC evidence is the closest match for this genre, but it is still an extrapolation to YouTube. |
| **tech_review** | General YouTube retention guidance (30 s intro, move top moments earlier). Tellis: information-led content is shared less. | No genre-specific study found. |
| **cooking** | No genre-specific study found. ABCD-style payoff preview is a heuristic. | Process audio and long process shots are normal, so dead-air and pacing rules are relaxed. |
| **vlog** | MrBeast re-engagement (practitioner). Berger & Milkman: arousal and story drive sharing. | Music-led cold opens are normal (corpus median for first word is about 17 s), so the time-to-voice rule is disabled. |

## 5. What we cannot measure

- **Thumbnail and title.** These drive click-through and the "intro" match that YouTube itself cites. We do not see them unless the user provides them.
- **Actual retention curves, viewed-vs-swiped rate, AVD/APV, CTR, shares and satisfaction surveys.** These are only in the creator's YouTube Studio or TikTok analytics. Our output is a set of structural hypotheses; it **does not predict** retention or reach. Lining up our flags with the creator's own retention dips (when available) shows co-occurrence, not cause.
- **Emotion.** We only have proxies (loudness, motion, perception labels). Facial-expression emotion detection, as used by Teixeira et al., is not implemented.
- **Logo or brand detection.** Brand timing relies on the transcript or the perception model.
- **Audience, topic demand, channel size, posting time and the recommender's exposure decisions.** These confound every "videos with X perform better" finding ([Salganik et al. 2006](https://pdodds.w3.uvm.edu/research/papers/years/2006/salganik2006a.pdf), cited in `research.md`).
- **Platform UI.** We cannot check whether text sits inside safe zones (overlay positions are not measured), whether sound is trending, or whether captions are burned in or are platform captions. Detected on-screen text includes both.
- **Loudness in LUFS.** `loudness_db` is mean RMS dBFS of active audio, not integrated LUFS, so platform normalisation targets cannot be checked directly.
- **Loops.** Detecting first/last-frame continuity would need a new frame-similarity signal.

## 6. Unverified or excluded claims

- **TikTok Help page:** I could not fetch it directly (repeated tool failures), so the "3 s / 6 s / 5–10 words per second" wording comes from search-engine snippets of the official page. The "21–34 s ideal length" and "63% of top ads" claims that circulate in vendor blogs could not be traced to TikTok and are **excluded**.
- **Meta Reels guidance:** I could not retrieve an official Meta page. The figures circulating in third-party guides (captions on all Reels ads, hook within 1.5–3 s, safe zones of 14% top and 35% bottom, "2× delivery", "75% watch with sound on") are **excluded as unverified**.
- **YouTube "Viewed vs. swiped away":** I found no official YouTube Help page defining it or giving a benchmark. Vendor benchmarks of 70–80% "viewed" are **excluded**.
- **TikTok Creative Codes (90% recall in 6 s):** The PDF footnotes this to TikTok's 2020 "Value of View" analysis, but a TikTok blog version gives a different footnote (an Ipsos 2022 study). I could not see the methodology.
- **MrBeast document:** I read it via a third-party reproduction of the leaked text. Its authenticity is widely reported but not confirmed by the company.
- **Muted autoplay with captions in YouTube feeds:** this is described in third-party articles, not in a YouTube Help page I could access.

## 7. Sources

| # | Source | Publisher | Date |
|---|---|---|---|
| 1 | [Measure key moments for audience retention](https://support.google.com/youtube/answer/9314415?hl=en) | YouTube Help | undated; accessed 2026-10-28 |
| 2 | [On YouTube's recommendation system](https://blog.youtube/inside-youtube/on-youtubes-recommendation-system/) | YouTube Official Blog (C. Goodrow) | 2021-09-15 |
| 3 | [Tall updates coming to Shorts](https://blog.youtube/news-and-events/tall-updates-coming-to-shorts/) | YouTube Official Blog | 2024-10-03 |
| 4 | [YouTube is changing how Shorts views are counted](https://techcrunch.com/2025/03/26/youtube-is-changing-how-youtube-shorts-views-are-counted) | TechCrunch | 2025-03-26 |
| 5 | [YouTube and Google ABCD Reference Guide](https://services.google.com/fh/files/misc/youtube_google_abcd_reference_guide_en.pdf) | Google / YouTube | 2019-11-26 (PDF metadata) |
| 6 | [Validating Google's ABCD framework with AI](https://www.kantar.com/industries/technology-and-telecoms/validating-googles-abcd-framework-with-the-power-of-artificial-intelligence) | Kantar | study cited by Google as Apr 2021 |
| 7 | [Creative best practices for performance ads](https://ads.tiktok.com/help/article/creative-best-practices) | TikTok Ads Help | reported 2025-06 (not fetched directly) |
| 8 | [TikTok Creative Codes](https://www.tiktok.com/business/library/Creative_Codes_May_2023.pdf) | TikTok for Business | 2023-05 |
| 9 | [TikTok Shares New Notes on Maximizing Ad Effectiveness](https://www.socialmediatoday.com/news/tiktok-shares-new-notes-on-how-to-maximize-ad-effectiveness-in-the-app/694989/) | Social Media Today | 2023-09-27 |
| 10 | [Kantar report: sound on TikTok](https://ads.tiktok.com/business/tr/blog/kantar-report-how-brands-are-making-noise-and-driving-impact-with-sound-on-tiktok) | TikTok for Business blog | 2021 |
| 11 | [Berger & Milkman, What Makes Online Content Viral?](https://faculty.wharton.upenn.edu/wp-content/uploads/2011/11/Virality.pdf) | J. Marketing Research 49(2) | 2012 |
| 12 | [Tellis et al., What Drives Virality (Sharing) of Online Digital Content?](https://www.ama.org/2020/06/11/what-drives-virality-sharing-of-online-digital-content-the-critical-role-of-information-emotion-and-brand-prominence/) | J. Marketing 83(4) | 2019 |
| 13 | [Teixeira, Wedel & Pieters, Preventing Avoidance by Pulsing](https://econpapers.repec.org/RePEc:inm:ormksc:v:29:y:2010:i:5:p:783-804) | Marketing Science 29(5) | 2010 |
| 14 | [Teixeira, Wedel & Pieters, Emotion-Induced Engagement in Internet Video Ads](https://www.library.hbs.edu/working-knowledge/creating-online-ads-we-want-to-watch) | J. Marketing Research 49(2) (HBS summary) | 2012 |
| 15 | [Cutting et al., Quicker, faster, darker](https://pmc.ncbi.nlm.nih.gov/articles/PMC3485803/) | i-Perception 2(6) | 2011 |
| 16 | [Guo, Kim & Rubin, How Video Production Affects Student Engagement](https://www.cs.rochester.edu/hci/pubs/pdfs/edX-MOOC-video-production-and-engagement_LAS-2014.pdf) | ACM Learning@Scale | 2014 |
| 17 | [Loewenstein, The Psychology of Curiosity](https://stafforini.com/works/loewenstein-1994-psychology-curiosity-review/) | Psychological Bulletin 116(1) | 1994 |
| 18 | [How to succeed in MrBeast production (reproduction)](https://www.alexanderjarvis.com/?p=90492) | practitioner (leaked) | 2024-09 |
| 19 | [MrBeast's leaked production guide](https://www.tubefilter.com/2024/09/17/mrbeast-internal-production-guide-leaked-key-points/) | Tubefilter | 2024-09-17 |
| 20 | [Understanding Audience Retention](https://wistia.com/library/understanding-audience-retention) | Wistia (vendor) | 2020-01-03 |
| 21 | [Salganik, Dodds & Watts, Experimental study of inequality and unpredictability](https://pdodds.w3.uvm.edu/research/papers/years/2006/salganik2006a.pdf) | Science | 2006 |
