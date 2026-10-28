# Content DNA Analyzer — Background Research

*Compiled 2026-10-27. Evidence labels: **[E]** = peer-reviewed or primary-source measured evidence; **[V]** = vendor/platform claim (often modelled or self-reported, not independently validated); **[F]** = industry folklore / widely repeated with no primary source found.*

---

## 1. Problem space

Creators, media teams and advertisers can see *outcomes* (views, retention curves, CTR, CPM), but rarely a structured account of *how a video is built*: where cuts land, how energy rises and falls, how dense the speech is, what the first seconds promise, and how the narrative unfolds. Analytics tell you **where** viewers left. They don't tell you **what in the edit** was happening at that moment. Teams fill the gap with rules of thumb, and many of those trace back to a single dated vendor study.

### What is known

**Pacing / shot length (strongest evidence base)**
- **[E]** Cutting et al. measured 160 Hollywood films (1935–2010). Average shot length (ASL) fell from "about 10 s in the 1930s and 1940s" to "below 4 s after 2000". The decline is roughly linear on a log scale (r = −.75), and films also got more motion and grew darker ([Cutting et al. 2011, *i-Perception*](https://pmc.ncbi.nlm.nih.gov/articles/PMC3485803/)).
- **[E]** Shot-length sequences in newer films increasingly follow 1/f ("pink noise") patterns, which the authors relate to attention dynamics ([Cutting, DeLong & Nothelfer 2010, *Psych. Science*, via ScienceDaily](https://www.sciencedaily.com/releases/2010/02/100223121435.htm); follow-up [Cutting, DeLong & Brunick 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC5849648)). This is **descriptive** of feature films. It does not show that shorter shots cause better engagement, and it does not show that the pattern carries over to YouTube.

**Hooks and retention**
- **[V]** YouTube's "Key moments for audience retention" report defines the **intro** as the share of viewers still watching at 30 s. YouTube reads a strong intro as the opening matching the title and thumbnail. The report also flags top moments, spikes (which can mean interest *or* confusion) and dips. It needs a video of 60 s or more with at least 100 views ([YouTube Help](https://support.google.com/youtube/answer/9314415?hl=en)). This is platform guidance, not a causal study, but it is the best available source on the *metric* creators actually see.
- **[V]** Facebook/Nielsen (c. 2016): "up to 47%" of a video campaign's value arrives in the first 3 s and "up to 74%" in the first 10 s ([Instagram Business blog](https://business.instagram.com/blog/coming-soon-view-counts-on-videos); [Marketing Dive](https://www.marketingdive.com/news/facebook-offers-tips-for-converting-tv-ads-to-mobile/448510/)). This is dated, it is an "up to" figure, and secondary sources often misquote it as "47% of ad recall".
- **[F]** "You have 3 seconds" / "viewers decide in under 2 s", and "85% of Facebook video is watched without sound". These are widely repeated ([examples](https://www.brandwatch.com/blog/facebook-video-ads-best-practices)), but I found no current primary Meta source for them.

**Ad creative frameworks**
- **[V]** Google's **ABCD** (Attract, Brand, Connect, Direct) for YouTube ads ([Think with Google PDF](https://thinkwithgoogle.com/_qs/documents/8472/ABCD_Complete_V7b_HR_1.pdf)). Google's "30% lift in short-term sales likelihood / 17% long-term brand contribution" comes from Kantar scoring 11,000 ads with LINK AI across 180 features. Those outcomes are **predicted by a model, not measured in market** ([Kantar case study](https://www.kantar.com/industries/technology-and-telecoms/validating-googles-abcd-framework-with-the-power-of-artificial-intelligence)).
- **[V]** Meta's guidance: design for sound-off (captions, on-screen text), put the brand and message early, use movement at the start, and prefer vertical 4:5 or 9:16 formats. These are summarized by [Smart Insights](https://www.smartinsights.com/social-media-marketing/facebook-marketing/facebook-video-advertising-creative-best-practices) and [ROI Revolution](https://roirevolution.com/blog/facebook-video-social-media-advertising/). I could not retrieve Meta's own current page, so verify the details in Meta's Business Help Center.

---

## 2. Existing solutions

| Group | Tool | What it does / outputs | Gap vs. "explain construction + timestamped, evidence-backed fixes" |
|---|---|---|---|
| **Creator analytics** | YouTube Studio | Retention curve, key moments (intro, spikes, dips), CTR, traffic sources ([Help](https://support.google.com/youtube/answer/9314415?hl=en)) | Shows *where* viewers drop, not *what* in the edit coincides with it. It also only works after publishing. |
| | vidIQ / TubeBuddy | Keyword/SEO scores, title and thumbnail tools. TubeBuddy offers thumbnail/title A/B tests ([TubeBuddy comparison, vendor-authored](https://www.tubebuddy.com/blog/vidiq-vs-tubebuddy/); [Learning Revolution](https://www.learningrevolution.net/tubebuddy-vs-vidiq/)) | Focused on packaging and discovery. Neither analyses shot rhythm, audio energy or narrative structure. |
| **Video understanding APIs** | Google Video Intelligence | Shot-change segments (start/end), labels, OCR, speech ([docs](https://cloud.google.com/video-intelligence/docs/feature-shot-change)) | Returns primitives only, with no interpretation or recommendations. It detects *abrupt* cuts. |
| | AWS Rekognition Video | Segment detection: `SHOT` and `TECHNICAL_CUE` (black frames, credits, slates) with SMPTE timecodes and confidence ([API ref](https://docs.aws.amazon.com/rekognition/latest/APIReference/API_SegmentDetection.html)) | Same: a building block, not an analysis. |
| | Twelve Labs (Marengo/Pegasus) | Semantic moment search with timestamps; video-to-text (chapters, highlights, timestamped events) ([docs](https://docs.twelvelabs.io/docs/video-understanding-models); [Pegasus](https://www.twelvelabs.io/pegasus)) | Describes content, but has no model of craft (pacing, hook mechanics) and no improvement advice. |
| | Gemini video | Multimodal Q&A. By default it samples **1 fps** with timestamps every second, and Google notes detail may suffer with "rapidly changing visuals" ([docs mirror](https://gemini-api.apidog.io/doc-965861); I could not reach Google's page directly) | Can't reliably see sub-second cuts. Its timestamps and claims need verification against measured signals. |
| **Clipping / repurposing** | Opus Clip | Auto-clips long videos and gives each clip a 0–99 "virality score" built from Hook, Flow, Value and Trend ([help](https://help.opus.pro/docs/article/virality-score)) | The score is opaque and relative, and Opus publishes no hit rates for it. It optimises clip *selection* and doesn't explain the source video's construction. |
| **Ad scoring / pre-testing** | Vidmob | Tags hundreds of creative elements (scene changes, text overlays, logo placement). Scores assets against brand/channel guidelines and links elements to KPIs ([help](https://help.vidmob.com/en/articles/12676204-vidmob-api-overview-unlock-your-creative-data)) | Closest to our idea. It is enterprise-only, ad-focused, and scores against checklists rather than explaining narrative or rhythm. |
| | CreativeX | Creative Quality Score = % of guidelines met. Vendor study: +10% CQS associated with −2% CPM ([CreativeX](https://learn.creativex.com/creative-quality-score)) | A compliance checklist. The correlation is vendor-reported and not causal. |
| | Neurons Predict | Predicted attention and brand-attention scores, overall and frame-by-frame ([Neurons](https://www.neuronsinc.com/insights/predict-benchmarks)) | Attention heatmaps, not structure. Its accuracy claims are vendor-supplied. |
| | Kantar LINK AI | Predicts survey-based ad-test outcomes from a normative database (230k tests) ([MRWeb](https://www.mrweb.com/drno/news32719.htm); [Kantar](https://www.kantar.com/press-center/kantar-supercharges-early-stage-creative-development)) | Gives a single prediction per ad, for advertisers, with little timestamped diagnosis. |
| | Memorable | Predicted memorability, saliency and brand-association scores ([Unite.ai](https://www.unite.ai/memorable-ai-raises-2-75m-in-pre-seed-funding-to-help-brands-analyze-visual-assets)) | Accuracy figures are self-reported. An acquisition was reported but I could not confirm it. |
| | System1 Test Your Ad | Star rating (1.0–5.9, long-term brand), Spike (short-term sales) and Fluency, from human panels measuring emotion and brand recognition ([System1](https://system1group.com/blog/super-bowl-ads-with-greatest-sales-potential)) | Panel-based and ad-only. It measures response, not construction. |

**Overall gap:** no tool found combines (a) measured structural signals such as cuts, loudness and words per second, (b) an interpretable account of hook and narrative construction, and (c) recommendations tied to specific timestamps with the supporting evidence attached, for **creators** rather than only enterprise advertisers.

---

## 3. Academic work

**Computational style analysis / cinemetrics**
- **[E]** Cinemetrics (Yuri Tsivian, U. Chicago) is an open, crowd-sourced database of per-shot timings for thousands of films, with ASL, median and standard-deviation statistics ([Film Comment](https://www.filmcomment.com/article/site-specifics-cinemetrics.lv?print); [Cinemetrics note on Cutting](https://cinemetrics.uchicago.edu/article/590235ff-85aa-4714-9553-71d4c44fd61c)). It sets a precedent for treating editing rhythm as measurable style. **Median** shot length is often preferred because shot-length distributions are skewed.
- **[E]** Shot boundary detection is mature for hard cuts. **TransNet V2** reports state-of-the-art results ([arXiv 2008.04838](https://arxiv.org/abs/2008.04838)). Gradual transitions (dissolves, whip pans) and the fast "jump cuts" common in creator content are harder; F1 on ClipShots is around 78 per a [secondary mirror](https://github.com/jebin2/TransNetV2), which I have not verified against the paper.

**Predicting engagement or popularity from content**
- **[E]** Early popularity strongly predicts later popularity on a log scale ([Szabo & Huberman, arXiv 0811.0405](https://arxiv.org/abs/0811.0405)). Trzciński & Rokita combine visual and early-view features and report that social/early-view features are a much stronger signal than visual ones, though visual features give some pre-publication signal ([arXiv 1510.06223](https://arxiv.org/abs/1510.06223)).
- **[E]** Salganik, Dodds & Watts (*Science*, 2006; 14,341 participants) found that social influence makes success both more unequal and **less predictable**. Quality mattered only partially: the best songs rarely flopped and the worst rarely hit, but anything else could happen ([paper PDF](https://pdodds.w3.uvm.edu/research/papers/years/2006/salganik2006a.pdf)).
- **Typical picture:** content features explain a modest share of the variance in success. Effects are confounded by channel size, topic, thumbnail and title, recommender exposure, and publish timing. Correlational "videos with X perform better" findings rarely survive these controls.

**Multimodal LLM temporal grounding**
- **[E]** Zero-shot temporal grounding is still weak. On Charades-STA, GPT-4o scores around 35 mIoU and Gemini-2.5-Pro around 35 mIoU under one re-evaluation, and the authors also document label-quality problems in the benchmarks themselves ([TimeLens, arXiv 2512.14698](https://arxiv.org/abs/2512.14698); [TimeThink, arXiv 2607.05089](https://arxiv.org/abs/2607.05089)). Results swing a lot with frame and token sampling density ([GroundVTS, arXiv 2604.02093](https://arxiv.org/abs/2604.02093)). Cross-paper numbers use different protocols, so treat them as indicative. **Implication:** LLM-produced timestamps are often off by seconds.

---

## 4. Implications for our design

1. **Measure first, interpret second.** Compute cuts (TransNet V2 / PySceneDetect), loudness and RMS energy, and speech rate from ASR word timestamps deterministically. Use the LLM only to *interpret* those signals. Never let it be the source of truth for timestamps.
2. **Snap every LLM-cited timestamp to a measured event** (a cut, a transcript word, an energy peak). Drop or flag any recommendation that can't be anchored to one.
3. **Attach evidence to every recommendation:** the timestamp, the measured signal, a frame or transcript excerpt, and the guideline it relates to, labelled [E], [V] or [F] using the scheme above.
4. **Report medians and distributions, not just ASL.** Also compare against genre or format baselines built from a reference set we can describe, rather than against film norms.
5. **Use 1 fps LLM sampling for semantics only.** Pacing and hook analysis in the first 3–5 s need full-frame-rate detectors.
6. **Frame output as "structure + hypotheses to test"**, for example "the first cut lands at 4.2 s; consider testing an earlier visual change", and not as predicted performance.
7. **Optionally ingest the creator's own YouTube retention data** to line up dips and spikes with structural events. Present these as co-occurrence, not cause.
8. **Calibrate and evaluate:** hand-label a small set of videos for cuts, hook end and section boundaries, and report our timestamp error honestly.

## Claims we must NOT make

- "This video will go viral" / any virality or view-count prediction score.
- "Shorter shots / faster pacing increase retention" as a causal rule (Cutting's work is descriptive and film-specific).
- "Following these fixes will lift retention or sales by X%" (ABCD's lifts are *modelled*; no comparable evidence exists for our output).
- Quoting "you have 3 seconds", "85% watch without sound" or "47% of value in 3 s" as established fact.
- "Frame-accurate" or "precise" LLM timestamps.
- That our score is "validated" or "neuroscience-backed" without our own study.
- That a recommendation explains *why* viewers left a specific moment. At most it co-occurs with the dip.
