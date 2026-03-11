/* ============================================
   BR COMMAND CENTER — LIVE APP.JS (v6 — Feed action controls)
   No CGI background refresh (static S3 site).
   Data is baked in at deploy time via window.__DASHBOARD_CACHE__.
   v5: Expandable feed rows now show actual email bodies, LinkedIn messages,
       and InMail content for quality monitoring.
   v6: Subtle action controls in expanded feed panel — remove from queue,
       remove & block contact. Uses direct HubSpot API calls.
   v7: Google SSO auth gate — popup-to-postMessage pattern.
   ============================================ */

// ─── Auth Config ───
// MIGRATION: Replace this Client ID with your own from Google Cloud Console.
// Project: buoyant-silicon-345213 | Also hardcoded in: oauth-popup.html, sapt-tool/app.js, sapt-tool/oauth-popup.html
const GOOGLE_CLIENT_ID = '105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com';
const AUTH_MAX_AGE_MS = 8 * 60 * 60 * 1000; // 8 hours
let _authState = null; // In-memory auth state (sandboxed iframe constraint)

// ─── API Config (feed actions via backend proxy) ───
// MIGRATION: On Perplexity hosting, the proxy path is 'port/8000'.
// On Replit, Azure, Docker, or any self-hosted environment, use '' (same origin).
// This auto-detects: if running on Perplexity's pplx.app, use the proxy; otherwise, relative.
const API_BASE = (window.location.hostname.includes('pplx.app') || window.location.hostname.includes('perplexity.ai')) ? 'port/8000' : '';
// MIGRATION: This is your HubSpot portal ID. Used for generating "View in HubSpot" links.
// Craig's HubSpot account: 6282372
const HS_PORTAL = '6282372';

let chartInstance = null;

// ─── Utilities ───
function updateClock() {
  const el = document.getElementById('sidebar-clock');
  if (el) el.textContent = new Date().toLocaleString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'America/New_York'
  });
}

function setSyncTime(ts) {
  const el = document.getElementById('sync-time');
  if (!el) return;
  if (!ts) { el.textContent = '—'; return; }
  const d = new Date(ts);
  const h = d.getHours(), m = d.getMinutes();
  el.textContent = `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h >= 12 ? 'PM' : 'AM'} EST`;
}

function fmtCurrency(v) {
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(2) + 'M';
  if (v >= 1e3) return '$' + Math.round(v).toLocaleString();
  return '$' + Math.round(v);
}
function fmtNum(v) { return Math.round(v).toLocaleString(); }

function animateTo(el, target, dur, fmt) {
  if (!el) return;
  const start = parseFloat(el.dataset.currentValue || '0');
  const t0 = performance.now();
  const ease = t => 1 - Math.pow(1 - t, 3);
  (function step(now) {
    const p = Math.min((now - t0) / dur, 1);
    el.textContent = fmt(start + (target - start) * ease(p));
    if (p < 1) requestAnimationFrame(step);
    else { el.textContent = fmt(target); el.dataset.currentValue = target; }
  })(t0);
}

function setStatus(text, level) {
  const dot = document.querySelector('.status-dot');
  const lbl = document.querySelector('.status-label');
  if (dot) { dot.className = `status-dot status-dot--${level}`; if (level === 'green') dot.classList.add('pulse'); }
  if (lbl) { lbl.textContent = text; lbl.style.color = `var(--${level})`; }
}

function showLoading(show) {
  const o = document.getElementById('loading-overlay');
  if (o) o.style.display = show ? 'flex' : 'none';
}

// ─── Renderers ───
function renderKPIs(c, co, d, h) {
  const kpis = [
    { id: 'kpi-pipeline', val: d.total_value, fmt: fmtCurrency, sub: 'Total weighted pipeline' },
    { id: 'kpi-deals', val: d.total, fmt: fmtNum, sub: `${d.tiers.enterprise.count} Ent · ${d.tiers.midmarket.count} Mid · ${d.tiers.smb.count} SMB` },
    { id: 'kpi-contacts', val: c.total, fmt: fmtNum, sub: `${c.leads} leads in CRM` },
    { id: 'kpi-companies', val: co.total, fmt: fmtNum, sub: `Across ${Object.keys(co.verticals).length} verticals` },
    { id: 'kpi-linkedin', val: c.with_linkedin, fmt: fmtNum, sub: `${c.linkedin_coverage_pct}% coverage` },
    { id: 'kpi-outreach', val: h.outreach_pieces || 400, fmt: v => fmtNum(v) + '+', sub: 'Ready to deploy' }
  ];
  kpis.forEach(k => {
    animateTo(document.getElementById(k.id + '-value'), k.val, 1200, k.fmt);
    const sub = document.getElementById(k.id + '-sub');
    if (sub) sub.textContent = k.sub;
  });
}

function renderFunnel(deals) {
  const order = ['Prospect', 'Qualified', 'Sequence Enrolled', 'Meeting Booked', 'Proposal Sent', 'Negotiation', 'Closed Won'];
  const short = ['Prospect', 'Qualified', 'Enrolled', 'Mtg Booked', 'Proposal', 'Negotiation', 'Won'];
  const el = document.getElementById('funnel-container');
  if (!el) return;
  const mx = Math.max(...order.map(s => deals.stages[s] || 0), 1);
  el.innerHTML = order.map((s, i) => {
    const n = deals.stages[s] || 0;
    const active = n > 0;
    return `<div class="funnel-stage ${active ? 'funnel-stage--active' : ''}">
      <div class="funnel-bar"><div class="funnel-bar-fill ${active ? 'funnel-bar-fill--active' : 'funnel-bar-fill--dim'}" data-pct="${Math.max((n / mx) * 100, n > 0 ? 8 : 3)}"></div></div>
      <div class="funnel-info">
        <span class="funnel-count ${active ? 'funnel-count--active' : ''}">${n}</span>
        <span class="funnel-label">${short[i]}</span>
        ${!active ? '<span class="funnel-badge">Pre-launch</span>' : ''}
      </div>
    </div>`;
  }).join('');
  requestAnimationFrame(() => { el.querySelectorAll('.funnel-bar-fill').forEach(b => { b.style.width = b.dataset.pct + '%'; }); });
}

function renderRouting(c) {
  const total = c.cold_dtc + c.expansion || 1;
  const cp = Math.round(c.cold_dtc / total * 100), ep = Math.round(c.expansion / total * 100);
  const set = (id, t) => { const e = document.getElementById(id); if (e) e.textContent = t; };
  set('routing-cold-value', `${c.cold_dtc} contacts`); set('routing-cold-pct', cp + '%');
  set('routing-exp-value', `${c.expansion} contacts`); set('routing-exp-pct', ep + '%');
  const cb = document.getElementById('routing-cold-bar'), eb = document.getElementById('routing-exp-bar');
  if (cb) { cb.style.setProperty('--target-width', cp + '%'); cb.classList.add('animate-bar'); }
  if (eb) { eb.style.setProperty('--target-width', ep + '%'); eb.classList.add('animate-bar'); }
  const ps = document.getElementById('expandi-push-stats');
  if (ps) ps.innerHTML = [['Pushed A', c.pushed_campaign_a], ['Pushed B', c.pushed_campaign_b], ['Queued', c.not_pushed], ['No LI URL', c.no_linkedin]]
    .map(([l, v]) => `<div class="push-stat"><span class="push-stat-value">${v}</span><span class="push-stat-label">${l}</span></div>`).join('');
}

function renderChart(verticals) {
  const ctx = document.getElementById('verticalChart');
  if (!ctx || !Object.keys(verticals).length) return;
  const nm = { 'fashion_apparel': 'Fashion & Apparel', '3pl_fulfillment': '3PL / Fulfillment', 'health_supplements': 'Health & Supplements', 'beauty_cosmetics': 'Beauty & Cosmetics', 'k_beauty_skincare': 'K-Beauty / Skincare', 'tech_accessories': 'Tech Accessories', 'subscription_boxes': 'Subscription Boxes', 'food_beverage': 'Food & Beverage', 'home_garden': 'Home & Garden', 'consumer_electronics': 'Consumer Electronics' };
  const colors = ['#0EA5E9', '#06B6D4', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#F97316', '#3D4556'];
  let items = Object.entries(verticals).map(([k, v]) => [nm[k] || k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), v]).sort((a, b) => b[1] - a[1]);
  const top = items.slice(0, 6);
  const otherSum = items.slice(6).reduce((s, [, v]) => s + v, 0);
  if (otherSum > 0) top.push(['Other', otherSum]);
  const labels = top.map(x => x[0]), data = top.map(x => x[1]);

  if (chartInstance) { chartInstance.data.labels = labels; chartInstance.data.datasets[0].data = data; chartInstance.data.datasets[0].backgroundColor = colors.slice(0, labels.length); chartInstance.update('active'); return; }
  chartInstance = new Chart(ctx, {
    type: 'doughnut', data: { labels, datasets: [{ data, backgroundColor: colors.slice(0, labels.length), borderColor: '#161922', borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '62%', animation: { animateRotate: true, duration: 1200, easing: 'easeOutQuart' },
      plugins: { legend: { position: 'right', labels: { color: '#8B95A9', font: { family: "'Inter', sans-serif", size: 11, weight: '500' }, padding: 12, usePointStyle: true, pointStyleWidth: 8, boxWidth: 8, boxHeight: 8 } },
        tooltip: { backgroundColor: '#1C2030', titleColor: '#E8ECF4', bodyColor: '#8B95A9', borderColor: 'rgba(255,255,255,0.08)', borderWidth: 1, padding: 10, cornerRadius: 4,
          titleFont: { family: "'Inter', sans-serif", size: 12, weight: '600' }, bodyFont: { family: "'Inter', sans-serif", size: 11 },
          callbacks: { label: c => { const t = c.dataset.data.reduce((a, b) => a + b, 0); return ` ${c.parsed} companies (${((c.parsed / t) * 100).toFixed(1)}%)`; } } } } }
  });
}

function renderHealth(h) {
  const el = document.getElementById('health-grid');
  if (!el || !h.systems) return;
  el.innerHTML = h.systems.map((s, i) => `
    <div class="health-card ${s.level === 'amber' ? 'health-card--warn' : s.level === 'red' ? 'health-card--error' : ''}" style="animation-delay: ${300 + i * 40}ms">
      <div class="health-status health-status--${s.level}"><span class="health-dot"></span>${s.status}</div>
      <div class="health-name">${s.name}</div>
      <div class="health-detail">${s.detail}</div>
    </div>`).join('');
}

function renderTimeline(warmup) {
  if (!warmup) return;
  const items = document.querySelectorAll('.timeline-item');
  const week = warmup.week || 0;
  items.forEach((item, i) => {
    const dot = item.querySelector('.timeline-dot');
    const done = (i === 0 && warmup.status === 'ACTIVE') || (i > 0 && i <= week && i < items.length - 1);
    if (done) {
      dot.classList.add('timeline-dot--done');
      item.classList.add('timeline-item--done');
      if (!item.querySelector('.timeline-check')) item.querySelector('.timeline-content').insertAdjacentHTML('beforeend', '<div class="timeline-check">✓</div>');
    }
  });
}

function renderTiers(tiers) {
  const mx = Math.max(tiers.enterprise.value, tiers.midmarket.value, tiers.smb.value, 1);
  [tiers.enterprise, tiers.midmarket, tiers.smb].forEach((t, i) => {
    const d = document.getElementById(`tier-${i}-deals`), v = document.getElementById(`tier-${i}-value`), b = document.getElementById(`tier-${i}-bar`);
    if (d) d.textContent = `${t.count} deals`;
    if (v) v.textContent = fmtCurrency(t.value);
    if (b) { b.style.setProperty('--target-width', Math.max((t.value / mx) * 100, t.count > 0 ? 2 : 0) + '%'); b.classList.add('animate-bar'); }
  });
}

function renderExclusion(count) { animateTo(document.getElementById('exclusion-value'), count, 1000, fmtNum); }

// ─── Activity Feed (v4 — with filters, timestamps, all channels) ───
const FEED_ICONS = {
  email:    `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>`,
  linkedin: `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.95v5.66H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45z"/></svg>`,
  enrolled: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  prospect: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>`,
  expandi:  `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>`
};

// Store all events globally for filtering
let allFeedEvents = [];
let currentFilter = 'all';

function fmtFeedTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 0) return formatAbsTime(d); // future = show absolute
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return diffMin + 'm ago';
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return diffH + 'h ago';
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return 'Yesterday';
  if (diffD < 7) return diffD + 'd ago';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatAbsTime(d) {
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
    d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function fmtFeedTimeFull(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const diffMs = now - d;
  const diffH = Math.floor(diffMs / 3600000);
  // For events older than 24h, show absolute date+time
  if (diffH >= 24) {
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ', ' +
      d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  }
  return fmtFeedTime(ts);
}

function filterFeedEvents(filter) {
  currentFilter = filter;
  // Update active tab
  document.querySelectorAll('.feed-tab').forEach(t => {
    t.classList.toggle('feed-tab--active', t.dataset.filter === filter);
  });

  let filtered = allFeedEvents;
  if (filter === 'email') {
    filtered = allFeedEvents.filter(e => e.channel_class === 'email');
  } else if (filter === 'linkedin') {
    filtered = allFeedEvents.filter(e => e.channel_class === 'linkedin' || e.channel_class === 'expandi');
  } else if (filter === 'sequence') {
    filtered = allFeedEvents.filter(e => e.channel_class === 'sequence');
  }

  renderFeedRows(filtered);

  // Update badge count
  const badge = document.getElementById('feed-count');
  if (badge) badge.textContent = filtered.length + ' events';
}

function toggleFeedExpand(idx) {
  const row = document.querySelector(`.feed-item[data-idx="${idx}"]`);
  if (!row) return;
  const panel = row.querySelector('.feed-expand');
  const chevron = row.querySelector('.feed-chevron');
  const isOpen = row.classList.contains('feed-item--open');

  // Close any other open rows
  document.querySelectorAll('.feed-item--open').forEach(r => {
    if (r !== row) {
      r.classList.remove('feed-item--open');
      const p = r.querySelector('.feed-expand');
      if (p) p.style.maxHeight = '0';
    }
  });

  if (isOpen) {
    row.classList.remove('feed-item--open');
    if (panel) {
      // If maxHeight is 'none', set it to scrollHeight first for smooth close animation
      if (panel.style.maxHeight === 'none') {
        panel.style.maxHeight = panel.scrollHeight + 'px';
        // Force reflow, then collapse
        panel.offsetHeight;
      }
      panel.style.maxHeight = '0';
    }
  } else {
    row.classList.add('feed-item--open');
    if (panel) {
      // Set to scrollHeight initially, then auto after transition for dynamic content
      panel.style.maxHeight = panel.scrollHeight + 'px';
      // After the transition completes, switch to auto so inner scrolling works
      panel.addEventListener('transitionend', function handler() {
        if (row.classList.contains('feed-item--open')) {
          panel.style.maxHeight = 'none';
        }
        panel.removeEventListener('transitionend', handler);
      });
    }
  }
}

function buildSummaryHTML(summary) {
  if (!summary) return '<div class="expand-empty">No additional details available.</div>';

  const rows = [];
  const label = (key) => key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  // Ordered fields for display (metadata fields first)
  const metaFields = [
    'event_type', 'contact', 'company', 'title', 'email', 'location',
    'sequence', 'campaign', 'prospect_type', 'icp_score', 'pain_score',
    'expandi_status', 'enrollment_status',
    'linkedin_url', 'last_email_sent', 'last_email_opened', 'last_reply',
    'website', 'channels', 'shipping_signals', 'pain_signals', 'size'
  ];

  // Message content fields — rendered as quoted blocks
  const messageFields = [
    { key: 'email_subject', label: 'Cold Email Subject' },
    { key: 'email_body', label: 'Cold Email Body' },
    { key: 'followup_subject', label: 'Follow-Up Subject' },
    { key: 'followup_body', label: 'Follow-Up Body' },
    { key: 'breakup_subject', label: 'Breakup Subject' },
    { key: 'breakup_body', label: 'Breakup Body' },
    { key: 'li_connection_msg', label: 'LinkedIn Connection Request' },
    { key: 'li_inmail_msg', label: 'LinkedIn InMail' },
  ];
  const messageKeys = messageFields.map(f => f.key);

  const friendlyLabels = {
    event_type: 'Event',
    contact: 'Contact',
    company: 'Company',
    title: 'Title',
    email: 'Email',
    location: 'Location',
    sequence: 'Sequence',
    campaign: 'Campaign',
    prospect_type: 'Type',
    icp_score: 'ICP Score',
    pain_score: 'Pain Score',
    expandi_status: 'Expandi',
    enrollment_status: 'Status',
    linkedin_url: 'LinkedIn',
    last_email_sent: 'Last Sent',
    last_email_opened: 'Last Opened',
    last_reply: 'Last Reply',
    website: 'Website',
    channels: 'Channels',
    shipping_signals: 'Shipping Signals',
    pain_signals: 'Pain Signals',
    size: 'Company Size'
  };

  // Format timestamps
  function fmtVal(key, val) {
    if (!val) return '';
    if (['last_email_sent', 'last_email_opened', 'last_reply'].includes(key)) {
      const d = new Date(val);
      if (!isNaN(d.getTime())) {
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) + ' ' +
               d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
      }
    }
    if (key === 'linkedin_url') {
      return `<a href="${val}" target="_blank" rel="noopener" class="expand-link">${val.replace('https://www.linkedin.com/in/', '').replace('http://www.linkedin.com/in/', '').replace(/\/$/, '')}</a>`;
    }
    if (key === 'website' && val.startsWith('http')) {
      return `<a href="${val}" target="_blank" rel="noopener" class="expand-link">${val.replace(/^https?:\/\//, '')}</a>`;
    }
    if (key === 'icp_score' || key === 'pain_score') {
      const n = parseInt(val);
      const color = n >= 80 ? 'var(--green)' : n >= 60 ? 'var(--amber)' : 'var(--text-muted)';
      return `<span style="color:${color};font-weight:600">${val}/100</span>`;
    }
    return val;
  }

  // Render metadata fields
  for (const key of metaFields) {
    const val = summary[key];
    if (val && String(val).trim()) {
      const formatted = fmtVal(key, String(val).trim());
      if (formatted) {
        rows.push(`<div class="expand-field">
          <span class="expand-label">${friendlyLabels[key] || label(key)}</span>
          <span class="expand-value">${formatted}</span>
        </div>`);
      }
    }
  }

  // Also include any extra non-message fields not in metaFields
  for (const [key, val] of Object.entries(summary)) {
    if (!metaFields.includes(key) && !messageKeys.includes(key) && val && String(val).trim() && key !== 'campaign_id') {
      rows.push(`<div class="expand-field">
        <span class="expand-label">${friendlyLabels[key] || label(key)}</span>
        <span class="expand-value">${String(val).trim()}</span>
      </div>`);
    }
  }

  // Check if there's any message content to show
  const hasMessages = messageFields.some(f => summary[f.key] && String(summary[f.key]).trim());

  if (hasMessages) {
    // Group email messages and LinkedIn messages separately
    const emailMsgFields = messageFields.filter(f => !f.key.startsWith('li_'));
    const linkedinMsgFields = messageFields.filter(f => f.key.startsWith('li_'));

    const hasEmailContent = emailMsgFields.some(f => summary[f.key] && String(summary[f.key]).trim());
    const hasLinkedInContent = linkedinMsgFields.some(f => summary[f.key] && String(summary[f.key]).trim());

    if (hasEmailContent) {
      rows.push('<div class="expand-divider"></div>');
      rows.push('<div class="expand-section-header"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg> Email Outreach Content</div>');

      // Cold email
      if (summary.email_subject) {
        rows.push(renderMessageBlock('Cold Email', summary.email_subject, summary.email_body, 'email'));
      }
      // Follow-up
      if (summary.followup_subject) {
        rows.push(renderMessageBlock('Follow-Up Email', summary.followup_subject, summary.followup_body, 'email'));
      }
      // Breakup
      if (summary.breakup_subject) {
        rows.push(renderMessageBlock('Breakup Email', summary.breakup_subject, summary.breakup_body, 'email'));
      }
    }

    if (hasLinkedInContent) {
      rows.push('<div class="expand-divider"></div>');
      rows.push('<div class="expand-section-header"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.95v5.66H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45z"/></svg> LinkedIn Outreach Content</div>');

      if (summary.li_connection_msg) {
        rows.push(renderMessageBlock('Connection Request', null, summary.li_connection_msg, 'linkedin'));
      }
      if (summary.li_inmail_msg) {
        rows.push(renderMessageBlock('InMail', null, summary.li_inmail_msg, 'linkedin'));
      }
    }
  }

  // ── Action controls (only for events with a contact_id) ──
  const contactId = summary.contact_id;
  if (contactId) {
    rows.push('<div class="expand-divider"></div>');
    rows.push(`<div class="expand-actions">
      <div class="expand-actions-row">
        <button class="action-btn action-btn--subtle" onclick="event.stopPropagation(); openActionMenu(this, '${contactId}', '${escapeHtml((summary.contact || '').replace(/'/g, ''))}', '${escapeHtml((summary.company || '').replace(/'/g, ''))}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>
          Actions
        </button>
        <a class="action-link" href="https://app.hubspot.com/contacts/${HS_PORTAL}/contact/${contactId}" target="_blank" rel="noopener">View in HubSpot</a>
      </div>
    </div>`);
  }

  return rows.join('');
}

function renderMessageBlock(label, subject, body, type) {
  const typeClass = type === 'linkedin' ? 'msg-block--linkedin' : 'msg-block--email';
  let html = `<div class="msg-block ${typeClass}">`;
  html += `<div class="msg-block-label">${label}</div>`;
  if (subject) {
    html += `<div class="msg-block-subject">Subject: ${escapeHtml(subject)}</div>`;
  }
  if (body) {
    html += `<div class="msg-block-body">${escapeHtml(body)}</div>`;
  }
  html += '</div>';
  return html;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function renderFeedRows(events) {
  const el = document.getElementById('feed-container');
  if (!el) return;

  if (!events || events.length === 0) {
    el.innerHTML = '<div class="feed-empty">No activity found for this filter. Events will appear here as emails send, LinkedIn touches go out, and contacts get enrolled.</div>';
    return;
  }

  el.innerHTML = events.map((e, i) => {
    const iconClass = e.icon || 'prospect';
    const channelClass = e.channel_class || 'prospect';
    const timeStr = fmtFeedTimeFull(e.timestamp);
    const hasSummary = e.summary && Object.keys(e.summary).length > 0;
    return `<div class="feed-item${hasSummary ? ' feed-item--expandable' : ''}" data-idx="${i}">
      <div class="feed-row" style="animation-delay: ${50 + i * 30}ms" onclick="toggleFeedExpand(${i})">
        <div class="feed-icon feed-icon--${iconClass}">${FEED_ICONS[iconClass] || FEED_ICONS.prospect}</div>
        <div class="feed-body">
          <div class="feed-action">${e.action}</div>
          <div class="feed-detail">${e.detail || ''}</div>
        </div>
        <div class="feed-meta">
          <span class="feed-time">${timeStr}</span>
          <span class="feed-channel feed-channel--${channelClass}">${e.channel || ''}</span>
        </div>
        ${hasSummary ? '<div class="feed-chevron"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg></div>' : ''}
      </div>
      ${hasSummary ? `<div class="feed-expand" style="max-height:0">${buildSummaryHTML(e.summary)}</div>` : ''}
    </div>`;
  }).join('');
}

function renderActivityFeed(events) {
  allFeedEvents = events || [];

  // Client-side safety net: filter out any events for blocked/removed contacts
  // This prevents stale cache from showing blocked contacts in the feed
  const cache = window.__DASHBOARD_CACHE__ || {};
  const blockedContacts = cache.blocked_contacts || [];
  if (blockedContacts.length > 0) {
    const blockedIds = new Set(blockedContacts.map(c => String(c.id)));
    const before = allFeedEvents.length;
    allFeedEvents = allFeedEvents.filter(e => {
      const cid = e.summary && e.summary.contact_id;
      return !cid || !blockedIds.has(String(cid));
    });
    if (allFeedEvents.length < before) {
      console.log(`Feed filter: removed ${before - allFeedEvents.length} events for blocked contacts`);
    }
  }

  // Update badge
  const badge = document.getElementById('feed-count');
  if (badge) badge.textContent = allFeedEvents.length + ' events';

  // Build filter tabs
  const tabContainer = document.getElementById('feed-tabs');
  if (tabContainer) {
    const emailCount = allFeedEvents.filter(e => e.channel_class === 'email').length;
    const linkedinCount = allFeedEvents.filter(e => e.channel_class === 'linkedin' || e.channel_class === 'expandi').length;
    const seqCount = allFeedEvents.filter(e => e.channel_class === 'sequence').length;

    tabContainer.innerHTML = `
      <button class="feed-tab feed-tab--active" data-filter="all" onclick="filterFeedEvents('all')">All (${allFeedEvents.length})</button>
      <button class="feed-tab" data-filter="email" onclick="filterFeedEvents('email')">Email (${emailCount})</button>
      <button class="feed-tab" data-filter="linkedin" onclick="filterFeedEvents('linkedin')">LinkedIn (${linkedinCount})</button>
      <button class="feed-tab" data-filter="sequence" onclick="filterFeedEvents('sequence')">Sequences (${seqCount})</button>
    `;
  }

  // Render all events
  renderFeedRows(allFeedEvents);
}

// ─── Feed Action Controls (v6) ───
let activeActionMenu = null;

function openActionMenu(btn, contactId, contactName, companyName) {
  // Close any existing menu
  closeActionMenu();

  const menu = document.createElement('div');
  menu.className = 'action-menu';
  menu.innerHTML = `
    <div class="action-menu-header">Actions for ${contactName || 'Contact'}</div>
    <button class="action-menu-item" onclick="execAction('remove', '${contactId}', this)">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
      Remove from Queue
      <span class="action-menu-desc">Unenroll from sequences, stop outreach</span>
    </button>
    <button class="action-menu-item action-menu-item--danger" onclick="execAction('block', '${contactId}', this)">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64A9 9 0 0 1 20.77 15"/><path d="M6.16 6.16a9 9 0 1 0 12.68 12.68"/><line x1="2" y1="2" x2="22" y2="22"/></svg>
      Remove &amp; Block Contact
      <span class="action-menu-desc">Stop outreach and permanently block</span>
    </button>
  `;

  btn.parentElement.appendChild(menu);
  activeActionMenu = menu;

  // Position relative to button
  requestAnimationFrame(() => {
    menu.classList.add('action-menu--visible');
  });

  // Close on outside click
  setTimeout(() => {
    document.addEventListener('click', closeActionMenuHandler, { once: true });
  }, 10);
}

function closeActionMenuHandler(e) {
  if (activeActionMenu && !activeActionMenu.contains(e.target)) {
    closeActionMenu();
  }
}

function closeActionMenu() {
  if (activeActionMenu) {
    activeActionMenu.classList.remove('action-menu--visible');
    setTimeout(() => { if (activeActionMenu) { activeActionMenu.remove(); activeActionMenu = null; } }, 150);
  }
}

function showConfirmModal(title, message, dangerMode) {
  return new Promise((resolve) => {
    // Remove any existing modal
    const old = document.getElementById('action-confirm-modal');
    if (old) old.remove();

    const modal = document.createElement('div');
    modal.id = 'action-confirm-modal';
    modal.className = 'confirm-overlay';
    modal.innerHTML = `
      <div class="confirm-dialog">
        <div class="confirm-title">${title}</div>
        <div class="confirm-msg">${message}</div>
        <div class="confirm-btns">
          <button class="confirm-btn confirm-btn--cancel" id="confirm-cancel">Cancel</button>
          <button class="confirm-btn ${dangerMode ? 'confirm-btn--danger' : 'confirm-btn--primary'}" id="confirm-ok">${title}</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    requestAnimationFrame(() => modal.classList.add('confirm-overlay--visible'));

    const cleanup = (result) => {
      modal.classList.remove('confirm-overlay--visible');
      setTimeout(() => modal.remove(), 150);
      resolve(result);
    };
    modal.querySelector('#confirm-cancel').onclick = () => cleanup(false);
    modal.querySelector('#confirm-ok').onclick = () => cleanup(true);
    modal.addEventListener('click', (e) => { if (e.target === modal) cleanup(false); });
  });
}

async function execAction(action, contactId, btnEl) {
  const actionLabel = action === 'block' ? 'Remove & Block' : 'Remove from Queue';
  const menuItem = btnEl;

  // Custom in-page confirmation
  closeActionMenu();
  const confirmed = await showConfirmModal(
    actionLabel,
    `This will stop all outreach activity${action === 'block' ? ' and permanently block this contact from future outreach' : ' for this contact'}.`,
    action === 'block'
  );
  if (!confirmed) return;

  // Show a processing toast
  showActionToast('Processing…', `${actionLabel} in progress`, 'success');

  try {
    const resp = await fetch(`${API_BASE}/api/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contact_id: contactId, action: action })
    });

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || `Server error ${resp.status}`);
    }

    const result = await resp.json();

    // Success feedback
    closeActionMenu();
    showActionToast(
      action === 'block' ? 'Contact blocked' : 'Removed from queue',
      `${result.contact_name || 'Contact'} at ${result.company || 'company'} — outreach stopped.`,
      action === 'block' ? 'danger' : 'success'
    );

    // Add to in-memory blocked list so client-side filter catches it on re-renders
    const cache = window.__DASHBOARD_CACHE__;
    if (cache && cache.blocked_contacts) {
      cache.blocked_contacts.push({ id: contactId, name: result.contact_name || '', company: result.company || '', reason: action === 'block' ? 'Blocked Manual' : 'Removed Manual' });
    }

    // Update the feed item visually
    markFeedItemActioned(contactId, action);

  } catch (err) {
    console.error('Action failed:', err);
    closeActionMenu();
    showActionToast('Action failed', err.message, 'danger');
  }
}

function markFeedItemActioned(contactId, action) {
  // Find all feed items with this contact_id and slide them out
  document.querySelectorAll('.feed-item').forEach(item => {
    const expandPanel = item.querySelector('.feed-expand');
    if (!expandPanel) return;
    if (expandPanel.innerHTML.includes(`'${contactId}'`)) {
      // Collapse the expand panel first
      if (item.classList.contains('feed-item--open')) {
        item.classList.remove('feed-item--open');
        expandPanel.style.maxHeight = '0';
      }
      // Animate the row out
      item.style.overflow = 'hidden';
      item.style.maxHeight = item.offsetHeight + 'px';
      item.style.transition = 'max-height 350ms ease, opacity 250ms ease, margin 350ms ease';
      requestAnimationFrame(() => {
        item.style.maxHeight = '0';
        item.style.opacity = '0';
      });
      // Remove from DOM and update allFeedEvents after animation
      setTimeout(() => {
        item.remove();
        // Remove from in-memory array so filters stay accurate
        allFeedEvents = allFeedEvents.filter(e =>
          !(e.summary && String(e.summary.contact_id) === String(contactId))
        );
        // Update badge count
        const badge = document.getElementById('feed-count');
        const visible = document.querySelectorAll('.feed-item').length;
        if (badge) badge.textContent = visible + ' events';
        // Update filter tab counts
        updateFilterCounts();
      }, 400);
    }
  });
}

function updateFilterCounts() {
  const tabContainer = document.getElementById('feed-tabs');
  if (!tabContainer) return;
  const emailCount = allFeedEvents.filter(e => e.channel_class === 'email').length;
  const linkedinCount = allFeedEvents.filter(e => e.channel_class === 'linkedin' || e.channel_class === 'expandi').length;
  const seqCount = allFeedEvents.filter(e => e.channel_class === 'sequence').length;
  tabContainer.innerHTML = `
    <button class="feed-tab ${currentFilter === 'all' ? 'feed-tab--active' : ''}" data-filter="all" onclick="filterFeedEvents('all')">All (${allFeedEvents.length})</button>
    <button class="feed-tab ${currentFilter === 'email' ? 'feed-tab--active' : ''}" data-filter="email" onclick="filterFeedEvents('email')">Email (${emailCount})</button>
    <button class="feed-tab ${currentFilter === 'linkedin' ? 'feed-tab--active' : ''}" data-filter="linkedin" onclick="filterFeedEvents('linkedin')">LinkedIn (${linkedinCount})</button>
    <button class="feed-tab ${currentFilter === 'sequence' ? 'feed-tab--active' : ''}" data-filter="sequence" onclick="filterFeedEvents('sequence')">Sequences (${seqCount})</button>
  `;
}

function showActionToast(title, msg, level) {
  // Remove existing toast
  const old = document.querySelector('.action-toast');
  if (old) old.remove();

  const toast = document.createElement('div');
  toast.className = `action-toast action-toast--${level}`;
  toast.innerHTML = `
    <div class="toast-title">${title}</div>
    <div class="toast-msg">${msg}</div>
  `;
  document.body.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('action-toast--visible'));
  setTimeout(() => {
    toast.classList.remove('action-toast--visible');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ─── Blocked Contacts Panel (v7) ───
let blockedContactsData = [];

function openBlockedPanel() {
  const overlay = document.getElementById('blocked-overlay');
  const panel = document.getElementById('blocked-panel');
  if (!overlay || !panel) return;

  overlay.classList.add('blocked-overlay--visible');
  panel.classList.add('blocked-panel--open');
  document.body.style.overflow = 'hidden';

  // Render from cache first (instant), then optionally refresh via API
  if (blockedContactsData.length > 0) {
    renderBlockedList(blockedContactsData);
  } else if (window.__DASHBOARD_CACHE__ && window.__DASHBOARD_CACHE__.blocked_contacts) {
    blockedContactsData = window.__DASHBOARD_CACHE__.blocked_contacts;
    renderBlockedList(blockedContactsData);
  } else {
    // Fetch from API as fallback
    fetchBlockedContacts();
  }
}

function closeBlockedPanel() {
  const overlay = document.getElementById('blocked-overlay');
  const panel = document.getElementById('blocked-panel');
  if (overlay) overlay.classList.remove('blocked-overlay--visible');
  if (panel) panel.classList.remove('blocked-panel--open');
  document.body.style.overflow = '';
}

async function fetchBlockedContacts() {
  const listEl = document.getElementById('blocked-panel-list');
  if (listEl) listEl.innerHTML = '<div class="blocked-panel-loading">Loading...</div>';

  try {
    const resp = await fetch(`${API_BASE}/api/blocked-contacts`);
    if (!resp.ok) throw new Error(`Server error ${resp.status}`);
    const data = await resp.json();
    blockedContactsData = data.contacts || [];
    renderBlockedList(blockedContactsData);
  } catch (err) {
    console.error('Failed to fetch blocked contacts:', err);
    if (listEl) listEl.innerHTML = `<div class="blocked-panel-empty">Could not load blocked contacts.<br><span style="color:var(--text-faint);font-size:10px">${err.message}</span></div>`;
  }
}

function renderBlockedList(contacts) {
  const listEl = document.getElementById('blocked-panel-list');
  const countEl = document.getElementById('blocked-panel-count');
  if (countEl) countEl.textContent = contacts.length;

  if (!listEl) return;

  if (contacts.length === 0) {
    listEl.innerHTML = '<div class="blocked-panel-empty">No blocked contacts found.</div>';
    return;
  }

  listEl.innerHTML = contacts.map((c, i) => {
    const reasonClass = c.reason === 'Blocked Manual' ? 'blocked-reason--manual'
      : c.reason === 'Removed Manual' ? 'blocked-reason--removed'
      : c.reason === 'Bounced' ? 'blocked-reason--bounced'
      : c.reason === 'Opted Out' ? 'blocked-reason--opted-out'
      : '';
    const reasonLabel = c.reason === 'Blocked Manual' ? 'Manually Blocked'
      : c.reason === 'Removed Manual' ? 'Manually Removed'
      : c.reason || 'Blocked';

    return `<div class="blocked-contact" data-idx="${i}" data-contact-id="${c.id}">
      <div class="blocked-contact-row" onclick="toggleBlockedDetail(${i})">
        <div class="blocked-contact-info">
          <div class="blocked-contact-name">${escapeHtml(c.name)}</div>
          <div class="blocked-contact-meta">${escapeHtml(c.title ? c.title + ' · ' : '')}${escapeHtml(c.company)}</div>
        </div>
        <div class="blocked-contact-right">
          <span class="blocked-reason ${reasonClass}">${reasonLabel}</span>
          <svg class="blocked-contact-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
      </div>
      <div class="blocked-contact-detail" id="blocked-detail-${i}">
        <div class="blocked-detail-grid">
          ${c.email ? `<div class="blocked-detail-field"><span class="blocked-detail-label">Email</span><span class="blocked-detail-value">${escapeHtml(c.email)}</span></div>` : ''}
          ${c.location ? `<div class="blocked-detail-field"><span class="blocked-detail-label">Location</span><span class="blocked-detail-value">${escapeHtml(c.location)}</span></div>` : ''}
          ${c.icp_score ? `<div class="blocked-detail-field"><span class="blocked-detail-label">ICP Score</span><span class="blocked-detail-value" style="color:var(--amber);font-weight:600">${c.icp_score}/100</span></div>` : ''}
          ${c.pain_score ? `<div class="blocked-detail-field"><span class="blocked-detail-label">Pain Score</span><span class="blocked-detail-value" style="color:var(--amber);font-weight:600">${c.pain_score}/100</span></div>` : ''}
          ${c.expandi_status ? `<div class="blocked-detail-field"><span class="blocked-detail-label">Expandi</span><span class="blocked-detail-value">${escapeHtml(c.expandi_status)}</span></div>` : ''}
          ${c.linkedin_url ? `<div class="blocked-detail-field"><span class="blocked-detail-label">LinkedIn</span><span class="blocked-detail-value"><a href="${c.linkedin_url}" target="_blank" rel="noopener" class="expand-link">${c.linkedin_url.replace('https://www.linkedin.com/in/', '').replace(/\/$/, '')}</a></span></div>` : ''}
        </div>
        <div class="blocked-detail-actions">
          <button class="blocked-unblock-btn" onclick="event.stopPropagation(); unblockContact('${c.id}', ${i})">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
            Unblock Contact
          </button>
          <a class="blocked-hubspot-link" href="https://app.hubspot.com/contacts/${HS_PORTAL}/contact/${c.id}" target="_blank" rel="noopener">View in HubSpot</a>
        </div>
      </div>
    </div>`;
  }).join('');
}

function toggleBlockedDetail(idx) {
  const item = document.querySelector(`.blocked-contact[data-idx="${idx}"]`);
  if (!item) return;
  const detail = document.getElementById(`blocked-detail-${idx}`);
  const isOpen = item.classList.contains('blocked-contact--open');

  // Close all others
  document.querySelectorAll('.blocked-contact--open').forEach(el => {
    if (el !== item) {
      el.classList.remove('blocked-contact--open');
      const d = el.querySelector('.blocked-contact-detail');
      if (d) d.style.maxHeight = '0';
    }
  });

  if (isOpen) {
    item.classList.remove('blocked-contact--open');
    if (detail) detail.style.maxHeight = '0';
  } else {
    item.classList.add('blocked-contact--open');
    if (detail) {
      detail.style.maxHeight = detail.scrollHeight + 'px';
      detail.addEventListener('transitionend', function handler() {
        if (item.classList.contains('blocked-contact--open')) {
          detail.style.maxHeight = 'none';
        }
        detail.removeEventListener('transitionend', handler);
      });
    }
  }
}

async function unblockContact(contactId, idx) {
  const confirmed = await showConfirmModal(
    'Unblock Contact',
    'This will reset all blocked properties and make this contact eligible for future outreach sequences.',
    false
  );
  if (!confirmed) return;

  showActionToast('Processing\u2026', 'Unblocking contact', 'success');

  try {
    const resp = await fetch(`${API_BASE}/api/unblock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contact_id: contactId })
    });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || `Server error ${resp.status}`);
    }
    const result = await resp.json();

    showActionToast(
      'Contact unblocked',
      `${result.contact_name || 'Contact'} at ${result.company || 'company'} is now eligible for outreach.`,
      'success'
    );

    // Animate out and remove from list
    const item = document.querySelector(`.blocked-contact[data-idx="${idx}"]`);
    if (item) {
      item.style.overflow = 'hidden';
      item.style.maxHeight = item.offsetHeight + 'px';
      item.style.transition = 'max-height 350ms ease, opacity 250ms ease';
      requestAnimationFrame(() => {
        item.style.maxHeight = '0';
        item.style.opacity = '0';
      });
      setTimeout(() => {
        item.remove();
        // Update in-memory data
        blockedContactsData = blockedContactsData.filter(c => String(c.id) !== String(contactId));
        const countEl = document.getElementById('blocked-panel-count');
        if (countEl) countEl.textContent = blockedContactsData.length;
        // Update badge on exclusion card
        updateBlockedBadge(blockedContactsData.length);
        if (blockedContactsData.length === 0) {
          const listEl = document.getElementById('blocked-panel-list');
          if (listEl) listEl.innerHTML = '<div class="blocked-panel-empty">No blocked contacts found.</div>';
        }
      }, 400);
    }
  } catch (err) {
    console.error('Unblock failed:', err);
    showActionToast('Unblock failed', err.message, 'danger');
  }
}

function updateBlockedBadge(count) {
  const badge = document.getElementById('blocked-count-badge');
  if (badge) {
    if (count > 0) {
      badge.textContent = count + ' blocked';
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  }
}

// ─── Render All From Data ───
function renderDashboard(data) {
  const c = data.contacts, co = data.companies, d = data.deals, h = data.health;
  renderKPIs(c, co, d, h);
  renderFunnel(d);
  renderRouting(c);
  renderChart(co.verticals);
  renderHealth(h);
  renderTimeline(h.warmup);
  renderTiers(d.tiers);
  renderExclusion(h.exclusion_count);
  renderActivityFeed(data.activity_feed || []);

  // Load blocked contacts from cache and show badge
  if (data.blocked_contacts) {
    blockedContactsData = data.blocked_contacts;
    updateBlockedBadge(blockedContactsData.length);
  }

  setSyncTime(data.timestamp);
  showLoading(false);

  const issues = (h.systems || []).filter(s => s.level !== 'green');
  setStatus(issues.length ? `${issues.length} SYSTEM${issues.length > 1 ? 'S' : ''} NEED ATTENTION` : 'ALL SYSTEMS LIVE', issues.length ? 'amber' : 'green');
}

// ─── Load Strategy: Inline cache only (stable, no disappearing content) ───
function loadDashboard() {
  // The inline cache is always present — baked in at deploy time
  if (window.__DASHBOARD_CACHE__ && window.__DASHBOARD_CACHE__.contacts) {
    renderDashboard(window.__DASHBOARD_CACHE__);
    return;
  }

  // Fallback: try loading the static JSON file (also deployed to S3)
  fetch('./dashboard_cache.json')
    .then(r => r.ok ? r.json() : Promise.reject('not found'))
    .then(data => {
      if (data && data.contacts) {
        renderDashboard(data);
      } else {
        showFallbackState();
      }
    })
    .catch(() => {
      showFallbackState();
    });
}

function showFallbackState() {
  showLoading(false);
  setStatus('DATA PENDING — Next sync at 7:00 AM EST', 'amber');
}

// ─── Navigation ───
function initNav() {
  const items = document.querySelectorAll('.nav-item');
  items.forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      items.forEach(n => n.classList.remove('active'));
      item.classList.add('active');
      const t = document.getElementById(item.dataset.section);
      if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
  const main = document.getElementById('main-content');
  const secs = document.querySelectorAll('.section[id]');
  if (main) main.addEventListener('scroll', () => {
    let cur = '';
    secs.forEach(s => { if (s.offsetTop - main.scrollTop <= 100) cur = s.id; });
    if (cur) items.forEach(n => { n.classList.remove('active'); if (n.dataset.section === cur) n.classList.add('active'); });
  });
}

// ─── Google SSO Auth ───
function _decodeJwtPayload(token) {
  try {
    var parts = token.split('.');
    if (parts.length !== 3) return null;
    var payload = parts[1];
    // Base64url decode
    payload = payload.replace(/-/g, '+').replace(/_/g, '/');
    var pad = payload.length % 4;
    if (pad) payload += '===='.slice(pad);
    var json = atob(payload);
    return JSON.parse(json);
  } catch (e) {
    console.error('JWT decode error:', e);
    return null;
  }
}

function _getAuthState() {
  if (!_authState || !_authState.token || !_authState.timestamp) return null;
  // Check max age (8 hours)
  if (Date.now() - _authState.timestamp > AUTH_MAX_AGE_MS) {
    _authState = null;
    return null;
  }
  return _authState;
}

function _setAuthState(token, email, name, picture) {
  _authState = {
    token: token,
    email: email,
    name: name,
    picture: picture,
    timestamp: Date.now()
  };
}

function _showAuthGate() {
  var gate = document.getElementById('auth-gate');
  var dash = document.querySelector('.dashboard');
  if (gate) gate.style.display = 'flex';
  if (dash) dash.style.display = 'none';
}

function _hideAuthGate() {
  var gate = document.getElementById('auth-gate');
  var dash = document.querySelector('.dashboard');
  if (gate) gate.style.display = 'none';
  if (dash) dash.style.display = 'grid';
}

function _showUserInfo(name, picture) {
  var container = document.getElementById('header-user');
  var avatarEl = document.getElementById('header-user-avatar');
  var nameEl = document.getElementById('header-user-name');
  if (!container) return;
  // Use first name only
  var firstName = (name || '').split(' ')[0];
  if (nameEl) nameEl.textContent = firstName;
  if (avatarEl && picture) {
    avatarEl.src = picture;
    avatarEl.alt = firstName;
    avatarEl.style.display = 'block';
  }
  container.style.display = 'flex';
}

function _openGooglePopup() {
  var w = 480, h = 600;
  var left = (screen.width - w) / 2;
  var top = (screen.height - h) / 2;
  var features = 'width=' + w + ',height=' + h + ',left=' + left + ',top=' + top + ',toolbar=no,menubar=no,scrollbars=yes,resizable=yes';
  window.open('./oauth-popup.html', 'br-google-auth', features);
}

function _signOut() {
  _authState = null;
  var userEl = document.getElementById('header-user');
  if (userEl) userEl.style.display = 'none';
  _showAuthGate();
}

// Listen for postMessage from OAuth popup
window.addEventListener('message', function(event) {
  if (!event.data || event.data.type !== 'br-google-credential') return;
  var credential = event.data.credential;
  if (!credential) return;

  var payload = _decodeJwtPayload(credential);
  if (!payload) {
    console.error('Failed to decode Google credential');
    return;
  }

  var email = payload.email || '';
  var name = payload.name || '';
  var picture = payload.picture || '';

  // Store auth
  _setAuthState(credential, email, name, picture);

  // Show dashboard
  _hideAuthGate();
  _showUserInfo(name, picture);
  loadDashboard();
});

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
  updateClock();
  setInterval(updateClock, 30000);
  initNav();

  // Check for existing auth
  var authState = _getAuthState();
  if (authState) {
    // Valid session exists — skip login
    _hideAuthGate();
    _showUserInfo(authState.name, authState.picture);

    // Data is always in inline cache — render immediately
    if (window.__DASHBOARD_CACHE__ && window.__DASHBOARD_CACHE__.contacts) {
      showLoading(false);
      loadDashboard();
    } else {
      showLoading(true);
      setTimeout(() => showLoading(false), 8000);
      loadDashboard();
    }
  } else {
    // No auth — show login gate, hide dashboard
    _showAuthGate();
    showLoading(false);
  }

  // No background refresh — this is a static site.
  // Data is updated by the daily cron which rebuilds and redeploys.
  // The refresh button re-renders from existing data (useful after filter changes).
  const btn = document.getElementById('refresh-btn');
  if (btn) btn.addEventListener('click', () => {
    btn.classList.add('spinning');
    loadDashboard();
    setTimeout(() => btn.classList.remove('spinning'), 600);
  });
});
