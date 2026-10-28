"""Self-contained per-video HTML report: fingerprint, structure strip, signal timeline, evidence-checked findings."""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from .fingerprint import FIELDS

ROLE_COLORS = {"hook": "#d1495b", "intro_setup": "#edae49", "context": "#c9c9c9", "main_content": "#00798c",
               "demonstration": "#30638e", "payoff_reveal": "#6a4c93", "recap": "#8ab17d", "cta": "#e76f51",
               "sponsor_ad_read": "#9c6644", "outro": "#7d7d7d"}

CSS = """:root{--bg:#fbfaf8;--fg:#1f2328;--muted:#656d76;--line:#d8dee4;--card:#fff;--ok:#1a7f37;--bad:#cf222e}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8d96a0;--line:#30363d;--card:#161b22;--ok:#3fb950;--bad:#f85149}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,sans-serif;margin:0;padding:24px 16px}
main{max-width:980px;margin:auto}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:10px 0}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:4px 6px;border-bottom:1px solid var(--line);text-align:left}
.tag{display:inline-block;border:1px solid var(--line);border-radius:12px;padding:1px 9px;margin:2px;font-size:12px}
.ev{font-size:12.5px;margin:2px 0}.ok{color:var(--ok)}.bad{color:var(--bad)}svg text{fill:var(--muted);font-size:10px}
.strip{display:flex;height:26px;border-radius:4px;overflow:hidden}.strip div{color:#fff;font-size:10px;padding:5px 3px;overflow:hidden;white-space:nowrap}
.frames img{width:150px;margin:2px;border-radius:4px}"""


def _mmss(t: float) -> str:
    t = max(0, float(t))
    return f"{int(t // 60)}:{t % 60:04.1f}"


def _line(xs, ys, w, h, dur, lo, hi, color):
    if not xs:
        return ""
    pts = " ".join(f"{x / dur * w:.1f},{h - (min(max(y, lo), hi) - lo) / (hi - lo + 1e-9) * h:.1f}" for x, y in zip(xs, ys))
    return f'<polyline fill="none" stroke="{color}" stroke-width="1.2" points="{pts}"/>'


def timeline_svg(vis, aud, dur, w=940) -> str:
    h = 60
    L = aud["loudness"]
    rows = []
    rows.append(f'<text x="0" y="10">loudness (dB)</text><g transform="translate(0,14)">'
                + _line(L["t"], L["db"], w, h, dur, -60, 0, "#00798c") + "</g>")
    C = vis["curves"]
    mmax = max(C["motion"] or [0.01]) or 0.01
    rows.append(f'<text x="0" y="{h + 34}">motion</text><g transform="translate(0,{h + 38})">'
                + _line(C["t"], C["motion"], w, h * 0.6, dur, 0, mmax, "#6a4c93") + "</g>")
    y0 = h + 38 + h * 0.6 + 14
    cuts = "".join(f'<line x1="{s / dur * w:.1f}" x2="{s / dur * w:.1f}" y1="{y0}" y2="{y0 + 16}" stroke="#d1495b" stroke-width="1"/>'
                   for s, _ in vis["shots"][1:])
    rows.append(f'<text x="0" y="{y0 - 3}">cuts</text>{cuts}')
    y1 = y0 + 32
    words = "".join(f'<rect x="{wd["s"] / dur * w:.1f}" y="{y1}" width="{max(0.5, (wd["e"] - wd["s"]) / dur * w):.1f}" height="10" fill="#edae49"/>'
                    for wd in aud["transcript"]["words"])
    rows.append(f'<text x="0" y="{y1 - 3}">speech</text>{words}')
    ticks = "".join(f'<text x="{t / dur * w:.0f}" y="{y1 + 26}">{_mmss(t)}</text>' for t in
                    [dur * k / 8 for k in range(8)])
    return f'<svg viewBox="0 0 {w} {y1 + 30}" width="100%" role="img" aria-label="signal timeline">{"".join(rows)}{ticks}</svg>'


def render(workdir: Path) -> Path:
    feats = json.loads((workdir / "features.json").read_text())
    vis = json.loads((workdir / "visual.json").read_text())
    aud = json.loads((workdir / "audio.json").read_text())
    crit = json.loads((workdir / "critique.json").read_text()) if (workdir / "critique.json").exists() else None
    fp, dur = feats["fingerprint"], feats["fingerprint"]["duration_s"]
    e = html.escape
    parts = [f"<h1>{e(feats.get('title') or feats['video_id'])}</h1>",
             f"<div class=muted>{e(feats.get('channel') or '')} · {e(feats['category'])} · analysed {_mmss(dur)}"
             + (f" · <a href='{e(feats['url'])}'>source</a>" if feats.get("url") else "") + "</div>"]
    if crit:
        parts.append(f"<div class=card>{e(crit['summary'])}<div>"
                     + "".join(f"<span class=tag>{e(t)}</span>" for t in crit["dna_tags"]) + "</div></div>")
        strip = "".join(f'<div title="{e(s["label"])}" style="width:{max(0.3, (s["end_s"] - s["start_s"]) / dur * 100):.2f}%;'
                        f'background:{ROLE_COLORS.get(s["role"], "#999")}">{e(s["role"])}</div>' for s in crit["structure"])
        parts.append(f"<h2>Structure</h2><div class=strip>{strip}</div>")
    parts.append(f"<h2>Signals</h2>{timeline_svg(vis, aud, dur)}")
    frames = sorted((workdir / "hook").glob("*.jpg"))
    if frames:
        parts.append("<h2>Opening 15 seconds</h2><div class=frames>" + "".join(
            f'<img alt="{f.stem}" src="data:image/jpeg;base64,{base64.b64encode(f.read_bytes()).decode()}">' for f in frames) + "</div>")
    if crit:
        g = crit["grounding"]
        parts.append(f"<h2>Recommendations</h2><div class=muted>Evidence check: {g['evidence_verified']}/{g['evidence_items']} "
                     f"cited evidence items verified against measured data; {g['recs_grounded']}/{g['recs']} recommendations have ≥1 verified item. "
                     "These are hypotheses to test, not performance predictions.</div>")
        checks = g["checks"]
        for i, r in enumerate(crit["recommendations"]):
            evs = "".join(f'<div class=ev><span class="{"ok" if c["verified"] else "bad"}">{"✓" if c["verified"] else "✗ unverified"}</span> '
                          f'{e(c["kind"])}: {e(c["ref"])} {e(c["value"])}</div>' for c in checks if c["owner"] == f"rec{i}")
            parts.append(f"<div class=card><b>{e(r['title'])}</b> <span class=muted>@ {_mmss(r['t_snapped_s'])}–{_mmss(r['t_end_s'])}"
                         f" · {e(r['priority'])} · basis: {e(r['basis'])}</span><p>{e(r['observation'])}</p>"
                         f"<p><b>Try:</b> {e(r['recommendation'])}</p>{evs}</div>")
        parts.append("<h2>Strengths</h2>" + "".join(f"<div class=card>@ {_mmss(s['t_s'])} — {e(s['point'])}</div>" for s in crit["strengths"]))
        h = crit["hook"]
        parts.append(f"<h2>Hook</h2><div class=card><p>{e(h['what_happens'])}</p><p><b>Promise:</b> {e(h['promise'])}</p>"
                     f"<p><b>+</b> {e('; '.join(h['strengths']))}</p><p><b>−</b> {e('; '.join(h['weaknesses']))}</p></div>")
    rows = "".join(f"<tr><td>{e(lbl)}</td><td>{e(grp)}</td><td>{fp[k]}</td><td class=muted>{e(unit)}</td></tr>"
                   for k, (grp, lbl, unit) in FIELDS.items())
    parts.append(f"<h2>Fingerprint</h2><table><tr><th>Feature</th><th>Group</th><th>Value</th><th>Unit</th></tr>{rows}</table>")
    out = workdir / "report.html"
    out.write_text(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                   f"<title>Content DNA report</title><style>{CSS}</style><main>{''.join(parts)}</main>")
    return out
