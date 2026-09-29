import { parseRich, speakable, splitSentences } from './rich.js';

// ---------------------------------------------------------------- helpers
const $ = (selector, root = document) => root.querySelector(selector);

/** Build an element. Text always goes in as text nodes, never as HTML. */
function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'text') el.textContent = value;
    else if (key === 'value') el.value = value;
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function errorFrom(response) {
  let detail = response.statusText || `Error ${response.status}`;
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') detail = body.detail;
    else if (Array.isArray(body.detail) && body.detail[0]?.msg) detail = body.detail[0].msg;
  } catch { /* keep the status text */ }
  return new ApiError(detail, response.status);
}

async function api(path, { method = 'GET', json, form, signal } = {}) {
  const init = { method, headers: {}, credentials: 'same-origin', signal };
  if (json !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(json);
  }
  if (form) init.body = form;
  const response = await fetch(path, init);
  if (response.status === 401 && !path.startsWith('/api/auth/')) {
    await signedOut();
    throw new ApiError('Please sign in.', 401);
  }
  if (!response.ok) throw await errorFrom(response);
  return response.status === 204 ? null : response.json();
}

const state = {
  user: null, collections: [], documents: [], jobs: new Map(), notices: [],
  scope: new Set(), subject: 'General', streaming: null,
  conversationId: null, readAloud: false, voiceName: '', autoSend: true,
};

function loadPrefs() {
  try {
    const prefs = JSON.parse(localStorage.getItem('studybot.prefs') || '{}');
    if (Array.isArray(prefs.scope)) state.scope = new Set(prefs.scope);
    if (typeof prefs.subject === 'string' && prefs.subject) state.subject = prefs.subject;
    if (typeof prefs.readAloud === 'boolean') state.readAloud = prefs.readAloud;
    if (typeof prefs.voiceName === 'string') state.voiceName = prefs.voiceName;
    if (typeof prefs.autoSend === 'boolean') state.autoSend = prefs.autoSend;
  } catch { /* storage may be blocked; the app works without it */ }
}
function savePrefs() {
  try {
    localStorage.setItem('studybot.prefs', JSON.stringify({ scope: [...state.scope], subject: state.subject,
      readAloud: state.readAloud, voiceName: state.voiceName, autoSend: state.autoSend }));
  } catch { /* ignore */ }
}

// ---------------------------------------------------------------- sign in / up
async function fetchStatus() {
  try {
    const response = await fetch('/api/auth/status', { credentials: 'same-origin' });
    if (!response.ok) throw new Error(String(response.status));
    return await response.json();
  } catch { return { offline: true }; }  // the server cannot be reached (e.g. the computer is off)
}

function renderOffline() {
  document.body.dataset.view = '';
  $('#app').replaceChildren(h('div', { class: 'auth-wrap' }, h('div', { class: 'auth-card' },
    h('h1', {}, 'Study', h('span', { class: 'muted', text: 'Bot' })),
    h('p', { class: 'lede', text: 'Can’t reach StudyBot right now.' }),
    h('p', { text: 'StudyBot runs on your own computer. Make sure it is switched on and connected, then try again.' }),
    h('button', { class: 'btn primary', type: 'button', text: 'Try again', onclick: () => init() }))));
}

async function signedOut() {
  speaker.stop();
  state.conversationId = null;
  for (const source of trackers.values()) source.close();
  trackers.clear();
  state.user = null;
  state.jobs.clear();
  state.notices = [];
  const status = await fetchStatus();
  if (status.offline) renderOffline(); else renderAuth(status);
}

function renderAuth(status) {
  document.body.dataset.view = '';
  let mode = status.has_users ? 'login' : 'register';
  const root = $('#app');

  const draw = () => {
    const error = h('p', { class: 'error-text', role: 'alert' });
    const username = h('input', { class: 'input', id: 'username', autocomplete: 'username', required: true, maxlength: 32 });
    const password = h('input', {
      class: 'input', id: 'password', type: 'password', required: true, maxlength: 128,
      autocomplete: mode === 'login' ? 'current-password' : 'new-password',
    });
    const submit = h('button', { class: 'btn primary', type: 'submit', text: mode === 'login' ? 'Sign in' : 'Create account' });
    const form = h('form', {
      onsubmit: async (event) => {
        event.preventDefault();
        submit.disabled = true;
        error.textContent = '';
        try {
          state.user = await api(`/api/auth/${mode === 'login' ? 'login' : 'register'}`,
            { method: 'POST', json: { username: username.value, password: password.value } });
          await startApp();
        } catch (err) {
          error.textContent = err.message;
          submit.disabled = false;
        }
      },
    },
      h('div', { class: 'field' }, h('label', { for: 'username', text: 'Username' }), username),
      h('div', { class: 'field' }, h('label', { for: 'password', text: 'Password' }), password,
        mode === 'register' ? h('p', { class: 'hint', text: 'At least 8 characters.' }) : null),
      submit, error);

    const tabs = status.has_users && status.registration_open ? h('div', { class: 'auth-tabs', role: 'group' },
      h('button', { class: 'btn', type: 'button', 'aria-pressed': String(mode === 'login'), text: 'Sign in', onclick: () => { mode = 'login'; draw(); } }),
      h('button', { class: 'btn', type: 'button', 'aria-pressed': String(mode === 'register'), text: 'Create account', onclick: () => { mode = 'register'; draw(); } })) : null;

    root.replaceChildren(h('div', { class: 'auth-wrap' }, h('div', { class: 'auth-card' },
      h('h1', {}, 'Study', h('span', { class: 'muted', text: 'Bot' })),
      h('p', { class: 'lede', text: status.has_users ? 'Ask questions about your own notes, slides and lectures.'
        : 'Welcome! Create the first account. It will be the owner of this StudyBot.' }),
      tabs, form)));
    username.focus();
  };
  draw();
}

// ---------------------------------------------------------------- app shell
async function startApp() {
  renderShell();
  buildVoiceBar();
  refreshVoiceStatus();
  await Promise.all([loadLibrary(), resumeJobs()]);
}

function renderShell() {
  document.body.dataset.view = 'chat';
  const setView = (view) => {
    document.body.dataset.view = view;
    for (const button of document.querySelectorAll('.tabbar button')) {
      button.setAttribute('aria-current', String(button.dataset.view === view));
    }
  };
  $('#app').replaceChildren(h('div', { class: 'app-shell' },
    h('header', { class: 'topbar' },
      h('div', { class: 'brand' }, 'Study', h('span', { text: 'Bot' })),
      h('div', { class: 'who' }, h('span', { class: 'name muted', text: state.user.username }),
        h('button', { class: 'btn small', type: 'button', text: 'Sign out', onclick: async () => {
          try { await api('/api/auth/logout', { method: 'POST' }); } catch { /* already signed out */ }
          await signedOut();
        } }))),
    h('main', { class: 'layout' }, buildLibraryPane(), buildChatPane()),
    h('nav', { class: 'tabbar', 'aria-label': 'Sections' },
      h('button', { type: 'button', dataset: { view: 'library' }, 'aria-current': 'false', text: 'Library', onclick: () => setView('library') }),
      h('button', { type: 'button', dataset: { view: 'chat' }, 'aria-current': 'true', text: 'Ask', onclick: () => setView('chat') }))));
}

// ---------------------------------------------------------------- library pane
const ALLOWED = ['.pdf', '.pptx', '.docx'];

function buildLibraryPane() {
  const fileInput = h('input', { type: 'file', id: 'file-input', class: 'sr-only', multiple: true,
    accept: '.pdf,.pptx,.docx', onchange: (e) => { uploadFiles([...e.target.files]); e.target.value = ''; } });
  const drop = h('div', { class: 'dropzone', id: 'dropzone',
    ondragover: (e) => { e.preventDefault(); drop.classList.add('over'); },
    ondragleave: () => drop.classList.remove('over'),
    ondrop: (e) => { e.preventDefault(); drop.classList.remove('over'); uploadFiles([...e.dataTransfer.files]); } },
    h('p', { text: 'Drop PDF, PowerPoint or Word files here' }),
    h('button', { class: 'btn primary', type: 'button', text: 'Choose files', onclick: () => fileInput.click() }), fileInput);

  const subject = h('input', { class: 'input', id: 'subject', list: 'subject-options', value: state.subject, maxlength: 60,
    'aria-describedby': 'subject-hint', onchange: (e) => { state.subject = e.target.value.trim() || 'General'; e.target.value = state.subject; savePrefs(); } });
  const link = h('input', { class: 'input', id: 'yt-url', type: 'url', placeholder: 'https://www.youtube.com/watch?v=…', 'aria-label': 'YouTube link' });
  const addLink = async () => {
    const url = link.value.trim();
    if (!url) return;
    try {
      const job = await api('/api/documents/youtube', { method: 'POST', json: { url, collection: state.subject } });
      link.value = '';
      trackJob(job, 'YouTube video');
    } catch (err) { notify('error', err.message); }
  };
  link.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); addLink(); } });

  return h('section', { class: 'pane library', 'aria-label': 'Your library' },
    h('div', { class: 'card section stack' },
      h('h2', { text: 'Add study material' }),
      h('div', { class: 'field' }, h('label', { for: 'subject', text: 'Add to subject' }), subject, h('datalist', { id: 'subject-options' }),
        h('p', { class: 'hint', id: 'subject-hint', text: 'Pick an existing subject or type a new name.' })),
      drop,
      h('div', { class: 'field' }, h('label', { for: 'yt-url', text: 'Or add a YouTube video' }),
        h('div', { class: 'row' }, link, h('button', { class: 'btn', type: 'button', text: 'Add', onclick: addLink })),
        h('p', { class: 'hint', text: 'Uses the video’s English captions.' })),
      h('div', { class: 'jobs', id: 'jobs', 'aria-live': 'polite' })),
    h('div', { class: 'card section' }, h('h2', { text: 'Your subjects' }), h('div', { id: 'subjects' })));
}

async function loadLibrary() {
  const [collections, documents] = await Promise.all([api('/api/collections'), api('/api/documents')]);
  state.collections = collections;
  state.documents = documents;
  const names = new Set(collections.map((c) => c.name));
  state.scope = new Set([...state.scope].filter((n) => names.has(n)));
  renderLibrary();
  renderScope();
}

function renderLibrary() {
  const options = $('#subject-options');
  if (options) options.replaceChildren(...state.collections.map((c) => h('option', { value: c.name })));
  const box = $('#subjects');
  if (!box) return;
  if (!state.collections.length) {
    box.replaceChildren(h('div', { class: 'empty', text: 'Nothing here yet. Add a file or a YouTube link above and it will show up here.' }));
    return;
  }
  box.replaceChildren(...state.collections.map((collection) => {
    const docs = state.documents.filter((d) => d.collection_id === collection.id);
    const checkbox = h('input', { type: 'checkbox', checked: state.scope.has(collection.name) ? true : null,
      'aria-label': `Ask only about ${collection.name}`,
      onchange: (e) => { e.target.checked ? state.scope.add(collection.name) : state.scope.delete(collection.name); savePrefs(); renderScope(); } });
    return h('div', { class: 'subject' },
      h('div', { class: 'subject-head' },
        h('label', { title: 'Tick to ask only about this subject' }, checkbox,
          h('span', { class: 'name', text: collection.name }), h('span', { class: 'count', text: `${docs.length}` })),
        h('button', { class: 'btn small ghost danger', type: 'button', text: 'Delete', 'aria-label': `Delete subject ${collection.name}`, onclick: () => deleteCollection(collection) })),
      docs.length ? docs.map(docRow) : h('div', { class: 'empty', text: 'No documents yet.' }));
  }));
}

const TYPE_LABEL = { pdf: 'PDF', pptx: 'PPTX', docx: 'DOCX', youtube: 'YouTube' };

function docRow(doc) {
  return h('div', { class: 'doc' },
    h('div', { class: 'info' },
      h('div', { class: 'doc-title' }, h('span', { class: 'tag', text: TYPE_LABEL[doc.type] || doc.type }), doc.title),
      h('div', { class: 'meta', text: `${doc.chunks} passages` }),
      ...doc.warnings.map((w) => h('div', { class: 'warn', text: w }))),
    h('button', { class: 'btn small ghost', type: 'button', text: 'Re-index', title: 'Read this document again', onclick: () => reindex(doc) }),
    h('button', { class: 'btn small ghost danger', type: 'button', text: 'Delete', 'aria-label': `Delete ${doc.title}`, onclick: () => deleteDocument(doc) }));
}

async function deleteDocument(doc) {
  if (!confirm(`Delete “${doc.title}”? It will no longer be used to answer questions.`)) return;
  try { await api(`/api/documents/${doc.id}`, { method: 'DELETE' }); await loadLibrary(); } catch (err) { notify('error', err.message); }
}
async function deleteCollection(collection) {
  if (!confirm(`Delete the subject “${collection.name}” and all ${collection.documents} document(s) in it?`)) return;
  try { await api(`/api/collections/${collection.id}`, { method: 'DELETE' }); await loadLibrary(); } catch (err) { notify('error', err.message); }
}
async function reindex(doc) {
  try { trackJob(await api(`/api/documents/${doc.id}/reindex`, { method: 'POST' }), doc.title); } catch (err) { notify('error', err.message); }
}

// ---------------------------------------------------------------- uploads and jobs
let noticeSeq = 0;

function notify(kind, text) {
  state.notices.push({ id: ++noticeSeq, kind, text });  // not crypto.randomUUID: it needs HTTPS
  renderJobs();
}

async function uploadFiles(files) {
  for (const file of files) {
    const name = file.name.toLowerCase();
    if (!ALLOWED.some((ext) => name.endsWith(ext))) {
      const old = name.endsWith('.doc') || name.endsWith('.ppt');
      notify('error', old ? `${file.name}: old .doc/.ppt files are not supported. Re-save as .docx/.pptx.`
        : `${file.name}: only PDF, PowerPoint (.pptx) and Word (.docx) files can be added.`);
      continue;
    }
    const form = new FormData();
    form.append('file', file);
    form.append('collection', state.subject);
    try { trackJob(await api('/api/documents', { method: 'POST', form }), file.name); }
    catch (err) { notify('error', `${file.name}: ${err.message}`); }
  }
}

const trackers = new Map();
const STAGE = { starting: 'Starting…', reading: 'Reading the file…', chunking: 'Splitting into passages…',
  embedding: 'Learning the content…', indexing: 'Saving…', 'queued again': 'Waiting…' };

function jobStateText(job) {
  if (job.status === 'pending') return 'Waiting in line…';
  if (job.status === 'running') return job.kind === 'youtube' && job.stage === 'reading' ? 'Fetching captions…' : (STAGE[job.stage] || 'Working…');
  if (job.status === 'done') return `Added ✓  ${job.chunks} passages`;
  return job.error || 'Something went wrong.';
}

function trackJob(job, label) {
  state.jobs.set(job.id, { ...job, label: label || job.title || 'Document' });
  renderJobs();
  const update = (next) => {
    state.jobs.set(next.id, { ...next, label: state.jobs.get(next.id)?.label });
    renderJobs();
    if (next.status === 'done' || next.status === 'failed') {
      trackers.get(next.id)?.close();
      trackers.delete(next.id);
      if (next.status === 'done') { loadLibrary().catch(() => {}); setTimeout(() => { state.jobs.delete(next.id); renderJobs(); }, 9000); }
    }
  };
  const source = new EventSource(`/api/jobs/${job.id}/events`);
  trackers.set(job.id, source);
  source.addEventListener('job', (event) => update(JSON.parse(event.data)));
  source.onerror = () => {  // stream dropped: fall back to polling this one job
    source.close();
    trackers.delete(job.id);
    const poll = async () => {
      try {
        const next = await api(`/api/jobs/${job.id}`);
        update(next);
        if (next.status === 'pending' || next.status === 'running') setTimeout(poll, 1500);
      } catch { /* signed out or gone */ }
    };
    poll();
  };
}

async function resumeJobs() {
  for (const job of (await api('/api/jobs')).reverse()) {
    if (job.status === 'pending' || job.status === 'running') trackJob(job, job.title || (job.kind === 'youtube' ? 'YouTube video' : 'Document'));
  }
}

function renderJobs() {
  const box = $('#jobs');
  if (!box) return;
  const rows = [];
  for (const notice of state.notices) {
    rows.push(h('div', { class: 'job failed', role: 'alert' },
      h('div', { class: 'state', text: notice.text }),
      h('button', { class: 'btn small ghost', type: 'button', text: 'Dismiss', onclick: () => { state.notices = state.notices.filter((n) => n.id !== notice.id); renderJobs(); } })));
  }
  for (const job of state.jobs.values()) {
    const active = job.status === 'pending' || job.status === 'running';
    rows.push(h('div', { class: `job ${job.status === 'done' ? 'done' : job.status === 'failed' ? 'failed' : ''}` },
      h('div', { class: 'title', text: job.label }),
      h('div', { class: 'state', text: jobStateText(job) }),
      active ? h('div', { class: 'bar' }, h('i')) : null,
      ...(job.warnings || []).map((w) => h('div', { class: 'note', text: w })),
      job.status === 'failed' ? h('button', { class: 'btn small ghost', type: 'button', text: 'Dismiss', onclick: () => { state.jobs.delete(job.id); renderJobs(); } }) : null));
  }
  box.replaceChildren(...rows);
}

// ---------------------------------------------------------------- chat pane
function icon(name) {
  const paths = {
    mic: 'M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z',
    stop: 'M7 7h10v10H7z',
  };
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', '20');
  svg.setAttribute('height', '20');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', paths[name]);
  path.setAttribute('fill', 'currentColor');
  svg.append(path);
  return svg;
}

function buildChatPane() {
  const input = h('textarea', { id: 'question', rows: 1, placeholder: 'Ask about your notes…', 'aria-label': 'Your question', maxlength: 2000,
    oninput: (e) => { e.target.style.height = 'auto'; e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`; },
    onkeydown: (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } } });
  const mic = h('button', { class: 'btn icon-btn', id: 'mic', type: 'button', 'aria-label': 'Ask by voice', title: 'Ask by voice',
    hidden: !voice.supported ? true : null, onclick: toggleRecording }, icon('mic'));
  const history = h('details', { class: 'history', id: 'history' }, h('summary', { class: 'btn small', text: 'History' }),
    h('div', { class: 'history-list card', id: 'history-list' }));
  history.addEventListener('toggle', () => { if (history.open) loadHistory(); });

  return h('section', { class: 'pane chat', 'aria-label': 'Ask a question' },
    h('div', { class: 'card chat-card' },
      h('div', { class: 'chat-head' },
        h('h2', { id: 'chat-title', text: 'New chat' }),
        h('div', { class: 'chat-actions' }, history, h('button', { class: 'btn small', type: 'button', text: 'New chat', onclick: newChat }))),
      h('div', { class: 'scope', id: 'scope' }),
      h('div', { class: 'messages', id: 'messages', 'aria-live': 'polite' }, welcome()),
      h('div', { class: 'voice-bar', id: 'voice-bar' }),
      h('div', { class: 'voice-note', id: 'voice-note', role: 'status' }),
      h('div', { class: 'composer' }, mic, input,
        h('button', { class: 'btn primary', id: 'send', type: 'button', text: 'Ask', onclick: () => (state.streaming ? state.streaming.abort() : send()) }))));
}

function welcome() {
  return h('div', { class: 'welcome', id: 'welcome' }, h('h2', { text: 'Ask anything about your material' }),
    h('p', { text: 'Answers come only from what you have added, with sources you can check. Ask follow-up questions naturally. If it is not in your notes, StudyBot will say so.' }));
}

function renderScope() {
  const el = $('#scope');
  if (!el) return;
  el.replaceChildren(...(state.scope.size
    ? ['Asking in: ', h('strong', { text: [...state.scope].join(', ') })]
    : ['Asking across ', h('strong', { text: 'all your subjects' }), state.collections.length > 1 ? '. Tick a subject to narrow it.' : '.']));
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && url.hostname === 'www.youtube.com' ? url.href : null;
  } catch { return null; }
}

function citeButton(n) {
  return h('button', { class: 'cite', type: 'button', text: String(n), title: `Show source ${n}`, 'aria-label': `Show source ${n}`,
    onclick: (e) => {
      const row = e.currentTarget.closest('.msg')?.querySelector(`.source[data-n="${n}"]`);
      if (!row) return;
      const details = row.closest('details');
      if (details) details.open = true;
      row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      row.classList.add('flash');
      setTimeout(() => row.classList.remove('flash'), 1600);
    } });
}

function inlineNodes(tokens) {
  return tokens.map((t) => (t.t === 'text' ? document.createTextNode(t.v) : t.t === 'strong' ? h('strong', { text: t.v })
    : t.t === 'code' ? h('code', { text: t.v }) : citeButton(t.n)));
}

function blockNode(block) {
  switch (block.type) {
    case 'h': return h('p', { class: 'answer-heading' }, inlineNodes(block.inline));
    case 'ul': case 'ol': return h(block.type, {}, block.items.map((item) => h('li', {}, inlineNodes(item))));
    case 'pre': return h('pre', {}, h('code', { text: block.text }));
    case 'table': return h('table', {},
      block.head ? h('thead', {}, h('tr', {}, block.head.map((c) => h('th', {}, inlineNodes(c))))) : null,
      h('tbody', {}, block.rows.map((row) => h('tr', {}, row.map((c) => h('td', {}, inlineNodes(c)))))));
    default: return h('p', {}, inlineNodes(block.inline));
  }
}

function renderRich(el, text) { el.replaceChildren(...parseRich(text).map(blockNode)); }

function sourceRow(source) {
  const label = source.location ? `${source.title} · ${source.location}` : source.title;
  const link = safeUrl(source.url);
  return h('div', { class: 'source', dataset: { n: source.n }, title: source.header },
    h('span', { class: 'n', text: `[${source.n}]` }),
    link ? h('a', { href: link, target: '_blank', rel: 'noopener noreferrer', text: label }) : h('span', { text: label }));
}

function renderSources(container, sources, cited) {
  const used = sources.filter((s) => cited.includes(s.n));
  const others = sources.filter((s) => !cited.includes(s.n));
  container.replaceChildren(
    used.length ? h('h3', { text: 'Sources' }) : null, ...used.map(sourceRow),
    others.length ? h('details', { class: 'others' },
      h('summary', { text: `${others.length} other passage${others.length > 1 ? 's' : ''} considered` }),
      ...others.map((s) => h('div', {}, sourceRow(s), h('div', { class: 'snippet', text: s.snippet })))) : null);
}

function nearBottom(el) { return el.scrollHeight - el.scrollTop - el.clientHeight < 80; }

// One assistant message: status line, answer, flags, sources, footer. Used live and for saved chats.
function makeBotMessage() {
  const parts = {
    searched: h('div', { class: 'searched', hidden: true }),
    status: h('div', { class: 'status' }, h('span', { class: 'dots' }, h('i'), h('i'), h('i')), h('span', { class: 'phase', text: 'Searching your notes…' })),
    answer: h('div', { class: 'answer', hidden: true }),
    flags: h('div', { class: 'flags' }),
    sources: h('div', { class: 'sources' }),
    foot: h('div', { class: 'foot' }),
  };
  parts.el = h('div', { class: 'msg bot' }, parts.searched, parts.status, parts.answer, parts.flags, parts.sources, parts.foot);
  parts.flag = (text, kind = '') => parts.flags.append(h('div', { class: `flag ${kind}`, text }));
  parts.showSearched = (text) => { parts.searched.textContent = `Searched for: “${text}”`; parts.searched.hidden = false; };
  return parts;
}

/** Show the finished answer. `result` has the same shape as the server's `done` event (and saved meta). */
function showFinal(m, result, sources) {
  m.status.hidden = true;
  m.answer.hidden = false;
  renderRich(m.answer, result.text);  // the server's cleaned text replaces whatever was streamed
  m.answer.classList.toggle('refused', !!result.refused);
  m.flags.replaceChildren();
  if (result.invalid_citations) m.flag(`Removed ${result.invalid_citations} reference${result.invalid_citations > 1 ? 's' : ''} to sources that do not exist.`);
  if (result.empty) m.flag('The model did not write an answer. Try asking again or rephrasing.', 'error');
  else if (!result.refused && !(result.cited || []).length) m.flag('No source was cited for this answer, so check it against the passages below.');
  if (!result.refused) renderSources(m.sources, sources, result.cited || []);  // nothing was answered from them
  if (!result.gated && result.seconds) m.foot.textContent = `Answered in ${result.seconds}s`;
}

async function send(override) {
  const input = $('#question');
  const question = (typeof override === 'string' ? override : input.value).trim();
  if (!question || state.streaming) return;
  speaker.stop();
  setVoiceNote('');
  $('#welcome')?.remove();
  const messages = $('#messages');
  messages.append(h('div', { class: 'msg user', text: question }));
  input.value = '';
  input.style.height = 'auto';

  const m = makeBotMessage();
  messages.append(m.el);
  messages.scrollTop = messages.scrollHeight;

  const controller = new AbortController();
  state.streaming = controller;
  const sendButton = $('#send');
  sendButton.textContent = 'Stop';
  const started = Date.now();
  const phase = $('.phase', m.status);
  let label = 'Searching your notes…';
  const ticker = setInterval(() => { phase.textContent = `${label} ${Math.round((Date.now() - started) / 1000)}s`; }, 1000);

  let raw = '', sources = [], finished = false, frame = 0;
  const paint = () => { frame = 0; const stick = nearBottom(messages); renderRich(m.answer, raw); if (stick) messages.scrollTop = messages.scrollHeight; };

  const handlers = {
    conversation(info) { state.conversationId = info.id; $('#chat-title').textContent = info.title; },
    query({ text }) { m.showSearched(text); label = 'Reading your notes…'; },
    sources(list) { sources = list; label = list.length ? `Reading ${list.length} passage${list.length > 1 ? 's' : ''}…` : 'Checking…'; },
    token({ text }) {
      if (m.answer.hidden) { m.answer.hidden = false; m.status.hidden = true; }
      raw += text;
      speaker.feed(text);
      if (!frame) frame = requestAnimationFrame(paint);
    },
    done(result) {
      finished = true;
      if (frame) cancelAnimationFrame(frame);
      showFinal(m, result, sources);
      if (result.gated || result.refused) speaker.say(result.text); else speaker.flush();
    },
    error({ message }) { finished = true; m.status.hidden = true; m.flag(message, 'error'); },
  };

  try {
    await streamChat({ question, collections: state.scope.size ? [...state.scope] : null, conversation_id: state.conversationId },
      handlers, controller.signal);
    if (!finished) { m.status.hidden = true; m.flag('The connection ended before the answer was complete.', 'error'); }
  } catch (err) {
    m.status.hidden = true;
    if (err.name === 'AbortError') { speaker.stop(); if (raw) { m.answer.hidden = false; renderRich(m.answer, raw); } m.flag('Stopped.'); }
    else m.flag(err.message, 'error');
  } finally {
    clearInterval(ticker);
    state.streaming = null;
    sendButton.textContent = 'Ask';
    messages.scrollTop = messages.scrollHeight;
    input.focus();
  }
}

async function streamChat(payload, handlers, signal) {
  const response = await fetch('/api/chat', { method: 'POST', credentials: 'same-origin', signal,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (response.status === 401) { await signedOut(); throw new ApiError('Please sign in.', 401); }
  if (!response.ok) throw await errorFrom(response);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const dispatch = (block) => {
    let event = 'message'; let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) event = line.slice(7);
      else if (line.startsWith('data: ')) data += line.slice(6);
    }
    if (data && handlers[event]) handlers[event](JSON.parse(data));
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf('\n\n')) >= 0) { dispatch(buffer.slice(0, end)); buffer = buffer.slice(end + 2); }
  }
}

// ---------------------------------------------------------------- saved chats
function resetChat() {
  speaker.stop();
  state.streaming?.abort();
  state.conversationId = null;
  $('#chat-title').textContent = 'New chat';
  $('#messages').replaceChildren(welcome());
  setVoiceNote('');
}

function newChat() { resetChat(); $('#history').open = false; $('#question').focus(); }

function renderSavedMessage(message) {
  if (message.role === 'user') return h('div', { class: 'msg user', text: message.content });
  const m = makeBotMessage();
  if (message.meta.search_query) m.showSearched(message.meta.search_query);
  showFinal(m, { ...message.meta, text: message.content }, message.sources || []);
  return m.el;
}

async function openConversation(id) {
  try {
    const conversation = await api(`/api/conversations/${id}`);
    resetChat();
    state.conversationId = conversation.id;
    $('#chat-title').textContent = conversation.title;
    $('#messages').replaceChildren(...conversation.messages.map(renderSavedMessage));
    $('#messages').scrollTop = $('#messages').scrollHeight;
    $('#history').open = false;
    document.body.dataset.view = 'chat';
  } catch (err) { notify('error', err.message); }
}

function when(seconds) {
  const date = new Date(seconds * 1000);
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

async function loadHistory() {
  const box = $('#history-list');
  try {
    const list = await api('/api/conversations');
    box.replaceChildren(...(list.length ? list.map((c) => h('div', { class: `history-item ${c.id === state.conversationId ? 'current' : ''}` },
      h('button', { class: 'history-open', type: 'button', onclick: () => openConversation(c.id) },
        h('span', { class: 'history-title', text: c.title }), h('span', { class: 'muted', text: when(c.updated_at) })),
      h('button', { class: 'btn small ghost danger', type: 'button', text: 'Delete', 'aria-label': `Delete chat ${c.title}`, onclick: async () => {
        if (!confirm(`Delete the chat “${c.title}”?`)) return;
        try { await api(`/api/conversations/${c.id}`, { method: 'DELETE' }); if (c.id === state.conversationId) resetChat(); await loadHistory(); }
        catch (err) { notify('error', err.message); }
      } })))
      : [h('div', { class: 'empty', text: 'No saved chats yet.' })]));
  } catch (err) { box.replaceChildren(h('div', { class: 'empty', text: err.message })); }
}

// ---------------------------------------------------------------- voice: speaking answers aloud
const speaker = {
  supported: 'speechSynthesis' in window,
  buffer: '',
  feed(text) {  // called with streamed text; speaks each sentence as soon as it is complete
    if (!state.readAloud || !this.supported) return;
    this.buffer += text;
    const [sentences, rest] = splitSentences(this.buffer);
    this.buffer = rest;
    sentences.forEach((s) => this.say(s));
  },
  flush() { const rest = this.buffer; this.buffer = ''; if (state.readAloud) this.say(rest); },
  say(text) {
    if (!state.readAloud || !this.supported) return;
    const clean = speakable(text);
    if (!clean) return;
    const utterance = new SpeechSynthesisUtterance(clean);
    const chosen = pickVoice();
    if (chosen) { utterance.voice = chosen; utterance.lang = chosen.lang; }
    window.speechSynthesis.speak(utterance);
  },
  stop() { this.buffer = ''; if (this.supported) window.speechSynthesis.cancel(); },  // also used to interrupt (barge-in)
};

function englishVoices() { return speaker.supported ? window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith('en')) : []; }
function pickVoice() {
  const voices = englishVoices();
  return voices.find((v) => v.name === state.voiceName) || voices.find((v) => v.localService) || voices[0] || null;
}

// ---------------------------------------------------------------- voice: asking by speaking
const voice = {
  supported: !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder),
  status: null, recorder: null, stop: null,
};

function setVoiceNote(text, kind = '') {
  const el = $('#voice-note');
  if (!el) return;
  el.textContent = text;
  el.className = `voice-note ${kind}`;
}

function buildVoiceBar() {
  const bar = $('#voice-bar');
  if (!bar) return;
  const items = [];
  if (speaker.supported) {
    const select = h('select', { class: 'input small', id: 'voice-select', 'aria-label': 'Voice for reading answers',
      onchange: (e) => { state.voiceName = e.target.value; savePrefs(); } });
    const fill = () => {
      const voices = englishVoices();
      select.replaceChildren(...voices.map((v) => h('option', { value: v.name, text: v.name.replace(/^Microsoft /, '').replace(/ (Desktop )?- English.*$/, '') })));
      if (voices.length) select.value = (pickVoice() || voices[0]).name;
      select.disabled = !voices.length || !state.readAloud;
    };
    fill();
    window.speechSynthesis.addEventListener('voiceschanged', fill);
    items.push(h('label', { class: 'check' },
      h('input', { type: 'checkbox', checked: state.readAloud ? true : null, onchange: (e) => {
        state.readAloud = e.target.checked; savePrefs(); if (!state.readAloud) speaker.stop(); select.disabled = !state.readAloud || !englishVoices().length;
      } }), 'Read answers aloud'), select);
  }
  if (voice.supported) {
    items.push(h('label', { class: 'check' },
      h('input', { type: 'checkbox', checked: state.autoSend ? true : null, onchange: (e) => { state.autoSend = e.target.checked; savePrefs(); } }),
      'Send automatically after speaking'));
  }
  bar.replaceChildren(...items);
  bar.hidden = !items.length;
}

async function refreshVoiceStatus() {
  if (!voice.supported) return;
  try { voice.status = await api('/api/voice/status'); } catch { voice.status = null; }
  const mic = $('#mic');
  if (!mic) return;
  const usable = voice.status?.available !== false;
  mic.disabled = !usable;
  mic.title = usable ? (voice.status?.ready ? 'Ask by voice' : 'Ask by voice (the speech model is still loading)')
    : `Voice input is unavailable: ${voice.status?.error || 'not installed'}`;
}

function micProblem(err) {
  if (!window.isSecureContext) return 'The microphone only works on https:// pages or on this computer (localhost). Open StudyBot from this PC, or through its HTTPS address.';
  if (err.name === 'NotAllowedError' || err.name === 'SecurityError') return 'Microphone access was blocked. Allow it in the browser’s address bar, then try again.';
  if (err.name === 'NotFoundError') return 'No microphone was found.';
  return `Could not start the microphone: ${err.message}`;
}

function setMic(stateName) {  // idle | listening | working
  const mic = $('#mic');
  if (!mic) return;
  mic.classList.toggle('listening', stateName === 'listening');
  mic.disabled = stateName === 'working';
  mic.replaceChildren(icon(stateName === 'listening' ? 'stop' : 'mic'));
  const label = stateName === 'listening' ? 'Stop listening' : 'Ask by voice';
  mic.setAttribute('aria-label', label);
  mic.title = label;
}

async function toggleRecording() {
  if (voice.recorder) { voice.stop?.(); return; }
  if (state.streaming) state.streaming.abort();
  speaker.stop();  // barge-in: speaking over the assistant silences it
  setVoiceNote('');
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
  catch (err) { setVoiceNote(micProblem(err), 'error'); return; }

  const type = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'].find((t) => MediaRecorder.isTypeSupported?.(t)) || '';
  const recorder = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
  const chunks = [];
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };

  // Stop by itself after speech followed by a pause, so no second tap is needed.
  const context = new (window.AudioContext || window.webkitAudioContext)();
  const analyser = context.createAnalyser();
  analyser.fftSize = 1024;
  context.createMediaStreamSource(stream).connect(analyser);
  const samples = new Uint8Array(analyser.fftSize);
  const began = Date.now();
  let heardSpeech = false, lastVoice = Date.now();
  const watcher = setInterval(() => {
    analyser.getByteTimeDomainData(samples);
    let sum = 0;
    for (const v of samples) sum += ((v - 128) / 128) ** 2;
    if (Math.sqrt(sum / samples.length) > 0.02) { heardSpeech = true; lastVoice = Date.now(); }
    const elapsed = Date.now() - began;
    if ((heardSpeech && Date.now() - lastVoice > 1500) || elapsed > 30000 || (!heardSpeech && elapsed > 8000)) voice.stop();
  }, 100);

  voice.recorder = recorder;
  voice.stop = () => { if (recorder.state !== 'inactive') recorder.stop(); };
  recorder.onstop = async () => {
    clearInterval(watcher);
    stream.getTracks().forEach((t) => t.stop());
    context.close().catch(() => {});
    voice.recorder = null;
    voice.stop = null;
    if (!heardSpeech) { setMic('idle'); setVoiceNote('I didn’t hear anything. Try again, a little closer to the microphone.'); return; }
    setMic('working');
    setVoiceNote('Transcribing…');
    try { await transcribe(new Blob(chunks, { type: recorder.mimeType || type || 'audio/webm' })); }
    finally { setMic('idle'); }
  };
  recorder.start();
  setMic('listening');
  setVoiceNote('Listening… speak your question, then pause.');
}

async function transcribe(blob) {
  const form = new FormData();
  form.append('audio', blob, `speech.${blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'}`);
  try {
    const result = await api('/api/voice/transcribe', { method: 'POST', form });
    if (!result.text) { setVoiceNote('I didn’t catch that. Please try again.'); return; }
    setVoiceNote('');
    const input = $('#question');
    input.value = result.text;
    input.dispatchEvent(new Event('input'));
    if (state.autoSend) send(result.text); else { input.focus(); setVoiceNote('Check the text, then press Ask.'); }
  } catch (err) {
    setVoiceNote(err.message, 'error');
    refreshVoiceStatus();
  }
}

// ---------------------------------------------------------------- start
async function init() {
  loadPrefs();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});  // makes the app installable
  const status = await fetchStatus();
  if (status.offline) { renderOffline(); return; }
  if (!status.user) { renderAuth(status); return; }
  state.user = status.user;
  try { await startApp(); } catch (err) { if (err.status !== 401) console.error(err); }
}

init();
