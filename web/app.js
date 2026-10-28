// Analyzer app: submits jobs to the API, polls them, and shows any analysed video in the explorer.
(function () {
  const $ = (id) => document.getElementById(id);
  const GENRE = { ad: 'Ads', cooking: 'Cooking', explainer: 'Explainers', shorts: 'Shorts', tech_review: 'Tech reviews', vlog: 'Vlogs', uncategorised: 'Uncategorised' };
  const STAGES = ['download', 'visual signals', 'audio + transcript', 'vision timeline', 'fingerprint', 'critique', 'done'];
  let mode = 'url', videos = [], current = null, lastVideo = null;

  // ---- tabs
  document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => {
    mode = b.dataset.tab;
    document.querySelectorAll('.tabs button').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
    $('f-url').hidden = mode !== 'url'; $('f-file').hidden = mode !== 'file';
  }));

  fetch('/api/genres').then((r) => r.json()).then((g) => {
    $('genre-hint').textContent = `Detection uses the video's measured structure and is right ${Math.round(g.auto.loo_accuracy * 100)}% of the time on our ${g.auto.n} videos (chance: ${Math.round(g.auto.chance * 100)}%). Pick the genre if you know it.`;
  }).catch(() => {});

  // ---- library
  async function loadLibrary() {
    videos = await (await fetch('/api/videos')).json();
    drawLibrary();
  }
  function drawLibrary() {
    const q = $('q').value.toLowerCase();
    const lib = $('lib'); lib.replaceChildren();
    const groups = {};
    videos.filter((v) => !q || `${v.title} ${v.channel} ${GENRE[v.genre]}`.toLowerCase().includes(q)).forEach((v) => (groups[v.genre] ||= []).push(v));
    Object.keys(groups).sort().forEach((g) => {
      const h = document.createElement('h3'); const i = document.createElement('i'); i.style.background = `var(--genre-${g})`; h.append(i, `${GENRE[g] || g} (${groups[g].length})`); lib.append(h);
      groups[g].forEach((v) => {
        const b = document.createElement('button'); b.type = 'button'; b.setAttribute('aria-current', String(v.video_id === current));
        const s = document.createElement('small'); s.textContent = `${v.channel || 'uploaded file'} · ${DNAExplorer.mmss(v.duration)}${v.has_critique ? '' : ' · no critique'}`;
        b.append(v.title || v.video_id, s); b.addEventListener('click', () => show(v.video_id)); lib.append(b);
      });
    });
  }
  $('q').addEventListener('input', drawLibrary);

  async function show(id) {
    current = id; drawLibrary();
    const v = await (await fetch(`/api/videos/${encodeURIComponent(id)}`)).json();
    lastVideo = v;
    $('empty').hidden = true; $('view').hidden = false;
    DNAExplorer.render($('explorer'), v, { player: true });
    const links = $('links'); links.replaceChildren();
    [[`/api/videos/${id}`, 'Download report JSON ↓'], [`/reports/${id}`, 'Printable HTML report'], ['/docs', 'API docs']].forEach(([h, t]) => {
      const a = document.createElement('a'); a.href = h; a.textContent = t; a.target = '_blank'; a.rel = 'noopener'; links.append(a);
    });
    history.replaceState(null, '', `#${id}`);
  }
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => lastVideo && DNAExplorer.render($('explorer'), lastVideo, { player: true }), 300); });

  // ---- submit + poll
  function drawJob(j) {
    const box = $('job'); box.hidden = false; box.replaceChildren();
    const head = document.createElement('div');
    head.textContent = j.status === 'error' ? 'Analysis failed' : j.status === 'done' ? 'Done' : (j.title ? `Analyzing “${j.title}”` : 'Starting…');
    box.append(head);
    if (j.status === 'error') { const e = document.createElement('div'); e.className = 'err'; e.textContent = j.error; box.append(e); return; }
    const ul = document.createElement('ul'); ul.className = 'steps';
    const idx = STAGES.indexOf(j.stage);
    STAGES.filter((s) => s !== 'done' && (s !== 'critique' || j.critique)).forEach((s) => {
      const li = document.createElement('li'); const k = STAGES.indexOf(s);
      li.className = j.status === 'done' || k < idx ? 'done' : k === idx ? 'now' : 'todo'; li.textContent = s; ul.append(li);
    });
    box.append(ul);
  }
  $('form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const genre = $('genre').value, critique = $('crit').checked;
    const start = Math.max(0, +$('start').value || 0), seconds = Math.min(900, Math.max(5, +$('seconds').value || 900));
    let res;
    $('go').disabled = true;
    try {
      if (mode === 'url') {
        const url = $('url').value.trim(); if (!url) throw new Error('Paste a YouTube URL first.');
        res = await fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, genre, critique, start, seconds }) });
      } else {
        const f = $('file').files[0]; if (!f) throw new Error('Choose a video file first.');
        const fd = new FormData(); fd.append('file', f); fd.append('genre', genre); fd.append('critique', String(critique)); fd.append('start', String(start)); fd.append('seconds', String(seconds));
        res = await fetch('/api/analyze/upload', { method: 'POST', body: fd });
      }
      const j = await res.json(); if (!res.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'Request rejected: check the URL, start and length');
      drawJob({ status: 'queued', stage: 'queued', critique });
      const poll = async () => {
        const s = await (await fetch(`/api/jobs/${j.job_id}`)).json(); drawJob(s);
        if (s.status === 'done') { $('go').disabled = false; await loadLibrary(); show(s.video_id); }
        else if (s.status === 'error') $('go').disabled = false;
        else setTimeout(poll, 2000);
      };
      poll();
    } catch (err) {
      $('go').disabled = false; drawJob({ status: 'error', error: err.message });
    }
  });

  loadLibrary().then(() => { const id = decodeURIComponent(location.hash.slice(1)); if (id) show(id); });
  addEventListener('hashchange', () => { const id = decodeURIComponent(location.hash.slice(1)); if (id && id !== current) show(id); });
})();
