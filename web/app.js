// Analyzer app: video -> target genre + goal -> researched parameters -> scorecard, pain points, frames and fixes.
(function () {
  const $ = (id) => document.getElementById(id);
  const API = (window.DNA_API || '').replace(/\/$/, '');
  const GENRE = { ad: 'Ad', cooking: 'Cooking', explainer: 'Explainer', shorts: 'Short', tech_review: 'Tech review', vlog: 'Vlog' };
  const GOAL = { retention: 'Retention', virality: 'Reach & sharing', both: 'Retention + reach' };
  const EVIDENCE = { 'platform-official': ['Platform guidance', 'ev-a'], experimental: ['Experiment', 'ev-b'], observational: ['Observational', 'ev-c'], practitioner: ['Practitioner', 'ev-d'] };
  const STATUS = { problem: ['✕', 'Problem'], watch: ['!', 'Watch'], good: ['✓', 'Good'], unmeasured: ['–', 'Not measurable'] };
  const RUN_STAGES = ['download', 'visual signals', 'audio + transcript', 'vision timeline', 'fingerprint', 'scorecard', 'critique'];
  let mode = 'demo', demoId = null, genre = null, goal = 'both', catalogue = [], selected = new Set(), demos = [], ex = null, last = null, apiReady = false;

  // Demos are static files baked by scripts/build_static_demos.py: no API, LLM call or compute. Each parameter is scored
  // independently, so the goal and parameter choice is a filter over the stored per-genre scorecard.
  const demoCache = {};
  const loadDemo = async (id) => demoCache[id] ||= await (await fetch(`assets/demo/${id}.json`)).json();
  function filterCard(card, params, g) {
    const ps = card.parameters.filter((p) => params.includes(p.id) && (g === 'both' || p.goal === g || p.goal === 'both'));
    const counts = { problem: 0, watch: 0, good: 0, unmeasured: 0 }; ps.forEach((p) => { counts[p.status] += 1; });
    return { ...card, goal: g, parameters: ps, counts, pain_points: ps.flatMap((p) => p.flags).sort((a, b) => a.t - b.t) };
  }

  const store = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) { if (v == null) continue; if (k === 'class') n.className = v; else if (k.startsWith('on')) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v); }
    for (const c of kids.flat(Infinity)) if (c != null) n.append(c.nodeType ? c : document.createTextNode(String(c)));
    return n;
  };
  const headers = () => { const c = $('code').value || store.get('dna-code'); return c ? { 'X-Access-Code': c } : {}; };
  async function api(path, opts = {}) {
    const r = await fetch(API + path, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `Request failed (${r.status})`);
    return j;
  }
  const mmss = (s) => DNAExplorer.mmss(s);
  const fmtv = (v) => typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/\.?0+$/, '')) : String(v);

  // links that point at the API host when the page is served elsewhere (GitHub Pages)
  if (API) { $('nav-docs').href = API + '/docs'; }

  // ---------------------------------------------------------------- step 1: video
  document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => {
    mode = b.dataset.tab;
    document.querySelectorAll('.tabs button').forEach((x) => x.setAttribute('aria-selected', String(x === b)));
    $('f-demo').hidden = mode !== 'demo'; $('f-file').hidden = mode !== 'file'; $('f-url').hidden = mode !== 'url';
    $('crit-row').hidden = mode === 'demo'; $('demo-note').hidden = mode !== 'demo'; $('api-note').hidden = mode === 'demo' || !$('api-note').textContent;
    if (mode !== 'demo' && genre === null) genre = 'auto';
    drawGenres(); drawParams();
  }));
  function drawDemos() {
    const box = $('f-demo'); box.replaceChildren();
    demos.forEach((d) => {
      const b = el('button', { type: 'button', role: 'radio', class: 'demo', 'aria-checked': String(d.video_id === demoId) },
        el('b', {}, d.title.split(' | ')[0].slice(0, 60)), el('small', {}, `${d.label}`));
      b.addEventListener('click', () => { demoId = d.video_id; genre = d.genre; drawDemos(); drawGenres(); drawParams(); });
      box.append(b);
    });
  }

  // ---------------------------------------------------------------- step 2: target
  function drawGenres() {
    const box = $('genres'); box.replaceChildren();
    const opts = mode === 'demo' ? Object.keys(GENRE) : ['auto', ...Object.keys(GENRE)];
    if (mode === 'demo' && genre === 'auto') genre = demos.find((d) => d.video_id === demoId)?.genre || 'ad';
    opts.forEach((g) => {
      const b = el('button', { type: 'button', role: 'radio', class: `chip g-${g}`, 'aria-checked': String(g === genre) }, el('i'), g === 'auto' ? 'Detect' : GENRE[g]);
      b.addEventListener('click', () => { genre = g; drawGenres(); drawParams(); });
      box.append(b);
    });
  }
  document.querySelectorAll('#goals button').forEach((b) => b.addEventListener('click', () => {
    goal = b.dataset.goal;
    document.querySelectorAll('#goals button').forEach((x) => x.setAttribute('aria-checked', String(x === b)));
    drawParams();
  }));

  // ---------------------------------------------------------------- step 3: parameters
  const visible = () => catalogue.filter((p) => (goal === 'both' || p.goal === goal || p.goal === 'both') && (genre === 'auto' || !genre || p.genres.includes(genre)));
  function drawParams() {
    const box = $('params'); box.replaceChildren();
    const vis = visible();
    vis.forEach((p) => {
      const [evl, evc] = EVIDENCE[p.evidence_strength] || [p.evidence_strength, 'ev-d'];
      const cb = el('input', { type: 'checkbox', value: p.id }); cb.checked = selected.has(p.id);
      cb.addEventListener('change', () => { cb.checked ? selected.add(p.id) : selected.delete(p.id); count(); });
      box.append(el('label', { class: 'param', title: p.summary }, cb,
        el('span', { class: 'pn' }, p.name, el('small', {}, p.summary)), el('span', { class: `ev ${evc}` }, evl)));
    });
    count();
  }
  function count() { const n = visible().filter((p) => selected.has(p.id)).length; $('pcount').textContent = `${n} of ${visible().length}`; }
  $('p-all').addEventListener('click', (e) => { e.preventDefault(); visible().forEach((p) => selected.add(p.id)); drawParams(); });
  $('p-none').addEventListener('click', (e) => { e.preventDefault(); visible().forEach((p) => selected.delete(p.id)); drawParams(); });

  // ---------------------------------------------------------------- run + poll
  function drawJob(j, stages) {
    const box = $('job'); box.hidden = false; box.replaceChildren();
    box.append(el('div', {}, j.status === 'error' ? 'Analysis failed' : j.status === 'done' ? 'Done' : (j.title ? `Analyzing “${j.title}”` : 'Starting…')));
    if (j.status === 'error') { box.append(el('div', { class: 'err' }, j.error)); return; }
    const idx = stages.indexOf(j.stage);
    box.append(el('ul', { class: 'steps' }, stages.filter((s) => s !== 'critique' || j.critique).map((s, k) =>
      el('li', { class: j.status === 'done' || (idx >= 0 && stages.indexOf(s) < idx) ? 'done' : s === j.stage ? 'now' : 'todo' }, s))));
  }
  $('form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if ($('code').value) store.set('dna-code', $('code').value);
    const params = visible().filter((p) => selected.has(p.id)).map((p) => p.id);
    const critique = $('crit').checked;
    if (!params.length) { drawJob({ status: 'error', error: 'Pick at least one parameter.' }, []); return; }
    $('go').disabled = true;
    try {
      let job, stages = RUN_STAGES;
      if (mode === 'demo') {
        if (!demoId) throw new Error('Pick a demo video first.');
        const d = await loadDemo(demoId);
        $('go').disabled = false; $('job').hidden = true;
        show({ ...d.report, scorecard: filterCard(d.scorecards[genre], params, goal), staticShots: d.shots, fixesFor: d.fixes_for }, params);
        return;
      } else if (mode === 'file') {
        const f = $('file').files[0]; if (!f) throw new Error('Choose a video file first.');
        const fd = new FormData(); fd.append('file', f); fd.append('genre', genre || 'auto'); fd.append('goal', goal); fd.append('parameters', params.join(',')); fd.append('critique', String(critique));
        job = await api('/api/analyze/upload', { method: 'POST', body: fd });
      } else {
        const url = $('url').value.trim(); if (!url) throw new Error('Paste a YouTube URL first.');
        job = await api('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, genre: genre || 'auto', goal, parameters: params, critique }) });
      }
      drawJob({ status: 'queued', stage: 'queued', critique }, stages);
      const poll = async () => {
        let s;
        try { s = await api(`/api/jobs/${job.job_id}`); } catch (err) { setTimeout(poll, 3000); return; }
        drawJob(s, stages);
        if (s.status === 'done') { $('go').disabled = false; show(s.result, params); connectApi(); }
        else if (s.status === 'error') { $('go').disabled = false; connectApi(); }
        else setTimeout(poll, 2000);
      };
      poll();
    } catch (err) {
      $('go').disabled = false; drawJob({ status: 'error', error: err.message }, []);
      if (/access code/i.test(err.message)) $('f-code').hidden = false;
    }
  });

  // ---------------------------------------------------------------- results
  function show(r, params) {
    last = { r, params };
    const sc = r.scorecard;
    $('empty').hidden = true; $('view').hidden = false;
    const ff = r.fixesFor, other = ff && (ff.genre !== sc.genre || ff.goal !== sc.goal);
    $('r-eyebrow').textContent = `${GENRE[sc.genre] || sc.genre} · ${GOAL[sc.goal]} · ${sc.parameters.length} parameters${other ? ` · fixes written for ${GENRE[ff.genre]}, ${GOAL[ff.goal].toLowerCase()}` : ''}`;
    $('r-title').textContent = r.title || r.video_id;
    $('tally').replaceChildren(...['problem', 'watch', 'good'].map((k) => el('div', { class: `t t-${k}` }, el('b', {}, sc.counts[k] || 0), STATUS[k][1])));
    const v = { ...r, pain_points: sc.pain_points, media_url: r.media_url ? API + r.media_url : null };
    ex = DNAExplorer.render($('explorer'), v, { player: true, compact: true });
    drawCards(sc);
    drawFrames(r, sc, params);
    const links = $('links'); links.replaceChildren();
    if (r.staticShots) links.append(el('a', { href: `assets/demo/${r.video_id}.json`, target: '_blank', rel: 'noopener' }, 'Demo data JSON ↗'),
      el('a', { href: `${API}/docs`, target: '_blank', rel: 'noopener' }, 'API docs ↗'));
    else links.append(el('a', { href: `${API}/api/videos/${r.video_id}/scorecard?genre=${sc.genre}&goal=${sc.goal}&params=${params.join(',')}`, target: '_blank', rel: 'noopener' }, 'Scorecard JSON ↗'),
      el('a', { href: `${API}/api/videos/${r.video_id}`, target: '_blank', rel: 'noopener' }, 'Full report JSON ↗'),
      el('a', { href: `${API}/docs`, target: '_blank', rel: 'noopener' }, 'API docs ↗'));
    $('view').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  const jump = (t) => { if (ex) ex.seek(t); $('explorer').scrollIntoView({ behavior: 'smooth', block: 'center' }); };

  function drawCards(sc) {
    const box = $('cards'); box.replaceChildren();
    sc.parameters.forEach((p) => {
      const [ic, label] = STATUS[p.status];
      const [evl, evc] = EVIDENCE[p.evidence_strength] || [p.evidence_strength, 'ev-d'];
      const checks = p.checks.map((c) => el('li', { class: c.ok ? 'ok' : 'bad', title: c.basis },
        el('span', { class: 'ci' }, c.ok ? '✓' : '✕'), el('span', { class: 'cl' }, c.label),
        el('span', { class: 'cv' }, fmtv(c.value), el('span', { class: 'ct' }, ` / ${c.target}`)),
        c.heuristic ? el('span', { class: 'tag' }, c.corpus ? 'genre range' : 'heuristic') : el('span', { class: 'tag src' }, 'sourced')));
      const flags = p.flags.map((f) => el('li', {},
        el('button', { type: 'button', class: 'ts', onclick: () => jump(f.t) }, mmss(f.t) + (f.t_end ? `–${mmss(f.t_end)}` : '')),
        el('span', {}, el('b', {}, f.description), f.detail ? ` · ${f.detail}` : '')));
      box.append(el('article', { class: `card s-${p.status}` },
        el('div', { class: 'ch' }, el('span', { class: 'si' }, ic), el('h3', {}, p.name), el('span', { class: 'sl' }, label)),
        el('div', { class: 'meta' }, el('span', { class: `ev ${evc}` }, evl), el('span', { class: 'goal' }, GOAL[p.goal] || p.goal)),
        el('p', { class: 'sum' }, p.summary),
        checks.length ? el('ul', { class: 'checks' }, checks) : null,
        flags.length ? el('ul', { class: 'flags' }, flags) : null,
        p.status === 'unmeasured' ? el('p', { class: 'hint' }, 'We cannot measure this yet (e.g. logos, thumbnails). Shown so it is not forgotten.') : null,
        p.genre_note ? el('p', { class: 'hint' }, p.genre_note) : null,
        p.sources.length ? el('p', { class: 'src' }, 'Sources: ', p.sources.slice(0, 2).map((s, i) => [i ? ' · ' : '', el('a', { href: s.url, target: '_blank', rel: 'noopener' }, s.publisher || s.title)])) : null));
    });
  }

  function drawFrames(r, sc, params) {
    if (r.staticShots) {  // demo: frames are static files, pain points matched to shots here
      renderShots(r.staticShots.map((s) => ({ ...s, pain_points: sc.pain_points.filter((p) => p.t < s.end && (p.t_end ?? p.t + 0.5) > s.start) })), '');
      return;
    }
    $('frames').replaceChildren(el('p', { class: 'hint' }, 'Loading frames…'));
    api(`/api/videos/${r.video_id}/frames?genre=${sc.genre}&goal=${sc.goal}&params=${params.join(',')}`)
      .then((f) => renderShots(f.shots, API)).catch((err) => $('frames').replaceChildren(el('p', { class: 'err' }, err.message)));
  }
  function renderShots(shots, base) {
    const box = $('frames');
    box.replaceChildren(...shots.map((s) => {
        const bad = s.pain_points.length > 0;
        return el('button', { type: 'button', class: `fr${bad ? ' bad' : ''}`, title: bad ? s.pain_points.map((p) => p.description).join('\n') : `Shot ${s.shot + 1}`, onclick: () => jump(s.start) },
          s.image ? el('img', { src: base + s.image, alt: `Shot ${s.shot + 1} at ${mmss(s.start)}`, loading: 'lazy' }) : el('div', { class: 'noimg' }, 'no frame'),
          el('span', { class: 'cap' }, `${mmss(s.start)} · ${s.length.toFixed(1)} s`, bad ? el('b', {}, ` ⚠ ${s.pain_points[0].description}`) : null));
    }));
  }
  let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => last && show(last.r, last.params), 300); });

  // ---------------------------------------------------------------- boot
  // The demo flow runs from static files; the API is only needed for uploads and YouTube links, so connect to it in the
  // background and keep retrying while a scaled-to-zero server wakes up.
  async function connectApi(tries = 0) {
    try {
      const cfg = await api('/api/config');
      apiReady = true;
      const left = cfg.videos_left_today;
      $('api-note').textContent = cfg.daily_videos && left != null ? `${left} of ${cfg.daily_videos} free video analyses left today (shared by all visitors).` : '';
      $('api-note').hidden = mode === 'demo' || !$('api-note').textContent;
      if (cfg.access_code_required && !store.get('dna-code')) $('f-code').hidden = false;
      $('upload-hint').textContent = `(up to ${cfg.max_upload_mb} MB)`;
      $('crit-hint').textContent = '(~1–2 min)';
    } catch (err) {
      $('api-note').textContent = tries < 12 ? 'Waking up the analysis server for uploads and YouTube links…' : 'The analysis server is unavailable right now. The demos still work.';
      $('api-note').hidden = mode === 'demo';
      if (tries < 12) setTimeout(() => connectApi(tries + 1), 5000);
    }
  }
  (async () => {
    try {
      const idx = await (await fetch('assets/demo/index.json')).json();
      demos = idx.demos; catalogue = idx.parameters; catalogue.forEach((p) => selected.add(p.id));
      demoId = demos[0]?.video_id; genre = demos[0]?.genre || 'auto';
      drawDemos(); drawGenres(); drawParams();
      // deep link for presenting: #demo=<id>&genre=<g>&goal=<goal> opens that demo's results straight away
      const h = new URLSearchParams(location.hash.slice(1));
      if (h.get('demo') && demos.some((x) => x.video_id === h.get('demo'))) {
        demoId = h.get('demo'); genre = GENRE[h.get('genre')] ? h.get('genre') : demos.find((x) => x.video_id === demoId).genre;
        if (GOAL[h.get('goal')]) { goal = h.get('goal'); document.querySelectorAll('#goals button').forEach((x) => x.setAttribute('aria-checked', String(x.dataset.goal === goal))); }
        drawDemos(); drawGenres(); drawParams();
        $('form').requestSubmit();
      }
    } catch (err) {
      $('job').hidden = false; $('job').replaceChildren(el('div', { class: 'err' }, `Couldn't load the demo data: ${err.message}`));
    }
    connectApi();
  })();
})();
