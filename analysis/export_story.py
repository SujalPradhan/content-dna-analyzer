"""Export everything the data story shows into results/story/ (one file per dataset). Every number on the
story page comes from these files, which are computed from the pipeline outputs — nothing is typed by hand
except the qualitative landscape table (our reading of public product docs, see docs/research.md)."""
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
OUT = RES / "story"
VID = ROOT / "data" / "videos"

import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "src"))
from content_dna.fingerprint import FIELDS  # noqa: E402

CAT_LABEL = {"ad": "Ads", "cooking": "Cooking", "explainer": "Explainers", "shorts": "Shorts",
             "tech_review": "Tech reviews", "vlog": "Vlogs"}


def _ref_label(ref):
    """'bin:75.0' -> 'bin at 1:15'; 'first_cta_pos' -> 'first cta pos'."""
    if ref.startswith("bin:"):
        try:
            t = float(ref[4:])
            return f"bin at {int(t // 60)}:{int(t % 60):02d}"
        except ValueError:
            return ref
    return ref.replace("_", " ")


def jload(p):
    return json.loads(Path(p).read_text()) if Path(p).exists() else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(RES / "corpus_features.csv")
    stats = jload(RES / "stats.json")
    shot = jload(RES / "eval/shot_eval.json")
    perc = jload(RES / "eval/perception_eval.json")
    rob = jload(RES / "eval/robustness.json")
    crit = jload(RES / "eval/critique_eval.json")
    usage = pd.read_csv(RES / "usage.csv")
    facts = []

    def fact(key, value, label):
        facts.append({"key": key, "value": None if value is None or (isinstance(value, float) and np.isnan(value)) else value,
                      "label": label})

    # ---------------- videos
    df["category_label"] = df["category"].map(CAT_LABEL)
    keep = ["video_id", "category", "category_label", "title", "channel", "duration_s", "shots_per_min", "median_shot_s",
            "hook_cuts", "time_to_first_word_s", "wpm", "speech_coverage", "nonspeech_audio_share", "talking_head_share",
            "broll_share", "screen_share", "text_overlay_share", "face_share", "cta_count", "first_cta_pos",
            "like_rate", "views", "hook_type", "archetype", "opening_contrast_db", "n_recs", "recs_grounded",
            "evidence_items", "evidence_verified"]
    vids = df[[c for c in keep if c in df]].copy()
    vids["url"] = "https://www.youtube.com/watch?v=" + vids["video_id"]
    vids.to_csv(OUT / "videos.csv", index=False)

    fact("n_videos", int(len(df)), "videos analysed")
    fact("n_categories", int(df.category.nunique()), "categories")
    fact("hours_analysed", round(float(df.duration_s.sum() / 3600), 1), "hours of video analysed")
    fact("n_features", len(FIELDS), "fingerprint features")
    fact("n_unavailable", 1, "selected video unavailable at download")

    # ---------------- category stats (H1)
    rows = []
    for f, v in stats["H1_category_differences"].items():
        for c, s in v["by_category"].items():
            rows.append({"feature": f, "feature_label": FIELDS[f][1], "unit": FIELDS[f][2], "category": c,
                         "category_label": CAT_LABEL[c], "median": s["median"], "ci_lo": s["ci95"][0], "ci_hi": s["ci95"][1],
                         "n": s["n"], "epsilon2": v["epsilon2"], "q_bh": v["q_bh"]})
    pd.DataFrame(rows).to_csv(OUT / "category_stats.csv", index=False)
    h1 = stats["H1_category_differences"]
    fact("h1_n_significant", sum(1 for v in h1.values() if v["q_bh"] < 0.05), "features differing by category (FDR q<0.05)")
    fact("h1_n_tested", len(h1), "features tested for category differences")
    med = df.groupby("category").median(numeric_only=True)
    for c in CAT_LABEL:
        fact(f"cuts_{c}", round(float(med.loc[c, "shots_per_min"]), 1), f"median cuts/min, {CAT_LABEL[c]}")
        fact(f"wpm_{c}", round(float(med.loc[c, "wpm"]))  , f"median words/min, {CAT_LABEL[c]}")
        fact(f"ttfw_{c}", round(float(med.loc[c, "time_to_first_word_s"]), 1), f"median seconds to first word, {CAT_LABEL[c]}")
        fact(f"speech_{c}", round(float(med.loc[c, "speech_coverage"]), 2), f"median speech coverage, {CAT_LABEL[c]}")
        fact(f"firstcta_{c}", round(float(med.loc[c, "first_cta_pos"]), 2), f"median first-CTA position, {CAT_LABEL[c]}")
    fact("cuts_ratio_ad_cooking", round(float(med.loc["ad", "shots_per_min"] / med.loc["cooking", "shots_per_min"]), 1),
         "ads cut this many times faster than cooking videos (median cuts/min ratio)")

    # ---------------- loudness profiles
    prof = stats["energy_arcs"]["median_profile_by_category"]
    pd.DataFrame([{"category": c, "category_label": CAT_LABEL[c], "bin": i, "pct_runtime": round((i + 0.5) * 5, 1), "db": v}
                  for c, vals in prof.items() for i, v in enumerate(vals)]).to_csv(OUT / "loudness_profiles.csv", index=False)
    for c, v in stats["energy_arcs"]["opening_contrast_by_category"].items():
        fact(f"opening_db_{c}", v, f"median loudness of first 10% minus rest (dB), {CAT_LABEL[c]}")

    # ---------------- format mix
    fm = []
    for c, g in df.groupby("category"):
        th, br, sc = g.talking_head_share.mean(), g.broll_share.mean(), g.screen_share.mean()
        other = max(0.0, 1 - th - br - sc)
        for fmt, v in [("Talking head", th), ("B-roll / product", br), ("Screen / graphics", sc), ("Other", other)]:
            fm.append({"category": c, "category_label": CAT_LABEL[c], "format": fmt, "share": round(float(v), 3)})
    pd.DataFrame(fm).to_csv(OUT / "format_mix.csv", index=False)

    # ---------------- hooks
    hk = df.groupby(["category", "hook_type"]).size().reset_index(name="n")
    hk["category_label"] = hk["category"].map(CAT_LABEL)
    hk.to_csv(OUT / "hook_types.csv", index=False)

    # ---------------- archetypes
    h3 = stats["H3_archetypes"]
    names = {}
    for a, p in h3["profiles"].items():
        top = list(p["high"])[0]
        names[a] = {"shots_per_min": "Rapid-cut", "nonspeech_audio_share": "Ambient montage",
                    "wpm": "Speech-led", "talking_head_share": "Presenter-led", "speech_coverage": "Speech-led",
                    "screen_share": "Screen & graphics", "broll_share": "Narrated b-roll",
                    "motion_mean": "Rapid-cut spot"}.get(top, top)
    arch = []
    for a, p in h3["profiles"].items():
        for c in CAT_LABEL:
            arch.append({"archetype": int(a), "archetype_name": names[a], "n_archetype": p["n"], "category": c,
                         "category_label": CAT_LABEL[c], "n": p["categories"].get(c, 0),
                         "defining_features": ", ".join(FIELDS[f][1] for f in list(p["high"])[:2])})
    pd.DataFrame(arch).to_csv(OUT / "archetypes.csv", index=False)
    vids["archetype_name"] = vids["archetype"].astype(str).map(names)
    vids.to_csv(OUT / "videos.csv", index=False)
    fact("arch_k", h3["k"], "archetypes found (k chosen by silhouette)")
    fact("arch_silhouette", h3["silhouette"], "silhouette score (0-1; <0.3 = weak structure)")
    fact("arch_ari", h3["ari_vs_category"], "agreement between archetypes and categories (ARI; 0 = none, 1 = identical)")
    fact("arch_mixed", sum(1 for p in h3["profiles"].values() if len(p["categories"]) >= 3),
         "archetypes containing 3+ categories")

    # ---------------- engagement
    eng = []
    for analysis in ["raw", "within_category"]:
        for f, v in stats["H4_engagement"][analysis].items():
            eng.append({"feature": f, "feature_label": FIELDS[f][1], "analysis": analysis, "rho": v["rho"],
                        "ci_lo": v["ci95"][0], "ci_hi": v["ci95"][1], "p": v["p"], "q_bh": v["q_bh"], "n": v["n"]})
    eng = pd.DataFrame(eng)
    eng.to_csv(OUT / "engagement_tests.csv", index=False)
    w = eng[eng.analysis == "within_category"]
    fact("eng_n_tests", int(len(w)), "features tested against like rate (within category)")
    fact("eng_n_surviving", int((w.q_bh < 0.05).sum()), "features surviving FDR correction")
    fact("eng_n", int(w.n.max()), "videos with public like counts")
    if rob:
        fact("th_rho", rob["within_category_rho"], "talking-head share vs like rate, within-category Spearman rho")
        fact("th_perm_p", rob["perm_p_within_category"], "permutation p (feature shuffled within category)")
        fact("th_partial", rob["partial_rho_controlling_views_subs"], "rho after controlling for views and subscribers")
        fact("th_loco_min", min(rob["leave_one_category_out"].values()), "smallest rho when leaving one category out")
        fact("th_any_share", rob["share_with_any_talking_head"], "share of videos with any talking-head time")
    vc = stats["H4_engagement"]["confounder_log_views"]
    fact("views_like_rho", vc["rho"], "views vs like rate, Spearman rho (bigger audiences like less)")

    # ---------------- shot eval
    if shot:
        pd.DataFrame(shot["per_video"]).to_csv(OUT / "shot_eval.csv", index=False)
        fact("shot_precision", shot["pooled"]["precision"], "shot detector pooled precision")
        fact("shot_recall", shot["pooled"]["recall"], "shot detector pooled recall")
        fact("shot_manual", shot["pooled"]["manual"], "hand-labelled cuts")

    # ---------------- perception eval
    if perc:
        pr = pd.DataFrame(perc["rows"])
        pr.to_csv(OUT / "perception_eval.csv", index=False)
        fact("perc_overrun_before", perc["overrun_gt_5pct_before"], "videos whose vision timeline overran runtime, before fix")
        fact("perc_overrun_after", perc["overrun_gt_5pct_after"], "after fix")
        fact("perc_hit_before", perc["median_boundary_hit_before"], "median share of vision-model boundaries on a measured cut, before fix")
        fact("perc_hit_after", perc["median_boundary_hit_after"], "after fix")
        fact("perc_overrun_ratio", round(float(pr["overrun_before"].dropna().loc[lambda s: s > 1.05].median()), 2),
             "median overrun ratio of affected timelines (100/60 = 1.67)")

    # ---------------- critique eval
    if crit:
        a, f_, b = crit["all_full"], crit["ablation_full"], crit["ablation_baseline"]
        fact("crit_videos", int(df.n_recs.notna().sum()), "videos critiqued")
        fact("crit_recs", a["recs"], "recommendations generated")
        fact("crit_evidence_items", a["evidence_items"], "evidence items cited")
        fact("crit_evidence_rate", a["evidence_rate"], "share of cited evidence verified against measurements")
        fact("crit_rec_grounded", a["rec_grounded_rate"], "share of recommendations with >=1 verified evidence item")
        fact("abl_n", len(crit["ablation_videos"]), "videos in ablation")
        fact("abl_full_rate", f_["evidence_rate"], "evidence verified, full pipeline (ablation set)")
        fact("abl_base_rate", b["evidence_rate"], "evidence verified, transcript-only baseline")
        fact("abl_full_per_rec", f_["evidence_per_rec"], "evidence items per recommendation, full")
        fact("abl_base_per_rec", b["evidence_per_rec"], "evidence items per recommendation, baseline")
        j = crit["judge"]
        fact("judge_full_wins", j["wins_full"], "blind judge preferred full pipeline")
        fact("judge_base_wins", j["wins_baseline"], "blind judge preferred baseline")
        fact("judge_ties", j["ties"], "ties")
        ce = []
        for side in ["full", "baseline"]:
            for k, v in j["mean_scores"][side].items():
                ce.append({"system": "Content DNA" if side == "full" else "Transcript-only baseline", "criterion": k, "score": v})
        pd.DataFrame(ce).to_csv(OUT / "judge_scores.csv", index=False)
        st = pd.DataFrame(crit["stability"])
        st.to_csv(OUT / "stability.csv", index=False)
        fact("stab_n", int(len(st)), "videos re-run for stability")
        fact("stab_roles", round(float(st.role_agreement.median()), 2), "median structure-role agreement between two runs")
        fact("stab_recs", round(float(st.rec_time_overlap.median()), 2), "median share of rec timestamps reproduced")
        fact("stab_tags", round(float(st.tag_jaccard.median()), 2), "median tag overlap (Jaccard)")
        kinds = []
        for sysname, g in [("Content DNA", f_), ("Transcript-only baseline", b)]:
            for k, (ok, tot) in g["by_kind"].items():
                kinds.append({"system": sysname, "kind": k, "verified": ok, "total": tot})
        pd.DataFrame(kinds).to_csv(OUT / "evidence_by_kind.csv", index=False)
        basis = []
        for d in VID.iterdir():
            c = jload(d / "critique.json")
            if c:
                for r in c["recommendations"]:
                    basis.append(r["basis"])
        bs = pd.Series(basis).value_counts().reset_index()
        bs.columns = ["basis", "n"]
        bs.to_csv(OUT / "rec_basis.csv", index=False)
        fact("basis_outlier", int(bs.set_index("basis").n.get("measured_outlier_vs_corpus", 0)), "recommendations based on a corpus outlier")

    # ---------------- cost
    u = usage[usage.video_id.notna() | usage.stage.str.startswith("eval")]
    stage_map = {"whisper": "Transcription", "perception": "Vision timeline", "critique": "Critique",
                 "eval_baseline": "Evaluation", "eval_judge": "Evaluation"}
    u = u.assign(step=u.stage.map(stage_map).fillna("Other"))
    cost = u.groupby("step").agg(usd=("usd", "sum"), calls=("usd", "size")).reset_index()
    cost["usd"] = cost.usd.round(3)
    cost.to_csv(OUT / "cost.csv", index=False)
    fact("total_usd", round(float(usage.usd.sum()), 2), "total estimated LLM spend for the whole project (USD)")
    # one clean pass per video: the last call of each stage (the vision step was re-run once after the timestamp fix)
    last = u[u.stage.isin(["whisper", "perception", "critique"]) & u.video_id.isin(set(df.video_id))]
    last = last.sort_values("ts").groupby(["video_id", "stage"]).tail(1)
    per_video = last.groupby("video_id").usd.sum()
    fact("usd_per_video", round(float(per_video.median()), 3), "median cost of one full pass per video (USD)")
    fact("usd_rerun", round(float(u[u.stage == "perception"].usd.sum() - last[last.stage == "perception"].usd.sum()), 2),
         "spent re-running the vision step after the timestamp fix (USD)")
    cache = usage[usage.stage == "critique"]
    fact("cache_read_share", round(float(cache.cache_read.sum() / (cache.cache_read.sum() + cache.cache_write.sum() + cache["in"].sum())), 2),
         "share of critique input tokens served from prompt cache")

    # ---------------- landscape (qualitative, from docs/research.md)
    land = [
        ("YouTube Studio", "Creator analytics", "Retention curve, CTR, key moments", "no", "no", "no"),
        ("vidIQ / TubeBuddy", "Creator analytics", "SEO, title & thumbnail tests", "no", "no", "no"),
        ("Google Video Intelligence", "Video API", "Shots, labels, OCR, speech", "partial", "no", "no"),
        ("AWS Rekognition Video", "Video API", "Shot & technical-cue segments", "partial", "no", "no"),
        ("Twelve Labs", "Video API", "Moment search, summaries, chapters", "partial", "no", "no"),
        ("Opus Clip", "Repurposing", "Clips + 0-99 virality score", "no", "no", "partial"),
        ("Vidmob", "Ad scoring", "Creative element tags, guideline scores", "partial", "partial", "partial"),
        ("CreativeX", "Ad scoring", "Guideline compliance score", "partial", "no", "no"),
        ("Neurons / Memorable", "Ad scoring", "Predicted attention / memorability", "no", "no", "partial"),
        ("Kantar LINK AI / System1", "Ad scoring", "Predicted ad-test outcome", "no", "no", "no"),
        ("Content DNA Analyzer", "This project", "Measured fingerprint + verified, timestamped critique", "yes", "yes", "yes"),
    ]
    with (OUT / "landscape.csv").open("w", newline="") as fh:
        w_ = csv.writer(fh)
        w_.writerow(["tool", "group", "outputs", "measures_structure", "explains_construction", "timestamped_fixes"])
        w_.writerows(land)

    # ---------------- anecdotes (all values read from saved pipeline outputs)
    old = jload(ROOT / "data/old_perception/3B3B9eSgMV0/perception.json")
    newp = jload(VID / "3B3B9eSgMV0/perception.json")
    if old and newp:
        f3 = jload(VID / "3B3B9eSgMV0/features.json")
        fact("anec_title", f3["title"].split(" #")[0], "video whose vision timeline overran")
        fact("anec_duration", f3["fingerprint"]["duration_s"], "its analysed duration (s)")
        fact("anec_bad_cta", max(c["t_s"] for c in old["overall"]["cta_moments"]), "last CTA time as first reported (s)")
        fact("anec_fixed_cta", max(c["t_s"] for c in newp["overall"]["cta_moments"]), "last CTA time after the fix (s)")
    flagged = {}
    for v in df.video_id:
        t = jload(VID / v / "audio.json")["transcript"]
        if t.get("quality", "ok") != "ok":
            flagged[v] = t
    fact("whisper_flagged", len(flagged), "transcripts where Whisper invented speech (rejected or partly dropped)")
    fact("whisper_rejected", sum(t["quality"] == "rejected" for t in flagged.values()), "transcripts rejected entirely")
    od = flagged.get("od29yqPu-aM")
    if od:
        fact("hall_sample", od["rejected_text"][:46], "start of the invented 'speech' on a music-only cooking video")
    fact("arch_single", sum(1 for p in h3["profiles"].values() if len(p["categories"]) == 1), "archetypes made of a single genre")

    # ---------------- evidence filmstrips: the opening 15 s of a fast and a slow video (frames every 2.5 s)
    import base64
    strips = []
    for v, label in [("s83EB_OtaEo", "fast"), ("glSXLZnOT4A", "slow")]:
        fr = sorted((VID / v / "hook").glob("hook_*.jpg"))
        f4 = jload(VID / v / "features.json")
        strips.append({"video_id": v, "role": label, "title": f4["title"], "genre": f4["category"],
                       "cuts_per_min": f4["fingerprint"]["shots_per_min"], "hook_cuts": f4["fingerprint"]["hook_cuts"],
                       "frames": [{"t": float(p.stem.split("_")[1].rstrip("s")),
                                   "src": "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()} for p in fr]})
    (OUT / "frames.json").write_text(json.dumps(strips))

    # ---------------- explorer: per-video timelines for every corpus video (same shape as GET /api/videos/{id})
    from content_dna.server import video_report
    ex = [video_report(v) for v in df["video_id"]]
    (OUT / "explorer.json").write_text(json.dumps(ex, separators=(",", ":"), allow_nan=False))

    pd.DataFrame(facts).to_json(OUT / "facts.json", orient="records", indent=1)
    print(f"wrote {len(list(OUT.iterdir()))} files; {len(facts)} facts")


if __name__ == "__main__":
    main()
