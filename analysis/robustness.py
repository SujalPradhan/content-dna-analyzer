"""Stress-test the one engagement association that survived FDR (talking_head_share ~ like_rate, within category)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
rng = np.random.default_rng(0)


def within_rank(df, cols):
    d = df.copy()
    for c in cols:
        d[c] = df.groupby("category")[c].rank(pct=True)
    return d


def main(feat="talking_head_share", target="like_rate"):
    df = pd.read_csv(ROOT / "results/corpus_features.csv").dropna(subset=[target, feat])
    r = within_rank(df, [feat, target, "log_views", "log_subs"])
    out = {"feature": feat, "target": target, "n": len(df)}
    rho, p = stats.spearmanr(r[feat], r[target])
    out["within_category_rho"], out["p"] = round(float(rho), 3), round(float(p), 4)
    # permutation test that shuffles the feature WITHIN each category (keeps category structure)
    perm = []
    for _ in range(5000):
        sh = r.groupby("category")[feat].transform(lambda s: s.sample(frac=1, random_state=int(rng.integers(1e9))).values)
        perm.append(stats.spearmanr(sh, r[target])[0])
    out["perm_p_within_category"] = round(float(np.mean(np.abs(perm) >= abs(rho))), 4)
    # leave-one-category-out
    out["leave_one_category_out"] = {c: round(float(stats.spearmanr(r[r.category != c][feat], r[r.category != c][target])[0]), 3)
                                     for c in sorted(df.category.unique())}
    # partial: control for audience size (log views, log subs) via rank residuals
    import numpy.linalg as la
    Z = np.column_stack([np.ones(len(r)), r["log_views"].fillna(r["log_views"].median()), r["log_subs"].fillna(r["log_subs"].median())])
    res = lambda y: y - Z @ la.lstsq(Z, y, rcond=None)[0]
    pr, pp = stats.pearsonr(res(r[feat].values), res(r[target].values))
    out["partial_rho_controlling_views_subs"] = round(float(pr), 3)
    out["partial_p"] = round(float(pp), 4)
    # how many videos have ANY talking head
    out["share_with_any_talking_head"] = round(float((df[feat] > 0).mean()), 2)
    out["by_category_rho"] = {c: (round(float(stats.spearmanr(g[feat], g[target])[0]), 2) if g[feat].nunique() > 1 else None, len(g))
                              for c, g in df.groupby("category")}
    (ROOT / "results/eval/robustness.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
