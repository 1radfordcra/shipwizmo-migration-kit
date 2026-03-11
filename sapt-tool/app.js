/* ═══════════════════════════════════════════════════════════════════════════════
   Broad Reach Customer Portal — app.js
   Complete SPA: Router, Auth, Admin Views, Client Views, Rate Analysis Engine
   ═══════════════════════════════════════════════════════════════════════════════ */

// MIGRATION: On Perplexity hosting, the proxy path is 'port/8000'.
// On Replit, Azure, Docker, or any self-hosted environment, use '' (same origin).
// This auto-detects: if running on Perplexity's pplx.app, use the proxy; otherwise, relative.
const _API_HOST = (window.location.hostname.includes('pplx.app') || window.location.hostname.includes('perplexity.ai')) ? 'port/8000' : '';
const API = `${_API_HOST}/api`;

// ─── State ────────────────────────────────────────────────────────────────────
let state = {
  token: null,
  userType: null,
  userId: null,
  userName: '',
  userEmail: '',
  companyName: '',
  logoUrl: '',
  clientStatus: '',
  theme: 'light'
};

// ─── Theme Toggle ─────────────────────────────────────────────────────────────
function initTheme() {
  state.theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', state.theme);
}

function toggleTheme() {
  state.theme = state.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', state.theme);
  const btn = document.querySelector('[data-theme-toggle]');
  if (btn) {
    btn.innerHTML = state.theme === 'dark'
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  }
}

// ─── API Helpers ──────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  let url = API + path;
  const sep = url.includes('?') ? '&' : '?';
  if (state.token) url += sep + 'token=' + encodeURIComponent(state.token);
  const res = await fetch(url, {
    method: opts.method || 'GET',
    headers: opts.body ? { 'Content-Type': 'application/json' } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined
  });
  if (res.status === 401) {
    // Session expired — clear state and redirect to login
    const wasAdmin = state.userType === 'admin';
    state.token = null;
    state.userType = null;
    state.userId = null;
    showToast('Your session has expired. Please log in again.', 'error');
    setTimeout(() => {
      window.location.hash = wasAdmin ? '#admin-login' : '#login';
      router();
    }, 300);
    throw new Error('Session expired');
  }
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

// ─── Toast Notifications ─────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 200);
  }, 3000);
}

// ─── Modal ────────────────────────────────────────────────────────────────────
function openModal(title, contentHtml, opts) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = contentHtml;
  document.getElementById('modal-overlay').classList.remove('hidden');
  const modalBox = document.querySelector('.modal-content');
  if (modalBox) {
    modalBox.classList.toggle('modal-wide', !!(opts && opts.wide));
  }
  document.body.style.overflow = 'hidden';
}

function closeModal(e) {
  // Only block if clicking directly on overlay background (not child elements)
  // When called programmatically (no event) or from a button, always close
  document.getElementById('modal-overlay').classList.add('hidden');
  document.body.style.overflow = '';
}

// ─── SVG Logo ─────────────────────────────────────────────────────────────────
const BR_LOGO = `<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Broad Reach">
  <rect x="2" y="2" width="28" height="28" rx="6" fill="var(--color-primary)"/>
  <path d="M8 10h6c2.2 0 4 1.2 4 3s-1.2 2.6-2.5 2.8c1.8.3 3.2 1.5 3.2 3.4 0 2.2-2 3.8-4.5 3.8H8V10z" fill="var(--color-text-inverse)"/>
  <path d="M21 10h2.5l3.5 6-3.5 7H21l3.5-7L21 10z" fill="var(--color-text-inverse)" opacity="0.85"/>
</svg>`;

const BR_LOGO_FULL = `<div class="logo-full">${BR_LOGO}<span class="logo-text">Broad Reach</span></div>`;

// ─── Router ───────────────────────────────────────────────────────────────────
function navigate(hash) {
  window.location.hash = hash;
}

function getRoute() {
  return window.location.hash.slice(1) || 'login';
}

function router() {
  if (window._skipHashChange) return;
  const route = getRoute();
  const app = document.getElementById('app');

  // Auth guard
  if (!state.token) {
    if (route === 'admin-login') {
      renderAdminLogin(app);
    } else {
      renderClientLogin(app);
    }
    return;
  }

  if (state.userType === 'admin') {
    renderAdminShell(app, route);
  } else {
    renderClientShell(app, route);
  }
}

window.addEventListener('hashchange', router);

// ─── Helpers ──────────────────────────────────────────────────────────────────
function esc(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + (dateStr.includes('Z') || dateStr.includes('+') ? '' : 'Z'));
  const now = new Date();
  const sec = Math.floor((now - d) / 1000);
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
}

function formatCurrency(n, currency) {
  const val = Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (currency === 'CAD') return 'C$' + val;
  return '$' + val;
}

function getCurrencyLabel(code) {
  return code === 'CAD' ? 'CAD (C$)' : 'USD ($)';
}

function formatDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function relativeTime(dateStr) {
  if (!dateStr) return '<span class="text-muted">Never</span>';
  const d = new Date(dateStr + 'Z');
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return 'Just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
  return d.toLocaleDateString();
}

function logout() {
  state = { token: null, userType: null, userId: null, userName: '', userEmail: '', companyName: '', logoUrl: '', clientStatus: '', theme: state.theme };
  navigate('login');
}


/* ═══════════════════════════════════════════════════════════════════════════════
   CLIENT LOGIN
   ═══════════════════════════════════════════════════════════════════════════════ */

function renderClientLogin(app) {
  app.innerHTML = `
    <div class="login-page">
      <div class="login-card">
        <div class="login-logo">${BR_LOGO_FULL}</div>
        <h1 class="login-heading">Customer Portal</h1>
        <p class="login-subtext">Welcome back. Sign in to access your shipping portal.</p>
        <div class="email-login-form-primary">
          <div class="form-field">
            <label for="client-email">Email address</label>
            <input type="email" id="client-email" placeholder="you@company.com" autocomplete="email">
          </div>
          <div class="form-field">
            <label for="client-password">Password</label>
            <input type="password" id="client-password" placeholder="From your invitation email" onkeydown="if(event.key==='Enter')clientLogin()" autocomplete="current-password">
          </div>
          <button class="btn-primary full-width" onclick="clientLogin()">Sign In</button>
        </div>
        <div id="client-login-error" class="login-error hidden"></div>
        <div class="google-divider"><span>or</span></div>
        <div id="google-signin-btn-client" class="google-btn-container" style="display:flex;justify-content:center;min-height:44px;"></div>
        <p class="forgot-password-help">Lost your password? Reply to your invitation email for help.</p>
        <div class="login-footer">
          <a href="#admin-login" class="admin-link">Admin Login</a>
          <button data-theme-toggle onclick="toggleTheme()" aria-label="Toggle theme" title="Toggle dark/light mode" class="theme-btn-inline">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          </button>
        </div>
      </div>
    </div>`;
  // Render the Google Sign-In button directly (inline, no popups)
  _renderGoogleButton('google-signin-btn-client', 'client');
}

async function handleGoogleCredential(response) {
  const errEl = document.getElementById('client-login-error');
  errEl.classList.add('hidden');
  try {
    const res = await api('/auth/google', {
      method: 'POST',
      body: { credential: response.credential }
    });
    state.token = res.token;
    state.userType = 'client';
    state.userId = res.user_id;
    state.companyName = res.company_name;
    state.userEmail = res.email;
    state.userName = res.contact_name;
    state.logoUrl = res.logo_url;
    state.clientStatus = res.status;
    navigate('client');
  } catch (e) {
    errEl.textContent = e.message || 'No invitation found for this Google account. Please contact your Broad Reach representative.';
    errEl.classList.remove('hidden');
  }
}

async function handleAdminGoogleCredential(response) {
  const errEl = document.getElementById('admin-login-error');
  if (errEl) errEl.classList.add('hidden');
  try {
    const res = await api('/auth/google-admin', {
      method: 'POST',
      body: { credential: response.credential }
    });
    state.token = res.token;
    state.userType = 'admin';
    state.userId = res.user_id;
    state.userName = res.name;
    state.userEmail = res.email;
    router();
  } catch (e) {
    if (errEl) {
      errEl.textContent = e.message || 'Google Sign-In failed for admin account';
      errEl.classList.remove('hidden');
    }
  }
}

// MIGRATION: Replace this Client ID with your own from Google Cloud Console.
// Project: buoyant-silicon-345213 | Also hardcoded in: oauth-popup.html, command-center/app.js, command-center/oauth-popup.html
const GOOGLE_CLIENT_ID = '105648453442-gjnirc4fa4tmii07lt1lmd353serh4ng.apps.googleusercontent.com';

function _ssoStatus(msg, isError) {
  console.log('Google SSO:', msg);
  // Show error in the appropriate login error element
  if (isError) {
    const errEl = document.getElementById('admin-login-error') || document.getElementById('client-login-error');
    if (errEl) { errEl.textContent = msg; errEl.classList.remove('hidden'); }
  }
}

function _clearSsoStatus() {
  // No overlay to clear anymore
}

// ─── Google Sign-In via popup window ─────────────────────────────────────────
// The portal runs in a sandboxed iframe that blocks Google auth popups.
// Solution: open our own popup (oauth-popup.html) as a top-level window.
// That page loads Google's GIS library, renders the sign-in button, gets the
// credential JWT, and sends it back to us via postMessage.

function _renderGoogleButton(containerId, role) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = `
    <button class="google-signin-btn" onclick="_openGooglePopup('${role}')" type="button" style="width:300px;">
      <svg width="20" height="20" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>
      Continue with Google
    </button>`;
}

function _openGooglePopup(role) {
  const errElId = role === 'admin' ? 'admin-login-error' : 'client-login-error';
  const errEl = document.getElementById(errElId);
  if (errEl) errEl.classList.add('hidden');

  // Build the popup URL — oauth-popup.html is in the same directory
  const currentUrl = window.location.href;
  const baseUrl = currentUrl.substring(0, currentUrl.lastIndexOf('/') + 1);
  const popupUrl = baseUrl + 'oauth-popup.html#' + role;

  // Open the popup as a top-level window (not constrained by iframe sandbox)
  const w = 480, h = 600;
  const left = (screen.width - w) / 2;
  const top = (screen.height - h) / 2;
  const popup = window.open(popupUrl, 'br_google_signin',
    `width=${w},height=${h},left=${left},top=${top},toolbar=no,menubar=no,scrollbars=yes,resizable=yes`);

  if (!popup || popup.closed) {
    if (errEl) {
      errEl.textContent = 'Popup was blocked by your browser. Please allow popups for this site and try again.';
      errEl.classList.remove('hidden');
    }
    return;
  }

  // Focus the popup
  popup.focus();
}

// Listen for the credential coming back from the popup via postMessage
window.addEventListener('message', function(event) {
  if (!event.data || event.data.type !== 'br-google-credential') return;
  const { credential, role } = event.data;
  if (credential) {
    _handleGoogleCredential({ credential }, role || 'client');
  }
});

async function _handleGoogleCredential(response, roleOverride) {
  // This receives the credential (JWT id_token) from the popup's postMessage
  const role = roleOverride || window._googleSsoRole || 'client';

  if (!response.credential) {
    _ssoStatus('No credential received from Google.', true);
    return;
  }

  console.log('Google SSO: credential received for role', role);

  // Show a loading indicator on the login error area (repurposed for status)
  const errElId = role === 'admin' ? 'admin-login-error' : 'client-login-error';
  const errEl = document.getElementById(errElId);
  if (errEl) {
    errEl.textContent = 'Signing you in...';
    errEl.style.color = '#166534';
    errEl.style.background = '#f0fdf4';
    errEl.style.border = '1px solid #86efac';
    errEl.classList.remove('hidden');
  }

  try {
    // Send the ID token (JWT credential) to our backend
    const endpoint = role === 'admin' ? '/auth/google-admin' : '/auth/google';
    const apiUrl = API + endpoint;
    console.log('Google SSO: posting credential to', apiUrl);
    const backendResp = await fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential: response.credential })
    });
    const res = await backendResp.json();
    console.log('Google SSO: backend responded', backendResp.status, res);

    // Handle unrecognized admin
    if (!backendResp.ok && role === 'admin' && res.error === 'not_recognized') {
      showAccessRequestUI(res.email, res.name, res.already_requested);
      return;
    }
    if (!backendResp.ok) throw new Error(res.error || 'Sign-in failed');

    if (role === 'admin') {
      state.token = res.token;
      state.userType = 'admin';
      state.userId = res.user_id;
      state.userName = res.name;
      state.userEmail = res.email;
      navigate('admin/dashboard');
    } else {
      state.token = res.token;
      state.userType = 'client';
      state.userId = res.user_id;
      state.companyName = res.company_name;
      state.userEmail = res.email;
      state.userName = res.contact_name;
      state.logoUrl = res.logo_url;
      state.clientStatus = res.status;
      navigate('client');
    }
  } catch (e) {
    console.error('Google SSO error:', e);
    _ssoStatus('Sign-in failed: ' + (e.message || String(e)), true);
  }
}

function showAccessRequestUI(email, name, alreadyRequested) {
  const app = document.getElementById('app');
  const card = app.querySelector('.login-card');
  if (!card) return;
  if (alreadyRequested) {
    card.innerHTML = `
      <div class="login-logo">${BR_LOGO_FULL}</div>
      <h1 class="login-heading">Request Pending</h1>
      <div class="access-request-status">
        <div class="access-request-icon pending">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        </div>
        <p>Your request for admin access with <strong>${esc(email)}</strong> is being reviewed.</p>
        <p class="access-request-hint">You'll receive an email once an administrator has approved your request.</p>
      </div>
      <div class="login-footer">
        <a href="#" class="admin-link" onclick="event.preventDefault();window.location.hash='admin';">Back to Login</a>
      </div>`;
  } else {
    card.innerHTML = `
      <div class="login-logo">${BR_LOGO_FULL}</div>
      <h1 class="login-heading">Access Not Found</h1>
      <div class="access-request-form-wrap">
        <p style="color: var(--text-secondary); margin-bottom: 1rem;">The account <strong>${esc(email)}</strong> does not have admin access to this portal.</p>
        <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">Would you like to request access? An administrator will be notified and can approve your request.</p>
        <div id="access-request-error" class="login-error hidden"></div>
        <button class="btn-primary full-width" onclick="submitAccessRequest('${esc(email)}', '${esc(name || '')}')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:8px;"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>
          Request Admin Access
        </button>
      </div>
      <div class="login-footer">
        <a href="#" class="admin-link" onclick="event.preventDefault();window.location.hash='admin';">Back to Login</a>
      </div>`;
  }
}

async function submitAccessRequest(email, name) {
  const errEl = document.getElementById('access-request-error');
  try {
    const resp = await fetch(API + '/access-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name })
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Failed to submit request');
    showAccessRequestUI(email, name, true);
  } catch (e) {
    if (errEl) {
      errEl.textContent = e.message;
      errEl.classList.remove('hidden');
    }
  }
}

async function clientLogin() {
  const email = document.getElementById('client-email').value.trim();
  const password = document.getElementById('client-password').value;
  if (!email) return;
  const errEl = document.getElementById('client-login-error');
  errEl.classList.add('hidden');
  try {
    const res = await api('/auth/login', { method: 'POST', body: { email, password, type: 'client' } });
    state.token = res.token;
    state.userType = 'client';
    state.userId = res.user_id;
    state.companyName = res.company_name;
    state.userEmail = res.email;
    state.userName = res.contact_name;
    state.logoUrl = res.logo_url;
    state.clientStatus = res.status;
    navigate('client');
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
  }
}


/* ═══════════════════════════════════════════════════════════════════════════════
   ADMIN LOGIN
   ═══════════════════════════════════════════════════════════════════════════════ */

function renderAdminLogin(app) {
  app.innerHTML = `
    <div class="login-page">
      <div class="login-card">
        <div class="login-logo">${BR_LOGO_FULL}</div>
        <h1 class="login-heading">Admin Portal</h1>
        <p class="login-subtext">Sign in to manage clients and rate cards.</p>
        <div class="email-login-form-primary">
          <div class="form-field">
            <label for="admin-email">Email</label>
            <input type="email" id="admin-email" placeholder="admin@company.com" autocomplete="email">
          </div>
          <div class="form-field">
            <label for="admin-password">Password</label>
            <input type="password" id="admin-password" placeholder="Password" onkeydown="if(event.key==='Enter')adminLogin()" autocomplete="current-password">
          </div>
          <button class="btn-primary full-width" onclick="adminLogin()">Sign In</button>
        </div>
        <div id="admin-login-error" class="login-error hidden"></div>
        <div class="google-divider"><span>or</span></div>
        <div id="google-signin-btn-admin" class="google-btn-container" style="display:flex;justify-content:center;min-height:44px;"></div>
        <div class="login-footer">
          <a href="#" class="admin-link" onclick="event.preventDefault();window.location.hash='';">Client Login</a>
          <button data-theme-toggle onclick="toggleTheme()" aria-label="Toggle theme" title="Toggle dark/light mode" class="theme-btn-inline">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          </button>
        </div>
      </div>
    </div>`;
  // Render the Google Sign-In button directly (inline, no popups)
  _renderGoogleButton('google-signin-btn-admin', 'admin');
}

async function adminLogin() {
  const email = document.getElementById('admin-email').value.trim();
  const password = document.getElementById('admin-password').value;
  const errEl = document.getElementById('admin-login-error');
  errEl.classList.add('hidden');
  try {
    const res = await api('/auth/login', { method: 'POST', body: { email, password, type: 'admin' } });
    state.token = res.token;
    state.userType = 'admin';
    state.userId = res.user_id;
    state.userName = res.name;
    state.userEmail = res.email;
    navigate('admin');
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
  }
}


/* ═══════════════════════════════════════════════════════════════════════════════
   CLIENT SHELL — Journey-Based Guided Experience
   ═══════════════════════════════════════════════════════════════════════════════ */

// ─── Journey State ───────────────────────────────────────────────────────────
let journeyStep = 1;        // 1=Welcome, 2=Upload, 3=Review, 4=Results
let journeySubStep = 'a';   // For step 2: a=choose method, b=configure, c=upload/map, d=confirm

let uploadedData = null;
let csvColumns = [];
let csvRows = [];
let uploadFileName = '';

function determineJourneyStep(client) {
  if (client.analysis && client.analysis.status === 'published') return 4;
  if (client.shipping_data && client.shipping_data.data && client.shipping_data.data.length > 0) return 3;
  return 1;
}

function isDataConfirmed(client) {
  return client.shipping_data && client.shipping_data.confirmed_at;
}

function renderClientShell(app, route) {
  const tab = route.replace('client/', '').replace('client', '') || '';

  // Build the shell DOM only once
  if (!document.getElementById('journey-stepper-container')) {
    app.innerHTML = `
      <div class="client-layout journey-layout">
        <header class="client-header">
          <div class="client-header-left">
            ${state.logoUrl ? `<img src="${esc(state.logoUrl)}" class="client-logo" alt="" onerror="this.style.display='none'">` : ''}
            <div>
              <div class="client-company">${esc(state.companyName)}</div>
              <div class="client-powered">Powered by Broad Reach</div>
            </div>
          </div>
          <div class="client-header-right">
            <a href="#" class="setup-info-link" onclick="event.preventDefault(); navigateJourney('setup')" title="Setup Information">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
              <span>Setup</span>
            </a>
            <button data-theme-toggle onclick="toggleTheme()" aria-label="Toggle theme" title="Toggle dark/light mode" class="icon-btn">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            </button>
            <button class="btn-ghost" onclick="logout()">Logout</button>
          </div>
        </header>
        <div id="journey-stepper-container"></div>
        <main class="client-main" id="client-content">
          <div class="content-area"><div class="skeleton-block"></div></div>
        </main>
      </div>`;
  }

  // Route to setup if explicit
  if (tab === 'setup') {
    renderJourneyStepper(0);
    const content = document.getElementById('client-content');
    renderClientSetup(content);
    return;
  }

  // Load client data and render the appropriate journey step
  loadJourney(tab);
}

async function loadJourney(requestedTab) {
  try {
    const client = await api(`/clients/${state.userId}?role=client`);
    window._clientData = client;
    const autoStep = determineJourneyStep(client);

    // Map tab routes to journey steps
    if (requestedTab === 'analysis' && autoStep === 4) {
      journeyStep = 4;
    } else if (requestedTab === 'upload') {
      journeyStep = 2;
    } else if (requestedTab === 'data-summary' && autoStep >= 3) {
      journeyStep = 3;
    } else if (requestedTab === 'overview' || requestedTab === '' || requestedTab === 'documents') {
      journeyStep = (autoStep === 1) ? 1 : autoStep;
    } else {
      journeyStep = autoStep;
    }

    renderJourneyStepper(journeyStep);
    const content = document.getElementById('client-content');
    if (content) renderJourneyContent(content, client);
  } catch (e) {
    const content = document.getElementById('client-content');
    if (content) content.innerHTML = `<div class="content-area"><div class="empty-state">Failed to load portal: ${esc(e.message)}</div></div>`;
  }
}

// Direct navigation — renders immediately using cached data, no hash-based routing
// Pass refresh=true after data mutations (upload, confirm, delete) to fetch fresh data
function navigateJourney(stepOrTab, opts) {
  const refresh = opts && opts.refresh;
  if (stepOrTab === 'setup') {
    navigate('client/setup');
    return;
  }
  if (typeof stepOrTab === 'number') {
    journeyStep = stepOrTab;
    journeySubStep = 'a';
    // Update hash for bookmarkability, but suppress the hashchange re-render
    const routeMap = { 1: 'client/overview', 2: 'client/upload', 3: 'client/data-summary', 4: 'client/analysis' };
    const target = routeMap[stepOrTab] || 'client';
    window._skipHashChange = true;
    window.location.hash = target;
    setTimeout(() => { window._skipHashChange = false; }, 50);

    if (refresh || !window._clientData) {
      // Fetch fresh data from server, then render
      _refreshAndRender();
    } else {
      // Render from cache
      renderJourneyStepper(journeyStep);
      const content = document.getElementById('client-content');
      if (content) renderJourneyContent(content, window._clientData);
    }
  }
}

async function _refreshAndRender() {
  try {
    const client = await api(`/clients/${state.userId}?role=client`);
    window._clientData = client;
    renderJourneyStepper(journeyStep);
    const content = document.getElementById('client-content');
    if (content) renderJourneyContent(content, client);
  } catch (e) {
    const content = document.getElementById('client-content');
    if (content) content.innerHTML = `<div class="content-area"><div class="empty-state">Failed to load: ${esc(e.message)}</div></div>`;
  }
}

function renderJourneyStepper(activeStep) {
  const container = document.getElementById('journey-stepper-container');
  if (!container) return;
  const maxReached = determineJourneyStep(window._clientData || {});
  const steps = [
    { num: 1, label: 'Welcome', icon: '👋' },
    { num: 2, label: 'Upload', icon: '📤' },
    { num: 3, label: 'Review', icon: '📋' },
    { num: 4, label: 'Results', icon: '📊' }
  ];

  container.innerHTML = `
    <div class="journey-stepper">
      <div class="journey-stepper-inner">
        ${steps.map((s, i) => {
          const done = s.num < activeStep || (maxReached >= s.num && s.num < activeStep);
          const isActive = s.num === activeStep;
          // Allow clicking any step up to the max reached OR the current step
          const isClickable = s.num <= maxReached || s.num <= activeStep;
          const statusClass = done ? 'completed' : isActive ? 'active' : (s.num <= maxReached ? 'completed' : 'upcoming');

          let connector = '';
          if (i < steps.length - 1) {
            const nextDone = (s.num + 1) <= activeStep || (s.num + 1) <= maxReached;
            connector = `<div class="journey-connector"><div class="journey-connector-fill" style="width:${nextDone ? 100 : (isActive ? 50 : 0)}%"></div></div>`;
          }

          return `
            <div class="journey-step ${statusClass} ${isClickable ? 'clickable' : ''}" ${isClickable ? `onclick="navigateJourney(${s.num})"` : ''}>
              <div class="journey-step-dot">
                ${done || (s.num <= maxReached && !isActive) ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>' : `<span>${s.num}</span>`}
              </div>
              <div class="journey-step-label">${s.label}</div>
            </div>
            ${connector}`;
        }).join('')}
      </div>
    </div>`;
}

function renderJourneyContent(el, client) {
  // Wrap in a transition container
  el.innerHTML = '<div class="journey-content journey-fade-in" id="journey-content-inner"></div>';
  const inner = document.getElementById('journey-content-inner');

  switch (journeyStep) {
    case 1: renderJourneyWelcome(inner, client); break;
    case 2: renderJourneyUpload(inner, client); break;
    case 3: renderJourneyReview(inner, client); break;
    case 4: renderJourneyResults(inner, client); break;
    default: renderJourneyWelcome(inner, client);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// STEP 1: Welcome
// ═══════════════════════════════════════════════════════════════════════════════

async function renderJourneyWelcome(el, client) {
  const contactName = state.userName || state.companyName || 'there';
  const firstName = contactName.split(' ')[0];
  const hasData = client.shipping_data && client.shipping_data.data && client.shipping_data.data.length > 0;
  const isConfirmed = isDataConfirmed(client);

  // Fetch documents
  let myDocs = [];
  try {
    const allDocs = await api('/documents');
    const myDocIds = client.documents_json || [];
    myDocs = allDocs.filter(d => myDocIds.includes(d.id));
  } catch (e) {}

  // Adapt CTA based on current progress
  let ctaStep, ctaLabel, ctaIcon, statusNote;
  if (isConfirmed) {
    ctaStep = 3;
    ctaLabel = 'View Analysis Status';
    ctaIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
    statusNote = '<div class="welcome-status-note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> Your data has been submitted — our team is working on your analysis.</div>';
  } else if (hasData) {
    ctaStep = 3;
    ctaLabel = 'Review Your Data';
    ctaIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
    statusNote = '<div class="welcome-status-note"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> Your shipping data is uploaded and ready for review.</div>';
  } else {
    ctaStep = 2;
    ctaLabel = "Let's Get Started";
    ctaIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>';
    statusNote = '';
  }

  el.innerHTML = `
    <div class="content-area welcome-content">
      <div class="welcome-hero">
        <h1 class="welcome-greeting">Hi ${esc(firstName)}! 👋</h1>
        <p class="welcome-message">
          ${hasData
            ? "Welcome back! Your shipping data is ready for the next step."
            : "We're going to collect your shipping data, analyze it against our carrier network, and show you exactly how much you could save."
          }
        </p>
        ${statusNote}
      </div>

      <div class="how-it-works">
        <h2 class="how-it-works-title">How it works</h2>
        <div class="how-it-works-cards">
          <div class="hiw-card ${hasData ? 'completed' : ''}">
            <div class="hiw-number">${hasData ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' : '1'}</div>
            <div class="hiw-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            </div>
            <h3 class="hiw-title">Upload</h3>
            <p class="hiw-desc">${hasData ? 'Done — your shipping history is uploaded.' : 'You share your shipping history — just a CSV file from your carrier.'}</p>
          </div>
          <div class="hiw-card">
            <div class="hiw-number">2</div>
            <div class="hiw-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            </div>
            <h3 class="hiw-title">We Analyze</h3>
            <p class="hiw-desc">Our team rates your data against 145+ carrier rate cards across 9 carriers.</p>
          </div>
          <div class="hiw-card">
            <div class="hiw-number">3</div>
            <div class="hiw-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
            </div>
            <h3 class="hiw-title">You Decide</h3>
            <p class="hiw-desc">Review your personalized savings report and see your potential.</p>
          </div>
        </div>
      </div>

      ${!hasData ? `<div class="welcome-time-estimate">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        <span>The upload takes about <strong>5 minutes</strong>. Results come back in <strong>1–2 business days</strong>.</span>
      </div>` : ''}

      <button class="btn-primary btn-large welcome-cta" onclick="navigateJourney(${ctaStep})">
        ${ctaLabel}
        ${ctaIcon}
      </button>

      ${myDocs.length > 0 ? `
      <div class="welcome-docs">
        <h3 class="welcome-docs-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          Shared Documents
        </h3>
        <div class="welcome-docs-list">
          ${myDocs.map(d => `
            <div class="welcome-doc-item">
              <div class="welcome-doc-info">
                <span class="welcome-doc-name">${esc(d.name)}</span>
                <span class="welcome-doc-meta">${esc(d.category)} · ${formatDate(d.created_at)}</span>
              </div>
              ${d.has_file ? `<button class="btn-secondary btn-sm" onclick="downloadDoc(${d.id})">Download</button>` : `<span class="text-muted" style="font-size:12px">No file</span>`}
            </div>
          `).join('')}
        </div>
      </div>` : ''}
    </div>`;
}


// ═══════════════════════════════════════════════════════════════════════════════
// STEP 2: Upload Your Data
// ═══════════════════════════════════════════════════════════════════════════════

async function renderJourneyUpload(el, client) {
  // If they already have data, redirect to review step
  if (client.shipping_data && client.shipping_data.data && client.shipping_data.data.length > 0) {
    // But if they explicitly navigated to upload, let them re-upload
    if (journeySubStep === 'reupload') {
      journeySubStep = 'a';
      renderUploadMethodChoice(el);
      return;
    }
    // Otherwise send them to review
    navigateJourney(3);
    return;
  }

  // Fresh upload — show method choice
  journeySubStep = 'a';
  renderUploadMethodChoice(el);
}

function renderUploadMethodChoice(el) {
  el.innerHTML = `
    <div class="content-area upload-journey-content">
      <div class="journey-back-row">
        <button class="btn-ghost journey-back-btn" onclick="navigateJourney(1)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          Back to Welcome
        </button>
      </div>
      <div class="upload-journey-header">
        <h2 class="journey-section-title">Upload Your Shipping Data</h2>
        <p class="journey-section-desc">Choose how you'd like to share your shipping history with us.</p>
      </div>

      <div class="upload-method-cards">
        <div class="method-card recommended" onclick="selectUploadMethod('template')">
          <div class="method-recommended-badge">Recommended</div>
          <div class="method-card-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          </div>
          <h3>Use Our Template</h3>
          <p>Download a pre-formatted CSV with 10 sample rows. Replace them with your data and upload it back.</p>
          <div class="method-card-preview">
            <code>16 columns · 10 sample shipments · UPS, FedEx, USPS</code>
          </div>
        </div>

        <div class="method-card" onclick="selectUploadMethod('own')">
          <div class="method-card-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          </div>
          <h3>Upload Your Own CSV</h3>
          <p>Already have shipping data? Upload any CSV with weight, origin/destination zips, and ship date. We'll help you map the columns.</p>
        </div>
      </div>
    </div>`;
}

function selectUploadMethod(method) {
  if (method === 'template') {
    downloadTemplate();
    showToast('Template downloaded with 10 sample rows. Replace them with your shipping data and upload.', 'success');
  }
  // Both methods proceed to configure step
  journeySubStep = 'b';
  const el = document.getElementById('journey-content-inner');
  renderUploadConfigure(el);
}

function renderUploadConfigure(el) {
  uploadedData = null; csvColumns = []; csvRows = []; uploadFileName = '';
  el.innerHTML = `
    <div class="content-area upload-journey-content">
      <div class="journey-back-row">
        <button class="btn-ghost journey-back-btn" onclick="navigateJourney(1)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          Back to Welcome
        </button>
      </div>
      <div class="upload-journey-header">
        <h2 class="journey-section-title">Configure Shipment Details</h2>
        <p class="journey-section-desc">Set up a few details before uploading your file.</p>
      </div>

      <!-- Origin Mode -->
      <div class="card upload-config-card">
        <div class="config-card-header">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          <h3>Ship-From Origin</h3>
        </div>
        <p class="config-card-desc">Where do your shipments originate?</p>
        <div class="origin-mode-toggle">
          <button type="button" class="origin-mode-btn active" data-mode="single" onclick="setOriginMode('single')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            <span class="origin-mode-label">Single Origin</span>
            <span class="origin-mode-desc">All shipments from one location</span>
          </button>
          <button type="button" class="origin-mode-btn" data-mode="multi" onclick="setOriginMode('multi')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="7" cy="10" r="2"/><circle cx="17" cy="10" r="2"/><circle cx="12" cy="17" r="2"/><path d="M7 10h10M12 10v7" opacity="0.4"/></svg>
            <span class="origin-mode-label">Multiple Origins</span>
            <span class="origin-mode-desc">Different warehouse locations</span>
          </button>
        </div>
        <div id="origin-single-fields">
          <div class="origin-single-intro">Enter your ship-from address. This applies to every row.</div>
          <div class="form-grid config-grid">
            <div class="form-field" id="origin-country-field"><label>Country</label>
              <select id="origin-default-country" onchange="onCountryChange()">
                <option value="US" selected>United States</option>
                <option value="CA">Canada</option>
                <option value="GB">United Kingdom</option>
                <option value="AU">Australia</option>
                <option value="MX">Mexico</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <div class="form-field ac-wrapper" id="origin-state-field"><label>State</label>
              <input id="origin-default-state" placeholder="Search state..." autocomplete="off"
                     onfocus="onStateInputFocus()" oninput="onStateInput(event)" onblur="hideStateDropdown()" data-code="">
              <div id="origin-state-dropdown" class="ac-dropdown hidden"></div>
            </div>
            <div class="form-field" id="origin-zip-field"><label>Zip Code</label>
              <input id="origin-default-zip" placeholder="e.g. 90210" autocomplete="off"
                     oninput="onZipInput(event)" onblur="validateZip()">
              <div id="zip-hint" class="field-hint"></div>
            </div>
          </div>
        </div>
        <div id="origin-multi-fields" class="hidden">
          <div class="upload-format-note origin-multi-note">
            <div class="format-note-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            </div>
            <div class="format-note-text">
              <strong>Your CSV must include origin data in every row.</strong><br>
              Each shipment row needs columns for <strong>Origin Zip/Postal</strong>, <strong>Origin State/Province</strong>, and <strong>Origin Country</strong>.
            </div>
          </div>
        </div>
      </div>

      <!-- Units -->
      <div class="card upload-config-card">
        <div class="config-card-header">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 20h20"/><path d="M2 20V4l4 4 4-4 4 4 4-4v16"/></svg>
          <h3>Units of Measurement</h3>
        </div>
        <div class="unit-system-picker">
          <button type="button" class="unit-system-card active" data-system="imperial" onclick="setUnitSystem('imperial')">
            <div class="usc-radio"><div class="usc-radio-dot"></div></div>
            <div class="usc-body">
              <div class="usc-title">Imperial</div>
              <div class="usc-specs">
                <span class="usc-spec"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18"/><path d="M8 7l4-4 4 4"/><path d="M8 17l4 4 4-4"/></svg>lbs</span>
                <span class="usc-dot-sep"></span>
                <span class="usc-spec"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18" opacity=".4"/><path d="M9 3v18" opacity=".4"/></svg>in</span>
              </div>
            </div>
          </button>
          <button type="button" class="unit-system-card" data-system="metric" onclick="setUnitSystem('metric')">
            <div class="usc-radio"><div class="usc-radio-dot"></div></div>
            <div class="usc-body">
              <div class="usc-title">Metric</div>
              <div class="usc-specs">
                <span class="usc-spec"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18"/><path d="M8 7l4-4 4 4"/><path d="M8 17l4 4 4-4"/></svg>kg</span>
                <span class="usc-dot-sep"></span>
                <span class="usc-spec"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18" opacity=".4"/><path d="M9 3v18" opacity=".4"/></svg>cm</span>
              </div>
            </div>
          </button>
        </div>
        <details class="unit-fine-tune">
          <summary class="unit-fine-tune-toggle">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            Fine-tune individual units
          </summary>
          <div class="unit-fine-tune-body">
            <div class="unit-ft-row">
              <span class="unit-ft-label">Weight</span>
              <div class="unit-toggle">
                <button type="button" class="unit-btn active" data-unit-group="weight" data-unit="lbs" onclick="setUnit(this)">lbs</button>
                <button type="button" class="unit-btn" data-unit-group="weight" data-unit="kg" onclick="setUnit(this)">kg</button>
              </div>
            </div>
            <div class="unit-ft-row">
              <span class="unit-ft-label">Dimensions</span>
              <div class="unit-toggle">
                <button type="button" class="unit-btn active" data-unit-group="dimensions" data-unit="in" onclick="setUnit(this)">in</button>
                <button type="button" class="unit-btn" data-unit-group="dimensions" data-unit="cm" onclick="setUnit(this)">cm</button>
              </div>
            </div>
          </div>
        </details>
      </div>

      <!-- Currency -->
      <div class="card upload-config-card">
        <div class="config-card-header">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
          <h3>Currency</h3>
        </div>
        <div class="unit-system-picker">
          <button type="button" class="unit-system-card active" data-currency="USD" onclick="setCurrency('USD')">
            <div class="usc-radio"><div class="usc-radio-dot"></div></div>
            <div class="usc-body">
              <div class="usc-title">USD</div>
              <div class="usc-specs"><span class="usc-spec"><strong>$</strong>&ensp;US Dollar</span></div>
            </div>
          </button>
          <button type="button" class="unit-system-card" data-currency="CAD" onclick="setCurrency('CAD')">
            <div class="usc-radio"><div class="usc-radio-dot"></div></div>
            <div class="usc-body">
              <div class="usc-title">CAD</div>
              <div class="usc-specs"><span class="usc-spec"><strong>C$</strong>&ensp;Canadian Dollar</span></div>
            </div>
          </button>
        </div>
      </div>

      <!-- Upload Zone -->
      <div class="upload-step-divider">
        <span>Now, drop your file below</span>
      </div>

      <div class="upload-zone" id="upload-zone"
           ondragover="event.preventDefault(); this.classList.add('dragover')"
           ondragleave="this.classList.remove('dragover')"
           ondrop="handleDrop(event)">
        <div class="upload-zone-inner">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-faint)" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          <p>Drag & drop your CSV file here</p>
          <span class="upload-or">or</span>
          <label class="btn-primary upload-btn">
            Choose File
            <input id="csv-file-input" type="file" accept=".csv,.tsv,.txt" onchange="handleFile(this.files[0])" hidden>
          </label>
        </div>
      </div>

      <div class="upload-format-note" style="margin-top:var(--space-4);">
        <div class="format-note-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        </div>
        <div class="format-note-text">
          <strong>Need the template?</strong>
          <button class="btn-ghost btn-sm" onclick="downloadTemplate()" style="text-decoration:underline;color:var(--color-primary);padding:0;">Download CSV Template</button>
          — or upload any CSV with shipping data. We'll help you map columns.
        </div>
      </div>

      <div id="upload-file-info" class="hidden"></div>
      <div id="upload-mapping" class="hidden"></div>
      <div id="upload-result" class="hidden"></div>
    </div>`;
}

// Upload confirm step (2d) — shown when data is already uploaded
function renderUploadConfirm(el, client) {
  const sd = client.shipping_data;
  const sm = sd.summary || {};
  const cur = sm.currency || 'USD';
  const data = sd.data || [];
  const profile = computeShippingProfile(data, sm);

  el.innerHTML = `
    <div class="content-area upload-journey-content">
      <div class="upload-journey-header">
        <div class="confirm-success-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        </div>
        <h2 class="journey-section-title">Data Uploaded Successfully!</h2>
        <p class="journey-section-desc">Here's a summary of what we received. Does this look right?</p>
      </div>

      <div class="confirm-summary">
        <div class="confirm-summary-grid">
          <div class="confirm-stat">
            <div class="confirm-stat-value">${sm.row_count || sd.row_count || data.length}</div>
            <div class="confirm-stat-label">Shipments</div>
          </div>
          ${sm.total_spend ? `<div class="confirm-stat">
            <div class="confirm-stat-value">${formatCurrency(sm.total_spend, cur)}</div>
            <div class="confirm-stat-label">Total Spend</div>
          </div>` : ''}
          ${sm.avg_weight ? `<div class="confirm-stat">
            <div class="confirm-stat-value">${sm.avg_weight} ${sm.weight_unit || 'lbs'}</div>
            <div class="confirm-stat-label">Avg Weight</div>
          </div>` : ''}
          ${sm.carriers ? `<div class="confirm-stat">
            <div class="confirm-stat-value">${sm.carriers.length}</div>
            <div class="confirm-stat-label">Carriers</div>
          </div>` : ''}
        </div>

        ${profile && profile.topCarriers.length > 0 ? `
        <div class="confirm-carriers">
          <div class="confirm-carriers-label">Carrier Mix</div>
          <div class="confirm-carrier-tags">
            ${profile.topCarriers.map(c => `<span class="confirm-carrier-tag">${esc(c.name)} <small>${c.pct}%</small></span>`).join('')}
          </div>
        </div>` : ''}

        <div class="confirm-preview">
          <div class="mapping-preview-title">Data Preview (first 5 rows)</div>
          <div class="table-container">
            <table class="data-table">
              <thead><tr><th>Date</th><th>Carrier</th><th>Service</th><th>Weight</th><th>Origin</th><th>Dest</th><th>Price</th></tr></thead>
              <tbody>${data.slice(0, 5).map(r => `<tr>
                <td>${esc(r.ship_date || '—')}</td>
                <td>${esc(r.carrier || '')}</td>
                <td>${esc(r.service || '')}</td>
                <td>${r.weight || '—'} lbs</td>
                <td>${esc(r.origin_zip || '')} ${esc(r.origin_state || '')}</td>
                <td>${esc(r.dest_zip || '')} ${esc(r.dest_state || '')}</td>
                <td>${formatCurrency(r.price || 0, cur)}</td>
              </tr>`).join('')}</tbody>
            </table>
          </div>
          ${data.length > 5 ? `<p class="preview-more">+ ${data.length - 5} more rows</p>` : ''}
        </div>
      </div>

      <div class="confirm-actions">
        <button class="btn-primary btn-large" onclick="confirmUploadAndProceed()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          Yes, This Looks Right — Continue
        </button>
        <button class="btn-secondary" onclick="reuploadData()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          Re-upload Different File
        </button>
      </div>
    </div>`;
}

function confirmUploadAndProceed() {
  // Show celebration animation
  showCelebration();
  setTimeout(() => {
    navigateJourney(3, {refresh: true});
  }, 1200);
}

function reuploadData() {
  openModal('Replace Shipping Data', `
    <div class="confirm-remove">
      <p>This will remove your current data and let you upload a new file. Any existing analysis will be cleared.</p>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn-danger" onclick="executeRemoveUpload()">Yes, Replace Data</button>
      </div>
    </div>`);
}

function showCelebration() {
  const existing = document.getElementById('celebration-overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'celebration-overlay';
  overlay.className = 'celebration';
  overlay.innerHTML = '<div class="celebration-inner">' +
    Array.from({length: 40}, (_, i) => {
      const colors = ['#01696f','#437a22','#da7101','#7a39bb','#006494','#d19900','#a13544'];
      const color = colors[i % colors.length];
      const left = Math.random() * 100;
      const delay = Math.random() * 0.5;
      const size = 4 + Math.random() * 8;
      return `<div class="confetti-piece" style="left:${left}%;animation-delay:${delay}s;background:${color};width:${size}px;height:${size * 1.5}px;"></div>`;
    }).join('') +
    '</div>';
  document.body.appendChild(overlay);
  setTimeout(() => overlay.remove(), 2500);
}


// ═══════════════════════════════════════════════════════════════════════════════
// STEP 3: Review & Confirm Data
// ═══════════════════════════════════════════════════════════════════════════════

async function renderJourneyReview(el, client) {
  const sd = client.shipping_data;
  if (!sd || !sd.data || sd.data.length === 0) {
    // No data yet — redirect to upload
    navigateJourney(2);
    return;
  }

  // If data is confirmed, show the "analyzing" waiting state
  if (isDataConfirmed(client)) {
    renderJourneyAnalyzingWait(el, client);
    return;
  }

  // Otherwise show the data review for confirmation
  const sm = sd.summary || {};
  const data = sd.data || [];
  const profile = computeShippingProfile(data, sm);
  const cur = profile ? profile.cur : 'USD';
  const wUnit = profile ? profile.wUnit : 'lbs';

  // Fetch documents for back-link context
  let myDocs = [];
  try {
    const allDocs = await api('/documents');
    const myDocIds = client.documents_json || [];
    myDocs = allDocs.filter(d => myDocIds.includes(d.id));
  } catch (e) {}

  el.innerHTML = `
    <div class="content-area review-journey-content">
      <div class="journey-back-row">
        <button class="btn-ghost journey-back-btn" onclick="navigateJourney(1)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          Back to Welcome
        </button>
        ${myDocs.length > 0 ? `
        <button class="btn-ghost journey-back-btn" onclick="navigateJourney(1)" title="View shared documents">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          View Documents
        </button>` : ''}
      </div>

      <div class="review-hero">
        <div class="review-hero-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        </div>
        <h2 class="journey-section-title">Your Data Is Ready for Review</h2>
        <p class="journey-section-desc">Take a look at the profile below. If everything looks correct, confirm it and we'll start the analysis.</p>
      </div>

      <!-- Volume Metrics -->
      ${profile ? `
      <div class="card review-volume-card">
        <div class="card-label">Shipping Volume Profile</div>
        <div class="review-volume-grid">
          <div class="review-vol-stat">
            <div class="review-vol-value">${profile.n.toLocaleString()}</div>
            <div class="review-vol-label">Total Shipments</div>
            <div class="review-vol-period">${profile.dateRangeStr}</div>
          </div>
          <div class="review-vol-stat">
            <div class="review-vol-value">${Math.round(profile.n / Math.max(1, profile.calendarDays)).toLocaleString()}</div>
            <div class="review-vol-label">Daily Average</div>
          </div>
          <div class="review-vol-stat">
            <div class="review-vol-value">${profile.weeklyShipments.toLocaleString()}</div>
            <div class="review-vol-label">Weekly Average</div>
          </div>
          <div class="review-vol-stat">
            <div class="review-vol-value">${profile.monthlyShipments.toLocaleString()}</div>
            <div class="review-vol-label">Monthly Average</div>
          </div>
          <div class="review-vol-stat">
            <div class="review-vol-value">${profile.annualShipments.toLocaleString()}</div>
            <div class="review-vol-label">Annual Projection</div>
          </div>
        </div>
      </div>

      <!-- Shipment Details -->
      <div class="card review-detail-card">
        <div class="card-label">Shipment Details</div>
        <div class="review-detail-grid">
          <div class="review-detail-stat">
            <div class="review-detail-label">Avg Weight</div>
            <div class="review-detail-value">${Number(profile.avgWeight).toFixed(1)} ${wUnit}</div>
          </div>
          <div class="review-detail-stat">
            <div class="review-detail-label">Avg Billed Weight</div>
            <div class="review-detail-value">${Number(profile.avgBilled).toFixed(1)} ${wUnit}</div>
          </div>
          ${profile.priceCount > 0 ? `
          <div class="review-detail-stat">
            <div class="review-detail-label">Total Spend</div>
            <div class="review-detail-value">${formatCurrency(profile.totalPrice, cur)}</div>
          </div>
          <div class="review-detail-stat">
            <div class="review-detail-label">Avg Cost / Shipment</div>
            <div class="review-detail-value">${formatCurrency(profile.avgPrice, cur)}</div>
          </div>
          <div class="review-detail-stat">
            <div class="review-detail-label">${profile.costPerUnitLabel}</div>
            <div class="review-detail-value">${formatCurrency(profile.costPerUnit, cur)}</div>
          </div>
          <div class="review-detail-stat">
            <div class="review-detail-label">Monthly Spend (est.)</div>
            <div class="review-detail-value">${formatCurrency(profile.monthlySpend, cur)}</div>
          </div>
          <div class="review-detail-stat">
            <div class="review-detail-label">Annual Spend (est.)</div>
            <div class="review-detail-value">${formatCurrency(profile.annualSpend, cur)}</div>
          </div>` : ''}
          ${profile.cubicCount > 0 ? `
          <div class="review-detail-stat">
            <div class="review-detail-label">Avg Volume</div>
            <div class="review-detail-value">${profile.avgCubicDisplay.toFixed(2)} ${profile.cubicLabel}</div>
          </div>` : ''}
        </div>
      </div>

      <!-- Carrier & Service Mix -->
      <div class="review-mix-row">
        ${profile.topCarriers.length > 0 ? `
        <div class="card review-mix-card">
          <div class="card-label">Carrier Mix</div>
          <div class="review-mix-list">
            ${profile.topCarriers.map(c => `
              <div class="review-mix-item">
                <div class="review-mix-name">${esc(c.name)}</div>
                <div class="review-mix-bar-wrap">
                  <div class="review-mix-bar" style="width:${c.pct}%"></div>
                </div>
                <div class="review-mix-pct">${c.pct}%</div>
                <div class="review-mix-count">${c.count.toLocaleString()}</div>
              </div>
            `).join('')}
          </div>
        </div>` : ''}
        ${profile.topServices.length > 0 ? `
        <div class="card review-mix-card">
          <div class="card-label">Service Mix</div>
          <div class="review-mix-list">
            ${profile.topServices.map(s => `
              <div class="review-mix-item">
                <div class="review-mix-name">${esc(s.name)}</div>
                <div class="review-mix-bar-wrap">
                  <div class="review-mix-bar" style="width:${s.pct}%"></div>
                </div>
                <div class="review-mix-pct">${s.pct}%</div>
                <div class="review-mix-count">${s.count.toLocaleString()}</div>
              </div>
            `).join('')}
          </div>
        </div>` : ''}
      </div>` : ''}

      <!-- Data Preview -->
      <div class="card">
        <div class="card-label">Data Preview (first 5 rows)</div>
        <div class="table-container">
          <table class="data-table compact">
            <thead><tr><th>Date</th><th>Carrier</th><th>Service</th><th>Weight</th><th>Origin</th><th>Dest</th><th>Price</th></tr></thead>
            <tbody>${data.slice(0, 5).map(r => `<tr>
              <td>${esc(r.ship_date || '\u2014')}</td>
              <td>${esc(r.carrier || '')}</td>
              <td>${esc(r.service || '')}</td>
              <td>${r.weight || '\u2014'} ${wUnit}</td>
              <td>${esc(r.origin_zip || '')} ${esc(r.origin_state || '')}</td>
              <td>${esc(r.dest_zip || '')} ${esc(r.dest_state || '')}</td>
              <td>${formatCurrency(r.price || 0, cur)}</td>
            </tr>`).join('')}</tbody>
          </table>
        </div>
        ${data.length > 5 ? `<p class="preview-more">+ ${(data.length - 5).toLocaleString()} more rows</p>` : ''}
      </div>

      <!-- Confirm Actions -->
      <div class="review-confirm-section">
        <div class="review-confirm-question">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <span>Does this data look correct? Once you confirm, our team will begin analyzing it.</span>
        </div>
        <div class="review-confirm-actions">
          <button class="btn-primary btn-large" id="confirm-data-btn" onclick="confirmAndSubmitData()">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            Confirm Data & Submit to Analyst
          </button>
          <button class="btn-secondary" onclick="goReupload()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            Re-upload Different File
          </button>
        </div>
      </div>
    </div>`;
}

function goReupload() {
  openModal('Replace Shipping Data', `
    <div class="confirm-remove">
      <p>This will remove your current data and let you upload a new file.</p>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn-danger" onclick="executeRemoveUpload()">Yes, Replace Data</button>
      </div>
    </div>`);
}

async function confirmAndSubmitData() {
  const btn = document.getElementById('confirm-data-btn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-sm"></span> Confirming...';
  }
  try {
    await api(`/clients/${state.userId}/confirm-data`, { method: 'POST', body: {} });
    showCelebration();
    showToast('Data confirmed! Our team will begin your analysis.', 'success');
    // Refresh to show the analyzing wait state
    setTimeout(() => {
      loadJourney('');
    }, 1500);
  } catch (e) {
    showToast('Failed to confirm: ' + e.message, 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Confirm Data & Submit to Analyst';
    }
  }
}

// Analyzing wait state (shown after confirmation)
function renderJourneyAnalyzingWait(el, client) {
  const sd = client.shipping_data;
  const rowCount = sd?.data?.length || sd?.row_count || 0;
  const contactEmail = state.userEmail || '';
  const sm = sd?.summary || {};
  const profile = sd?.data ? computeShippingProfile(sd.data, sm) : null;

  el.innerHTML = `
    <div class="content-area analyzing-journey-content">
      <div class="journey-back-row">
        <button class="btn-ghost journey-back-btn" onclick="navigateJourney(1)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          Back to Welcome
        </button>
      </div>

      <div class="analyzing-hero">
        <div class="analyzing-hero-icon">
          <div class="analyzing-pulse-ring"></div>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="1.5">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </div>
        <h2 class="analyzing-title">We're on it! \ud83d\udd0d</h2>
        <p class="analyzing-desc">Our team is analyzing your <strong>${rowCount.toLocaleString()}</strong> shipments against our carrier network. You'll hear back within <strong>1\u20132 business days</strong>.</p>
      </div>

      <div class="analyzing-visual card">
        <div class="analyzing-visual-header">What's happening now</div>
        <div class="analyzing-visual-steps">
          <div class="av-step">
            <div class="av-step-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></div>
            <div class="av-step-text">Reading your shipment data</div>
            <div class="av-step-check">\u2713</div>
          </div>
          <div class="av-step active">
            <div class="av-step-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>
            <div class="av-step-text">Rating against <strong>145+ carrier rate cards</strong> across <strong>9 carriers</strong></div>
            <div class="av-step-spinner"></div>
          </div>
          <div class="av-step upcoming">
            <div class="av-step-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg></div>
            <div class="av-step-text">Building your savings report</div>
          </div>
        </div>
      </div>

      ${contactEmail ? `
      <div class="analyzing-notify card">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
        <span>We'll notify you at <strong>${esc(contactEmail)}</strong> when results are ready.</span>
      </div>` : ''}

      ${profile ? `
      <details class="analyzing-data-summary">
        <summary class="analyzing-data-toggle">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          Your confirmed data summary
        </summary>
        <div class="analyzing-data-content card">
          <div class="sp-kpi-grid compact">
            <div class="sp-kpi"><div class="sp-kpi-label">Shipments</div><div class="sp-kpi-value">${profile.n.toLocaleString()}</div></div>
            <div class="sp-kpi"><div class="sp-kpi-label">Avg Weight</div><div class="sp-kpi-value">${Number(profile.avgWeight).toFixed(1)} <span class="sp-kpi-unit">${profile.wUnit}</span></div></div>
            ${profile.priceCount > 0 ? `<div class="sp-kpi"><div class="sp-kpi-label">Total Spend</div><div class="sp-kpi-value">${formatCurrency(profile.totalPrice, profile.cur)}</div></div>` : ''}
            ${profile.priceCount > 0 ? `<div class="sp-kpi"><div class="sp-kpi-label">Avg Cost/Pkg</div><div class="sp-kpi-value">${formatCurrency(profile.avgPrice, profile.cur)}</div></div>` : ''}
          </div>
          ${profile.topCarriers.length > 0 ? `
          <div class="confirm-carriers" style="margin-top:var(--space-3);">
            <div class="confirm-carriers-label">Carriers</div>
            <div class="confirm-carrier-tags">
              ${profile.topCarriers.map(c => `<span class="confirm-carrier-tag">${esc(c.name)} <small>${c.pct}%</small></span>`).join('')}
            </div>
          </div>` : ''}
        </div>
      </details>` : ''}

      <div class="analyzing-reupload-section">
        <button class="btn-ghost" onclick="startNewUpload()" style="font-size:var(--text-xs);color:var(--color-text-muted);">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          Changed your mind? Upload different data
        </button>
      </div>
    </div>`;
}


// ═══════════════════════════════════════════════════════════════════════════════
// STEP 4: Your Results
// ═══════════════════════════════════════════════════════════════════════════════

let analysisCharts = [];

async function renderJourneyResults(el, client) {
  // Destroy existing charts
  analysisCharts.forEach(c => c.destroy());
  analysisCharts = [];

  if (!client.analysis || client.analysis.status !== 'published') {
    // Not ready yet — show analyzing state
    renderJourneyAnalyzingWait(el, client);
    return;
  }

  const r = client.analysis.results;
  const sm = r.summary;
  const cur = r.currency || 'USD';
  const byService = r.by_service;
  const byCarrier = r.by_carrier || {};
  const byZone = r.by_zone || {};
  const zones = Object.keys(byZone).sort((a, b) => parseInt(a) - parseInt(b));
  const carriers = Object.keys(byCarrier).sort((a, b) => (byCarrier[b].original || 0) - (byCarrier[a].original || 0));

  const clientShipDates = (r.shipments || []).map(sh => sh.ship_date).filter(Boolean).sort();
  const clientDateRange = clientShipDates.length > 1
    ? clientShipDates[0] + ' to ' + clientShipDates[clientShipDates.length - 1]
    : clientShipDates.length === 1 ? clientShipDates[0] : '';

  // Compute annualization factor using 250 business days/year
  let annualFactor = 12; // fallback
  if (clientShipDates.length > 1) {
    const firstDate = new Date(clientShipDates[0]);
    const lastDate  = new Date(clientShipDates[clientShipDates.length - 1]);
    const calDays = Math.max(1, Math.round((lastDate - firstDate) / 86400000) + 1);
    const bizDaysInRange = Math.round(calDays * 5 / 7);
    annualFactor = bizDaysInRange > 0 ? 250 / bizDaysInRange : 12;
  }
  const annualSavings = sm.total_savings * annualFactor;
  const annualLabel = clientShipDates.length > 1
    ? `Based on ${sm.shipment_count} shipments over ${clientDateRange}, annualized to 250 business days`
    : `Based on ${sm.shipment_count} shipments \u00d7 12 months`;

  el.innerHTML = `
    <div class="content-area results-journey-content">
      <!-- Celebration header -->
      <div class="results-celebration-header">
        <div class="results-celebration-icon">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        </div>
        <h2 class="results-title">Great news! We found savings for you. 🎉</h2>
        <p class="results-subtitle">Here's your personalized shipping savings analysis.</p>
        <div class="analysis-freshness">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
  Analysis generated ${formatDate(client.analysis.created_at)}${client.analysis.published_at ? ' · Published ' + formatDate(client.analysis.published_at) : ''}
</div>
      </div>

      <!-- Key Insights -->
      ${sm.total_savings > 0 ? `
      <div class="card insights-card">
        <div class="insights-card-header">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          <div class="card-label" style="margin-bottom:0;">Key Insights</div>
        </div>
        <div class="insights-list">
          <div class="insight-item">
            <span class="insight-bullet">&#10003;</span>
            Based on your shipping profile of <strong>${sm.shipment_count}</strong> shipments, Broad Reach can save you an estimated <strong>${formatCurrency(annualSavings, cur)}</strong> annually.
          </div>
          ${(() => {
            const topZone = Object.entries(byZone).sort((a,b) => (b[1].savings_pct||0) - (a[1].savings_pct||0))[0];
            return topZone && topZone[1].savings_pct > 0 ? `<div class="insight-item"><span class="insight-bullet">&#10003;</span>Your highest savings opportunity is in <strong>Zone ${topZone[0]}</strong> shipments where we save <strong>${topZone[1].savings_pct}%</strong> on average.</div>` : '';
          })()}
          <div class="insight-item">
            <span class="insight-bullet">&#10003;</span>
            <strong>${Math.round((sm.shipments_with_savings / sm.shipment_count) * 100)}%</strong> of your shipments would see cost reduction with Broad Reach.
          </div>
        </div>
        <div class="insight-annual">
          <div class="insight-annual-label">Projected Annual Savings</div>
          <div class="insight-annual-value">${formatCurrency(annualSavings, cur)}</div>
          <div class="insight-annual-sub">${annualLabel}</div>
        </div>
      </div>` : ''}

      <!-- Executive Summary -->
      <div class="exec-summary card">
        <div class="card-label">Executive Summary</div>
        <div class="exec-grid-enhanced">
          <div class="exec-card">
            <div class="exec-card-label">Current Spend</div>
            <div class="exec-card-value">${formatCurrency(sm.total_original, cur)}</div>
            <div class="exec-card-sub">${sm.shipment_count} shipments${clientDateRange ? ' · ' + clientDateRange : ''}</div>
          </div>
          <div class="exec-card accent">
            <div class="exec-card-label">Broad Reach Price</div>
            <div class="exec-card-value">${formatCurrency(sm.total_br, cur)}</div>
            <div class="exec-card-sub">Avg ${formatCurrency(sm.avg_br || (sm.total_br / sm.shipment_count), cur)}/shipment</div>
          </div>
          <div class="exec-card ${sm.total_savings > 0 ? 'savings' : ''}">
            <div class="exec-card-label">Total Savings</div>
            <div class="exec-card-value">${formatCurrency(sm.total_savings, cur)}</div>
            <div class="exec-card-sub">${sm.savings_pct}% reduction</div>
          </div>
          <div class="exec-card">
            <div class="exec-card-label">Coverage</div>
            <div class="exec-card-value">${sm.shipments_with_savings}/${sm.shipment_count}</div>
            <div class="exec-card-sub">shipments with savings</div>
          </div>
        </div>
      </div>

      ${zones.length > 0 ? `
      <div class="card">
        <div class="card-label">Savings by Zone</div>
        <div class="table-container">
          <table class="data-table compact">
            <thead><tr><th>Zone</th><th class="num">Parcels</th><th class="num">Distrib.</th><th class="num">Avg Current</th><th class="num">Avg BR</th><th class="num">Savings</th><th class="num">Savings %</th></tr></thead>
            <tbody>
              ${zones.map(z => {
                const zb = byZone[z];
                return '<tr><td class="fw-500">Zone ' + z + '</td><td class="num">' + zb.count + '</td><td class="num">' + zb.distribution + '%</td><td class="num">' + formatCurrency(zb.avg_original, cur) + '</td><td class="num">' + formatCurrency(zb.avg_br, cur) + '</td><td class="num ' + (zb.savings > 0 ? 'text-success' : '') + '">' + formatCurrency(zb.savings, cur) + '</td><td class="num ' + (zb.savings_pct > 0 ? 'text-success' : '') + '">' + zb.savings_pct + '%</td></tr>';
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>` : ''}

      <div class="charts-row">
        <div class="card chart-card">
          <div class="card-label">Spend by Service Level</div>
          <canvas id="chart-service" height="260"></canvas>
        </div>
        <div class="card chart-card">
          <div class="card-label">Savings by Carrier</div>
          <canvas id="chart-carrier" height="260"></canvas>
        </div>
      </div>

      <div class="card">
        <div class="card-header-row">
          <div class="card-label">Detailed Comparison</div>
          <button class="btn-secondary btn-sm" onclick="${state.userType === 'client' ? 'downloadAnalysisExcel' : 'downloadAnalysisCSV'}()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            ${state.userType === 'client' ? 'Download Excel' : 'Download CSV'}
          </button>
        </div>
        <div class="table-container">
          <table class="data-table analysis-table">
            <thead>
              <tr>
                <th>Date</th><th>Carrier</th><th>Service</th><th>Actual Wt</th><th>Billed Wt</th><th>Zone</th>
                <th>Origin</th><th>Dest</th><th>Original</th>
                <th>BR Service</th><th>BR Price</th><th>Savings</th>
              </tr>
            </thead>
            <tbody>
              ${r.shipments.map(s => `
                <tr class="${s.savings > 0 ? 'row-savings' : ''}">
                  <td>${esc(s.ship_date || '—')}</td>
                  <td>${esc(s.carrier)}</td>
                  <td>${esc(s.service)}</td>
                  <td class="num">${s.weight} lbs</td>
                  <td class="num">${s.billable_weight || s.billed_weight || s.weight} lbs</td>
                  <td class="num">${s.zone}</td>
                  <td>${esc(s.origin_state)}</td>
                  <td>${esc(s.dest_state)}</td>
                  <td class="num">${formatCurrency(s.price, cur)}</td>
                  <td class="${s.savings > 0 ? 'text-accent' : 'text-muted'}">${esc(s.br_service)}</td>
                  <td class="num">${formatCurrency(s.br_price, cur)}</td>
                  <td class="num ${s.savings > 0 ? 'text-success fw-500' : 'text-muted'}">${s.savings > 0 ? formatCurrency(s.savings, cur) : '—'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Download Data Kit Section -->
      <div class="card download-kit-card">
        <div class="download-kit-header">
          <div class="download-kit-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </div>
          <div>
            <div class="download-kit-title">Download Your Complete Analysis</div>
            <div class="download-kit-desc">Your full analysis in a polished Excel workbook — ready to share with your team.</div>
          </div>
        </div>
        <div class="download-kit-features">
          <div class="download-kit-feature">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Executive summary with KPIs and savings breakdown</span>
          </div>
          <div class="download-kit-feature">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Shipment-by-shipment comparison — current vs. best price</span>
          </div>
          <div class="download-kit-feature">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Separate rate card tabs for every service we priced</span>
          </div>
          <div class="download-kit-feature">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Side-by-side all-services price matrix</span>
          </div>
          <div class="download-kit-feature">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Your original pricing vs. our pricing — see exactly what changes</span>
          </div>
        </div>
        <button class="btn-download-kit" onclick="downloadAnalysisExcel()">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download Full Analysis (Excel)
        </button>
        ${state.userType !== 'client' ? `
        <button class="btn-secondary btn-sm" style="margin-top:8px;width:100%;" onclick="downloadAnalysisCSV()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download CSV
        </button>` : ''}

      </div>

      <div class="card contact-card">
        <div class="contact-card-inner">
          <div>
            <div class="card-label">Questions?</div>
            <p style="font-size:var(--text-sm);color:var(--color-text-muted);margin:0;">Our team is ready to walk you through the analysis and answer any questions.</p>
          </div>
          <a href="mailto:contact@broadreach.com" class="btn-primary" style="white-space:nowrap;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
            Contact Us
          </a>
        </div>
      </div>

      <!-- Re-analyze with new data -->
      <div class="card reanalyze-card">
        <div class="reanalyze-card-inner">
          <div class="reanalyze-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          </div>
          <div>
            <div class="card-label" style="margin-bottom:4px;">Have newer shipping data?</div>
            <p style="font-size:var(--text-sm);color:var(--color-text-muted);margin:0;">Upload a fresh dataset and we'll run a new analysis. Your current results will remain available until the new analysis is published.</p>
          </div>
        </div>
        <button class="btn-secondary full-width" style="margin-top:var(--space-3);" onclick="startNewUpload()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          Upload New Data for Re-analysis
        </button>
      </div>
    </div>`;

  // Render charts
  setTimeout(() => renderAnalysisCharts(byService, byCarrier, cur), 100);
}


// ═══════════════════════════════════════════════════════════════════════════════
// PRESERVED FUNCTIONS — All existing client functionality
// ═══════════════════════════════════════════════════════════════════════════════

// ─── Client Notification Banner ───────────────────────────────────────────────
async function checkClientNotifications(currentTab) {
  try {
    const data = await api(`/clients/${state.userId}/notifications`);
    const unread = (data.notifications || []).filter(n => !n.read && n.type === 'analysis_ready');
    if (unread.length === 0) return;
    // If analysis is ready, auto-redirect to step 4
    if (journeyStep !== 4) {
      navigateJourney(4);
    }
  } catch (e) {}
}

async function dismissClientBanner() {
  const banner = document.getElementById('client-notif-banner');
  if (banner) banner.remove();
  try {
    await api(`/clients/${state.userId}/notifications/read`, { method: 'POST', body: {} });
  } catch (e) {}
}

// ─── Client Documents (now embedded in Welcome) ──────────────────────────────
async function renderClientDocuments(el) {
  // Redirects to welcome
  navigateJourney(1);
}

// ─── Client Upload (wrapper for journey) ─────────────────────────────────────
async function renderClientUpload(el) {
  navigateJourney(2);
}

// ─── Existing Upload wrapper ─────────────────────────────────────────────────
function renderExistingUpload(el, sd) {
  // This is now handled by renderUploadConfirm in the journey flow
  const client = window._clientData || { shipping_data: sd };
  renderUploadConfirm(el, client);
}

function renderFreshUpload(el) {
  renderUploadConfigure(el);
}

function confirmRemoveUpload() {
  openModal('Remove Shipping Data', `
    <div class="confirm-remove">
      <p>Are you sure you want to remove your uploaded shipping data? This will also clear any existing savings analysis.</p>
      <p class="confirm-remove-note">You can upload a new file immediately after.</p>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn-danger" onclick="executeRemoveUpload()">Yes, Remove Data</button>
      </div>
    </div>`);
}

async function executeRemoveUpload() {
  try {
    await api(`/clients/${state.userId}/shipping-data`, { method: 'DELETE' });
    closeModal();
    showToast('Shipping data removed. You can now upload a new file.', 'info');
    navigateJourney(2, {refresh: true});
  } catch(e) {
    showToast(e.message, 'error');
  }
}

// ─── Re-upload / Re-analysis Flow ──────────────────────────────────────────
// Called from Step 4 Results card and Analyzing Wait "Changed your mind?" link
function startNewUpload() {
  openModal('Upload New Shipping Data', `
    <div class="confirm-remove">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
        <div style="width:44px;height:44px;border-radius:50%;background:var(--color-primary-light,#e0f2fe);display:flex;align-items:center;justify-content:center;flex-shrink:0;">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        </div>
        <div>
          <p style="margin:0;font-weight:600;">Ready for a fresh analysis?</p>
          <p style="margin:4px 0 0;font-size:var(--text-sm);color:var(--color-text-muted);">This will clear your current data and analysis so you can upload a new shipping file.</p>
        </div>
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn-primary" onclick="executeNewUpload()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          Start Fresh Upload
        </button>
      </div>
    </div>`);
}

async function executeNewUpload() {
  try {
    await api(`/clients/${state.userId}/shipping-data`, { method: 'DELETE' });
    closeModal();
    // Reset local cached data
    window._clientData = null;
    uploadedData = null;
    csvColumns = [];
    csvRows = [];
    uploadFileName = '';
    showToast('Starting fresh — upload your new shipping data below.', 'success');
    navigateJourney(2, {refresh: true});
  } catch(e) {
    closeModal();
    showToast('Failed to reset: ' + e.message, 'error');
  }
}

// ─── Geo Data: States/Provinces + Zip/Postal Prefixes ────────────────────────
const GEO_DATA = {
  US: {
    label: 'State', zipLabel: 'Zip Code', zipPlaceholder: 'e.g. 90210',
    zipPattern: /^\d{5}(-\d{4})?$/, zipMask: '#####',
    regions: [
      {code:'AL',name:'Alabama',zips:['35','36']},{code:'AK',name:'Alaska',zips:['99']},
      {code:'AZ',name:'Arizona',zips:['85','86']},{code:'AR',name:'Arkansas',zips:['71','72']},
      {code:'CA',name:'California',zips:['90','91','92','93','94','95','96']},
      {code:'CO',name:'Colorado',zips:['80','81']},{code:'CT',name:'Connecticut',zips:['06']},
      {code:'DE',name:'Delaware',zips:['19']},{code:'FL',name:'Florida',zips:['32','33','34']},
      {code:'GA',name:'Georgia',zips:['30','31','39']},{code:'HI',name:'Hawaii',zips:['96']},
      {code:'ID',name:'Idaho',zips:['83']},{code:'IL',name:'Illinois',zips:['60','61','62']},
      {code:'IN',name:'Indiana',zips:['46','47']},{code:'IA',name:'Iowa',zips:['50','51','52']},
      {code:'KS',name:'Kansas',zips:['66','67']},{code:'KY',name:'Kentucky',zips:['40','41','42']},
      {code:'LA',name:'Louisiana',zips:['70','71']},{code:'ME',name:'Maine',zips:['03','04']},
      {code:'MD',name:'Maryland',zips:['20','21']},{code:'MA',name:'Massachusetts',zips:['01','02']},
      {code:'MI',name:'Michigan',zips:['48','49']},{code:'MN',name:'Minnesota',zips:['55','56']},
      {code:'MS',name:'Mississippi',zips:['38','39']},{code:'MO',name:'Missouri',zips:['63','64','65']},
      {code:'MT',name:'Montana',zips:['59']},{code:'NE',name:'Nebraska',zips:['68','69']},
      {code:'NV',name:'Nevada',zips:['88','89']},{code:'NH',name:'New Hampshire',zips:['03']},
      {code:'NJ',name:'New Jersey',zips:['07','08']},{code:'NM',name:'New Mexico',zips:['87','88']},
      {code:'NY',name:'New York',zips:['10','11','12','13','14']},
      {code:'NC',name:'North Carolina',zips:['27','28']},{code:'ND',name:'North Dakota',zips:['58']},
      {code:'OH',name:'Ohio',zips:['43','44','45']},{code:'OK',name:'Oklahoma',zips:['73','74']},
      {code:'OR',name:'Oregon',zips:['97']},{code:'PA',name:'Pennsylvania',zips:['15','16','17','18','19']},
      {code:'RI',name:'Rhode Island',zips:['02']},{code:'SC',name:'South Carolina',zips:['29']},
      {code:'SD',name:'South Dakota',zips:['57']},{code:'TN',name:'Tennessee',zips:['37','38']},
      {code:'TX',name:'Texas',zips:['73','75','76','77','78','79']},
      {code:'UT',name:'Utah',zips:['84']},{code:'VT',name:'Vermont',zips:['05']},
      {code:'VA',name:'Virginia',zips:['20','22','23','24']},{code:'WA',name:'Washington',zips:['98','99']},
      {code:'WV',name:'West Virginia',zips:['24','25','26']},{code:'WI',name:'Wisconsin',zips:['53','54']},
      {code:'WY',name:'Wyoming',zips:['82','83']},{code:'DC',name:'District of Columbia',zips:['20']}
    ]
  },
  CA: {
    label: 'Province', zipLabel: 'Postal Code', zipPlaceholder: 'e.g. M5V 2T6',
    zipPattern: /^[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d$/, zipMask: 'A#A #A#',
    regions: [
      {code:'AB',name:'Alberta',zips:['T']},{code:'BC',name:'British Columbia',zips:['V']},
      {code:'MB',name:'Manitoba',zips:['R']},{code:'NB',name:'New Brunswick',zips:['E']},
      {code:'NL',name:'Newfoundland and Labrador',zips:['A']},{code:'NS',name:'Nova Scotia',zips:['B']},
      {code:'NT',name:'Northwest Territories',zips:['X']},{code:'NU',name:'Nunavut',zips:['X']},
      {code:'ON',name:'Ontario',zips:['K','L','M','N','P']},{code:'PE',name:'Prince Edward Island',zips:['C']},
      {code:'QC',name:'Quebec',zips:['G','H','J']},{code:'SK',name:'Saskatchewan',zips:['S']},
      {code:'YT',name:'Yukon',zips:['Y']}
    ]
  },
  GB: {
    label: 'Region', zipLabel: 'Postcode', zipPlaceholder: 'e.g. SW1A 1AA',
    zipPattern: /^[A-Za-z]{1,2}\d[A-Za-z\d]?\s?\d[A-Za-z]{2}$/, zipMask: '',
    regions: [
      {code:'ENG',name:'England',zips:[]},{code:'SCT',name:'Scotland',zips:[]},
      {code:'WLS',name:'Wales',zips:[]},{code:'NIR',name:'Northern Ireland',zips:[]}
    ]
  },
  AU: {
    label: 'State', zipLabel: 'Postcode', zipPlaceholder: 'e.g. 2000',
    zipPattern: /^\d{4}$/, zipMask: '####',
    regions: [
      {code:'NSW',name:'New South Wales',zips:['2']},{code:'VIC',name:'Victoria',zips:['3']},
      {code:'QLD',name:'Queensland',zips:['4']},{code:'SA',name:'South Australia',zips:['5']},
      {code:'WA',name:'Western Australia',zips:['6']},{code:'TAS',name:'Tasmania',zips:['7']},
      {code:'NT',name:'Northern Territory',zips:['0']},{code:'ACT',name:'Australian Capital Territory',zips:['2']}
    ]
  },
  MX: {
    label: 'State', zipLabel: 'Código Postal', zipPlaceholder: 'e.g. 06600',
    zipPattern: /^\d{5}$/, zipMask: '#####',
    regions: [
      {code:'AGU',name:'Aguascalientes',zips:['20']},{code:'BCN',name:'Baja California',zips:['21','22']},
      {code:'BCS',name:'Baja California Sur',zips:['23']},{code:'CAM',name:'Campeche',zips:['24']},
      {code:'CHP',name:'Chiapas',zips:['29','30']},{code:'CHH',name:'Chihuahua',zips:['31','32','33']},
      {code:'COA',name:'Coahuila',zips:['25','26','27']},{code:'COL',name:'Colima',zips:['28']},
      {code:'CMX',name:'Ciudad de México',zips:['01','02','03','04','05','06','07','08','09','10','11','12','13','14','15','16']},
      {code:'DUR',name:'Durango',zips:['34','35']},{code:'GUA',name:'Guanajuato',zips:['36','37','38']},
      {code:'GRO',name:'Guerrero',zips:['39','40','41']},{code:'HID',name:'Hidalgo',zips:['42','43']},
      {code:'JAL',name:'Jalisco',zips:['44','45','46','47','48','49']},
      {code:'MEX',name:'Estado de México',zips:['50','51','52','53','54','55','56']},
      {code:'MIC',name:'Michoacán',zips:['58','59','60','61']},{code:'MOR',name:'Morelos',zips:['62']},
      {code:'NAY',name:'Nayarit',zips:['63']},{code:'NLE',name:'Nuevo León',zips:['64','65','66','67']},
      {code:'OAX',name:'Oaxaca',zips:['68','69','70','71']},{code:'PUE',name:'Puebla',zips:['72','73','74','75']},
      {code:'QUE',name:'Querétaro',zips:['76']},{code:'ROO',name:'Quintana Roo',zips:['77']},
      {code:'SLP',name:'San Luis Potosí',zips:['78','79']},{code:'SIN',name:'Sinaloa',zips:['80','81','82']},
      {code:'SON',name:'Sonora',zips:['83','84','85']},{code:'TAB',name:'Tabasco',zips:['86']},
      {code:'TAM',name:'Tamaulipas',zips:['87','88','89']},{code:'TLA',name:'Tlaxcala',zips:['90']},
      {code:'VER',name:'Veracruz',zips:['91','92','93','94','95','96']},
      {code:'YUC',name:'Yucatán',zips:['97']},{code:'ZAC',name:'Zacatecas',zips:['98','99']}
    ]
  }
};

function getGeo(country) {
  return GEO_DATA[country] || { label: 'State/Province', zipLabel: 'Zip/Postal', zipPlaceholder: '', zipPattern: null, zipMask: '', regions: [] };
}

// ─── Smart Origin Selector ───────────────────────────────────────────────────
function initOriginSelectors() {
  const countryEl = document.getElementById('origin-default-country');
  if (!countryEl) return;
  countryEl.addEventListener('change', () => onCountryChange());
  onCountryChange();
}

function onCountryChange() {
  const country = document.getElementById('origin-default-country').value;
  const geo = getGeo(country);
  const stateLabel = document.querySelector('#origin-state-field > label');
  if (stateLabel) stateLabel.textContent = geo.label;
  const stateInput = document.getElementById('origin-default-state');
  const stateDropdown = document.getElementById('origin-state-dropdown');
  if (stateInput) {
    stateInput.value = '';
    stateInput.placeholder = geo.regions.length ? `Search ${geo.label.toLowerCase()}...` : `Enter ${geo.label.toLowerCase()}`;
    stateInput.dataset.code = '';
  }
  const zipLabel = document.querySelector('#origin-zip-field > label');
  if (zipLabel) zipLabel.textContent = geo.zipLabel;
  const zipInput = document.getElementById('origin-default-zip');
  if (zipInput) { zipInput.value = ''; zipInput.placeholder = geo.zipPlaceholder; }
  const zipHint = document.getElementById('zip-hint');
  if (zipHint) { zipHint.textContent = ''; zipHint.className = 'field-hint'; }
}

function onStateInputFocus() { showStateDropdown(''); }
function onStateInput(e) { showStateDropdown(e.target.value); }

function showStateDropdown(query) {
  const country = document.getElementById('origin-default-country').value;
  const geo = getGeo(country);
  const dd = document.getElementById('origin-state-dropdown');
  if (!dd || !geo.regions.length) { if (dd) dd.classList.add('hidden'); return; }
  const q = query.toLowerCase();
  const matches = geo.regions.filter(r => r.name.toLowerCase().includes(q) || r.code.toLowerCase().includes(q));
  if (matches.length === 0) {
    dd.innerHTML = '<div class="ac-empty">No matches</div>';
  } else {
    dd.innerHTML = matches.map(r =>
      `<div class="ac-item" onmousedown="selectState('${r.code}','${esc(r.name)}')">
        <span class="ac-code">${esc(r.code)}</span><span class="ac-name">${esc(r.name)}</span>
      </div>`
    ).join('');
  }
  dd.classList.remove('hidden');
}

function hideStateDropdown() {
  setTimeout(() => { const dd = document.getElementById('origin-state-dropdown'); if (dd) dd.classList.add('hidden'); }, 150);
}

function selectState(code, name) {
  const input = document.getElementById('origin-default-state');
  if (input) { input.value = `${code} — ${name}`; input.dataset.code = code; }
  const dd = document.getElementById('origin-state-dropdown'); if (dd) dd.classList.add('hidden');
  const zipInput = document.getElementById('origin-default-zip'); if (zipInput) zipInput.value = '';
  validateZip();
}

function onZipInput(e) {
  const country = document.getElementById('origin-default-country').value;
  if (country === 'CA') {
    let v = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (v.length > 3) v = v.slice(0, 3) + ' ' + v.slice(3);
    if (v.length > 7) v = v.slice(0, 7);
    e.target.value = v;
  }
  validateZip();
}

function validateZip() {
  const country = document.getElementById('origin-default-country').value;
  const geo = getGeo(country);
  const zipInput = document.getElementById('origin-default-zip');
  const hint = document.getElementById('zip-hint');
  if (!zipInput || !hint) return;
  const val = zipInput.value.trim();
  if (!val) { hint.textContent = ''; hint.className = 'field-hint'; return; }
  if (geo.zipPattern && !geo.zipPattern.test(val)) {
    hint.textContent = `Format: ${geo.zipMask || geo.zipPlaceholder}`;
    hint.className = 'field-hint hint-warn'; return;
  }
  const stateCode = document.getElementById('origin-default-state')?.dataset.code || '';
  if (stateCode && geo.regions.length) {
    const region = geo.regions.find(r => r.code === stateCode);
    if (region && region.zips.length > 0) {
      const prefix = country === 'CA' ? val.charAt(0).toUpperCase() : val.slice(0, 2);
      if (!region.zips.some(z => prefix.startsWith(z) || z.startsWith(prefix))) {
        hint.textContent = `This doesn't look like a ${region.name} ${geo.zipLabel.toLowerCase()}`;
        hint.className = 'field-hint hint-warn'; return;
      }
    }
  }
  hint.textContent = '\u2713 Valid format'; hint.className = 'field-hint hint-ok';
}

// ─── Generic Geo Selectors ─────────────────────────────────────────────────────
function initGeoFields(prefix) {
  const countryEl = document.getElementById(prefix + '-country');
  if (!countryEl) return;
  countryEl.addEventListener('change', () => geoOnCountryChange(prefix));
  geoOnCountryChange(prefix);
}

function geoOnCountryChange(prefix) {
  const country = document.getElementById(prefix + '-country').value;
  const geo = getGeo(country);
  const stateLabel = document.querySelector(`#${prefix}-state-field > label`);
  if (stateLabel) stateLabel.textContent = geo.label;
  const stateInput = document.getElementById(prefix + '-state');
  if (stateInput) {
    stateInput.value = ''; stateInput.dataset.code = '';
    stateInput.placeholder = geo.regions.length ? `Search ${geo.label.toLowerCase()}...` : `Enter ${geo.label.toLowerCase()}`;
  }
  const zipLabel = document.querySelector(`#${prefix}-zip-field > label`);
  if (zipLabel) zipLabel.textContent = geo.zipLabel;
  const zipInput = document.getElementById(prefix + '-zip');
  if (zipInput) { zipInput.value = ''; zipInput.placeholder = geo.zipPlaceholder; }
  const hint = document.getElementById(prefix + '-zip-hint');
  if (hint) { hint.textContent = ''; hint.className = 'field-hint'; }
}

function geoShowStates(prefix) {
  const input = document.getElementById(prefix + '-state');
  geoFilterStates(prefix, input ? input.value : '');
}

function geoFilterStates(prefix, query) {
  const country = document.getElementById(prefix + '-country').value;
  const geo = getGeo(country);
  const dd = document.getElementById(prefix + '-state-dropdown');
  if (!dd || !geo.regions.length) { if (dd) dd.classList.add('hidden'); return; }
  const q = query.toLowerCase();
  const matches = geo.regions.filter(r => r.name.toLowerCase().includes(q) || r.code.toLowerCase().includes(q));
  dd.innerHTML = matches.length === 0
    ? '<div class="ac-empty">No matches</div>'
    : matches.map(r => `<div class="ac-item" onmousedown="geoSelectState('${prefix}','${r.code}','${esc(r.name)}')"><span class="ac-code">${esc(r.code)}</span><span class="ac-name">${esc(r.name)}</span></div>`).join('');
  dd.classList.remove('hidden');
}

function geoHideStates(prefix) {
  setTimeout(() => { const dd = document.getElementById(prefix + '-state-dropdown'); if (dd) dd.classList.add('hidden'); }, 150);
}

function geoSelectState(prefix, code, name) {
  const input = document.getElementById(prefix + '-state');
  if (input) { input.value = `${code} \u2014 ${name}`; input.dataset.code = code; }
  const dd = document.getElementById(prefix + '-state-dropdown'); if (dd) dd.classList.add('hidden');
  const zipInput = document.getElementById(prefix + '-zip'); if (zipInput) zipInput.value = '';
  geoValidateZip(prefix);
}

function geoOnZipInput(prefix) {
  const country = document.getElementById(prefix + '-country').value;
  const zipInput = document.getElementById(prefix + '-zip');
  if (country === 'CA' && zipInput) {
    let v = zipInput.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (v.length > 3) v = v.slice(0, 3) + ' ' + v.slice(3);
    if (v.length > 7) v = v.slice(0, 7);
    zipInput.value = v;
  }
  geoValidateZip(prefix);
}

function geoValidateZip(prefix) {
  const country = document.getElementById(prefix + '-country').value;
  const geo = getGeo(country);
  const zipInput = document.getElementById(prefix + '-zip');
  const hint = document.getElementById(prefix + '-zip-hint');
  if (!zipInput || !hint) return;
  const val = zipInput.value.trim();
  if (!val) { hint.textContent = ''; hint.className = 'field-hint'; return; }
  if (geo.zipPattern && !geo.zipPattern.test(val)) {
    hint.textContent = `Format: ${geo.zipMask || geo.zipPlaceholder}`;
    hint.className = 'field-hint hint-warn'; return;
  }
  const stateCode = document.getElementById(prefix + '-state')?.dataset.code || '';
  if (stateCode && geo.regions.length) {
    const region = geo.regions.find(r => r.code === stateCode);
    if (region && region.zips.length > 0) {
      const pfx = country === 'CA' ? val.charAt(0).toUpperCase() : val.slice(0, 2);
      if (!region.zips.some(z => pfx.startsWith(z) || z.startsWith(pfx))) {
        hint.textContent = `This doesn't look like a ${region.name} ${geo.zipLabel.toLowerCase()}`;
        hint.className = 'field-hint hint-warn'; return;
      }
    }
  }
  hint.textContent = '\u2713 Valid format'; hint.className = 'field-hint hint-ok';
}

// ─── Upload Helper Functions ─────────────────────────────────────────────────
function setOriginMode(mode) {
  document.querySelectorAll('.origin-mode-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.origin-mode-btn[data-mode="${mode}"]`).classList.add('active');
  const singleEl = document.getElementById('origin-single-fields');
  const multiEl = document.getElementById('origin-multi-fields');
  if (mode === 'single') { singleEl.classList.remove('hidden'); multiEl.classList.add('hidden'); }
  else { singleEl.classList.add('hidden'); multiEl.classList.remove('hidden'); }
}

function getOriginMode() {
  return document.querySelector('.origin-mode-btn.active')?.dataset.mode || 'single';
}

function setUnitSystem(system) {
  document.querySelectorAll('.unit-system-card').forEach(c => c.classList.remove('active'));
  document.querySelector(`.unit-system-card[data-system="${system}"]`).classList.add('active');
  const wTarget = system === 'metric' ? 'kg' : 'lbs';
  const dTarget = system === 'metric' ? 'cm' : 'in';
  document.querySelectorAll('.unit-btn[data-unit-group="weight"]').forEach(b => b.classList.toggle('active', b.dataset.unit === wTarget));
  document.querySelectorAll('.unit-btn[data-unit-group="dimensions"]').forEach(b => b.classList.toggle('active', b.dataset.unit === dTarget));
}

function setUnit(btn) {
  const group = btn.dataset.unitGroup;
  document.querySelectorAll(`.unit-btn[data-unit-group="${group}"]`).forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const w = document.querySelector('.unit-btn[data-unit-group="weight"].active')?.dataset.unit;
  const d = document.querySelector('.unit-btn[data-unit-group="dimensions"].active')?.dataset.unit;
  document.querySelectorAll('.unit-system-card').forEach(c => c.classList.remove('active'));
  if (w === 'lbs' && d === 'in') document.querySelector('.unit-system-card[data-system="imperial"]')?.classList.add('active');
  else if (w === 'kg' && d === 'cm') document.querySelector('.unit-system-card[data-system="metric"]')?.classList.add('active');
}

function setCurrency(code) {
  document.querySelectorAll('.unit-system-card[data-currency]').forEach(c => c.classList.remove('active'));
  document.querySelector(`.unit-system-card[data-currency="${code}"]`)?.classList.add('active');
}

function getSelectedCurrency() {
  return document.querySelector('.unit-system-card[data-currency].active')?.dataset.currency || 'USD';
}

function getUploadMeta() {
  const originMode = getOriginMode();
  const stateEl = document.getElementById('origin-default-state');
  const stateCode = stateEl?.dataset.code || stateEl?.value?.trim() || '';
  return {
    origin_mode: originMode,
    origin_defaults: originMode === 'single' ? {
      state: stateCode,
      zip: (document.getElementById('origin-default-zip')?.value || '').trim(),
      country: document.getElementById('origin-default-country')?.value || 'US'
    } : null,
    unit_system: {
      weight: document.querySelector('.unit-btn[data-unit-group="weight"].active')?.dataset.unit || 'lbs',
      dimensions: document.querySelector('.unit-btn[data-unit-group="dimensions"].active')?.dataset.unit || 'in'
    },
    currency: getSelectedCurrency()
  };
}

function clearUploadedFile() {
  uploadedData = null; csvColumns = []; csvRows = []; uploadFileName = '';
  const fileInfoEl = document.getElementById('upload-file-info');
  if (fileInfoEl) { fileInfoEl.classList.add('hidden'); fileInfoEl.innerHTML = ''; }
  const mapEl = document.getElementById('upload-mapping');
  if (mapEl) { mapEl.classList.add('hidden'); mapEl.innerHTML = ''; }
  const resultEl = document.getElementById('upload-result');
  if (resultEl) { resultEl.classList.add('hidden'); resultEl.innerHTML = ''; }
  const uploadZone = document.getElementById('upload-zone');
  if (uploadZone) uploadZone.classList.remove('hidden');
  showToast('File cleared. Choose a different file.', 'info');
}

function downloadTemplate() {
  const headers = "Ship Date,Service Level,Carrier,Actual Weight,Billed Weight,Length,Width,Height,Tracking Number,Price,Origin Zip,Origin State,Origin Country,Dest Zip,Dest State,Dest Country\n";
  const samples = [
    "2025-01-06,Ground,UPS,5.2,6,12,8,6,1Z999AA10012345,12.50,90210,CA,US,10001,NY,US",
    "2025-01-06,Ground,FedEx,2.1,3,10,8,4,7489012345600001,8.75,90210,CA,US,60601,IL,US",
    "2025-01-07,Priority,USPS,0.8,1,9,6,3,9400111899223100001,7.20,90210,CA,US,30301,GA,US",
    "2025-01-07,2Day,FedEx,14.6,15,24,18,12,7489012345600002,28.90,90210,CA,US,98101,WA,US",
    "2025-01-08,Ground,UPS,32,35,30,20,16,1Z999AA10012346,42.15,60601,IL,US,33101,FL,US",
    "2025-01-08,Express Saver,FedEx,8.4,9,16,12,10,7489012345600003,19.60,60601,IL,US,02101,MA,US",
    "2025-01-09,SurePost,UPS,1.3,2,11,8,3,1Z999AA10012347,6.40,10001,NY,US,75201,TX,US",
    "2025-01-09,SmartPost,FedEx,3.7,4,14,10,8,7489012345600004,9.85,10001,NY,US,85001,AZ,US",
    "2025-01-10,Ground,UPS,48,50,36,24,18,1Z999AA10012348,55.30,30301,GA,US,94102,CA,US",
    "2025-01-10,Home Delivery,FedEx,6.5,7,18,12,8,7489012345600005,14.25,30301,GA,US,80201,CO,US"
  ].join('\n') + '\n';
  const blob = new Blob([headers + samples], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'broad-reach-shipping-template.csv';
  a.click();
}

function handleDrop(e) {
  e.preventDefault();
  e.target.closest('.upload-zone').classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
}

function handleFile(file) {
  if (!file) return;
  uploadFileName = file.name;
  const reader = new FileReader();
  reader.onload = function (ev) { parseCSV(ev.target.result); };
  reader.readAsText(file);
}

function parseCSV(text) {
  const lines = text.trim().split('\n');
  if (lines.length < 2) { showToast('CSV must have headers and data', 'error'); return; }
  csvColumns = lines[0].split(',').map(c => c.trim().replace(/"/g, ''));
  csvRows = lines.slice(1).map(l => {
    const row = [];
    let current = '';
    let inQuotes = false;
    for (const ch of l) {
      if (ch === '"') inQuotes = !inQuotes;
      else if (ch === ',' && !inQuotes) { row.push(current.trim()); current = ''; }
      else current += ch;
    }
    row.push(current.trim());
    return row;
  });
  showMappingUI();
}

const REQUIRED_FIELDS = [
  { key: 'ship_date', label: 'Ship Date' },
  { key: 'service', label: 'Service Level' },
  { key: 'carrier', label: 'Carrier' },
  { key: 'weight', label: 'Actual Weight' },
  { key: 'billed_weight', label: 'Billed Weight' },
  { key: 'length', label: 'Length' },
  { key: 'width', label: 'Width' },
  { key: 'height', label: 'Height' },
  { key: 'tracking', label: 'Tracking Number' },
  { key: 'price', label: 'Price' },
  { key: 'origin_zip', label: 'Origin Zip/Postal' },
  { key: 'origin_state', label: 'Origin State' },
  { key: 'origin_country', label: 'Origin Country' },
  { key: 'dest_zip', label: 'Dest Zip/Postal' },
  { key: 'dest_state', label: 'Dest State' },
  { key: 'dest_country', label: 'Dest Country' }
];

function autoDetectColumn(fieldKey) {
  const aliases = {
    ship_date: ['ship date', 'ship_date', 'shipdate', 'date', 'ship dt', 'shipment date'],
    service: ['service', 'service level', 'service_level', 'servicelevel'],
    carrier: ['carrier', 'provider'],
    weight: ['actual weight', 'actual_weight', 'actualweight', 'weight', 'wt', 'lbs', 'weight (lbs)'],
    billed_weight: ['billed weight', 'billed_weight', 'billedweight', 'billed wt', 'billed'],
    length: ['length', 'len', 'l'],
    width: ['width', 'wid', 'w'],
    height: ['height', 'ht', 'h'],
    tracking: ['tracking', 'tracking number', 'tracking_number', 'trackingnumber'],
    price: ['price', 'cost', 'amount', 'total', 'charge'],
    origin_zip: ['origin zip', 'origin_zip', 'originzip', 'from zip', 'origin postal'],
    origin_state: ['origin state', 'origin_state', 'originstate', 'from state'],
    origin_country: ['origin country', 'origin_country', 'origincountry', 'from country'],
    dest_zip: ['dest zip', 'dest_zip', 'destzip', 'destination zip', 'to zip', 'dest postal'],
    dest_state: ['dest state', 'dest_state', 'deststate', 'destination state', 'to state'],
    dest_country: ['dest country', 'dest_country', 'destcountry', 'destination country', 'to country']
  };
  const options = aliases[fieldKey] || [];
  for (let i = 0; i < csvColumns.length; i++) {
    const col = csvColumns[i].toLowerCase();
    if (options.some(a => col.includes(a))) return i;
  }
  return -1;
}

function showMappingUI() {
  const fileInfoEl = document.getElementById('upload-file-info');
  if (fileInfoEl) {
    fileInfoEl.classList.remove('hidden');
    fileInfoEl.innerHTML = `
      <div class="card upload-file-bar">
        <div class="file-bar-left">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <div class="file-bar-info">
            <span class="file-bar-name">${esc(uploadFileName || 'File')}</span>
            <span class="file-bar-meta">${csvColumns.length} columns · ${csvRows.length} rows detected</span>
          </div>
        </div>
        <button class="btn-ghost file-bar-clear" onclick="clearUploadedFile()" title="Clear file">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          Clear
        </button>
      </div>`;
  }
  const uploadZone = document.getElementById('upload-zone');
  if (uploadZone) uploadZone.classList.add('hidden');

  const mapEl = document.getElementById('upload-mapping');
  mapEl.classList.remove('hidden');
  mapEl.innerHTML = `
    <div class="card mapping-card">
      <h3>Map Your Columns</h3>
      <p class="mapping-desc">We detected ${csvColumns.length} columns and ${csvRows.length} rows. Map them to required fields.</p>
      <div class="mapping-grid">
        ${REQUIRED_FIELDS.map(f => {
          const auto = autoDetectColumn(f.key);
          return `<div class="mapping-row">
            <label class="mapping-label">${f.label}</label>
            <select id="map-${f.key}" class="mapping-select">
              <option value="-1">— Skip —</option>
              ${csvColumns.map((c, i) => `<option value="${i}" ${i === auto ? 'selected' : ''}>${esc(c)}</option>`).join('')}
            </select>
          </div>`;
        }).join('')}
      </div>
      <div class="mapping-preview">
        <div class="mapping-preview-title">Preview (first 5 rows)</div>
        <div class="table-container">
          <table class="data-table">
            <thead><tr>${csvColumns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>
            <tbody>${csvRows.slice(0, 5).map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody>
          </table>
        </div>
      </div>
      <button class="btn-primary btn-large" onclick="submitUpload()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        Upload ${csvRows.length} Shipments
      </button>
    </div>`;
}

async function submitUpload() {
  const mapping = {};
  REQUIRED_FIELDS.forEach(f => {
    mapping[f.key] = parseInt(document.getElementById(`map-${f.key}`).value);
  });
  const meta = getUploadMeta();
  const od = meta.origin_defaults || { state: '', zip: '', country: '' };
  const isMulti = meta.origin_mode === 'multi';

  const data = csvRows.map(row => ({
    ship_date: mapping.ship_date >= 0 ? row[mapping.ship_date] || '' : '',
    service: mapping.service >= 0 ? row[mapping.service] || '' : '',
    carrier: mapping.carrier >= 0 ? row[mapping.carrier] || '' : '',
    weight: mapping.weight >= 0 ? parseFloat(row[mapping.weight]) || 0 : 0,
    billed_weight: mapping.billed_weight >= 0 ? parseFloat(row[mapping.billed_weight]) || 0 : 0,
    length: mapping.length >= 0 ? parseFloat(row[mapping.length]) || 0 : 0,
    width: mapping.width >= 0 ? parseFloat(row[mapping.width]) || 0 : 0,
    height: mapping.height >= 0 ? parseFloat(row[mapping.height]) || 0 : 0,
    tracking: mapping.tracking >= 0 ? row[mapping.tracking] || '' : '',
    price: mapping.price >= 0 ? parseFloat(row[mapping.price]) || 0 : 0,
    origin_zip: mapping.origin_zip >= 0 ? (row[mapping.origin_zip] || (isMulti ? '' : od.zip)) : (isMulti ? '' : od.zip),
    origin_state: mapping.origin_state >= 0 ? (row[mapping.origin_state] || (isMulti ? '' : od.state)) : (isMulti ? '' : od.state),
    origin_country: mapping.origin_country >= 0 ? (row[mapping.origin_country] || (isMulti ? '' : od.country)) : (isMulti ? '' : od.country),
    dest_zip: mapping.dest_zip >= 0 ? row[mapping.dest_zip] || '' : '',
    dest_state: mapping.dest_state >= 0 ? row[mapping.dest_state] || '' : '',
    dest_country: mapping.dest_country >= 0 ? row[mapping.dest_country] || '' : 'US'
  })).filter(r => r.weight > 0);

  try {
    await api(`/clients/${state.userId}/shipping-data`, {
      method: 'POST',
      body: { data, origin_mode: meta.origin_mode, origin_defaults: meta.origin_defaults, unit_system: meta.unit_system, currency: meta.currency }
    });
    showToast('Shipping data uploaded successfully!', 'success');
    // Go to review step
    setTimeout(() => navigateJourney(3, {refresh: true}), 500);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── Shipping Profile ────────────────────────────────────────────────────────
function computeShippingProfile(data, summary) {
  const rows = data;
  const n = rows.length;
  if (n === 0) return null;

  const unitSys = summary.unit_system || { weight: 'lbs', dimensions: 'in' };
  const wUnit = unitSys.weight || 'lbs';
  const dUnit = unitSys.dimensions || 'in';
  const cur = summary.currency || 'USD';

  let totalWeight = 0, totalBilled = 0;
  let totalCubicVol = 0, cubicCount = 0;
  let totalPrice = 0, priceCount = 0;
  const carrierCounts = {};
  const serviceCounts = {};
  const dates = [];

  for (const r of rows) {
    const w = parseFloat(r.weight) || 0;
    const bw = parseFloat(r.billed_weight) || w;
    totalWeight += w;
    totalBilled += bw;
    const l = parseFloat(r.length) || 0;
    const wd = parseFloat(r.width) || 0;
    const h = parseFloat(r.height) || 0;
    if (l > 0 && wd > 0 && h > 0) { totalCubicVol += l * wd * h; cubicCount++; }
    const p = parseFloat(r.price) || 0;
    if (p > 0) { totalPrice += p; priceCount++; }
    const c = (r.carrier || 'Unknown').trim();
    carrierCounts[c] = (carrierCounts[c] || 0) + 1;
    const s = (r.service || 'Unknown').trim();
    serviceCounts[s] = (serviceCounts[s] || 0) + 1;
    if (r.ship_date) {
      const d = new Date(r.ship_date);
      if (!isNaN(d.getTime())) dates.push(d);
    }
  }

  const avgWeight = totalWeight / n;
  const avgBilled = totalBilled / n;
  let avgCubicDisplay = 0, cubicLabel = '';
  if (cubicCount > 0) {
    const avgCubicRaw = totalCubicVol / cubicCount;
    if (dUnit === 'cm') { avgCubicDisplay = avgCubicRaw / 1000000; cubicLabel = 'm\u00B3'; }
    else { avgCubicDisplay = avgCubicRaw / 1728; cubicLabel = 'ft\u00B3'; }
  }

  const avgPrice = priceCount > 0 ? totalPrice / priceCount : 0;
  const costPerUnit = totalWeight > 0 ? totalPrice / totalWeight : 0;
  const costPerUnitLabel = wUnit === 'kg' ? 'Cost / kg' : 'Cost / lb';

  let dateMin = null, dateMax = null;
  if (dates.length >= 2) { dates.sort((a, b) => a - b); dateMin = dates[0]; dateMax = dates[dates.length - 1]; }
  else if (dates.length === 1) { dateMin = dates[0]; dateMax = dates[0]; }

  let calendarDays = 1;
  if (dateMin && dateMax) calendarDays = Math.max(1, Math.round((dateMax - dateMin) / 86400000) + 1);

  // Business-day-based projections (250 shipping days/year, 5/week, ~21/month)
  const BUSINESS_DAYS_PER_YEAR = 250;
  const BUSINESS_DAYS_PER_WEEK = 5;
  const BUSINESS_DAYS_PER_MONTH = Math.round(BUSINESS_DAYS_PER_YEAR / 12); // ~21

  // Estimate business days in the date range
  let businessDaysInRange = 1;
  if (dateMin && dateMax) {
    // Count weekdays (Mon-Fri) in the date range
    let bd = 0;
    const d = new Date(dateMin);
    const end = new Date(dateMax);
    while (d <= end) {
      const dow = d.getDay();
      if (dow !== 0 && dow !== 6) bd++;
      d.setDate(d.getDate() + 1);
    }
    businessDaysInRange = Math.max(1, bd);
  }

  const shipmentsPerBizDay = n / businessDaysInRange;
  const weeklyShipments = Math.round(shipmentsPerBizDay * BUSINESS_DAYS_PER_WEEK);
  const monthlyShipments = Math.round(shipmentsPerBizDay * BUSINESS_DAYS_PER_MONTH);
  const annualShipments = Math.round(shipmentsPerBizDay * BUSINESS_DAYS_PER_YEAR);
  const spendPerBizDay = totalPrice / businessDaysInRange;
  const weeklySpend = spendPerBizDay * BUSINESS_DAYS_PER_WEEK;
  const monthlySpend = spendPerBizDay * BUSINESS_DAYS_PER_MONTH;
  const annualSpend = spendPerBizDay * BUSINESS_DAYS_PER_YEAR;

  const dateRangeStr = dateMin && dateMax
    ? dateMin.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      + ' \u2013 ' + dateMax.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : 'N/A';

  const topCarriers = Object.entries(carrierCounts)
    .sort((a, b) => b[1] - a[1]).slice(0, 5)
    .map(([name, count]) => ({ name, count, pct: Math.round((count / n) * 100) }));
  const topServices = Object.entries(serviceCounts)
    .sort((a, b) => b[1] - a[1]).slice(0, 5)
    .map(([name, count]) => ({ name, count, pct: Math.round((count / n) * 100) }));

  return {
    n, cur, wUnit, dUnit, cubicLabel,
    avgWeight, avgBilled, avgCubicDisplay, cubicCount,
    avgPrice, costPerUnit, costPerUnitLabel,
    totalPrice, priceCount, calendarDays,
    dateRangeStr, dateMin, dateMax,
    weeklyShipments, monthlyShipments, annualShipments,
    weeklySpend, monthlySpend, annualSpend,
    topCarriers, topServices
  };
}

// ─── Client Data Summary (kept for compatibility, redirects to journey) ──────
async function renderClientDataSummary(el) {
  navigateJourney(3);
}

function renderShippingProfile(el, client, animate) {
  // Redirected to journey step 3
}

function confirmShippingProfile() {
  confirmAndSubmitData();
}

// ─── Savings Analysis rendering (kept for compatibility) ─────────────────────
async function renderClientAnalysis(el) {
  navigateJourney(4);
}

function renderAnalysisCharts(byService, byCarrier, currency) {
  const isDark = state.theme === 'dark';
  const textColor = isDark ? '#cdccca' : '#28251d';
  const gridColor = isDark ? '#393836' : '#dcd9d5';
  const prefix = currency === 'CAD' ? 'C$' : '$';

  const svcLabels = Object.keys(byService);
  const svcCtx = document.getElementById('chart-service');
  if (svcCtx) {
    const c = new Chart(svcCtx, {
      type: 'bar',
      data: {
        labels: svcLabels,
        datasets: [
          { label: 'Current Spend', data: svcLabels.map(k => byService[k].original), backgroundColor: isDark ? '#dd6974' : '#a13544', borderRadius: 4 },
          { label: 'Broad Reach', data: svcLabels.map(k => byService[k].br), backgroundColor: isDark ? '#4f98a3' : '#01696f', borderRadius: 4 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: textColor, font: { family: 'Inter', size: 12 } } } },
        scales: {
          x: { ticks: { color: textColor, font: { family: 'Inter', size: 11 } }, grid: { display: false } },
          y: { ticks: { color: textColor, font: { family: 'Inter', size: 11 }, callback: v => prefix + v.toLocaleString() }, grid: { color: gridColor } }
        }
      }
    });
    analysisCharts.push(c);
  }

  const carrierLabels = Object.keys(byCarrier);
  const carrierCtx = document.getElementById('chart-carrier');
  if (carrierCtx) {
    const colors = isDark
      ? ['#4f98a3', '#6daa45', '#fdab43', '#a86fdf', '#5591c7']
      : ['#01696f', '#437a22', '#da7101', '#7a39bb', '#006494'];
    const c = new Chart(carrierCtx, {
      type: 'doughnut',
      data: {
        labels: carrierLabels,
        datasets: [{ data: carrierLabels.map(k => byCarrier[k].savings), backgroundColor: colors.slice(0, carrierLabels.length), borderWidth: 0 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        cutout: '55%',
        plugins: {
          legend: { position: 'bottom', labels: { color: textColor, font: { family: 'Inter', size: 12 }, padding: 16 } },
          tooltip: { callbacks: { label: ctx => `${ctx.label}: ${formatCurrency(ctx.parsed, currency)}` } }
        }
      }
    });
    analysisCharts.push(c);
  }
}

function downloadAnalysisCSV() {
  const roleParam = state.userType === 'client' ? '?role=client' : '';
  api(`/clients/${state.userId}${roleParam}`).then(client => {
    if (!client.analysis) return;
    const cur = client.analysis.results.currency || 'USD';
    const sm = client.analysis.results.summary || {};
    const rows = client.analysis.results.shipments;
    if (!rows || rows.length === 0) { showToast('No shipment data to export', 'info'); return; }

    // Collect all unique service names from all_rates across all shipments
    const allServiceNames = new Set();
    rows.forEach(s => {
      if (s.all_rates) Object.keys(s.all_rates).forEach(name => allServiceNames.add(name));
    });
    const serviceList = Array.from(allServiceNames).sort();

    // Build header
    const headers = [
      'Ship Date', 'Tracking', 'Carrier', 'Service',
      'Weight (lbs)', 'Billed Weight (lbs)', 'DIM Weight (lbs)',
      'Length', 'Width', 'Height',
      'Origin Zip', 'Origin State', 'Origin Country',
      'Dest Zip', 'Dest State', 'Dest Country',
      'Zone',
      `Current Price (${cur})`,
      'Lowest Cost BR Service', `BR Price (${cur})`,
      `Fuel (${cur})`, `Accessorials (${cur})`,
      `Savings (${cur})`, 'Savings %'
    ];
    // Add a column for each rated service (total, base, fuel, access breakdown)
    serviceList.forEach(name => {
      headers.push(`${name} Total (${cur})`);
      headers.push(`${name} Base (${cur})`);
      headers.push(`${name} Fuel (${cur})`);
      headers.push(`${name} Accessorials (${cur})`);
    });

    // Build rows
    const csvRows = [headers.map(h => '"' + h.replace(/"/g, '""') + '"').join(',')];
    rows.forEach(s => {
      const row = [
        s.ship_date || '',
        s.tracking || '',
        s.carrier || '',
        s.service || '',
        s.weight || '',
        s.billable_weight || s.billed_weight || s.weight || '',
        s.dim_weight || '',
        s.length || '',
        s.width || '',
        s.height || '',
        s.origin_zip || '',
        s.origin_state || '',
        s.origin_country || '',
        s.dest_zip || '',
        s.dest_state || '',
        s.dest_country || '',
        s.zone || '',
        s.price || 0,
        s.br_service || '',
        s.br_price || 0,
        s.fuel || 0,
        s.accessorials || 0,
        s.savings || 0,
        s.savings_pct ? s.savings_pct + '%' : '0%'
      ];
      // Add each service rate with breakdown
      serviceList.forEach(name => {
        const rate = s.all_rates ? s.all_rates[name] : null;
        row.push(rate ? rate.final : '');
        row.push(rate ? rate.base : '');
        row.push(rate ? rate.fuel : '');
        row.push(rate ? rate.accessorials : '');
      });
      csvRows.push(row.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(','));
    });

    // Add summary rows at the bottom
    csvRows.push('');
    csvRows.push('"=== ANALYSIS SUMMARY ==="');
    csvRows.push(`"Total Shipments","${sm.shipment_count || rows.length}"`);
    csvRows.push(`"Current Total Spend","${sm.total_original || ''}"`);
    csvRows.push(`"Broad Reach Total Price","${sm.total_br || ''}"`);
    csvRows.push(`"Total Savings","${sm.total_savings || ''}"`);
    csvRows.push(`"Savings Percentage","${sm.savings_pct || ''}%"`);
    csvRows.push(`"Shipments With Savings","${sm.shipments_with_savings || ''}"`);
    csvRows.push(`"Total Fuel Surcharges","${sm.total_fuel || 0}"`);
    csvRows.push(`"Total Accessorials","${sm.total_accessorials || 0}"`);
    csvRows.push(`"Currency","${cur}"`);
    csvRows.push(`"Analysis Date","${new Date().toISOString().split('T')[0]}"`);
    csvRows.push(`"Annualized Savings (250 biz days)","${sm.total_savings > 0 ? (sm.total_savings / Math.max(sm.shipment_count, 1) * 250 * (sm.shipment_count / Math.max(1, 1))).toFixed(2) : 0}"`);

    const csv = csvRows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    const companySlug = (client.company_name || 'company').replace(/[^a-zA-Z0-9]/g, '-').toLowerCase();
    a.download = `broad-reach-${companySlug}-savings-analysis.csv`;
    a.click();
  });
}

function previewClientExcel() {
  const clientId = window._workbenchClientId;
  if (!clientId) { showToast('No client selected', 'error'); return; }
  const tokenParam = state.token ? `&token=${encodeURIComponent(state.token)}` : '';
  const url = `${API}/clients/${clientId}/analysis-excel?role=client${tokenParam}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  a.click();
  showToast('Downloading client preview Excel...', 'success');
}

function downloadAnalysisExcel() {
  const roleParam = state.userType === 'client' ? '?role=client' : '';
  const tokenParam = state.token ? `${roleParam ? '&' : '?'}token=${state.token}` : '';
  const url = `${API}/clients/${state.userId}/analysis-excel${roleParam}${tokenParam}`;
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  a.click();
}

function downloadProcessedData() {
  // Use cached client data if available, otherwise fetch
  const clientData = window._clientData;
  if (!clientData || !clientData.analysis) {
    showToast('No analysis data available to download', 'info');
    return;
  }
  const results = clientData.analysis.results;
  if (!results || !results.shipments || results.shipments.length === 0) {
    showToast('No shipment data to export', 'info');
    return;
  }
  const cur = results.currency || 'USD';
  const sm = results.summary || {};
  const rows = results.shipments;

  // Collect all unique service names
  const allServiceNames = new Set();
  rows.forEach(s => {
    if (s.all_rates) Object.keys(s.all_rates).forEach(name => allServiceNames.add(name));
  });
  const serviceList = Array.from(allServiceNames).sort();

  // Build headers with buy/sell/profit fields
  const headers = [
    'Ship Date', 'Tracking', 'Carrier', 'Service',
    'Weight (lbs)', 'Billed Weight (lbs)', 'DIM Weight (lbs)',
    'Length', 'Width', 'Height',
    'Origin Zip', 'Origin State', 'Origin Country',
    'Dest Zip', 'Dest State', 'Dest Country',
    'Zone',
    `Original Price (${cur})`,
    'Best BR Service',
    `BR Sell Price (${cur})`,
    `BR Buy Price (${cur})`,
    `Fuel (${cur})`,
    `Accessorials (${cur})`,
    `Profit (${cur})`,
    'Margin %',
    `Savings (${cur})`,
    'Savings %'
  ];
  // Per service: total, base, fuel_buy, buy_price, sell_price, profit, margin_pct
  serviceList.forEach(name => {
    headers.push(`${name} Sell (${cur})`);
    headers.push(`${name} Buy (${cur})`);
    headers.push(`${name} Base (${cur})`);
    headers.push(`${name} Fuel Sell (${cur})`);
    headers.push(`${name} Fuel Buy (${cur})`);
    headers.push(`${name} Profit (${cur})`);
    headers.push(`${name} Margin%`);
    headers.push(`${name} Access (${cur})`);
  });

  const csvRows = [headers.map(h => '"' + h.replace(/"/g, '""') + '"').join(',')];

  rows.forEach(s => {
    // Resolve buy price and profit from shipment or from all_rates of br_service
    let bestRate = null;
    if (s.all_rates && s.br_service && s.all_rates[s.br_service]) {
      bestRate = s.all_rates[s.br_service];
    }
    const buyPrice = s.buy_price != null ? s.buy_price : (bestRate ? (bestRate.buy_price || bestRate.base_buy || '') : '');
    const profit = s.profit != null ? s.profit : (bestRate ? (bestRate.profit || '') : '');
    const marginPct = s.margin_pct != null ? s.margin_pct : (bestRate ? (bestRate.margin_pct || '') : '');

    const row = [
      s.ship_date || '',
      s.tracking || '',
      s.carrier || '',
      s.service || '',
      s.weight || '',
      s.billable_weight || s.billed_weight || s.weight || '',
      s.dim_weight || '',
      s.length || '',
      s.width || '',
      s.height || '',
      s.origin_zip || '',
      s.origin_state || '',
      s.origin_country || '',
      s.dest_zip || '',
      s.dest_state || '',
      s.dest_country || '',
      s.zone || '',
      s.price || 0,
      s.br_service || '',
      s.br_price || 0,
      buyPrice,
      s.fuel || 0,
      s.accessorials || 0,
      profit,
      marginPct !== '' ? (typeof marginPct === 'number' ? marginPct.toFixed(2) + '%' : marginPct + '%') : '',
      s.savings || 0,
      s.savings_pct ? s.savings_pct + '%' : '0%'
    ];
    serviceList.forEach(name => {
      const rate = s.all_rates ? s.all_rates[name] : null;
      row.push(rate ? (rate.final || rate.sell_price || '') : '');
      row.push(rate ? (rate.buy_price || rate.base_buy || '') : '');
      row.push(rate ? (rate.base || '') : '');
      row.push(rate ? (rate.fuel || '') : '');
      row.push(rate ? (rate.fuel_buy || '') : '');
      row.push(rate ? (rate.profit || '') : '');
      row.push(rate && rate.margin_pct != null ? rate.margin_pct.toFixed(2) + '%' : '');
      row.push(rate ? (rate.accessorials || 0) : '');
    });
    csvRows.push(row.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(','));
  });

  // Summary
  csvRows.push('');
  csvRows.push('"=== PROFITABILITY SUMMARY ==="');
  csvRows.push(`"Total Shipments","${sm.shipment_count || rows.length}"`);
  csvRows.push(`"Current Total Spend","${sm.total_original || ''}"`);
  csvRows.push(`"BR Total Sell Price","${sm.total_br || ''}"`);
  csvRows.push(`"Total Buy Cost","${sm.total_buy_cost || ''}"`);
  csvRows.push(`"Total Profit","${sm.total_profit_actual || ''}"`);
  csvRows.push(`"Actual Margin %","${sm.actual_margin_pct != null ? sm.actual_margin_pct.toFixed(2) + '%' : ''}"`);
  csvRows.push(`"Total Savings vs Current","${sm.total_savings || ''}"`);
  csvRows.push(`"Savings %","${sm.savings_pct || ''}%"`);
  csvRows.push(`"Currency","${cur}"`);
  csvRows.push(`"Export Date","${new Date().toISOString().split('T')[0]}"`);

  const csv = csvRows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  const companySlug = (clientData.company_name || 'company').replace(/[^a-zA-Z0-9]/g, '-').toLowerCase();
  a.download = `broad-reach-${companySlug}-processed-data.csv`;
  a.click();
}

// ─── Client Setup ─────────────────────────────────────────────────────────────
async function renderClientSetup(el) {
  el.innerHTML = `<div class="content-area"><div class="skeleton-block"></div></div>`;
  try {
    const client = await api(`/clients/${state.userId}?role=client`);
    const info = client.setup_info_json || {};

    el.innerHTML = `
      <div class="content-area">
        <div class="setup-header-row">
          <button class="btn-ghost" onclick="history.back()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            Back to Journey
          </button>
        </div>
        <h2 class="page-title">Setup Information</h2>
        <p class="page-desc">Complete the form below to finalize your onboarding. You can save progress at any time.</p>

        <form id="setup-form" class="setup-form" onsubmit="event.preventDefault(); saveSetup(true)">
          <fieldset class="form-section">
            <legend>Company Information</legend>
            <div class="form-grid">
              <div class="form-field"><label>Company Legal Name *</label><input name="legal_name" required value="${esc(info.legal_name || '')}"></div>
              <div class="form-field"><label>DBA</label><input name="dba" value="${esc(info.dba || '')}"></div>
              <div class="form-field span-2"><label>Address</label><input name="address" value="${esc(info.address || '')}"></div>
              <div class="form-field"><label>City</label><input name="city" value="${esc(info.city || '')}"></div>
              <div class="form-field" id="setup-country-field"><label>Country</label>
                <select id="setup-country">
                  ${[['US','United States'],['CA','Canada'],['GB','United Kingdom'],['AU','Australia'],['MX','Mexico']].map(([code,name]) =>
                    `<option value="${code}" ${(info.country || 'US') === code ? 'selected' : ''}>${name}</option>`
                  ).join('')}
                </select>
              </div>
              <div class="form-field ac-wrapper" id="setup-state-field"><label>State</label>
                <input id="setup-state" placeholder="Search state..." autocomplete="off"
                       onfocus="geoShowStates('setup')" oninput="geoFilterStates('setup', this.value)" onblur="geoHideStates('setup')" data-code="${esc(info.state_code || info.state || '')}">
                <div id="setup-state-dropdown" class="ac-dropdown hidden"></div>
              </div>
              <div class="form-field" id="setup-zip-field"><label>Zip Code</label>
                <input id="setup-zip" placeholder="e.g. 90210" autocomplete="off"
                       oninput="geoOnZipInput('setup')" value="${esc(info.zip || '')}">
                <div id="setup-zip-hint" class="field-hint"></div>
              </div>
              <div class="form-field"><label>Website</label><input name="website" type="url" value="${esc(info.website || '')}"></div>
              <div class="form-field"><label>Tax ID</label><input name="tax_id" value="${esc(info.tax_id || '')}"></div>
            </div>
          </fieldset>

          <fieldset class="form-section">
            <legend>Primary Contact</legend>
            <div class="form-grid">
              <div class="form-field"><label>Name *</label><input name="contact_name" required value="${esc(info.contact_name || state.userName || '')}"></div>
              <div class="form-field"><label>Title</label><input name="contact_title" value="${esc(info.contact_title || '')}"></div>
              <div class="form-field"><label>Email *</label><input name="contact_email" type="email" required value="${esc(info.contact_email || state.userEmail || '')}"></div>
              <div class="form-field"><label>Phone</label><input name="contact_phone" type="tel" value="${esc(info.contact_phone || '')}"></div>
            </div>
          </fieldset>

          <fieldset class="form-section">
            <legend>Billing Contact</legend>
            <div class="form-grid">
              <div class="form-field"><label>Name</label><input name="billing_name" value="${esc(info.billing_name || '')}"></div>
              <div class="form-field"><label>Title</label><input name="billing_title" value="${esc(info.billing_title || '')}"></div>
              <div class="form-field"><label>Email</label><input name="billing_email" type="email" value="${esc(info.billing_email || '')}"></div>
              <div class="form-field"><label>Phone</label><input name="billing_phone" type="tel" value="${esc(info.billing_phone || '')}"></div>
              <div class="form-field span-2"><label>Billing Address (if different)</label><input name="billing_address" value="${esc(info.billing_address || '')}"></div>
            </div>
          </fieldset>

          <fieldset class="form-section">
            <legend>Banking Information</legend>
            <div class="form-grid">
              <div class="form-field"><label>Bank Name</label><input name="bank_name" value="${esc(info.bank_name || '')}"></div>
              <div class="form-field"><label>Account Holder</label><input name="account_holder" value="${esc(info.account_holder || '')}"></div>
              <div class="form-field"><label>Account Number</label><input name="account_number" type="password" autocomplete="off" value="${esc(info.account_number || '')}"></div>
              <div class="form-field"><label>Routing Number</label><input name="routing_number" value="${esc(info.routing_number || '')}"></div>
              <div class="form-field">
                <label>Account Type</label>
                <select name="account_type"><option value="">Select...</option><option ${info.account_type === 'Checking' ? 'selected' : ''}>Checking</option><option ${info.account_type === 'Savings' ? 'selected' : ''}>Savings</option></select>
              </div>
            </div>
          </fieldset>

          <fieldset class="form-section">
            <legend>Terms & Agreements</legend>
            <div class="form-grid">
              <div class="form-field span-2"><label class="check-label"><input type="checkbox" name="agree_tos" ${info.agree_tos ? 'checked' : ''}> I agree to Broad Reach Terms of Service</label></div>
              <div class="form-field span-2"><label class="check-label"><input type="checkbox" name="agree_bank" ${info.agree_bank ? 'checked' : ''}> I authorize Broad Reach to verify banking information</label></div>
              <div class="form-field"><label>Digital Signature (Full Name)</label><input name="signature" value="${esc(info.signature || '')}"></div>
              <div class="form-field"><label>Date</label><input name="sign_date" type="date" value="${esc(info.sign_date || new Date().toISOString().split('T')[0])}"></div>
            </div>
          </fieldset>

          <div class="form-actions">
            <button type="button" class="btn-secondary" onclick="saveSetup(false)">Save Progress</button>
            <button type="submit" class="btn-primary">Submit</button>
          </div>
        </form>
      </div>`;

    initGeoFields('setup');
    const savedStateCode = info.state_code || info.state || '';
    const savedCountry = info.country || 'US';
    if (savedStateCode) {
      const geo = getGeo(savedCountry);
      const region = geo.regions.find(r => r.code === savedStateCode);
      const stateInput = document.getElementById('setup-state');
      if (region && stateInput) { stateInput.value = `${region.code} \u2014 ${region.name}`; stateInput.dataset.code = region.code; }
      else if (stateInput) { stateInput.value = savedStateCode; stateInput.dataset.code = savedStateCode; }
    }
  } catch (e) {
    el.innerHTML = `<div class="content-area"><div class="empty-state">Failed to load setup form</div></div>`;
  }
}

async function saveSetup(isSubmit) {
  const form = document.getElementById('setup-form');
  const data = {};
  new FormData(form).forEach((v, k) => { data[k] = v; });
  form.querySelectorAll('input[type=checkbox]').forEach(cb => { data[cb.name] = cb.checked; });
  const countryEl = document.getElementById('setup-country');
  if (countryEl) data.country = countryEl.value;
  const stateEl = document.getElementById('setup-state');
  if (stateEl) { data.state = stateEl.dataset.code || stateEl.value; data.state_code = stateEl.dataset.code || ''; }
  const zipEl = document.getElementById('setup-zip');
  if (zipEl) data.zip = zipEl.value;

  try {
    await api(`/clients/${state.userId}/setup`, { method: 'POST', body: data });
    showToast(isSubmit ? 'Setup information submitted!' : 'Progress saved', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── Client Overview (compatibility redirect) ────────────────────────────────
async function renderClientOverview(el) {
  navigateJourney(1);
}

/* ═══════════════════════════════════════════════════════════════════════════════
   ADMIN SHELL & VIEWS
   ═══════════════════════════════════════════════════════════════════════════════ */

function renderAdminShell(app, route) {
  const page = route.replace('admin/', '').replace('admin', '') || 'dashboard';
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>' },
    { id: 'clients', label: 'Clients', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>' },
    { id: 'rate-cards', label: 'Rate Cards', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>' },
    { id: 'zone-charts', label: 'Zone Charts', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>' },
    { id: 'accessorials', label: 'Accessorials', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1v22M1 12h22"/><circle cx="12" cy="12" r="8"/></svg>' },
    { id: 'pricing-config', label: 'Pricing Config', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>' },
    { id: 'induction-locations', label: 'Induction Sites', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" title="Induction Locations"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>' },
    { id: 'zone-skip', label: 'Zone Skip', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" title="Zone Skip Config"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg>' },
    { id: 'data-files', label: 'Data Files', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" title="Data Files Upload"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>' },
    { id: 'cost-overrides', label: 'Cost Overrides', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" title="Cost Overrides"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>' },
    { id: 'service-catalog', label: 'Service Catalog', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>' },
    { id: 'transit-times', label: 'Transit Times', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' },
    { id: 'documents', label: 'Documents', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>' },
    { id: 'settings', label: 'Settings', icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.604.852.997 1.51 1H21a2 2 0 0 1 0 4h-.09c-.658.003-1.25.396-1.51 1z"/></svg>' }
  ];

  app.innerHTML = `
    <div class="admin-layout">
      <aside class="admin-sidebar" id="admin-sidebar">
        <div class="sidebar-logo">${BR_LOGO_FULL}</div>
        <nav class="sidebar-nav">
          ${navItems.map(n => `
            <a href="#admin/${n.id}" class="sidebar-link ${page === n.id || (page.startsWith('client-') && n.id === 'clients') ? 'active' : ''}" title="${n.label}">
              ${n.icon}<span>${n.label}</span>${n.id === 'settings' ? '<span id="settings-badge" class="sidebar-badge" style="display:none;"></span>' : ''}
            </a>
          `).join('')}
        </nav>
        <div class="sidebar-footer">
          <div class="sidebar-user">
            <div class="avatar">${state.userName.charAt(0).toUpperCase()}</div>
            <div class="user-info"><div class="user-name">${esc(state.userName)}</div><div class="user-email">${esc(state.userEmail)}</div></div>
          </div>
        </div>
      </aside>
      <div class="admin-main-area">
        <header class="admin-header">
          <button class="hamburger" onclick="document.getElementById('admin-sidebar').classList.toggle('open')" aria-label="Menu" title="Toggle menu">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
          </button>
          <div class="admin-header-title" id="admin-header-title"></div>
          <div class="admin-header-right">
            <div class="notif-bell-wrap" id="notif-bell-wrap">
              <button class="icon-btn notif-bell-btn" id="notif-bell-btn" onclick="toggleNotifDropdown()" title="Notifications" aria-label="Notifications">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
                <span class="notif-badge hidden" id="notif-badge">0</span>
              </button>
              <div class="notif-dropdown hidden" id="notif-dropdown"></div>
            </div>
            <button data-theme-toggle onclick="toggleTheme()" aria-label="Toggle theme" title="Toggle dark/light mode" class="icon-btn">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            </button>
            <button class="btn-ghost" onclick="logout()">Logout</button>
          </div>
        </header>
        <main class="admin-main" id="admin-content"></main>
      </div>
    </div>`;

  const content = document.getElementById('admin-content');
  if (page === 'dashboard') renderAdminDashboard(content);
  else if (page === 'clients') renderAdminClients(content);
  else if (page.startsWith('client-')) renderAdminClientDetail(content, page.replace('client-', ''));
  else if (page === 'rate-cards') renderAdminRateCards(content);
  else if (page === 'zone-charts') renderAdminZoneCharts(content);
  else if (page === 'accessorials') renderAdminAccessorials(content);
  else if (page === 'pricing-config') renderAdminPricingConfig(content);
  else if (page === 'induction-locations') renderAdminInductionLocations(content);
  else if (page === 'zone-skip') renderAdminZoneSkip(content);
  else if (page === 'data-files') renderAdminDataFiles(content);
  else if (page === 'cost-overrides') renderAdminCostOverrides(content);
  else if (page === 'service-catalog') renderServiceCatalog(content);
  else if (page === 'transit-times') renderTransitTimes(content);
  else if (page === 'documents') renderAdminDocuments(content);
  else if (page === 'settings') renderAdminSettings(content);
  else renderAdminDashboard(content);

  // Load admin notifications bell
  loadAdminNotifications();

  // Load pending access request badge on Settings
  loadAccessRequestBadge();

  // Close notif dropdown on outside click
  document.addEventListener('click', function onOutsideClick(e) {
    const wrap = document.getElementById('notif-bell-wrap');
    if (wrap && !wrap.contains(e.target)) {
      const dd = document.getElementById('notif-dropdown');
      if (dd) dd.classList.add('hidden');
    }
  }, { once: false });
}

// ─── Admin Notification Bell ──────────────────────────────────────────────────
async function loadAccessRequestBadge() {
  try {
    const data = await api('/access-requests/pending-count');
    const badge = document.getElementById('settings-badge');
    if (!badge) return;
    if (data.count > 0) {
      badge.textContent = data.count;
      badge.style.display = '';
    } else {
      badge.style.display = 'none';
    }
  } catch (e) { /* ignore */ }
}

async function loadAdminNotifications() {
  try {
    const data = await api('/notifications');
    const badge = document.getElementById('notif-badge');
    if (!badge) return;
    const count = data.unread_count || 0;
    if (count > 0) {
      badge.textContent = count > 9 ? '9+' : count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
    // Store notifications for dropdown
    window._adminNotifs = data.notifications || [];
  } catch (e) {
    // Silent fail — notifications are non-critical
  }
}

function toggleNotifDropdown() {
  const dd = document.getElementById('notif-dropdown');
  if (!dd) return;
  const isHidden = dd.classList.contains('hidden');
  if (isHidden) {
    renderNotifDropdown(dd);
    dd.classList.remove('hidden');
  } else {
    dd.classList.add('hidden');
  }
}

function renderNotifDropdown(dd) {
  const notifs = window._adminNotifs || [];
  const typeLabels = {
    upload_received: 'New Upload',
    setup_submitted: 'Setup Submitted',
    data_confirmed: 'Data Confirmed',
    data_cleared: 'Re-upload',
    analysis_ready: 'Analysis Ready'
  };
  const typeIcons = {
    upload_received: '📤',
    setup_submitted: '📋',
    data_confirmed: '✅',
    data_cleared: '🔄',
    analysis_ready: '📊'
  };
  dd.innerHTML = `
    <div class="notif-dropdown-header">
      <span class="notif-dropdown-title">Notifications</span>
      ${notifs.some(n => !n.read) ? `<button class="btn-ghost btn-sm" onclick="markAllNotifsRead()">Mark all read</button>` : ''}
    </div>
    <div class="notif-dropdown-list">
      ${notifs.length === 0
        ? '<div class="notif-empty">No notifications</div>'
        : notifs.slice(0, 10).map(n => `
          <div class="notif-item ${n.read ? 'notif-read' : 'notif-unread'}" onclick="handleNotifClick(${n.id}, ${n.client_id})"
               title="Click to view client">
            <span class="notif-item-icon">${typeIcons[n.type] || '🔔'}</span>
            <div class="notif-item-body">
              <div class="notif-item-msg">${esc(n.message)}</div>
              <div class="notif-item-time">${formatTimeAgo(n.created_at)}</div>
            </div>
            ${!n.read ? '<span class="notif-dot"></span>' : ''}
          </div>
        `).join('')
      }
    </div>`;
}

async function handleNotifClick(notifId, clientId) {
  try {
    await api(`/notifications/${notifId}/read`, { method: 'POST', body: {} });
  } catch (e) {}
  document.getElementById('notif-dropdown')?.classList.add('hidden');
  if (clientId) navigate(`admin/client-${clientId}`);
}

async function markAllNotifsRead() {
  try {
    await api('/notifications/read-all', { method: 'POST', body: {} });
    const badge = document.getElementById('notif-badge');
    if (badge) badge.classList.add('hidden');
    window._adminNotifs = (window._adminNotifs || []).map(n => ({...n, read: 1}));
    const dd = document.getElementById('notif-dropdown');
    if (dd && !dd.classList.contains('hidden')) renderNotifDropdown(dd);
  } catch (e) {}
}

function formatTimeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const then = new Date(dateStr.replace(' ', 'T') + 'Z');
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + ' min ago';
  if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
  return Math.floor(diff / 86400) + 'd ago';
}

// ─── Admin Page Title Helper ──────────────────────────────────────────────────
function setAdminPageTitle(title, breadcrumbs) {
  const el = document.getElementById('admin-header-title');
  if (!el) return;
  if (breadcrumbs && breadcrumbs.length > 0) {
    const parts = breadcrumbs.map(b =>
      `<a href="${b.href}">${esc(b.label)}</a><span class="header-sep">/</span>`
    ).join('');
    el.innerHTML = parts + `<span class="header-current">${esc(title)}</span>`;
  } else {
    el.innerHTML = `<span class="header-current">${esc(title)}</span>`;
  }
}

// ─── Admin Dashboard ──────────────────────────────────────────────────────────
async function renderAdminDashboard(el) {
  setAdminPageTitle('Dashboard');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const dash = await api('/dashboard');
    const clients = await api('/clients');
    const pendingClients = clients.filter(c => c.status === 'Analysis Pending' && c.has_shipping_data);

    el.innerHTML = `
      <div class="admin-content">
        <h2 class="page-title">Dashboard</h2>
        <div class="kpi-grid kpi-grid-6">
          <div class="kpi-card"><div class="kpi-label">Total Clients</div><div class="kpi-value">${dash.total_clients}</div></div>
          <div class="kpi-card"><div class="kpi-label">Active Analyses</div><div class="kpi-value">${dash.active_analyses}</div></div>
          <div class="kpi-card"><div class="kpi-label">Pending Uploads</div><div class="kpi-value">${dash.pending_uploads}</div></div>
          <div class="kpi-card"><div class="kpi-label">Completed</div><div class="kpi-value">${dash.completed_analyses}</div></div>
          <div class="kpi-card kpi-card-accent" onclick="navigate('admin/rate-cards')" style="cursor:pointer;" title="Browse all rate cards">
            <div class="kpi-label">Rate Cards</div>
            <div class="kpi-value">${dash.total_rate_cards}</div>
            <div class="kpi-sub-label">across ${dash.active_carriers || '—'} carriers</div>
          </div>
          <div class="kpi-card kpi-card-accent" onclick="navigate('admin/zone-charts')" style="cursor:pointer;" title="View zone lookup tool">
            <div class="kpi-label">Zone Coverage</div>
            <div class="kpi-value kpi-value-sm">41,877</div>
            <div class="kpi-sub-label">US ZIPs + 1,698 CA FSAs</div>
          </div>
        </div>

        <!-- Quick Zone Lookup Widget -->
        <div class="card dash-zone-lookup" style="margin-bottom:var(--space-4);">
          <div class="card-header-row">
            <div style="display:flex;align-items:center;gap:var(--space-2);">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              <div class="card-label" style="margin-bottom:0;">Quick Zone Lookup</div>
            </div>
            <a href="#admin/zone-charts" class="btn-ghost btn-sm" title="Open full zone lookup tool">Full Tool →</a>
          </div>
          <div class="zone-lookup-inline">
            <input type="text" id="dash-zip-input" class="zone-lookup-input" placeholder="Enter ZIP or CA postal code (e.g. 10001 or M5V)" maxlength="10"
              oninput="dashZoneLookup(this.value)" autocomplete="off">
            <div id="dash-zone-results" class="zone-lookup-results"></div>
          </div>
        </div>

        ${pendingClients.length > 0 ? `
        <div class="card pending-reviews-card" style="margin-bottom: var(--space-4);">
          <div class="card-header-row">
            <div style="display:flex;align-items:center;gap:var(--space-2);">
              <div class="card-label" style="margin-bottom:0;">Pending Reviews</div>
              <span class="notif-badge-inline">${pendingClients.length}</span>
            </div>
          </div>
          <p style="font-size:var(--text-xs);color:var(--color-text-muted);margin-bottom:var(--space-3);">These clients have uploaded shipping data and are waiting for analysis.</p>
          <div class="pending-reviews-list">
            ${pendingClients.map(c => `
              <div class="pending-review-item">
                <div class="pending-review-info">
                  <span class="pending-review-company">${esc(c.company_name)}</span>
                  <span class="pending-review-meta">${c.shipping_summary ? (c.shipping_summary.row_count || c.shipping_summary.row_count) + ' shipments' : ''} &middot; ${formatDate(c.invited_at)}</span>
                </div>
                <button class="btn-primary btn-sm" onclick="navigate('admin/client-${c.id}')" title="Run analysis for ${esc(c.company_name)}">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                  Run Analysis
                </button>
              </div>
            `).join('')}
          </div>
        </div>` : ''}

        <div class="card">
          <div class="card-header-row">
            <div class="card-label">Recent Clients</div>
            <button class="btn-primary btn-sm" onclick="navigate('admin/clients')" title="View all clients">View All</button>
          </div>
          <div class="table-container">
            <table class="data-table">
              <thead><tr><th>Company</th><th>Email</th><th>Status</th><th>Invited</th></tr></thead>
              <tbody>
                ${clients.slice(0, 5).map(c => `
                  <tr class="clickable" onclick="navigate('admin/client-${c.id}')" title="View ${esc(c.company_name)}">
                    <td class="fw-500">${esc(c.company_name)}</td>
                    <td>${esc(c.email)}</td>
                    <td><span class="status-badge status-${c.status.toLowerCase().replace(/\s/g, '-')}">${esc(c.status)}</span></td>
                    <td>${formatDate(c.invited_at)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
        <div style="text-align:center">
          <button class="btn-secondary btn-sm" onclick="exportAllAnalyses()" title="Export all published analyses as CSV" style="margin-top:var(--space-3)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Export All Analyses
          </button>
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load dashboard</div></div>`;
  }
}

// ─── Dashboard Quick Zone Lookup ─────────────────────────────────────────────
let _dashZoneLookupTimer = null;

async function exportAllAnalyses() {
  try {
    const data = await api('/analyses/export');
    if (!data || data.length === 0) { showToast('No published analyses to export', 'info'); return; }
    const rows = [];
    rows.push(['Company','Contact','Email','Published Date','Total Shipments','Current Spend','BR Best Cost','Savings','Savings %'].join(','));
    for (const a of data) {
      const r = a.results || {};
      const s = r.summary || {};
      rows.push([
        '"' + (a.company_name||'').replace(/"/g,'""') + '"',
        '"' + (a.contact_name||'').replace(/"/g,'""') + '"',
        a.email||'',
        a.published_at||'',
        s.total_shipments||0,
        (s.current_total_cost||0).toFixed(2),
        (s.best_total_cost||0).toFixed(2),
        (s.total_savings||0).toFixed(2),
        s.savings_pct ? s.savings_pct.toFixed(1)+'%' : 'N/A'
      ].join(','));
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'broad-reach-all-analyses.csv';
    a.click();
    showToast('Exported ' + data.length + ' analyses', 'success');
  } catch (e) {
    showToast('Export failed: ' + e.message, 'error');
  }
}

function dashZoneLookup(val) {
  clearTimeout(_dashZoneLookupTimer);
  const resultsEl = document.getElementById('dash-zone-results');
  if (!resultsEl) return;
  const zip = val.trim();
  if (zip.length < 3) {
    resultsEl.innerHTML = '';
    return;
  }
  resultsEl.innerHTML = '<div class="zone-lookup-loading"><span class="spinner-sm"></span> Looking up zones...</div>';
  _dashZoneLookupTimer = setTimeout(async () => {
    try {
      const data = await api('/zones/lookup?zip=' + encodeURIComponent(zip));
      resultsEl.innerHTML = renderZoneLookupResult(data);
    } catch (e) {
      resultsEl.innerHTML = `<div class="zone-lookup-error">No zone data found for "${esc(zip)}"</div>`;
    }
  }, 300);
}

// ─── Admin Clients ────────────────────────────────────────────────────────────
async function renderAdminClients(el) {
  setAdminPageTitle('Clients');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const clients = await api('/clients');
    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Clients</h2>
          <button class="btn-primary btn-sm" onclick="showInviteClientModal()">+ Invite Client</button>
        </div>
        <div class="card">
          <div class="table-container">
            <table class="data-table">
              <thead><tr><th>Company</th><th>Contact</th><th>Email</th><th>Status</th><th>Data</th><th>Last Active</th><th>Invitation</th><th></th></tr></thead>
              <tbody>
                ${clients.map(c => `
                  <tr class="clickable">
                    <td class="fw-500" onclick="navigate('admin/client-${c.id}')">${esc(c.company_name)}</td>
                    <td onclick="navigate('admin/client-${c.id}')">${esc(c.contact_name)}</td>
                    <td onclick="navigate('admin/client-${c.id}')">${esc(c.email)}</td>
                    <td onclick="navigate('admin/client-${c.id}')"><span class="status-badge status-${c.status.toLowerCase().replace(/\s/g, '-')}">${esc(c.status)}</span></td>
                    <td onclick="navigate('admin/client-${c.id}')">${c.has_shipping_data ? '✓' : '—'}</td>
                    <td onclick="navigate('admin/client-${c.id}')">${relativeTime(c.last_login_at)}</td>
                    <td>${c.invitation_sent_at ? '<span class="badge badge-success" title="Sent ' + formatDate(c.invitation_sent_at) + '">Sent ✓</span>' : '<span class="badge badge-muted">Not sent</span>'}</td>
                    <td class="td-actions">
                      <button class="btn-secondary btn-xs" onclick="event.stopPropagation(); showSendInviteModal(${c.id})" title="Send invitation email">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                        ${c.invitation_sent_at ? 'Resend' : 'Send Invite'}
                      </button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
        <div style="margin-top:var(--space-4);text-align:center">
          <button class="btn-ghost btn-sm" onclick="toggleArchivedClients()" id="toggle-archived-btn">Show Archived Clients</button>
        </div>
        <div id="archived-clients-container" class="hidden"></div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load clients</div></div>`;
  }
}

async function showInviteClientModal() {
  const docs = await api('/documents');
  openModal('Invite New Client', `
    <form id="invite-form" onsubmit="event.preventDefault(); submitInvite()">
      <div class="form-grid modal-form">
        <div class="form-field span-2"><label>Company Name *</label><input name="company_name" required></div>
        <div class="form-field"><label>Client Email *</label><input name="email" type="email" required></div>
        <div class="form-field"><label>Contact Name</label><input name="contact_name"></div>
        <div class="form-field span-2"><label>Logo URL</label><input name="logo_url" placeholder="https://..."></div>
        <div class="form-field span-2">
          <label>Share Documents</label>
          <div class="checkbox-group">
            ${docs.map(d => `<label class="check-label"><input type="checkbox" name="doc_${d.id}" value="${d.id}"> ${esc(d.name)}</label>`).join('')}
          </div>
        </div>
      </div>
      <div class="modal-actions"><button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button><button type="submit" class="btn-primary">Invite</button></div>
    </form>
  `);
}

async function submitInvite() {
  const form = document.getElementById('invite-form');
  const fd = new FormData(form);
  const docIds = [];
  form.querySelectorAll('input[type=checkbox]:checked').forEach(cb => docIds.push(parseInt(cb.value)));
  try {
    await api('/clients', { method: 'POST', body: {
      company_name: fd.get('company_name'),
      email: fd.get('email'),
      contact_name: fd.get('contact_name'),
      logo_url: fd.get('logo_url'),
      documents: docIds
    }});
    closeModal();
    showToast('Client invited!', 'success');
    router();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── Send Invitation Email Modal ──────────────────────────────────────────────
let _inviteEmailData = null;

async function showSendInviteModal(clientId) {
  try {
    // Get the portal URL from current location
    const portalUrl = window.location.origin + window.location.pathname;

    // Generate invitation (creates password, builds email)
    const data = await api(`/clients/${clientId}/generate-invitation`, {
      method: 'POST',
      body: {
        portal_url: portalUrl,
        sender_name: state.userName || 'Craig'
      }
    });

    _inviteEmailData = { clientId, ...data };

    openModal('Send Invitation Email', `
      <div class="invite-email-preview">
        <div class="invite-email-meta">
          <div class="invite-meta-row">
            <span class="invite-meta-label">To:</span>
            <span class="invite-meta-value">${esc(data.client_name)} &lt;${esc(data.client_email)}&gt;</span>
          </div>
          <div class="invite-meta-row">
            <span class="invite-meta-label">Subject:</span>
            <span class="invite-meta-value fw-500">${esc(data.email_subject)}</span>
          </div>
          <div class="invite-meta-row">
            <span class="invite-meta-label">Login:</span>
            <span class="invite-meta-value">Google Sign-In (primary)</span>
          </div>
          <div class="invite-meta-row">
            <span class="invite-meta-label">Backup:</span>
            <span class="invite-meta-value" style="font-family:monospace;color:var(--color-text-muted);font-size:var(--text-xs)">${esc(data.password)}</span>
            <span style="font-size:var(--text-xs);color:var(--color-text-muted);margin-left:var(--space-2)">(fallback password — included as footnote in email)</span>
          </div>
        </div>
        <div class="invite-email-body-preview">
          <pre class="invite-email-pre">${esc(data.email_body)}</pre>
        </div>
        <div class="invite-email-note">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          This email will be sent from your Gmail account. The client will sign in with their Google account — a backup password is included as a footnote in case they can't use Google.
        </div>
        ${data.invite_count > 0 ? `
        <div class="invite-resend-warning">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          This client has been invited ${data.invite_count} time${data.invite_count > 1 ? 's' : ''} before${data.last_invited_at ? '. Last sent: ' + formatDate(data.last_invited_at) : ''}.
        </div>` : ''}
      </div>
      <div class="modal-actions">
        <button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="button" class="btn-primary" id="send-invite-btn" onclick="sendInvitationEmail()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          Send Invitation Email
        </button>
      </div>
    `, { wide: true });
  } catch (e) {
    showToast('Failed to generate invitation: ' + e.message, 'error');
  }
}

async function sendInvitationEmail() {
  if (!_inviteEmailData) return;
  const btn = document.getElementById('send-invite-btn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-sm"></span> Sending...';
  }
  try {
    // Queue the email for sending via the server
    await api(`/clients/${_inviteEmailData.clientId}/send-invitation`, {
      method: 'POST',
      body: {
        to_email: _inviteEmailData.client_email,
        to_name: _inviteEmailData.client_name,
        subject: _inviteEmailData.email_subject,
        body: _inviteEmailData.email_body
      }
    });

    closeModal();
    showToast('Invitation email sent to ' + _inviteEmailData.client_name + '!', 'success');
    _inviteEmailData = null;
    router();
  } catch (e) {
    showToast('Failed: ' + e.message, 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> Send Invitation Email';
    }
  }
}

// ─── Admin Client Detail ──────────────────────────────────────────────────────
async function renderAdminClientDetail(el, clientId) {
  setAdminPageTitle('Loading…', [{label: 'Clients', href: '#admin/clients'}]);
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const client = await api(`/clients/${clientId}`);
    setAdminPageTitle('Analysis Workbench — ' + client.company_name, [{label: 'Clients', href: '#admin/clients'}]);
    const allDocs = await api('/documents');
    const rateCards = await api('/rate-cards');
    const zoneCharts = await api('/zone-charts').catch(() => []);

    el.innerHTML = `
      <div class="admin-content">
        <div class="breadcrumb">
          <a href="#admin/clients">Clients</a> <span>/</span> <span>${esc(client.company_name)}</span>
        </div>

        <div class="client-detail-header">
          <div style="width:44px;height:44px;border-radius:12px;background:var(--color-primary-highlight);display:flex;align-items:center;justify-content:center;flex-shrink:0;">
            <span style="font-size:18px;font-weight:700;color:var(--color-primary);">${esc(client.company_name.charAt(0))}</span>
          </div>
          <div>
            <h2 class="page-title">${esc(client.company_name)}</h2>
            <div class="client-meta">${esc(client.email)} · ${esc(client.contact_name)} · <span class="status-badge status-${client.status.toLowerCase().replace(/\s/g, '-')}">${esc(client.status)}</span></div>
          </div>
          <button class="btn-ghost btn-sm" onclick="showEditClientModal(${clientId}, ${JSON.stringify({company_name: client.company_name, email: client.email, contact_name: client.contact_name, logo_url: client.logo_url || ''}).replace(/"/g, '&quot;')})" title="Edit client info" style="margin-left:auto">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            Edit
          </button>
          <button class="btn-ghost btn-sm" onclick="archiveClient(${clientId}, '${esc(client.company_name)}')" title="Archive this client" style="color:var(--color-danger);">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            Archive
          </button>
        </div>

        <!-- Documents Section -->
        <div class="card">
          <div class="card-header-row"><div class="card-label">Shared Documents</div><button class="btn-secondary btn-sm" onclick="showAssignDocsModal(${clientId}, ${JSON.stringify(client.documents_json).replace(/"/g, '&quot;')})">Manage</button></div>
          ${client.documents_json.length > 0
            ? `<div class="tag-list">${allDocs.filter(d => client.documents_json.includes(d.id)).map(d => `<span class="badge">${esc(d.name)}</span>`).join('')}</div>`
            : '<div class="empty-inline">No documents shared</div>'}
        </div>

        <!-- Shipping Data Section -->
        <div class="card">
          <div class="card-header-row"><div class="card-label">Shipping Data</div></div>
          ${client.shipping_data ? `
            <div class="upload-summary-grid">
              <div class="upload-stat"><span class="stat-label">Rows</span><span class="stat-value">${client.shipping_data.row_count}</span></div>
              <div class="upload-stat"><span class="stat-label">Spend</span><span class="stat-value">${formatCurrency(client.shipping_data.summary.total_spend, client.shipping_data.summary.currency)}</span></div>
              <div class="upload-stat"><span class="stat-label">Avg Actual Wt</span><span class="stat-value">${client.shipping_data.summary.avg_weight} ${client.shipping_data.summary.weight_unit || 'lbs'}</span></div>
              <div class="upload-stat"><span class="stat-label">Avg Billed Wt</span><span class="stat-value">${client.shipping_data.summary.avg_billed_weight || client.shipping_data.summary.avg_weight} ${client.shipping_data.summary.weight_unit || 'lbs'}</span></div>
              <div class="upload-stat"><span class="stat-label">Carriers</span><span class="stat-value">${(client.shipping_data.summary.carriers || []).join(', ')}</span></div>
            </div>
            ${client.shipping_data.summary.unit_system ? `<div class="upload-meta-tags">
              <span class="meta-tag">Currency: ${getCurrencyLabel(client.shipping_data.summary.currency || 'USD')}</span>
              <span class="meta-tag">Weight: ${client.shipping_data.summary.unit_system.weight === 'kg' ? 'Kilograms' : 'Pounds'}</span>
              <span class="meta-tag">Dimensions: ${client.shipping_data.summary.unit_system.dimensions === 'cm' ? 'Centimeters' : 'Inches'}</span>
              ${client.shipping_data.summary.origin_defaults?.state ? `<span class="meta-tag">Default origin: ${client.shipping_data.summary.origin_defaults.state} ${client.shipping_data.summary.origin_defaults.zip || ''} ${client.shipping_data.summary.origin_defaults.country || ''}</span>` : ''}
            </div>` : ''}
            <details class="data-details">
              <summary class="btn-ghost btn-sm">View Raw Data (${client.shipping_data.row_count} rows)</summary>
              <div class="table-container">
                <table class="data-table compact">
                  <thead><tr><th>Date</th><th>Carrier</th><th>Service</th><th>Actual Wt</th><th>Billed Wt</th><th>Origin</th><th>Dest</th><th>Price</th></tr></thead>
                  <tbody>
                    ${client.shipping_data.data.slice(0, 50).map(s => `
                      <tr><td>${esc(s.ship_date || '—')}</td><td>${esc(s.carrier)}</td><td>${esc(s.service)}</td><td class="num">${s.weight}</td><td class="num">${s.billed_weight || '—'}</td><td>${esc(s.origin_state)}</td><td>${esc(s.dest_state)}</td><td class="num">${formatCurrency(s.price, client.shipping_data.summary.currency)}</td></tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            </details>
          ` : '<div class="empty-inline">No shipping data uploaded yet</div>'}
        </div>

        <!-- Analysis Section -->
        <div class="card" id="analysis-section">
          <div class="card-header-row"><div class="card-label">Analysis Workbench</div></div>
          ${client.shipping_data ? `
            <!-- Step 1: Rate Card Selection -->
            <div class="workbench-step">
              <div class="workbench-step-header">
                <div class="workbench-step-num">1</div>
                <div class="workbench-step-title">Rate Card Selection</div>
              </div>
              <p class="workbench-step-desc">Select rate cards to include in the comparison analysis.</p>
              <!-- Rate Card Search Filter -->
              <div class="wb-rc-search-row">
                <div class="rc-search-input-wrap" style="flex:1;">
                  <svg class="rc-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                  <input type="text" id="wb-rc-search" class="rc-search-input" placeholder="Filter rate cards…" oninput="filterWbRateCards()" autocomplete="off">
                </div>
                <span class="wb-rc-selected-count" id="wb-rc-selected-count"></span>
              </div>
              <div class="wb-carrier-filter" id="wb-carrier-filter"></div>
              <div class="rc-toggle-grid" id="rc-toggle-grid">
                ${(() => {
                  const wbCarrierOrder = ['USPS','UPS','UPS Canada','FedEx','DHL','OSM','Amazon','UniUni','Canada Post','Asendia'];
                  const wbByCarrier = {};
                  rateCards.forEach(rc => {
                    const carrier = rc.carrier || 'Other';
                    if (!wbByCarrier[carrier]) wbByCarrier[carrier] = [];
                    wbByCarrier[carrier].push(rc);
                  });
                  const wbSorted = Object.keys(wbByCarrier).sort((a, b) => {
                    const ai = wbCarrierOrder.indexOf(a), bi = wbCarrierOrder.indexOf(b);
                    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
                  });
                  return wbSorted.map(carrier => {
                    const cards = wbByCarrier[carrier];
                    const selectedCount = cards.filter(rc => client.analysis?.config?.rate_card_ids?.includes(rc.id)).length;
                    return `
                    <div class="wb-carrier-section wb-expanded" data-wb-carrier="${carrier}">
                      <div class="wb-carrier-header" onclick="this.parentElement.classList.toggle('wb-expanded')">
                        <div class="wb-carrier-header-left">
                          <svg class="wb-carrier-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                          <div class="wb-carrier-label">${esc(carrier)}</div>
                          <span class="wb-carrier-count">${cards.length} card${cards.length !== 1 ? 's' : ''}</span>
                          ${selectedCount > 0 ? `<span class="wb-carrier-selected-badge" title="${selectedCount} selected">${selectedCount} selected</span>` : ''}
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;">
                          <span class="wb-select-all" onclick="event.stopPropagation();toggleCarrierAll('${carrier}')" title="Select or deselect all ${carrier} cards">Toggle all</span>
                        </div>
                      </div>
                      <div class="wb-carrier-cards">
                        ${cards.map(rc => {
                          const isSelected = false;  // Nothing preselected — user must click to select
                          const pType = rc.pricing_type === 'CUBICFEET' ? 'Cubic' : rc.pricing_type === 'WEIGHT_OUNCES' ? 'Oz' : 'Wt';
                          return `
                          <div class="rc-toggle-card ${isSelected ? 'rc-toggle-selected' : ''}" data-rc-id="${rc.id}" data-rc-name="${esc(rc.name.toLowerCase())}" data-rc-carrier="${esc((rc.carrier||'').toLowerCase())}" onclick="toggleRateCard(this, ${rc.id})" title="${esc(rc.name)} — ${rc.zone_count} zones · ${rc.weight_count} wt breaks · DIM÷${rc.dim_divisor || 166}">
                            <div class="rc-toggle-check"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg></div>
                            <div class="rc-toggle-info">
                              <div class="rc-toggle-name">${esc(rc.name)}</div>
                              <div class="rc-toggle-meta">${pType} · DIM÷${rc.dim_divisor || 166} · ${rc.currency || 'USD'}${rc.country === 'CA' ? ' 🇨🇦' : ''} ${rc.zone_key ? '· <span class="rc-zone-key" title="Zone data source">' + esc(rc.zone_key) + '</span>' : ''}</div>
                            </div>
                          </div>`;
                        }).join('')}
                      </div>
                    </div>`;
                  }).join('');
                })()}
              </div>
            </div>

            <!-- Step 2: Markup Configuration -->
            <div class="workbench-step">
              <div class="workbench-step-header">
                <div class="workbench-step-num">2</div>
                <div class="workbench-step-title">Markup Configuration</div>
                <button class="btn-secondary btn-sm" onclick="applyMarkupToAll()" title="Copy the first rate card's markup values to all selected rate cards" style="margin-left:auto;">Apply to All</button>
              </div>
              <p class="workbench-step-desc">Set markup for each selected rate card. Click any card to expand sliders. Metrics update live from shipment data.</p>

              <!-- Markup Formula Reference -->
              <div class="markup-formula-bar">
                <span class="markup-formula-label">Formula:</span>
                <code class="markup-formula">Final Price = (Base Rate × (1 + <em>%</em>)) + (Billable Wt × <em>$/lb</em>) + <em>$/piece</em></code>
              </div>

              <div id="markup-fields">
                ${rateCards.map(rc => {
                  const m = client.analysis?.config?.markups?.[String(rc.id)] || { pct: 0.15, per_lb: 0.10, per_shipment: 1.00 };
                  const isSelected = false;  // Start inactive until card is selected
                  const pctVal = (m.pct * 100).toFixed(0);
                  return `
                  <div class="markup-panel ${isSelected ? '' : 'markup-panel-inactive'}" data-rc-id="${rc.id}" id="markup-panel-${rc.id}">
                    <div class="markup-panel-header" onclick="this.parentElement.classList.toggle('markup-expanded')">
                      <div class="markup-panel-name">${esc(rc.name)}</div>
                      <div class="markup-metrics-row" id="preview-${rc.id}">
                        <div class="markup-metric">
                          <div class="markup-metric-label">Cost</div>
                          <div class="markup-metric-value" id="preview-cost-${rc.id}"><span class="metric-loading"><span class="spinner-dot"></span></span></div>
                        </div>
                        <div class="markup-metric-arrow">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
                        </div>
                        <div class="markup-metric">
                          <div class="markup-metric-label">Sell</div>
                          <div class="markup-metric-value accent" id="preview-sell-${rc.id}"><span class="metric-loading"><span class="spinner-dot"></span></span></div>
                        </div>
                        <div class="markup-metric-eq">=</div>
                        <div class="markup-metric">
                          <div class="markup-metric-label">Margin</div>
                          <div class="markup-metric-value" id="preview-margin-${rc.id}"><span class="metric-loading"><span class="spinner-dot"></span></span></div>
                          <div class="markup-metric-sub" id="preview-margin-pct-${rc.id}"></div>
                        </div>
                      </div>
                      <div class="markup-panel-chevron"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg></div>
                    </div>
                    <div class="markup-panel-controls">
                      <div class="markup-control-card">
                        <div class="markup-control-top">
                          <label class="markup-control-label">Percentage</label>
                          <span class="markup-big-value" id="pct-display-${rc.id}">${pctVal}%</span>
                        </div>
                        <input type="range" class="markup-range markup-pct" min="0" max="50" step="1"
                               value="${pctVal}"
                               oninput="syncMarkup(${rc.id}, 'pct', this.value)">
                        <div class="markup-range-labels">
                          <span>0%</span>
                          <input type="number" id="pct-num-${rc.id}" class="markup-inline-num markup-pct-num" step="1" min="0" max="50"
                                 value="${pctVal}"
                                 oninput="syncMarkup(${rc.id}, 'pct', this.value)">
                          <span>50%</span>
                        </div>
                      </div>
                      <div class="markup-control-card">
                        <div class="markup-control-top">
                          <label class="markup-control-label">Per Pound</label>
                          <span class="markup-big-value" id="lb-display-${rc.id}">$${Number(m.per_lb).toFixed(2)}</span>
                        </div>
                        <input type="range" class="markup-range markup-lb-range" min="0" max="1" step="0.01"
                               value="${m.per_lb}"
                               oninput="syncMarkup(${rc.id}, 'lb', this.value)">
                        <div class="markup-range-labels">
                          <span>$0</span>
                          <input type="number" id="lb-num-${rc.id}" class="markup-inline-num markup-lb" step="0.01" min="0" max="5"
                                 value="${m.per_lb}"
                                 oninput="syncMarkup(${rc.id}, 'lb', this.value)">
                          <span>$1.00</span>
                        </div>
                      </div>
                      <div class="markup-control-card">
                        <div class="markup-control-top">
                          <label class="markup-control-label">Per Piece</label>
                          <span class="markup-big-value" id="ship-display-${rc.id}">$${Number(m.per_shipment).toFixed(2)}</span>
                        </div>
                        <input type="range" class="markup-range markup-ship-range" min="0" max="5" step="0.05"
                               value="${m.per_shipment}"
                               oninput="syncMarkup(${rc.id}, 'ship', this.value)">
                        <div class="markup-range-labels">
                          <span>$0</span>
                          <input type="number" id="ship-num-${rc.id}" class="markup-inline-num markup-ship" step="0.01" min="0" max="20"
                                 value="${m.per_shipment}"
                                 oninput="syncMarkup(${rc.id}, 'ship', this.value)">
                          <span>$5.00</span>
                        </div>
                      </div>
                    </div>
                  </div>`;
                }).join('')}
              </div>
            </div>

            <!-- Step 3: First & Middle Mile Costs -->
            <div class="workbench-step">
              <div class="workbench-step-header">
                <div class="workbench-step-num">3</div>
                <div class="workbench-step-title">First &amp; Middle Mile Costs</div>
              </div>
              <p class="workbench-step-desc">Logistics costs deducted from margin in the profitability analysis.</p>
              
              <div class="fmm-cost-grid">
                <div class="fmm-cost-card">
                  <div class="fmm-cost-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>
                  </div>
                  <label class="fmm-label">Daily Pickup / Line-Haul Cost</label>
                  <p class="fmm-desc">The daily cost of first mile pickup and middle mile transportation for this account.</p>
                  <div class="fmm-input-row">
                    <span class="fmm-prefix">$</span>
                    <input type="number" id="fmm-daily-cost" class="fmm-input" value="0" min="0" step="1" placeholder="0.00"
                           oninput="updateProfitabilityPreview()">
                    <span class="fmm-suffix">/ day</span>
                  </div>
                </div>
                
                <div class="fmm-cost-card">
                  <div class="fmm-cost-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                  </div>
                  <label class="fmm-label">Pickup Days Per Year</label>
                  <p class="fmm-desc">Business days per year this account has scheduled pickups.</p>
                  <div class="fmm-input-row">
                    <input type="number" id="fmm-pickup-days" class="fmm-input" value="250" min="1" max="365" step="1"
                           oninput="updateProfitabilityPreview()">
                    <span class="fmm-suffix">days / year</span>
                  </div>
                </div>
                
                <div class="fmm-cost-card">
                  <div class="fmm-cost-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                  </div>
                  <label class="fmm-label">Handling Cost Per Piece</label>
                  <p class="fmm-desc">Sorting, handling, and cross-docking cost per shipment at the facility.</p>
                  <div class="fmm-input-row">
                    <span class="fmm-prefix">$</span>
                    <input type="number" id="fmm-handling-cost" class="fmm-input" value="0" min="0" step="0.01" placeholder="0.00"
                           oninput="updateProfitabilityPreview()">
                    <span class="fmm-suffix">/ piece</span>
                  </div>
                </div>

                <div class="fmm-cost-card">
                  <div class="fmm-cost-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
                  </div>
                  <label class="fmm-label">Est. Daily Volume</label>
                  <p class="fmm-desc">Estimated shipments per pickup day. Used for daily/weekly/monthly/annual projections.</p>
                  <div class="fmm-input-row">
                    <input type="number" id="fmm-daily-volume" class="fmm-input" value="1" min="1" step="1" placeholder="1"
                           oninput="updateProfitabilityPreview()">
                    <span class="fmm-suffix">pieces / day</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Step 4: Advanced Settings -->
            <div class="workbench-step">
              <div class="workbench-step-header">
                <div class="workbench-step-num">4</div>
                <div class="workbench-step-title">Advanced Settings</div>
              </div>
              <div class="form-grid" style="margin-top:8px;">
                <div class="form-field">
                  <label style="display:flex;align-items:center;gap:6px;">DIM Divisor
                    <span class="tooltip-icon" title="Each rate card uses its own DIM divisor. Override here to use a single value for all cards in this analysis.">?</span>
                  </label>
                  <select id="analysis-dim-divisor">
                    <option value="" ${!client.analysis?.config?.dim_divisor ? 'selected' : ''}>Auto (per rate card)</option>
                    <option value="166" ${client.analysis?.config?.dim_divisor == 166 ? 'selected' : ''}>166 — USPS / DHL / OSM</option>
                    <option value="139" ${client.analysis?.config?.dim_divisor == 139 ? 'selected' : ''}>139 — FedEx / UPS</option>
                    <option value="225" ${client.analysis?.config?.dim_divisor == 225 ? 'selected' : ''}>225 — Amazon</option>
                    <option value="custom" ${client.analysis?.config?.dim_divisor && client.analysis.config.dim_divisor != 166 && client.analysis.config.dim_divisor != 139 && client.analysis.config.dim_divisor != 225 ? 'selected' : ''}>Custom...</option>
                  </select>
                  <input type="number" id="analysis-dim-custom" placeholder="Enter divisor" step="0.1" min="1"
                    class="${client.analysis?.config?.dim_divisor && client.analysis.config.dim_divisor != 166 && client.analysis.config.dim_divisor != 139 ? '' : 'hidden'}"
                    value="${client.analysis?.config?.dim_divisor && client.analysis.config.dim_divisor != 166 && client.analysis.config.dim_divisor != 139 ? client.analysis.config.dim_divisor : ''}"
                    style="margin-top:4px;">
                </div>
                <div class="form-field">
                  <label style="display:flex;align-items:center;gap:6px;">Zone Chart
                    <span class="tooltip-icon" title="Select a zone chart for ZIP-to-zone lookup. Auto uses heuristic zone detection from shipment data.">?</span>
                  </label>
                  <select id="analysis-zone-chart">
                    <option value="">Auto (heuristic detection)</option>
                    ${zoneCharts.map(zc => `<option value="${zc.id}" ${client.analysis?.config?.zone_chart_id == zc.id ? 'selected' : ''}>${esc(zc.name)}${zc.carrier ? ' — ' + esc(zc.carrier) : ''}</option>`).join('')}
                  </select>
                </div>
              </div>
            </div>

            <!-- Live Analysis Status + Publish Row -->
            <div class="workbench-run-row">
              <div class="live-analysis-status" id="live-analysis-status">
                <span class="live-dot"></span>
                <span class="live-label">Live Analysis</span>
              </div>
              ${client.analysis ? `
              ${(() => { const daysOld = Math.floor((Date.now() - new Date(client.analysis.created_at)) / 86400000); return daysOld > 30 ? `<span class="analysis-stale-badge">⚠ Analysis is ${daysOld} days old — consider re-running</span>` : ''; })()}
              <button class="btn-publish" onclick="confirmPublishAnalysis(${clientId}, '${esc(client.company_name)}')" ${client.analysis.status === 'published' ? 'disabled' : ''} title="Publish this analysis so ${esc(client.company_name)} can view it">
                ${client.analysis.status === 'published'
                  ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Published'
                  : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg> Publish & Notify Client'}
              </button>
              <button class="btn-secondary btn-sm" onclick="previewClientExcel()" title="Preview the Excel file the client will receive" style="margin-left:4px;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                Preview Client Excel
              </button>` : ''}
            </div>

            <div id="analysis-results">
            ${client.analysis?.results?.summary ? renderAnalysisResults(client.analysis.results) : ''}
            </div>
          ` : '<div class="empty-inline">Upload shipping data first to configure analysis</div>'}
        </div>        </div>

        <!-- Analysis History -->
        <div class="card" id="analysis-history-section">
          <div class="card-header-row">
            <div class="card-label">Analysis History</div>
          </div>
          <div id="analysis-history-list"><span class="text-muted" style="font-size:13px;">Loading history...</span></div>
        </div>

        <!-- Setup Info Section -->
        <div class="card">
          <div class="card-header-row"><div class="card-label">Setup Information</div></div>
          ${Object.keys(client.setup_info_json || {}).length > 0 ? `
            <div class="setup-info-preview">
              ${Object.entries(client.setup_info_json).filter(([k, v]) => v && v !== false).map(([k, v]) =>
                `<div class="info-row"><span class="info-key">${k.replace(/_/g, ' ')}</span><span class="info-val">${typeof v === 'boolean' ? '✓' : esc(String(v))}</span></div>`
              ).join('')}
            </div>
          ` : '<div class="empty-inline">Client has not submitted setup information yet</div>'}
        </div>
      </div>`;

    // Wire up DIM divisor custom toggle
    const dimSel = document.getElementById('analysis-dim-divisor');
    const dimCustom = document.getElementById('analysis-dim-custom');
    if (dimSel && dimCustom) {
      dimSel.addEventListener('change', () => {
        dimCustom.classList.toggle('hidden', dimSel.value !== 'custom');
        if (dimSel.value !== 'custom') dimCustom.value = '';
      });
    }
    // Store clientId globally for live analysis
    window._workbenchClientId = clientId;
    window._workbenchCompanyName = client.company_name;
    window._workbenchAnalysisPublished = client.analysis?.status === 'published';
    // Only auto-run analysis if client has shipping data AND previously saved rate card selections
    if (client.shipping_data && client.analysis?.config?.rate_card_ids?.length > 0) {
      autoRunAnalysis(clientId, rateCards, client);
    } else if (client.shipping_data) {
      // No saved selections — show empty state prompting admin to select rate cards
      const resultsEl = document.getElementById('analysis-results');
      if (resultsEl) {
        resultsEl.innerHTML = renderAnalysisEmptyState();
      }
    }
    // Load analysis history
    loadAnalysisHistory(clientId);
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load client: ${e.message}</div></div>`;
  }
}

// ─── Analysis History ─────────────────────────────────────────────────────────
async function loadAnalysisHistory(clientId) {
  const el = document.getElementById('analysis-history-list');
  if (!el) return;
  try {
    const history = await api(`/clients/${clientId}/analysis-history`);
    if (!history || history.length === 0) {
      el.innerHTML = '<span class="text-muted" style="font-size:13px;">No analyses yet</span>';
      return;
    }
    const currency = history[0]?.total_sell != null ? 'USD' : 'USD';
    el.innerHTML = `
      <table class="data-table compact" style="font-size:13px;">
        <thead>
          <tr>
            <th>Version</th>
            <th>Date</th>
            <th>Status</th>
            <th>Our Price</th>
            <th>Client Spend</th>
            <th>Savings</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${history.map((h, i) => {
            const ver = history.length - i;
            const isLatest = i === 0;
            const statusBadge = h.status === 'published'
              ? '<span class="badge" style="background:#dcfce7;color:#166534;font-size:11px;">Published</span>'
              : '<span class="badge" style="background:#f3f4f6;color:#6b7280;font-size:11px;">Draft</span>';
            return `<tr style="${isLatest ? 'font-weight:500;' : ''}">
              <td>v${ver}${isLatest ? ' <span style="color:var(--color-primary);font-size:11px;">(latest)</span>' : ''}</td>
              <td>${formatDate(h.created_at)}</td>
              <td>${statusBadge}${h.published_at ? ' <span style="font-size:11px;color:var(--text-muted);">(' + formatDate(h.published_at) + ')</span>' : ''}</td>
              <td class="num">${h.total_sell != null ? formatCurrency(h.total_sell) : '—'}</td>
              <td class="num">${h.total_spend != null ? formatCurrency(h.total_spend) : '—'}</td>
              <td class="num">${h.total_savings != null ? formatCurrency(h.total_savings) : '—'}${h.savings_pct != null ? ' <span style="font-size:11px;color:var(--color-success);">(' + (h.savings_pct * 100).toFixed(1) + '%)</span>' : ''}</td>
              <td>
                <button class="btn-ghost btn-sm" onclick="viewAnalysisVersion(${clientId}, ${h.id})" title="View this analysis version">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  View
                </button>
                <button class="btn-ghost btn-sm" onclick="downloadAnalysisVersion(${clientId}, ${h.id})" title="Download Excel for this version">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </button>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>`;
  } catch (e) {
    el.innerHTML = `<span class="text-muted" style="font-size:13px;">Could not load analysis history</span>`;
  }
}

async function viewAnalysisVersion(clientId, analysisId) {
  try {
    const analysis = await api(`/clients/${clientId}/analysis/${analysisId}`);
    const resultsEl = document.getElementById('analysis-results');
    if (resultsEl && analysis.results?.summary) {
      resultsEl.innerHTML = renderAnalysisResults(analysis.results);
      resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      showToast(`Viewing analysis from ${formatDate(analysis.created_at)}`, 'info');
    }
  } catch (e) { showToast(e.message, 'error'); }
}

function downloadAnalysisVersion(clientId, analysisId) {
  const url = API + `/clients/${clientId}/analysis-excel?role=admin&analysis_id=${analysisId}` + (state.token ? `&token=${encodeURIComponent(state.token)}` : '');
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function showAssignDocsModal(clientId, currentDocs) {
  const docs = await api('/documents');
  openModal('Manage Documents', `
    <form id="assign-docs-form" onsubmit="event.preventDefault(); submitAssignDocs(${clientId})">
      <div class="checkbox-group modal-form">
        ${docs.map(d => `<label class="check-label"><input type="checkbox" value="${d.id}" ${currentDocs.includes(d.id) ? 'checked' : ''}> ${esc(d.name)} <span class="text-muted">(${esc(d.category)})</span></label>`).join('')}
      </div>
      <div class="modal-actions"><button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button><button type="submit" class="btn-primary">Save</button></div>
    </form>
  `);
}

async function submitAssignDocs(clientId) {
  const form = document.getElementById('assign-docs-form');
  const ids = [];
  form.querySelectorAll('input:checked').forEach(cb => ids.push(parseInt(cb.value)));
  try {
    await api(`/clients/${clientId}/documents`, { method: 'POST', body: { document_ids: ids } });
    closeModal();
    showToast('Documents updated', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

function showEditClientModal(clientId, info) {
  openModal('Edit Client Info', `
    <form id="edit-client-form" class="form-grid" style="gap:var(--space-3);">
      <div class="form-field"><label>Company Name *</label><input name="company_name" value="${esc(info.company_name)}" required></div>
      <div class="form-field"><label>Client Email *</label><input name="email" type="email" value="${esc(info.email)}" required></div>
      <div class="form-field"><label>Contact Name</label><input name="contact_name" value="${esc(info.contact_name || '')}"></div>
      <div class="form-field span-2"><label>Logo URL</label><input name="logo_url" value="${esc(info.logo_url || '')}" placeholder="https://..."></div>
      <div class="modal-actions" style="grid-column:1/-1;">
        <button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn-primary">Save Changes</button>
      </div>
    </form>
  `);
  document.getElementById('edit-client-form').onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api('/clients/' + clientId, { method: 'PUT', body: {
        company_name: fd.get('company_name'),
        email: fd.get('email'),
        contact_name: fd.get('contact_name'),
        logo_url: fd.get('logo_url')
      }});
      closeModal();
      showToast('Client info updated', 'success');
      router();
    } catch (err) {
      showToast('Failed to update: ' + err.message, 'error');
    }
  };
}


async function archiveClient(clientId, companyName) {
  if (!confirm('Archive ' + companyName + '? They will be hidden from the active clients list.')) return;
  try {
    await api('/clients/' + clientId + '/archive', { method: 'POST', body: { archived: true } });
    showToast(companyName + ' archived', 'success');
    navigate('admin/clients');
  } catch (e) {
    showToast('Failed: ' + e.message, 'error');
  }
}
async function restoreClient(clientId, companyName) {
  try {
    await api('/clients/' + clientId + '/archive', { method: 'POST', body: { archived: false } });
    showToast(companyName + ' restored', 'success');
    router();
  } catch (e) {
    showToast('Failed: ' + e.message, 'error');
  }
}

async function toggleArchivedClients() {
  const container = document.getElementById('archived-clients-container');
  const btn = document.getElementById('toggle-archived-btn');
  if (!container || !btn) return;
  if (!container.classList.contains('hidden')) {
    container.classList.add('hidden');
    btn.textContent = 'Show Archived Clients';
    return;
  }
  try {
    const archived = await api('/archived-clients');
    if (!archived || archived.length === 0) {
      container.innerHTML = '<p class="text-muted" style="text-align:center;padding:var(--space-3)">No archived clients</p>';
    } else {
      container.innerHTML = '<div class="table-container"><table class="data-table"><thead><tr><th>Company</th><th>Contact</th><th>Email</th><th>Actions</th></tr></thead><tbody>' +
        archived.map(c => `<tr><td>${esc(c.company_name)}</td><td>${esc(c.contact_name || '')}</td><td>${esc(c.email)}</td><td><button class="btn-ghost btn-xs" onclick="restoreClient(${c.id}, '${esc(c.company_name)}')" >Restore</button></td></tr>`).join('') +
        '</tbody></table></div>';
    }
    container.classList.remove('hidden');
    btn.textContent = 'Hide Archived Clients';
  } catch (e) {
    showToast('Failed to load archived clients', 'error');
  }
}

function renderAnalysisResults(results) {
  try {
    const s = results.summary || {};
    const cur = results.currency || 'USD';
    const byZone = results.by_zone || {};
    const byCarrier = results.by_carrier || {};
    const byService = results.by_service || {};
    const byWeightBand = results.by_weight_band || {};
    const brMix = results.br_service_mix || {};
    const pivot = results.zone_weight_pivot || {};
    const zones = Object.keys(byZone).sort((a, b) => parseInt(a) - parseInt(b));
    const carriers = Object.keys(byCarrier).sort((a, b) => (byCarrier[b].original || 0) - (byCarrier[a].original || 0));
    const serviceKeys = Object.keys(byService).sort((a, b) => (byService[b].original || 0) - (byService[a].original || 0));
    const wBandOrder = ['0-1 lbs', '1-2 lbs', '2-5 lbs', '5-10 lbs', '10-20 lbs', '20-40 lbs', '40+ lbs'];
    const wBands = wBandOrder.filter(w => byWeightBand[w]);
    const mixKeys = Object.keys(brMix).sort((a, b) => (brMix[b].count || 0) - (brMix[a].count || 0));
    const savingsPositive = (s.total_savings || 0) > 0;

    // Zone x Weight Pivot
    const pivotZones = [...new Set(Object.values(pivot).flatMap(wb => Object.keys(wb)))].sort((a, b) => parseInt(a) - parseInt(b));
    const pivotBands = wBandOrder.filter(w => pivot[w]);

    // Compute date range from shipments
    const shipDates = (results.shipments || []).map(sh => sh.ship_date).filter(Boolean).sort();
    const dateRangeStr = shipDates.length > 1
      ? shipDates[0] + ' to ' + shipDates[shipDates.length - 1]
      : shipDates.length === 1 ? shipDates[0] : '';

    return `
    <div class="analysis-results-v2">
      <!-- Executive Summary KPI Bar -->
      <div class="kpi-bar">
        <div class="kpi-card-v2">
          <div class="kpi-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></div>
          <div class="kpi-content"><div class="kpi-number">${formatCurrency(s.total_original || 0, cur)}</div><div class="kpi-label-v2">Current Spend</div><div class="kpi-sub">${s.shipment_count || 0} shipments${dateRangeStr ? ' &middot; ' + dateRangeStr : ''}</div></div>
        </div>
        <div class="kpi-card-v2 accent">
          <div class="kpi-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg></div>
          <div class="kpi-content"><div class="kpi-number">${formatCurrency(s.total_br || 0, cur)}</div><div class="kpi-label-v2">BR Price</div><div class="kpi-sub">Avg ${formatCurrency(s.avg_br || 0, cur)}/shipment</div></div>
        </div>
        <div class="kpi-card-v2 ${savingsPositive ? 'savings-positive' : ''}">
          <div class="kpi-icon">${savingsPositive ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>' : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/></svg>'}</div>
          <div class="kpi-content"><div class="kpi-number">${formatCurrency(s.total_savings || 0, cur)}</div><div class="kpi-label-v2">Total Savings</div><div class="kpi-sub">${s.savings_pct || 0}% reduction</div></div>
        </div>
        <div class="kpi-card-v2">
          <div class="kpi-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg></div>
          <div class="kpi-content"><div class="kpi-number">${s.shipments_with_savings || 0}<span class="kpi-denom">/${s.shipment_count || 0}</span></div><div class="kpi-label-v2">Coverage</div><div class="kpi-sub">${s.dim_weight_flags || 0} DIM-wt adjusted</div></div>
        </div>
        ${s.total_fuel != null ? `
        <div class="kpi-card-v2">
          <div class="kpi-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 22V8l9-6 9 6v14"/><path d="M9 22V12h6v10"/><path d="M12 2v4"/></svg></div>
          <div class="kpi-content"><div class="kpi-number">${formatCurrency(s.total_fuel || 0, cur)}</div><div class="kpi-label-v2">Total Fuel</div><div class="kpi-sub">Avg ${formatCurrency((s.total_fuel || 0) / Math.max(s.shipment_count || 1, 1), cur)}/shipment</div></div>
        </div>` : ''}
        ${s.total_accessorials != null ? `
        <div class="kpi-card-v2">
          <div class="kpi-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1v22M1 12h22"/><circle cx="12" cy="12" r="8"/></svg></div>
          <div class="kpi-content"><div class="kpi-number">${formatCurrency(s.total_accessorials || 0, cur)}</div><div class="kpi-label-v2">Total Accessorials</div><div class="kpi-sub">Avg ${formatCurrency((s.total_accessorials || 0) / Math.max(s.shipment_count || 1, 1), cur)}/shipment</div></div>
        </div>` : ''}
        ${s.margin_gross != null ? `
        <div class="kpi-card-v2 ${(s.margin_gross || 0) >= 0 ? 'savings-positive' : ''}">
          <div class="kpi-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></div>
          <div class="kpi-content"><div class="kpi-number">${formatCurrency(s.margin_gross || 0, cur)}</div><div class="kpi-label-v2">Gross Margin</div><div class="kpi-sub">${s.shipment_count > 0 ? formatCurrency((s.margin_gross || 0) / s.shipment_count, cur) + '/shipment' : ''}</div></div>
        </div>` : ''}
        ${s.total_buy_cost != null ? `
        <div class="kpi-card-v2">
          <div class="kpi-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg></div>
          <div class="kpi-content"><div class="kpi-number">${formatCurrency(s.total_buy_cost || 0, cur)}</div><div class="kpi-label-v2">Total Buy Cost</div><div class="kpi-sub">Avg ${formatCurrency((s.total_buy_cost || 0) / Math.max(s.shipment_count || 1, 1), cur)}/shipment</div></div>
        </div>` : ''}
        ${s.total_profit_actual != null ? `
        <div class="kpi-card-v2 ${(s.total_profit_actual || 0) >= 0 ? 'savings-positive' : ''}">
          <div class="kpi-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg></div>
          <div class="kpi-content"><div class="kpi-number">${formatCurrency(s.total_profit_actual || 0, cur)}</div><div class="kpi-label-v2">Total Profit</div><div class="kpi-sub">${s.actual_margin_pct != null ? s.actual_margin_pct.toFixed(1) + '% margin' : ''}</div></div>
        </div>` : ''}
      </div>

      <!-- Zone-Powered Badge -->
      <div class="zone-powered-bar">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
        Zones powered by SAPT &mdash; 41,877 US ZIPs + 1,698 CA FSAs
        ${zones.length > 0 ? `<span class="zone-dist-inline">${zones.map(z => `<span class="zdist-chip zdist-z${z}" title="Zone ${z}: ${byZone[z]?.count || 0} shipments (${byZone[z]?.distribution || 0}%)">Z${z}: ${byZone[z]?.distribution || 0}%</span>`).join('')}</span>` : ''}
      </div>

      <div class="analysis-grid-2col">
        <!-- Zone Breakdown -->
        ${zones.length > 0 ? `
        <div class="analysis-panel">
          <div class="panel-header"><h4>Zone Breakdown</h4></div>
          <div class="table-container">
            <table class="data-table compact striped">
              <thead><tr><th>Zone</th><th class="num">Count</th><th class="num">Dist%</th><th class="num">Avg Current</th><th class="num">Avg BR</th><th class="num">Diff</th><th class="num">Savings%</th></tr></thead>
              <tbody>
                ${zones.map(z => {
                  const zb = byZone[z];
                  const sv = (zb.savings || 0) > 0;
                  return `<tr><td class="fw-500">Zone ${z}</td><td class="num">${zb.count}</td><td class="num"><span class="dist-bar"><span class="dist-fill" style="width:${zb.distribution || 0}%"></span>${zb.distribution || 0}%</span></td><td class="num">${formatCurrency(zb.avg_original || 0, cur)}</td><td class="num">${formatCurrency(zb.avg_br || 0, cur)}</td><td class="num ${sv ? 'cell-savings' : ''}">${formatCurrency(zb.savings || 0, cur)}</td><td class="num ${sv ? 'cell-savings' : ''}">${zb.savings_pct || 0}%</td></tr>`;
                }).join('')}
                <tr class="total-row"><td class="fw-500">Total</td><td class="num fw-500">${s.shipment_count}</td><td class="num">100%</td><td class="num fw-500">${formatCurrency(s.avg_original || 0, cur)}</td><td class="num fw-500">${formatCurrency(s.avg_br || 0, cur)}</td><td class="num fw-500 cell-savings">${formatCurrency(s.total_savings || 0, cur)}</td><td class="num fw-500 cell-savings">${s.savings_pct || 0}%</td></tr>
              </tbody>
            </table>
          </div>
        </div>` : ''}

        <!-- Carrier Comparison -->
        ${carriers.length > 0 ? `
        <div class="analysis-panel">
          <div class="panel-header"><h4>Carrier Comparison</h4></div>
          <div class="table-container">
            <table class="data-table compact striped">
              <thead><tr><th>Carrier</th><th class="num">Count</th><th class="num">Current</th><th class="num">BR</th><th class="num">Savings</th><th class="num">%</th></tr></thead>
              <tbody>
                ${carriers.map(c => {
                  const cb = byCarrier[c];
                  const sv = (cb.savings || 0) > 0;
                  return `<tr><td class="fw-500">${esc(c)}</td><td class="num">${cb.count}</td><td class="num">${formatCurrency(cb.original || 0, cur)}</td><td class="num">${formatCurrency(cb.br || 0, cur)}</td><td class="num ${sv ? 'cell-savings' : ''}">${formatCurrency(cb.savings || 0, cur)}</td><td class="num ${sv ? 'cell-savings' : ''}">${cb.savings_pct || 0}%</td></tr>`;
                }).join('')}
              </tbody>
            </table>
          </div>
        </div>` : ''}
      </div>

      <div class="analysis-grid-2col">
        <!-- Weight Band Breakdown -->
        ${wBands.length > 0 ? `
        <div class="analysis-panel">
          <div class="panel-header"><h4>Weight Band Breakdown</h4></div>
          <div class="table-container">
            <table class="data-table compact striped">
              <thead><tr><th>Weight</th><th class="num">Count</th><th class="num">Current</th><th class="num">BR</th><th class="num">Savings</th><th class="num">%</th></tr></thead>
              <tbody>
                ${wBands.map(w => {
                  const wb = byWeightBand[w];
                  const sv = (wb.savings || 0) > 0;
                  return `<tr><td class="fw-500">${w}</td><td class="num">${wb.count}</td><td class="num">${formatCurrency(wb.original || 0, cur)}</td><td class="num">${formatCurrency(wb.br || 0, cur)}</td><td class="num ${sv ? 'cell-savings' : ''}">${formatCurrency(wb.savings || 0, cur)}</td><td class="num ${sv ? 'cell-savings' : ''}">${wb.savings_pct || 0}%</td></tr>`;
                }).join('')}
              </tbody>
            </table>
          </div>
        </div>` : ''}

        <!-- Service Type Breakdown -->
        ${serviceKeys.length > 0 ? `
        <div class="analysis-panel">
          <div class="panel-header"><h4>By Service Type</h4></div>
          <div class="table-container">
            <table class="data-table compact striped">
              <thead><tr><th>Service</th><th class="num">Count</th><th class="num">Current</th><th class="num">BR</th><th class="num">Savings</th><th class="num">%</th></tr></thead>
              <tbody>
                ${serviceKeys.map(k => {
                  const sv = byService[k];
                  const pos = (sv.savings || 0) > 0;
                  return `<tr><td class="fw-500">${esc(k)}</td><td class="num">${sv.count}</td><td class="num">${formatCurrency(sv.original || 0, cur)}</td><td class="num">${formatCurrency(sv.br || 0, cur)}</td><td class="num ${pos ? 'cell-savings' : ''}">${formatCurrency(sv.savings || 0, cur)}</td><td class="num ${pos ? 'cell-savings' : ''}">${sv.savings_pct || 0}%</td></tr>`;
                }).join('')}
              </tbody>
            </table>
          </div>
        </div>` : ''}
      </div>

      <!-- BR Service Mix -->
      ${mixKeys.length > 0 ? `
      <div class="analysis-panel">
        <div class="panel-header"><h4>Recommended Service Mix (Winner Distribution)</h4></div>
        <div class="service-mix-grid">
          ${mixKeys.map(k => {
            const m = brMix[k];
            const pct = (s.shipments_with_savings || 1) > 0 ? Math.round((m.count / s.shipments_with_savings) * 100) : 0;
            const hasBuySell = m.total_buy != null;
            return `<div class="service-mix-card">
              <div class="mix-name">${esc(k)}</div>
              <div class="mix-bar"><div class="mix-fill" style="width:${pct}%"></div></div>
              <div class="mix-stats">${m.count} shipments (${pct}%) &middot; Sell: ${formatCurrency(m.total || 0, cur)}</div>
              ${hasBuySell ? `<div class="mix-stats text-muted" style="font-size:11px;">Buy: ${formatCurrency(m.total_buy || 0, cur)} &middot; Profit: ${formatCurrency(m.total_profit || 0, cur)} &middot; Margin: ${m.margin_pct != null ? m.margin_pct.toFixed(1) + '%' : '—'}</div>` : ''}
            </div>`;
          }).join('')}
        </div>
      </div>` : ''}

      <!-- Zone x Weight Pivot -->
      ${pivotBands.length > 0 && pivotZones.length > 0 ? `
      <div class="analysis-panel">
        <div class="panel-header"><h4>Zone &times; Weight Pivot (Shipment Counts)</h4></div>
        <div class="table-container">
          <table class="data-table compact pivot-table">
            <thead><tr><th>Weight Band</th>${pivotZones.map(z => `<th class="num">Z${z}</th>`).join('')}<th class="num fw-500">Total</th></tr></thead>
            <tbody>
              ${pivotBands.map(wb => {
                const row = pivot[wb] || {};
                const rowTotal = pivotZones.reduce((sum, z) => sum + (row[z] || 0), 0);
                const maxVal = Math.max(...pivotZones.map(z => row[z] || 0), 1);
                return `<tr><td class="fw-500">${wb}</td>${pivotZones.map(z => {
                  const val = row[z] || 0;
                  const intensity = val > 0 ? Math.max(0.08, Math.min(0.6, val / maxVal * 0.6)) : 0;
                  return `<td class="num pivot-cell" style="${val > 0 ? 'background:rgba(16,185,129,' + intensity + ')' : ''}">${val || ''}</td>`;
                }).join('')}<td class="num fw-500">${rowTotal}</td></tr>`;
              }).join('')}
              <tr class="total-row"><td class="fw-500">Total</td>${pivotZones.map(z => {
                const colTotal = pivotBands.reduce((sum, wb) => sum + ((pivot[wb] || {})[z] || 0), 0);
                return `<td class="num fw-500">${colTotal}</td>`;
              }).join('')}<td class="num fw-500">${s.shipment_count || 0}</td></tr>
            </tbody>
          </table>
        </div>
      </div>` : ''}

      <!-- Per-Shipment Detail -->
      <div class="analysis-panel">
        <div class="panel-header">
          <h4>Per-Shipment Detail</h4>
          <button class="btn-ghost btn-sm" onclick="exportAnalysisCSV()">Export CSV</button>
        </div>
        <details class="data-details" id="shipment-detail-toggle">
          <summary class="btn-ghost btn-sm">Show All ${s.shipment_count || 0} Shipments</summary>
          <div class="table-container">
            <table class="data-table compact striped" id="shipment-detail-table">
              <thead><tr><th>Date</th><th>Tracking</th><th>Carrier</th><th>Service</th><th class="num">Actual</th><th class="num">DIM</th><th class="num">Billed</th><th>Zone</th><th class="num">Current</th><th>BR Service</th><th class="num">Buy</th><th class="num">BR Sell</th><th class="num">Fuel</th><th class="num">Access.</th><th class="num">Profit</th><th class="num">Margin%</th><th class="num">Savings</th></tr></thead>
              <tbody>
                ${(results.shipments || []).map(r => {
                  // Find best rate card buy/sell info from all_rates
                  let bestRate = null;
                  if (r.all_rates && r.br_service && r.all_rates[r.br_service]) {
                    bestRate = r.all_rates[r.br_service];
                  }
                  const buyPrice = r.buy_price != null ? r.buy_price : (bestRate ? (bestRate.buy_price || bestRate.base_buy || null) : null);
                  const profit = r.profit != null ? r.profit : (bestRate ? bestRate.profit : null);
                  const marginPct = r.margin_pct != null ? r.margin_pct : (bestRate ? bestRate.margin_pct : null);
                  return `
                  <tr class="${(r.savings || 0) > 0 ? 'row-savings' : ''}">
                    <td>${esc(r.ship_date || '')}</td>
                    <td class="text-mono text-xs">${esc((r.tracking || '').slice(0, 12))}</td>
                    <td>${esc(r.carrier || '')}</td>
                    <td>${esc(r.service || '')}</td>
                    <td class="num">${r.weight || 0}</td>
                    <td class="num ${(r.dim_weight || 0) > (r.weight || 0) ? 'text-warning' : ''}">${r.dim_weight ? r.dim_weight.toFixed(1) : '\u2014'}</td>
                    <td class="num fw-500">${r.billable_weight || r.weight || '\u2014'}</td>
                    <td class="text-center">${r.zone || '\u2014'}</td>
                    <td class="num">${formatCurrency(r.price || 0, cur)}</td>
                    <td class="${(r.savings || 0) > 0 ? 'text-accent' : 'text-muted'}">${esc(r.br_service || '')}</td>
                    <td class="num text-muted">${buyPrice != null ? formatCurrency(buyPrice, cur) : '\u2014'}</td>
                    <td class="num">${formatCurrency(r.br_price || 0, cur)}</td>
                    <td class="num text-muted">${r.fuel != null ? formatCurrency(r.fuel, cur) : '\u2014'}</td>
                    <td class="num text-muted">${r.accessorials != null ? formatCurrency(r.accessorials, cur) : '\u2014'}</td>
                    <td class="num ${profit != null && profit > 0 ? 'cell-savings' : (profit != null ? 'text-error' : '')}">${profit != null ? formatCurrency(profit, cur) : '\u2014'}</td>
                    <td class="num ${marginPct != null && marginPct > 0 ? 'cell-savings' : (marginPct != null ? 'text-error' : '')}">${marginPct != null ? marginPct.toFixed(1) + '%' : '\u2014'}</td>
                    <td class="num ${(r.savings || 0) > 0 ? 'cell-savings fw-500' : 'text-muted'}">${(r.savings || 0) > 0 ? formatCurrency(r.savings, cur) : '\u2014'}</td>
                  </tr>`;
                }).join('')}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <!-- Master Profitability Analysis -->
      <div class="analysis-panel profitability-panel" id="profitability-dashboard">
        <!-- Will be populated by updateProfitabilityPreview() after analysis runs -->
      </div>

      <!-- Bottom Publish Action Bar -->
      <div class="analysis-publish-bar" id="analysis-publish-bar">
        <div class="publish-bar-inner">
          <div class="publish-bar-text">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            <span>${window._workbenchAnalysisPublished ? 'This analysis has been published to the client.' : 'Ready to share this analysis with the client?'}</span>
          </div>
          <div style="display:flex;gap:8px;align-items:center;">
            <button class="btn-secondary btn-sm" onclick="previewClientExcel()" title="Download the same Excel file the client will receive">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Preview Client Excel
            </button>
            ${window._workbenchAnalysisPublished
              ? `<button class="btn-publish-lg" disabled style="opacity:0.6;cursor:default;background:#888;box-shadow:none;">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                  Published
                </button>`
              : `<button class="btn-publish-lg" onclick="confirmPublishAnalysis(window._workbenchClientId, window._workbenchCompanyName)" title="Publish analysis and notify the client">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                  Publish & Notify Client
                </button>`}
          </div>
        </div>
      </div>
    </div>`;
  } catch (err) {
    console.error('renderAnalysisResults error:', err);
    return `<div class="empty-state">Error rendering analysis results. Please try running the analysis again.</div>`;
  }
}

function exportAnalysisCSV() {
  const table = document.getElementById('shipment-detail-table');
  if (!table) { showToast('Open the shipment detail first', 'info'); return; }
  const rows = Array.from(table.querySelectorAll('tr'));
  const csv = rows.map(row => Array.from(row.querySelectorAll('th, td')).map(cell => '"' + cell.textContent.trim().replace(/"/g, '""') + '"').join(',')).join('\n');
  navigator.clipboard.writeText(csv).then(() => showToast('Copied to clipboard as CSV', 'success')).catch(() => showToast('Copy failed', 'error'));
}

// ─── Profitability Dashboard ───────────────────────────────────────────────────
function updateProfitabilityPreview() {
  const el = document.getElementById('profitability-dashboard');
  if (!el) return;

  const results = window._lastAnalysisResults;
  if (!results || !results.summary) {
    el.innerHTML = `<div class="profit-empty">Run an analysis above to see the Master Profitability dashboard.</div>`;
    return;
  }

  const s = results.summary;
  const cur = results.currency || 'USD';
  const shipmentCount = s.shipment_count || 1;

  // Read FMM inputs
  const dailyCost = parseFloat(document.getElementById('fmm-daily-cost')?.value) || 0;
  const pickupDays = parseFloat(document.getElementById('fmm-pickup-days')?.value) || 250;
  const handlingPerPiece = parseFloat(document.getElementById('fmm-handling-cost')?.value) || 0;
  const dailyVolume = parseFloat(document.getElementById('fmm-daily-volume')?.value) || 1;

  // Dataset P&L
  const totalSell = s.total_br || 0;
  const totalBuy = s.total_base_cost != null ? s.total_base_cost : totalSell; // fallback
  const grossMargin = totalSell - totalBuy;
  const totalHandling = handlingPerPiece * shipmentCount;
  const datasetDays = shipmentCount / Math.max(dailyVolume, 1);
  const datasetFmm = dailyCost * datasetDays;
  const datasetNetProfit = grossMargin - totalHandling - datasetFmm;

  // Scaling factors for projections
  const piecesPerDay = dailyVolume;
  const piecesPerWeek = piecesPerDay * 5;   // 5 working days
  const piecesPerMonth = piecesPerDay * 20.83;
  const piecesPerYear = piecesPerDay * pickupDays;

  // Per-piece unit economics (from dataset)
  const profitPerPiece = shipmentCount > 0 ? datasetNetProfit / shipmentCount : 0;
  const sellPerPiece = shipmentCount > 0 ? totalSell / shipmentCount : 0;
  const buyPerPiece = shipmentCount > 0 ? totalBuy / shipmentCount : 0;
  const handlingUnit = handlingPerPiece;
  const fmmUnit = dailyCost / Math.max(piecesPerDay, 1);

  function project(pieces) {
    const sell = sellPerPiece * pieces;
    const buy = buyPerPiece * pieces;
    const gm = sell - buy;
    const h = handlingUnit * pieces;
    const fmm = fmmUnit * pieces;
    return { sell, buy, gm, h, fmm, net: gm - h - fmm };
  }

  const daily = project(piecesPerDay);
  const weekly = project(piecesPerWeek);
  const monthly = project(piecesPerMonth);
  const annual = project(piecesPerYear);

  const netPositive = datasetNetProfit >= 0;

  function fc(v) { return formatCurrency(Math.abs(v), cur); }
  function fmtNum(v, isNeg) {
    if (isNeg) return `(${fc(v)})`;
    return fc(v);
  }
  function rowClass(v) { return v < 0 ? 'profit-row-cost' : ''; }
  function projCell(v) {
    const neg = v < 0;
    return `<td class="${neg ? 'text-error' : ''}">${neg ? '(' + fc(v) + ')' : fc(v)}</td>`;
  }

  // Margin % and unit economics
  const marginPct = totalSell > 0 ? (datasetNetProfit / totalSell * 100).toFixed(1) : '0.0';
  const profitPerLb = (s.total_weight_lbs || 0) > 0 ? datasetNetProfit / s.total_weight_lbs : null;
  const profitPerCuFt = (s.total_cubic_ft || 0) > 0 ? datasetNetProfit / s.total_cubic_ft : null;

  el.innerHTML = `
    <div class="profit-header">
      <div class="profit-header-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
        </svg>
      </div>
      <div>
        <h4>Master Profitability Analysis</h4>
        <div class="profit-subtitle">${shipmentCount} shipments in dataset &middot; ${piecesPerDay.toFixed(1)} pieces/day est. &middot; ${pickupDays} pickup days/yr</div>
      </div>
    </div>

    <div class="profit-table-wrap">
      <table class="profit-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Dataset (${shipmentCount} pcs)</th>
            <th>Daily</th>
            <th>Weekly</th>
            <th>Monthly</th>
            <th>Annual</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Client Sell Price</td>
            <td>${fc(totalSell)}</td>
            ${projCell(daily.sell)}
            ${projCell(weekly.sell)}
            ${projCell(monthly.sell)}
            ${projCell(annual.sell)}
          </tr>
          <tr class="profit-row-cost">
            <td>Our Buy Cost (cards)</td>
            <td>(${fc(totalBuy)})</td>
            ${projCell(-daily.buy)}
            ${projCell(-weekly.buy)}
            ${projCell(-monthly.buy)}
            ${projCell(-annual.buy)}
          </tr>
          <tr>
            <td style="font-weight:600;">Gross Markup Revenue</td>
            <td style="font-weight:600;">${grossMargin >= 0 ? fc(grossMargin) : '(' + fc(grossMargin) + ')'}</td>
            ${projCell(daily.gm)}
            ${projCell(weekly.gm)}
            ${projCell(monthly.gm)}
            ${projCell(annual.gm)}
          </tr>
          ${handlingPerPiece > 0 ? `
          <tr class="profit-row-cost">
            <td>Less: Handling Cost</td>
            <td>(${fc(totalHandling)})</td>
            ${projCell(-daily.h)}
            ${projCell(-weekly.h)}
            ${projCell(-monthly.h)}
            ${projCell(-annual.h)}
          </tr>` : ''}
          ${dailyCost > 0 ? `
          <tr class="profit-row-cost">
            <td>Less: First / Mid Mile</td>
            <td>(${fc(datasetFmm)})</td>
            ${projCell(-daily.fmm)}
            ${projCell(-weekly.fmm)}
            ${projCell(-monthly.fmm)}
            ${projCell(-annual.fmm)}
          </tr>` : ''}
          <tr class="profit-row-divider"><td colspan="6"></td></tr>
          <tr class="profit-row-total ${netPositive ? 'positive' : 'negative'}">
            <td>Net Profit</td>
            <td>${netPositive ? fc(datasetNetProfit) : '(' + fc(datasetNetProfit) + ')'}</td>
            ${projCell(daily.net)}
            ${projCell(weekly.net)}
            ${projCell(monthly.net)}
            ${projCell(annual.net)}
          </tr>
        </tbody>
      </table>
    </div>

    <div class="profit-unit-grid">
      <div class="profit-unit-card">
        <div class="profit-unit-value ${parseFloat(marginPct) >= 0 ? 'positive' : 'negative'}">${marginPct}%</div>
        <div class="profit-unit-label">Net Margin</div>
      </div>
      <div class="profit-unit-card">
        <div class="profit-unit-value ${profitPerPiece >= 0 ? 'positive' : 'negative'}">$${profitPerPiece.toFixed(2)}</div>
        <div class="profit-unit-label">Profit Per Piece</div>
      </div>
      ${profitPerLb !== null ? `
      <div class="profit-unit-card">
        <div class="profit-unit-value ${profitPerLb >= 0 ? 'positive' : 'negative'}">$${profitPerLb.toFixed(3)}</div>
        <div class="profit-unit-label">Profit Per Lb</div>
      </div>` : ''}
      ${profitPerCuFt !== null ? `
      <div class="profit-unit-card">
        <div class="profit-unit-value ${profitPerCuFt >= 0 ? 'positive' : 'negative'}">$${profitPerCuFt.toFixed(2)}</div>
        <div class="profit-unit-label">Profit Per Cu Ft</div>
      </div>` : ''}
      <div class="profit-unit-card">
        <div class="profit-unit-value">${formatCurrency(annual.sell, cur)}</div>
        <div class="profit-unit-label">Est. Annual Revenue</div>
      </div>
      <div class="profit-unit-card">
        <div class="profit-unit-value ${annual.net >= 0 ? 'positive' : 'negative'}">${formatCurrency(annual.net, cur)}</div>
        <div class="profit-unit-label">Est. Annual Profit</div>
      </div>
    </div>
  `;
}

function toggleRateCard(card, rcId) {
  card.classList.toggle('rc-toggle-selected');
  const panel = document.getElementById(`markup-panel-${rcId}`);
  if (panel) {
    panel.classList.toggle('markup-panel-inactive', !card.classList.contains('rc-toggle-selected'));
  }
  updateWbSelectedCount();
  // Trigger live re-analysis when cards change
  debouncedLiveAnalysis();
}


// Toggle all rate cards for a specific carrier
function toggleCarrierAll(carrier) {
  const section = document.querySelector(`.wb-carrier-section[data-wb-carrier="${carrier}"]`);
  if (!section) return;
  const cards = section.querySelectorAll('.rc-toggle-card');
  const allSelected = [...cards].every(c => c.classList.contains('rc-toggle-selected'));
  cards.forEach(card => {
    const rcId = parseInt(card.dataset.rcId);
    if (allSelected) {
      card.classList.remove('rc-toggle-selected');
      const panel = document.getElementById(`markup-panel-${rcId}`);
      if (panel) panel.classList.add('markup-panel-inactive');
    } else {
      card.classList.add('rc-toggle-selected');
      const panel = document.getElementById(`markup-panel-${rcId}`);
      if (panel) panel.classList.remove('markup-panel-inactive');
    }
  });
  updateWbSelectedCount();
  debouncedLiveAnalysis();
}

function updateWbSelectedCount() {
  const total = document.querySelectorAll('.rc-toggle-card.rc-toggle-selected').length;
  const el = document.getElementById('wb-rc-selected-count');
  if (el) el.textContent = total > 0 ? `${total} selected` : '';
}

function filterWbRateCards() {
  const query = (document.getElementById('wb-rc-search')?.value || '').toLowerCase().trim();
  const sections = document.querySelectorAll('.wb-carrier-section');
  sections.forEach(section => {
    const cards = section.querySelectorAll('.rc-toggle-card');
    let visible = 0;
    cards.forEach(card => {
      const match = !query || card.dataset.rcName?.includes(query) || card.dataset.rcCarrier?.includes(query);
      card.style.display = match ? '' : 'none';
      if (match) visible++;
    });
    section.style.display = visible > 0 ? '' : 'none';
    if (query && visible > 0) section.classList.add('wb-expanded');
  });
}

// ─── Markup Controls: sync slider ↔ number ↔ display ↔ preview ──────────────
function syncMarkup(rcId, field, value) {
  const v = parseFloat(value) || 0;
  if (field === 'pct') {
    const slider = document.querySelector(`#markup-panel-${rcId} .markup-pct`);
    const num = document.getElementById(`pct-num-${rcId}`);
    const display = document.getElementById(`pct-display-${rcId}`);
    if (slider) slider.value = v;
    if (num) num.value = v;
    if (display) display.textContent = v + '%';
  } else if (field === 'lb') {
    const slider = document.querySelector(`#markup-panel-${rcId} .markup-lb-range`);
    const num = document.getElementById(`lb-num-${rcId}`);
    const display = document.getElementById(`lb-display-${rcId}`);
    if (slider) slider.value = Math.min(v, 1);
    if (num) num.value = v;
    if (display) display.textContent = '$' + v.toFixed(2);
  } else if (field === 'ship') {
    const slider = document.querySelector(`#markup-panel-${rcId} .markup-ship-range`);
    const num = document.getElementById(`ship-num-${rcId}`);
    const display = document.getElementById(`ship-display-${rcId}`);
    if (slider) slider.value = Math.min(v, 5);
    if (num) num.value = v;
    if (display) display.textContent = '$' + v.toFixed(2);
  }
  updateMarkupPreview(rcId);
  // Trigger live re-analysis when markup sliders change
  debouncedLiveAnalysis();
}

function updateMarkupPreview(rcId) {
  const panel = document.getElementById(`markup-panel-${rcId}`);
  if (!panel) return;
  const pctEl = panel.querySelector('.markup-pct-num') || panel.querySelector('.markup-pct');
  const lbEl = panel.querySelector('.markup-lb');
  const shipEl = panel.querySelector('.markup-ship');
  const pct = parseFloat(pctEl?.value || 15) / 100;
  const perLb = parseFloat(lbEl?.value || 0.10);
  const perShip = parseFloat(shipEl?.value || 1.00);

  const hasActual = window._rcAvgBase && window._rcAvgBase[rcId];

  const costEl = document.getElementById(`preview-cost-${rcId}`);
  const weightEl = document.getElementById(`preview-weight-${rcId}`);
  const sellEl = document.getElementById(`preview-sell-${rcId}`);
  const marginEl = document.getElementById(`preview-margin-${rcId}`);
  const marginPctEl = document.getElementById(`preview-margin-pct-${rcId}`);

  if (hasActual) {
    const avgBase = window._rcAvgBase[rcId].avgBase;
    const avgWeight = window._rcAvgBase[rcId].avgWeight;
    // Calculate sell price using actual avg data from this rate card
    const sellPrice = (avgBase * (1 + pct)) + (avgWeight * perLb) + perShip;
    const margin = sellPrice - avgBase;
    const marginPct = avgBase > 0 ? (margin / sellPrice) * 100 : 0;

    if (costEl) costEl.textContent = '$' + avgBase.toFixed(2);
    if (weightEl) weightEl.textContent = 'avg billable wt: ' + avgWeight.toFixed(1) + ' lbs';
    if (sellEl) {
      sellEl.textContent = '$' + sellPrice.toFixed(2);
      sellEl.style.color = 'var(--color-warning, #da7101)';
    }
    if (marginEl) {
      marginEl.textContent = '$' + margin.toFixed(2);
      marginEl.style.color = margin > 0 ? 'var(--color-success, #16a34a)' : 'var(--color-error, #dc2626)';
    }
    if (marginPctEl) {
      marginPctEl.textContent = marginPct.toFixed(1) + '% margin';
      marginPctEl.style.color = margin > 0 ? 'var(--color-success, #16a34a)' : 'var(--color-error, #dc2626)';
    }
  } else {
    // Analysis hasn't loaded yet — show loading indicator
    if (costEl) costEl.innerHTML = '<span class="metric-loading"><span class="spinner-dot"></span></span>';
    if (weightEl) { weightEl.textContent = 'Calculating…'; weightEl.style.color = 'var(--text-muted)'; }
    if (sellEl) { sellEl.innerHTML = '<span class="metric-loading"><span class="spinner-dot"></span></span>'; sellEl.style.color = ''; }
    if (marginEl) { marginEl.innerHTML = '<span class="metric-loading"><span class="spinner-dot"></span></span>'; marginEl.style.color = ''; }
    if (marginPctEl) { marginPctEl.textContent = ''; marginPctEl.style.color = ''; }
  }

  // Also recalc profitability if results available
  updateProfitabilityPreview();
}

function initAllMarkupPreviews() {
  document.querySelectorAll('.markup-panel').forEach(panel => {
    const rcId = panel.dataset.rcId;
    if (rcId) updateMarkupPreview(rcId);
  });
}

function applyMarkupToAll() {
  const panels = document.querySelectorAll('.markup-panel:not(.markup-panel-inactive)');
  if (panels.length < 2) { showToast('Select at least 2 rate cards to use Apply to All', 'info'); return; }
  const first = panels[0];
  const pct = first.querySelector('.markup-pct-num')?.value || first.querySelector('.markup-pct')?.value || '15';
  const lb = first.querySelector('.markup-lb')?.value || '0.10';
  const ship = first.querySelector('.markup-ship')?.value || '1.00';
  panels.forEach((panel, i) => {
    if (i === 0) return;
    const rcId = panel.dataset.rcId;
    syncMarkup(rcId, 'pct', pct);
    syncMarkup(rcId, 'lb', lb);
    syncMarkup(rcId, 'ship', ship);
  });
  showToast('Markup applied to all selected rate cards', 'success');
}

function confirmPublishAnalysis(clientId, companyName) {
  openModal('Publish Analysis', `
    <div style="padding: var(--space-2) 0;">
      <p style="font-size:var(--text-sm);color:var(--color-text);margin-bottom:var(--space-4);">This will make the analysis visible to <strong>${esc(companyName)}</strong> and send them an email notification.</p>
      <div style="background:var(--color-success-highlight);border:1px solid var(--color-success);border-radius:var(--radius-md);padding:var(--space-3) var(--space-4);margin-bottom:var(--space-4);font-size:var(--text-sm);">
        <strong>What happens next:</strong><br>
        <span style="color:var(--color-text-muted);">The client will see a banner notification when they next log in, and their analysis tab will become active.</span>
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn-primary" style="background:var(--color-success);" onclick="closeModal(); publishAnalysis(${clientId}, '${esc(companyName)}')"
                title="Confirm and publish analysis to client">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          Confirm & Publish
        </button>
      </div>
    </div>`);
}

// Empty state shown when no rate cards are selected for analysis
function renderAnalysisEmptyState() {
  return `
    <div class="analysis-empty-state">
      <div class="analysis-empty-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="1.5" opacity="0.5">
          <rect x="3" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/>
          <rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>
      </div>
      <div class="analysis-empty-title">Select Rate Cards to Begin</div>
      <div class="analysis-empty-desc">Click on one or more rate cards above to start analyzing this client's shipping data. Most shippers use 1–3 carriers, so pick the services that best match their profile.</div>
    </div>
  `;
}

// Auto-run analysis on page load so markup metrics show real averages from the dataset.
// Shows a loading state on the metric cards, runs silently, populates _rcAvgBase.
async function autoRunAnalysis(clientId, rateCards, client) {
  // Only auto-run if the admin has previously saved specific rate card selections
  // Do NOT auto-restore previous selections — admin must click to select
  return;

  // Show loading state on all markup metric values
  document.querySelectorAll('.markup-metric-value').forEach(el => {
    el.innerHTML = '<span class="metric-loading"><span class="spinner-dot"></span></span>';
    el.style.color = '';
  });
  document.querySelectorAll('.markup-metric-sub').forEach(el => {
    el.textContent = 'Analyzing shipment data…';
    el.style.color = 'var(--text-muted)';
  });

  // Build markups from current slider values (defaults)
  const markups = {};
  document.querySelectorAll('.markup-panel').forEach(row => {
    const id = row.dataset.rcId;
    if (rcIds.includes(parseInt(id))) {
      const pctEl = row.querySelector('.markup-pct-num') || row.querySelector('.markup-pct');
      markups[id] = {
        pct: parseFloat(pctEl?.value || 15) / 100 || 0.15,
        per_lb: parseFloat(row.querySelector('.markup-lb')?.value) || 0.10,
        per_shipment: parseFloat(row.querySelector('.markup-ship')?.value) || 1.00
      };
    }
  });

  try {
    const body = { rate_card_ids: rcIds, markups };
    const res = await api(`/clients/${clientId}/analysis`, { method: 'POST', body });

    if (res.results?.shipments) {
      // Compute per-card average base rates
      const rcTotals = {};
      res.results.shipments.forEach(s => {
        if (s.all_rates) {
          Object.entries(s.all_rates).forEach(([name, info]) => {
            const id = String(info.id);
            if (!rcTotals[id]) rcTotals[id] = { totalBase: 0, totalWeight: 0, count: 0 };
            rcTotals[id].totalBase += info.base;
            rcTotals[id].totalWeight += (info.billable_wt || s.billable_weight || s.weight || 1);
            rcTotals[id].count++;
          });
        }
      });
      window._rcAvgBase = {};
      Object.entries(rcTotals).forEach(([id, t]) => {
        window._rcAvgBase[id] = {
          avgBase: t.count > 0 ? t.totalBase / t.count : 5,
          avgWeight: t.count > 0 ? t.totalWeight / t.count : 3
        };
      });
      window._lastAnalysisResults = res.results;

      // Compute smart default for daily volume
      const shipments = res.results.shipments || [];
      const uniqueDates = new Set(shipments.map(s => s.ship_date).filter(Boolean));
      const defaultDailyVol = uniqueDates.size > 0
        ? Math.max(1, Math.ceil(shipments.length / uniqueDates.size))
        : Math.max(1, shipments.length);
      const dailyVolInput = document.getElementById('fmm-daily-volume');
      if (dailyVolInput && parseFloat(dailyVolInput.value) === 1) {
        dailyVolInput.value = defaultDailyVol;
      }

      // Render full results table on initial auto-analysis
      const resultsEl = document.getElementById('analysis-results');
      if (resultsEl) {
        resultsEl.innerHTML = renderAnalysisResults(res.results);
      }
      updateProfitabilityPreview();
    }
  } catch (e) {
    // Silently fail — user can still use live analysis
    console.warn('Auto-analysis failed:', e);
  }

  // Refresh previews with actual data (or clear loading if analysis failed)
  initAllMarkupPreviews();
  setLiveStatus('ready');
}

// ─── Live Analysis: debounced auto-rerun on any slider/toggle change ─────────
let _liveAnalysisTimer = null;
let _liveAnalysisInFlight = false;
let _liveAnalysisQueued = false;

function debouncedLiveAnalysis() {
  if (_liveAnalysisTimer) clearTimeout(_liveAnalysisTimer);
  _liveAnalysisTimer = setTimeout(() => {
    _liveAnalysisTimer = null;
    triggerLiveAnalysis();
  }, 600); // 600ms debounce — lets sliders settle
}

async function triggerLiveAnalysis() {
  const clientId = window._workbenchClientId;
  if (!clientId) return;

  // If already in-flight, queue another run for after it finishes
  if (_liveAnalysisInFlight) {
    _liveAnalysisQueued = true;
    return;
  }

  _liveAnalysisInFlight = true;
  setLiveStatus('analyzing');

  // Add a subtle shimmer overlay on the results while updating
  const resultsEl = document.getElementById('analysis-results');
  if (resultsEl && resultsEl.innerHTML.trim()) {
    resultsEl.classList.add('results-updating');
  }

  try {
    // Gather selected rate cards
    const selectedCards = document.querySelectorAll('.rc-toggle-card.rc-toggle-selected');
    const rcIds = Array.from(selectedCards).map(c => parseInt(c.dataset.rcId));
    if (rcIds.length === 0) {
      setLiveStatus('idle');
      _liveAnalysisInFlight = false;
      // Show empty state when all cards are deselected
      const resultsEl = document.getElementById('analysis-results');
      if (resultsEl) resultsEl.innerHTML = renderAnalysisEmptyState();
      return;
    }

    // Gather markup values
    const markups = {};
    document.querySelectorAll('.markup-panel').forEach(row => {
      const id = row.dataset.rcId;
      if (rcIds.includes(parseInt(id))) {
        const pctEl = row.querySelector('.markup-pct-num') || row.querySelector('.markup-pct');
        markups[id] = {
          pct: parseFloat(pctEl?.value || 15) / 100 || 0.15,
          per_lb: parseFloat(row.querySelector('.markup-lb')?.value) || 0.10,
          per_shipment: parseFloat(row.querySelector('.markup-ship')?.value) || 1.00
        };
      }
    });

    // Read DIM divisor
    let dimDivisor = null;
    const dimSel = document.getElementById('analysis-dim-divisor');
    const dimCustom = document.getElementById('analysis-dim-custom');
    if (dimSel) {
      if (dimSel.value === 'custom' && dimCustom && dimCustom.value) {
        dimDivisor = parseFloat(dimCustom.value) || null;
      } else if (dimSel.value && dimSel.value !== 'custom' && dimSel.value !== '') {
        dimDivisor = parseFloat(dimSel.value);
      }
    }

    // Read zone chart
    const zoneChartSel = document.getElementById('analysis-zone-chart');
    const zoneChartId = zoneChartSel && zoneChartSel.value ? parseInt(zoneChartSel.value) : null;

    const body = { rate_card_ids: rcIds, markups };
    if (dimDivisor) body.dim_divisor = dimDivisor;
    if (zoneChartId) body.zone_chart_id = zoneChartId;

    const res = await api(`/clients/${clientId}/analysis`, { method: 'POST', body });

    if (res.results) {
      window._lastAnalysisResults = res.results;

      // Compute per-card averages
      if (res.results.shipments) {
        const rcTotals = {};
        res.results.shipments.forEach(s => {
          if (s.all_rates) {
            Object.entries(s.all_rates).forEach(([name, info]) => {
              const id = String(info.id);
              if (!rcTotals[id]) rcTotals[id] = { totalBase: 0, totalWeight: 0, count: 0 };
              rcTotals[id].totalBase += info.base;
              rcTotals[id].totalWeight += (info.billable_wt || s.billable_weight || s.weight || 1);
              rcTotals[id].count++;
            });
          }
        });
        window._rcAvgBase = {};
        Object.entries(rcTotals).forEach(([id, t]) => {
          window._rcAvgBase[id] = {
            avgBase: t.count > 0 ? t.totalBase / t.count : 5,
            avgWeight: t.count > 0 ? t.totalWeight / t.count : 3
          };
        });
        initAllMarkupPreviews();
      }

      // Update results table
      const resultsEl = document.getElementById('analysis-results');
      if (resultsEl) {
        resultsEl.innerHTML = renderAnalysisResults(res.results);
      }
      updateProfitabilityPreview();
    }

    setLiveStatus('ready');
  } catch (e) {
    console.warn('Live analysis error:', e);
    setLiveStatus('error');
  }

  // Remove shimmer overlay
  const resultsClean = document.getElementById('analysis-results');
  if (resultsClean) resultsClean.classList.remove('results-updating');

  _liveAnalysisInFlight = false;

  // If another change came in while we were running, go again
  if (_liveAnalysisQueued) {
    _liveAnalysisQueued = false;
    triggerLiveAnalysis();
  }
}

function setLiveStatus(state) {
  const el = document.getElementById('live-analysis-status');
  if (!el) return;
  const dot = el.querySelector('.live-dot');
  const label = el.querySelector('.live-label');
  el.className = 'live-analysis-status live-status-' + state;
  if (state === 'analyzing') {
    label.textContent = 'Updating analysis\u2026';
  } else if (state === 'ready') {
    label.textContent = 'Live Analysis';
  } else if (state === 'error') {
    label.textContent = 'Analysis error';
  } else {
    label.textContent = 'Live Analysis';
  }
}

async function runAnalysis(clientId) {
  const selectedCards = document.querySelectorAll('.rc-toggle-card.rc-toggle-selected');
  // Fallback to old checkbox style if workbench not present
  const checkedOld = document.querySelectorAll('.rc-check:checked');
  const rcIds = selectedCards.length > 0
    ? Array.from(selectedCards).map(c => parseInt(c.dataset.rcId))
    : Array.from(checkedOld).map(cb => parseInt(cb.value));
  if (rcIds.length === 0) { showToast('Select at least one rate card', 'error'); return; }

  const markups = {};
  // Support both new workbench panels and legacy markup-row
  const markupContainers = document.querySelectorAll('.markup-panel, .markup-row');
  markupContainers.forEach(row => {
    const id = row.dataset.rcId;
    if (rcIds.includes(parseInt(id))) {
      // For .markup-panel, pct comes from slider (markup-pct) or num input (markup-pct-num)
      const pctEl = row.querySelector('.markup-pct-num') || row.querySelector('.markup-pct');
      markups[id] = {
        pct: parseFloat(pctEl?.value || 15) / 100 || 0.15,
        per_lb: parseFloat(row.querySelector('.markup-lb')?.value) || 0.10,
        per_shipment: parseFloat(row.querySelector('.markup-ship')?.value) || 1.00
      };
    }
  });

  // Read DIM divisor override
  let dimDivisor = null;
  const dimSel = document.getElementById('analysis-dim-divisor');
  const dimCustom = document.getElementById('analysis-dim-custom');
  if (dimSel) {
    if (dimSel.value === 'custom' && dimCustom && dimCustom.value) {
      dimDivisor = parseFloat(dimCustom.value) || null;
    } else if (dimSel.value && dimSel.value !== 'custom' && dimSel.value !== '') {
      dimDivisor = parseFloat(dimSel.value);
    }
  }

  // Read zone chart selection
  const zoneChartSel = document.getElementById('analysis-zone-chart');
  const zoneChartId = zoneChartSel && zoneChartSel.value ? parseInt(zoneChartSel.value) : null;

  const runBtn = document.querySelector('.analysis-run-btn');
  const resultsEl = document.getElementById('analysis-results');
  try {
    if (runBtn) { runBtn.disabled = true; runBtn.innerHTML = '<span class="spinner-sm"></span> Analyzing...'; }
    if (resultsEl) { resultsEl.innerHTML = '<div class="analysis-loading"><div class="spinner-sm"></div><span>Processing ' + rcIds.length + ' rate card(s) against shipment data...</span></div>'; }
    const body = { rate_card_ids: rcIds, markups };
    if (dimDivisor) body.dim_divisor = dimDivisor;
    if (zoneChartId) body.zone_chart_id = zoneChartId;
    const res = await api(`/clients/${clientId}/analysis`, {
      method: 'POST',
      body
    });
    showToast('Analysis complete!', 'success');
    if (resultsEl && res.results) {
      // Store results globally for profitability dashboard
      window._lastAnalysisResults = res.results;

      // Compute per-card average base rates from results
      if (res.results.shipments) {
        const rcTotals = {};
        res.results.shipments.forEach(s => {
          if (s.all_rates) {
            Object.entries(s.all_rates).forEach(([name, info]) => {
              const id = String(info.id);
              if (!rcTotals[id]) rcTotals[id] = { totalBase: 0, totalWeight: 0, count: 0 };
              rcTotals[id].totalBase += info.base;
              rcTotals[id].totalWeight += (info.billable_wt || s.billable_weight || s.weight || 1);
              rcTotals[id].count++;
            });
          }
        });
        window._rcAvgBase = {};
        Object.entries(rcTotals).forEach(([id, t]) => {
          window._rcAvgBase[id] = {
            avgBase: t.count > 0 ? t.totalBase / t.count : 5,
            avgWeight: t.count > 0 ? t.totalWeight / t.count : 3
          };
        });
        // Re-init previews with actual data
        initAllMarkupPreviews();
      }

      // Compute smart default for daily volume from unique ship dates
      const shipments = res.results.shipments || [];
      const uniqueDates = new Set(shipments.map(s => s.ship_date).filter(Boolean));
      const defaultDailyVol = uniqueDates.size > 0
        ? Math.max(1, Math.ceil(shipments.length / uniqueDates.size))
        : Math.max(1, shipments.length);
      const dailyVolInput = document.getElementById('fmm-daily-volume');
      if (dailyVolInput && parseFloat(dailyVolInput.value) === 1) {
        dailyVolInput.value = defaultDailyVol;
      }

      resultsEl.innerHTML = renderAnalysisResults(res.results);
      updateProfitabilityPreview();
    } else {
      router();
    }
  } catch (e) {
    showToast(e.message, 'error');
    if (resultsEl) { resultsEl.innerHTML = '<div class="empty-state">Analysis failed: ' + esc(e.message) + '</div>'; }
  } finally {
    if (runBtn) { runBtn.disabled = false; runBtn.innerHTML = 'Run Analysis'; }
  }
}

async function publishAnalysis(clientId, companyName) {
  try {
    const res = await api(`/clients/${clientId}/analysis/publish`, { method: 'POST', body: {} });
    const name = companyName || res.company_name || 'the client';
    showToast(`Analysis published! ${name} has been notified.`, 'success');
    router();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── Admin Rate Cards ─────────────────────────────────────────────────────────
async function renderAdminRateCards(el) {
  setAdminPageTitle('Rate Cards');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const cards = await api('/rate-cards');
    // Group by carrier for organized display
    const carrierOrder = ['USPS','UPS','UPS Canada','FedEx','DHL','OSM','Amazon','UniUni','Canada Post','Asendia'];
    const byCarrier = {};
    cards.forEach(c => {
      const carrier = c.carrier || 'Other';
      if (!byCarrier[carrier]) byCarrier[carrier] = [];
      byCarrier[carrier].push(c);
    });
    const sortedCarriers = Object.keys(byCarrier).sort((a, b) => {
      const ai = carrierOrder.indexOf(a), bi = carrierOrder.indexOf(b);
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });

    // Store cards globally for search
    window._allRateCards = cards;
    window._allRateCardsByCarrier = byCarrier;
    window._sortedRateCardCarriers = sortedCarriers;

    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Rate Cards <span class="page-title-count">${cards.length}</span></h2>
          <div class="page-header-actions">
            <button class="btn-secondary btn-sm" onclick="showCompareCardsModal()" title="Compare two rate cards side by side with a % difference heatmap">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>
              Compare Cards
            </button>
            <button class="btn-secondary btn-sm" onclick="showImportCSVModal()" title="Import a Wizmo 4-header CSV or simple CSV rate card file">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Import CSV
            </button>
            <button class="btn-primary btn-sm" onclick="showRateCardModal()" title="Create a new rate card">+ New Rate Card</button>
          </div>
        </div>

        <!-- Search + Sort Bar -->
        <div class="rc-search-bar">
          <div class="rc-search-input-wrap">
            <svg class="rc-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="rc-search-input" class="rc-search-input" placeholder="Search by carrier, service name, or type…"
              oninput="filterRateCards()" autocomplete="off">
            <button class="rc-search-clear hidden" id="rc-search-clear" onclick="clearRcSearch()" title="Clear search">&times;</button>
          </div>
          <div class="rc-sort-wrap">
            <label class="rc-sort-label" for="rc-sort-select">Sort:</label>
            <select id="rc-sort-select" class="rc-sort-select" onchange="filterRateCards()" title="Sort rate cards">
              <option value="carrier">Carrier</option>
              <option value="name">Name</option>
              <option value="service_type">Service Type</option>
            </select>
          </div>
          <button class="btn-ghost btn-sm" onclick="rcExpandAll(true)" title="Expand all carrier groups">Expand All</button>
          <button class="btn-ghost btn-sm" onclick="rcExpandAll(false)" title="Collapse all carrier groups">Collapse All</button>
        </div>

        <div class="rc-summary-bar">
          <span class="rc-total-count" id="rc-visible-count">${cards.length} rate cards across ${sortedCarriers.length} carriers</span>
        </div>

        <div id="rc-card-grid">
          ${sortedCarriers.map(carrier => `
            <div class="rc-carrier-group rc-group-collapsed" data-carrier="${esc(carrier)}">
              <div class="rc-carrier-heading" onclick="this.parentElement.classList.toggle('rc-group-collapsed')" title="Toggle ${esc(carrier)} cards">
                <div class="rc-carrier-heading-left">
                  <svg class="rc-group-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                  <span class="rc-carrier-name">${esc(carrier)}</span>
                  <span class="rc-carrier-count">${byCarrier[carrier].length} card${byCarrier[carrier].length !== 1 ? 's' : ''}</span>
                </div>
                <div class="rc-carrier-heading-badges">
                  ${byCarrier[carrier].some(c => c.country === 'CA') ? '<span class="badge badge-outline" title="Includes Canadian services">🇨🇦 CA</span>' : ''}
                  ${[...new Set(byCarrier[carrier].map(c => c.currency))].map(cur => `<span class="rc-badge-currency">${cur}</span>`).join('')}
                </div>
              </div>
              <div class="rc-carrier-cards-wrap">
                <div class="card-grid rc-card-grid-inner">
                  ${byCarrier[carrier].map(c => `
                    <div class="card rate-card-item" onclick="showRateCardDetail(${c.id})"
                      title="${esc(c.name)} — Click to view full rate grid"
                      data-carrier="${esc(c.carrier || '').toLowerCase()}"
                      data-name="${esc(c.name).toLowerCase()}"
                      data-service="${esc(c.service_type || '').toLowerCase()}">
                      <button class="rc-delete-x" onclick="event.stopPropagation(); deleteRateCard(${c.id})" title="Delete this rate card">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      </button>
                      <div class="rc-header">
                        <div class="rc-name">${esc(c.name)}</div>
                        <span class="badge" title="Service type">${esc(c.service_type || 'N/A')}</span>
                      </div>
                      <div class="rc-meta">
                        <span title="Number of zones">${c.zone_count} zones</span>
                        <span class="rc-meta-sep">·</span>
                        <span title="Number of weight breaks">${c.weight_count} wt breaks</span>
                        ${c.zone_key ? `<span class="rc-meta-sep">·</span><span class="rc-zone-key" title="Zone data source">${esc(c.zone_key)}</span>` : ''}
                      </div>
                      <div class="rc-badges">
                        <span class="rc-badge-type" title="Pricing type">${c.pricing_type === 'CUBICFEET' ? 'Cubic' : c.pricing_type === 'WEIGHT_OUNCES' ? 'Ounces' : 'Weight (lbs)'}</span>
                        <span class="rc-badge-dim" title="DIM divisor">DIM ÷${c.dim_divisor || 166}</span>
                        <span class="rc-badge-currency" title="Currency">${c.currency || 'USD'}</span>
                        ${c.country === 'CA' ? '<span class="rc-badge-country" title="Canadian service">🇨🇦 CA</span>' : '<span class="rc-badge-country rc-badge-us" title="US service">🇺🇸 US</span>'}
                        ${c.fuel_rate > 0 ? `<span class="rc-badge-fuel" title="Fuel surcharge: ${c.fuel_type === 'per_lb' ? '$' + c.fuel_rate + '/lb' : (c.fuel_rate * 100).toFixed(0) + '%'}">&#9981; ${c.fuel_type === 'per_lb' ? '$' + c.fuel_rate + '/lb' : (c.fuel_rate * 100).toFixed(0) + '%'}</span>` : ''}
                        ${c.card_type ? `<span class="badge badge-sm" title="Card type: ${esc(c.card_type)}" style="background:var(--color-primary-highlight);color:var(--color-primary);">${esc(c.card_type.replace(/_/g,' '))}</span>` : ''}
                        ${c.service_class && c.service_class !== 'economy' ? `<span class="badge badge-sm" title="Service class: ${esc(c.service_class)}" style="background:#fef3c7;color:#92400e;">${esc(c.service_class)}</span>` : ''}
                        ${c.status && c.status !== 'active' ? `<span class="rc-badge-status rc-badge-inactive" title="Status: ${esc(c.status)}">${esc(c.status)}</span>` : '<span class="rc-badge-status rc-badge-active" title="Active">Active</span>'}
                      </div>
                      ${c.description ? `<div class="rc-desc">${esc(c.description)}</div>` : ''}
                      <div class="rc-footer">Updated ${formatDate(c.updated_at)}</div>
                    </div>
                  `).join('')}
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load rate cards</div></div>`;
  }
}

function filterRateCards() {
  const query = (document.getElementById('rc-search-input')?.value || '').toLowerCase().trim();
  const sortBy = document.getElementById('rc-sort-select')?.value || 'carrier';
  const clearBtn = document.getElementById('rc-search-clear');
  if (clearBtn) clearBtn.classList.toggle('hidden', !query);

  const groups = document.querySelectorAll('.rc-carrier-group');
  let totalVisible = 0;

  groups.forEach(group => {
    const cards = group.querySelectorAll('.rate-card-item');
    let groupVisible = 0;
    cards.forEach(card => {
      const carrierMatch = card.dataset.carrier?.includes(query);
      const nameMatch = card.dataset.name?.includes(query);
      const serviceMatch = card.dataset.service?.includes(query);
      const show = !query || carrierMatch || nameMatch || serviceMatch;
      card.style.display = show ? '' : 'none';
      if (show) groupVisible++;
    });
    group.style.display = groupVisible > 0 ? '' : 'none';
    if (groupVisible > 0) {
      totalVisible += groupVisible;
      // Auto-expand when searching
      if (query) group.classList.remove('rc-group-collapsed');
    }
  });

  // Sort cards within each group
  if (sortBy !== 'carrier') {
    groups.forEach(group => {
      const grid = group.querySelector('.rc-card-grid-inner');
      if (!grid) return;
      const cards = [...grid.querySelectorAll('.rate-card-item')];
      cards.sort((a, b) => {
        const va = (sortBy === 'name' ? a.dataset.name : a.dataset.service) || '';
        const vb = (sortBy === 'name' ? b.dataset.name : b.dataset.service) || '';
        return va.localeCompare(vb);
      });
      cards.forEach(c => grid.appendChild(c));
    });
  }

  const countEl = document.getElementById('rc-visible-count');
  if (countEl) {
    const visibleCarriers = [...groups].filter(g => g.style.display !== 'none').length;
    countEl.textContent = `${totalVisible} rate card${totalVisible !== 1 ? 's' : ''} across ${visibleCarriers} carrier${visibleCarriers !== 1 ? 's' : ''}${query ? ' (filtered)' : ''}`;
  }
}

function clearRcSearch() {
  const inp = document.getElementById('rc-search-input');
  if (inp) { inp.value = ''; inp.focus(); }
  filterRateCards();
}

function rcExpandAll(expand) {
  document.querySelectorAll('.rc-carrier-group').forEach(g => {
    g.classList.toggle('rc-group-collapsed', !expand);
  });
}

function showRateCardModal(existing) {
  const rc = existing || { name: '', service_type: '', carrier: '', description: '', dim_divisor: 166, currency: 'USD', country: 'US', version: 'v1', fuel_rate: 0, fuel_type: 'percentage', fuel_discount: 0, dim_threshold_cu_in: 0, dim_divisor_alt: 0, service_class: 'economy', card_type: 'sell_current', fuel_rate_buy: 0, fuel_rate_sell: 0, dim_divisor_buy: 166 };
  openModal(existing ? 'Edit Rate Card' : 'New Rate Card', `
    <form id="rc-form" onsubmit="event.preventDefault(); submitRateCard(${existing?.id || 'null'})">
      <div class="form-grid modal-form">
        <div class="form-field"><label>Name *</label><input name="name" required value="${esc(rc.name)}"></div>
        <div class="form-field"><label>Service Type</label><input name="service_type" value="${esc(rc.service_type)}" placeholder="Ground, Express, etc."></div>
        <div class="form-field"><label>Carrier</label><input name="carrier" value="${esc(rc.carrier)}"></div>
        <div class="form-field">
          <label>Currency</label>
          <select name="currency">
            <option value="USD" ${(!rc.currency || rc.currency === 'USD') ? 'selected' : ''}>USD</option>
            <option value="CAD" ${rc.currency === 'CAD' ? 'selected' : ''}>CAD</option>
          </select>
        </div>
        <div class="form-field">
          <label>Country</label>
          <select name="country">
            <option value="US" ${(!rc.country || rc.country === 'US') ? 'selected' : ''}>US</option>
            <option value="CA" ${rc.country === 'CA' ? 'selected' : ''}>Canada</option>
          </select>
        </div>
        <div class="form-field">
          <label>Version</label>
          <input name="version" value="${esc(rc.version || 'v1')}" placeholder="v1, 2025, 2026-Q1, etc.">
        </div>
        <div class="form-field">
          <label title="Service class determines economy vs express tier">Service Class</label>
          <select name="service_class">
            <option value="economy" ${(!rc.service_class || rc.service_class === 'economy') ? 'selected' : ''}>Economy</option>
            <option value="express" ${rc.service_class === 'express' ? 'selected' : ''}>Express</option>
          </select>
        </div>
        <div class="form-field">
          <label title="Card type indicates buy/sell and current/previous rate generation">Card Type</label>
          <select name="card_type">
            <option value="sell_current" ${(!rc.card_type || rc.card_type === 'sell_current') ? 'selected' : ''}>Sell — Current</option>
            <option value="buy_current" ${rc.card_type === 'buy_current' ? 'selected' : ''}>Buy — Current</option>
            <option value="sell_previous" ${rc.card_type === 'sell_previous' ? 'selected' : ''}>Sell — Previous</option>
            <option value="buy_previous" ${rc.card_type === 'buy_previous' ? 'selected' : ''}>Buy — Previous</option>
          </select>
        </div>
        <div class="form-field">
          <label title="DIM divisor controls dimensional weight calculation. 166 = USPS standard; 139 = FedEx/UPS standard">
            DIM Divisor
            <span class="tooltip-icon" title="166 = USPS standard; 139 = FedEx/UPS standard">?</span>
          </label>
          <select name="dim_divisor" id="rc-dim-divisor">
            <option value="166" ${(!rc.dim_divisor || rc.dim_divisor == 166) ? 'selected' : ''}>166 (USPS/DHL/OSM standard)</option>
            <option value="139" ${rc.dim_divisor == 139 ? 'selected' : ''}>139 (FedEx/UPS standard)</option>
            <option value="225" ${rc.dim_divisor == 225 ? 'selected' : ''}>225 (Amazon standard)</option>
            <option value="custom">Custom...</option>
          </select>
          <input type="number" id="rc-dim-divisor-custom" name="dim_divisor_custom" placeholder="Enter divisor" step="0.1" min="1"
            class="${rc.dim_divisor && rc.dim_divisor != 166 && rc.dim_divisor != 139 && rc.dim_divisor != 225 ? '' : 'hidden'}"
            value="${rc.dim_divisor && rc.dim_divisor != 166 && rc.dim_divisor != 139 && rc.dim_divisor != 225 ? rc.dim_divisor : ''}">
        </div>
        <div class="form-field">
          <label>Pricing Type</label>
          <select name="pricing_type">
            <option value="WEIGHT_POUNDS" ${(!rc.pricing_type || rc.pricing_type === 'WEIGHT_POUNDS') ? 'selected' : ''}>Weight (lbs)</option>
            <option value="WEIGHT_OUNCES" ${rc.pricing_type === 'WEIGHT_OUNCES' ? 'selected' : ''}>Weight (oz)</option>
            <option value="CUBICFEET" ${rc.pricing_type === 'CUBICFEET' ? 'selected' : ''}>Cubic Feet</option>
          </select>
        </div>
        <div class="form-field span-2" style="border-top:1px solid var(--color-border);padding-top:12px;margin-top:4px">
          <label style="font-weight:600;font-size:13px;color:var(--color-text-muted)">Fuel Surcharge</label>
        </div>
        <div class="form-field">
          <label>Fuel Rate</label>
          <input type="number" name="fuel_rate" step="0.001" min="0" max="1" value="${rc.fuel_rate || 0}" placeholder="e.g. 0.18 for 18%">
        </div>
        <div class="form-field">
          <label>Fuel Type</label>
          <select name="fuel_type">
            <option value="percentage" ${(!rc.fuel_type || rc.fuel_type === 'percentage') ? 'selected' : ''}>Percentage of base rate</option>
            <option value="per_lb" ${rc.fuel_type === 'per_lb' ? 'selected' : ''}>Per pound ($)</option>
          </select>
        </div>
        <div class="form-field">
          <label>Fuel Discount</label>
          <input type="number" name="fuel_discount" step="0.01" min="0" max="1" value="${rc.fuel_discount || 0}" placeholder="e.g. 0.05 for 5% off">
        </div>
        <div class="form-field">
          <label title="Buy-side fuel rate applied to cost calculation">Buy Fuel Rate</label>
          <input type="number" name="fuel_rate_buy" step="0.001" min="0" max="1" value="${rc.fuel_rate_buy || 0}" placeholder="e.g. 0.15 for 15%">
        </div>
        <div class="form-field">
          <label title="Sell-side fuel rate applied to sell price calculation">Sell Fuel Rate</label>
          <input type="number" name="fuel_rate_sell" step="0.001" min="0" max="1" value="${rc.fuel_rate_sell || 0}" placeholder="e.g. 0.18 for 18%">
        </div>
        <div class="form-field">
          <label title="DIM divisor used for buy-side cost calculations. Default 166.">Buy DIM Divisor</label>
          <input type="number" name="dim_divisor_buy" step="0.1" min="1" value="${rc.dim_divisor_buy || 166}" placeholder="166">
        </div>
        <div class="form-field span-2" style="border-top:1px solid var(--color-border);padding-top:12px;margin-top:4px">
          <label style="font-weight:600;font-size:13px;color:var(--color-text-muted)">Conditional DIM Weight</label>
        </div>
        <div class="form-field">
          <label title="Package cubic inch threshold. Above this, use main DIM divisor. Below, use alt divisor (or actual weight).">Cubic Inch Threshold <span class="tooltip-icon" title="e.g. 1728 for UPS. Below this uses alt divisor.">?</span></label>
          <input type="number" name="dim_threshold_cu_in" step="1" min="0" value="${rc.dim_threshold_cu_in || 0}" placeholder="0 = disabled">
        </div>
        <div class="form-field">
          <label title="Alternative DIM divisor for packages below the threshold">Alt DIM Divisor <span class="tooltip-icon" title="Used when cubic inches are below threshold. 0 = use actual weight.">?</span></label>
          <input type="number" name="dim_divisor_alt" step="0.1" min="0" value="${rc.dim_divisor_alt || 0}" placeholder="0 = use actual weight">
        </div>
        <div class="form-field span-2"><label>Description</label><textarea name="description" rows="2">${esc(rc.description)}</textarea></div>
        <div class="form-field span-2">
          <label>Rate Grid (paste CSV: weight in first column, zones in remaining columns)</label>
          <textarea name="rate_csv" rows="6" placeholder="Weight,Zone1,Zone2,Zone3,...&#10;1,5.50,6.00,6.50,...&#10;2,6.00,6.50,7.00,..."></textarea>
        </div>
      </div>
      <div class="modal-actions"><button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button><button type="submit" class="btn-primary">${existing ? 'Update' : 'Create'}</button></div>
    </form>
  `);
  // DIM divisor custom toggle
  document.getElementById('rc-dim-divisor').addEventListener('change', function() {
    const customEl = document.getElementById('rc-dim-divisor-custom');
    if (this.value === 'custom') {
      customEl.classList.remove('hidden');
      customEl.focus();
    } else {
      customEl.classList.add('hidden');
    }
  });
}

async function submitRateCard(id) {
  const form = document.getElementById('rc-form');
  const fd = new FormData(form);
  const rateCSV = fd.get('rate_csv');
  let rateGrid = {};

  if (rateCSV.trim()) {
    const lines = rateCSV.trim().split('\n');
    lines.forEach((line, i) => {
      if (i === 0 && line.toLowerCase().includes('weight')) return;
      const parts = line.split(',').map(p => p.trim());
      const weight = parts[0];
      rateGrid[weight] = {};
      for (let z = 1; z < parts.length; z++) {
        rateGrid[weight][String(z)] = parseFloat(parts[z]) || 0;
      }
    });
  }

  // Get DIM divisor
  const dimSel = document.getElementById('rc-dim-divisor');
  let dimDivisor = 166;
  if (dimSel) {
    if (dimSel.value === 'custom') {
      dimDivisor = parseFloat(document.getElementById('rc-dim-divisor-custom').value) || 166;
    } else {
      dimDivisor = parseFloat(dimSel.value) || 166;
    }
  }

  const body = {
    name: fd.get('name'), service_type: fd.get('service_type'),
    carrier: fd.get('carrier'), description: fd.get('description'),
    pricing_type: fd.get('pricing_type') || 'WEIGHT_POUNDS',
    dim_divisor: dimDivisor,
    currency: fd.get('currency') || 'USD',
    country: fd.get('country') || 'US',
    version: fd.get('version') || 'v1',
    service_class: fd.get('service_class') || 'economy',
    card_type: fd.get('card_type') || 'sell_current',
    fuel_rate: parseFloat(fd.get('fuel_rate')) || 0,
    fuel_type: fd.get('fuel_type') || 'percentage',
    fuel_discount: parseFloat(fd.get('fuel_discount')) || 0,
    fuel_rate_buy: parseFloat(fd.get('fuel_rate_buy')) || 0,
    fuel_rate_sell: parseFloat(fd.get('fuel_rate_sell')) || 0,
    dim_divisor_buy: parseFloat(fd.get('dim_divisor_buy')) || 166,
    dim_threshold_cu_in: parseFloat(fd.get('dim_threshold_cu_in')) || 0,
    dim_divisor_alt: parseFloat(fd.get('dim_divisor_alt')) || 0,
    rate_grid: rateGrid, zone_mapping: {}
  };

  try {
    if (id) {
      await api(`/rate-cards/${id}`, { method: 'PUT', body });
    } else {
      await api('/rate-cards', { method: 'POST', body });
    }
    closeModal();
    showToast(id ? 'Rate card updated' : 'Rate card created', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

function filterRateCardsByCarrier(carrier) {
  // Update button active states
  document.querySelectorAll('.rc-filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.trim().startsWith(carrier === 'All' ? 'All' : carrier));
  });
  // Show/hide carrier groups
  document.querySelectorAll('.rc-carrier-group').forEach(group => {
    if (carrier === 'All' || group.dataset.carrier === carrier) {
      group.style.display = '';
    } else {
      group.style.display = 'none';
    }
  });
}

async function showRateCardDetail(id) {
  try {
    const rc = await api(`/rate-cards/${id}`);
    const grid = rc.rate_grid_json;
    const weights = Object.keys(grid).sort((a, b) => parseFloat(a) - parseFloat(b));
    const zones = weights.length > 0 ? Object.keys(grid[weights[0]]).sort((a, b) => parseInt(a) - parseInt(b)) : [];
    const dimDivisor = rc.dim_divisor || 166;

    openModal(rc.name, `
      <div class="rc-detail-meta">
        ${esc(rc.carrier)} · ${esc(rc.service_type)} · ${esc(rc.description || '')}
        <span class="rc-detail-badge" title="DIM divisor for dimensional weight calculation (166=USPS, 139=FedEx/UPS)">DIM ÷${dimDivisor}</span>
        <span class="rc-detail-badge" title="Pricing type">${rc.pricing_type === 'CUBICFEET' ? 'Cubic Feet' : rc.pricing_type === 'WEIGHT_OUNCES' ? 'Weight (oz)' : 'Weight (lbs)'}</span>
        <span class="rc-detail-badge" title="Currency">${rc.currency || 'USD'}</span>
        ${rc.country === 'CA' ? '<span class="rc-detail-badge" title="Canada service">🇨🇦 Canada</span>' : ''}
        ${rc.version && rc.version !== 'v1' ? `<span class="rc-detail-badge" title="Version">${esc(rc.version)}</span>` : ''}
      </div>
      ${(rc.fuel_rate > 0 || rc.dim_threshold_cu_in > 0) ? `
      <div class="rc-detail-extra-section">
        ${rc.fuel_rate > 0 ? `
        <div class="rc-detail-extra-group">
          <div class="rc-detail-extra-label">Fuel Surcharge</div>
          <div class="rc-detail-extra-row">
            <span class="rc-detail-badge-sm" title="Fuel rate">Rate: ${rc.fuel_type === 'per_lb' ? formatCurrency(rc.fuel_rate) + '/lb' : (rc.fuel_rate * 100).toFixed(1) + '%'}</span>
            <span class="rc-detail-badge-sm" title="Fuel type">${rc.fuel_type === 'per_lb' ? 'Per pound' : 'Pct of base'}</span>
            ${rc.fuel_discount > 0 ? `<span class="rc-detail-badge-sm" title="Fuel discount">Discount: ${(rc.fuel_discount * 100).toFixed(0)}%</span>` : ''}
          </div>
        </div>` : '<div class="rc-detail-extra-group"><div class="rc-detail-extra-label">Fuel Surcharge</div><span class="rc-detail-muted">None configured</span></div>'}
        ${rc.dim_threshold_cu_in > 0 ? `
        <div class="rc-detail-extra-group">
          <div class="rc-detail-extra-label">Conditional DIM</div>
          <div class="rc-detail-extra-row">
            <span class="rc-detail-badge-sm" title="Cubic inch threshold">Threshold: ${rc.dim_threshold_cu_in} cu in</span>
            <span class="rc-detail-badge-sm" title="Alt DIM divisor">${rc.dim_divisor_alt > 0 ? 'Alt DIM ÷' + rc.dim_divisor_alt : 'Alt: actual weight'}</span>
          </div>
        </div>` : '<div class="rc-detail-extra-group"><div class="rc-detail-extra-label">Conditional DIM</div><span class="rc-detail-muted">Standard</span></div>'}
      </div>` : ''}
      <div class="table-container">
        <table class="data-table compact rate-grid-table">
          <thead><tr><th>Weight</th>${zones.map(z => `<th>Zone ${z}</th>`).join('')}</tr></thead>
          <tbody>
            ${weights.map(w => `
              <tr><td class="fw-500">${w} ${rc.pricing_type === 'CUBICFEET' ? 'cu ft' : 'lbs'}</td>${zones.map(z => `<td class="num">${grid[w][z] != null ? formatCurrency(grid[w][z]) : '—'}</td>`).join('')}</tr>
            `).join('')}
          </tbody>
        </table>
      </div>
      <div class="modal-actions">
        <button class="btn-secondary btn-delete-outline" onclick="deleteRateCard(${id})" title="Permanently remove this rate card from the system">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          Delete
        </button>
        <button class="btn-secondary" onclick="cloneRateCard(${id})" title="Create a duplicate of this rate card">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          Clone
        </button>
        <button class="btn-secondary" onclick="exportRateCardCSV(${id})" title="Download this rate card as a CSV file">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Export CSV
        </button>
        <button class="btn-secondary" onclick="showImportCSVToCard(${id})" title="Import CSV data into this rate card's grid">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          Import CSV
        </button>
        <button class="btn-secondary" onclick="closeModal(); showCompareCardsModal(${id})" title="Compare this rate card against another">Compare...</button>
        <button class="btn-primary" onclick="closeModal(); showRateCardModal(${JSON.stringify({id: rc.id, name: rc.name, service_type: rc.service_type, carrier: rc.carrier, description: rc.description, dim_divisor: dimDivisor, pricing_type: rc.pricing_type, currency: rc.currency || 'USD', country: rc.country || 'US', version: rc.version || 'v1', fuel_rate: rc.fuel_rate || 0, fuel_type: rc.fuel_type || 'percentage', fuel_discount: rc.fuel_discount || 0, dim_threshold_cu_in: rc.dim_threshold_cu_in || 0, dim_divisor_alt: rc.dim_divisor_alt || 0}).replace(/"/g, '&quot;')})">Edit</button>
      </div>
    `);
  } catch (e) { showToast(e.message, 'error'); }
}

function deleteRateCard(id) {
  // Fetch the rate card name for the confirmation dialog
  api(`/rate-cards/${id}`).then(rc => {
    const rcName = rc.name || `Rate Card #${id}`;
    closeModal();
    setTimeout(() => {
      openModal('Delete Rate Card', `
        <div class="delete-confirm-modal">
          <div class="delete-confirm-warning">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
          </div>
          <p class="delete-confirm-title">Permanently delete this rate card?</p>
          <div class="delete-confirm-card-name">${esc(rcName)}</div>
          <p class="delete-confirm-desc">This will <strong>permanently remove</strong> this rate card from the system. It will no longer be available for any future or existing client analyses. Any past analyses that used this card will lose access to it. This action cannot be undone.</p>
          <div class="form-field" style="margin-top:16px;">
            <label class="delete-confirm-label">Type <strong>delete</strong> to confirm</label>
            <input type="text" id="delete-confirm-input" class="delete-confirm-input" placeholder="Type delete here…" autocomplete="off" oninput="
              const btn = document.getElementById('delete-confirm-btn');
              btn.disabled = this.value.trim().toLowerCase() !== 'delete';
              btn.classList.toggle('btn-danger-active', this.value.trim().toLowerCase() === 'delete');
            ">
          </div>
          <div class="modal-actions" style="margin-top:20px;">
            <button class="btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn-danger" id="delete-confirm-btn" disabled onclick="confirmDeleteRateCard(${id})">Delete Rate Card</button>
          </div>
        </div>
      `);
      setTimeout(() => document.getElementById('delete-confirm-input')?.focus(), 100);
    }, 200);
  }).catch(() => {
    showToast('Could not load rate card details', 'error');
  });
}

async function confirmDeleteRateCard(id) {
  const input = document.getElementById('delete-confirm-input');
  if (!input || input.value.trim().toLowerCase() !== 'delete') {
    showToast('Please type "delete" to confirm', 'error');
    return;
  }
  try {
    await api(`/rate-cards/${id}`, { method: 'DELETE' });
    closeModal();
    showToast('Rate card permanently deleted', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

// ─── Rate Card Clone ──────────────────────────────────────────────────────────
async function cloneRateCard(id) {
  try {
    const result = await api(`/rate-cards/${id}/clone`, { method: 'POST' });
    closeModal();
    showToast(`Rate card cloned as "${result.name}"`, 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

// ─── Rate Card Export CSV ─────────────────────────────────────────────────────
function exportRateCardCSV(id) {
  const url = API + `/rate-cards/${id}/export-csv` + (state.token ? `?token=${encodeURIComponent(state.token)}` : '');
  const a = document.createElement('a');
  a.href = url;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast('Downloading rate card CSV...', 'success');
}

// ─── Rate Card Import CSV to Existing Card ────────────────────────────────────
function showImportCSVToCard(rcId) {
  closeModal();
  setTimeout(() => {
    openModal('Import CSV Data', `
      <div class="modal-form">
        <p class="text-muted" style="margin-bottom:12px;font-size:13px;">Upload or paste CSV data to replace this rate card's grid. First column = weight, remaining columns = zone prices.</p>
        <div class="form-field">
          <label>Upload CSV File</label>
          <input type="file" id="csv-import-file" accept=".csv,.txt" onchange="handleImportToCardFile(this)">
        </div>
        <div class="form-field">
          <label>Or paste CSV data</label>
          <textarea id="csv-import-paste" rows="8" placeholder="Weight,Zone 1,Zone 2,..." style="font-family:monospace;font-size:12px;"></textarea>
        </div>
        <div id="csv-import-preview" style="margin:8px 0;"></div>
        <div class="modal-actions">
          <button class="btn-secondary" onclick="closeModal()">Cancel</button>
          <button class="btn-primary" onclick="submitImportToCard(${rcId})">Import &amp; Replace Grid</button>
        </div>
      </div>
    `);
  }, 200);
}

function handleImportToCardFile(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = function(ev) {
    document.getElementById('csv-import-paste').value = ev.target.result;
    const lines = ev.target.result.trim().split('\n');
    document.getElementById('csv-import-preview').innerHTML = `<span class="text-muted" style="font-size:12px;">Loaded ${file.name} — ${lines.length} lines</span>`;
  };
  reader.readAsText(file);
}

async function submitImportToCard(rcId) {
  const csvData = document.getElementById('csv-import-paste')?.value || '';
  if (!csvData.trim()) { showToast('No CSV data provided', 'error'); return; }
  try {
    const result = await api(`/rate-cards/${rcId}/import-csv`, {
      method: 'POST',
      body: { csv_data: csvData }
    });
    closeModal();
    showToast(result.message, 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

// ─── Rate Card CSV Import ─────────────────────────────────────────────────────
function showImportCSVModal() {
  openModal('Import Rate Card CSV', `
    <div class="modal-form">
      <p class="text-muted" style="margin-bottom:12px;font-size:13px;">Supports Wizmo 4-header format (Row1=name, Row2=MIN days, Row3=MAX days, Row4=header+zones, Row5+=data) or simple CSV (header row + data rows).</p>
      <div class="form-field">
        <label>Upload CSV File</label>
        <input type="file" id="csv-file-input" accept=".csv,.txt" onchange="handleCSVFileSelect(this)">
      </div>
      <div class="form-field">
        <label>— or paste CSV text —</label>
        <textarea id="csv-paste-area" rows="8" style="width:100%;font-family:monospace;font-size:12px;" placeholder="Paste CSV content here..." oninput="handleCSVPaste(this.value)"></textarea>
      </div>
      <div id="csv-format-badge" style="display:none;margin-bottom:8px;"></div>
      <div id="csv-preview-container" style="display:none;">
        <div style="font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px;">Preview (first 20 rows)</div>
        <div class="csv-import-preview">
          <div class="table-container"><table id="csv-preview-table" class="data-table csv-preview-table"></table></div>
        </div>
      </div>
      <div id="csv-import-status" style="display:none;padding:8px 12px;border-radius:6px;font-size:13px;margin-top:8px;"></div>
    </div>
    <div class="modal-actions">
      <button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn-primary" id="csv-import-btn" onclick="submitCSVImport()" disabled>Import Rate Card</button>
    </div>
  `);
  window._csvParsed = null;
}

function handleCSVFileSelect(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    document.getElementById('csv-paste-area').value = e.target.result;
    handleCSVPaste(e.target.result);
  };
  reader.readAsText(file);
}

function handleCSVPaste(text) {
  if (!text || !text.trim()) {
    document.getElementById('csv-preview-container').style.display = 'none';
    document.getElementById('csv-format-badge').style.display = 'none';
    document.getElementById('csv-import-btn').disabled = true;
    window._csvParsed = null;
    return;
  }
  const parsed = parseCSVForPreview(text);
  window._csvParsed = { raw: text, info: parsed };

  // Show format badge
  const badgeEl = document.getElementById('csv-format-badge');
  badgeEl.style.display = 'inline-block';
  badgeEl.innerHTML = parsed.isWizmo
    ? `<span class="rc-badge-type" style="background:var(--accent-blue,#3b82f6);color:#fff;padding:3px 10px;border-radius:12px;font-size:12px;">Wizmo 4-Header Format — "${esc(parsed.name)}"</span>`
    : `<span class="rc-badge-type" style="background:var(--surface-3);color:var(--text-primary);padding:3px 10px;border-radius:12px;font-size:12px;">Simple CSV Format</span>`;

  // Render preview table
  const rows = parsed.previewRows;
  if (rows.length > 0) {
    const headers = rows[0];
    const dataRows = rows.slice(1);
    const tableEl = document.getElementById('csv-preview-table');
    tableEl.innerHTML = `
      <thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
      <tbody>${dataRows.map(r => `<tr>${r.map(c => `<td>${esc(String(c ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody>
    `;
    document.getElementById('csv-preview-container').style.display = 'block';
  }

  document.getElementById('csv-import-btn').disabled = false;
}

function parseCSVForPreview(text) {
  const lines = text.trim().split('\n').map(l => l.trim()).filter(l => l);
  if (lines.length < 2) return { isWizmo: false, previewRows: [], name: '' };

  // Parse a single CSV line respecting quotes
  function parseLine(line) {
    const result = [];
    let cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') { inQ = !inQ; }
      else if (ch === ',' && !inQ) { result.push(cur.trim()); cur = ''; }
      else { cur += ch; }
    }
    result.push(cur.trim());
    return result;
  }

  const firstCells = parseLine(lines[0]);
  // Wizmo format: first row has service name as sole cell, OR first cell non-numeric and second line has MIN_DELIVERY_DAYS
  const isWizmo = lines.length >= 4 &&
    (lines[1].toUpperCase().includes('MIN_DELIVERY') ||
     lines[1].toUpperCase().includes('DELIVERY_DAYS') ||
     (firstCells.length === 1 && !/^\d/.test(firstCells[0])));

  let name = '';
  let previewRows = [];

  if (isWizmo) {
    name = firstCells[0] || '';
    // Row4 = header row, Row5+ = data
    const headerLine = lines[3] || '';
    const headerCells = parseLine(headerLine);
    previewRows.push(headerCells);
    const dataLines = lines.slice(4, 24); // up to 20 data rows
    dataLines.forEach(dl => previewRows.push(parseLine(dl)));
  } else {
    // Simple format: first row = headers
    const allParsed = lines.slice(0, 21).map(parseLine);
    previewRows = allParsed;
    name = '';
  }

  return { isWizmo, previewRows, name };
}

async function submitCSVImport() {
  if (!window._csvParsed) return;
  const statusEl = document.getElementById('csv-import-status');
  const btnEl = document.getElementById('csv-import-btn');
  btnEl.disabled = true;
  btnEl.innerHTML = '<span class="spinner-sm"></span> Importing...';
  statusEl.style.display = 'none';

  try {
    const res = await api('/rate-cards', {
      method: 'POST',
      body: { csv_data: window._csvParsed.raw }
    });
    closeModal();
    showToast(`Rate card "${res.name || 'Imported'}" created successfully`, 'success');
    window._csvParsed = null;
    router();
  } catch (e) {
    statusEl.style.display = 'block';
    statusEl.style.background = 'var(--error-bg, #fee2e2)';
    statusEl.style.color = 'var(--error-text, #dc2626)';
    statusEl.textContent = 'Import failed: ' + e.message;
    btnEl.disabled = false;
    btnEl.innerHTML = 'Import Rate Card';
  }
}

// ─── Rate Card Comparison Matrix ──────────────────────────────────────────────
async function showCompareCardsModal(preselectedId) {
  let rateCards = [];
  try { rateCards = await api('/rate-cards'); } catch (e) { showToast('Failed to load rate cards', 'error'); return; }
  if (rateCards.length < 2) { showToast('Need at least 2 rate cards to compare', 'error'); return; }

  const opts = rateCards.map(rc => `<option value="${rc.id}" ${rc.id === preselectedId ? 'selected' : ''}>${esc(rc.name)}</option>`).join('');
  const opts2 = rateCards.map((rc, i) => `<option value="${rc.id}" ${(!preselectedId && i === 1) ? 'selected' : (preselectedId && rc.id !== preselectedId && i === (rateCards[0].id === preselectedId ? 1 : 0)) ? 'selected' : ''}>${esc(rc.name)}</option>`).join('');

  openModal('Compare Rate Cards', `
    <div style="min-width:480px;">
      <div style="display:flex;gap:12px;align-items:flex-end;margin-bottom:16px;">
        <div class="form-field" style="flex:1;margin:0;">
          <label>Card 1 (baseline)</label>
          <select id="compare-card1">${opts}</select>
        </div>
        <div class="form-field" style="flex:1;margin:0;">
          <label>Card 2 (compare to)</label>
          <select id="compare-card2">${opts2}</select>
        </div>
        <button class="btn-primary" onclick="runCompareCards()">Compare</button>
      </div>
      <div id="compare-results"><div class="empty-inline">Select two rate cards and click Compare</div></div>
    </div>
    <div class="modal-actions"><button class="btn-secondary" onclick="closeModal()">Close</button></div>
  `, { wide: true });
}

async function runCompareCards() {
  const card1 = parseInt(document.getElementById('compare-card1').value);
  const card2 = parseInt(document.getElementById('compare-card2').value);
  if (card1 === card2) { showToast('Select two different rate cards', 'error'); return; }

  const resultsEl = document.getElementById('compare-results');
  resultsEl.innerHTML = '<div class="analysis-loading"><div class="spinner-sm"></div><span>Comparing rate cards...</span></div>';

  try {
    const res = await api('/rate-cards/compare', {
      method: 'POST',
      body: { card_id_1: card1, card_id_2: card2 }
    });
    resultsEl.innerHTML = renderCompareMatrix(res);
  } catch (e) {
    resultsEl.innerHTML = `<div class="empty-state">Comparison failed: ${esc(e.message)}</div>`;
  }
}

function renderCompareMatrix(data) {
  const { card1_name, card2_name, zones, weights, matrix, summary } = data;
  if (!matrix || matrix.length === 0) return '<div class="empty-inline">No overlapping weights/zones to compare</div>';

  // Summary stats bar
  const summaryHtml = summary ? `
    <div class="compare-summary">
      <div class="compare-stat">
        <span class="compare-stat-label">${esc(card1_name)}</span>
        <span class="compare-stat-val compare-cheaper">cheaper in ${summary.card1_cheaper_count} of ${summary.total_cells} cells</span>
      </div>
      <div class="compare-stat">
        <span class="compare-stat-label">${esc(card2_name)}</span>
        <span class="compare-stat-val compare-expensive">cheaper in ${summary.card2_cheaper_count} of ${summary.total_cells} cells</span>
      </div>
      <div class="compare-stat">
        <span class="compare-stat-label">Avg difference</span>
        <span class="compare-stat-val">${summary.avg_pct_diff != null ? (summary.avg_pct_diff > 0 ? '+' : '') + summary.avg_pct_diff.toFixed(1) + '%' : 'N/A'}</span>
      </div>
    </div>
  ` : '';

  // Build heatmap table
  const zonesArr = zones || [];
  const rows = matrix.map(row => {
    const cells = (row.zones || []).map(cell => {
      if (cell.pct_diff == null) return `<td class="heatmap-cell heatmap-na">—</td>`;
      const pct = cell.pct_diff;
      const cls = pct > 2 ? 'heatmap-positive' : pct < -2 ? 'heatmap-negative' : 'heatmap-neutral';
      const label = (pct > 0 ? '+' : '') + pct.toFixed(1) + '%';
      const title = `Card1: $${cell.card1_rate?.toFixed(2) ?? 'N/A'} | Card2: $${cell.card2_rate?.toFixed(2) ?? 'N/A'}`;
      return `<td class="heatmap-cell ${cls}" title="${title}">${label}</td>`;
    }).join('');
    return `<tr><td class="heatmap-weight">${row.weight} lb</td>${cells}</tr>`;
  }).join('');

  return `
    ${summaryHtml}
    <div style="font-size:11px;color:var(--text-tertiary);margin-bottom:6px;">
      % = how much more expensive <strong>${esc(card1_name)}</strong> is vs <strong>${esc(card2_name)}</strong>.
      <span style="color:#dc2626;">Red = Card1 more expensive</span> &nbsp;
      <span style="color:#16a34a;">Green = Card1 cheaper</span>
    </div>
    <div class="compare-matrix-wrap">
      <table class="compare-matrix">
        <thead>
          <tr>
            <th>Weight</th>
            ${zonesArr.map(z => `<th>Zone ${esc(String(z))}</th>`).join('')}
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

// ─── Admin Zone Charts ────────────────────────────────────────────────────────
async function renderAdminZoneCharts(el) {
  setAdminPageTitle('Zone Charts');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const charts = await api('/zone-charts');
    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Zone Lookup</h2>
          <div class="zone-coverage-badge" title="Total ZIP codes and FSAs in the zone database">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            41,877 US ZIPs &nbsp;&bull;&nbsp; 1,698 CA FSAs &nbsp;&bull;&nbsp; Powered by SAPT
          </div>
        </div>

        <!-- Main Zone Lookup Tool -->
        <div class="card zone-lookup-card">
          <div class="zone-lookup-header">
            <div>
              <div class="card-label" style="margin-bottom:4px;">Real-Time Zone Lookup</div>
              <p class="zone-lookup-desc">Type a US ZIP code or Canadian postal code (FSA) to instantly see all carrier zones and DAS flags.</p>
            </div>
          </div>
          <div class="zone-lookup-search-wrap">
            <svg class="zone-lookup-search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="zl-input" class="zone-lookup-main-input"
              placeholder="Enter ZIP code or Canadian postal code (e.g. 10001 or M5V)"
              maxlength="10" oninput="zoneLookupPage(this.value)" autocomplete="off">
            <button class="zone-lookup-clear hidden" id="zl-clear" onclick="clearZoneLookup()" title="Clear">&times;</button>
          </div>
          <div id="zl-results" class="zone-lookup-page-results"></div>
        </div>

        <!-- Legacy Zone Charts List -->
        <div class="card" style="margin-top:var(--space-4);">
          <div class="card-header-row">
            <div class="card-label" style="margin-bottom:0;">Uploaded Zone Charts</div>
            <button class="btn-primary btn-sm" onclick="showUploadZoneChartModal()" title="Upload a new zone chart CSV">+ Upload Zone Chart</button>
          </div>
          <p style="color:var(--color-text-muted);font-size:var(--text-sm);margin-bottom:var(--space-3);margin-top:var(--space-2);">Legacy zone chart CSVs used for manual zone mapping. Real-time lookup above uses the SAPT database.</p>
          ${charts.length === 0 ? `
            <div class="empty-state" style="padding:var(--space-4);">
              <div style="font-size:28px;margin-bottom:8px;">&#128506;</div>
              <div>No legacy zone charts uploaded</div>
            </div>
          ` : `
            <div class="zone-chart-list">
              ${charts.map(zc => `
                <div class="zc-item" onclick="showZoneChartDetail(${zc.id})" title="View ${esc(zc.name)}">
                  <div class="zc-icon">&#128506;</div>
                  <div class="zc-body">
                    <div class="zc-name">${esc(zc.name)}</div>
                    <div class="zc-meta">
                      ${zc.carrier ? `<span class="badge">${esc(zc.carrier)}</span>` : ''}
                      ${zc.origin_zip ? `<span class="badge badge-outline">Origin: ${esc(zc.origin_zip)}</span>` : ''}
                      <span class="text-muted">${zc.row_count?.toLocaleString() || 0} ZIP mappings</span>
                      <span class="text-muted">${formatDate(zc.created_at)}</span>
                    </div>
                  </div>
                  <div class="zc-actions">
                    <button class="btn-secondary btn-sm" onclick="event.stopPropagation(); deleteZoneChart(${zc.id}, '${esc(zc.name)}')" title="Delete this zone chart">Delete</button>
                  </div>
                </div>
              `).join('')}
            </div>
          `}
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load zone charts: ${esc(e.message)}</div></div>`;
  }
}

// ─── Zone Lookup Page Logic ─────────────────────────────────────────────────────
let _zoneLookupTimer = null;
function zoneLookupPage(val) {
  clearTimeout(_zoneLookupTimer);
  const resultsEl = document.getElementById('zl-results');
  const clearBtn = document.getElementById('zl-clear');
  if (!resultsEl) return;
  const zip = val.trim();
  if (clearBtn) clearBtn.classList.toggle('hidden', !zip);
  if (zip.length < 3) {
    resultsEl.innerHTML = '';
    return;
  }
  resultsEl.innerHTML = '<div class="zone-lookup-loading"><span class="spinner-sm"></span> Looking up zones for <strong>' + esc(zip) + '</strong>…</div>';
  _zoneLookupTimer = setTimeout(async () => {
    try {
      const data = await api('/zones/lookup?zip=' + encodeURIComponent(zip));
      resultsEl.innerHTML = renderZoneLookupResult(data, true);
    } catch (e) {
      resultsEl.innerHTML = `<div class="zone-lookup-error"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> No zone data found for &ldquo;${esc(zip)}&rdquo;. Try a different ZIP or FSA.</div>`;
    }
  }, 300);
}

function clearZoneLookup() {
  const inp = document.getElementById('zl-input');
  if (inp) { inp.value = ''; inp.focus(); }
  const resultsEl = document.getElementById('zl-results');
  if (resultsEl) resultsEl.innerHTML = '';
  const clearBtn = document.getElementById('zl-clear');
  if (clearBtn) clearBtn.classList.add('hidden');
}

// Shared zone lookup result renderer (used by dashboard widget + full page)
function renderZoneLookupResult(data, fullView) {
  const zones = data.zones || {};
  const dasFlags = data.das_flags || {};
  const carriers = Object.keys(zones).sort();
  if (carriers.length === 0) {
    return '<div class="zone-lookup-empty">No carrier zones found for this location.</div>';
  }
  const isCA = data.country === 'CA';
  const locationLine = isCA
    ? `${data.zip} &mdash; ${data.province || data.state || ''} &mdash; <span class="zone-country-badge zone-ca">Canada</span>`
    : `${data.zip} &mdash; ${data.state || ''} &mdash; <span class="zone-country-badge zone-us">United States</span>`;

  const cards = carriers.map(carrier => {
    const zone = zones[carrier];
    const hasDas = dasFlags[carrier];
    const zoneNum = parseInt(zone) || 0;
    const zoneColor = zoneNum <= 2 ? 'zone-near' : zoneNum <= 4 ? 'zone-mid' : zoneNum <= 6 ? 'zone-far' : 'zone-distant';
    return `
      <div class="zone-result-card ${hasDas ? 'zone-has-das' : ''}">
        <div class="zone-result-carrier">${esc(carrier)}</div>
        <div class="zone-result-zone ${zoneColor}" title="Zone ${zone} for ${carrier}">Zone ${esc(String(zone))}</div>
        ${hasDas ? '<div class="zone-das-flag" title="Delivery Area Surcharge applies"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> DAS</div>' : ''}
      </div>`;
  }).join('');

  const dasList = Object.entries(dasFlags).filter(([,v]) => v).map(([k]) => k);

  return `
    <div class="zone-lookup-result-header">
      <span class="zone-result-location">${locationLine}</span>
      ${dasList.length > 0 ? `<span class="zone-das-summary" title="These carriers apply a Delivery Area Surcharge for this location"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> DAS: ${dasList.map(esc).join(', ')}</span>` : ''}
    </div>
    <div class="zone-result-grid">${cards}</div>
    ${fullView ? '<p class="zone-result-footer">Zone data powered by SAPT (41,877 US ZIPs + 1,698 CA FSAs)</p>' : ''}
  `;
}

function showUploadZoneChartModal() {
  openModal('Upload Zone Chart', `
    <div class="modal-form">
      <p class="text-muted" style="margin-bottom:12px;font-size:13px;">CSV format: header row with <code>dest_zip,zone</code> columns (or <code>origin_zip,dest_zip,carrier,zone</code> for multi-origin charts). Destination ZIP can be 3-digit prefix or 5-digit full ZIP.</p>
      <div class="form-grid">
        <div class="form-field">
          <label>Chart Name *</label>
          <input id="zc-name" required placeholder="e.g. USPS Zone Chart 2024">
        </div>
        <div class="form-field">
          <label>Carrier</label>
          <select id="zc-carrier">
            <option value="">— Any —</option>
            <option>USPS</option>
            <option>FedEx</option>
            <option>UPS</option>
            <option>DHL</option>
            <option>Other</option>
          </select>
        </div>
        <div class="form-field">
          <label>Origin ZIP (optional)</label>
          <input id="zc-origin-zip" placeholder="e.g. 90210" maxlength="10">
        </div>
      </div>
      <div class="form-field" style="margin-top:4px;">
        <label>Upload CSV File</label>
        <input type="file" id="zc-file-input" accept=".csv,.txt" onchange="handleZCFileSelect(this)">
      </div>
      <div class="form-field">
        <label>— or paste CSV text —</label>
        <textarea id="zc-paste-area" rows="8" style="width:100%;font-family:monospace;font-size:12px;" placeholder="dest_zip,zone&#10;005,2&#10;006,3&#10;..." oninput="handleZCPaste(this.value)"></textarea>
      </div>
      <div id="zc-preview-container" style="display:none;">
        <div style="font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px;">Preview (first 10 rows)</div>
        <div class="csv-import-preview">
          <div class="table-container"><table id="zc-preview-table" class="data-table csv-preview-table"></table></div>
        </div>
      </div>
      <div id="zc-import-status" style="display:none;padding:8px 12px;border-radius:6px;font-size:13px;margin-top:8px;"></div>
    </div>
    <div class="modal-actions">
      <button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button type="button" class="btn-primary" id="zc-submit-btn" onclick="submitZoneChart()">Upload Zone Chart</button>
    </div>
  `);
  window._zcCsvText = null;
}

function handleZCFileSelect(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    document.getElementById('zc-paste-area').value = e.target.result;
    handleZCPaste(e.target.result);
  };
  reader.readAsText(file);
}

function handleZCPaste(text) {
  window._zcCsvText = text && text.trim() ? text : null;
  if (!text || !text.trim()) {
    document.getElementById('zc-preview-container').style.display = 'none';
    return;
  }
  // Parse and preview first 10 rows
  const lines = text.trim().split('\n').slice(0, 11);
  function parseLine(line) {
    const result = []; let cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') { inQ = !inQ; }
      else if (ch === ',' && !inQ) { result.push(cur.trim()); cur = ''; }
      else { cur += ch; }
    }
    result.push(cur.trim()); return result;
  }
  const rows = lines.map(parseLine);
  if (rows.length > 0) {
    const headers = rows[0];
    const dataRows = rows.slice(1);
    const tableEl = document.getElementById('zc-preview-table');
    tableEl.innerHTML = `
      <thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
      <tbody>${dataRows.map(r => `<tr>${r.map(c => `<td>${esc(String(c ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody>
    `;
    document.getElementById('zc-preview-container').style.display = 'block';
  }
}

async function submitZoneChart() {
  const name = document.getElementById('zc-name').value.trim();
  if (!name) { showToast('Chart name is required', 'error'); return; }
  if (!window._zcCsvText) { showToast('Upload or paste CSV data', 'error'); return; }

  const carrier = document.getElementById('zc-carrier').value;
  const originZip = document.getElementById('zc-origin-zip').value.trim();
  const statusEl = document.getElementById('zc-import-status');
  const btnEl = document.getElementById('zc-submit-btn');
  btnEl.disabled = true;
  btnEl.innerHTML = '<span class="spinner-sm"></span> Uploading...';

  try {
    await api('/zone-charts', {
      method: 'POST',
      body: { name, carrier: carrier || null, origin_zip: originZip || null, csv_data: window._zcCsvText }
    });
    closeModal();
    showToast('Zone chart uploaded successfully', 'success');
    window._zcCsvText = null;
    router();
  } catch (e) {
    statusEl.style.display = 'block';
    statusEl.style.background = 'var(--error-bg, #fee2e2)';
    statusEl.style.color = 'var(--error-text, #dc2626)';
    statusEl.textContent = 'Upload failed: ' + e.message;
    btnEl.disabled = false;
    btnEl.innerHTML = 'Upload Zone Chart';
  }
}

async function showZoneChartDetail(id) {
  try {
    const zc = await api(`/zone-charts/${id}`);
    const sampleRows = (zc.sample_rows || []).slice(0, 20);
    const cols = sampleRows.length > 0 ? Object.keys(sampleRows[0]) : [];
    openModal(zc.name, `
      <div style="min-width:400px;">
        <div class="rc-detail-meta" style="margin-bottom:16px;">
          ${zc.carrier ? `<span class="badge">${esc(zc.carrier)}</span>` : ''}
          ${zc.origin_zip ? `<span class="badge badge-outline">Origin: ${esc(zc.origin_zip)}</span>` : ''}
          <span class="text-muted">${(zc.row_count || 0).toLocaleString()} total ZIP mappings</span>
          <span class="text-muted">Uploaded ${formatDate(zc.created_at)}</span>
        </div>
        ${sampleRows.length > 0 ? `
          <div style="font-size:12px;font-weight:600;color:var(--text-secondary);margin-bottom:6px;">Sample rows (first 20)</div>
          <div class="table-container">
            <table class="data-table">
              <thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead>
              <tbody>${sampleRows.map(row => `<tr>${cols.map(c => `<td>${esc(String(row[c] ?? ''))}</td>`).join('')}</tr>`).join('')}</tbody>
            </table>
          </div>
        ` : '<div class="empty-inline">No data rows found</div>'}
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="closeModal()">Close</button>
        <button class="btn-secondary" style="color:var(--error);" onclick="closeModal(); deleteZoneChart(${id}, '${esc(zc.name)}')">Delete</button>
      </div>
    `, { wide: true });
  } catch (e) {
    showToast('Failed to load zone chart: ' + e.message, 'error');
  }
}

async function deleteZoneChart(id, name) {
  if (!confirm(`Delete zone chart "${name}"? This cannot be undone.`)) return;
  try {
    await api(`/zone-charts/${id}`, { method: 'DELETE' });
    showToast('Zone chart deleted', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

// ─── Admin Documents ──────────────────────────────────────────────────────────
function _formatFileSize(bytes) {
  if (!bytes) return '—';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

async function renderAdminDocuments(el) {
  setAdminPageTitle('Documents');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const docs = await api('/documents');
    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Documents</h2>
          <button class="btn-primary btn-sm" onclick="showNewDocModal()">+ Upload Document</button>
        </div>
        ${docs.length === 0 ? '<div class="empty-state">No documents yet. Upload your first document to share with clients.</div>' : `
        <div class="card">
          <div class="table-container">
            <table class="data-table">
              <thead><tr><th>Name</th><th>Category</th><th>File</th><th>Clients</th><th>Date</th><th style="width:100px">Actions</th></tr></thead>
              <tbody>
                ${docs.map(d => `
                  <tr>
                    <td class="fw-500">${esc(d.name)}</td>
                    <td><span class="badge">${esc(d.category)}</span></td>
                    <td>${d.has_file
                      ? `<span class="file-info-inline" style="display:flex;align-items:center;gap:6px"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>${esc(d.filename || 'file')} <span class="text-muted">(${_formatFileSize(d.file_size)})</span></span>`
                      : '<span class="text-muted">No file</span>'}</td>
                    <td>${d.client_count} client${d.client_count !== 1 ? 's' : ''}</td>
                    <td>${formatDate(d.created_at)}</td>
                    <td>
                      <div style="display:flex;gap:4px">
                        ${d.has_file ? `<button class="btn-ghost btn-xs" onclick="downloadDoc(${d.id})" title="Download file"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></button>` : ''}
                        <button class="btn-ghost btn-xs text-danger" onclick="deleteDoc(${d.id}, '${esc(d.name).replace(/'/g, "\\'")}')"
                          title="Delete document"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
                      </div>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>`}
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load documents</div></div>`;
  }
}

function downloadDoc(docId) {
  const url = API + '/documents/' + docId + '/download?token=' + encodeURIComponent(state.token);
  const a = document.createElement('a');
  a.href = url; a.target = '_blank'; a.click();
}

async function deleteDoc(docId, docName) {
  if (!confirm('Delete "' + docName + '"? This will also remove it from any clients it\'s shared with.')) return;
  try {
    await api('/documents/' + docId, { method: 'DELETE' });
    showToast('Document deleted', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

function showNewDocModal() {
  openModal('Upload Document', `
    <form id="doc-form" onsubmit="event.preventDefault(); submitDoc()">
      <div class="form-grid modal-form">
        <div class="form-field span-2"><label>Document Name *</label><input name="name" required placeholder="e.g. Service Overview 2026"></div>
        <div class="form-field">
          <label>Category</label>
          <select name="category"><option>Proposal</option><option>Service Guide</option><option>Rate Sheet</option><option>Contract</option><option>Other</option></select>
        </div>
        <div class="form-field span-2">
          <label>File</label>
          <div id="doc-upload-zone" class="upload-zone-mini" onclick="document.getElementById('doc-file-input').click()" style="border:2px dashed var(--color-border);border-radius:8px;padding:16px;text-align:center;cursor:pointer;transition:border-color 0.2s">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" stroke-width="2" style="margin-bottom:4px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <div id="doc-file-label" style="color:var(--color-text-muted);font-size:13px">Click to choose a file (PDF, DOCX, etc.)</div>
          </div>
          <input type="file" id="doc-file-input" style="display:none" onchange="onDocFileSelect(this)">
        </div>
      </div>
      <div class="modal-actions"><button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button><button type="submit" class="btn-primary">Upload</button></div>
    </form>
  `);
}

function onDocFileSelect(input) {
  const file = input.files[0];
  const label = document.getElementById('doc-file-label');
  const zone = document.getElementById('doc-upload-zone');
  if (file) {
    label.innerHTML = '<strong>' + esc(file.name) + '</strong> (' + _formatFileSize(file.size) + ')';
    label.style.color = 'var(--color-text)';
    zone.style.borderColor = 'var(--color-primary)';
    // Auto-fill name if empty
    const nameInput = document.querySelector('#doc-form input[name="name"]');
    if (nameInput && !nameInput.value) {
      nameInput.value = file.name.replace(/\.[^.]+$/, '').replace(/[_-]/g, ' ');
    }
  } else {
    label.textContent = 'Click to choose a file (PDF, DOCX, etc.)';
    label.style.color = 'var(--color-text-muted)';
    zone.style.borderColor = 'var(--color-border)';
  }
}

async function submitDoc() {
  const form = document.getElementById('doc-form');
  const nameVal = form.querySelector('input[name="name"]').value.trim();
  const catVal = form.querySelector('select[name="category"]').value;
  const fileInput = document.getElementById('doc-file-input');
  const file = fileInput && fileInput.files[0];

  if (!nameVal && !file) {
    showToast('Please enter a name or choose a file', 'error');
    return;
  }

  const fd = new FormData();
  fd.append('name', nameVal);
  fd.append('category', catVal);
  if (file) fd.append('file', file);

  try {
    let url = API + '/documents?token=' + encodeURIComponent(state.token);
    const res = await fetch(url, { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Upload failed');
    closeModal();
    showToast('Document uploaded', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

// ─── Admin Settings ───────────────────────────────────────────────────────────
async function renderAdminSettings(el) {
  setAdminPageTitle('Settings');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const [settings, adminUsers, accessRequests] = await Promise.all([
      api('/settings'),
      api('/admin-users'),
      api('/access-requests')
    ]);
    const currentEmail = (settings.email || '').toLowerCase();
    const pendingRequests = accessRequests.filter(r => r.status === 'pending');
    const pastRequests = accessRequests.filter(r => r.status !== 'pending');
    el.innerHTML = `
      <div class="admin-content">
        <h2 class="page-title">Settings</h2>

        <!-- Access Requests (show first if any pending) -->
        ${pendingRequests.length > 0 ? `
        <div class="card access-requests-card" style="margin-bottom: 1.5rem; border-left: 4px solid var(--amber, #f59e0b);">
          <div class="card-label" style="display: flex; align-items: center; gap: 0.5rem;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>
            Pending Access Requests
            <span class="badge badge-warning">${pendingRequests.length}</span>
          </div>
          <p style="color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 1rem;">
            These people tried to sign in and requested admin access.
          </p>
          <div id="pending-requests-list">
            ${pendingRequests.map(r => `
              <div class="admin-user-row" data-req-id="${r.id}">
                <div class="admin-user-info">
                  <div class="admin-user-avatar" style="background: var(--amber, #f59e0b);">${(r.name || r.email)[0].toUpperCase()}</div>
                  <div>
                    <div class="admin-user-name">${esc(r.name || '')}</div>
                    <div class="admin-user-email">${esc(r.email)}</div>
                    <div style="font-size: 0.75rem; color: var(--text-tertiary);">${timeAgo(r.created_at)}</div>
                  </div>
                </div>
                <div style="display: flex; gap: 0.5rem;">
                  <button class="btn-primary btn-sm" onclick="approveAccessRequest(${r.id}, '${esc(r.name || r.email)}')" title="Approve access">Approve</button>
                  <button class="btn-ghost btn-sm btn-danger-text" onclick="denyAccessRequest(${r.id}, '${esc(r.name || r.email)}')" title="Deny access">Deny</button>
                </div>
              </div>
            `).join('')}
          </div>
        </div>` : ''}

        <!-- Admin Profile -->
        <div class="card">
          <div class="card-label">Your Profile</div>
          <form id="settings-form" class="setup-form" onsubmit="event.preventDefault(); saveSettings()">
            <div class="form-grid">
              <div class="form-field"><label>Name</label><input name="name" value="${esc(settings.name || '')}"></div>
              <div class="form-field"><label>Email</label><input name="email" value="${esc(settings.email || '')}" disabled></div>
              <div class="form-field"><label>New Password</label><input name="password" type="password" placeholder="Leave blank to keep current"></div>
            </div>
            <div class="form-actions"><button type="submit" class="btn-primary">Save Profile</button></div>
          </form>
        </div>

        <!-- Admin Team -->
        <div class="card" style="margin-top: 1.5rem;">
          <div class="card-label">Admin Team</div>
          <p style="color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 1rem;">
            Only people listed here can sign in to the admin portal. They'll use Google Sign-In with the email listed below.
          </p>
          <div id="admin-users-list">
            ${adminUsers.map(u => `
              <div class="admin-user-row" data-id="${u.id}">
                <div class="admin-user-info">
                  <div class="admin-user-avatar">${(u.name || u.email)[0].toUpperCase()}</div>
                  <div>
                    <div class="admin-user-name">${esc(u.name)}${u.email.toLowerCase() === currentEmail ? ' <span class="badge badge-info" style="margin-left: 0.5rem;">You</span>' : ''}</div>
                    <div class="admin-user-email">${esc(u.email)}</div>
                  </div>
                </div>
                ${u.email.toLowerCase() !== currentEmail ? `<button class="btn-ghost btn-sm btn-danger-text" onclick="removeAdminUser(${u.id}, '${esc(u.name)}')"
                  title="Remove admin access">Remove</button>` : ''}
              </div>
            `).join('')}
          </div>
          <div style="border-top: 1px solid var(--border); padding-top: 1rem; margin-top: 1rem;">
            <div class="card-label" style="margin-bottom: 0.75rem;">Add Admin User</div>
            <form id="add-admin-form" class="setup-form" onsubmit="event.preventDefault(); addAdminUser()">
              <div class="form-grid">
                <div class="form-field"><label>Name</label><input id="new-admin-name" placeholder="e.g. Jane Smith" required></div>
                <div class="form-field"><label>Google Email</label><input id="new-admin-email" type="email" placeholder="e.g. jane@company.com" required></div>
              </div>
              <div class="form-actions"><button type="submit" class="btn-primary">Add Admin</button></div>
            </form>
          </div>
        </div>

        <!-- Past Access Requests (history) -->
        ${pastRequests.length > 0 ? `
        <div class="card" style="margin-top: 1.5rem;">
          <details>
            <summary class="card-label" style="cursor: pointer; user-select: none;">Access Request History (${pastRequests.length})</summary>
            <div style="margin-top: 0.75rem;">
              ${pastRequests.map(r => `
                <div class="admin-user-row">
                  <div class="admin-user-info">
                    <div class="admin-user-avatar" style="background: ${r.status === 'approved' ? 'var(--green, #10b981)' : '#9ca3af'}; font-size: 0.75rem;">
                      ${r.status === 'approved' ? '✓' : '✗'}
                    </div>
                    <div>
                      <div class="admin-user-name">${esc(r.name || '')} <span class="badge ${r.status === 'approved' ? 'badge-success' : 'badge-neutral'}" style="margin-left: 0.5rem;">${r.status}</span></div>
                      <div class="admin-user-email">${esc(r.email)}</div>
                      <div style="font-size: 0.75rem; color: var(--text-tertiary);">${timeAgo(r.created_at)}${r.reviewed_at ? ' • reviewed ' + timeAgo(r.reviewed_at) : ''}</div>
                    </div>
                  </div>
                </div>
              `).join('')}
            </div>
          </details>
        </div>` : ''}
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load settings</div></div>`;
  }
}

async function addAdminUser() {
  const name = document.getElementById('new-admin-name').value.trim();
  const email = document.getElementById('new-admin-email').value.trim();
  if (!name || !email) return showToast('Name and email are required', 'error');
  try {
    await api('/admin-users', { method: 'POST', body: { name, email } });
    showToast(`${name} added as admin`, 'success');
    renderAdminSettings(document.getElementById('admin-content'));
  } catch (e) { showToast(e.message, 'error'); }
}

async function removeAdminUser(id, name) {
  if (!confirm(`Remove ${name} from admin access? They will no longer be able to sign in to the admin portal.`)) return;
  try {
    await api(`/admin-users/${id}`, { method: 'DELETE' });
    showToast(`${name} removed`, 'success');
    renderAdminSettings(document.getElementById('admin-content'));
  } catch (e) { showToast(e.message, 'error'); }
}

async function approveAccessRequest(id, name) {
  try {
    await api(`/access-requests/${id}/approve`, { method: 'POST' });
    showToast(`${name} approved and added as admin`, 'success');
    renderAdminSettings(document.getElementById('admin-content'));
  } catch (e) { showToast(e.message, 'error'); }
}

async function denyAccessRequest(id, name) {
  if (!confirm(`Deny ${name}'s request for admin access?`)) return;
  try {
    await api(`/access-requests/${id}/deny`, { method: 'POST' });
    showToast(`${name}'s request denied`, 'success');
    renderAdminSettings(document.getElementById('admin-content'));
  } catch (e) { showToast(e.message, 'error'); }
}

async function saveSettings() {
  const form = document.getElementById('settings-form');
  const fd = new FormData(form);
  try {
    await api('/settings', { method: 'PUT', body: { name: fd.get('name'), password: fd.get('password') } });
    showToast('Settings saved', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}


/* ═══════════════════════════════════════════════════════════════════════════════
   SERVICE CATALOG
   ═══════════════════════════════════════════════════════════════════════════════ */

async function renderServiceCatalog(el) {
  setAdminPageTitle('Service Catalog');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const services = await api('/service-catalog');

    // Assign a color per carrier for visual distinction
    const carrierColors = {};
    const palette = [
      '#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6',
      '#06b6d4','#f97316','#84cc16','#ec4899','#14b8a6',
      '#a855f7','#64748b','#d97706','#0ea5e9','#e11d48'
    ];
    let colorIdx = 0;
    services.forEach(s => {
      if (!carrierColors[s.carrier]) {
        carrierColors[s.carrier] = palette[colorIdx % palette.length];
        colorIdx++;
      }
    });

    const carriers = [...new Set(services.map(s => s.carrier))].sort();
    window._allCatalogServices = services;
    window._catalogCarrierColors = carrierColors;

    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Service Catalog <span class="page-title-count">${services.length}</span></h2>
          <div class="page-title-sub">${carriers.length} carriers</div>
        </div>

        <div class="sc-toolbar">
          <div class="sc-search-wrap">
            <svg class="rc-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="sc-search" class="rc-search-input" placeholder="Search by carrier or service name…"
              oninput="filterServiceCatalog()" autocomplete="off">
          </div>
          <select id="sc-carrier-filter" class="rc-sort-select" onchange="filterServiceCatalog()" title="Filter by carrier">
            <option value="">All Carriers</option>
            ${carriers.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('')}
          </select>
        </div>

        <div class="card" style="overflow:hidden;">
          <div class="table-container">
            <table class="data-table sc-table" id="sc-table">
              <thead>
                <tr>
                  <th>Carrier</th>
                  <th>Service Name</th>
                  <th>Service ID</th>
                  <th class="num">DIM Factor</th>
                  <th class="num">Max Weight</th>
                  <th class="num">GRI%</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody id="sc-tbody">
                ${services.map(s => `
                  <tr class="sc-row" data-carrier="${esc((s.carrier||'').toLowerCase())}" data-name="${esc((s.name||s.service_name||'').toLowerCase())}">
                    <td>
                      <span class="sc-carrier-dot" style="background:${esc(carrierColors[s.carrier] || '#94a3b8')};"></span>
                      <span class="fw-500">${esc(s.carrier)}</span>
                    </td>
                    <td>${esc(s.name || s.service_name || '')}</td>
                    <td class="text-mono text-xs">${esc(s.service_id || s.id || '')}</td>
                    <td class="num">${s.dim_factor != null ? s.dim_factor : s.dim_divisor != null ? s.dim_divisor : '—'}</td>
                    <td class="num">${s.max_weight != null ? s.max_weight + ' lbs' : '—'}</td>
                    <td class="num">${s.gri_pct != null ? s.gri_pct + '%' : '—'}</td>
                    <td><span class="status-badge ${s.status === 'active' || !s.status ? 'status-active' : 'status-inactive'}">${esc(s.status || 'Active')}</span></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
        <p class="sc-footer-note" id="sc-count-note">${services.length} services across ${carriers.length} carriers</p>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load service catalog: ${esc(e.message)}</div></div>`;
  }
}

function filterServiceCatalog() {
  const query = (document.getElementById('sc-search')?.value || '').toLowerCase().trim();
  const carrierFilter = (document.getElementById('sc-carrier-filter')?.value || '').toLowerCase();
  const rows = document.querySelectorAll('#sc-tbody .sc-row');
  let visible = 0;
  rows.forEach(row => {
    const carrierMatch = !carrierFilter || row.dataset.carrier === carrierFilter;
    const textMatch = !query || row.dataset.carrier?.includes(query) || row.dataset.name?.includes(query);
    const show = carrierMatch && textMatch;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  const note = document.getElementById('sc-count-note');
  if (note) note.textContent = `${visible} service${visible !== 1 ? 's' : ''} shown${query || carrierFilter ? ' (filtered)' : ''}`;
}


/* ═══════════════════════════════════════════════════════════════════════════════
   TRANSIT TIMES
   ═══════════════════════════════════════════════════════════════════════════════ */

async function renderTransitTimes(el) {
  setAdminPageTitle('Transit Times');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const data = await api('/transit-times');
    const hubs = data.hubs || ['Buffalo', 'Seattle', 'Ohio', 'Reno', 'Texas', 'Kansas'];
    const rows = data.rows || [];

    window._allTransitRows = rows;
    window._transitHubs = hubs;

    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Transit Times</h2>
        </div>
        <p style="color:var(--color-text-muted);font-size:var(--text-sm);margin-bottom:var(--space-3);">Transit days from each hub to US states. Color: <span class="tt-legend tt-green">1 day</span> <span class="tt-legend tt-yellow">2–3 days</span> <span class="tt-legend tt-orange">4–5 days</span> <span class="tt-legend tt-red">6+ days</span>.</p>

        <div class="tt-toolbar">
          <div class="sc-search-wrap">
            <svg class="rc-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="tt-search" class="rc-search-input" placeholder="Filter by state…"
              oninput="filterTransitTimes()" autocomplete="off">
          </div>
        </div>

        <div class="card" style="overflow:hidden;">
          <div class="table-container">
            <table class="data-table tt-table">
              <thead>
                <tr>
                  <th>State</th>
                  ${hubs.map(h => `<th class="num tt-hub-header" title="Hub: ${esc(h)}">${esc(h)}</th>`).join('')}
                </tr>
              </thead>
              <tbody id="tt-tbody">
                ${rows.map(row => `
                  <tr class="tt-row" data-state="${esc((row.state||'').toLowerCase())}">
                    <td class="fw-500">${esc(row.state)}</td>
                    ${hubs.map(hub => {
                      const days = row[hub] != null ? row[hub] : row[hub.toLowerCase()] != null ? row[hub.toLowerCase()] : null;
                      if (days == null) return `<td class="num"><span class="tt-cell tt-na">—</span></td>`;
                      const cls = days <= 1 ? 'tt-green' : days <= 3 ? 'tt-yellow' : days <= 5 ? 'tt-orange' : 'tt-red';
                      return `<td class="num"><span class="tt-cell ${cls}" title="${days} day${days !== 1 ? 's' : ''} from ${esc(hub)} to ${esc(row.state)}">${days}</span></td>`;
                    }).join('')}
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load transit times: ${esc(e.message)}</div></div>`;
  }
}

function filterTransitTimes() {
  const query = (document.getElementById('tt-search')?.value || '').toLowerCase().trim();
  document.querySelectorAll('#tt-tbody .tt-row').forEach(row => {
    row.style.display = (!query || row.dataset.state?.includes(query)) ? '' : 'none';
  });
}


/* ═══════════════════════════════════════════════════════════════════════════════
   ACCESSORIAL RULES
   ═══════════════════════════════════════════════════════════════════════════════ */

const ACCESSORIAL_CARRIERS = ['UPS','FedEx','DHL','USPS','Amazon','OnTrac','OSM','UniUni','Sendle'];
const ACCESSORIAL_FEE_TYPES = [
  'DAS', 'EDAS', 'additional_handling', 'oversize', 'over_max',
  'residential', 'remote_area', 'nonstandard_length_22', 'nonstandard_length_30',
  'nonstandard_volume', 'dim_noncompliance', 'demand_surcharge'
];

async function renderAdminAccessorials(el) {
  setAdminPageTitle('Accessorial Rules');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const rules = await api('/accessorial-rules');

    // Group by carrier
    const byCarrier = {};
    rules.forEach(r => {
      const c = r.carrier || 'Other';
      if (!byCarrier[c]) byCarrier[c] = [];
      byCarrier[c].push(r);
    });
    const carriers = Object.keys(byCarrier).sort();

    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Accessorial Rules <span class="page-title-count">${rules.length}</span></h2>
          <div class="page-header-actions">
            <button class="btn-primary btn-sm" onclick="showAccessorialModal()">+ Add Rule</button>
          </div>
        </div>

        ${rules.length === 0 ? `
          <div class="empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 1v22M1 12h22"/><circle cx="12" cy="12" r="8"/></svg>
            <p>No accessorial rules configured yet.</p>
            <button class="btn-primary" onclick="showAccessorialModal()">Add First Rule</button>
          </div>
        ` : `
          ${carriers.map(carrier => `
            <div class="acc-carrier-group">
              <div class="acc-carrier-heading">
                <span class="acc-carrier-name">${esc(carrier)}</span>
                <span class="acc-carrier-count">${byCarrier[carrier].length} rule${byCarrier[carrier].length !== 1 ? 's' : ''}</span>
              </div>
              <div class="table-container">
                <table class="data-table compact">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Fee Type</th>
                      <th class="num">Amount</th>
                      <th>Conditions</th>
                      <th style="width:80px"></th>
                    </tr>
                  </thead>
                  <tbody>
                    ${byCarrier[carrier].map(r => {
                      const conds = [];
                      if (r.weight_over) conds.push('Wt &gt;' + r.weight_over + 'lb');
                      if (r.length_over) conds.push('Len &gt;' + r.length_over + '"');
                      if (r.lg_over) conds.push('LG &gt;' + r.lg_over + '"');
                      if (r.month_min || r.month_max) conds.push('Months ' + (r.month_min||1) + '\u2013' + (r.month_max||12));
                      if (r.start_date) conds.push('From ' + r.start_date.slice(0,10));
                      if (r.end_date) conds.push('To ' + r.end_date.slice(0,10));
                      return `
                      <tr class="acc-rule-row">
                        <td class="fw-500">${esc(r.name)}</td>
                        <td><span class="badge badge-sm">${esc(r.fee_type || '')}</span></td>
                        <td class="num">${formatCurrency(r.amount || 0)}</td>
                        <td class="text-muted text-xs">${conds.length ? conds.join(', ') : '<span class="text-faint">Always</span>'}</td>
                        <td class="text-right">
                          <button class="btn-ghost btn-xs" onclick="showAccessorialModal(${JSON.stringify(r).replace(/"/g,'&quot;')})" title="Edit rule">Edit</button>
                          <button class="btn-ghost btn-xs text-error" onclick="deleteAccessorialRule(${r.id})" title="Delete rule">Del</button>
                        </td>
                      </tr>`;
                    }).join('')}
                  </tbody>
                </table>
              </div>
            </div>
          `).join('')}
        `}
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load accessorial rules: ${esc(e.message)}</div></div>`;
  }
}

function showAccessorialModal(existing) {
  const r = existing || {};
  openModal(existing ? 'Edit Accessorial Rule' : 'New Accessorial Rule', `
    <form id="acc-form" onsubmit="event.preventDefault(); submitAccessorialRule(${existing?.id || 'null'})">
      <div class="form-grid modal-form">
        <div class="form-field span-2">
          <label>Name *</label>
          <input name="name" required value="${esc(r.name || '')}" placeholder="e.g. Delivery Area Surcharge — Extended">
        </div>
        <div class="form-field">
          <label>Carrier</label>
          <select name="carrier">
            <option value="">-- Any --</option>
            ${ACCESSORIAL_CARRIERS.map(c => `<option value="${c}" ${r.carrier === c ? 'selected' : ''}>${c}</option>`).join('')}
          </select>
        </div>
        <div class="form-field">
          <label>Fee Type</label>
          <select name="fee_type" id="acc-fee-type" onchange="toggleDemandSurchargeDates(this.value)">
            <option value="">-- Select --</option>
            ${ACCESSORIAL_FEE_TYPES.map(t => `<option value="${t}" ${r.fee_type === t ? 'selected' : ''}>${t}</option>`).join('')}
          </select>
        </div>
        <div class="form-field">
          <label>Amount ($)</label>
          <input type="number" name="amount" step="0.01" min="0" value="${r.amount || ''}" placeholder="0.00">
        </div>
        <div class="form-field span-2" style="border-top:1px solid var(--color-border);padding-top:12px;margin-top:4px">
          <label style="font-weight:600;font-size:13px;color:var(--color-text-muted)">Conditions (leave blank to always apply)</label>
        </div>
        <div class="form-field">
          <label title="Apply when actual weight exceeds this value (lbs)">Weight Over (lbs)</label>
          <input type="number" name="weight_over" step="0.1" min="0" value="${r.weight_over || ''}" placeholder="e.g. 150">
        </div>
        <div class="form-field">
          <label title="Apply when longest side exceeds this value (inches)">Length Over (in)</label>
          <input type="number" name="length_over" step="0.1" min="0" value="${r.length_over || ''}" placeholder="e.g. 48">
        </div>
        <div class="form-field">
          <label title="Apply when length + girth exceeds this value (inches)">L+G Over (in)</label>
          <input type="number" name="lg_over" step="0.1" min="0" value="${r.lg_over || ''}" placeholder="e.g. 165">
        </div>
        <div class="form-field">
          <label title="Seasonal: first month this applies (1=Jan)">Month Min</label>
          <input type="number" name="month_min" step="1" min="1" max="12" value="${r.month_min || ''}" placeholder="1">
        </div>
        <div class="form-field">
          <label title="Seasonal: last month this applies (12=Dec)">Month Max</label>
          <input type="number" name="month_max" step="1" min="1" max="12" value="${r.month_max || ''}" placeholder="12">
        </div>
        <div class="form-field span-2 demand-surcharge-dates" id="demand-dates-section" style="${r.fee_type === 'demand_surcharge' ? '' : 'display:none;'}border-top:1px solid var(--color-border);padding-top:12px;margin-top:4px;">
          <label style="font-weight:600;font-size:13px;color:var(--color-text-muted)">Demand Surcharge Date Range <span class="text-muted text-xs">(optional)</span></label>
        </div>
        <div class="form-field demand-surcharge-dates" id="demand-dates-start" style="${r.fee_type === 'demand_surcharge' ? '' : 'display:none;'}">
          <label title="Start date for this demand surcharge (leave blank for always on)">Start Date</label>
          <input type="date" name="start_date" value="${r.start_date ? r.start_date.slice(0, 10) : ''}">
        </div>
        <div class="form-field demand-surcharge-dates" id="demand-dates-end" style="${r.fee_type === 'demand_surcharge' ? '' : 'display:none;'}">
          <label title="End date for this demand surcharge (leave blank for no end)">End Date</label>
          <input type="date" name="end_date" value="${r.end_date ? r.end_date.slice(0, 10) : ''}">
        </div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn-primary">${existing ? 'Update' : 'Create'}</button>
      </div>
    </form>
  `);
}

function toggleDemandSurchargeDates(feeType) {
  const show = feeType === 'demand_surcharge';
  document.querySelectorAll('.demand-surcharge-dates').forEach(el => {
    el.style.display = show ? '' : 'none';
  });
}

async function submitAccessorialRule(id) {
  const form = document.getElementById('acc-form');
  const fd = new FormData(form);
  const body = {
    name: fd.get('name'),
    carrier: fd.get('carrier') || null,
    fee_type: fd.get('fee_type') || null,
    amount: parseFloat(fd.get('amount')) || 0,
    weight_over: parseFloat(fd.get('weight_over')) || null,
    length_over: parseFloat(fd.get('length_over')) || null,
    lg_over: parseFloat(fd.get('lg_over')) || null,
    month_min: parseInt(fd.get('month_min')) || null,
    month_max: parseInt(fd.get('month_max')) || null,
    start_date: fd.get('start_date') || null,
    end_date: fd.get('end_date') || null,
  };
  try {
    if (id) {
      await api(`/accessorial-rules/${id}`, { method: 'PUT', body });
    } else {
      await api('/accessorial-rules', { method: 'POST', body });
    }
    closeModal();
    showToast(id ? 'Rule updated' : 'Rule created', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteAccessorialRule(id) {
  if (!confirm('Delete this accessorial rule?')) return;
  try {
    await api(`/accessorial-rules/${id}`, { method: 'DELETE' });
    showToast('Rule deleted', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}


/* ═══════════════════════════════════════════════════════════════════════════════
   PRICING CONFIG
   ═══════════════════════════════════════════════════════════════════════════════ */

async function renderAdminPricingConfig(el) {
  setAdminPageTitle('Pricing Config');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const cfg = await api('/service-cost-config').catch(() => ({}));

    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Pricing Config</h2>
        </div>

        <div class="card pricing-config-card">
          <div class="card-header-row">
            <div class="card-label">Service Cost Configuration</div>
          </div>
          <p class="pricing-config-desc">These values are used by the SAPT rating engine when calculating profitability. Based on <strong>250 business days/year</strong> annualization.</p>

          <form id="pricing-config-form" onsubmit="event.preventDefault(); savePricingConfig()">
            <div class="form-grid pricing-config-grid">
              <div class="form-field">
                <label title="Annual line-haul cost allocated to this service">Line Haul Cost ($/year)
                  <span class="tooltip-icon" title="Total annual line-haul cost for this service, annualized across 250 business days.">?</span>
                </label>
                <input type="number" id="pc-line-haul" name="line_haul_cost" step="0.01" min="0"
                  value="${cfg.line_haul_cost || ''}" placeholder="0.00">
              </div>
              <div class="form-field">
                <label title="Fixed daily cost for operating pickup on this route">Daily Pickup Cost ($/day)
                  <span class="tooltip-icon" title="Cost per pickup day (driver, vehicle, etc.). Annualized over pickup_days.">?</span>
                </label>
                <input type="number" id="pc-daily-pickup" name="daily_pickup_cost" step="0.01" min="0"
                  value="${cfg.daily_pickup_cost || ''}" placeholder="0.00">
              </div>
              <div class="form-field">
                <label title="Number of business days per year pickups run on this route">Pickup Days / Year
                  <span class="tooltip-icon" title="250 = standard US business days. Adjust down for routes that skip certain days.">?</span>
                </label>
                <input type="number" id="pc-pickup-days" name="pickup_days" step="1" min="1" max="365"
                  value="${cfg.pickup_days || 250}" placeholder="250">
              </div>
              <div class="form-field">
                <label title="Per-piece sort/handling cost at the facility">Sort Cost ($/piece)
                  <span class="tooltip-icon" title="Per-shipment sort and injection cost at the facility level.">?</span>
                </label>
                <input type="number" id="pc-sort-cost" name="sort_cost" step="0.001" min="0"
                  value="${cfg.sort_cost || ''}" placeholder="0.000">
              </div>
            </div>

            <div class="pricing-config-annualize-note">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              Annualization basis: <strong>250 business days/year</strong>. Daily cost = annual cost ÷ 250. Used for per-shipment cost allocation in profitability analysis.
            </div>

            <div class="modal-actions" style="margin-top:var(--space-5);justify-content:flex-start;">
              <button type="submit" class="btn-primary" id="pricing-config-save-btn">Save Configuration</button>
            </div>
          </form>
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load pricing config: ${esc(e.message)}</div></div>`;
  }
}

async function savePricingConfig() {
  const form = document.getElementById('pricing-config-form');
  const fd = new FormData(form);
  const body = {
    line_haul_cost: parseFloat(fd.get('line_haul_cost')) || 0,
    daily_pickup_cost: parseFloat(fd.get('daily_pickup_cost')) || 0,
    pickup_days: parseInt(fd.get('pickup_days')) || 250,
    sort_cost: parseFloat(fd.get('sort_cost')) || 0,
  };
  const btn = document.getElementById('pricing-config-save-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
  try {
    await api('/service-cost-config', { method: 'PUT', body });
    showToast('Pricing config saved', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Save Configuration'; }
  }
}


/* ═══════════════════════════════════════════════════════════════════════════════
   INITIALIZATION
   ═══════════════════════════════════════════════════════════════════════════════ */
initTheme();
router();

/* ═══════════════════════════════════════════════════════════════════════════════
   INDUCTION LOCATIONS
   ═══════════════════════════════════════════════════════════════════════════════ */

async function renderAdminInductionLocations(el) {
  setAdminPageTitle('Induction Sites');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const locs = await api('/induction-locations');
    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Induction Sites <span class="page-title-count">${locs.length}</span></h2>
          <div class="page-header-actions">
            <button class="btn-primary btn-sm" onclick="showInductionLocationModal()" title="Add a new induction location">+ Add Location</button>
          </div>
        </div>
        ${locs.length === 0 ? `
          <div class="empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            <p>No induction locations configured yet.</p>
            <button class="btn-primary" onclick="showInductionLocationModal()">Add First Location</button>
          </div>
        ` : `
          <div class="table-container">
            <table class="admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Display Name</th>
                  <th>Country</th>
                  <th>ZIP / Postal</th>
                  <th class="text-center">Primary</th>
                  <th class="text-center">Active</th>
                  <th style="width:100px"></th>
                </tr>
              </thead>
              <tbody>
                ${locs.map(loc => `
                  <tr>
                    <td class="fw-500">${esc(loc.name)}</td>
                    <td>${esc(loc.display_name || '')}</td>
                    <td><span class="badge badge-sm">${esc(loc.country || '')}</span></td>
                    <td class="text-mono">${esc(loc.zip_or_postal || '—')}</td>
                    <td class="text-center">
                      ${loc.is_primary ? '<span class="badge" style="background:var(--color-primary);color:#fff;" title="Primary induction location">Primary</span>' : '<span class="text-muted text-xs">—</span>'}
                    </td>
                    <td class="text-center">
                      <button class="toggle-switch-btn ${loc.active ? 'active' : ''}" onclick="toggleInductionActive(${loc.id}, ${loc.active ? 0 : 1})" title="${loc.active ? 'Active — click to deactivate' : 'Inactive — click to activate'}">
                        <span class="toggle-knob"></span>
                      </button>
                    </td>
                    <td class="text-right">
                      <button class="btn-ghost btn-xs" onclick="showInductionLocationModal(${JSON.stringify(loc).replace(/"/g,'&quot;')})" title="Edit this location">Edit</button>
                      <button class="btn-ghost btn-xs text-error" onclick="deleteInductionLocation(${loc.id})" title="Delete this location">Del</button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load induction locations: ${esc(e.message)}</div></div>`;
  }
}

function showInductionLocationModal(existing) {
  const loc = existing || {};
  openModal(existing ? 'Edit Induction Location' : 'New Induction Location', `
    <form id="induction-form" onsubmit="event.preventDefault(); submitInductionLocation(${existing?.id || 'null'})">
      <div class="form-grid modal-form">
        <div class="form-field">
          <label>Name * <span class="text-muted text-xs">(short code, e.g. NJ, YYZ)</span></label>
          <input name="name" required value="${esc(loc.name || '')}" placeholder="e.g. NJ">
        </div>
        <div class="form-field">
          <label>Display Name</label>
          <input name="display_name" value="${esc(loc.display_name || '')}" placeholder="e.g. New Jersey">
        </div>
        <div class="form-field">
          <label>Country</label>
          <select name="country">
            <option value="US" ${(!loc.country || loc.country === 'US') ? 'selected' : ''}>United States (US)</option>
            <option value="CA" ${loc.country === 'CA' ? 'selected' : ''}>Canada (CA)</option>
          </select>
        </div>
        <div class="form-field">
          <label>ZIP / Postal Code</label>
          <input name="zip_or_postal" value="${esc(loc.zip_or_postal || '')}" placeholder="e.g. 07001">
        </div>
        <div class="form-field span-2">
          <label class="check-label" title="Mark as the primary induction location for this country">
            <input type="checkbox" name="is_primary" value="1" ${loc.is_primary ? 'checked' : ''}>
            Primary Location
          </label>
        </div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn-primary">${existing ? 'Update' : 'Create'}</button>
      </div>
    </form>
  `);
}

async function submitInductionLocation(id) {
  const form = document.getElementById('induction-form');
  const fd = new FormData(form);
  const body = {
    name: fd.get('name'),
    display_name: fd.get('display_name') || fd.get('name'),
    country: fd.get('country') || 'US',
    zip_or_postal: fd.get('zip_or_postal') || null,
    is_primary: fd.get('is_primary') === '1' ? 1 : 0,
    active: 1
  };
  try {
    if (id) {
      await api(`/induction-locations/${id}`, { method: 'PUT', body });
    } else {
      await api('/induction-locations', { method: 'POST', body });
    }
    closeModal();
    showToast(id ? 'Location updated' : 'Location created', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

async function toggleInductionActive(id, newActive) {
  try {
    await api(`/induction-locations/${id}`, { method: 'PUT', body: { active: newActive } });
    showToast(newActive ? 'Location activated' : 'Location deactivated', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteInductionLocation(id) {
  if (!confirm('Delete this induction location? This may affect zone skip configurations.')) return;
  try {
    await api(`/induction-locations/${id}`, { method: 'DELETE' });
    showToast('Location deleted', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

/* ═══════════════════════════════════════════════════════════════════════════════
   ZONE SKIP CONFIG
   ═══════════════════════════════════════════════════════════════════════════════ */

async function renderAdminZoneSkip(el) {
  setAdminPageTitle('Zone Skip Config');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const [locations, configs] = await Promise.all([
      api('/induction-locations'),
      api('/zone-skip-config').catch(() => [])
    ]);
    const carriers = ['USPS', 'UPS', 'FedEx', 'DHL', 'OSM', 'Amazon', 'UniUni'];

    // Build lookup map: key = `${location_id}_${carrier}`
    const configMap = {};
    configs.forEach(c => {
      configMap[`${c.induction_location_id}_${c.carrier}`] = c;
    });

    // Collect pending edits in a window variable
    window._zoneSkipEdits = {};

    const tableRows = locations.map(loc => {
      return carriers.map(carrier => {
        const key = `${loc.id}_${carrier}`;
        const cfg = configMap[key] || {};
        return `
          <tr data-loc-id="${loc.id}" data-carrier="${esc(carrier)}">
            <td class="fw-500">${esc(loc.display_name || loc.name)}</td>
            <td><span class="badge badge-sm">${esc(carrier)}</span></td>
            <td class="text-center">
              <input type="checkbox" class="zs-check" data-key="${key}" data-field="zone_skip_allowed"
                ${cfg.zone_skip_allowed ? 'checked' : ''}
                onchange="zoneSkipEdit('${key}', 'zone_skip_allowed', this.checked ? 1 : 0)"
                title="Allow zone skip for ${esc(loc.display_name || loc.name)} — ${esc(carrier)}">
            </td>
            <td>
              <input type="number" class="zs-num-input" step="0.01" min="0"
                value="${cfg.zone_skip_fixed != null ? cfg.zone_skip_fixed : ''}"
                placeholder="0.00"
                onchange="zoneSkipEdit('${key}', 'zone_skip_fixed', parseFloat(this.value) || 0)"
                title="Fixed zone skip cost ($)">
            </td>
            <td>
              <input type="number" class="zs-num-input" step="0.001" min="0"
                value="${cfg.zone_skip_per_lb != null ? cfg.zone_skip_per_lb : ''}"
                placeholder="0.000"
                onchange="zoneSkipEdit('${key}', 'zone_skip_per_lb', parseFloat(this.value) || 0)"
                title="Zone skip cost per lb ($/lb)">
            </td>
            <td class="text-center">
              <input type="checkbox" class="zs-check" data-key="${key}" data-field="service_available"
                ${cfg.service_available || cfg.service_available == null ? 'checked' : ''}
                onchange="zoneSkipEdit('${key}', 'service_available', this.checked ? 1 : 0)"
                title="Service available for this location/carrier combo">
            </td>
          </tr>`;
      }).join('');
    }).join('');

    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Zone Skip Configuration</h2>
          <div class="page-header-actions">
            <button class="btn-primary btn-sm" onclick="saveZoneSkipConfig()" title="Save all zone skip settings">Save Changes</button>
          </div>
        </div>
        <p style="color:var(--color-text-muted);font-size:var(--text-sm);margin-bottom:16px;">
          Configure zone skip availability and cost per induction location and carrier. Changes are saved in bulk when you click Save Changes.
        </p>
        ${locations.length === 0 ? `
          <div class="empty-state">
            <p>No induction locations configured yet. <a href="#admin/induction-locations">Add locations first.</a></p>
          </div>
        ` : `
          <div class="table-container">
            <table class="admin-table">
              <thead>
                <tr>
                  <th>Location</th>
                  <th>Carrier</th>
                  <th class="text-center" title="Allow zone skip pricing for this combination">Zone Skip Allowed</th>
                  <th class="text-center" title="Fixed zone skip cost per shipment ($)">Fixed Cost ($)</th>
                  <th class="text-center" title="Per-pound zone skip cost ($/lb)">Per Lb Cost ($/lb)</th>
                  <th class="text-center" title="Service is available for this location/carrier">Available</th>
                </tr>
              </thead>
              <tbody id="zone-skip-tbody">
                ${tableRows}
              </tbody>
            </table>
          </div>
        `}
      </div>`;

    // Store current config for saving
    window._zoneSkipCurrentConfigs = configs;
    window._zoneSkipLocations = locations;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load zone skip config: ${esc(e.message)}</div></div>`;
  }
}

function zoneSkipEdit(key, field, value) {
  if (!window._zoneSkipEdits) window._zoneSkipEdits = {};
  if (!window._zoneSkipEdits[key]) window._zoneSkipEdits[key] = {};
  window._zoneSkipEdits[key][field] = value;
}

async function saveZoneSkipConfig() {
  // Collect all current values from the table
  const tbody = document.getElementById('zone-skip-tbody');
  if (!tbody) return;
  const records = [];
  tbody.querySelectorAll('tr[data-loc-id]').forEach(row => {
    const locId = parseInt(row.dataset.locId);
    const carrier = row.dataset.carrier;
    const allowedEl = row.querySelector('[data-field="zone_skip_allowed"]');
    const fixedEl = row.querySelectorAll('.zs-num-input')[0];
    const perLbEl = row.querySelectorAll('.zs-num-input')[1];
    const availEl = row.querySelector('[data-field="service_available"]');
    records.push({
      induction_location_id: locId,
      carrier,
      zone_skip_allowed: allowedEl ? (allowedEl.checked ? 1 : 0) : 0,
      zone_skip_fixed: parseFloat(fixedEl?.value) || 0,
      zone_skip_per_lb: parseFloat(perLbEl?.value) || 0,
      service_available: availEl ? (availEl.checked ? 1 : 0) : 1
    });
  });
  try {
    await api('/zone-skip-config', { method: 'PUT', body: { records } });
    showToast('Zone skip config saved', 'success');
    window._zoneSkipEdits = {};
  } catch (e) { showToast(e.message, 'error'); }
}

/* ═══════════════════════════════════════════════════════════════════════════════
   DATA FILES (ZONE FILES + DAS FILES)
   ═══════════════════════════════════════════════════════════════════════════════ */

async function renderAdminDataFiles(el) {
  setAdminPageTitle('Data Files');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const [zoneFiles, dasFiles] = await Promise.all([
      api('/zone-files').catch(() => []),
      api('/das-files').catch(() => [])
    ]);

    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Data Files</h2>
        </div>

        <!-- Zone Files Section -->
        <div class="card">
          <div class="card-header-row">
            <div class="card-label">Zone Files</div>
            <button class="btn-primary btn-sm" onclick="showZoneFileUploadModal()" title="Upload a new zone file CSV">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              Upload Zone File
            </button>
          </div>
          ${zoneFiles.length === 0 ? `<div class="empty-inline">No zone files uploaded yet.</div>` : `
            <div class="table-container">
              <table class="admin-table">
                <thead>
                  <tr>
                    <th>File Name</th>
                    <th>Carrier</th>
                    <th>Country</th>
                    <th>Effective Date</th>
                    <th class="text-center">Status</th>
                    <th>Uploaded</th>
                    <th style="width:60px"></th>
                  </tr>
                </thead>
                <tbody>
                  ${zoneFiles.map(f => `
                    <tr>
                      <td class="fw-500">${esc(f.file_name || '—')}</td>
                      <td><span class="badge badge-sm">${esc(f.carrier || '')}</span></td>
                      <td>${esc(f.country || '—')}</td>
                      <td>${esc(f.effective_date || '—')}</td>
                      <td class="text-center">${f.is_active ? '<span class="badge" style="background:var(--color-success);color:#fff;" title="Active zone file">Active</span>' : '<span class="badge badge-sm text-muted">Inactive</span>'}</td>
                      <td class="text-muted text-xs">${esc(f.uploaded_at ? f.uploaded_at.slice(0,10) : '—')}</td>
                      <td class="text-right">
                        <button class="btn-ghost btn-xs text-error" onclick="deleteDataFile('zone', ${f.id})" title="Delete this zone file">Del</button>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `}
        </div>

        <!-- DAS Files Section -->
        <div class="card">
          <div class="card-header-row">
            <div class="card-label">DAS Files (Delivery Area Surcharge)</div>
            <button class="btn-primary btn-sm" onclick="showDasFileUploadModal()" title="Upload a new DAS file CSV">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              Upload DAS File
            </button>
          </div>
          ${dasFiles.length === 0 ? `<div class="empty-inline">No DAS files uploaded yet.</div>` : `
            <div class="table-container">
              <table class="admin-table">
                <thead>
                  <tr>
                    <th>File Name</th>
                    <th>Carrier</th>
                    <th>Effective Date</th>
                    <th class="text-center">Status</th>
                    <th>Uploaded</th>
                    <th style="width:60px"></th>
                  </tr>
                </thead>
                <tbody>
                  ${dasFiles.map(f => `
                    <tr>
                      <td class="fw-500">${esc(f.file_name || '—')}</td>
                      <td><span class="badge badge-sm">${esc(f.carrier || '')}</span></td>
                      <td>${esc(f.effective_date || '—')}</td>
                      <td class="text-center">${f.is_active ? '<span class="badge" style="background:var(--color-success);color:#fff;" title="Active DAS file">Active</span>' : '<span class="badge badge-sm text-muted">Inactive</span>'}</td>
                      <td class="text-muted text-xs">${esc(f.uploaded_at ? f.uploaded_at.slice(0,10) : '—')}</td>
                      <td class="text-right">
                        <button class="btn-ghost btn-xs text-error" onclick="deleteDataFile('das', ${f.id})" title="Delete this DAS file">Del</button>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          `}
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load data files: ${esc(e.message)}</div></div>`;
  }
}

function showZoneFileUploadModal() {
  openModal('Upload Zone File', `
    <form id="zone-file-form" onsubmit="event.preventDefault(); submitZoneFile()">
      <div class="form-grid modal-form">
        <div class="form-field">
          <label>Carrier *</label>
          <input name="carrier" required placeholder="e.g. USPS, UPS, FedEx">
        </div>
        <div class="form-field">
          <label>Country</label>
          <select name="country">
            <option value="US">US</option>
            <option value="CA">CA</option>
          </select>
        </div>
        <div class="form-field">
          <label>Effective Date</label>
          <input type="date" name="effective_date">
        </div>
        <div class="form-field span-2">
          <label>CSV File * <span class="text-muted text-xs">(will be parsed client-side)</span></label>
          <input type="file" name="zone_file" accept=".csv" required id="zone-file-input" onchange="previewFileSize('zone-file-input','zone-file-preview')">
          <div id="zone-file-preview" class="text-muted text-xs" style="margin-top:4px;"></div>
        </div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn-primary">Upload</button>
      </div>
    </form>
  `);
}

function showDasFileUploadModal() {
  openModal('Upload DAS File', `
    <form id="das-file-form" onsubmit="event.preventDefault(); submitDasFile()">
      <div class="form-grid modal-form">
        <div class="form-field">
          <label>Carrier *</label>
          <input name="carrier" required placeholder="e.g. USPS, UPS, FedEx">
        </div>
        <div class="form-field">
          <label>Effective Date</label>
          <input type="date" name="effective_date">
        </div>
        <div class="form-field span-2">
          <label>CSV File * <span class="text-muted text-xs">(will be parsed client-side)</span></label>
          <input type="file" name="das_file" accept=".csv" required id="das-file-input" onchange="previewFileSize('das-file-input','das-file-preview')">
          <div id="das-file-preview" class="text-muted text-xs" style="margin-top:4px;"></div>
        </div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn-primary">Upload</button>
      </div>
    </form>
  `);
}

function previewFileSize(inputId, previewId) {
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);
  if (!input || !preview) return;
  const file = input.files[0];
  if (file) {
    preview.textContent = `${file.name} — ${(file.size / 1024).toFixed(1)} KB`;
  }
}

function parseCSVToArray(csvText) {
  const lines = csvText.trim().split('\n');
  if (lines.length === 0) return [];
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
  return lines.slice(1).map(line => {
    const values = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''));
    const obj = {};
    headers.forEach((h, i) => { obj[h] = values[i] || ''; });
    return obj;
  });
}

async function submitZoneFile() {
  const form = document.getElementById('zone-file-form');
  const fd = new FormData(form);
  const file = fd.get('zone_file');
  if (!file || !file.size) { showToast('Please select a CSV file', 'error'); return; }
  const btn = form.querySelector('[type="submit"]');
  if (btn) { btn.disabled = true; btn.textContent = 'Parsing…'; }
  try {
    const text = await file.text();
    const data = parseCSVToArray(text);
    const body = {
      carrier: fd.get('carrier'),
      country: fd.get('country') || 'US',
      file_name: file.name,
      effective_date: fd.get('effective_date') || null,
      data
    };
    await api('/zone-files/upload', { method: 'POST', body });
    closeModal();
    showToast('Zone file uploaded successfully', 'success');
    router();
  } catch (e) {
    showToast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Upload'; }
  }
}

async function submitDasFile() {
  const form = document.getElementById('das-file-form');
  const fd = new FormData(form);
  const file = fd.get('das_file');
  if (!file || !file.size) { showToast('Please select a CSV file', 'error'); return; }
  const btn = form.querySelector('[type="submit"]');
  if (btn) { btn.disabled = true; btn.textContent = 'Parsing…'; }
  try {
    const text = await file.text();
    const data = parseCSVToArray(text);
    const body = {
      carrier: fd.get('carrier'),
      file_name: file.name,
      effective_date: fd.get('effective_date') || null,
      data
    };
    await api('/das-files/upload', { method: 'POST', body });
    closeModal();
    showToast('DAS file uploaded successfully', 'success');
    router();
  } catch (e) {
    showToast(e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Upload'; }
  }
}

async function deleteDataFile(type, id) {
  const label = type === 'zone' ? 'zone file' : 'DAS file';
  if (!confirm(`Delete this ${label}? This cannot be undone.`)) return;
  try {
    const endpoint = type === 'zone' ? `/zone-files/${id}` : `/das-files/${id}`;
    await api(endpoint, { method: 'DELETE' });
    showToast(`${label.charAt(0).toUpperCase() + label.slice(1)} deleted`, 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

/* ═══════════════════════════════════════════════════════════════════════════════
   COST OVERRIDES
   ═══════════════════════════════════════════════════════════════════════════════ */

async function renderAdminCostOverrides(el) {
  setAdminPageTitle('Cost Overrides');
  el.innerHTML = `<div class="admin-content"><div class="skeleton-block"></div></div>`;
  try {
    const [rateCards, overrides, globalCfg] = await Promise.all([
      api('/rate-cards'),
      api('/service-cost-overrides').catch(() => []),
      api('/service-cost-config').catch(() => ({}))
    ]);

    // Build lookup by rate_card_id
    const overrideMap = {};
    overrides.forEach(o => { overrideMap[o.rate_card_id] = o; });

    el.innerHTML = `
      <div class="admin-content">
        <div class="page-header-row">
          <h2 class="page-title">Cost Overrides <span class="page-title-count">${overrides.length} set</span></h2>
        </div>

        <!-- Global Defaults Reference -->
        <div class="card" style="margin-bottom:16px;">
          <div class="card-header-row">
            <div class="card-label">Global Cost Defaults <span class="text-muted text-xs">(from Pricing Config)</span></div>
          </div>
          <div class="upload-summary-grid">
            <div class="upload-stat">
              <span class="stat-label">Line Haul Cost</span>
              <span class="stat-value">${formatCurrency(globalCfg.line_haul_cost || 0)}</span>
            </div>
            <div class="upload-stat">
              <span class="stat-label">Line Haul Type</span>
              <span class="stat-value">${esc(globalCfg.line_haul_type || 'per_piece')}</span>
            </div>
            <div class="upload-stat">
              <span class="stat-label">Daily Pickup Cost</span>
              <span class="stat-value">${formatCurrency(globalCfg.daily_pickup_cost || 0)}</span>
            </div>
            <div class="upload-stat">
              <span class="stat-label">Sort Cost</span>
              <span class="stat-value">${formatCurrency(globalCfg.sort_cost || 0)}</span>
            </div>
          </div>
        </div>

        <p style="color:var(--color-text-muted);font-size:var(--text-sm);margin-bottom:16px;">
          Set per-rate-card cost overrides. When set, these override the global defaults for that rate card's profitability calculations.
        </p>

        <div class="table-container">
          <table class="admin-table">
            <thead>
              <tr>
                <th>Rate Card</th>
                <th>Carrier</th>
                <th class="num" title="Line haul cost override">Line Haul ($)</th>
                <th title="Line haul cost type">LH Type</th>
                <th class="num" title="Pickup cost override">Pickup ($)</th>
                <th class="num" title="Sort/handling cost override">Sort ($)</th>
                <th style="width:100px"></th>
              </tr>
            </thead>
            <tbody>
              ${rateCards.map(rc => {
                const ov = overrideMap[rc.id];
                return `
                  <tr id="co-row-${rc.id}">
                    <td class="fw-500">${esc(rc.name)}</td>
                    <td><span class="badge badge-sm">${esc(rc.carrier || '')}</span></td>
                    <td class="num">${ov ? formatCurrency(ov.line_haul_cost || 0) : '<span class="text-faint">global</span>'}</td>
                    <td>${ov ? `<span class="badge badge-sm">${esc(ov.line_haul_type || 'per_piece')}</span>` : '<span class="text-faint">—</span>'}</td>
                    <td class="num">${ov ? formatCurrency(ov.pickup_cost || 0) : '<span class="text-faint">global</span>'}</td>
                    <td class="num">${ov ? formatCurrency(ov.sort_cost || 0) : '<span class="text-faint">global</span>'}</td>
                    <td class="text-right">
                      <button class="btn-ghost btn-xs" onclick="showCostOverrideModal(${rc.id}, '${esc(rc.name)}', ${JSON.stringify(ov || {}).replace(/"/g,'&quot;')})" title="Set cost override for ${esc(rc.name)}">${ov ? 'Edit' : 'Set'}</button>
                      ${ov ? `<button class="btn-ghost btn-xs text-error" onclick="deleteCostOverride(${ov.id})" title="Remove override for ${esc(rc.name)}">Remove</button>` : ''}
                    </td>
                  </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="admin-content"><div class="empty-state">Failed to load cost overrides: ${esc(e.message)}</div></div>`;
  }
}

function showCostOverrideModal(rateCardId, rateCardName, existing) {
  const ov = existing || {};
  openModal(`Cost Override: ${rateCardName}`, `
    <form id="cost-override-form" onsubmit="event.preventDefault(); submitCostOverride(${rateCardId})">
      <div class="form-grid modal-form">
        <div class="form-field">
          <label title="Line haul cost per piece or per lb">Line Haul Cost ($)</label>
          <input type="number" name="line_haul_cost" step="0.01" min="0" value="${ov.line_haul_cost != null ? ov.line_haul_cost : ''}" placeholder="Leave blank to use global">
        </div>
        <div class="form-field">
          <label title="How line haul cost is applied">Line Haul Type</label>
          <select name="line_haul_type">
            <option value="per_piece" ${(!ov.line_haul_type || ov.line_haul_type === 'per_piece') ? 'selected' : ''}>Per Piece</option>
            <option value="per_lb" ${ov.line_haul_type === 'per_lb' ? 'selected' : ''}>Per Pound</option>
          </select>
        </div>
        <div class="form-field">
          <label title="Daily pickup cost allocated per shipment">Pickup Cost ($)</label>
          <input type="number" name="pickup_cost" step="0.01" min="0" value="${ov.pickup_cost != null ? ov.pickup_cost : ''}" placeholder="Leave blank to use global">
        </div>
        <div class="form-field">
          <label title="Sort/handling cost per shipment">Sort Cost ($)</label>
          <input type="number" name="sort_cost" step="0.01" min="0" value="${ov.sort_cost != null ? ov.sort_cost : ''}" placeholder="Leave blank to use global">
        </div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn-secondary" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn-primary">Save Override</button>
      </div>
    </form>
  `);
}

async function submitCostOverride(rateCardId) {
  const form = document.getElementById('cost-override-form');
  const fd = new FormData(form);
  const body = {
    rate_card_id: rateCardId,
    line_haul_cost: fd.get('line_haul_cost') !== '' ? parseFloat(fd.get('line_haul_cost')) : null,
    line_haul_type: fd.get('line_haul_type') || 'per_piece',
    pickup_cost: fd.get('pickup_cost') !== '' ? parseFloat(fd.get('pickup_cost')) : null,
    sort_cost: fd.get('sort_cost') !== '' ? parseFloat(fd.get('sort_cost')) : null
  };
  try {
    await api('/service-cost-overrides', { method: 'PUT', body });
    closeModal();
    showToast('Cost override saved', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteCostOverride(id) {
  if (!confirm('Remove this cost override? The global default will apply instead.')) return;
  try {
    await api(`/service-cost-overrides/${id}`, { method: 'DELETE' });
    showToast('Override removed', 'success');
    router();
  } catch (e) { showToast(e.message, 'error'); }
}

