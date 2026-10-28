"""Shot-detection precision/recall against manual contact-sheet labels (results/eval/shot_labels.json)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOL = 1.0


def match(manual, detected, tol=TOL):
    used, tp = set(), 0
    for m in manual:
        best = min((abs(d - m), i) for i, d in enumerate(detected) if i not in used) if len(used) < len(detected) else (99, -1)
        if best[0] <= tol:
            used.add(best[1])
            tp += 1
    return tp


def main():
    labels = json.loads((ROOT / "results/eval/shot_labels.json").read_text())
    rows, TP, M, D = [], 0, 0, 0
    for vid, L in labels.items():
        if vid.startswith("_"):
            continue
        a, b = L["window"]
        man = [c for c in L["manual_cuts"] if a < c < b]
        det = [c for c in L["detected"] if a < c < b]
        tp = match(man, det)
        TP, M, D = TP + tp, M + len(man), D + len(det)
        rows.append({"video_id": vid, "style": L["style"], "manual": len(man), "detected": len(det), "tp": tp,
                     "precision": round(tp / len(det), 2) if det else None, "recall": round(tp / len(man), 2) if man else None})
    pooled = {"precision": round(TP / D, 3), "recall": round(TP / M, 3), "tp": TP, "manual": M, "detected": D}
    out = {"tolerance_s": TOL, "per_video": rows, "pooled": pooled}
    (ROOT / "results/eval/shot_eval.json").write_text(json.dumps(out, indent=1))
    for r in rows:
        print(r)
    print("pooled", pooled)


if __name__ == "__main__":
    main()
