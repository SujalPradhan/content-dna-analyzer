"""Build data/corpus.csv reproducibly from YouTube search results (no hand-picked URLs).

For each category: run 2 search queries (40 results each, metadata only), keep public videos within the
duration window, one video per channel, then pick 6 spread across view-count tertiles (2 low, 2 mid, 2 high)
so the corpus is not only mega-hits. Selection is seeded and logged.
"""
import csv
import random
import sys
from pathlib import Path

import yt_dlp

ROOT = Path(__file__).resolve().parents[1]
PER_CAT = 6
CATEGORIES = {
    "tech_review": (["smartphone review 2025", "laptop review honest"], 120, 900),
    "cooking": (["easy dinner recipe", "how to cook pasta recipe"], 120, 900),
    "explainer": (["science explained animation", "how does it work explained"], 180, 900),
    "vlog": (["day in my life vlog", "travel vlog weekend"], 180, 900),
    "ad": (["official tv commercial 2025", "best super bowl commercial"], 15, 120),
    "shorts": (["#shorts cooking hack", "#shorts tech tip"], 10, 60),
}


def search(q: str, n: int = 40) -> list[dict]:
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist"}) as ydl:
        res = ydl.extract_info(f"ytsearch{n}:{q}", download=False)
    return [e for e in res.get("entries", []) if e]


def main(seed: int = 7) -> None:
    rng = random.Random(seed)
    rows, log = [], []
    for cat, (queries, lo, hi) in CATEGORIES.items():
        pool, seen_ch = [], set()
        for q in queries:
            for e in search(q):
                dur, ch, views = e.get("duration"), e.get("channel_id") or e.get("channel"), e.get("view_count")
                if not dur or not (lo <= dur <= hi) or views is None or ch in seen_ch or e.get("live_status") == "is_live":
                    continue
                seen_ch.add(ch)
                pool.append({"id": e["id"], "title": e.get("title"), "channel": e.get("channel"), "duration": dur,
                             "views": views, "query": q})
        pool.sort(key=lambda r: r["views"])
        k = len(pool) // 3
        tiers = [pool[:k], pool[k:2 * k], pool[2 * k:]]
        picked = []
        for tier_name, tier in zip(["low", "mid", "high"], tiers):
            for r in rng.sample(tier, min(PER_CAT // 3, len(tier))):
                r["view_tier"] = tier_name
                picked.append(r)
        log.append(f"{cat}: pool={len(pool)} picked={len(picked)}")
        for r in picked:
            url = f"https://www.youtube.com/shorts/{r['id']}" if cat == "shorts" else f"https://www.youtube.com/watch?v={r['id']}"
            rows.append({"url": url, "category": cat, "title": r["title"], "channel": r["channel"],
                         "duration_s": r["duration"], "views_at_selection": r["views"], "view_tier": r["view_tier"],
                         "query": r["query"]})
    out = ROOT / "data" / "corpus.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\n".join(log), f"\nwrote {len(rows)} rows -> {out}", sep="\n")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 7)
