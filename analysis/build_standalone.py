"""Build story/standalone.html: the data story as one self-contained page (data embedded, d3 from cdnjs).
It reuses story/index.html unchanged and supplies a small `dash` shim that serves the exported datasets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "results" / "story"
IDS = ["facts", "videos", "landscape", "cost", "format_mix",
       "engagement_tests", "evidence_by_kind", "judge_scores", "explorer", "frames"]
JSON_IDS = {"facts", "explorer", "frames"}

TOKENS = """
:root{color-scheme:dark;background:#0f1215}
body{background:#0f1215;color:#edf0f4;margin:0}
#dash-root{padding:0}
"""

SHIM = """
const RAW = %s;
const parsed = {};
const dark = () => document.documentElement.dataset.theme === 'dark' || (document.documentElement.dataset.theme !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
const LIGHT = ['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767'];  // dark-validated steps: the story is dark-only
const DARK = ['#3987e5','#d95926','#199e70','#c98500','#d55181','#008300','#9085e9','#e66767'];
const fns = [];
window.dash = {
  get colors() { return dark() ? DARK : LIGHT; },
  data(id) {
    const r = RAW[id]; if (!r) return { status: 'missing', data: [] };
    if (!parsed[id]) parsed[id] = r.kind === 'json' ? JSON.parse(r.text) : d3.csvParse(r.text);
    const rows = parsed[id]; return { status: 'ok', data: rows, columns: rows.columns || Object.keys(rows[0] || {}), meta: [] };
  },
  onData(fn) { fns.push(fn); fn(); },
  calc() {}, loader() {}, params() { return {}; }, setParams() {}, resetParams() {}, setLink() {}, refresh() {},
};
let t; const redraw = () => { clearTimeout(t); t = setTimeout(() => fns.forEach((f) => f()), 120); };
addEventListener('resize', redraw);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', redraw);
new MutationObserver(redraw).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
"""


def inline_explorer(page: str) -> str:
    marker = '<script data-inline="explorer">/* web/explorer.js is inlined here by analysis/build_standalone.py */</script>'
    assert marker in page
    return page.replace(marker, "<script>\n" + (ROOT / "web" / "explorer.js").read_text() + "\n</script>")


def main():
    raw = {}
    for i in IDS:
        p = STORY / (f"{i}.json" if i in JSON_IDS else f"{i}.csv")
        raw[i] = {"kind": "json" if i in JSON_IDS else "csv", "text": p.read_text()}
    page = inline_explorer((ROOT / "story" / "index.html").read_text())
    (ROOT / "story" / "index.built.html").write_text(page)  # the Dashboard artifact's page
    html = ('<meta charset="utf-8">\n<title>Content DNA</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,650;12..96,700&family=Instrument+Sans:wght@400;500;600;700&display=swap">\n'
            f"<style>{TOKENS}</style>\n"
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>\n'
            f"<script>{SHIM % json.dumps(raw)}</script>\n"
            f'<div id="dash-root">\n{page}\n</div>\n')
    out = ROOT / "story" / "standalone.html"
    out.write_text(html)
    print(out, len(html))


if __name__ == "__main__":
    main()
