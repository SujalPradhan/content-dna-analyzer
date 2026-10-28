/* Content DNA video explorer: a YouTube player synced to the analysis timeline.
   DNAExplorer.render(container, video, {player: true}) — `video` is the shape returned by GET /api/videos/{id}.
   Where YouTube can't be embedded (sandboxed pages), timestamps become links that open YouTube at that moment. */
(function () {
  const ROLE = { hook: ['Hook', 'r1'], intro_setup: ['Setup', 'r2'], context: ['Context', 'r0'], main_content: ['Main content', 'r3'],
    demonstration: ['Demonstration', 'r4'], payoff_reveal: ['Payoff', 'r5'], recap: ['Recap', 'r0'], cta: ['Call to action', 'r6'],
    sponsor_ad_read: ['Sponsor read', 'r7'], outro: ['Outro', 'r0'] };
  const FMT = { talking_head: ['Talking head', 'f1'], interview_multi_person: ['Talking head', 'f1'], b_roll: ['B-roll', 'f2'],
    product_closeup: ['Product close-up', 'f2'], screen_recording: ['Screen', 'f3'], slides: ['Slides', 'f3'],
    graphics_text: ['Graphics / text', 'f3'], animation: ['Animation', 'f4'], gameplay: ['Gameplay', 'f4'],
    performance_music: ['Performance', 'f4'], other: ['Other', 'f0'] };
  const BASIS = { measured_outlier_vs_corpus: 'Outlier vs genre', internal_inconsistency: 'Inconsistency', craft_heuristic: 'Craft heuristic' };
  const GENRE = { ad: 'Ads', cooking: 'Cooking', explainer: 'Explainers', shorts: 'Shorts', tech_review: 'Tech reviews', vlog: 'Vlogs', uncategorised: 'Uncategorised' };

  const CSS = `
.dx{--dx-r0:#a8a69e;--dx-r1:#d6453d;--dx-r2:#e8892f;--dx-r3:#2a78d6;--dx-r4:#1a9a8a;--dx-r5:#8a56d6;--dx-r6:#c99a06;--dx-r7:#9c6644;
--dx-f0:#b9b8b0;--dx-f1:#3d4f63;--dx-f2:#b07d48;--dx-f3:#4f8a8b;--dx-f4:#8a6f9e;--dx-ink:var(--color-fg,#1d1f22);--dx-muted:var(--color-fg-muted,#62656b);
--dx-line:var(--color-border-line,#e1e1dc);--dx-panel:var(--color-panel,#fff);--dx-bg:var(--color-bg,#f6f6f3);--dx-ok:var(--color-ok,#1a7f37);--dx-warn:var(--color-warn,#8a5a00);--dx-bad:var(--color-bad,#cf222e);
font-family:var(--font-anthropic-sans,system-ui,sans-serif);color:var(--dx-ink)}
.dx *{box-sizing:border-box}
.dx-head{display:flex;flex-wrap:wrap;gap:.5rem 1rem;align-items:baseline;margin-bottom:.75rem}
.dx-head h3{font-family:var(--font-anthropic-serif,Georgia,serif);font-weight:400;font-size:1.45rem;margin:0;flex:1 1 20rem;line-height:1.2}
.dx-chip{display:inline-flex;align-items:center;gap:.35rem;border:1px solid var(--dx-line);border-radius:999px;padding:.1rem .6rem;font-size:12px;white-space:nowrap;color:var(--dx-ink)}
.dx-chip i{width:.6rem;height:.6rem;border-radius:2px;display:inline-block}
.dx-top{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:1rem;align-items:start}
@media (max-width:760px){.dx-top{grid-template-columns:1fr}}
.dx-player{position:relative;aspect-ratio:16/9;max-width:100%;background:#000;border-radius:8px;overflow:hidden}
.dx-player iframe,.dx-player>div{position:absolute;inset:0;width:100%;height:100%}
.dx-noplayer{aspect-ratio:16/9;border:1px dashed var(--dx-line);border-radius:8px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:.4rem;text-align:center;padding:1rem;font-size:13px;color:var(--dx-muted)}
.dx-noplayer a{color:var(--dx-ink);font-weight:600}
.dx-now{border:1px solid var(--dx-line);border-radius:8px;padding:.75rem .9rem;background:var(--dx-panel);font-size:13px;display:grid;gap:.35rem}
.dx-now .t{font-variant-numeric:tabular-nums;font-weight:600;font-size:15px}
.dx-now .row{display:grid;grid-template-columns:6.5rem 1fr;gap:.5rem;align-items:baseline}
.dx-now .k{color:var(--dx-muted);font-size:12px}
.dx-sum{font-size:14px;line-height:1.55;margin:.25rem 0 .5rem}
.dx-tags{display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:.5rem}
.dx-lanes{margin-top:1rem;position:relative;user-select:none}
.dx-lanes svg{display:block;width:100%;cursor:pointer}
.dx-lanes text{font-size:11px;fill:var(--dx-muted)}
.dx-lanes .lab{fill:var(--dx-ink);font-weight:600}
.dx-legend{display:flex;flex-wrap:wrap;gap:.25rem .9rem;font-size:12px;color:var(--dx-muted);margin:.35rem 0 0}
.dx-legend span{display:inline-flex;align-items:center;gap:.3rem}.dx-legend i{width:.65rem;height:.65rem;border-radius:2px;display:inline-block}
.dx-tip{position:absolute;pointer-events:none;background:var(--cds-surface-popover,var(--dx-panel));border:1px solid var(--dx-line);border-radius:8px;box-shadow:0 4px 14px rgba(0,0,0,.14);padding:.35rem .55rem;font-size:12px;max-width:20rem;z-index:5}
.dx-tip .t{color:var(--dx-muted)}
.dx-cols{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:1rem;margin-top:1rem}
@media (max-width:760px){.dx-cols{grid-template-columns:1fr}}
.dx h4{font-size:15px;margin:0 0 .5rem;font-weight:600}
.dx-rec{border:1px solid var(--dx-line);border-left-width:4px;border-radius:8px;padding:.6rem .75rem;margin-bottom:.6rem;background:var(--dx-panel)}
.dx-rec.high{border-left-color:var(--dx-r1)}.dx-rec.medium{border-left-color:var(--dx-r6)}.dx-rec.low{border-left-color:var(--dx-r0)}
.dx-rec .meta{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;font-size:12px;color:var(--dx-muted)}
.dx-rec b.title{display:block;font-size:14px;margin:.3rem 0 .15rem}
.dx-rec p{margin:.2rem 0;font-size:13px;line-height:1.5}
.dx-clamp{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.dx-mini{padding:.45rem .7rem}.dx-mini summary{display:flex;flex-wrap:wrap;gap:.45rem;align-items:center;cursor:pointer;font-size:14px}
.dx-mini summary .title{font-weight:600;flex:1 1 14rem}.dx-mini[open] summary{margin-bottom:.35rem}
.dx-ev{font-size:12px;color:var(--dx-muted);margin-top:.3rem;display:grid;gap:.1rem}
.dx-ev .ok{color:var(--dx-ok)}.dx-ev .bad{color:var(--dx-bad)}
.dx-ts{font:inherit;font-weight:600;font-variant-numeric:tabular-nums;border:1px solid var(--dx-line);border-radius:6px;padding:.05rem .45rem;background:var(--dx-bg);color:var(--dx-ink);cursor:pointer;text-decoration:none}
.dx-ts:hover,.dx-ts:focus-visible{outline:2px solid var(--dx-r3);outline-offset:1px}
.dx-side{display:grid;gap:.6rem;align-content:start}
.dx-card{border:1px solid var(--dx-line);border-radius:8px;padding:.6rem .75rem;background:var(--dx-panel);font-size:13px;line-height:1.5}
.dx-card ul{margin:.25rem 0 0;padding-left:1.1rem}
@media (prefers-reduced-motion:reduce){.dx *{transition:none!important}}
`;

  const mmss = (s) => { s = Math.max(0, +s || 0); const m = Math.floor(s / 60); return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`; };
  const el = (tag, attrs, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null) continue;
      if (k === 'class') n.className = v; else if (k === 'style') n.setAttribute('style', v); else if (k.startsWith('on')) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
    }
    for (const c of kids.flat()) if (c != null) n.append(c.nodeType ? c : document.createTextNode(String(c)));
    return n;
  };
  const varc = (root, name) => getComputedStyle(root).getPropertyValue(name).trim();
  const at = (list, t, a = 'start_s', b = 'end_s') => list.find((x) => x[a] <= t && t < x[b]);

  let ytPromise = null;
  function loadYT() {
    if (window.YT && window.YT.Player) return Promise.resolve(window.YT);
    if (ytPromise) return ytPromise;
    ytPromise = new Promise((resolve, reject) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { prev && prev(); resolve(window.YT); };
      const s = document.createElement('script'); s.src = 'https://www.youtube.com/iframe_api'; s.async = true;
      s.onerror = () => reject(new Error('blocked')); document.head.appendChild(s);
      setTimeout(() => reject(new Error('timeout')), 6000);
    });
    return ytPromise;
  }

  function render(root, v, opts = {}) {
    if (!document.getElementById('dx-css')) document.head.appendChild(el('style', { id: 'dx-css' }, CSS));
    if (root._dxTimer) clearInterval(root._dxTimer);
    root.replaceChildren();
    const box = el('div', { class: 'dx' }); root.appendChild(box);
    const dur = +v.duration || 1;
    const c = v.critique || {};
    const off = +v.start_offset || 0;  // report times are relative to the analysed excerpt
    const ytUrl = (t) => v.youtube_id ? `https://www.youtube.com/watch?v=${v.youtube_id}&t=${Math.floor(t + off)}s` : null;
    let player = null; let cur = 0;

    // ----- header
    const g = v.genre_inference;
    box.append(el('div', { class: 'dx-head' },
      el('h3', {}, v.title || v.video_id),
      el('span', { class: 'dx-chip' }, el('i', { style: `background:var(--genre-${v.genre},var(--dx-r0))` }), GENRE[v.genre] || v.genre,
        g && g.method !== 'given by caller' && g.confidence != null ? ` · inferred ${Math.round(g.confidence * 100)}%` : ''),
      el('span', { class: 'dx-chip' }, `${mmss(dur)} analysed`),
      c.grounding ? el('span', { class: 'dx-chip' }, `${c.grounding.evidence_verified}/${c.grounding.evidence_items} evidence verified`) : null,
      v.youtube_id ? el('a', { class: 'dx-chip', href: ytUrl(0), target: '_blank', rel: 'noopener' }, 'Open on YouTube ↗') : null));

    // ----- player + now panel
    const pbox = el('div');
    const now = el('div', { class: 'dx-now', 'aria-live': 'polite' });
    const right = el('div', {}, c.summary ? el('p', { class: opts.compact ? 'dx-sum dx-clamp' : 'dx-sum' }, c.summary) : null,
      c.tags && !opts.compact ? el('div', { class: 'dx-tags' }, c.tags.map((t) => el('span', { class: 'dx-chip' }, t))) : null, now);
    box.append(el('div', { class: 'dx-top' }, pbox, right));

    const noPlayer = () => {
      pbox.replaceChildren(el('div', { class: 'dx-noplayer' },
        el('div', {}, opts.noPlayerNote || 'This page blocks embedded players, so the video opens on YouTube instead.'),
        v.youtube_id ? el('a', { href: ytUrl(0), target: '_blank', rel: 'noopener' }, 'Watch on YouTube ↗') : el('div', {}, 'Uploaded file: no online player.'),
        v.youtube_id ? el('div', {}, 'Every timestamp below opens YouTube at that moment.') : null));
    };
    // Two players behind one interface: YouTube IFrame API for YouTube sources, HTML5 <video> for uploads.
    const follow = (getT) => { root._dxTimer = setInterval(() => { const t = getT(); if (t != null && Math.abs(t - cur) > 0.05) setTime(t); }, 250); };
    if (opts.player !== false && v.media_url) {
      const vid = el('video', { src: v.media_url, controls: '', preload: 'metadata', playsinline: '', style: 'position:absolute;inset:0;width:100%;height:100%;background:#000' });
      pbox.append(el('div', { class: 'dx-player' }, vid));
      player = { seekTo: (t) => { vid.currentTime = t; }, playVideo: () => vid.play().catch(() => {}), getCurrentTime: () => vid.currentTime, local: true };
      follow(() => vid.currentTime);
    } else if (opts.player !== false && v.youtube_id) {
      const holder = el('div', { class: 'dx-player' }, el('div', { id: `dx-yt-${v.video_id}-${Date.now()}` }));
      pbox.append(holder);
      loadYT().then((YT) => {
        const yt = new YT.Player(holder.firstChild, { videoId: v.youtube_id, playerVars: { rel: 0, modestbranding: 1, playsinline: 1, start: Math.floor(off) } });
        player = { seekTo: (t) => yt.seekTo(t + off, true), playVideo: () => yt.playVideo && yt.playVideo(),
          getCurrentTime: () => (yt.getCurrentTime ? yt.getCurrentTime() - off : null) };
        follow(() => player.getCurrentTime());
        if (opts.onPlayer) opts.onPlayer(true);
      }).catch(() => { noPlayer(); if (opts.onPlayer) opts.onPlayer(false); });
    } else noPlayer();

    const seek = (t, e) => {
      if (player && player.seekTo) { if (e) e.preventDefault(); player.seekTo(t); player.playVideo(); setTime(t); }
      else setTime(t);
    };
    const ts = (t) => {
      const href = player ? null : ytUrl(t);
      return el(href ? 'a' : 'button', { class: 'dx-ts', href, target: href ? '_blank' : null, rel: href ? 'noopener' : null, type: href ? null : 'button',
        title: 'Jump to this moment', onclick: (e) => { if (player) seek(t, e); else if (!href) setTime(t); } }, mmss(t));
    };

    // ----- lanes
    const lanesWrap = el('div', { class: 'dx-lanes' }); box.append(lanesWrap);
    const tip = el('div', { class: 'dx-tip', hidden: '' }); lanesWrap.append(tip);
    const W = Math.max(320, lanesWrap.clientWidth || root.clientWidth || 800);
    const mL = W < 520 ? 70 : 104, mR = 10, laneH = 22, gap = 8;
    const lanes = [['Structure', 'structure'], ['Visual format', 'format'], ['Cuts', 'cuts'], ['Speech', 'speech'], ['Loudness', 'loud'], ['Fixes', 'recs']];
    const pains = v.pain_points || null;  // from the scorecard: timestamped problems found by the detectors
    if (pains) lanes.splice(5, 0, ['Pain points', 'pain']);
    const li = (key) => lanes.findIndex((l) => l[1] === key);
    const painAt = (t) => (pains || []).filter((p) => p.t - 0.5 <= t && t <= (p.t_end ?? p.t) + 0.5);
    const H = lanes.length * (laneH + gap) + 22;
    const x = (t) => mL + (Math.min(dur, Math.max(0, t)) / dur) * (W - mL - mR);
    const ns = 'http://www.w3.org/2000/svg';
    const S = (tag, a) => { const n = document.createElementNS(ns, tag); for (const k in a) n.setAttribute(k, a[k]); return n; };
    const svg = S('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Timeline of structure, visual format, cuts, speech, loudness, pain points and recommendations' });
    lanesWrap.prepend(svg);
    const y = (i) => i * (laneH + gap);
    lanes.forEach(([name], i) => {
      const tx = S('text', { x: 0, y: y(i) + laneH / 2 + 4, class: 'lab' }); tx.textContent = name; svg.append(tx);
      svg.append(S('rect', { x: mL, y: y(i), width: W - mL - mR, height: laneH, rx: 3, fill: varc(box, '--dx-line'), 'fill-opacity': .35 }));
    });
    const blocks = (i, list, colorOf) => list.forEach((s) => {
      const w = Math.max(1, x(s.end_s) - x(s.start_s) - 1.5);
      svg.append(S('rect', { x: x(s.start_s), y: y(i), width: w, height: laneH, rx: 3, fill: varc(box, colorOf(s)) }));
    });
    const struct = c.structure || [];
    blocks(0, struct, (s) => `--dx-${(ROLE[s.role] || ['', 'r0'])[1]}`);
    struct.forEach((s) => { const w = x(s.end_s) - x(s.start_s); if (w > 60) { const t = S('text', { x: x(s.start_s) + 5, y: y(0) + 15, style: 'fill:#fff;font-weight:600' }); t.textContent = (ROLE[s.role] || [s.role])[0]; svg.append(t); } });
    blocks(1, v.formats || [], (s) => `--dx-${(FMT[s.format] || ['', 'f0'])[1]}`);
    (v.cuts || []).forEach((t) => svg.append(S('line', { x1: x(t), x2: x(t), y1: y(2) + 3, y2: y(2) + laneH - 3, stroke: varc(box, '--dx-ink'), 'stroke-width': 1, 'stroke-opacity': .7 })));
    (v.transcript || []).forEach((s) => svg.append(S('rect', { x: x(s.s), y: y(3) + 5, width: Math.max(1, x(s.e) - x(s.s)), height: laneH - 10, rx: 2, fill: varc(box, '--dx-r6') })));
    const L = v.loudness || { t: [], db: [] };
    if (L.t.length) {
      const yv = (db) => y(4) + laneH - ((Math.max(-60, Math.min(0, db)) + 60) / 60) * laneH;
      let d = `M${x(L.t[0])},${y(4) + laneH}`; L.t.forEach((t, k) => { d += `L${x(t)},${yv(L.db[k])}`; }); d += `L${x(L.t[L.t.length - 1])},${y(4) + laneH}Z`;
      svg.append(S('path', { d, fill: varc(box, '--dx-r3'), 'fill-opacity': .55 }));
    }
    (pains || []).forEach((p) => {
      const x0 = x(p.t), w = Math.max(6, x(p.t_end ?? p.t) - x0);
      svg.append(S('rect', { x: x0, y: y(li('pain')) + 3, width: w, height: laneH - 6, rx: 3, fill: varc(box, '--dx-bad'), 'fill-opacity': .8 }));
    });
    const recs = c.recommendations || [];
    recs.forEach((r, k) => {
      const cx = x(r.t);
      svg.append(S('circle', { cx, cy: y(li('recs')) + laneH / 2, r: 8, fill: varc(box, r.priority === 'high' ? '--dx-r1' : r.priority === 'medium' ? '--dx-r6' : '--dx-r0') }));
      const t = S('text', { x: cx, y: y(li('recs')) + laneH / 2 + 4, 'text-anchor': 'middle', style: 'fill:#fff;font-weight:700;font-size:10px' }); t.textContent = k + 1; svg.append(t);
    });
    const axisY = lanes.length * (laneH + gap) + 12;
    for (let k = 0; k <= 6; k++) { const t = (dur * k) / 6; const tx = S('text', { x: x(t), y: axisY, 'text-anchor': k === 0 ? 'start' : k === 6 ? 'end' : 'middle' }); tx.textContent = mmss(t); svg.append(tx); }
    const head = S('line', { x1: x(0), x2: x(0), y1: 0, y2: H - 18, stroke: varc(box, '--dx-ink'), 'stroke-width': 2 }); svg.append(head);
    const tAt = (ev) => { const r = svg.getBoundingClientRect(); const px = ((ev.clientX - r.left) / r.width) * W; return Math.min(dur, Math.max(0, ((px - mL) / (W - mL - mR)) * dur)); };
    svg.addEventListener('pointermove', (ev) => {
      const t = tAt(ev); const s = at(struct, t); const f = at(v.formats || [], t); const sp = at(v.transcript || [], t, 's', 'e');
      tip.replaceChildren(...[el('div', { class: 't' }, mmss(t) + (s ? ` · ${(ROLE[s.role] || [s.role])[0]}` : '')),
        f ? el('div', {}, (FMT[f.format] || [f.format])[0]) : null, sp ? el('div', {}, `“${sp.text.slice(0, 90)}${sp.text.length > 90 ? '…' : ''}”`) : null,
        ...painAt(t).slice(0, 2).map((p) => el('div', { style: 'color:var(--dx-bad)' }, `⚠ ${p.description}`))].filter(Boolean));
      tip.hidden = false; const r = lanesWrap.getBoundingClientRect(); let lx = ev.clientX - r.left + 12; if (lx + 240 > r.width) lx = ev.clientX - r.left - 252;
      tip.style.left = Math.max(0, lx) + 'px'; tip.style.top = (ev.clientY - r.top + 14) + 'px';
    });
    svg.addEventListener('pointerleave', () => { tip.hidden = true; });
    svg.addEventListener('click', (ev) => { const t = tAt(ev); if (player) seek(t, ev); else { setTime(t); const u = ytUrl(t); if (u && opts.openOnClick) window.open(u, '_blank', 'noopener'); } });
    const legend = el('div', { class: 'dx-legend' },
      [...new Map(struct.map((s) => [(ROLE[s.role] || [s.role, 'r0'])[0], (ROLE[s.role] || [s.role, 'r0'])[1]])).entries()].map(([n, k]) => el('span', {}, el('i', { style: `background:var(--dx-${k})` }), n)),
      el('span', {}, '·'),
      [...new Map((v.formats || []).map((s) => [(FMT[s.format] || [s.format, 'f0'])[0], (FMT[s.format] || [s.format, 'f0'])[1]])).entries()].map(([n, k]) => el('span', {}, el('i', { style: `background:var(--dx-${k})` }), n)));
    lanesWrap.append(legend);

    // ----- recommendations + side
    // compact: one line per recommendation (time, title, evidence count); the detail opens on click
    const evCount = (r) => `${r.evidence.filter((e) => e.verified).length}/${r.evidence.length} verified`;
    const recList = el('div', {}, el('h4', {}, 'Recommendations'),
      recs.length && opts.compact ? recs.map((r, k) => el('details', { class: `dx-rec dx-mini ${r.priority}` },
        el('summary', {}, el('b', {}, `#${k + 1}`), ts(r.t), el('span', { class: 'title' }, r.title), el('span', { class: 'dx-chip' }, evCount(r))),
        el('p', {}, r.observation), el('p', {}, el('b', {}, 'Try: '), r.recommendation),
        el('div', { class: 'dx-ev' }, r.evidence.map((e) => el('div', {}, el('span', { class: e.verified ? 'ok' : 'bad' }, e.verified ? '✓ ' : '✗ unverified '),
          `${e.kind}${e.ref ? ' ' + e.ref : ''}: ${String(e.value).slice(0, 140)}`)))))
      : recs.length ? recs.map((r, k) => el('div', { class: `dx-rec ${r.priority}` },
        el('div', { class: 'meta' }, el('b', {}, `#${k + 1}`), ts(r.t), el('span', { class: 'dx-chip' }, BASIS[r.basis] || r.basis), el('span', { class: 'dx-chip' }, `${r.priority} priority`),
          el('span', { class: 'dx-chip' }, `${r.evidence.filter((e) => e.verified).length}/${r.evidence.length} evidence verified`)),
        el('b', { class: 'title' }, r.title), el('p', {}, r.observation), el('p', {}, el('b', {}, 'Try: '), r.recommendation),
        el('div', { class: 'dx-ev' }, r.evidence.map((e) => el('div', {}, el('span', { class: e.verified ? 'ok' : 'bad' }, e.verified ? '✓ ' : '✗ unverified '),
          `${e.kind}${e.ref ? ' ' + e.ref : ''}: ${String(e.value).slice(0, 140)}`)))))
        : el('p', { class: 'dx-sum' }, 'No critique was run for this video (fingerprint only).'));
    const fp = v.fingerprint || {};
    const side = el('div', { class: 'dx-side' },
      c.hook && !opts.compact ? el('div', { class: 'dx-card' }, el('h4', {}, 'Hook'), c.hook.what_happens, el('div', {}, el('b', {}, 'Promise: '), c.hook.promise)) : null,
      (c.strengths || []).length && !opts.compact ? el('div', { class: 'dx-card' }, el('h4', {}, 'Strengths'), el('ul', {}, c.strengths.map((s) => el('li', {}, ts(s.t_s), ' ', s.point)))) : null,
      el('div', { class: 'dx-card' }, el('h4', {}, 'Key measurements'), el('ul', {},
        el('li', {}, `${(+fp.shots_per_min || 0).toFixed(1)} cuts/min · median shot ${(+fp.median_shot_s || 0).toFixed(1)} s`),
        el('li', {}, `${Math.round(+fp.wpm || 0)} words/min · speech covers ${Math.round((+fp.speech_coverage || 0) * 100)}% of runtime`),
        el('li', {}, `First voice at ${fp.time_to_first_word_s == null ? '—' : (+fp.time_to_first_word_s).toFixed(1) + ' s'} · ${fp.hook_cuts ?? '—'} cuts in first 15 s`),
        el('li', {}, `Talking head ${Math.round((+fp.talking_head_share || 0) * 100)}% · b-roll ${Math.round((+fp.broll_share || 0) * 100)}% · screen ${Math.round((+fp.screen_share || 0) * 100)}%`))));
    box.append(el('div', { class: 'dx-cols' }, recList, side));

    function setTime(t) {
      cur = t; head.setAttribute('x1', x(t)); head.setAttribute('x2', x(t));
      const s = at(struct, t), f = at(v.formats || [], t), sp = at(v.transcript || [], t, 's', 'e');
      const near = recs.map((r, k) => [r, k]).filter(([r]) => Math.abs(r.t - t) <= Math.max(5, dur * 0.03));
      now.replaceChildren(...[el('div', { class: 't' }, `At ${mmss(t)}`),
        el('div', { class: 'row' }, el('span', { class: 'k' }, 'Story beat'), s ? `${(ROLE[s.role] || [s.role])[0]} — ${s.label}` : '—'),
        el('div', { class: 'row' }, el('span', { class: 'k' }, 'On screen'), f ? `${(FMT[f.format] || [f.format])[0]}${f.on_screen_text ? ` · “${f.on_screen_text}”` : ''}` : '—'),
        el('div', { class: 'row' }, el('span', { class: 'k' }, 'Said'), sp ? `“${sp.text}”` : 'No speech here'),
        near.length ? el('div', { class: 'row' }, el('span', { class: 'k' }, 'Recommendation'), near.map(([r, k]) => `#${k + 1} ${r.title}`).join('; ')) : null,
        painAt(t).length ? el('div', { class: 'row', style: 'color:var(--dx-bad)' }, el('span', { class: 'k' }, 'Pain point'), painAt(t).map((p) => p.description).join('; ')) : null].filter(Boolean));
    }
    setTime(0);
    return { seek, setTime };
  }
  window.DNAExplorer = { render, mmss };
})();
