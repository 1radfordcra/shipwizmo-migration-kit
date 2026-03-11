(function() {
  'use strict';

  // ============================================================================
  // Core Setup (Lines 1–50)
  // ============================================================================

  const API_BASE = '';

  let authState = {
    token: null,
    user: null
  };

  function saveSession() {
    try {
      sessionStorage.setItem('customs_auth', JSON.stringify(authState));
    } catch (e) {
      console.warn('Failed to save session:', e);
    }
  }

  function restoreSession() {
    try {
      const stored = sessionStorage.getItem('customs_auth');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed && parsed.token) {
          authState.token = parsed.token;
          authState.user = parsed.user;
          return true;
        }
      }
    } catch (e) {
      console.warn('Failed to restore session:', e);
    }
    return false;
  }

  function clearSession() {
    sessionStorage.removeItem('customs_auth');
    authState.token = null;
    authState.user = null;
  }

  // ============================================================================
  // SVG Icon Library & Logo (Lines 51–98)
  // ============================================================================

  const ICONS = {
    dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>',
    package: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
    certificate: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
    activity: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    api: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
    x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    chevronDown: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>',
    chevronLeft: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>',
    chevronRight: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>',
    sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>',
    moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
    menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',
    compass: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>',
    wand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/><path d="M20 9h2"/><path d="M17.8 11.8 19 13"/><path d="M15 9h0"/><path d="M17.8 6.2 19 5"/><path d="m3 21 9-9"/><path d="M12.2 6.2 11 5"/></svg>',
    alertTriangle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    key: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>',
    users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
    globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    google: '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>'
  };

  function icon(name, className) {
    const svg = ICONS[name] || '';
    if (className && svg) {
      return svg.replace('<svg', '<svg class="' + className + '"');
    }
    return svg;
  }

  // ============================================================================
  // API Helpers & Utilities (Lines 100–168)
  // ============================================================================

  async function apiCall(method, path, body, isFormData) {
    const headers = {};
    if (authState.token) {
      headers['Authorization'] = 'Bearer ' + authState.token;
    }
    if (!isFormData && body) {
      headers['Content-Type'] = 'application/json';
    }

    const options = {
      method: method,
      headers: headers
    };

    if (body) {
      options.body = isFormData ? body : JSON.stringify(body);
    }

    try {
      const response = await fetch(API_BASE + path, options);
      if (response.status === 401) {
        clearSession();
        navigate('login');
        showToast('Session expired. Please sign in again.', 'warning');
        return null;
      }
      return response;
    } catch (err) {
      showToast('Network error. Please check your connection.', 'error');
      throw err;
    }
  }

  async function apiJSON(method, path, body) {
    const response = await apiCall(method, path, body);
    if (!response) return null;
    if (response.status === 204) return {};
    const data = await response.json();
    if (!response.ok) {
      const msg = data.detail || data.message || 'An error occurred';
      throw new Error(msg);
    }
    return data;
  }

  function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;

    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toastIcons = {
      info: ICONS.info,
      success: ICONS.check,
      warning: ICONS.alertTriangle,
      error: ICONS.x
    };

    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML =
      '<span class="toast-icon">' + (toastIcons[type] || toastIcons.info) + '</span>' +
      '<span class="toast-message">' + escapeHtml(message) + '</span>' +
      '<button class="toast-close" onclick="this.parentElement.classList.add(\'removing\'); setTimeout(() => this.parentElement.remove(), 200)">' + ICONS.x + '</button>';

    container.appendChild(toast);

    setTimeout(function() {
      if (toast.parentElement) {
        toast.classList.add('removing');
        setTimeout(function() {
          if (toast.parentElement) toast.remove();
        }, 200);
      }
    }, duration);
  }

  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function() {
        showToast('Copied to clipboard', 'success', 2000);
      }).catch(function() {
        fallbackCopy(text);
      });
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
      showToast('Copied to clipboard', 'success', 2000);
    } catch (e) {
      showToast('Failed to copy', 'error');
    }
    document.body.removeChild(ta);
  }

  function formatDate(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return '—';
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return months[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear();
  }

  function formatDateTime(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return '—';
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    let hours = d.getHours();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    const mins = d.getMinutes().toString().padStart(2, '0');
    return months[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear() + ' ' + hours + ':' + mins + ' ' + ampm;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function debounce(fn, delay) {
    let timer;
    return function() {
      const context = this;
      const args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function() {
        fn.apply(context, args);
      }, delay);
    };
  }

  // ============================================================================
  // HTS Autocomplete (Lines 169–338)
  // ============================================================================

  function initHtsAutocomplete(inputEl, onSelect) {
    let dropdown = null;
    let items = [];
    let highlightIndex = -1;
    let abortController = null;

    function closeDropdown() {
      if (dropdown && dropdown.parentElement) {
        dropdown.remove();
      }
      dropdown = null;
      items = [];
      highlightIndex = -1;
    }

    function renderDropdown(results) {
      closeDropdown();
      if (!results || results.length === 0) return;

      items = results;
      dropdown = document.createElement('div');
      dropdown.className = 'hts-autocomplete-dropdown';

      results.forEach(function(result, idx) {
        const item = document.createElement('div');
        item.className = 'hts-autocomplete-item';
        if (idx === highlightIndex) item.classList.add('highlighted');
        item.innerHTML =
          '<div class="hts-code">' + escapeHtml(result.hts_code || result.code) + '</div>' +
          '<div class="hts-desc">' + escapeHtml(result.description) + '</div>';
        item.addEventListener('click', function(e) {
          e.stopPropagation();
          selectItem(result);
        });
        dropdown.appendChild(item);
      });

      const parent = inputEl.parentElement;
      if (parent) {
        parent.style.position = 'relative';
        parent.appendChild(dropdown);
      }
    }

    function selectItem(result) {
      inputEl.value = result.hts_code || result.code || '';
      closeDropdown();
      if (onSelect) {
        onSelect({
          hts_code: result.hts_code || result.code,
          description: result.description
        });
      }
    }

    function updateHighlight() {
      if (!dropdown) return;
      const children = dropdown.querySelectorAll('.hts-autocomplete-item');
      children.forEach(function(child, idx) {
        child.classList.toggle('highlighted', idx === highlightIndex);
      });
      if (children[highlightIndex]) {
        children[highlightIndex].scrollIntoView({ block: 'nearest' });
      }
    }

    const doSearch = debounce(async function() {
      const query = inputEl.value.trim();
      if (query.length < 2) {
        closeDropdown();
        return;
      }

      if (abortController) abortController.abort();
      abortController = new AbortController();

      try {
        const response = await fetch(API_BASE + '/api/hts/search?q=' + encodeURIComponent(query), {
          headers: authState.token ? { 'Authorization': 'Bearer ' + authState.token } : {},
          signal: abortController.signal
        });
        if (response.ok) {
          const results = await response.json();
          renderDropdown(Array.isArray(results) ? results : (results.results || []));
        }
      } catch (e) {
        if (e.name !== 'AbortError') {
          console.warn('HTS search error:', e);
        }
      }
    }, 300);

    inputEl.addEventListener('input', doSearch);

    inputEl.addEventListener('keydown', function(e) {
      if (!dropdown) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        highlightIndex = Math.min(highlightIndex + 1, items.length - 1);
        updateHighlight();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        highlightIndex = Math.max(highlightIndex - 1, 0);
        updateHighlight();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (highlightIndex >= 0 && items[highlightIndex]) {
          selectItem(items[highlightIndex]);
        }
      } else if (e.key === 'Escape') {
        closeDropdown();
      }
    });

    document.addEventListener('click', function(e) {
      if (e.target !== inputEl && dropdown && !dropdown.contains(e.target)) {
        closeDropdown();
      }
    });

    return { close: closeDropdown };
  }

  function initHtsValidation(inputEl, statusEl) {
    inputEl.addEventListener('blur', async function() {
      const code = inputEl.value.trim();
      if (!code) {
        statusEl.innerHTML = '';
        statusEl.className = 'hts-validation-status';
        return;
      }

      statusEl.innerHTML = '<span class="loading-spinner"></span>';
      statusEl.className = 'hts-validation-status';

      try {
        const response = await fetch(API_BASE + '/api/hts/validate?code=' + encodeURIComponent(code), {
          headers: authState.token ? { 'Authorization': 'Bearer ' + authState.token } : {}
        });
        const data = await response.json();
        if (data.valid) {
          statusEl.innerHTML = icon('check') + ' <span>Valid — ' + escapeHtml(data.description || '') + '</span>';
          statusEl.className = 'hts-validation-status valid';
        } else {
          statusEl.innerHTML = icon('x') + ' <span>Invalid HTS code</span>';
          statusEl.className = 'hts-validation-status invalid';
        }
      } catch (e) {
        statusEl.innerHTML = icon('x') + ' <span>Validation failed</span>';
        statusEl.className = 'hts-validation-status invalid';
      }
    });
  }

  // ============================================================================
  // Theme Toggle (Lines 340–350)
  // ============================================================================

  function initTheme() {
    const saved = localStorage.getItem('theme');
    if (saved) {
      document.documentElement.setAttribute('data-theme', saved);
    }
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
  }

  function getCurrentTheme() {
    return document.documentElement.getAttribute('data-theme') || 'light';
  }

  // ============================================================================
  // Router (Lines 352–408)
  // ============================================================================

  const ROUTES = {
    '': 'dashboard',
    'login': 'login',
    'register': 'register',
    'forgot-password': 'forgotPassword',
    'dashboard': 'dashboard',
    'skus': 'skus',
    'cusma': 'cusma',
    'activity-log': 'activityLog',
    'api-docs': 'apiDocs',
    'settings': 'settings'
  };

  const AUTH_REQUIRED = ['dashboard', 'skus', 'cusma', 'activity-log', 'api-docs', 'settings'];

  function navigate(hash) {
    window.location.hash = '#' + hash;
  }

  function getRoute() {
    const hash = window.location.hash.replace('#', '').split('?')[0].split('/')[0];
    return hash || '';
  }

  function getRouteParams() {
    const hash = window.location.hash.replace('#', '');
    const parts = hash.split('/');
    return parts.slice(1);
  }

  const RENDER_MAP = {
    login: renderLogin,
    register: renderRegister,
    forgotPassword: renderForgotPassword,
    dashboard: renderDashboard,
    skus: renderSkus,
    cusma: renderCusma,
    activityLog: renderActivityLog,
    apiDocs: renderApiDocs,
    settings: renderSettings
  };

  function handleRoute() {
    const route = getRoute();
    const routeName = ROUTES[route];

    if (!routeName) {
      if (authState.token) {
        navigate('dashboard');
      } else {
        navigate('login');
      }
      return;
    }

    if (AUTH_REQUIRED.indexOf(route) !== -1 && !authState.token) {
      navigate('login');
      return;
    }

    if ((route === 'login' || route === 'register' || route === 'forgot-password') && authState.token) {
      navigate('dashboard');
      return;
    }

    const renderFn = RENDER_MAP[routeName];
    if (renderFn) {
      renderFn();
    } else {
      navigate('login');
    }
  }

  window.addEventListener('hashchange', handleRoute);

  // ============================================================================
  // Google Sign-In (Lines 413–491)
  // ============================================================================

  function openGoogleSignIn() {
    const width = 480;
    const height = 600;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const features = 'width=' + width + ',height=' + height + ',left=' + left + ',top=' + top + ',menubar=no,toolbar=no,status=no';
    window.open('oauth-callback.html', 'GoogleSignIn', features);
  }

  window.addEventListener('message', async function(event) {
    if (event.data && event.data.type === 'google-credential') {
      const credential = event.data.credential;
      try {
        const data = await apiJSON('POST', '/api/auth/google', { id_token: credential });
        if (data && data.token) {
          authState.token = data.token;
          authState.user = data.user;
          saveSession();
          navigate('dashboard');
          showToast('Welcome, ' + (data.user && data.user.name ? data.user.name : 'User') + '!', 'success');
        }
      } catch (err) {
        showToast('Google sign-in failed: ' + err.message, 'error');
      }
    }
  });

  // ============================================================================
  // Auth Pages (Lines 493–729)
  // ============================================================================

  function renderLogin() {
    const app = document.getElementById('app');
    app.innerHTML =
      '<div class="auth-container">' +
        '<div class="auth-card">' +
          '<div class="auth-logo">' +
            '<span style="color: var(--color-primary)">' + icon('compass') + '</span>' +
            '<span class="auth-logo-text">Broad Reach</span>' +
          '</div>' +
          '<h1 class="auth-title">Welcome back</h1>' +
          '<p class="auth-subtitle">Sign in to your customs data portal</p>' +
          '<button class="btn btn-google" id="google-signin-btn">' +
            ICONS.google +
            ' Continue with Google' +
          '</button>' +
          '<div class="auth-divider">or sign in with email</div>' +
          '<form id="login-form">' +
            '<div class="form-group">' +
              '<label class="form-label" for="login-email">Email</label>' +
              '<input class="form-input" type="email" id="login-email" placeholder="you@company.com" required autocomplete="email">' +
            '</div>' +
            '<div class="form-group">' +
              '<label class="form-label" for="login-password">Password</label>' +
              '<input class="form-input" type="password" id="login-password" placeholder="Enter your password" required autocomplete="current-password">' +
            '</div>' +
            '<a class="forgot-link" id="forgot-link">Forgot password?</a>' +
            '<button class="btn btn-primary btn-lg" type="submit" style="width:100%">Sign in</button>' +
          '</form>' +
          '<div class="auth-footer">' +
            'Don\'t have an account? <a class="link" id="register-link">Create account</a>' +
          '</div>' +
        '</div>' +
      '</div>';

    document.getElementById('google-signin-btn').addEventListener('click', openGoogleSignIn);
    document.getElementById('forgot-link').addEventListener('click', function() { navigate('forgot-password'); });
    document.getElementById('register-link').addEventListener('click', function() { navigate('register'); });

    document.getElementById('login-form').addEventListener('submit', async function(e) {
      e.preventDefault();
      const email = document.getElementById('login-email').value.trim();
      const password = document.getElementById('login-password').value;
      const btn = this.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.innerHTML = '<span class="loading-spinner"></span> Signing in...';

      try {
        const data = await apiJSON('POST', '/api/auth/login', { email: email, password: password });
        if (data && data.token) {
          authState.token = data.token;
          authState.user = data.user;
          saveSession();
          navigate('dashboard');
          showToast('Welcome back, ' + (data.user && data.user.name ? data.user.name : 'User') + '!', 'success');
        }
      } catch (err) {
        showToast(err.message || 'Login failed', 'error');
        btn.disabled = false;
        btn.textContent = 'Sign in';
      }
    });
  }

  function renderRegister() {
    const app = document.getElementById('app');
    app.innerHTML =
      '<div class="auth-container">' +
        '<div class="auth-card">' +
          '<div class="auth-logo">' +
            '<span style="color: var(--color-primary)">' + icon('compass') + '</span>' +
            '<span class="auth-logo-text">Broad Reach</span>' +
          '</div>' +
          '<h1 class="auth-title">Create account</h1>' +
          '<p class="auth-subtitle">Get started with your customs data portal</p>' +
          '<button class="btn btn-google" id="google-signin-btn">' +
            ICONS.google +
            ' Continue with Google' +
          '</button>' +
          '<div class="auth-divider">or register with email</div>' +
          '<form id="register-form">' +
            '<div class="form-group">' +
              '<label class="form-label" for="reg-name">Full Name</label>' +
              '<input class="form-input" type="text" id="reg-name" placeholder="Your full name" required>' +
            '</div>' +
            '<div class="form-group">' +
              '<label class="form-label" for="reg-email">Email</label>' +
              '<input class="form-input" type="email" id="reg-email" placeholder="you@company.com" required autocomplete="email">' +
            '</div>' +
            '<div class="form-group">' +
              '<label class="form-label" for="reg-password">Password</label>' +
              '<input class="form-input" type="password" id="reg-password" placeholder="Create a password" required autocomplete="new-password">' +
            '</div>' +
            '<div class="form-group">' +
              '<label class="form-label" for="reg-confirm">Confirm Password</label>' +
              '<input class="form-input" type="password" id="reg-confirm" placeholder="Confirm your password" required autocomplete="new-password">' +
            '</div>' +
            '<button class="btn btn-primary btn-lg" type="submit" style="width:100%">Create account</button>' +
          '</form>' +
          '<div class="auth-footer">' +
            'Already have an account? <a class="link" id="login-link">Sign in</a>' +
          '</div>' +
        '</div>' +
      '</div>';

    document.getElementById('google-signin-btn').addEventListener('click', openGoogleSignIn);
    document.getElementById('login-link').addEventListener('click', function() { navigate('login'); });

    document.getElementById('register-form').addEventListener('submit', async function(e) {
      e.preventDefault();
      const name = document.getElementById('reg-name').value.trim();
      const email = document.getElementById('reg-email').value.trim();
      const password = document.getElementById('reg-password').value;
      const confirm = document.getElementById('reg-confirm').value;

      if (password !== confirm) {
        showToast('Passwords do not match', 'error');
        return;
      }

      if (password.length < 8) {
        showToast('Password must be at least 8 characters', 'error');
        return;
      }

      const btn = this.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.innerHTML = '<span class="loading-spinner"></span> Creating account...';

      try {
        const data = await apiJSON('POST', '/api/auth/register', { name: name, email: email, password: password });
        if (data && data.token) {
          authState.token = data.token;
          authState.user = data.user;
          saveSession();
          navigate('dashboard');
          showToast('Account created! Welcome, ' + (data.user && data.user.name ? data.user.name : name) + '!', 'success');
        }
      } catch (err) {
        showToast(err.message || 'Registration failed', 'error');
        btn.disabled = false;
        btn.textContent = 'Create account';
      }
    });
  }

  function renderForgotPassword() {
    const app = document.getElementById('app');
    app.innerHTML =
      '<div class="auth-container">' +
        '<div class="auth-card">' +
          '<div class="auth-logo">' +
            '<span style="color: var(--color-primary)">' + icon('compass') + '</span>' +
            '<span class="auth-logo-text">Broad Reach</span>' +
          '</div>' +
          '<h1 class="auth-title">Reset password</h1>' +
          '<p class="auth-subtitle">Enter your email to receive a reset code</p>' +
          '<div id="forgot-step1">' +
            '<form id="forgot-form">' +
              '<div class="form-group">' +
                '<label class="form-label" for="forgot-email">Email</label>' +
                '<input class="form-input" type="email" id="forgot-email" placeholder="you@company.com" required autocomplete="email">' +
              '</div>' +
              '<button class="btn btn-primary btn-lg" type="submit" style="width:100%">Send reset code</button>' +
            '</form>' +
          '</div>' +
          '<div id="forgot-step2" style="display:none">' +
            '<div class="banner banner-warning" style="margin-bottom: var(--space-4)">' +
              '<span class="banner-icon">' + icon('info') + '</span>' +
              '<span class="banner-text">Check your email for a reset code.</span>' +
            '</div>' +
            '<form id="reset-form">' +
              '<div class="form-group">' +
                '<label class="form-label" for="reset-token">Reset Code</label>' +
                '<input class="form-input" type="text" id="reset-token" placeholder="Enter the code from your email" required>' +
              '</div>' +
              '<div class="form-group">' +
                '<label class="form-label" for="reset-password">New Password</label>' +
                '<input class="form-input" type="password" id="reset-password" placeholder="Enter new password" required autocomplete="new-password">' +
              '</div>' +
              '<button class="btn btn-primary btn-lg" type="submit" style="width:100%">Reset password</button>' +
            '</form>' +
          '</div>' +
          '<div class="auth-footer">' +
            '<a class="link" id="back-login">Back to sign in</a>' +
          '</div>' +
        '</div>' +
      '</div>';

    document.getElementById('back-login').addEventListener('click', function() { navigate('login'); });

    document.getElementById('forgot-form').addEventListener('submit', async function(e) {
      e.preventDefault();
      const email = document.getElementById('forgot-email').value.trim();
      const btn = this.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.innerHTML = '<span class="loading-spinner"></span> Sending...';

      try {
        await apiJSON('POST', '/api/auth/forgot-password', { email: email });
        document.getElementById('forgot-step1').style.display = 'none';
        document.getElementById('forgot-step2').style.display = 'block';
        showToast('Reset code sent to your email', 'success');
      } catch (err) {
        showToast(err.message || 'Failed to send reset code', 'error');
        btn.disabled = false;
        btn.textContent = 'Send reset code';
      }
    });

    document.getElementById('reset-form').addEventListener('submit', async function(e) {
      e.preventDefault();
      const token = document.getElementById('reset-token').value.trim();
      const password = document.getElementById('reset-password').value;
      const btn = this.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.innerHTML = '<span class="loading-spinner"></span> Resetting...';

      try {
        await apiJSON('POST', '/api/auth/reset-password', { token: token, new_password: password });
        showToast('Password reset successfully! Please sign in.', 'success');
        navigate('login');
      } catch (err) {
        showToast(err.message || 'Failed to reset password', 'error');
        btn.disabled = false;
        btn.textContent = 'Reset password';
      }
    });
  }

  // ============================================================================
  // App Shell (Lines 731–849)
  // ============================================================================

  function renderAppShell(pageTitle, contentFn) {
    const app = document.getElementById('app');
    const route = getRoute();
    const user = authState.user || {};
    const initials = (user.name || 'U').split(' ').map(function(n) { return n[0]; }).join('').toUpperCase().substring(0, 2);

    const navItems = [
      { route: 'dashboard', icon: 'dashboard', label: 'Dashboard' },
      { route: 'skus', icon: 'package', label: 'SKU Management' },
      { route: 'cusma', icon: 'certificate', label: 'CUSMA Certificates' },
      { route: 'activity-log', icon: 'activity', label: 'Activity Log' },
      { route: 'api-docs', icon: 'api', label: 'API Documentation' },
      { route: 'settings', icon: 'settings', label: 'Settings' }
    ];

    let navHtml = '';
    navItems.forEach(function(item) {
      const isActive = item.route === route;
      navHtml +=
        '<button class="sidebar-nav-item' + (isActive ? ' active' : '') + '" data-route="' + item.route + '">' +
          icon(item.icon) +
          '<span>' + item.label + '</span>' +
        '</button>';
    });

    const themeIcon = getCurrentTheme() === 'dark' ? icon('sun') : icon('moon');

    app.innerHTML =
      '<div class="app-layout">' +
        '<aside class="sidebar" id="sidebar">' +
          '<div class="sidebar-logo" id="sidebar-logo">' +
            '<span style="color: var(--color-accent)">' + icon('compass') + '</span>' +
            '<div>' +
              '<span class="sidebar-logo-text">Broad Reach</span>' +
              '<span class="sidebar-logo-sub">Customs Data Portal</span>' +
            '</div>' +
          '</div>' +
          '<nav class="sidebar-nav">' + navHtml + '</nav>' +
          '<div class="sidebar-footer">' +
            '<div class="sidebar-user">' +
              '<div class="sidebar-avatar">' + escapeHtml(initials) + '</div>' +
              '<div class="sidebar-user-info">' +
                '<div class="sidebar-user-name">' + escapeHtml(user.name || 'User') + '</div>' +
                '<div class="sidebar-user-email">' + escapeHtml(user.email || '') + '</div>' +
              '</div>' +
            '</div>' +
            '<button class="sidebar-signout" id="signout-btn">' +
              icon('logout') +
              '<span>Sign out</span>' +
            '</button>' +
          '</div>' +
        '</aside>' +
        '<div class="main-wrapper">' +
          '<header class="top-bar">' +
            '<div class="top-bar-left">' +
              '<button class="mobile-menu-btn" id="mobile-menu-btn">' + icon('menu') + '</button>' +
              '<h1 class="top-bar-title">' + escapeHtml(pageTitle) + '</h1>' +
            '</div>' +
            '<div class="top-bar-right">' +
              '<button class="theme-toggle" id="theme-toggle" title="Toggle theme">' + themeIcon + '</button>' +
            '</div>' +
          '</header>' +
          '<main class="main-content" id="main-content"></main>' +
        '</div>' +
      '</div>';

    // Sidebar navigation
    document.querySelectorAll('.sidebar-nav-item').forEach(function(btn) {
      btn.addEventListener('click', function() {
        navigate(this.getAttribute('data-route'));
      });
    });

    // Logo click
    document.getElementById('sidebar-logo').addEventListener('click', function() {
      navigate('dashboard');
    });

    // Sign out
    document.getElementById('signout-btn').addEventListener('click', function() {
      clearSession();
      navigate('login');
      showToast('Signed out successfully', 'info');
    });

    // Theme toggle
    document.getElementById('theme-toggle').addEventListener('click', function() {
      toggleTheme();
      this.innerHTML = getCurrentTheme() === 'dark' ? icon('sun') : icon('moon');
    });

    // Mobile menu
    document.getElementById('mobile-menu-btn').addEventListener('click', function() {
      const sidebar = document.getElementById('sidebar');
      const isOpen = sidebar.classList.contains('open');
      if (isOpen) {
        sidebar.classList.remove('open');
        const overlay = document.querySelector('.sidebar-overlay');
        if (overlay) overlay.remove();
      } else {
        sidebar.classList.add('open');
        const overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.addEventListener('click', function() {
          sidebar.classList.remove('open');
          this.remove();
        });
        document.querySelector('.app-layout').appendChild(overlay);
      }
    });

    // Render content
    if (contentFn) {
      contentFn(document.getElementById('main-content'));
    }
  }

  // ============================================================================
  // Dashboard (Lines 851–962)
  // ============================================================================

  function renderDashboard() {
    renderAppShell('Dashboard', async function(container) {
      container.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span> Loading dashboard...</div>';

      try {
        const data = await apiJSON('GET', '/api/dashboard');
        if (!data) return;

        const stats = data.stats || {};
        const recentActivity = data.recent_activity || [];
        const expiringCerts = data.expiring_certificates || [];
        const invalidHts = data.invalid_hts_count || 0;
        const apiKey = data.api_key || '';

        let html = '';

        // Stats grid
        html += '<div class="stats-grid">';
        html += renderStatCard('Total SKUs', stats.total_skus || 0, 'package', '', '');
        html += renderStatCard('Validated HTS', stats.validated_hts || 0, 'check', 'success', '');
        html += renderStatCard('Active Certificates', stats.active_certificates || 0, 'certificate', 'accent', '');
        html += renderStatCard('Compliance Score', (stats.compliance_score || 0) + '%', 'shield', stats.compliance_score >= 80 ? 'success' : 'warning', '');
        html += '</div>';

        // Expiring certificates banner
        if (expiringCerts.length > 0) {
          html +=
            '<div class="banner banner-warning">' +
              '<span class="banner-icon">' + icon('alertTriangle') + '</span>' +
              '<span class="banner-text"><strong>' + expiringCerts.length + ' certificate(s)</strong> expiring within 30 days</span>' +
              '<a class="banner-link" id="view-expiring">View certificates →</a>' +
            '</div>';
        }

        // Invalid HTS banner
        if (invalidHts > 0) {
          html +=
            '<div class="banner banner-error">' +
              '<span class="banner-icon">' + icon('alertTriangle') + '</span>' +
              '<span class="banner-text"><strong>' + invalidHts + ' SKU(s)</strong> have invalid or unvalidated HTS codes</span>' +
              '<a class="banner-link" id="view-invalid-hts">Fix SKUs →</a>' +
            '</div>';
        }

        // Dashboard grid
        html += '<div class="dashboard-grid">';

        // Recent activity
        html += '<div class="card">';
        html += '<div class="card-header"><h2 class="card-title">Recent Activity</h2></div>';
        if (recentActivity.length > 0) {
          html += '<div class="activity-feed">';
          recentActivity.slice(0, 10).forEach(function(entry) {
            html +=
              '<div class="activity-item">' +
                '<span class="activity-dot"></span>' +
                '<div class="activity-content">' +
                  '<div class="activity-action">' + escapeHtml(entry.action || entry.event_type || '') + '</div>' +
                  '<div class="activity-details">' + escapeHtml(entry.details || entry.description || '') + '</div>' +
                '</div>' +
                '<span class="activity-time">' + formatDateTime(entry.timestamp || entry.created_at) + '</span>' +
              '</div>';
          });
          html += '</div>';
        } else {
          html += '<div class="empty-state"><p class="empty-state-text">No recent activity</p></div>';
        }
        html += '</div>';

        // Quick actions + API key
        html += '<div>';

        // Quick actions
        html += '<div class="card" style="margin-bottom: var(--space-4)">';
        html += '<div class="card-header"><h2 class="card-title">Quick Actions</h2></div>';
        html += '<div class="quick-actions">';
        html += '<button class="quick-action-btn" id="qa-add-sku">' + icon('plus') + '<span>Add SKU</span></button>';
        html += '<button class="quick-action-btn" id="qa-gen-cert">' + icon('certificate') + '<span>Generate Certificate</span></button>';
        html += '<button class="quick-action-btn" id="qa-api-docs">' + icon('api') + '<span>View API Docs</span></button>';
        html += '</div>';
        html += '</div>';

        // API key display
        html += '<div class="card">';
        html += '<div class="card-header"><h2 class="card-title">API Key</h2></div>';
        const maskedKey = apiKey ? apiKey.substring(0, 8) + '••••••••' + apiKey.substring(apiKey.length - 4) : '••••••••••••';
        html += '<div class="api-key-display">';
        html += '<code id="api-key-value" data-full="' + escapeHtml(apiKey) + '">' + maskedKey + '</code>';
        html += '<button class="btn btn-icon btn-ghost" id="copy-api-key" title="Copy API key">' + icon('copy') + '</button>';
        html += '</div>';
        html += '</div>';

        html += '</div>';
        html += '</div>';

        container.innerHTML = html;

        // Event listeners
        if (document.getElementById('view-expiring')) {
          document.getElementById('view-expiring').addEventListener('click', function() { navigate('cusma'); });
        }
        if (document.getElementById('view-invalid-hts')) {
          document.getElementById('view-invalid-hts').addEventListener('click', function() { navigate('skus'); });
        }
        document.getElementById('qa-add-sku').addEventListener('click', function() {
          navigate('skus');
          setTimeout(function() { renderSkuModal(null); }, 300);
        });
        document.getElementById('qa-gen-cert').addEventListener('click', function() { navigate('cusma'); });
        document.getElementById('qa-api-docs').addEventListener('click', function() { navigate('api-docs'); });
        document.getElementById('copy-api-key').addEventListener('click', function() {
          const fullKey = document.getElementById('api-key-value').getAttribute('data-full');
          copyToClipboard(fullKey);
        });

      } catch (err) {
        container.innerHTML = '<div class="empty-state"><p class="empty-state-title">Failed to load dashboard</p><p class="empty-state-text">' + escapeHtml(err.message) + '</p></div>';
      }
    });
  }

  function renderStatCard(label, value, iconName, variant, trend) {
    const variantClass = variant ? ' ' + variant : '';
    return (
      '<div class="stat-card">' +
        '<div class="stat-card-header">' +
          '<div class="stat-card-icon' + variantClass + '">' + icon(iconName) + '</div>' +
          (trend ? '<span class="stat-card-trend ' + (trend.startsWith('+') ? 'up' : 'down') + '">' + escapeHtml(trend) + '</span>' : '') +
        '</div>' +
        '<div class="stat-card-value">' + escapeHtml(String(value)) + '</div>' +
        '<div class="stat-card-label">' + escapeHtml(label) + '</div>' +
      '</div>'
    );
  }

  // ============================================================================
  // SKU Management (Lines 964–1218)
  // ============================================================================

  let skuState = {
    page: 1,
    pageSize: 25,
    search: '',
    sort: 'sku_code',
    order: 'asc',
    total: 0,
    items: []
  };

  function renderSkus() {
    renderAppShell('SKU Management', async function(container) {
      container.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span> Loading SKUs...</div>';
      await loadSkuTable(container);
    });
  }

  async function loadSkuTable(container) {
    if (!container) container = document.getElementById('main-content');
    if (!container) return;

    try {
      const params = new URLSearchParams({
        page: skuState.page,
        page_size: skuState.pageSize,
        search: skuState.search,
        sort: skuState.sort,
        order: skuState.order
      });
      const data = await apiJSON('GET', '/api/skus?' + params.toString());
      if (!data) return;

      skuState.items = data.items || data.skus || [];
      skuState.total = data.total || 0;

      let html = '';

      // Toolbar
      html += '<div class="toolbar">';
      html += '<div class="toolbar-search">' + icon('search') +
        '<input class="form-input" type="text" id="sku-search" placeholder="Search SKUs..." value="' + escapeHtml(skuState.search) + '">' +
        '</div>';
      html += '<div class="toolbar-actions">';
      html += '<button class="btn btn-secondary btn-sm" id="validate-all-btn">' + icon('check') + ' Validate All</button>';
      html += '<button class="btn btn-secondary btn-sm" id="import-csv-btn">' + icon('upload') + ' Import CSV</button>';
      html += '<button class="btn btn-secondary btn-sm" id="export-csv-btn">' + icon('download') + ' Export CSV</button>';
      html += '<button class="btn btn-primary btn-sm" id="add-sku-btn">' + icon('plus') + ' Add SKU</button>';
      html += '</div>';
      html += '</div>';

      // Table
      html += '<div class="table-wrapper">';
      html += '<table class="data-table">';
      html += '<thead><tr>';
      html += renderSortHeader('SKU Code', 'sku_code');
      html += renderSortHeader('Description', 'description');
      html += renderSortHeader('HTS Code', 'hts_code');
      html += renderSortHeader('Country', 'country_of_origin');
      html += renderSortHeader('Customs Value', 'customs_value');
      html += '<th>Currency</th>';
      html += '<th>Actions</th>';
      html += '</tr></thead>';
      html += '<tbody>';

      if (skuState.items.length === 0) {
        html += '<tr><td colspan="7"><div class="empty-state">' +
          icon('package') +
          '<p class="empty-state-title">No SKUs found</p>' +
          '<p class="empty-state-text">Add your first SKU or import from CSV.</p>' +
          '</div></td></tr>';
      } else {
        skuState.items.forEach(function(sku) {
          const htsValid = sku.hts_validated || sku.hts_valid;
          const htsBadge = htsValid
            ? '<span class="badge badge-success">' + icon('check') + ' Valid</span>'
            : '<span class="badge badge-error">' + icon('x') + ' Invalid</span>';

          const cusmaBadge = sku.cusma_certificate_id
            ? ' <span class="badge badge-info" style="cursor:pointer" data-cert-id="' + sku.cusma_certificate_id + '">CUSMA</span>'
            : '';

          html += '<tr data-sku-id="' + escapeHtml(sku.id) + '">';
          html += '<td><strong>' + escapeHtml(sku.sku_code) + '</strong></td>';
          html += '<td>' + escapeHtml(sku.description || '') + '</td>';
          html += '<td><code style="font-size:var(--text-xs)">' + escapeHtml(sku.hts_code || '—') + '</code> ' + htsBadge + cusmaBadge + '</td>';
          html += '<td>' + escapeHtml(sku.country_of_origin || '—') + '</td>';
          html += '<td>' + (sku.customs_value != null ? Number(sku.customs_value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—') + '</td>';
          html += '<td>' + escapeHtml(sku.currency || 'USD') + '</td>';
          html += '<td class="actions-cell">';
          html += '<button class="btn btn-icon btn-ghost btn-sm edit-sku-btn" data-sku=\'' + escapeHtml(JSON.stringify(sku)) + '\' title="Edit">' + icon('edit') + '</button>';
          html += '<button class="btn btn-icon btn-ghost btn-sm delete-sku-btn" data-sku-id="' + escapeHtml(sku.id) + '" data-sku-code="' + escapeHtml(sku.sku_code) + '" title="Delete">' + icon('trash') + '</button>';
          html += '</td>';
          html += '</tr>';
        });
      }

      html += '</tbody></table>';

      // Pagination
      const totalPages = Math.ceil(skuState.total / skuState.pageSize) || 1;
      html += '<div class="pagination">';
      html += '<span class="pagination-info">Showing ' + skuState.items.length + ' of ' + skuState.total + ' SKUs</span>';
      html += '<div class="pagination-controls">';
      html += '<select class="page-size-select" id="page-size-select">';
      [10, 25, 50, 100].forEach(function(size) {
        html += '<option value="' + size + '"' + (size === skuState.pageSize ? ' selected' : '') + '>' + size + ' per page</option>';
      });
      html += '</select>';
      html += '<button class="btn btn-secondary btn-sm" id="prev-page" ' + (skuState.page <= 1 ? 'disabled' : '') + '>' + icon('chevronLeft') + ' Prev</button>';
      html += '<span style="font-size: var(--text-sm); color: var(--text-secondary)">Page ' + skuState.page + ' of ' + totalPages + '</span>';
      html += '<button class="btn btn-secondary btn-sm" id="next-page" ' + (skuState.page >= totalPages ? 'disabled' : '') + '>Next ' + icon('chevronRight') + '</button>';
      html += '</div>';
      html += '</div>';
      html += '</div>';

      container.innerHTML = html;

      // Event listeners
      document.getElementById('sku-search').addEventListener('input', debounce(function() {
        skuState.search = this.value;
        skuState.page = 1;
        loadSkuTable(container);
      }, 300));

      document.getElementById('add-sku-btn').addEventListener('click', function() { renderSkuModal(null); });
      document.getElementById('validate-all-btn').addEventListener('click', handleValidateAll);
      document.getElementById('import-csv-btn').addEventListener('click', function() { renderBulkUploadModal(); });
      document.getElementById('export-csv-btn').addEventListener('click', handleExportCsv);

      // Sort headers
      document.querySelectorAll('[data-sort-field]').forEach(function(th) {
        th.addEventListener('click', function() {
          const field = this.getAttribute('data-sort-field');
          if (skuState.sort === field) {
            skuState.order = skuState.order === 'asc' ? 'desc' : 'asc';
          } else {
            skuState.sort = field;
            skuState.order = 'asc';
          }
          skuState.page = 1;
          loadSkuTable(container);
        });
      });

      // Pagination
      document.getElementById('prev-page').addEventListener('click', function() {
        if (skuState.page > 1) { skuState.page--; loadSkuTable(container); }
      });
      document.getElementById('next-page').addEventListener('click', function() {
        if (skuState.page < totalPages) { skuState.page++; loadSkuTable(container); }
      });
      document.getElementById('page-size-select').addEventListener('change', function() {
        skuState.pageSize = parseInt(this.value);
        skuState.page = 1;
        loadSkuTable(container);
      });

      // Edit buttons
      document.querySelectorAll('.edit-sku-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          try {
            const sku = JSON.parse(this.getAttribute('data-sku'));
            renderSkuModal(sku);
          } catch (err) {
            showToast('Failed to load SKU data', 'error');
          }
        });
      });

      // Delete buttons
      document.querySelectorAll('.delete-sku-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          const skuId = this.getAttribute('data-sku-id');
          const skuCode = this.getAttribute('data-sku-code');
          renderDeleteConfirm('SKU', { id: skuId, name: skuCode }, async function() {
            try {
              await apiJSON('DELETE', '/api/skus/' + skuId);
              showToast('SKU "' + skuCode + '" deleted', 'success');
              loadSkuTable(container);
            } catch (err) {
              showToast('Failed to delete: ' + err.message, 'error');
            }
          });
        });
      });

      // CUSMA badge clicks
      document.querySelectorAll('[data-cert-id]').forEach(function(badge) {
        badge.addEventListener('click', function(e) {
          e.stopPropagation();
          navigate('cusma');
        });
      });

    } catch (err) {
      container.innerHTML = '<div class="empty-state"><p class="empty-state-title">Failed to load SKUs</p><p class="empty-state-text">' + escapeHtml(err.message) + '</p></div>';
    }
  }

  function renderSortHeader(label, field) {
    const isActive = skuState.sort === field;
    const arrow = isActive ? (skuState.order === 'asc' ? '↑' : '↓') : '↕';
    const activeClass = isActive ? ' active' : '';
    return '<th data-sort-field="' + field + '">' + escapeHtml(label) + ' <span class="sort-icon' + activeClass + '">' + arrow + '</span></th>';
  }

  async function handleValidateAll() {
    const btn = document.getElementById('validate-all-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="loading-spinner"></span> Validating...';
    }
    try {
      const result = await apiJSON('POST', '/api/skus/validate-all');
      const msg = result ? ('Validated: ' + (result.validated || 0) + ' valid, ' + (result.invalid || 0) + ' invalid') : 'Validation complete';
      showToast(msg, 'success');
      loadSkuTable(document.getElementById('main-content'));
    } catch (err) {
      showToast('Validation failed: ' + err.message, 'error');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = icon('check') + ' Validate All';
      }
    }
  }

  async function handleExportCsv() {
    try {
      const response = await apiCall('GET', '/api/skus/export');
      if (!response) return;
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'skus-export.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast('CSV exported successfully', 'success');
    } catch (err) {
      showToast('Export failed: ' + err.message, 'error');
    }
  }

  // ============================================================================
  // SKU Modal — Add/Edit (Lines 1220–1547)
  // ============================================================================

  function renderSkuModal(sku) {
    const isEdit = sku !== null && sku !== undefined;
    const title = isEdit ? 'Edit SKU' : 'Add SKU';

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    // Don't close on backdrop click to prevent accidental data loss

    overlay.innerHTML =
      '<div class="modal modal-lg">' +
        '<div class="modal-header">' +
          '<h2 class="modal-title">' + title + '</h2>' +
          '<button class="modal-close" id="sku-modal-close">' + icon('x') + '</button>' +
        '</div>' +
        '<div class="modal-body">' +
          '<form id="sku-form">' +
            '<div class="form-row">' +
              '<div class="form-group">' +
                '<label class="form-label">SKU Code <span class="required">*</span></label>' +
                '<input class="form-input" type="text" id="sku-code" value="' + escapeHtml(isEdit ? sku.sku_code : '') + '" required placeholder="e.g. WIDGET-001"' + (isEdit ? ' readonly' : '') + '>' +
              '</div>' +
              '<div class="form-group">' +
                '<label class="form-label">Country of Origin</label>' +
                '<input class="form-input" type="text" id="sku-country" value="' + escapeHtml(isEdit ? (sku.country_of_origin || '') : '') + '" placeholder="e.g. US, CA, MX" maxlength="2" style="text-transform:uppercase">' +
                '<span class="form-hint" id="country-hint">ISO 3166-1 alpha-2 code</span>' +
              '</div>' +
            '</div>' +
            '<div class="form-group">' +
              '<label class="form-label">Product Description <span class="required">*</span></label>' +
              '<textarea class="form-textarea" id="sku-description" required placeholder="Describe the product...">' + escapeHtml(isEdit ? (sku.description || '') : '') + '</textarea>' +
            '</div>' +
            '<div class="form-group">' +
              '<label class="form-label">HTS Code</label>' +
              '<div style="display:flex; gap: var(--space-2); align-items:center;">' +
                '<div style="flex:1; position:relative;">' +
                  '<input class="form-input" type="text" id="sku-hts" value="' + escapeHtml(isEdit ? (sku.hts_code || '') : '') + '" placeholder="e.g. 8471.30.0100">' +
                '</div>' +
                '<button type="button" class="ai-wand-btn" id="ai-wand-btn">' + icon('wand') + ' AI Suggest</button>' +
              '</div>' +
              '<div id="hts-validation-status" class="hts-validation-status"></div>' +
              '<div id="ai-recommendation-area"></div>' +
            '</div>' +
            '<div class="form-row">' +
              '<div class="form-group">' +
                '<label class="form-label">Customs Value</label>' +
                '<input class="form-input" type="number" id="sku-value" value="' + (isEdit && sku.customs_value != null ? sku.customs_value : '') + '" placeholder="0.00" step="0.01" min="0">' +
              '</div>' +
              '<div class="form-group">' +
                '<label class="form-label">Currency</label>' +
                '<select class="form-select" id="sku-currency">' +
                  '<option value="USD"' + (isEdit && sku.currency === 'USD' ? ' selected' : (!isEdit ? ' selected' : '')) + '>USD</option>' +
                  '<option value="CAD"' + (isEdit && sku.currency === 'CAD' ? ' selected' : '') + '>CAD</option>' +
                '</select>' +
              '</div>' +
            '</div>' +
          '</form>' +
        '</div>' +
        '<div class="modal-footer">' +
          '<button class="btn btn-secondary" id="sku-modal-cancel">Cancel</button>' +
          '<button class="btn btn-primary" id="sku-modal-save">' + (isEdit ? 'Update SKU' : 'Create SKU') + '</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    // Close handlers
    document.getElementById('sku-modal-close').addEventListener('click', function() { overlay.remove(); });
    document.getElementById('sku-modal-cancel').addEventListener('click', function() { overlay.remove(); });

    // HTS autocomplete
    const htsInput = document.getElementById('sku-hts');
    const htsStatus = document.getElementById('hts-validation-status');
    initHtsAutocomplete(htsInput, function(selected) {
      htsStatus.innerHTML = icon('check') + ' <span>Selected: ' + escapeHtml(selected.description) + '</span>';
      htsStatus.className = 'hts-validation-status valid';
    });
    initHtsValidation(htsInput, htsStatus);

    // Country validation
    var validCountries = ['US','CA','MX','CN','DE','GB','FR','JP','KR','IN','TW','IT','BR','AU','NL','ES','SE','CH','BE','AT','DK','NO','FI','IE','SG','HK','NZ','IL','TH','VN','MY','PH','ID','CL','CO','PE','AR','ZA','EG','TR','PL','CZ','HU','RO','PT','GR'];
    document.getElementById('sku-country').addEventListener('blur', function() {
      var val = this.value.trim().toUpperCase();
      this.value = val;
      var hint = document.getElementById('country-hint');
      if (val && val.length === 2 && validCountries.indexOf(val) === -1) {
        hint.textContent = 'Warning: "' + val + '" may not be a valid ISO country code';
        hint.style.color = 'var(--color-warning)';
      } else if (val && val.length !== 2) {
        hint.textContent = 'Must be a 2-letter ISO country code';
        hint.style.color = 'var(--color-error)';
      } else {
        hint.textContent = 'ISO 3166-1 alpha-2 code';
        hint.style.color = '';
      }
    });

    // AI Wand
    document.getElementById('ai-wand-btn').addEventListener('click', async function() {
      const desc = document.getElementById('sku-description').value.trim();
      const code = document.getElementById('sku-code').value.trim();
      if (!desc) {
        showToast('Please enter a product description first', 'warning');
        return;
      }

      const area = document.getElementById('ai-recommendation-area');
      area.innerHTML = '<div style="display:flex;align-items:center;gap:var(--space-2);padding:var(--space-2);font-size:var(--text-sm);color:var(--text-secondary)"><span class="loading-spinner"></span> Getting AI recommendation...</div>';

      try {
        const result = await apiJSON('POST', '/api/hts/recommend', { description: desc, sku_code: code });
        if (result && result.hts_code) {
          area.innerHTML =
            '<div class="ai-recommendation">' +
              '<div>AI Recommendation:</div>' +
              '<div class="ai-recommendation-code">' + escapeHtml(result.hts_code) + '</div>' +
              '<div class="ai-recommendation-desc">' + escapeHtml(result.description || '') + '</div>' +
              (result.confidence ? '<div style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--space-1)">Confidence: ' + escapeHtml(result.confidence) + '</div>' : '') +
              '<div class="ai-recommendation-actions">' +
                '<button class="btn btn-primary btn-sm" id="accept-ai-rec">Accept</button>' +
                '<button class="btn btn-ghost btn-sm" id="dismiss-ai-rec">Dismiss</button>' +
              '</div>' +
            '</div>';

          document.getElementById('accept-ai-rec').addEventListener('click', function() {
            document.getElementById('sku-hts').value = result.hts_code;
            htsStatus.innerHTML = icon('check') + ' <span>AI recommended — ' + escapeHtml(result.description || '') + '</span>';
            htsStatus.className = 'hts-validation-status valid';
            area.innerHTML = '';
          });
          document.getElementById('dismiss-ai-rec').addEventListener('click', function() {
            area.innerHTML = '';
          });
        } else {
          area.innerHTML = '<div style="padding:var(--space-2);font-size:var(--text-sm);color:var(--text-muted)">No recommendation available.</div>';
        }
      } catch (err) {
        area.innerHTML = '<div style="padding:var(--space-2);font-size:var(--text-sm);color:var(--color-error)">AI recommendation failed: ' + escapeHtml(err.message) + '</div>';
      }
    });

    // Save
    document.getElementById('sku-modal-save').addEventListener('click', async function() {
      const skuCode = document.getElementById('sku-code').value.trim();
      const description = document.getElementById('sku-description').value.trim();
      const htsCode = document.getElementById('sku-hts').value.trim();
      const country = document.getElementById('sku-country').value.trim().toUpperCase();
      const customsValue = document.getElementById('sku-value').value;
      const currency = document.getElementById('sku-currency').value;

      if (!skuCode) {
        showToast('SKU Code is required', 'error');
        return;
      }
      if (!description) {
        showToast('Product Description is required', 'error');
        return;
      }

      const body = {
        sku_code: skuCode,
        description: description,
        hts_code: htsCode || null,
        country_of_origin: country || null,
        customs_value: customsValue ? parseFloat(customsValue) : null,
        currency: currency
      };

      const saveBtn = this;
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="loading-spinner"></span> Saving...';

      try {
        if (isEdit) {
          await apiJSON('PUT', '/api/skus/' + sku.id, body);
          showToast('SKU "' + skuCode + '" updated', 'success');
        } else {
          await apiJSON('POST', '/api/skus', body);
          showToast('SKU "' + skuCode + '" created', 'success');
        }
        overlay.remove();
        loadSkuTable(document.getElementById('main-content'));
      } catch (err) {
        showToast(err.message || 'Failed to save SKU', 'error');
        saveBtn.disabled = false;
        saveBtn.textContent = isEdit ? 'Update SKU' : 'Create SKU';
      }
    });
  }

  // ============================================================================
  // Delete Confirm, Bulk Upload, CSV Export (Lines 1549–1698)
  // ============================================================================

  function renderDeleteConfirm(type, item, onConfirm) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';

    overlay.innerHTML =
      '<div class="modal" style="max-width:420px">' +
        '<div class="modal-header">' +
          '<h2 class="modal-title">Delete ' + escapeHtml(type) + '</h2>' +
          '<button class="modal-close" id="delete-modal-close">' + icon('x') + '</button>' +
        '</div>' +
        '<div class="modal-body">' +
          '<p style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--space-4)">' +
            'Are you sure you want to delete <strong>' + escapeHtml(item.name || item.id) + '</strong>? This action cannot be undone.' +
          '</p>' +
        '</div>' +
        '<div class="modal-footer">' +
          '<button class="btn btn-secondary" id="delete-modal-cancel">Cancel</button>' +
          '<button class="btn btn-danger" id="delete-modal-confirm">Delete</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) overlay.remove();
    });
    document.getElementById('delete-modal-close').addEventListener('click', function() { overlay.remove(); });
    document.getElementById('delete-modal-cancel').addEventListener('click', function() { overlay.remove(); });
    document.getElementById('delete-modal-confirm').addEventListener('click', async function() {
      this.disabled = true;
      this.innerHTML = '<span class="loading-spinner"></span> Deleting...';
      await onConfirm();
      overlay.remove();
    });
  }

  function renderBulkUploadModal() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';

    overlay.innerHTML =
      '<div class="modal modal-lg">' +
        '<div class="modal-header">' +
          '<h2 class="modal-title">Import SKUs from CSV</h2>' +
          '<button class="modal-close" id="upload-modal-close">' + icon('x') + '</button>' +
        '</div>' +
        '<div class="modal-body">' +
          '<div class="upload-zone" id="upload-zone">' +
            icon('upload') +
            '<p class="upload-zone-text">Drag &amp; drop your CSV file here, or <strong>browse</strong></p>' +
            '<p style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--space-2)">Accepts .csv files</p>' +
            '<input type="file" id="csv-file-input" accept=".csv" style="display:none">' +
          '</div>' +
          '<div id="upload-preview-area"></div>' +
          '<div id="upload-progress-area"></div>' +
          '<div id="upload-results-area"></div>' +
        '</div>' +
        '<div class="modal-footer">' +
          '<button class="btn btn-secondary" id="upload-modal-cancel">Cancel</button>' +
          '<button class="btn btn-primary" id="upload-modal-submit" disabled>Upload</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    let selectedFile = null;

    document.getElementById('upload-modal-close').addEventListener('click', function() { overlay.remove(); });
    document.getElementById('upload-modal-cancel').addEventListener('click', function() { overlay.remove(); });

    const zone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('csv-file-input');

    zone.addEventListener('click', function() { fileInput.click(); });

    zone.addEventListener('dragover', function(e) {
      e.preventDefault();
      zone.classList.add('dragover');
    });
    zone.addEventListener('dragleave', function() {
      zone.classList.remove('dragover');
    });
    zone.addEventListener('drop', function(e) {
      e.preventDefault();
      zone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        handleFile(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', function() {
      if (this.files.length > 0) {
        handleFile(this.files[0]);
      }
    });

    function handleFile(file) {
      if (!file.name.endsWith('.csv')) {
        showToast('Please select a CSV file', 'error');
        return;
      }
      selectedFile = file;
      zone.innerHTML = icon('check') + '<p class="upload-zone-text"><strong>' + escapeHtml(file.name) + '</strong> (' + (file.size / 1024).toFixed(1) + ' KB)</p>';
      document.getElementById('upload-modal-submit').disabled = false;

      // Preview
      const reader = new FileReader();
      reader.onload = function(e) {
        const text = e.target.result;
        const lines = text.split('\n').filter(function(l) { return l.trim(); });
        const previewArea = document.getElementById('upload-preview-area');
        if (lines.length > 0) {
          let previewHtml = '<div class="upload-preview"><p style="font-size:var(--text-sm);font-weight:var(--weight-medium);margin:var(--space-3) 0">Preview (first 5 rows):</p>';
          previewHtml += '<div class="table-wrapper"><table class="data-table"><thead><tr>';
          const headers = lines[0].split(',');
          headers.forEach(function(h) { previewHtml += '<th>' + escapeHtml(h.trim().replace(/"/g, '')) + '</th>'; });
          previewHtml += '</tr></thead><tbody>';
          for (var i = 1; i < Math.min(6, lines.length); i++) {
            previewHtml += '<tr>';
            var cols = lines[i].split(',');
            cols.forEach(function(c) { previewHtml += '<td>' + escapeHtml(c.trim().replace(/"/g, '')) + '</td>'; });
            previewHtml += '</tr>';
          }
          previewHtml += '</tbody></table></div>';
          previewHtml += '<p style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--space-2)">' + (lines.length - 1) + ' rows total</p>';
          previewHtml += '</div>';
          previewArea.innerHTML = previewHtml;
        }
      };
      reader.readAsText(file);
    }

    document.getElementById('upload-modal-submit').addEventListener('click', async function() {
      if (!selectedFile) return;
      const btn = this;
      btn.disabled = true;
      btn.innerHTML = '<span class="loading-spinner"></span> Uploading...';

      const progressArea = document.getElementById('upload-progress-area');
      progressArea.innerHTML = '<div class="progress-bar"><div class="progress-bar-fill" id="upload-progress" style="width:0%"></div></div>';

      // Simulate progress
      let progress = 0;
      const progressInterval = setInterval(function() {
        progress = Math.min(progress + 10, 90);
        const bar = document.getElementById('upload-progress');
        if (bar) bar.style.width = progress + '%';
      }, 200);

      try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        const response = await apiCall('POST', '/api/skus/import', formData, true);
        clearInterval(progressInterval);
        const bar = document.getElementById('upload-progress');
        if (bar) bar.style.width = '100%';

        if (response && response.ok) {
          const result = await response.json();
          const resultsArea = document.getElementById('upload-results-area');
          let resultsHtml = '<div class="upload-results">';
          resultsHtml += '<p><span class="success-count">' + (result.imported || result.success || 0) + ' imported</span>';
          if (result.errors && result.errors.length > 0) {
            resultsHtml += ', <span class="error-count">' + result.errors.length + ' errors</span>';
            resultsHtml += '<div class="upload-error-list">';
            result.errors.forEach(function(err) {
              resultsHtml += '<div>Row ' + (err.row || '?') + ': ' + escapeHtml(err.message || err.error || String(err)) + '</div>';
            });
            resultsHtml += '</div>';
          }
          resultsHtml += '</p></div>';
          resultsArea.innerHTML = resultsHtml;

          showToast('CSV import complete', 'success');
          btn.textContent = 'Done';
          btn.addEventListener('click', function() {
            overlay.remove();
            loadSkuTable(document.getElementById('main-content'));
          });
          btn.disabled = false;
        } else {
          const errData = response ? await response.json() : {};
          throw new Error(errData.detail || 'Upload failed');
        }
      } catch (err) {
        clearInterval(progressInterval);
        showToast('Import failed: ' + err.message, 'error');
        btn.disabled = false;
        btn.textContent = 'Upload';
      }
    });
  }

  // ============================================================================
  // CUSMA Certificates (Lines 1700–1946)
  // ============================================================================

  function renderCusma() {
    renderAppShell('CUSMA Certificates', async function(container) {
      container.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span> Loading certificates...</div>';

      try {
        const data = await apiJSON('GET', '/api/cusma');
        if (!data) return;

        const certs = data.certificates || data.items || data || [];
        const certsList = Array.isArray(certs) ? certs : [];

        const totalCerts = certsList.length;
        const activeCerts = certsList.filter(function(c) { return c.status === 'active'; }).length;
        const draftCerts = certsList.filter(function(c) { return c.status === 'draft'; }).length;
        const expiredCerts = certsList.filter(function(c) { return c.status === 'expired'; }).length;

        const now = new Date();
        const thirtyDays = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
        const expiringCerts = certsList.filter(function(c) {
          if (c.status !== 'active' || !c.end_date) return false;
          const end = new Date(c.end_date);
          return end <= thirtyDays && end > now;
        });

        let html = '';

        // Stats
        html += '<div class="stats-grid">';
        html += renderStatCard('Total Certificates', totalCerts, 'certificate', '', '');
        html += renderStatCard('Active', activeCerts, 'check', 'success', '');
        html += renderStatCard('Draft', draftCerts, 'edit', '', '');
        html += renderStatCard('Expired', expiredCerts, 'x', 'warning', '');
        html += '</div>';

        // Expiring banner
        if (expiringCerts.length > 0) {
          html +=
            '<div class="banner banner-warning">' +
              '<span class="banner-icon">' + icon('alertTriangle') + '</span>' +
              '<span class="banner-text"><strong>' + expiringCerts.length + ' certificate(s)</strong> expiring within 30 days</span>' +
            '</div>';
        }

        // Toolbar
        html += '<div class="toolbar">';
        html += '<div class="toolbar-search">' + icon('search') +
          '<input class="form-input" type="text" id="cusma-search" placeholder="Search certificates...">' +
          '</div>';
        html += '<div class="toolbar-actions">';
        html += '<button class="btn btn-secondary btn-sm" id="auto-gen-btn">' + icon('wand') + ' Auto-generate</button>';
        html += '<button class="btn btn-primary btn-sm" id="new-cert-btn">' + icon('plus') + ' Generate Certificate</button>';
        html += '</div>';
        html += '</div>';

        // Certificates list
        html += '<div id="cusma-list">';
        if (certsList.length === 0) {
          html += '<div class="empty-state">' +
            icon('certificate') +
            '<p class="empty-state-title">No certificates yet</p>' +
            '<p class="empty-state-text">Generate your first CUSMA certificate.</p>' +
            '<button class="btn btn-primary" id="empty-new-cert">' + icon('plus') + ' Generate Certificate</button>' +
            '</div>';
        } else {
          html += '<div class="table-wrapper"><table class="data-table">';
          html += '<thead><tr><th>Cert Number</th><th>Type</th><th>Status</th><th>SKU Count</th><th>Period</th><th>Actions</th></tr></thead>';
          html += '<tbody>';
          certsList.forEach(function(cert) {
            const statusBadge = cert.status === 'active'
              ? '<span class="badge badge-success">Active</span>'
              : cert.status === 'expired'
                ? '<span class="badge badge-error">Expired</span>'
                : '<span class="badge badge-draft">Draft</span>';
            const certType = cert.blanket_period || cert.type === 'blanket' ? 'Blanket' : 'Single';
            const period = cert.start_date ? formatDate(cert.start_date) + ' — ' + formatDate(cert.end_date) : '—';
            const skuCount = cert.sku_count || (cert.items ? cert.items.length : 0);

            html += '<tr class="cert-row" data-cert-id="' + escapeHtml(cert.id) + '">';
            html += '<td><strong>' + escapeHtml(cert.certificate_number || cert.id) + '</strong></td>';
            html += '<td>' + certType + '</td>';
            html += '<td>' + statusBadge + '</td>';
            html += '<td>' + skuCount + '</td>';
            html += '<td style="font-size:var(--text-xs)">' + period + '</td>';
            html += '<td class="actions-cell">';
            html += '<button class="btn btn-icon btn-ghost btn-sm view-cert-btn" data-cert-id="' + escapeHtml(cert.id) + '" title="View">' + icon('chevronRight') + '</button>';
            html += '<button class="btn btn-icon btn-ghost btn-sm download-cert-btn" data-cert-id="' + escapeHtml(cert.id) + '" title="Download PDF">' + icon('download') + '</button>';
            html += '<button class="btn btn-icon btn-ghost btn-sm delete-cert-btn" data-cert-id="' + escapeHtml(cert.id) + '" data-cert-num="' + escapeHtml(cert.certificate_number || cert.id) + '" title="Delete">' + icon('trash') + '</button>';
            html += '</td>';
            html += '</tr>';
          });
          html += '</tbody></table></div>';
        }
        html += '</div>';

        // Certificate detail area
        html += '<div id="cusma-detail" style="display:none"></div>';

        container.innerHTML = html;

        // Event listeners
        document.getElementById('new-cert-btn').addEventListener('click', function() { renderCusmaModal(null); });
        if (document.getElementById('auto-gen-btn')) {
          document.getElementById('auto-gen-btn').addEventListener('click', function() { renderAutoGenerateModal(); });
        }
        if (document.getElementById('empty-new-cert')) {
          document.getElementById('empty-new-cert').addEventListener('click', function() { renderCusmaModal(null); });
        }

        // Search
        if (document.getElementById('cusma-search')) {
          document.getElementById('cusma-search').addEventListener('input', debounce(function() {
            const query = this.value.toLowerCase();
            document.querySelectorAll('.cert-row').forEach(function(row) {
              const text = row.textContent.toLowerCase();
              row.style.display = text.includes(query) ? '' : 'none';
            });
          }, 300));
        }

        // View cert
        document.querySelectorAll('.view-cert-btn, .cert-row').forEach(function(el) {
          el.addEventListener('click', function(e) {
            if (e.target.closest('.download-cert-btn') || e.target.closest('.delete-cert-btn')) return;
            const certId = this.getAttribute('data-cert-id') || this.closest('[data-cert-id]').getAttribute('data-cert-id');
            showCertDetail(certId, container);
          });
        });

        // Download PDF
        document.querySelectorAll('.download-cert-btn').forEach(function(btn) {
          btn.addEventListener('click', async function(e) {
            e.stopPropagation();
            const certId = this.getAttribute('data-cert-id');
            await downloadCertPdf(certId);
          });
        });

        // Delete cert
        document.querySelectorAll('.delete-cert-btn').forEach(function(btn) {
          btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const certId = this.getAttribute('data-cert-id');
            const certNum = this.getAttribute('data-cert-num');
            renderDeleteConfirm('Certificate', { id: certId, name: certNum }, async function() {
              try {
                await apiJSON('DELETE', '/api/cusma/' + certId);
                showToast('Certificate deleted', 'success');
                renderCusma();
              } catch (err) {
                showToast('Failed to delete: ' + err.message, 'error');
              }
            });
          });
        });

      } catch (err) {
        container.innerHTML = '<div class="empty-state"><p class="empty-state-title">Failed to load certificates</p><p class="empty-state-text">' + escapeHtml(err.message) + '</p></div>';
      }
    });
  }

  async function showCertDetail(certId, container) {
    try {
      const cert = await apiJSON('GET', '/api/cusma/' + certId);
      if (!cert) return;

      const detailDiv = document.getElementById('cusma-detail') || container;
      const listDiv = document.getElementById('cusma-list');
      if (listDiv) listDiv.style.display = 'none';
      detailDiv.style.display = 'block';

      const statusBadge = cert.status === 'active'
        ? '<span class="badge badge-success">Active</span>'
        : cert.status === 'expired'
          ? '<span class="badge badge-error">Expired</span>'
          : '<span class="badge badge-draft">Draft</span>';

      let html = '';
      html += '<div style="margin-bottom:var(--space-4);display:flex;align-items:center;gap:var(--space-3)">';
      html += '<button class="btn btn-ghost btn-sm" id="back-to-certs">' + icon('chevronLeft') + ' Back to Certificates</button>';
      html += '</div>';

      html += '<div class="card">';
      html += '<div class="card-header">';
      html += '<div style="display:flex;align-items:center;gap:var(--space-3)">';
      html += '<h2 class="card-title">' + escapeHtml(cert.certificate_number || cert.id) + '</h2>';
      html += statusBadge;
      html += '</div>';
      html += '<div style="display:flex;gap:var(--space-2)">';
      if (cert.status === 'draft') {
        html += '<button class="btn btn-primary btn-sm" id="activate-cert">' + icon('check') + ' Activate</button>';
      } else if (cert.status === 'active') {
        html += '<button class="btn btn-secondary btn-sm" id="deactivate-cert">Deactivate</button>';
      }
      html += '<button class="btn btn-secondary btn-sm" id="edit-cert">' + icon('edit') + ' Edit</button>';
      html += '<button class="btn btn-secondary btn-sm" id="download-cert-pdf">' + icon('download') + ' PDF</button>';
      html += '</div>';
      html += '</div>';

      // Certificate data elements
      html += '<div class="cert-detail-section">';
      html += '<h3>Certifier Information</h3>';
      html += '<div class="cert-detail-grid">';
      html += certDetailItem('Name', cert.certifier_name);
      html += certDetailItem('Title', cert.certifier_title);
      html += certDetailItem('Company', cert.certifier_company);
      html += certDetailItem('Phone', cert.certifier_phone);
      html += certDetailItem('Email', cert.certifier_email);
      html += certDetailItem('Address', cert.certifier_address);
      html += '</div></div>';

      html += '<div class="cert-detail-section">';
      html += '<h3>Exporter Information</h3>';
      html += '<div class="cert-detail-grid">';
      html += certDetailItem('Name', cert.exporter_name);
      html += certDetailItem('Company', cert.exporter_company);
      html += certDetailItem('Address', cert.exporter_address);
      html += '</div></div>';

      html += '<div class="cert-detail-section">';
      html += '<h3>Producer Information</h3>';
      html += '<div class="cert-detail-grid">';
      html += certDetailItem('Name', cert.producer_name);
      html += certDetailItem('Company', cert.producer_company);
      html += certDetailItem('Address', cert.producer_address);
      html += '</div></div>';

      html += '<div class="cert-detail-section">';
      html += '<h3>Importer Information</h3>';
      html += '<div class="cert-detail-grid">';
      html += certDetailItem('Name', cert.importer_name);
      html += certDetailItem('Company', cert.importer_company);
      html += certDetailItem('Address', cert.importer_address);
      html += '</div></div>';

      html += '<div class="cert-detail-section">';
      html += '<h3>Period</h3>';
      html += '<div class="cert-detail-grid">';
      html += certDetailItem('Type', cert.blanket_period || cert.type === 'blanket' ? 'Blanket' : 'Single Shipment');
      html += certDetailItem('Start Date', formatDate(cert.start_date));
      html += certDetailItem('End Date', formatDate(cert.end_date));
      html += '</div></div>';

      // SKUs / Items
      const items = cert.items || cert.skus || [];
      html += '<div class="cert-detail-section">';
      html += '<h3>Covered Goods (' + items.length + ')</h3>';
      if (items.length > 0) {
        html += '<div class="table-wrapper"><table class="data-table"><thead><tr>';
        html += '<th>SKU Code</th><th>Description</th><th>HTS Code</th><th>Origin</th>';
        html += '</tr></thead><tbody>';
        items.forEach(function(item) {
          html += '<tr>';
          html += '<td><strong>' + escapeHtml(item.sku_code || '') + '</strong></td>';
          html += '<td>' + escapeHtml(item.description || '') + '</td>';
          html += '<td><code>' + escapeHtml(item.hts_code || '') + '</code></td>';
          html += '<td>' + escapeHtml(item.country_of_origin || item.origin_criterion || '') + '</td>';
          html += '</tr>';
        });
        html += '</tbody></table></div>';
      } else {
        html += '<p style="font-size:var(--text-sm);color:var(--text-muted)">No goods attached.</p>';
      }
      html += '</div>';

      html += '</div>';

      detailDiv.innerHTML = html;

      // Event listeners
      document.getElementById('back-to-certs').addEventListener('click', function() {
        detailDiv.style.display = 'none';
        detailDiv.innerHTML = '';
        if (listDiv) listDiv.style.display = 'block';
        // Also re-show stats/toolbar by re-rendering
        renderCusma();
      });

      if (document.getElementById('activate-cert')) {
        document.getElementById('activate-cert').addEventListener('click', async function() {
          try {
            await apiJSON('PUT', '/api/cusma/' + certId, Object.assign({}, cert, { status: 'active' }));
            showToast('Certificate activated', 'success');
            showCertDetail(certId, container);
          } catch (err) {
            showToast('Failed to activate: ' + err.message, 'error');
          }
        });
      }

      if (document.getElementById('deactivate-cert')) {
        document.getElementById('deactivate-cert').addEventListener('click', async function() {
          try {
            await apiJSON('PUT', '/api/cusma/' + certId, Object.assign({}, cert, { status: 'draft' }));
            showToast('Certificate deactivated', 'success');
            showCertDetail(certId, container);
          } catch (err) {
            showToast('Failed to deactivate: ' + err.message, 'error');
          }
        });
      }

      if (document.getElementById('edit-cert')) {
        document.getElementById('edit-cert').addEventListener('click', function() {
          renderCusmaModal(cert);
        });
      }

      if (document.getElementById('download-cert-pdf')) {
        document.getElementById('download-cert-pdf').addEventListener('click', function() {
          downloadCertPdf(certId);
        });
      }

    } catch (err) {
      showToast('Failed to load certificate: ' + err.message, 'error');
    }
  }

  function certDetailItem(label, value) {
    return '<div class="cert-detail-item"><span class="cert-detail-label">' + escapeHtml(label) + '</span><span class="cert-detail-value">' + escapeHtml(value || '—') + '</span></div>';
  }

  async function downloadCertPdf(certId) {
    try {
      const response = await apiCall('GET', '/api/cusma/' + certId + '/pdf');
      if (!response) return;
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'cusma-certificate-' + certId + '.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast('PDF downloaded', 'success');
    } catch (err) {
      showToast('Failed to download PDF: ' + err.message, 'error');
    }
  }

  // ============================================================================
  // CUSMA Modal — Create/Edit (Lines 1982–2316)
  // ============================================================================

  function renderCusmaModal(cert) {
    const isEdit = cert !== null && cert !== undefined;
    const title = isEdit ? 'Edit Certificate' : 'Generate CUSMA Certificate';

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';

    let html = '<div class="modal modal-xl">';
    html += '<div class="modal-header">';
    html += '<h2 class="modal-title">' + title + '</h2>';
    html += '<button class="modal-close" id="cusma-modal-close">' + icon('x') + '</button>';
    html += '</div>';
    html += '<div class="modal-body">';

    // Section 1: Certifier Info
    html += '<div class="modal-section">';
    html += '<h3 class="modal-section-title">1. Certifier Information</h3>';
    html += '<div class="form-row">';
    html += formField('certifier-name', 'Name', 'text', isEdit ? cert.certifier_name : (authState.user ? authState.user.name : ''), true);
    html += formField('certifier-title', 'Title', 'text', isEdit ? cert.certifier_title : '');
    html += '</div>';
    html += '<div class="form-row">';
    html += formField('certifier-company', 'Company', 'text', isEdit ? cert.certifier_company : '', true);
    html += formField('certifier-phone', 'Phone', 'tel', isEdit ? cert.certifier_phone : '');
    html += '</div>';
    html += formField('certifier-email', 'Email', 'email', isEdit ? cert.certifier_email : (authState.user ? authState.user.email : ''));
    html += formField('certifier-address', 'Address', 'text', isEdit ? cert.certifier_address : '');
    html += '</div>';

    // Section 2: Exporter Info
    html += '<div class="modal-section">';
    html += '<h3 class="modal-section-title">2. Exporter Information</h3>';
    html += '<label class="checkbox-label" style="margin-bottom:var(--space-3)"><input type="checkbox" id="exporter-same"> Same as certifier</label>';
    html += '<div id="exporter-fields">';
    html += '<div class="form-row">';
    html += formField('exporter-name', 'Name', 'text', isEdit ? cert.exporter_name : '');
    html += formField('exporter-company', 'Company', 'text', isEdit ? cert.exporter_company : '');
    html += '</div>';
    html += formField('exporter-address', 'Address', 'text', isEdit ? cert.exporter_address : '');
    html += '</div></div>';

    // Section 3: Producer Info
    html += '<div class="modal-section">';
    html += '<h3 class="modal-section-title">3. Producer Information</h3>';
    html += '<label class="checkbox-label" style="margin-bottom:var(--space-3)"><input type="checkbox" id="producer-same"> Same as certifier</label>';
    html += '<div id="producer-fields">';
    html += '<div class="form-row">';
    html += formField('producer-name', 'Name', 'text', isEdit ? cert.producer_name : '');
    html += formField('producer-company', 'Company', 'text', isEdit ? cert.producer_company : '');
    html += '</div>';
    html += formField('producer-address', 'Address', 'text', isEdit ? cert.producer_address : '');
    html += '</div></div>';

    // Section 4: Importer Info
    html += '<div class="modal-section">';
    html += '<h3 class="modal-section-title">4. Importer Information</h3>';
    html += '<div class="form-row">';
    html += formField('importer-name', 'Name', 'text', isEdit ? cert.importer_name : '');
    html += formField('importer-company', 'Company', 'text', isEdit ? cert.importer_company : '');
    html += '</div>';
    html += formField('importer-address', 'Address', 'text', isEdit ? cert.importer_address : '');
    html += '</div>';

    // Section 5: SKU Selection
    html += '<div class="modal-section">';
    html += '<h3 class="modal-section-title">5. Goods / SKU Selection</h3>';
    html += '<div class="toolbar-search" style="margin-bottom:var(--space-3)">' + icon('search') +
      '<input class="form-input" type="text" id="cusma-sku-search" placeholder="Search SKUs...">' +
      '</div>';
    html += '<div class="sku-picker" id="cusma-sku-picker"><div class="loading-overlay"><span class="loading-spinner"></span></div></div>';
    html += '<div style="margin-top:var(--space-3)">';
    html += '<button class="btn btn-ghost btn-sm" id="add-manual-item">' + icon('plus') + ' Add item manually</button>';
    html += '</div>';
    html += '<div id="manual-items-area"></div>';
    html += '</div>';

    // Section 6: Period
    html += '<div class="modal-section">';
    html += '<h3 class="modal-section-title">6. Certificate Period</h3>';
    html += '<label class="checkbox-label" style="margin-bottom:var(--space-3)"><input type="checkbox" id="blanket-toggle"' + (isEdit && (cert.blanket_period || cert.type === 'blanket') ? ' checked' : ' checked') + '> Blanket period (up to 12 months)</label>';
    html += '<div class="form-row">';
    html += formField('cert-start-date', 'Start Date', 'date', isEdit && cert.start_date ? cert.start_date.substring(0, 10) : new Date().toISOString().substring(0, 10));
    html += formField('cert-end-date', 'End Date', 'date', isEdit && cert.end_date ? cert.end_date.substring(0, 10) : new Date(new Date().getFullYear(), 11, 31).toISOString().substring(0, 10));
    html += '</div></div>';

    html += '</div>';
    html += '<div class="modal-footer">';
    html += '<button class="btn btn-secondary" id="cusma-modal-cancel">Cancel</button>';
    html += '<button class="btn btn-primary" id="cusma-modal-save">' + (isEdit ? 'Update Certificate' : 'Create Certificate') + '</button>';
    html += '</div>';
    html += '</div>';

    overlay.innerHTML = html;
    document.body.appendChild(overlay);

    // Close handlers
    document.getElementById('cusma-modal-close').addEventListener('click', function() { overlay.remove(); });
    document.getElementById('cusma-modal-cancel').addEventListener('click', function() { overlay.remove(); });

    // "Same as certifier" checkboxes
    document.getElementById('exporter-same').addEventListener('change', function() {
      var fields = document.getElementById('exporter-fields');
      if (this.checked) {
        fields.style.opacity = '0.5';
        fields.style.pointerEvents = 'none';
        document.getElementById('exporter-name').value = document.getElementById('certifier-name').value;
        document.getElementById('exporter-company').value = document.getElementById('certifier-company').value;
        document.getElementById('exporter-address').value = document.getElementById('certifier-address').value;
      } else {
        fields.style.opacity = '1';
        fields.style.pointerEvents = 'auto';
      }
    });

    document.getElementById('producer-same').addEventListener('change', function() {
      var fields = document.getElementById('producer-fields');
      if (this.checked) {
        fields.style.opacity = '0.5';
        fields.style.pointerEvents = 'none';
        document.getElementById('producer-name').value = document.getElementById('certifier-name').value;
        document.getElementById('producer-company').value = document.getElementById('certifier-company').value;
        document.getElementById('producer-address').value = document.getElementById('certifier-address').value;
      } else {
        fields.style.opacity = '1';
        fields.style.pointerEvents = 'auto';
      }
    });

    // Load SKUs into picker
    let selectedSkuIds = new Set();
    if (isEdit && cert.items) {
      cert.items.forEach(function(item) {
        if (item.sku_id) selectedSkuIds.add(item.sku_id);
      });
    }
    let manualItems = [];

    loadSkuPicker();

    async function loadSkuPicker(search) {
      try {
        const params = new URLSearchParams({ page: 1, page_size: 100, search: search || '' });
        const data = await apiJSON('GET', '/api/skus?' + params.toString());
        if (!data) return;
        const skus = data.items || data.skus || [];
        const picker = document.getElementById('cusma-sku-picker');
        if (skus.length === 0) {
          picker.innerHTML = '<div style="padding:var(--space-4);text-align:center;font-size:var(--text-sm);color:var(--text-muted)">No SKUs found</div>';
          return;
        }
        let ph = '';
        skus.forEach(function(sku) {
          const selected = selectedSkuIds.has(sku.id) ? ' selected' : '';
          ph += '<div class="sku-picker-item' + selected + '" data-sku-id="' + escapeHtml(sku.id) + '">';
          ph += '<input type="checkbox"' + (selected ? ' checked' : '') + '>';
          ph += '<span class="sku-picker-code">' + escapeHtml(sku.sku_code) + '</span>';
          ph += '<span class="sku-picker-desc">' + escapeHtml(sku.description || '') + '</span>';
          ph += '<span class="sku-picker-hts">' + escapeHtml(sku.hts_code || '') + '</span>';
          ph += '</div>';
        });
        picker.innerHTML = ph;

        // Click to toggle
        picker.querySelectorAll('.sku-picker-item').forEach(function(item) {
          item.addEventListener('click', function() {
            const id = this.getAttribute('data-sku-id');
            const cb = this.querySelector('input[type="checkbox"]');
            if (selectedSkuIds.has(id)) {
              selectedSkuIds.delete(id);
              this.classList.remove('selected');
              cb.checked = false;
            } else {
              selectedSkuIds.add(id);
              this.classList.add('selected');
              cb.checked = true;
            }
          });
        });
      } catch (err) {
        document.getElementById('cusma-sku-picker').innerHTML = '<div style="padding:var(--space-4);color:var(--color-error);font-size:var(--text-sm)">Failed to load SKUs</div>';
      }
    }

    // SKU search
    document.getElementById('cusma-sku-search').addEventListener('input', debounce(function() {
      loadSkuPicker(this.value);
    }, 300));

    // Manual items
    document.getElementById('add-manual-item').addEventListener('click', function() {
      const area = document.getElementById('manual-items-area');
      const idx = manualItems.length;
      manualItems.push({});
      const div = document.createElement('div');
      div.className = 'card';
      div.style.marginTop = 'var(--space-3)';
      div.style.padding = 'var(--space-4)';
      div.innerHTML =
        '<div style="display:flex;justify-content:space-between;margin-bottom:var(--space-3)">' +
          '<strong style="font-size:var(--text-sm)">Manual Item #' + (idx + 1) + '</strong>' +
          '<button class="btn btn-ghost btn-sm remove-manual-item" data-idx="' + idx + '">' + icon('trash') + '</button>' +
        '</div>' +
        '<div class="form-row">' +
          '<div class="form-group">' +
            '<label class="form-label">Description</label>' +
            '<input class="form-input manual-desc" type="text" placeholder="Product description" data-idx="' + idx + '">' +
          '</div>' +
          '<div class="form-group">' +
            '<label class="form-label">HTS Code</label>' +
            '<input class="form-input manual-hts" type="text" placeholder="HTS code" data-idx="' + idx + '">' +
          '</div>' +
        '</div>' +
        '<div class="form-row">' +
          '<div class="form-group">' +
            '<label class="form-label">Origin Criterion</label>' +
            '<input class="form-input manual-origin" type="text" placeholder="e.g. A, B, C, D" data-idx="' + idx + '">' +
          '</div>' +
          '<div class="form-group">' +
            '<label class="form-label">Country of Origin</label>' +
            '<input class="form-input manual-country" type="text" placeholder="e.g. US" data-idx="' + idx + '">' +
          '</div>' +
        '</div>';
      area.appendChild(div);

      div.querySelector('.remove-manual-item').addEventListener('click', function() {
        div.remove();
      });
    });

    // Save
    document.getElementById('cusma-modal-save').addEventListener('click', async function() {
      const body = {
        certifier_name: document.getElementById('certifier-name').value.trim(),
        certifier_title: document.getElementById('certifier-title').value.trim(),
        certifier_company: document.getElementById('certifier-company').value.trim(),
        certifier_phone: document.getElementById('certifier-phone').value.trim(),
        certifier_email: document.getElementById('certifier-email').value.trim(),
        certifier_address: document.getElementById('certifier-address').value.trim(),
        exporter_name: document.getElementById('exporter-name').value.trim(),
        exporter_company: document.getElementById('exporter-company').value.trim(),
        exporter_address: document.getElementById('exporter-address').value.trim(),
        producer_name: document.getElementById('producer-name').value.trim(),
        producer_company: document.getElementById('producer-company').value.trim(),
        producer_address: document.getElementById('producer-address').value.trim(),
        importer_name: document.getElementById('importer-name').value.trim(),
        importer_company: document.getElementById('importer-company').value.trim(),
        importer_address: document.getElementById('importer-address').value.trim(),
        blanket_period: document.getElementById('blanket-toggle').checked,
        start_date: document.getElementById('cert-start-date').value,
        end_date: document.getElementById('cert-end-date').value,
        sku_ids: Array.from(selectedSkuIds),
        manual_items: []
      };

      // Collect manual items
      document.querySelectorAll('.manual-desc').forEach(function(input) {
        const idx = input.getAttribute('data-idx');
        const desc = input.value.trim();
        const hts = document.querySelector('.manual-hts[data-idx="' + idx + '"]');
        const origin = document.querySelector('.manual-origin[data-idx="' + idx + '"]');
        const country = document.querySelector('.manual-country[data-idx="' + idx + '"]');
        if (desc) {
          body.manual_items.push({
            description: desc,
            hts_code: hts ? hts.value.trim() : '',
            origin_criterion: origin ? origin.value.trim() : '',
            country_of_origin: country ? country.value.trim() : ''
          });
        }
      });

      if (!body.certifier_name) {
        showToast('Certifier name is required', 'error');
        return;
      }
      if (!body.certifier_company) {
        showToast('Certifier company is required', 'error');
        return;
      }
      if (body.sku_ids.length === 0 && body.manual_items.length === 0) {
        showToast('Please select at least one SKU or add a manual item', 'error');
        return;
      }

      const saveBtn = this;
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="loading-spinner"></span> Saving...';

      try {
        if (isEdit) {
          await apiJSON('PUT', '/api/cusma/' + cert.id, body);
          showToast('Certificate updated', 'success');
        } else {
          await apiJSON('POST', '/api/cusma', body);
          showToast('Certificate created', 'success');
        }
        overlay.remove();
        renderCusma();
      } catch (err) {
        showToast(err.message || 'Failed to save certificate', 'error');
        saveBtn.disabled = false;
        saveBtn.textContent = isEdit ? 'Update Certificate' : 'Create Certificate';
      }
    });
  }

  function formField(id, label, type, value, required) {
    const val = value || '';
    const req = required ? ' required' : '';
    const reqMark = required ? ' <span class="required">*</span>' : '';
    return (
      '<div class="form-group">' +
        '<label class="form-label" for="' + id + '">' + escapeHtml(label) + reqMark + '</label>' +
        '<input class="form-input" type="' + type + '" id="' + id + '" value="' + escapeHtml(val) + '"' + req + '>' +
      '</div>'
    );
  }

  // ============================================================================
  // Auto-generate CUSMA (Lines 2318–2388)
  // ============================================================================

  function renderAutoGenerateModal() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';

    overlay.innerHTML =
      '<div class="modal modal-lg">' +
        '<div class="modal-header">' +
          '<h2 class="modal-title">Auto-generate Certificate from SKUs</h2>' +
          '<button class="modal-close" id="auto-gen-close">' + icon('x') + '</button>' +
        '</div>' +
        '<div class="modal-body">' +
          '<p style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--space-4)">Select SKUs to include in the certificate. Certifier info will be pre-filled from your profile.</p>' +
          '<div class="toolbar-search" style="margin-bottom:var(--space-3)">' + icon('search') +
            '<input class="form-input" type="text" id="auto-gen-search" placeholder="Search SKUs...">' +
          '</div>' +
          '<div class="sku-picker" id="auto-gen-sku-picker"><div class="loading-overlay"><span class="loading-spinner"></span></div></div>' +
        '</div>' +
        '<div class="modal-footer">' +
          '<button class="btn btn-secondary" id="auto-gen-cancel">Cancel</button>' +
          '<button class="btn btn-primary" id="auto-gen-submit">Generate Certificate</button>' +
        '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    document.getElementById('auto-gen-close').addEventListener('click', function() { overlay.remove(); });
    document.getElementById('auto-gen-cancel').addEventListener('click', function() { overlay.remove(); });

    let selectedIds = new Set();

    async function loadPicker(search) {
      try {
        const params = new URLSearchParams({ page: 1, page_size: 100, search: search || '' });
        const data = await apiJSON('GET', '/api/skus?' + params.toString());
        if (!data) return;
        const skus = data.items || data.skus || [];
        const picker = document.getElementById('auto-gen-sku-picker');
        if (skus.length === 0) {
          picker.innerHTML = '<div style="padding:var(--space-4);text-align:center;font-size:var(--text-sm);color:var(--text-muted)">No SKUs found</div>';
          return;
        }
        let ph = '';
        skus.forEach(function(sku) {
          const selected = selectedIds.has(sku.id) ? ' selected' : '';
          ph += '<div class="sku-picker-item' + selected + '" data-sku-id="' + escapeHtml(sku.id) + '">';
          ph += '<input type="checkbox"' + (selected ? ' checked' : '') + '>';
          ph += '<span class="sku-picker-code">' + escapeHtml(sku.sku_code) + '</span>';
          ph += '<span class="sku-picker-desc">' + escapeHtml(sku.description || '') + '</span>';
          ph += '<span class="sku-picker-hts">' + escapeHtml(sku.hts_code || '') + '</span>';
          ph += '</div>';
        });
        picker.innerHTML = ph;
        picker.querySelectorAll('.sku-picker-item').forEach(function(item) {
          item.addEventListener('click', function() {
            const id = this.getAttribute('data-sku-id');
            const cb = this.querySelector('input[type="checkbox"]');
            if (selectedIds.has(id)) {
              selectedIds.delete(id);
              this.classList.remove('selected');
              cb.checked = false;
            } else {
              selectedIds.add(id);
              this.classList.add('selected');
              cb.checked = true;
            }
          });
        });
      } catch (err) {
        document.getElementById('auto-gen-sku-picker').innerHTML = '<div style="padding:var(--space-4);color:var(--color-error);font-size:var(--text-sm)">Failed to load SKUs</div>';
      }
    }

    loadPicker();

    document.getElementById('auto-gen-search').addEventListener('input', debounce(function() {
      loadPicker(this.value);
    }, 300));

    document.getElementById('auto-gen-submit').addEventListener('click', async function() {
      if (selectedIds.size === 0) {
        showToast('Please select at least one SKU', 'warning');
        return;
      }

      const btn = this;
      btn.disabled = true;
      btn.innerHTML = '<span class="loading-spinner"></span> Generating...';

      try {
        const result = await apiJSON('POST', '/api/cusma/auto-generate', { sku_ids: Array.from(selectedIds) });
        showToast('Certificate generated!', 'success');
        overlay.remove();
        renderCusma();
      } catch (err) {
        showToast('Auto-generate failed: ' + err.message, 'error');
        btn.disabled = false;
        btn.textContent = 'Generate Certificate';
      }
    });
  }

  // ============================================================================
  // Full Data Export (Lines 2390–2406)
  // ============================================================================

  async function exportAllData() {
    try {
      showToast('Preparing export...', 'info', 2000);
      const response = await apiCall('GET', '/api/export');
      if (!response) return;
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'customs-data-export.zip';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast('Data exported successfully', 'success');
    } catch (err) {
      showToast('Export failed: ' + err.message, 'error');
    }
  }

  // ============================================================================
  // Activity Log (Lines 2408–2541)
  // ============================================================================

  let activityState = {
    page: 1,
    pageSize: 50,
    search: '',
    type: ''
  };

  function renderActivityLog() {
    renderAppShell('Activity Log', async function(container) {
      container.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span> Loading activity...</div>';
      await loadActivityLog(container);
    });
  }

  async function loadActivityLog(container) {
    if (!container) container = document.getElementById('main-content');
    if (!container) return;

    try {
      const params = new URLSearchParams({
        page: activityState.page,
        page_size: activityState.pageSize,
        search: activityState.search,
        type: activityState.type
      });
      const data = await apiJSON('GET', '/api/audit-log?' + params.toString());
      if (!data) return;

      const entries = data.items || data.entries || data.logs || [];
      const total = data.total || entries.length;

      let html = '';

      // Toolbar
      html += '<div class="toolbar">';
      html += '<div class="toolbar-search">' + icon('search') +
        '<input class="form-input" type="text" id="activity-search" placeholder="Search activity..." value="' + escapeHtml(activityState.search) + '">' +
        '</div>';
      html += '<select class="form-select" id="activity-type-filter" style="width:auto;min-width:180px">';
      html += '<option value="">All Types</option>';
      html += '<option value="sku.created"' + (activityState.type === 'sku.created' ? ' selected' : '') + '>SKU Created</option>';
      html += '<option value="sku.updated"' + (activityState.type === 'sku.updated' ? ' selected' : '') + '>SKU Updated</option>';
      html += '<option value="sku.deleted"' + (activityState.type === 'sku.deleted' ? ' selected' : '') + '>SKU Deleted</option>';
      html += '<option value="cusma.created"' + (activityState.type === 'cusma.created' ? ' selected' : '') + '>Certificate Created</option>';
      html += '<option value="cusma.updated"' + (activityState.type === 'cusma.updated' ? ' selected' : '') + '>Certificate Updated</option>';
      html += '<option value="cusma.deleted"' + (activityState.type === 'cusma.deleted' ? ' selected' : '') + '>Certificate Deleted</option>';
      html += '<option value="auth.login"' + (activityState.type === 'auth.login' ? ' selected' : '') + '>Login</option>';
      html += '<option value="api.access"' + (activityState.type === 'api.access' ? ' selected' : '') + '>API Access</option>';
      html += '</select>';
      html += '</div>';

      // Table
      html += '<div class="table-wrapper">';
      html += '<table class="data-table">';
      html += '<thead><tr><th>Timestamp</th><th>Action</th><th>Details</th><th>User</th></tr></thead>';
      html += '<tbody>';

      if (entries.length === 0) {
        html += '<tr><td colspan="4"><div class="empty-state">' +
          icon('activity') +
          '<p class="empty-state-title">No activity found</p>' +
          '</div></td></tr>';
      } else {
        entries.forEach(function(entry) {
          const actionBadge = getActionBadge(entry.action || entry.event_type || '');
          html += '<tr class="activity-row" data-entry-id="' + escapeHtml(entry.id || '') + '">';
          html += '<td style="white-space:nowrap;font-size:var(--text-xs)">' + formatDateTime(entry.timestamp || entry.created_at) + '</td>';
          html += '<td>' + actionBadge + '</td>';
          html += '<td style="font-size:var(--text-sm)">' + escapeHtml(entry.details || entry.description || '') + '</td>';
          html += '<td style="font-size:var(--text-sm)">' + escapeHtml(entry.user_name || entry.user_email || '') + '</td>';
          html += '</tr>';
          // Expandable details
          if (entry.changes || entry.diff) {
            html += '<tr class="activity-detail-row" style="display:none" data-parent="' + escapeHtml(entry.id || '') + '">';
            html += '<td colspan="4"><div class="response-block" style="margin:0;font-size:var(--text-xs)">' + escapeHtml(JSON.stringify(entry.changes || entry.diff, null, 2)) + '</div></td>';
            html += '</tr>';
          }
        });
      }

      html += '</tbody></table>';

      // Pagination
      const totalPages = Math.ceil(total / activityState.pageSize) || 1;
      html += '<div class="pagination">';
      html += '<span class="pagination-info">Showing ' + entries.length + ' of ' + total + ' entries</span>';
      html += '<div class="pagination-controls">';
      html += '<button class="btn btn-secondary btn-sm" id="activity-prev" ' + (activityState.page <= 1 ? 'disabled' : '') + '>' + icon('chevronLeft') + ' Previous</button>';
      html += '<span style="font-size: var(--text-sm); color: var(--text-secondary)">Page ' + activityState.page + ' of ' + totalPages + '</span>';
      html += '<button class="btn btn-secondary btn-sm" id="activity-next" ' + (activityState.page >= totalPages ? 'disabled' : '') + '>Next ' + icon('chevronRight') + '</button>';
      html += '</div>';
      html += '</div>';
      html += '</div>';

      container.innerHTML = html;

      // Events
      document.getElementById('activity-search').addEventListener('input', debounce(function() {
        activityState.search = this.value;
        activityState.page = 1;
        loadActivityLog(container);
      }, 300));

      document.getElementById('activity-type-filter').addEventListener('change', function() {
        activityState.type = this.value;
        activityState.page = 1;
        loadActivityLog(container);
      });

      document.getElementById('activity-prev').addEventListener('click', function() {
        if (activityState.page > 1) { activityState.page--; loadActivityLog(container); }
      });

      document.getElementById('activity-next').addEventListener('click', function() {
        if (activityState.page < totalPages) { activityState.page++; loadActivityLog(container); }
      });

      // Expandable rows
      document.querySelectorAll('.activity-row').forEach(function(row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function() {
          const id = this.getAttribute('data-entry-id');
          const detail = document.querySelector('.activity-detail-row[data-parent="' + id + '"]');
          if (detail) {
            detail.style.display = detail.style.display === 'none' ? '' : 'none';
          }
        });
      });

    } catch (err) {
      container.innerHTML = '<div class="empty-state"><p class="empty-state-title">Failed to load activity</p><p class="empty-state-text">' + escapeHtml(err.message) + '</p></div>';
    }
  }

  function getActionBadge(action) {
    const lower = (action || '').toLowerCase();
    if (lower.includes('created') || lower.includes('create')) {
      return '<span class="badge badge-success">' + escapeHtml(action) + '</span>';
    } else if (lower.includes('updated') || lower.includes('update')) {
      return '<span class="badge badge-info">' + escapeHtml(action) + '</span>';
    } else if (lower.includes('deleted') || lower.includes('delete')) {
      return '<span class="badge badge-error">' + escapeHtml(action) + '</span>';
    } else if (lower.includes('login') || lower.includes('auth')) {
      return '<span class="badge badge-draft">' + escapeHtml(action) + '</span>';
    } else {
      return '<span class="badge badge-draft">' + escapeHtml(action) + '</span>';
    }
  }

  // ============================================================================
  // API Documentation (Lines 2543–2683)
  // ============================================================================

  function renderApiDocs() {
    renderAppShell('API Documentation', async function(container) {
      container.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span> Loading...</div>';

      let apiKey = '';
      try {
        const settings = await apiJSON('GET', '/api/settings');
        apiKey = settings ? (settings.api_key || '') : '';
      } catch (e) {
        // try dashboard endpoint
        try {
          const dash = await apiJSON('GET', '/api/dashboard');
          apiKey = dash ? (dash.api_key || '') : '';
        } catch (e2) { /* ignore */ }
      }

      const maskedKey = apiKey ? apiKey.substring(0, 8) + '••••••••' + apiKey.substring(apiKey.length - 4) : 'YOUR_API_KEY';
      const displayKey = apiKey || 'YOUR_API_KEY';

      let html = '';

      // API Key section
      html += '<div class="api-section">';
      html += '<h2>Your API Key</h2>';
      html += '<div class="card" style="margin-bottom:var(--space-6)">';
      html += '<div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-3)">';
      html += '<div class="api-key-display" style="flex:1">';
      html += '<code id="apidoc-key-value" data-full="' + escapeHtml(apiKey) + '">' + maskedKey + '</code>';
      html += '<button class="btn btn-icon btn-ghost" id="apidoc-copy-key" title="Copy">' + icon('copy') + '</button>';
      html += '</div>';
      html += '<button class="btn btn-secondary btn-sm" id="apidoc-regen-key">' + icon('key') + ' Regenerate</button>';
      html += '</div>';
      html += '<p style="font-size:var(--text-xs);color:var(--text-muted)">Include this key as a query parameter <code>api_key</code> or in the header <code>X-API-Key</code>.</p>';
      html += '</div>';
      html += '</div>';

      // Endpoint: Single SKU Lookup
      html += '<div class="api-section">';
      html += '<h2>Single SKU Lookup</h2>';
      html += '<div class="api-endpoint">';
      html += '<span class="api-method get">GET</span>';
      html += '<span class="api-path">/api/lookup/{sku_code}</span>';
      html += '</div>';
      html += '<p style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--space-3)">Look up a single SKU by code. Optionally include CUSMA certificate data with <code>include_cusma=true</code>.</p>';

      // Code examples
      html += renderCodeExamples(displayKey, 'single', 'WIDGET-001');
      html += '</div>';

      // Endpoint: Batch Lookup
      html += '<div class="api-section">';
      html += '<h2>Batch SKU Lookup</h2>';
      html += '<div class="api-endpoint">';
      html += '<span class="api-method post">POST</span>';
      html += '<span class="api-path">/api/lookup/batch</span>';
      html += '</div>';
      html += '<p style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--space-3)">Look up multiple SKUs in a single request. Send an array of SKU codes.</p>';

      html += renderCodeExamples(displayKey, 'batch', null);
      html += '</div>';

      // Response format
      html += '<div class="api-section">';
      html += '<h2>Response Format</h2>';
      html += '<p style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--space-3)">Successful responses return JSON with SKU details:</p>';
      html += '<div class="response-block">' + escapeHtml(JSON.stringify({
        sku_code: "WIDGET-001",
        description: "Premium Widget Assembly",
        hts_code: "8471.30.0100",
        hts_valid: true,
        country_of_origin: "US",
        customs_value: 150.00,
        currency: "USD",
        cusma_certificate: {
          certificate_number: "CUSMA-2026-001",
          status: "active",
          start_date: "2026-01-01",
          end_date: "2026-12-31"
        }
      }, null, 2)) + '</div>';
      html += '</div>';

      // CUSMA data section
      html += '<div class="api-section">';
      html += '<h2>CUSMA Certificate Data</h2>';
      html += '<p style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--space-3)">When <code>include_cusma=true</code>, the response includes the CUSMA certificate data for the SKU:</p>';
      html += '<div class="table-wrapper"><table class="data-table">';
      html += '<thead><tr><th>Field</th><th>Description</th></tr></thead>';
      html += '<tbody>';
      html += '<tr><td><code>certificate_number</code></td><td>Unique certificate identifier</td></tr>';
      html += '<tr><td><code>status</code></td><td>Certificate status: active, draft, or expired</td></tr>';
      html += '<tr><td><code>certifier_name</code></td><td>Name of the certifying party</td></tr>';
      html += '<tr><td><code>exporter_name</code></td><td>Name of the exporter</td></tr>';
      html += '<tr><td><code>producer_name</code></td><td>Name of the producer</td></tr>';
      html += '<tr><td><code>importer_name</code></td><td>Name of the importer</td></tr>';
      html += '<tr><td><code>start_date</code></td><td>Certificate validity start date</td></tr>';
      html += '<tr><td><code>end_date</code></td><td>Certificate validity end date</td></tr>';
      html += '<tr><td><code>blanket_period</code></td><td>Whether this is a blanket certificate</td></tr>';
      html += '</tbody></table></div>';
      html += '</div>';

      // Rate limits
      html += '<div class="api-section">';
      html += '<h2>Rate Limits</h2>';
      html += '<div class="card">';
      html += '<p style="font-size:var(--text-sm);color:var(--text-secondary)">API requests are limited to <strong>120 requests per 60 seconds</strong> per API key. Exceeding this limit will return a <code>429 Too Many Requests</code> response.</p>';
      html += '</div>';
      html += '</div>';

      container.innerHTML = html;

      // Event listeners
      document.getElementById('apidoc-copy-key').addEventListener('click', function() {
        const key = document.getElementById('apidoc-key-value').getAttribute('data-full');
        copyToClipboard(key);
      });

      document.getElementById('apidoc-regen-key').addEventListener('click', function() {
        renderDeleteConfirm('API Key', { name: 'current API key' }, async function() {
          try {
            const result = await apiJSON('POST', '/api/settings/regenerate-api-key');
            if (result && result.api_key) {
              showToast('API key regenerated', 'success');
              renderApiDocs();
            }
          } catch (err) {
            showToast('Failed to regenerate: ' + err.message, 'error');
          }
        });
      });

      // Code tab switching
      document.querySelectorAll('.code-tabs').forEach(function(tabGroup) {
        tabGroup.querySelectorAll('.code-tab').forEach(function(tab) {
          tab.addEventListener('click', function() {
            const target = this.getAttribute('data-tab');
            const parent = this.closest('.code-example-group');
            parent.querySelectorAll('.code-tab').forEach(function(t) { t.classList.remove('active'); });
            parent.querySelectorAll('.code-block').forEach(function(b) { b.style.display = 'none'; });
            this.classList.add('active');
            parent.querySelector('.code-block[data-tab="' + target + '"]').style.display = 'block';
          });
        });
      });
    });
  }

  function renderCodeExamples(apiKey, type, skuCode) {
    const baseUrl = window.location.origin;
    let curlExample, jsExample, pyExample;

    if (type === 'single') {
      curlExample = 'curl -X GET "' + baseUrl + '/api/lookup/' + skuCode + '?include_cusma=true" \\\n  -H "X-API-Key: ' + apiKey + '"';
      jsExample = 'const response = await fetch(\n  "' + baseUrl + '/api/lookup/' + skuCode + '?include_cusma=true",\n  {\n    headers: {\n      "X-API-Key": "' + apiKey + '"\n    }\n  }\n);\nconst data = await response.json();\nconsole.log(data);';
      pyExample = 'import requests\n\nresponse = requests.get(\n    "' + baseUrl + '/api/lookup/' + skuCode + '",\n    params={"include_cusma": "true"},\n    headers={"X-API-Key": "' + apiKey + '"}\n)\ndata = response.json()\nprint(data)';
    } else {
      curlExample = 'curl -X POST "' + baseUrl + '/api/lookup/batch" \\\n  -H "X-API-Key: ' + apiKey + '" \\\n  -H "Content-Type: application/json" \\\n  -d \'{"sku_codes": ["WIDGET-001", "WIDGET-002"], "include_cusma": true}\'';
      jsExample = 'const response = await fetch(\n  "' + baseUrl + '/api/lookup/batch",\n  {\n    method: "POST",\n    headers: {\n      "X-API-Key": "' + apiKey + '",\n      "Content-Type": "application/json"\n    },\n    body: JSON.stringify({\n      sku_codes: ["WIDGET-001", "WIDGET-002"],\n      include_cusma: true\n    })\n  }\n);\nconst data = await response.json();\nconsole.log(data);';
      pyExample = 'import requests\n\nresponse = requests.post(\n    "' + baseUrl + '/api/lookup/batch",\n    json={\n        "sku_codes": ["WIDGET-001", "WIDGET-002"],\n        "include_cusma": True\n    },\n    headers={"X-API-Key": "' + apiKey + '"}\n)\ndata = response.json()\nprint(data)';
    }

    return (
      '<div class="code-example-group">' +
        '<div class="code-tabs">' +
          '<button class="code-tab active" data-tab="curl">cURL</button>' +
          '<button class="code-tab" data-tab="javascript">JavaScript</button>' +
          '<button class="code-tab" data-tab="python">Python</button>' +
        '</div>' +
        '<div class="code-block" data-tab="curl" style="display:block">' + escapeHtml(curlExample) + '</div>' +
        '<div class="code-block" data-tab="javascript" style="display:none">' + escapeHtml(jsExample) + '</div>' +
        '<div class="code-block" data-tab="python" style="display:none">' + escapeHtml(pyExample) + '</div>' +
      '</div>'
    );
  }

  // ============================================================================
  // Settings (Lines 2685–3034)
  // ============================================================================

  function renderSettings() {
    renderAppShell('Settings', async function(container) {
      container.innerHTML = '<div class="loading-overlay"><span class="loading-spinner"></span> Loading settings...</div>';

      let settings = {};
      try {
        settings = await apiJSON('GET', '/api/settings') || {};
      } catch (e) {
        // use authState as fallback
      }

      const user = authState.user || settings.user || {};
      const apiKey = settings.api_key || '';
      const webhooks = settings.webhooks || [];
      const team = settings.team || settings.team_members || [];
      const maskedKey = apiKey ? apiKey.substring(0, 8) + '••••••••' + apiKey.substring(apiKey.length - 4) : '••••••••••••';

      let html = '';

      // Section 1: Account Info
      html += '<div class="settings-section">';
      html += '<h2 class="settings-section-title">Account Information</h2>';
      html += '<div class="settings-row">';
      html += '<span class="settings-row-label">Name</span>';
      html += '<span class="settings-row-value">' + escapeHtml(user.name || '—') + '</span>';
      html += '</div>';
      html += '<div class="settings-row">';
      html += '<span class="settings-row-label">Email</span>';
      html += '<span class="settings-row-value">' + escapeHtml(user.email || '—') + '</span>';
      html += '</div>';
      html += '<div class="settings-row">';
      html += '<span class="settings-row-label">Member since</span>';
      html += '<span class="settings-row-value">' + formatDate(user.created_at || user.member_since) + '</span>';
      html += '</div>';
      html += '</div>';

      // Section 2: Change Password
      html += '<div class="settings-section">';
      html += '<h2 class="settings-section-title">Change Password</h2>';
      html += '<form id="change-password-form">';
      html += '<div class="form-group">';
      html += '<label class="form-label" for="current-password">Current Password</label>';
      html += '<input class="form-input" type="password" id="current-password" placeholder="Enter current password" required autocomplete="current-password">';
      html += '</div>';
      html += '<div class="form-row">';
      html += '<div class="form-group">';
      html += '<label class="form-label" for="new-password">New Password</label>';
      html += '<input class="form-input" type="password" id="new-password" placeholder="Enter new password" required autocomplete="new-password">';
      html += '</div>';
      html += '<div class="form-group">';
      html += '<label class="form-label" for="confirm-new-password">Confirm New Password</label>';
      html += '<input class="form-input" type="password" id="confirm-new-password" placeholder="Confirm new password" required autocomplete="new-password">';
      html += '</div>';
      html += '</div>';
      html += '<button class="btn btn-primary" type="submit">Update Password</button>';
      html += '</form>';
      html += '</div>';

      // Section 3: API Key
      html += '<div class="settings-section">';
      html += '<h2 class="settings-section-title">API Key Management</h2>';
      html += '<div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-3)">';
      html += '<div class="api-key-display" style="flex:1">';
      html += '<code id="settings-key-value" data-full="' + escapeHtml(apiKey) + '">' + maskedKey + '</code>';
      html += '<button class="btn btn-icon btn-ghost" id="settings-copy-key" title="Copy API key">' + icon('copy') + '</button>';
      html += '</div>';
      html += '<button class="btn btn-secondary btn-sm" id="settings-regen-key">' + icon('key') + ' Regenerate</button>';
      html += '</div>';
      html += '<p style="font-size:var(--text-xs);color:var(--text-muted)">Use this key to authenticate API requests. Regenerating will invalidate the current key.</p>';
      html += '</div>';

      // Section 4: Webhooks
      html += '<div class="settings-section">';
      html += '<h2 class="settings-section-title">Webhooks</h2>';
      html += '<div id="webhooks-list">';
      if (webhooks.length === 0) {
        html += '<p style="font-size:var(--text-sm);color:var(--text-muted);margin-bottom:var(--space-3)">No webhooks configured.</p>';
      } else {
        webhooks.forEach(function(wh) {
          html += '<div class="webhook-item" data-webhook-id="' + escapeHtml(wh.id) + '">';
          html += '<span class="webhook-url">' + escapeHtml(wh.url) + '</span>';
          html += '<div class="webhook-events">';
          (wh.events || []).forEach(function(ev) {
            html += '<span class="badge badge-draft">' + escapeHtml(ev) + '</span>';
          });
          html += '</div>';
          html += '<button class="btn btn-ghost btn-sm test-webhook-btn" data-webhook-id="' + escapeHtml(wh.id) + '" title="Test">Test</button>';
          html += '<button class="btn btn-ghost btn-sm delete-webhook-btn" data-webhook-id="' + escapeHtml(wh.id) + '" title="Delete">' + icon('trash') + '</button>';
          html += '</div>';
        });
      }
      html += '</div>';
      html += '<div style="margin-top:var(--space-3)">';
      html += '<button class="btn btn-secondary btn-sm" id="add-webhook-btn">' + icon('plus') + ' Add Webhook</button>';
      html += '</div>';
      html += '<div id="webhook-form-area"></div>';
      html += '</div>';

      // Section 5: Team Management
      html += '<div class="settings-section">';
      html += '<h2 class="settings-section-title">Team Management</h2>';
      html += '<div id="team-list">';
      if (team.length === 0) {
        html += '<p style="font-size:var(--text-sm);color:var(--text-muted);margin-bottom:var(--space-3)">No team members.</p>';
      } else {
        team.forEach(function(member) {
          html += '<div class="team-member">';
          html += '<div class="sidebar-avatar" style="width:32px;height:32px;font-size:var(--text-xs)">' + escapeHtml((member.name || 'U')[0].toUpperCase()) + '</div>';
          html += '<div class="team-member-info">';
          html += '<div class="team-member-name">' + escapeHtml(member.name || '—') + '</div>';
          html += '<div class="team-member-email">' + escapeHtml(member.email || '') + '</div>';
          html += '</div>';
          html += '<span class="team-member-role">' + escapeHtml(member.role || 'Member') + '</span>';
          if (member.role !== 'owner' && member.role !== 'Owner') {
            html += '<button class="btn btn-ghost btn-sm remove-member-btn" data-member-id="' + escapeHtml(member.id) + '" data-member-name="' + escapeHtml(member.name || member.email) + '">' + icon('trash') + '</button>';
          }
          html += '</div>';
        });
      }
      html += '</div>';
      html += '<div style="margin-top:var(--space-3);display:flex;gap:var(--space-2)">';
      html += '<input class="form-input" type="email" id="invite-email" placeholder="Email address" style="max-width:300px">';
      html += '<button class="btn btn-secondary btn-sm" id="invite-member-btn">Invite</button>';
      html += '</div>';
      html += '</div>';

      // Section 6: Data Management
      html += '<div class="settings-section">';
      html += '<h2 class="settings-section-title">Data Management</h2>';
      html += '<p style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--space-3)">Export all your data (SKUs, certificates, audit log) as a ZIP archive.</p>';
      html += '<button class="btn btn-secondary" id="export-all-btn">' + icon('download') + ' Export All Data</button>';
      html += '</div>';

      // Section 7: Sign Out
      html += '<div class="settings-section" style="border-color:var(--color-error)">';
      html += '<h2 class="settings-section-title" style="color:var(--color-error)">Sign Out</h2>';
      html += '<p style="font-size:var(--text-sm);color:var(--text-secondary);margin-bottom:var(--space-3)">Sign out of your account on this device.</p>';
      html += '<button class="btn btn-danger" id="settings-signout">' + icon('logout') + ' Sign Out</button>';
      html += '</div>';

      container.innerHTML = html;

      // ── Event Listeners ──

      // Change password
      document.getElementById('change-password-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const current = document.getElementById('current-password').value;
        const newPass = document.getElementById('new-password').value;
        const confirm = document.getElementById('confirm-new-password').value;

        if (newPass !== confirm) {
          showToast('Passwords do not match', 'error');
          return;
        }
        if (newPass.length < 8) {
          showToast('Password must be at least 8 characters', 'error');
          return;
        }

        const btn = this.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner"></span> Updating...';

        try {
          await apiJSON('POST', '/api/auth/change-password', {
            current_password: current,
            new_password: newPass
          });
          showToast('Password updated successfully', 'success');
          this.reset();
        } catch (err) {
          showToast(err.message || 'Failed to update password', 'error');
        }
        btn.disabled = false;
        btn.textContent = 'Update Password';
      });

      // API key copy
      document.getElementById('settings-copy-key').addEventListener('click', function() {
        const key = document.getElementById('settings-key-value').getAttribute('data-full');
        copyToClipboard(key);
      });

      // API key regenerate
      document.getElementById('settings-regen-key').addEventListener('click', function() {
        renderDeleteConfirm('API Key', { name: 'current API key' }, async function() {
          try {
            const result = await apiJSON('POST', '/api/settings/regenerate-api-key');
            if (result && result.api_key) {
              showToast('API key regenerated', 'success');
              renderSettings();
            }
          } catch (err) {
            showToast('Failed to regenerate: ' + err.message, 'error');
          }
        });
      });

      // Add webhook
      document.getElementById('add-webhook-btn').addEventListener('click', function() {
        const area = document.getElementById('webhook-form-area');
        if (area.querySelector('.card')) return; // already open

        const events = ['sku.created', 'sku.updated', 'sku.deleted', 'cusma.created', 'cusma.updated'];
        let formHtml = '<div class="card" style="margin-top:var(--space-3);padding:var(--space-4)">';
        formHtml += '<h3 style="font-size:var(--text-md);font-weight:var(--weight-semibold);margin-bottom:var(--space-3)">New Webhook</h3>';
        formHtml += '<div class="form-group">';
        formHtml += '<label class="form-label">URL (HTTPS required)</label>';
        formHtml += '<input class="form-input" type="url" id="new-webhook-url" placeholder="https://example.com/webhook" required>';
        formHtml += '</div>';
        formHtml += '<div class="form-group">';
        formHtml += '<label class="form-label">Events</label>';
        formHtml += '<div style="display:flex;flex-wrap:wrap;gap:var(--space-3)">';
        events.forEach(function(ev) {
          formHtml += '<label class="checkbox-label"><input type="checkbox" class="webhook-event-cb" value="' + ev + '" checked> ' + ev + '</label>';
        });
        formHtml += '</div></div>';
        formHtml += '<div style="display:flex;gap:var(--space-2)">';
        formHtml += '<button class="btn btn-primary btn-sm" id="save-webhook-btn">Save Webhook</button>';
        formHtml += '<button class="btn btn-ghost btn-sm" id="cancel-webhook-btn">Cancel</button>';
        formHtml += '</div>';
        formHtml += '</div>';
        area.innerHTML = formHtml;

        document.getElementById('cancel-webhook-btn').addEventListener('click', function() {
          area.innerHTML = '';
        });

        document.getElementById('save-webhook-btn').addEventListener('click', async function() {
          const url = document.getElementById('new-webhook-url').value.trim();
          if (!url.startsWith('https://')) {
            showToast('Webhook URL must use HTTPS', 'error');
            return;
          }

          // Basic private IP check
          const urlObj = new URL(url);
          const hostname = urlObj.hostname;
          if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('192.168.') || hostname.startsWith('10.') || hostname.startsWith('172.16.')) {
            showToast('Private/loopback IPs are not allowed', 'error');
            return;
          }

          const selectedEvents = [];
          document.querySelectorAll('.webhook-event-cb:checked').forEach(function(cb) {
            selectedEvents.push(cb.value);
          });

          if (selectedEvents.length === 0) {
            showToast('Please select at least one event', 'warning');
            return;
          }

          const btn = this;
          btn.disabled = true;
          btn.innerHTML = '<span class="loading-spinner"></span>';

          try {
            await apiJSON('POST', '/api/webhooks', { url: url, events: selectedEvents });
            showToast('Webhook added', 'success');
            renderSettings();
          } catch (err) {
            showToast('Failed to add webhook: ' + err.message, 'error');
            btn.disabled = false;
            btn.textContent = 'Save Webhook';
          }
        });
      });

      // Test webhook
      document.querySelectorAll('.test-webhook-btn').forEach(function(btn) {
        btn.addEventListener('click', async function() {
          const id = this.getAttribute('data-webhook-id');
          this.disabled = true;
          this.textContent = 'Testing...';
          try {
            await apiJSON('POST', '/api/webhooks/' + id + '/test');
            showToast('Test payload sent', 'success');
          } catch (err) {
            showToast('Test failed: ' + err.message, 'error');
          }
          this.disabled = false;
          this.textContent = 'Test';
        });
      });

      // Delete webhook
      document.querySelectorAll('.delete-webhook-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
          const id = this.getAttribute('data-webhook-id');
          renderDeleteConfirm('Webhook', { name: 'this webhook', id: id }, async function() {
            try {
              await apiJSON('DELETE', '/api/webhooks/' + id);
              showToast('Webhook deleted', 'success');
              renderSettings();
            } catch (err) {
              showToast('Failed to delete: ' + err.message, 'error');
            }
          });
        });
      });

      // Invite member
      document.getElementById('invite-member-btn').addEventListener('click', async function() {
        const email = document.getElementById('invite-email').value.trim();
        if (!email) {
          showToast('Please enter an email address', 'warning');
          return;
        }
        this.disabled = true;
        this.innerHTML = '<span class="loading-spinner"></span>';
        try {
          await apiJSON('POST', '/api/team/invite', { email: email });
          showToast('Invitation sent to ' + email, 'success');
          document.getElementById('invite-email').value = '';
          renderSettings();
        } catch (err) {
          showToast('Failed to invite: ' + err.message, 'error');
        }
        this.disabled = false;
        this.textContent = 'Invite';
      });

      // Remove member
      document.querySelectorAll('.remove-member-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
          const memberId = this.getAttribute('data-member-id');
          const memberName = this.getAttribute('data-member-name');
          renderDeleteConfirm('Team Member', { name: memberName, id: memberId }, async function() {
            try {
              await apiJSON('DELETE', '/api/team/' + memberId);
              showToast('Team member removed', 'success');
              renderSettings();
            } catch (err) {
              showToast('Failed to remove: ' + err.message, 'error');
            }
          });
        });
      });

      // Export all
      document.getElementById('export-all-btn').addEventListener('click', exportAllData);

      // Sign out
      document.getElementById('settings-signout').addEventListener('click', function() {
        clearSession();
        navigate('login');
        showToast('Signed out successfully', 'info');
      });
    });
  }

  // ============================================================================
  // Initialization (Lines 3036–3069)
  // ============================================================================

  function checkAutoLogin() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('demo') === 'true') {
      apiJSON('POST', '/api/auth/login', { email: 'demo@broadreach.com', password: 'demo1234' })
        .then(function(data) {
          if (data && data.token) {
            authState.token = data.token;
            authState.user = data.user;
            saveSession();
            navigate('dashboard');
            showToast('Welcome to the demo!', 'success');
          }
        })
        .catch(function() {
          navigate('login');
        });
    }
  }

  function init() {
    initTheme();
    const restored = restoreSession();

    checkAutoLogin();

    // Initial route
    if (!window.location.hash || window.location.hash === '#') {
      if (restored && authState.token) {
        navigate('dashboard');
      } else {
        navigate('login');
      }
    } else {
      handleRoute();
    }
  }

  // Start the application
  init();

})();
