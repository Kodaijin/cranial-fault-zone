/* Cranial Fault Zone — SPA (vanilla JS, hash router) */
'use strict';

const app = document.getElementById('app');

// ── API helper ───────────────────────────────────────────
const api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  },
  async put(path, body) {
    const r = await fetch(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, { method: 'DELETE' });
    if (!r.ok && r.status !== 204) throw new Error(`${r.status} ${await r.text()}`);
  },
};

// ── Utility helpers ──────────────────────────────────────
function el(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );
}

function toast(msg, kind = 'ok') {
  const box = document.getElementById('toast');
  const icon = kind === 'err' ? '✕' : '✓';
  box.innerHTML = `<div class="toast-card ${kind}"><span>${icon}</span><span>${esc(msg)}</span></div>`;
  box.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => box.classList.add('hidden'), 3000);
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ── Wordmark (global header) ─────────────────────────────
function wordmark() {
  return `
    <div class="wordmark">
      <div class="wordmark-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 12 Q6 6 9 12 Q12 18 15 12 Q18 6 21 12"/>
          <line x1="3" y1="17" x2="21" y2="17" stroke-opacity="0.35"/>
        </svg>
      </div>
      <div>
        <div class="wordmark-text">Cranial Fault Zone</div>
        <div class="wordmark-sub">Migraine Observatory</div>
      </div>
    </div>`;
}

// ── Page header ──────────────────────────────────────────
function pageHeader(title, sub) {
  return `
    <div class="page-header">
      <h1 class="page-title">${title}</h1>
      ${sub ? `<p class="page-sub">${esc(sub)}</p>` : ''}
    </div>`;
}

// ── Loading screen ───────────────────────────────────────
function loadingScreen() {
  return `<div class="cfz-loading">
    <div class="cfz-loader"></div>
    <p class="text-sm" style="color:var(--muted)">Reading fault data…</p>
  </div>`;
}

// ── Card ─────────────────────────────────────────────────
function card(inner, extra = '') {
  return `<div class="cfz-card ${extra}">${inner}</div>`;
}
function cardTitle(t) {
  return `<div class="card-title">${esc(t)}</div>`;
}

// ── Router ───────────────────────────────────────────────
const routes = {
  dashboard: renderDashboard,
  log:       renderLog,
  reports:   renderReports,
  manage:    renderManage,
};

async function router() {
  const hash  = location.hash.replace(/^#\//, '') || 'dashboard';
  const route = hash.split('/')[0];
  const fn    = routes[route] || renderDashboard;

  document.querySelectorAll('[data-nav]').forEach((a) =>
    a.classList.toggle('active', a.dataset.nav === route));

  app.innerHTML = loadingScreen();
  try {
    await fn();
  } catch (e) {
    app.innerHTML = `
      <div class="error-card">
        <p style="font-weight:700;color:var(--fault2);margin-bottom:0.4rem;">Fault detected</p>
        <p style="font-size:0.8125rem;color:var(--muted)">${esc(e.message)}</p>
      </div>`;
  }
}

window.addEventListener('hashchange', router);
window.addEventListener('DOMContentLoaded', router);

// ═════════════════════════════════════════════════════════
//  DASHBOARD
// ═════════════════════════════════════════════════════════
async function renderDashboard() {
  const [game, grid, entries] = await Promise.all([
    api.get('/api/gamification'),
    api.get('/api/stats/grid'),
    api.get('/api/entries'),
  ]);

  const pct = game.next_level_xp
    ? Math.round(100 * (game.xp - game.current_level_floor) /
        (game.next_level_xp - game.current_level_floor))
    : 100;

  const xpToNext = game.next_level_xp
    ? `${game.next_level_xp - game.xp} XP to next level`
    : 'MAX LEVEL';

  app.innerHTML = pageHeader('Dashboard', 'Stabilize the fault line by logging consistently.');

  // ── Gamification hero ──────────────────────────────────
  const heroCard = el(`
    <div class="cfz-card gam-hero" style="margin-bottom:1rem">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;flex-wrap:wrap">
        <div style="flex:1;min-width:0">
          <div class="level-badge">
            <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor"><polygon points="5,1 6.5,4 10,4.5 7.5,7 8.2,10.5 5,8.5 1.8,10.5 2.5,7 0,4.5 3.5,4"/></svg>
            Level ${game.level}
          </div>
          <div class="gam-title">${esc(game.title)}</div>
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.4rem">
            <span class="stat-pill">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
              <strong>${game.total_logged_days}</strong> days tracked
            </span>
            <span class="stat-pill"><strong>${game.longest_streak}</strong>d best streak</span>
          </div>
        </div>
        <div style="text-align:right;flex-shrink:0">
          <div class="streak-display" style="justify-content:flex-end">
            <span class="streak-num">${game.current_streak}</span>
            <span class="streak-unit">day streak</span>
          </div>
          <div style="font-size:0.65rem;color:var(--muted);margin-top:0.15rem">🔥 consecutive logs</div>
        </div>
      </div>
      <div class="xp-track">
        <div class="xp-fill" style="width:${pct}%"></div>
      </div>
      <div class="xp-label">
        <span>${game.xp.toLocaleString()} XP</span>
        <span>${xpToNext}</span>
      </div>
    </div>`);
  app.appendChild(heroCard);

  // ── Stability Index ────────────────────────────────────
  const si = game.stability_index;
  const stColor = si >= 80 ? '#30d88a'
    : si >= 50 ? '#e8a020'
    : si >= 20 ? '#ff7043' : '#e8334a';
  const stGlow = si >= 80 ? 'rgba(48,216,138,0.35)'
    : si >= 50 ? 'rgba(232,160,32,0.35)'
    : si >= 20 ? 'rgba(255,112,67,0.35)' : 'rgba(232,51,74,0.35)';

  const stabilityCard = el(`
    <div class="cfz-card stability-card" style="margin-bottom:1rem">
      ${cardTitle('Fault Zone Stability Index')}
      <div class="stability-meter" id="stability-meter">
        <canvas class="seismo-canvas" id="seismo-canvas"></canvas>
      </div>
      <div class="stability-footer">
        <div>
          <div class="stability-state" style="color:${stColor};text-shadow:0 0 12px ${stGlow}">${esc(game.stability_state)}</div>
          <div style="font-size:0.7rem;color:var(--muted);margin-top:0.1rem">30-day consistency</div>
        </div>
        <div class="stability-score">
          <strong style="color:${stColor}">${si}</strong>
          <span style="color:var(--muted);font-size:0.7rem">/ 100</span>
        </div>
      </div>
    </div>`);
  app.appendChild(stabilityCard);

  // Draw seismograph canvas after DOM insertion
  requestAnimationFrame(() => drawSeismo(si, stColor));

  // ── Activity Heatmap ───────────────────────────────────
  const cells = grid.days.map((d) => {
    let cls, tooltip;
    if (d.count > 0) {
      cls = `l${d.level}`;
      tooltip = `${d.date}: ${d.count} entr${d.count === 1 ? 'y' : 'ies'}`;
    } else if (d.tracked) {
      cls = 'l0'; // good day (green) — only from the first entry forward
      tooltip = `${d.date}: good day (no pain logged)`;
    } else {
      cls = 'lu'; // untracked: before the first entry / no data yet
      tooltip = `${d.date}: no tracking`;
    }
    return `<div class="grid-cell ${cls}" title="${tooltip}"></div>`;
  }).join('');

  const heatCard = el(`
    <div class="cfz-card heatmap-card" style="margin-bottom:1rem">
      ${cardTitle('Seismic Activity — last 365 days')}
      <div class="grid-scroll"><div class="activity-grid">${cells}</div></div>
      <div class="heatmap-legend">
        <div class="grid-cell lu" title="No tracking / no data"></div>
        <span style="margin-right:0.75rem;font-size:0.7rem;color:var(--muted)">No data</span>
        <div class="grid-cell l0" title="Good day (no pain logged)"></div>
        <span style="font-size:0.7rem;color:var(--muted)">Good day</span>
        <span style="margin-left:0.75rem;margin-right:0.5rem;font-size:0.7rem;color:var(--muted)">Pain:</span>
        <div class="grid-cell l1" title="Low pain"></div>
        <div class="grid-cell l2" title="Moderate pain"></div>
        <div class="grid-cell l3" title="High pain"></div>
        <div class="grid-cell l4" title="Very high pain"></div>
        <span style="font-size:0.7rem;color:var(--muted)">high</span>
        <span style="margin-left:auto">${grid.max_count ? `Peak: ${grid.max_count}` : ''}</span>
      </div>
    </div>`);
  app.appendChild(heatCard);

  // ── Quests ─────────────────────────────────────────────
  const questsHtml = game.quests.length
    ? game.quests.map((q) => {
        const progPct = q.target ? Math.min(100, Math.round(100 * (q.progress || 0) / q.target)) : 0;
        return `
          <div class="quest-item${q.complete ? ' complete' : ''}">
            <div class="quest-icon ${q.complete ? 'done' : 'open'}">
              ${q.complete ? '✓' : '○'}
            </div>
            <div style="flex:1;min-width:0">
              <div class="quest-title${q.complete ? ' done' : ''}">
                ${esc(q.title)}<span class="quest-scope">${esc(q.scope)}</span>
              </div>
              <div class="quest-desc">${esc(q.description)}${q.target ? ` · ${q.progress}/${q.target}` : ''}</div>
              ${q.target && !q.complete ? `
                <div class="quest-progress-bar">
                  <div class="quest-progress-fill" style="width:${progPct}%"></div>
                </div>` : ''}
            </div>
          </div>`;
      }).join('')
    : `<div class="empty-state">No active quests.</div>`;

  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Active Quests')}
      ${questsHtml}
    </div>`));

  // ── Achievements ───────────────────────────────────────
  const achvHtml = game.achievements.map((a) => `
    <div class="achv-item${a.unlocked ? ' achv-unlocked' : ' locked'}">
      <span class="achv-icon">${a.unlocked ? '🏆' : '🔒'}</span>
      <div class="achv-name">${esc(a.title)}</div>
      <div class="achv-desc">${esc(a.description)}</div>
    </div>`).join('');

  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Achievements')}
      <div class="achv-grid">${achvHtml}</div>
    </div>`));

  // ── Recent entries ─────────────────────────────────────
  const recentHtml = entries.length === 0
    ? `<div class="empty-state">No entries yet. <a href="#/log">Log your first one →</a></div>`
    : entries.slice(0, 8).map(entryRow).join('');

  const recentCard = el(`
    <div class="cfz-card">
      ${cardTitle('Recent Entries')}
      <div>${recentHtml}</div>
    </div>`);
  app.appendChild(recentCard);

  app.querySelectorAll('[data-del-entry]').forEach((b) =>
    b.addEventListener('click', async () => {
      if (!confirm('Delete this entry?')) return;
      await api.del(`/api/entries/${b.dataset.delEntry}`);
      toast('Entry deleted');
      router();
    }));
}

// ── Seismograph canvas draw ──────────────────────────────
function drawSeismo(stabilityIndex, color) {
  const canvas = document.getElementById('seismo-canvas');
  if (!canvas) return;
  const parent = canvas.parentElement;
  const W = parent.offsetWidth;
  const H = parent.offsetHeight;
  canvas.width  = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  const instability = 1 - stabilityIndex / 100;
  const cx = W / 2;
  const cy = H / 2;

  // Glowing baseline
  ctx.beginPath();
  ctx.strokeStyle = color + '40';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 8]);
  ctx.moveTo(0, cy);
  ctx.lineTo(W, cy);
  ctx.stroke();
  ctx.setLineDash([]);

  // Seismo trace
  const amplitude = instability * (H * 0.38);
  const points = [];
  const segments = Math.floor(W / 3);

  for (let i = 0; i <= segments; i++) {
    const x = (i / segments) * W;
    let y = cy;

    if (instability > 0.05) {
      // Chaotic tremor peaks near high instability
      const base = Math.sin(i * 0.35) * amplitude * 0.5;
      const spike = (Math.random() < instability * 0.25)
        ? (Math.random() - 0.5) * amplitude * 2.2
        : 0;
      const noise = (Math.random() - 0.5) * amplitude * 0.6;
      y = cy + base + spike + noise;
    }
    points.push({ x, y });
  }

  // Draw glow (thick, low alpha)
  ctx.beginPath();
  ctx.strokeStyle = color + '25';
  ctx.lineWidth = 8;
  ctx.lineJoin = 'round';
  ctx.lineCap  = 'round';
  points.forEach(({ x, y }, i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y));
  ctx.stroke();

  // Draw main line
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.lineCap  = 'round';
  points.forEach(({ x, y }, i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y));
  ctx.stroke();

  // Scanning cursor
  let pos = 0;
  let raf;
  const speed = 0.5 + instability * 2;
  function animate() {
    pos = (pos + speed) % W;
    // Clear cursor column
    ctx.clearRect(pos - 2, 0, 4, H);
    // Redraw base line in cleared area
    ctx.strokeStyle = color + '40';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 8]);
    ctx.beginPath();
    ctx.moveTo(pos, cy);
    ctx.lineTo(pos, cy);
    ctx.stroke();
    ctx.setLineDash([]);
    // Draw cursor glow
    ctx.beginPath();
    const grad = ctx.createLinearGradient(pos - 1, 0, pos + 1, 0);
    grad.addColorStop(0, 'transparent');
    grad.addColorStop(0.5, color + 'aa');
    grad.addColorStop(1, 'transparent');
    ctx.fillStyle = grad;
    ctx.fillRect(pos - 1, 0, 2, H);
    raf = requestAnimationFrame(animate);
  }
  raf = requestAnimationFrame(animate);

  // Clean up animation when page navigates away
  const origRouter = window._seismoCleanup;
  window._seismoCleanup = () => {
    cancelAnimationFrame(raf);
    if (origRouter) origRouter();
  };
}

// Clean up seismo on route change
const _origRouter = router;
window.addEventListener('hashchange', () => {
  if (window._seismoCleanup) { window._seismoCleanup(); window._seismoCleanup = null; }
});

// ── Entry row helper ─────────────────────────────────────
function entryRow(e) {
  const zones = (e.pain_zones || []).map((z) => z.zone_name).join(', ') || '—';
  const meds = (e.medications || []).map(m => m.name).join(', ');
  const press = e.weather_data && e.weather_data.pressure_hpa;
  const hasWeather = press && press !== 'N/A';
  return `
    <div class="entry-row">
      <div style="flex:1;min-width:0">
        <div>
          <span class="entry-type">${esc(e.headache_type?.name || '—')}</span>
          <span class="entry-ts">${fmtDate(e.timestamp)}</span>
        </div>
        <div class="entry-meta">
          ${esc(zones)}${e.duration_minutes != null ? ` · ${e.duration_minutes}min` : ''}${meds ? ` · ${esc(meds)}` : ''}
        </div>
        ${hasWeather ? `<div class="entry-weather">${press} hPa · ${esc(e.weather_data.conditions || '')}</div>` : ''}
      </div>
      <a href="#/log/${e.id}" class="del-btn" aria-label="Edit entry" title="Edit">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M7.5 2.5 L7.5 1 L8 0.5 L9.5 2 L9 2.5 Z" stroke="none" fill="currentColor"/>
          <line x1="1" y1="9" x2="1" y2="9"/>
        </svg>
      </a>
      <button class="del-btn" data-del-entry="${e.id}" aria-label="Delete entry" title="Delete">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <line x1="1.5" y1="1.5" x2="8.5" y2="8.5"/><line x1="8.5" y1="1.5" x2="1.5" y2="8.5"/>
        </svg>
      </button>
    </div>`;
}

// ═════════════════════════════════════════════════════════
//  LOG ENTRY
// ═════════════════════════════════════════════════════════
async function renderLog() {
  const editId = location.hash.replace(/^#\//, '').split('/')[1] || null;

  const [types, meds, locs, zones] = await Promise.all([
    api.get('/api/headache_types'),
    api.get('/api/medications'),
    api.get('/api/locations'),
    api.get('/api/pain_zones'),
  ]);

  let entry = null;
  if (editId) {
    entry = await api.get('/api/entries/' + editId);
  }

  const nowLocal = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
    .toISOString().slice(0, 16);

  const pageTitle = editId ? 'Edit Entry' : '<span class="fault-accent">Log</span> Entry';
  const pageSubtitle = editId ? 'Modify your headache record.' : 'Record a headache or a pain-free check-in.';

  app.innerHTML = pageHeader(pageTitle, pageSubtitle);

  // Helper to format ISO timestamp to datetime-local format (local time)
  function formatToLocalDatetimeInput(isoString) {
    const d = new Date(isoString);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  }

  const tsValue = editId && entry ? formatToLocalDatetimeInput(entry.timestamp) : nowLocal;
  const typeValue = editId && entry ? entry.headache_type.id : '';
  const durValue = editId && entry && entry.duration_minutes ? entry.duration_minutes : '';
  const locValue = editId && entry && entry.location ? entry.location.id : '';
  const notesValue = editId && entry ? (entry.notes || '') : '';
  const medIds = editId && entry ? new Set(entry.medications.map(m => m.id)) : new Set();
  const zoneIds = editId && entry ? new Set(entry.pain_zones.map(z => z.id)) : new Set();

  const formCard = el(`
    <div class="cfz-card">
      <form id="entry-form">

        <div class="form-group">
          <label class="cfz-label" for="f-ts">Date &amp; Time</label>
          <input id="f-ts" name="timestamp" type="datetime-local" value="${tsValue}"
            class="cfz-input" />
        </div>

        <div class="form-group">
          <label class="cfz-label" for="f-type">Headache Type</label>
          <select id="f-type" name="headache_type_id" required class="cfz-input">
            ${types.map((t) => `<option value="${t.id}"${typeValue == t.id ? ' selected' : ''}>${esc(t.name)}</option>`).join('')}
          </select>
        </div>

        <div class="form-group">
          <label class="cfz-label" for="f-dur">Duration (min)</label>
          <input id="f-dur" name="duration_minutes" type="number" min="0" placeholder="e.g. 120"
            value="${durValue}"
            class="cfz-input" />
        </div>

        <div class="form-group">
          <label class="cfz-label">Medication(s)</label>
          <div class="zone-chip-wrap" id="med-chips">
            ${meds.map((m) => `
              <label class="zone-chip${medIds.has(m.id) ? ' selected' : ''}">
                <input type="checkbox" value="${m.id}"${medIds.has(m.id) ? ' checked' : ''} />
                <span class="zone-chip-dot"></span>
                ${esc(m.name)}
              </label>`).join('')}
          </div>
          ${meds.length === 0 ? '<p style="font-size:0.75rem;color:var(--muted)">No medications configured in Manage.</p>' : '<p style="font-size:0.75rem;color:var(--muted)">Optional.</p>'}
        </div>

        <div class="form-group">
          <label class="cfz-label" for="f-loc">Location</label>
          <select id="f-loc" name="location_id" class="cfz-input">
            <option value="">None (no weather lookup)</option>
            ${locs.map((l) => `<option value="${l.id}"${locValue == l.id ? ' selected' : ''}>${esc(l.city_name)}, ${esc(l.state_code)}</option>`).join('')}
          </select>
        </div>

        <div class="form-group">
          <label class="cfz-label">Pain Zones</label>
          <div class="zone-chip-wrap" id="zone-chips">
            ${zones.map((z) => `
              <label class="zone-chip${zoneIds.has(z.id) ? ' selected' : ''}">
                <input type="checkbox" value="${z.id}"${zoneIds.has(z.id) ? ' checked' : ''} />
                <span class="zone-chip-dot"></span>
                ${esc(z.zone_name)}
              </label>`).join('')}
          </div>
          ${zones.length === 0 ? '<p style="font-size:0.75rem;color:var(--muted)">No pain zones configured in Manage.</p>' : ''}
        </div>

        <div class="form-group">
          <label class="cfz-label" for="f-notes">Notes</label>
          <textarea id="f-notes" name="notes" rows="3"
            placeholder="Triggers, aura, context…"
            class="cfz-input">${esc(notesValue)}</textarea>
        </div>

        <button type="submit" class="cfz-btn-primary" id="submit-btn">
          ${editId ? 'Update Entry' : 'Save Entry'}
        </button>
      </form>
    </div>`);

  app.appendChild(formCard);

  // Zone & medication chip toggle
  app.querySelectorAll('.zone-chip input, #med-chips input').forEach((cb) =>
    cb.addEventListener('change', () =>
      cb.closest('.zone-chip').classList.toggle('selected', cb.checked)));

  // Form submit
  app.querySelector('#entry-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    const pain_zone_ids = [...f.querySelectorAll('.zone-chip input:checked')]
      .map((c) => Number(c.value));
    const medication_ids = [...f.querySelectorAll('#med-chips input:checked')]
      .map((c) => Number(c.value));
    const payload = {
      timestamp:        f.timestamp.value ? new Date(f.timestamp.value).toISOString() : null,
      headache_type_id: Number(f.headache_type_id.value),
      duration_minutes: f.duration_minutes.value ? Number(f.duration_minutes.value) : null,
      medication_ids,
      location_id:      f.location_id.value ? Number(f.location_id.value) : null,
      pain_zone_ids,
      notes:            f.notes.value.trim() || null,
    };
    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    const isEditing = editId !== null;
    const originalText = isEditing ? 'Update Entry' : 'Save Entry';
    const savingText = isEditing ? 'Updating…' : 'Saving & fetching conditions…';
    btn.textContent = savingText;
    try {
      let saved;
      if (isEditing) {
        saved = await api.put('/api/entries/' + editId, payload);
        toast('Entry updated');
      } else {
        saved = await api.post('/api/entries', payload);
        const w = saved.weather_data || {};
        const detail = (w.pressure_hpa && w.pressure_hpa !== 'N/A')
          ? ` · ${w.pressure_hpa} hPa, ${w.conditions}` : '';
        toast('Entry saved' + detail);
      }
      location.hash = '#/dashboard';
    } catch (e) {
      toast('Save failed: ' + e.message, 'err');
      btn.disabled = false;
      btn.textContent = originalText;
    }
  });
}

// ═════════════════════════════════════════════════════════
//  REPORTS
// ═════════════════════════════════════════════════════════
let _charts = [];
let _reportRange = { mode: 'all', start: null, end: null };

// Returns YYYY-MM-DD in local time for a given Date object
function isoDate(d) {
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

// Converts _reportRange to a query string like ?start=...&end=...
function rangeQueryString() {
  const { mode, start, end } = _reportRange;
  if (mode === 'all' || (!start && !end)) return '';
  const parts = [];
  if (start) parts.push(`start=${encodeURIComponent(start)}`);
  if (end)   parts.push(`end=${encodeURIComponent(end)}`);
  return parts.length ? '?' + parts.join('&') : '';
}

async function renderReports() {
  _charts.forEach((c) => c.destroy());
  _charts = [];

  const qs     = rangeQueryString();
  const trends = await api.get('/api/stats/trends' + qs);

  app.innerHTML = pageHeader(
    '<span class="fault-accent">Environmental</span> Reports',
    'Correlate barometric pressure, humidity, and allergens with onset.'
  );

  // ── Date-range selector card ───────────────────────────
  {
    // Presets leave `end` open (null) so the latest entries are always included
    // regardless of the browser/server timezone offset (entries are stored in UTC,
    // so a local "today" can lag the UTC date of a just-logged entry).
    const today   = new Date();
    const presets = [
      { key: 'week',  label: 'Week',  start: isoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6)),  end: null },
      { key: 'month', label: 'Month', start: isoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 29)), end: null },
      { key: 'year',  label: 'Year',  start: isoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 364)),end: null },
      { key: 'all',   label: 'All',   start: null, end: null },
    ];

    const activeMode = _reportRange.mode;
    const presetBtns = presets.map((p) =>
      `<button class="rng-preset${activeMode === p.key ? ' active' : ''}" data-preset="${p.key}"
         data-start="${p.start || ''}" data-end="${p.end || ''}">${esc(p.label)}</button>`
    ).join('');

    const customStart = activeMode === 'custom' ? (_reportRange.start || '') : '';
    const customEnd   = activeMode === 'custom' ? (_reportRange.end   || '') : '';

    const selectorCard = el(`
      <div class="cfz-card rng-card" style="margin-bottom:1rem">
        <div class="card-title">Date Range</div>
        <div class="rng-controls">
          <div class="rng-presets">${presetBtns}</div>
          <div class="rng-custom">
            <label class="cfz-label rng-custom-label" for="rng-start">From</label>
            <input id="rng-start" type="date" class="cfz-input rng-date-input"
              value="${esc(customStart)}" placeholder="Start" />
            <label class="cfz-label rng-custom-label" for="rng-end">To</label>
            <input id="rng-end" type="date" class="cfz-input rng-date-input"
              value="${esc(customEnd)}" placeholder="End" />
            <button class="cfz-btn-add rng-apply-btn" id="rng-apply">Apply</button>
          </div>
        </div>
      </div>`);

    // Wire preset buttons
    selectorCard.querySelectorAll('.rng-preset').forEach((btn) => {
      btn.addEventListener('click', () => {
        const k = btn.dataset.preset;
        const s = btn.dataset.start || null;
        const e = btn.dataset.end   || null;
        _reportRange = { mode: k, start: s, end: e };
        renderReports();
      });
    });

    // Wire Apply button
    selectorCard.querySelector('#rng-apply').addEventListener('click', () => {
      const sv = selectorCard.querySelector('#rng-start').value.trim() || null;
      const ev = selectorCard.querySelector('#rng-end').value.trim()   || null;
      if (!sv && !ev) {
        _reportRange = { mode: 'all', start: null, end: null };
      } else {
        _reportRange = { mode: 'custom', start: sv, end: ev };
      }
      renderReports();
    });

    app.appendChild(selectorCard);
  }

  // Pressure chart card
  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Barometric Pressure & Humidity')}
      <div class="chart-wrap">
        <div style="position:relative;height:240px">
          <canvas id="press-chart"></canvas>
        </div>
        <div id="press-empty" class="chart-empty" style="display:none">
          <span class="chart-empty-icon">📡</span>
          No pressure data yet — log entries with a location to populate trends automatically from Open-Meteo.
        </div>
      </div>
    </div>`));

  // Major Pollutants chart card
  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Major Pollutants')}
      <div class="card-subtitle" style="font-size:0.75rem;color:var(--muted);margin:-0.5rem 0 1rem 0">µg/m³</div>
      <div class="chart-wrap">
        <div style="position:relative;height:240px">
          <canvas id="air-major-chart"></canvas>
        </div>
        <div id="air-major-empty" class="chart-empty" style="display:none">
          <span class="chart-empty-icon">💨</span>
          No air quality data yet — log entries with a location to populate trends automatically from Open-Meteo.
        </div>
      </div>
    </div>`));

  // Trace Pollutants chart card
  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Trace Pollutants')}
      <div class="card-subtitle" style="font-size:0.75rem;color:var(--muted);margin:-0.5rem 0 1rem 0">µg/m³</div>
      <div class="chart-wrap">
        <div style="position:relative;height:240px">
          <canvas id="air-trace-chart"></canvas>
        </div>
        <div id="air-trace-empty" class="chart-empty" style="display:none">
          <span class="chart-empty-icon">💨</span>
          No air quality data yet — log entries with a location to populate trends automatically from Open-Meteo.
        </div>
      </div>
    </div>`));

  // Allergens chart card
  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Allergens')}
      <div class="chart-wrap">
        <div style="position:relative;height:240px">
          <canvas id="pollen-chart"></canvas>
        </div>
        <div id="pollen-empty" class="chart-empty" style="display:none">
          <span class="chart-empty-icon">🌿</span>
          No pollen data yet — log entries with a location to populate trends automatically from Open-Meteo.
        </div>
      </div>
    </div>`));

  // PDF export card
  const pdfQs = rangeQueryString();
  app.appendChild(el(`
    <div class="cfz-card">
      ${cardTitle('Clinical Export')}
      <div class="pdf-promo">
        <p class="pdf-promo-text">
          Black-and-white PDF report: totals, frequent pain zones, medication efficacy, and a
          chronological notes appendix — ready to share with your clinician.
        </p>
        <a href="/api/export/pdf${esc(pdfQs)}" class="cfz-btn-amber" download>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download PDF Report
        </a>
        <p class="pdf-range-note">Exports the currently selected date range.</p>
      </div>
    </div>`));

  const pts = trends.points || [];

  if (pts.length === 0) {
    document.getElementById('press-chart').style.display = 'none';
    document.getElementById('press-empty').style.display = 'flex';
    document.getElementById('air-major-chart').style.display = 'none';
    document.getElementById('air-major-empty').style.display = 'flex';
    document.getElementById('air-trace-chart').style.display = 'none';
    document.getElementById('air-trace-empty').style.display = 'flex';
    document.getElementById('pollen-chart').style.display = 'none';
    document.getElementById('pollen-empty').style.display = 'flex';
    return;
  }

  const labels    = pts.map((p) => p.date ? new Date(p.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '');
  const gridColor = 'rgba(44,44,74,0.6)';
  const tickColor = '#7070a0';

  const baseOpts = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: {
        ticks: { color: tickColor, maxTicksLimit: 8, font: { family: "'DM Sans'" } },
        grid: { color: gridColor },
        border: { color: 'transparent' },
      },
      y: {
        ticks: { color: tickColor, font: { family: "'DM Sans'" } },
        grid: { color: gridColor },
        border: { color: 'transparent' },
      },
    },
    plugins: {
      legend: {
        labels: { color: '#9090b8', font: { family: "'DM Sans'" }, usePointStyle: true, pointStyleWidth: 10 },
      },
      tooltip: {
        backgroundColor: 'rgba(17,17,32,0.95)',
        borderColor: '#2c2c4a',
        borderWidth: 1,
        titleColor: '#eeeef8',
        bodyColor: '#9090b8',
        titleFont: { family: "'Syne'", weight: '700' },
        bodyFont: { family: "'DM Sans'" },
        padding: 10,
        cornerRadius: 8,
      },
    },
  };

  _charts.push(new Chart(document.getElementById('press-chart'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Pressure (hPa)',
          data: pts.map((p) => p.pressure_hpa),
          borderColor: '#e8334a',
          backgroundColor: 'rgba(232,51,74,0.12)',
          pointBackgroundColor: '#e8334a',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: true,
        },
        {
          label: 'Humidity (%)',
          data: pts.map((p) => p.humidity_pct),
          borderColor: '#e8a020',
          backgroundColor: 'rgba(232,160,32,0.08)',
          pointBackgroundColor: '#e8a020',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: true,
        },
      ],
    },
    options: baseOpts,
  }));

  _charts.push(new Chart(document.getElementById('air-major-chart'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Carbon Monoxide',
          data: pts.map((p) => p.carbon_monoxide),
          borderColor: '#d84040',
          backgroundColor: 'rgba(216,64,64,0.08)',
          pointBackgroundColor: '#d84040',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
        {
          label: 'Ozone',
          data: pts.map((p) => p.ozone),
          borderColor: '#e8a020',
          backgroundColor: 'rgba(232,160,32,0.08)',
          pointBackgroundColor: '#e8a020',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
        {
          label: 'PM10',
          data: pts.map((p) => p.pm10),
          borderColor: '#ff9a56',
          backgroundColor: 'rgba(255,154,86,0.08)',
          pointBackgroundColor: '#ff9a56',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
        {
          label: 'PM2.5',
          data: pts.map((p) => p.pm2_5),
          borderColor: '#ff7043',
          backgroundColor: 'rgba(255,112,67,0.08)',
          pointBackgroundColor: '#ff7043',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
      ],
    },
    options: baseOpts,
  }));

  _charts.push(new Chart(document.getElementById('air-trace-chart'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Nitrogen Dioxide',
          data: pts.map((p) => p.nitrogen_dioxide),
          borderColor: '#a8d04b',
          backgroundColor: 'rgba(168,208,75,0.08)',
          pointBackgroundColor: '#a8d04b',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
        {
          label: 'Nitrogen Monoxide',
          data: pts.map((p) => p.nitrogen_monoxide),
          borderColor: '#70d8da',
          backgroundColor: 'rgba(112,216,218,0.08)',
          pointBackgroundColor: '#70d8da',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
        {
          label: 'Nitrogen Oxides',
          data: pts.map((p) => p.nitrogen_oxides),
          borderColor: '#b88ae8',
          backgroundColor: 'rgba(184,138,232,0.08)',
          pointBackgroundColor: '#b88ae8',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
        {
          label: 'Sulphur Dioxide',
          data: pts.map((p) => p.sulphur_dioxide),
          borderColor: '#ffc56d',
          backgroundColor: 'rgba(255,197,109,0.08)',
          pointBackgroundColor: '#ffc56d',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
      ],
    },
    options: baseOpts,
  }));

  _charts.push(new Chart(document.getElementById('pollen-chart'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Tree Pollen',
          data: pts.map((p) => p.tree_pollen),
          borderColor: '#30d88a',
          backgroundColor: 'rgba(48,216,138,0.08)',
          pointBackgroundColor: '#30d88a',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
        {
          label: 'Grass Pollen',
          data: pts.map((p) => p.grass_pollen),
          borderColor: '#a8d04b',
          backgroundColor: 'rgba(168,208,75,0.08)',
          pointBackgroundColor: '#a8d04b',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
        {
          label: 'Weed Pollen',
          data: pts.map((p) => p.weed_pollen),
          borderColor: '#e8334a',
          backgroundColor: 'rgba(232,51,74,0.08)',
          pointBackgroundColor: '#e8334a',
          pointRadius: 3,
          pointHoverRadius: 5,
          borderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
        },
      ],
    },
    options: baseOpts,
  }));
}

// ═════════════════════════════════════════════════════════
//  MANAGE
// ═════════════════════════════════════════════════════════
async function renderManage() {
  const [types, meds, locs] = await Promise.all([
    api.get('/api/headache_types'),
    api.get('/api/medications'),
    api.get('/api/locations'),
  ]);

  app.innerHTML = pageHeader(
    '<span class="fault-accent">Manage</span> Data',
    'Customize your reference lists.'
  );

  // ── Headache Types ─────────────────────────────────────
  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Headache Types')}
      <div id="types-list">
        ${manageRows(types, (t) => t.name, null, 'type')}
      </div>
      <form data-add="type" class="add-row" style="margin-top:0.75rem">
        <input name="name" placeholder="New type name" required class="cfz-input" style="flex:1" />
        <button type="submit" class="cfz-btn-add">Add</button>
      </form>
    </div>`));

  // ── Medications ────────────────────────────────────────
  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Medications')}
      <div id="meds-list">
        ${manageRows(meds, (m) => m.name, (m) => m.dosage_notes, 'med')}
      </div>
      <form data-add="med" class="add-row" style="margin-top:0.75rem">
        <input name="name" placeholder="Medication name" required class="cfz-input" style="flex:1;min-width:120px" />
        <input name="dosage_notes" placeholder="Dosage notes" class="cfz-input" style="flex:1;min-width:120px" />
        <button type="submit" class="cfz-btn-add">Add</button>
      </form>
    </div>`));

  // ── Locations ──────────────────────────────────────────
  app.appendChild(el(`
    <div class="cfz-card">
      ${cardTitle('Locations')}
      <div id="locs-list">
        ${manageRows(locs, (l) => l.city_name, (l) => l.state_code, 'loc')}
      </div>
      <form data-add="loc" class="add-row" style="margin-top:0.75rem">
        <input name="city_name" placeholder="City" required class="cfz-input" style="flex:1" />
        <input name="state_code" placeholder="ST" required maxlength="3" class="cfz-input state-input" />
        <button type="submit" class="cfz-btn-add">Add</button>
      </form>
    </div>`));

  const endpoints = { type: 'headache_types', med: 'medications', loc: 'locations' };

  app.querySelectorAll('[data-del]').forEach((b) =>
    b.addEventListener('click', async () => {
      const [kind, id] = b.dataset.del.split(':');
      try {
        await api.del(`/api/${endpoints[kind]}/${id}`);
        toast('Deleted');
        router();
      } catch (e) {
        toast('Delete failed: ' + e.message, 'err');
      }
    }));

  app.querySelectorAll('form[data-add]').forEach((form) =>
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const kind = form.dataset.add;
      const body = Object.fromEntries(new FormData(form).entries());
      try {
        await api.post(`/api/${endpoints[kind]}`, body);
        toast('Added');
        router();
      } catch (e) {
        toast('Failed: ' + e.message, 'err');
      }
    }));
}

function manageRows(items, label, sub, kind) {
  if (!items.length) return `<p style="font-size:0.8125rem;color:var(--muted);padding:0.5rem 0">None yet.</p>`;
  return items.map((it) => `
    <div class="manage-row">
      <span class="manage-row-label">
        ${esc(label(it))}${sub && sub(it) ? `<span class="sub">(${esc(sub(it))})</span>` : ''}
      </span>
      <button class="del-text-btn" data-del="${kind}:${it.id}">Remove</button>
    </div>`).join('');
}
