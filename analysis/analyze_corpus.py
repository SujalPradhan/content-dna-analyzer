"""Corpus-level experiments over extracted fingerprints. Writes results/corpus_features.csv and results/stats.json.

H1  Creative grammar differs by category (pacing, speech, format mix)       -> Kruskal-Wallis + epsilon^2
H2  Hooks are built differently by category (time-to-first-word, hook cuts, hook type)
H3  Creative archetypes exist that cut across categories                    -> PCA + k-means (silhouette-chosen k)
H4  Do any creative features track engagement (likes/view)?                 -> Spearman, bootstrap CI, BH-FDR,
    computed on raw values AND within-category ranks. Correlational only; n is small; confounded by channel/audience.
E   Energy arcs: loudness over normalised runtime, clustered into shapes.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
VID = ROOT / "data" / "videos"
RES = ROOT / "results"
rng = np.random.default_rng(42)

CORE = ["shots_per_min", "median_shot_s", "wpm", "speech_coverage", "time_to_first_word_s", "hook_cuts",
        "nonspeech_audio_share", "loudness_range_db", "motion_mean", "colorfulness_mean", "talking_head_share",
        "broll_share", "screen_share", "text_overlay_share", "face_share", "format_switches_per_min", "you_rate",
        "questions_per_min", "cta_count"]
CLUSTER_FEATS = ["shots_per_min", "wpm", "speech_coverage", "nonspeech_audio_share", "motion_mean",
                 "talking_head_share", "broll_share", "screen_share", "text_overlay_share", "face_share"]


def load() -> pd.DataFrame:
    rows = []
    import csv
    import re
    ids = {re.search(r"([\w-]{11})$", r["url"].rstrip("/")).group(1) for r in csv.DictReader(open(ROOT / "data/corpus.csv"))}
    for p in sorted(VID.glob("*/features.json")):
        f = json.loads(p.read_text())
        if f["video_id"] not in ids:  # only the study corpus; ad-hoc API/CLI analyses are excluded
            continue
        per = json.loads((p.parent / "perception.json").read_text()) if (p.parent / "perception.json").exists() else {}
        crit = json.loads((p.parent / "critique.json").read_text()) if (p.parent / "critique.json").exists() else None
        r = {"video_id": f["video_id"], "category": f["category"], "title": f["title"], "channel": f["channel"],
             "views": f["views"], "likes": f["likes"], "comments": f["comments"], "subscribers": f["subscribers"],
             "upload_date": f["upload_date"], **f["fingerprint"],
             "hook_type": (per.get("hook") or {}).get("hook_type"),
             "production_style": (per.get("overall") or {}).get("production_style"),
             "music_presence": (per.get("overall") or {}).get("music_presence")}
        if crit:
            g = crit["grounding"]
            r.update({"n_recs": g["recs"], "recs_grounded": g["recs_grounded"], "evidence_items": g["evidence_items"],
                      "evidence_verified": g["evidence_verified"]})
        rows.append(r)
    df = pd.DataFrame(rows)
    df["like_rate"] = df["likes"] / df["views"]
    df["comment_rate"] = df["comments"] / df["views"]
    df["log_views"] = np.log10(df["views"].clip(lower=1))
    df["log_subs"] = np.log10(df["subscribers"].astype(float).clip(lower=1))
    df["views_per_sub"] = df["views"] / df["subscribers"].astype(float)
    return df


def eps2(h, n, k):
    return max(0.0, (h - k + 1) / (n - k))


def boot_median_ci(x, n=2000):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 3:
        return [None, None]
    meds = np.median(rng.choice(x, (n, len(x)), replace=True), axis=1)
    return [round(float(np.percentile(meds, 2.5)), 3), round(float(np.percentile(meds, 97.5)), 3)]


def h1_by_category(df):
    out = {}
    for f in CORE:
        groups = [g[f].dropna().values for _, g in df.groupby("category")]
        groups = [g for g in groups if len(g) >= 2]
        if len(groups) < 2:
            continue
        h, p = stats.kruskal(*groups)
        n = sum(len(g) for g in groups)
        out[f] = {"H": round(float(h), 2), "p": float(p), "epsilon2": round(eps2(h, n, len(groups)), 3),
                  "by_category": {c: {"median": round(float(g[f].median()), 3), "ci95": boot_median_ci(g[f]),
                                      "n": int(g[f].notna().sum())} for c, g in df.groupby("category")}}
    ps = [v["p"] for v in out.values()]
    q = bh(ps)
    for (k, v), qq in zip(out.items(), q):
        v["q_bh"] = round(qq, 4)
        v["p"] = round(v["p"], 5)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["epsilon2"]))


def bh(p):
    p = np.asarray(p, float)
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, i in enumerate(order[::-1]):
        k = n - rank
        prev = min(prev, p[i] * n / k)
        q[i] = prev
    return q.tolist()


def h2_hooks(df):
    out = {"hook_type_by_category": pd.crosstab(df["category"], df["hook_type"]).to_dict(orient="index")}
    for f in ["time_to_first_word_s", "hook_cuts", "hook_wpm", "hook_text_overlay", "hook_motion"]:
        out[f] = {c: round(float(g[f].median()), 2) for c, g in df.groupby("category")}
    return out


def h3_archetypes(df):
    X = df[CLUSTER_FEATS].astype(float)
    X = X.fillna(X.median())
    Z = StandardScaler().fit_transform(X)
    pca = PCA(n_components=2, random_state=0).fit(Z)
    P = pca.transform(Z)
    best = None
    for k in range(3, 7):
        km = KMeans(k, n_init=20, random_state=0).fit(Z)
        s = silhouette_score(Z, km.labels_)
        if best is None or s > best[0]:
            best = (s, k, km)
    s, k, km = best
    df["archetype"] = km.labels_
    df["pc1"], df["pc2"] = P[:, 0], P[:, 1]
    centers = pd.DataFrame(km.cluster_centers_, columns=CLUSTER_FEATS)
    profiles = {}
    for c in range(k):
        top = centers.loc[c].sort_values()
        profiles[int(c)] = {"n": int((km.labels_ == c).sum()),
                            "high": {f: round(float(top[f]), 2) for f in top.index[::-1][:3]},
                            "low": {f: round(float(top[f]), 2) for f in top.index[:3]},
                            "categories": df[df.archetype == c]["category"].value_counts().to_dict(),
                            "raw_medians": {f: round(float(df[df.archetype == c][f].median()), 3) for f in CLUSTER_FEATS}}
    loadings = {f"PC{i + 1}": dict(sorted({f: round(float(v), 3) for f, v in zip(CLUSTER_FEATS, comp)}.items(),
                                          key=lambda kv: -abs(kv[1]))[:5]) for i, comp in enumerate(pca.components_)}
    # How much do archetypes simply restate category? Adjusted Rand vs category labels.
    from sklearn.metrics import adjusted_rand_score
    return {"k": k, "silhouette": round(float(s), 3), "explained_var": [round(float(v), 3) for v in pca.explained_variance_ratio_],
            "loadings": loadings, "profiles": profiles,
            "ari_vs_category": round(float(adjusted_rand_score(df["category"], km.labels_)), 3),
            "silhouette_by_k": None}


def spearman_boot(x, y, n=2000):
    m = ~(np.isnan(x) | np.isnan(y))
    x, y = x[m], y[m]
    if len(x) < 8:
        return None
    rho, p = stats.spearmanr(x, y)
    idx = rng.integers(0, len(x), (n, len(x)))
    bs = [stats.spearmanr(x[i], y[i])[0] for i in idx]
    return {"rho": round(float(rho), 3), "p": float(p), "ci95": [round(float(np.nanpercentile(bs, 2.5)), 3),
                                                              round(float(np.nanpercentile(bs, 97.5)), 3)], "n": int(len(x))}


def h4_engagement(df):
    res = {}
    target = "like_rate"
    df = df.dropna(subset=[target])  # rank only among videos with public like counts
    # within-category ranks remove between-category differences in both feature and engagement
    ranked = df.copy()
    for f in CORE + [target]:
        ranked[f] = df.groupby("category")[f].rank(pct=True)
    for name, d in [("raw", df), ("within_category", ranked)]:
        rows = {}
        for f in CORE:
            r = spearman_boot(d[f].astype(float).values, d[target].astype(float).values)
            if r:
                rows[f] = r
        q = bh([v["p"] for v in rows.values()])
        for (k, v), qq in zip(rows.items(), q):
            v["q_bh"] = round(qq, 3)
            v["p"] = round(v["p"], 4)
        res[name] = dict(sorted(rows.items(), key=lambda kv: kv[1]["p"]))
    # confounder check: does audience size alone relate to like_rate?
    res["confounder_log_subs"] = spearman_boot(df["log_subs"].astype(float).values, df[target].astype(float).values)
    res["confounder_log_views"] = spearman_boot(df["log_views"].astype(float).values, df[target].astype(float).values)
    res["like_rate_by_category"] = {c: round(float(g[target].median()), 4) for c, g in df.groupby("category")}
    return res


def energy_arcs(df, n_bins=20):
    curves, ids = [], []
    for vid in df["video_id"]:
        a = json.loads((VID / vid / "audio.json").read_text())["loudness"]
        t, db = np.array(a["t"]), np.array(a["db"])
        if len(t) < n_bins * 2:
            continue
        edges = np.linspace(0, t.max() + 1e-6, n_bins + 1)
        prof = np.array([db[(t >= edges[i]) & (t < edges[i + 1])].mean() for i in range(n_bins)])
        prof = np.clip(prof, -60, 0)
        curves.append(prof - prof.mean())
        ids.append(vid)
    C = np.array(curves)
    cat_of = dict(zip(df["video_id"], df["category"]))
    by_cat = {}
    for vid, c in zip(ids, C):
        by_cat.setdefault(cat_of[vid], []).append(c)
    opening = {vid: float(c[:2].mean() - c[2:].mean()) for vid, c in zip(ids, C)}
    df["opening_contrast_db"] = df["video_id"].map(opening)
    return {"n_bins": n_bins, "note": "loudness per 5% of runtime, mean-centred per video (dB)",
            "median_profile_by_category": {k: [round(float(x), 2) for x in np.median(np.array(cs), axis=0)]
                                           for k, cs in by_cat.items()},
            "opening_contrast_by_category": {k: round(float(np.median([c[:2].mean() - c[2:].mean() for c in v])), 2)
                                             for k, v in by_cat.items()},
            "profiles": {vid: [round(float(v), 2) for v in c] for vid, c in zip(ids, curves)}}


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(float(o)) else float(o)
    return o


def main():
    df = load()
    out = {"n_videos": len(df), "n_by_category": df["category"].value_counts().to_dict(),
           "H1_category_differences": h1_by_category(df), "H2_hooks": h2_hooks(df),
           "H3_archetypes": h3_archetypes(df), "H4_engagement": h4_engagement(df), "energy_arcs": energy_arcs(df)}
    if "n_recs" in df:
        d = df.dropna(subset=["n_recs"])
        out["critique_grounding"] = {"videos": int(len(d)), "recs": int(d.n_recs.sum()),
                                     "recs_grounded": int(d.recs_grounded.sum()),
                                     "evidence_items": int(d.evidence_items.sum()),
                                     "evidence_verified": int(d.evidence_verified.sum())}
    RES.mkdir(exist_ok=True)
    df.to_csv(RES / "corpus_features.csv", index=False)
    (RES / "stats.json").write_text(json.dumps(clean(out), indent=1))
    print(f"n={len(df)}")
    for k, v in list(out["H1_category_differences"].items())[:8]:
        print(f"H1 {k:26s} eps2={v['epsilon2']:.2f} q={v['q_bh']}")
    h3 = out["H3_archetypes"]
    print("H3 k", h3["k"], "sil", h3["silhouette"], "ARI vs category", h3["ari_vs_category"])
    for c, p in h3["profiles"].items():
        print("  ", c, p["n"], p["high"], p["categories"])
    for name in ["raw", "within_category"]:
        top = list(out["H4_engagement"][name].items())[:4]
        print("H4", name, [(k, v["rho"], v["q_bh"]) for k, v in top])
    print("H4 confounders", out["H4_engagement"]["confounder_log_subs"], out["H4_engagement"]["confounder_log_views"])
    print("opening contrast dB", out["energy_arcs"]["opening_contrast_by_category"])


if __name__ == "__main__":
    main()
