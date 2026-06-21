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

// Minutes → "45m" / "2h" / "1d 3h" (compact, for entry duration display)
function fmtDuration(mins) {
  if (mins == null) return '—';
  if (mins < 60) return `${mins}m`;
  const days = Math.floor(mins / 1440);
  const hours = Math.floor((mins % 1440) / 60);
  const m = mins % 60;
  if (days > 0) return `${days}d${hours ? ` ${hours}h` : ''}`;
  return `${hours}h${m ? ` ${m}m` : ''}`;
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

// ── Activity heatmap (shared by dashboard + expanded page) ───
const _MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Build the heatmap stack (episode strip + day grid), optionally with a month-label
// row. `days` is how many trailing days of grid.days to render; cell/gap set size.
function heatmapHTML(grid, { days, cell, gap, withMonths = false }) {
  const COL_PX = cell + gap;
  const viewDays = grid.days.slice(-days);
  if (viewDays.length === 0) return '';

  const cells = viewDays.map((d) => {
    let cls, tooltip;
    if (d.state === 'pain') {
      cls = `l${d.level}`;
      tooltip = `${d.date}: pain${d.count > 1 ? ` (${d.count} overlapping episodes)` : ''}`;
    } else if (d.state === 'good') {
      cls = 'l0';
      tooltip = `${d.date}: good day (no pain)`;
    } else {
      cls = 'lu';
      tooltip = `${d.date}: no tracking`;
    }
    if (d.ongoing) { cls += ' ongoing'; tooltip += ' · still going'; }
    return `<div class="grid-cell ${cls}" title="${tooltip}"></div>`;
  }).join('');

  // Episode-bar strip — one bar per episode, positioned over its week-columns.
  // The grid flows column-by-column (7 rows), so each week is one COL_PX column.
  const viewStart = new Date(viewDays[0].date + 'T00:00');
  const dayOffset = (iso) => Math.round((new Date(iso + 'T00:00') - viewStart) / 86400000);
  const totalCols = Math.ceil(viewDays.length / 7);
  const stripWidth = totalCols * COL_PX;
  const episodeBars = (grid.episodes || []).map((ep) => {
    const sRaw = dayOffset(ep.start);
    const eRaw = dayOffset(ep.end);
    // Skip episodes that fall entirely outside the visible window.
    if (eRaw < 0 || sRaw > viewDays.length - 1) return '';
    const sOff = Math.max(0, sRaw);
    const eOff = Math.min(viewDays.length - 1, eRaw);
    const left = Math.floor(sOff / 7) * COL_PX;
    const right = Math.floor(eOff / 7) * COL_PX + cell;
    const w = Math.max(cell / 2, right - left);
    const tip = `${ep.start} → ${ep.ongoing ? 'ongoing' : ep.end}`;
    return `<div class="episode-bar${ep.ongoing ? ' ongoing' : ''}" style="left:${left}px;width:${w}px" title="${tip}"></div>`;
  }).join('');

  // Optional month labels positioned at the column where each new month begins.
  let monthsRow = '';
  if (withMonths) {
    const labels = [];
    let lastMonth = -1;
    for (let c = 0; c < totalCols; c++) {
      const d = viewDays[c * 7];
      if (!d) break;
      const m = new Date(d.date + 'T00:00').getMonth();
      if (m !== lastMonth) {
        lastMonth = m;
        labels.push(`<span class="heatmap-month" style="left:${c * COL_PX}px">${_MONTH_ABBR[m]}</span>`);
      }
    }
    monthsRow = `<div class="heatmap-months" style="width:${stripWidth}px">${labels.join('')}</div>`;
  }

  return `
    <div class="grid-scroll">
      ${monthsRow}
      <div class="heatmap-stack" style="width:${stripWidth}px;--cell-size:${cell}px;--cell-gap:${gap}px">
        <div class="episode-strip">${episodeBars}</div>
        <div class="activity-grid">${cells}</div>
      </div>
    </div>`;
}

function heatmapLegend() {
  return `
    <div class="heatmap-legend">
      <div class="grid-cell lu" title="No tracking / no data"></div>
      <span style="margin-right:0.6rem;font-size:0.7rem;color:var(--muted)">No data</span>
      <div class="grid-cell l0" title="Good day (no pain logged)"></div>
      <span style="font-size:0.7rem;color:var(--muted)">Good day</span>
      <span style="margin-left:0.6rem;margin-right:0.5rem;font-size:0.7rem;color:var(--muted)">Pain:</span>
      <div class="grid-cell l1" title="Low pain"></div>
      <div class="grid-cell l2" title="Moderate pain"></div>
      <div class="grid-cell l3" title="High pain"></div>
      <div class="grid-cell l4" title="Very high pain"></div>
      <div class="grid-cell l4 ongoing" title="Ongoing (still going)" style="margin-left:0.6rem"></div>
      <span style="font-size:0.7rem;color:var(--muted)">Ongoing</span>
    </div>`;
}

// ── Router ───────────────────────────────────────────────
const routes = {
  dashboard: renderDashboard,
  log:       renderLog,
  entries:   renderEntries,
  activity:  renderActivity,
  reports:   renderReports,
  manage:    renderManage,
};

async function router() {
  const hash  = location.hash.replace(/^#\//, '') || 'dashboard';
  const route = hash.split('/')[0];
  const fn    = routes[route] || renderDashboard;

  document.querySelectorAll('[data-nav]').forEach((a) =>
    a.classList.toggle('active', a.dataset.nav === route));

  // Keep the active tab visible when the nav row scrolls on mobile.
  const activeNav = document.querySelector('[data-nav].active');
  if (activeNav) activeNav.scrollIntoView({ inline: 'center', block: 'nearest' });

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

// On first load, backfill any missing days with auto good-day entries (captures
// historical weather/air/pollen). Render immediately from current data, then
// refresh once the fill completes so new entries appear without a manual reload.
let _goodDaysFilled = false;
async function ensureGoodDaysFilled() {
  if (_goodDaysFilled) return 0;
  _goodDaysFilled = true;
  try {
    const res = await api.post('/api/good_days/fill', {});
    return res && res.created ? res.created : 0;
  } catch (_) {
    return 0;  // never block the UI on backfill failure
  }
}

window.addEventListener('DOMContentLoaded', async () => {
  router();
  const created = await ensureGoodDaysFilled();
  if (created) router();
});

// ═════════════════════════════════════════════════════════
//  DASHBOARD
// ═════════════════════════════════════════════════════════
async function renderDashboard() {
  const [game, grid] = await Promise.all([
    api.get('/api/gamification'),
    api.get('/api/stats/grid'),
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

  // ── Activity Heatmap (last 4 months; tap to expand) ────
  const heatCard = el(`
    <a href="#/activity" class="cfz-card heatmap-card heatmap-link" style="margin-bottom:1rem">
      <div class="heatmap-head">
        ${cardTitle('Seismic Activity — last 4 months')}
        <span class="heatmap-expand">
          Expand
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/>
            <line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
          </svg>
        </span>
      </div>
      ${heatmapHTML(grid, { days: 120, cell: 12, gap: 3 })}
      ${heatmapLegend()}
    </a>`);
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

}

// ═════════════════════════════════════════════════════════
//  ACTIVITY (expanded full-year heatmap)
// ═════════════════════════════════════════════════════════
async function renderActivity() {
  const grid = await api.get('/api/stats/grid');

  // Summary counts across the full window.
  let good = 0, pain = 0, tracked = 0;
  for (const d of grid.days) {
    if (d.state === 'untracked') continue;
    tracked++;
    if (d.state === 'pain') pain++;
    else if (d.state === 'good') good++;
  }

  app.innerHTML = pageHeader(
    '<span class="fault-accent">Seismic</span> Activity',
    'Your full 365-day fault-line history.'
  );

  app.appendChild(el(
    `<a href="#/dashboard" class="back-link">
       <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
       Back to dashboard
     </a>`));

  app.appendChild(el(`
    <div class="cfz-card heatmap-card" style="margin-bottom:1rem">
      ${cardTitle('Last 365 days')}
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:0.9rem">
        <span class="stat-pill"><strong>${tracked}</strong> days tracked</span>
        <span class="stat-pill" style="color:var(--stable)"><strong>${good}</strong> good</span>
        <span class="stat-pill" style="color:var(--fault2)"><strong>${pain}</strong> pain</span>
      </div>
      ${heatmapHTML(grid, { days: grid.days.length, cell: 14, gap: 4, withMonths: true })}
      ${heatmapLegend()}
    </div>`));
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
  if (e.is_good_day) {
    return `
    <div class="entry-row">
      <div style="flex:1;min-width:0">
        <div>
          <span class="entry-type good-day-label" style="color:var(--stable)">&#9679; Good day</span>
          <span class="entry-ts">${fmtDate(e.timestamp)}</span>
        </div>
        ${e.notes ? `<div class="entry-meta">${esc(e.notes)}</div>` : ''}
      </div>
      <a href="#/log/${e.id}" class="del-btn edit-btn" aria-label="Edit entry" title="Edit">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 20h9"/>
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
        </svg>
      </a>
      <button class="del-btn" data-del-entry="${e.id}" aria-label="Delete entry" title="Delete">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <line x1="1.5" y1="1.5" x2="8.5" y2="8.5"/><line x1="8.5" y1="1.5" x2="1.5" y2="8.5"/>
        </svg>
      </button>
    </div>`;
  }
  const zones = (e.pain_zones || []).map((z) => z.zone_name).join(', ') || '—';
  const meds = (e.medications || []).map(m => m.name).join(', ');
  const press = e.weather_data && e.weather_data.pressure_hpa;
  const hasWeather = press && press !== 'N/A';
  const durText = e.is_ongoing
    ? ' · ongoing'
    : (e.duration_minutes != null ? ` · ${fmtDuration(e.duration_minutes)}` : '');
  return `
    <div class="entry-row">
      <div style="flex:1;min-width:0">
        <div>
          <span class="entry-type">${esc(e.headache_type?.name || '—')}</span>
          ${e.is_ongoing ? '<span class="ongoing-tag">&#9679; ongoing</span>' : ''}
          <span class="entry-ts">${fmtDate(e.timestamp)}</span>
        </div>
        <div class="entry-meta">
          ${esc(zones)}${durText}${meds ? ` · ${esc(meds)}` : ''}
        </div>
        ${hasWeather ? `<div class="entry-weather">${press} hPa · ${esc(e.weather_data.conditions || '')}</div>` : ''}
      </div>
      <a href="#/log/${e.id}" class="del-btn edit-btn" aria-label="Edit entry" title="Edit">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 20h9"/>
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
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
//  ENTRIES (log history)
// ═════════════════════════════════════════════════════════
async function renderEntries() {
  const entries = await api.get('/api/entries');

  app.innerHTML = pageHeader(
    '<span class="fault-accent">Log</span> Entries',
    'Every headache and good-day check-in you\'ve recorded.'
  );

  const listHtml = entries.length === 0
    ? `<div class="empty-state">No entries yet. <a href="#/log">Log your first one →</a></div>`
    : entries.map(entryRow).join('');

  app.appendChild(el(`
    <div class="cfz-card">
      ${cardTitle(`All Entries (${entries.length})`)}
      <div>${listHtml}</div>
    </div>`));

  app.querySelectorAll('[data-del-entry]').forEach((b) =>
    b.addEventListener('click', async () => {
      if (!confirm('Delete this entry?')) return;
      await api.del(`/api/entries/${b.dataset.delEntry}`);
      toast('Entry deleted');
      router();
    }));
}

// ═════════════════════════════════════════════════════════
//  LOG ENTRY
// ═════════════════════════════════════════════════════════
async function renderLog() {
  const editId = location.hash.replace(/^#\//, '').split('/')[1] || null;

  const [types, meds, locs, zones, settings, allEntries] = await Promise.all([
    api.get('/api/headache_types'),
    api.get('/api/medications'),
    api.get('/api/locations'),
    api.get('/api/pain_zones'),
    api.get('/api/settings'),
    api.get('/api/entries'),
  ]);

  const goodDayTypeId = settings.good_day_type_id;
  const painTypes = types.filter((t) => t.id !== goodDayTypeId);

  // The 5 most recent non-good-day entries are offered as "continues episode"
  // link targets (exclude the entry being edited so it can't link to itself).

  let entry = null;
  if (editId) {
    entry = await api.get('/api/entries/' + editId);
  }

  // Determine initial mode
  let mode = (editId && entry && entry.is_good_day) ? 'good' : 'pain';

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
  const typeValue = editId && entry && !entry.is_good_day ? entry.headache_type.id : '';
  const endValue = editId && entry && entry.end_time ? formatToLocalDatetimeInput(entry.end_time) : '';
  const ongoingValue = editId && entry ? !!entry.is_ongoing : false;
  const linkValue = editId && entry && entry.linked_entry_id ? entry.linked_entry_id : '';
  const locValue = editId && entry && entry.location ? entry.location.id : '';
  const notesValue = editId && entry ? (entry.notes || '') : '';
  const medIds = editId && entry && !entry.is_good_day ? new Set(entry.medications.map(m => m.id)) : new Set();
  const zoneIds = editId && entry && !entry.is_good_day ? new Set(entry.pain_zones.map(z => z.id)) : new Set();

  // Recent non-good-day entries available as episode-link targets.
  const linkCandidates = allEntries
    .filter((e) => !e.is_good_day && String(e.id) !== String(editId))
    .slice(0, 5);

  // Local ongoing flag, toggled by the "Still going" button / end-time edits.
  let ongoing = ongoingValue;

  function buildFormHTML(currentMode) {
    const isPain = currentMode === 'pain';
    const submitLabel = editId
      ? (isPain ? 'Update Entry' : 'Update Good Day')
      : (isPain ? 'Save Entry' : 'Save Good Day');
    return `
      <div class="cfz-card">
        <form id="entry-form">

          <!-- Mode toggle -->
          <div class="form-group">
            <div class="seg-toggle" id="mode-toggle" role="group" aria-label="Entry mode">
              <button type="button" class="seg-btn${isPain ? ' seg-active' : ''}" data-mode="pain">Pain entry</button>
              <button type="button" class="seg-btn${!isPain ? ' seg-active' : ''}" data-mode="good">Good day</button>
            </div>
          </div>

          <!-- Date & Time (always shown) -->
          <div class="form-group">
            <label class="cfz-label" for="f-ts">Date &amp; Time</label>
            <input id="f-ts" name="timestamp" type="datetime-local" value="${tsValue}"
              class="cfz-input" />
          </div>

          <!-- Pain-only fields -->
          <div id="pain-fields" style="${isPain ? '' : 'display:none'}">
            <div class="form-group">
              <label class="cfz-label" for="f-type">Headache Type</label>
              <select id="f-type" name="headache_type_id"${isPain ? ' required' : ''} class="cfz-input">
                ${painTypes.map((t) => `<option value="${t.id}"${typeValue == t.id ? ' selected' : ''}>${esc(t.name)}</option>`).join('')}
              </select>
            </div>

            <div class="form-group">
              <label class="cfz-label" for="f-end">End Time</label>
              <input id="f-end" name="end_time" type="datetime-local" value="${endValue}"
                class="cfz-input" />
              <button type="button" class="cfz-btn-add still-going-btn${ongoing ? ' active' : ''}" id="still-going-btn"
                style="margin-top:0.5rem">
                Still going (end of day)
              </button>
              <p style="font-size:0.75rem;color:var(--muted);margin-top:0.4rem">
                Leave blank if unknown. "Still going" sets the end to 11:59 PM and flags the episode as ongoing.
              </p>
            </div>

            <div class="form-group">
              <label class="cfz-label" for="f-link">Continues episode</label>
              <select id="f-link" name="linked_entry_id" class="cfz-input">
                <option value="">— New episode —</option>
                ${linkCandidates.map((e) => `<option value="${e.id}"${linkValue == e.id ? ' selected' : ''}>${esc(e.headache_type?.name || 'Entry')} · ${esc(fmtDate(e.timestamp))}</option>`).join('')}
              </select>
              ${linkCandidates.length === 0 ? '<p style="font-size:0.75rem;color:var(--muted)">No earlier entries to link to yet.</p>' : '<p style="font-size:0.75rem;color:var(--muted)">Link to a previous entry if this is the same headache continuing.</p>'}
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
          </div>

          <!-- Location (always shown) -->
          <div class="form-group">
            <label class="cfz-label" for="f-loc">Location</label>
            <select id="f-loc" name="location_id" class="cfz-input">
              <option value="">None (no weather lookup)</option>
              ${locs.map((l) => `<option value="${l.id}"${locValue == l.id ? ' selected' : ''}>${esc(l.city_name)}, ${esc(l.state_code)}</option>`).join('')}
            </select>
          </div>

          <!-- Pain zones (pain mode only) -->
          <div id="zones-field" style="${isPain ? '' : 'display:none'}">
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
          </div>

          <!-- Notes (always shown) -->
          <div class="form-group">
            <label class="cfz-label" for="f-notes">Notes</label>
            <textarea id="f-notes" name="notes" rows="3"
              placeholder="Triggers, aura, context…"
              class="cfz-input">${esc(notesValue)}</textarea>
          </div>

          <button type="submit" class="cfz-btn-primary" id="submit-btn">
            ${submitLabel}
          </button>
        </form>
      </div>`;
  }

  function mountForm(currentMode) {
    // Remove existing card if present
    const existing = app.querySelector('.cfz-card');
    if (existing) existing.remove();

    const formCard = el(buildFormHTML(currentMode));
    app.appendChild(formCard);

    // Mode toggle buttons
    app.querySelectorAll('#mode-toggle .seg-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        mode = btn.dataset.mode;
        mountForm(mode);
      });
    });

    // Zone & medication chip toggle
    app.querySelectorAll('.zone-chip input, #med-chips input').forEach((cb) =>
      cb.addEventListener('change', () =>
        cb.closest('.zone-chip').classList.toggle('selected', cb.checked)));

    // "Still going (end of day)" → set end time to 23:59 of the start day + flag ongoing.
    const stillBtn = app.querySelector('#still-going-btn');
    const endInput = app.querySelector('#f-end');
    if (stillBtn && endInput) {
      stillBtn.addEventListener('click', () => {
        const tsInput = app.querySelector('#f-ts');
        const startDay = (tsInput.value || nowLocal).slice(0, 10);
        endInput.value = `${startDay}T23:59`;
        ongoing = true;
        stillBtn.classList.add('active');
      });
      // Editing the end time by hand clears the ongoing flag.
      endInput.addEventListener('input', () => {
        ongoing = false;
        stillBtn.classList.remove('active');
      });
    }

    // Form submit
    app.querySelector('#entry-form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const f = ev.target;
      const btn = document.getElementById('submit-btn');
      btn.disabled = true;
      const isEditing = editId !== null;

      try {
        let saved;
        if (mode === 'good') {
          const payload = {
            is_good_day:  true,
            timestamp:    f.timestamp.value ? new Date(f.timestamp.value).toISOString() : null,
            location_id:  f.location_id.value ? Number(f.location_id.value) : null,
            notes:        f.notes.value.trim() || null,
          };
          btn.textContent = isEditing ? 'Updating…' : 'Saving…';
          if (isEditing) {
            saved = await api.put('/api/entries/' + editId, payload);
            toast('Good day updated');
          } else {
            saved = await api.post('/api/entries', payload);
            toast('Good day logged');
          }
        } else {
          const pain_zone_ids = [...f.querySelectorAll('#zone-chips input:checked')]
            .map((c) => Number(c.value));
          const medication_ids = [...f.querySelectorAll('#med-chips input:checked')]
            .map((c) => Number(c.value));
          const payload = {
            timestamp:        f.timestamp.value ? new Date(f.timestamp.value).toISOString() : null,
            headache_type_id: Number(f.headache_type_id.value),
            end_time:         f.end_time.value ? new Date(f.end_time.value).toISOString() : null,
            is_ongoing:       ongoing,
            linked_entry_id:  f.linked_entry_id.value ? Number(f.linked_entry_id.value) : null,
            medication_ids,
            location_id:      f.location_id.value ? Number(f.location_id.value) : null,
            pain_zone_ids,
            notes:            f.notes.value.trim() || null,
          };
          btn.textContent = isEditing ? 'Updating…' : 'Saving & fetching conditions…';
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
        }
        location.hash = '#/dashboard';
      } catch (e) {
        toast('Save failed: ' + e.message, 'err');
        btn.disabled = false;
        btn.textContent = isEditing
          ? (mode === 'good' ? 'Update Good Day' : 'Update Entry')
          : (mode === 'good' ? 'Save Good Day' : 'Save Entry');
      }
    });
  }

  mountForm(mode);
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
    'Correlate barometric pressure, humidity, and allergens with onset. Diamonds mark pain days; small dots mark good days.'
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

  // Distinguish pain onsets from good days on every chart: pain days are larger
  // diamonds, good days are small dots. Shared across all datasets.
  const ptStyle  = pts.map((p) => (p.is_good_day ? 'circle' : 'rectRot'));
  const ptRadius = pts.map((p) => (p.is_good_day ? 2 : 4.5));

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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
          pointRadius: ptRadius,
          pointStyle: ptStyle,
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
  const [types, meds, locs, settings] = await Promise.all([
    api.get('/api/headache_types'),
    api.get('/api/medications'),
    api.get('/api/locations'),
    api.get('/api/settings'),
  ]);

  const goodDayTypeId = settings.good_day_type_id;
  const visibleTypes = types.filter((t) => t.id !== goodDayTypeId);

  app.innerHTML = pageHeader(
    '<span class="fault-accent">Manage</span> Data',
    'Customize your reference lists.'
  );

  // ── Settings card (first) ──────────────────────────────
  const gdMode = settings.good_day_mode || 'auto';
  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Settings')}
      <div class="form-group" style="margin-bottom:0.25rem">
        <label class="cfz-label" style="margin-bottom:0.5rem">Good day mode</label>
        <div class="seg-toggle" id="gdmode-toggle" role="group" aria-label="Good day mode">
          <button type="button" class="seg-btn${gdMode === 'auto' ? ' seg-active' : ''}" data-gdmode="auto">Auto</button>
          <button type="button" class="seg-btn${gdMode === 'manual' ? ' seg-active' : ''}" data-gdmode="manual">Manual</button>
        </div>
        <p style="font-size:0.72rem;color:var(--muted);margin-top:0.5rem;line-height:1.5">
          <strong style="color:var(--muted2)">Auto</strong> — days with no entries (from your first entry on) count as good days automatically.<br>
          <strong style="color:var(--muted2)">Manual</strong> — only days you explicitly log as a Good Day count as good.
        </p>
      </div>
    </div>`));

  app.querySelector('#gdmode-toggle').addEventListener('click', async (ev) => {
    const btn = ev.target.closest('.seg-btn');
    if (!btn) return;
    const newMode = btn.dataset.gdmode;
    try {
      await api.put('/api/settings', { good_day_mode: newMode });
      toast('Good days: ' + (newMode === 'auto' ? 'Auto' : 'Manual'));
      renderManage();
    } catch (e) {
      toast('Failed: ' + e.message, 'err');
    }
  });

  // ── Backup & Restore ───────────────────────────────────
  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Backup &amp; Restore')}
      <p style="font-size:0.72rem;color:var(--muted);margin:0 0 0.75rem;line-height:1.5">
        Download your full history as a JSON file, or restore one when moving to another
        deployment. <strong style="color:var(--accent)">Importing replaces all current data.</strong>
      </p>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:center">
        <a href="/api/data/export" class="cfz-btn-amber" download>Export data</a>
        <button type="button" id="import-btn" class="cfz-btn-add">Import data…</button>
        <input type="file" id="import-file" accept="application/json,.json" style="display:none" />
      </div>
    </div>`));

  const importBtn = app.querySelector('#import-btn');
  const importFile = app.querySelector('#import-file');
  importBtn.addEventListener('click', () => importFile.click());
  importFile.addEventListener('change', async () => {
    const file = importFile.files[0];
    if (!file) return;
    if (!confirm('Importing will REPLACE all current data with the contents of this file. This cannot be undone. Continue?')) {
      importFile.value = '';
      return;
    }
    try {
      const text = await file.text();
      let data;
      try { data = JSON.parse(text); }
      catch { throw new Error('not a valid JSON file'); }
      const res = await api.post('/api/data/import', data);
      const c = res.counts || {};
      toast(`Imported ${c.entries ?? 0} entries`);
      location.hash = '#/dashboard';
    } catch (e) {
      toast('Import failed: ' + e.message, 'err');
    } finally {
      importFile.value = '';
    }
  });

  // ── Headache Types ─────────────────────────────────────
  app.appendChild(el(`
    <div class="cfz-card" style="margin-bottom:1rem">
      ${cardTitle('Headache Types')}
      <div id="types-list">
        ${manageRows(visibleTypes, (t) => t.name, null, 'type')}
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
