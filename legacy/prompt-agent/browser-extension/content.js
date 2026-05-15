/* ── styles ─────────────────────────────────────────────── */
const _style = document.createElement('style');
_style.textContent = `
.pa-loading {
  display: inline;
  background: linear-gradient(90deg,
    rgba(0,113,227,0.10) 0%,
    rgba(0,113,227,0.28) 40%,
    rgba(0,113,227,0.10) 80%);
  background-size: 200% 100%;
  animation: pa-shimmer 1.1s ease-in-out infinite;
  border-radius: 3px;
  padding: 0 2px;
  color: rgba(0,0,0,0) !important;
  user-select: none;
}
@keyframes pa-shimmer {
  0%   { background-position: 150% center; }
  100% { background-position: -50%  center; }
}
.pa-result-highlight {
  background: rgba(0,113,227,0.09);
  border-radius: 3px;
  padding: 0 2px;
  border-bottom: 2px solid #0071e3;
}
.pa-overlay {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 380px;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.16), 0 0 0 1px rgba(0,0,0,0.06);
  padding: 16px 18px;
  z-index: 2147483647;
  font-family: -apple-system, "SF Pro Display", sans-serif;
  font-size: 13px;
  color: #1d1d1f;
  animation: pa-in 180ms cubic-bezier(0.4,0,0.2,1);
}
@keyframes pa-in {
  from { transform: translateY(10px); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}
.pa-overlay-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #aeaeb2;
  margin-bottom: 8px;
}
.pa-loading-row {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #6e6e73;
  padding: 4px 0 2px;
}
.pa-spinner {
  width: 16px; height: 16px;
  border: 2px solid rgba(0,113,227,0.20);
  border-top-color: #0071e3;
  border-radius: 50%;
  animation: pa-spin 0.65s linear infinite;
  flex-shrink: 0;
}
@keyframes pa-spin { to { transform: rotate(360deg); } }
.pa-result-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.55;
  max-height: 260px;
  overflow-y: auto;
  margin-bottom: 12px;
  font-size: 13px;
}
.pa-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}
.pa-btn {
  height: 28px;
  padding: 0 13px;
  border: none;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: opacity 100ms;
}
.pa-btn:hover { opacity: 0.82; }
.pa-btn-primary   { background: #0071e3; color: #fff; }
.pa-btn-secondary { background: rgba(0,0,0,0.07); color: #1d1d1f; }
.pa-btn-undo      { background: rgba(255,59,48,0.10); color: #ff3b30; }
`;
document.head.appendChild(_style);

/* ── state ──────────────────────────────────────────────── */
let _ctx        = null;   // saved selection context (set on right-click)
let _overlay    = null;   // current floating panel
let _undoState  = null;   // saved original text/position for one-step undo
let _undoEnabled = true;  // mirrors chrome.storage undoEnabled setting

/* Sync undo setting from storage at load time */
chrome.storage.local.get({ undoEnabled: true }, ({ undoEnabled }) => {
  _undoEnabled = undoEnabled;
});
chrome.storage.onChanged.addListener((changes) => {
  if ('undoEnabled' in changes) _undoEnabled = changes.undoEnabled.newValue;
});

/* Save selection context on right-click — fires before menu appears */
document.addEventListener('contextmenu', () => {
  const active = document.activeElement;
  const sel    = window.getSelection();

  if (_isEditableInput(active) && active.selectionStart !== active.selectionEnd) {
    _ctx = {
      type:     'input',
      el:       active,
      start:    active.selectionStart,
      end:      active.selectionEnd,
      original: active.value.slice(active.selectionStart, active.selectionEnd),
    };
  } else if (_isContentEditable(active) && sel?.toString().trim()) {
    try {
      _ctx = {
        type:     'contenteditable',
        el:       active,
        range:    sel.getRangeAt(0).cloneRange(),
        original: sel.toString(),
      };
    } catch (_) { _ctx = null; }
  } else if (sel?.toString().trim()) {
    try {
      _ctx = {
        type:     'static',
        range:    sel.getRangeAt(0).cloneRange(),
        original: sel.toString(),
      };
    } catch (_) { _ctx = null; }
  } else {
    _ctx = null;
  }
}, true);

/* ── message handler ────────────────────────────────────── */
chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.action === 'getSelection') {
    reply({ text: window.getSelection()?.toString() || '', url: location.href });
  }
  if (msg.action === 'prompt_start')  { _showLoading();          reply({ ok: true }); }
  if (msg.action === 'prompt_done')   { _showResult(msg.result); reply({ ok: true }); }
  if (msg.action === 'prompt_error')  { _cancelLoading(msg.hint); reply({ ok: true }); }
  return true;
});

/* ── loading ─────────────────────────────────────────────── */
const MARK = '﻿​﻿'; // unique invisible marker (BOM + ZWS + BOM)

function _showLoading() {
  _removeOverlay();
  _undoState = null;

  if (_ctx?.type === 'input') {
    const { el, start, end } = _ctx;
    el.setRangeText(MARK, start, end, 'end');
    _ctx.markStart = start;
    el.dataset.paOldBg = el.style.background || '';
    el.style.background =
      'linear-gradient(135deg, rgba(0,113,227,0.04) 0%, rgba(0,113,227,0.08) 100%)';
    _overlaySpinner('正在优化提示词…');

  } else if (_ctx?.type === 'contenteditable') {
    try {
      const range = _ctx.range;
      const span  = document.createElement('span');
      span.className   = 'pa-loading';
      span.textContent = _ctx.original;
      span.dataset.paMark = '1';
      range.deleteContents();
      range.insertNode(span);
      _ctx.loadingSpan = span;
    } catch (_) { _ctx = null; }
    _overlaySpinner('正在优化提示词…');

  } else if (_ctx?.type === 'static') {
    try {
      const range = _ctx.range;
      const span  = document.createElement('span');
      span.className   = 'pa-loading';
      span.textContent = _ctx.original;
      span.dataset.paMark = '1';
      range.deleteContents();
      range.insertNode(span);
      _ctx.loadingSpan = span;
    } catch (_) { _ctx = null; }
    _overlaySpinner('正在优化提示词…');

  } else {
    _overlaySpinner('正在优化提示词…');
  }
}

/* ── result ──────────────────────────────────────────────── */
function _showResult(result) {
  _removeOverlay();

  if (_ctx?.type === 'input') {
    const { el, markStart, original } = _ctx;
    const val = el.value;
    const idx = val.indexOf(MARK, Math.max(0, markStart - 5));
    if (idx !== -1) {
      el.setRangeText(result, idx, idx + MARK.length, 'end');
      el.focus();
      el.setSelectionRange(idx, idx + result.length);
      // Save undo state before clearing ctx
      _undoState = { type: 'input', el, start: idx, length: result.length, original };
    }
    el.style.background = el.dataset.paOldBg || '';
    delete el.dataset.paOldBg;
    _ctx = null;
    _overlayResult(result, true);

  } else if (_ctx?.type === 'contenteditable' && _ctx.loadingSpan) {
    const span = document.createElement('span');
    span.className   = 'pa-result-highlight';
    span.textContent = result;
    _undoState = { type: 'span', span, original: _ctx.original };
    _ctx.loadingSpan.replaceWith(span);
    _ctx = null;
    _overlayResult(result, true);

  } else if (_ctx?.type === 'static' && _ctx.loadingSpan) {
    const span = document.createElement('span');
    span.className   = 'pa-result-highlight';
    span.textContent = result;
    _undoState = { type: 'span', span, original: _ctx.original };
    _ctx.loadingSpan.replaceWith(span);
    _ctx = null;
    _overlayResult(result, false); // static page — keep overlay open for copy

  } else {
    _undoState = null;
    _ctx = null;
    _overlayResult(result, false);
  }
}

/* ── undo ─────────────────────────────────────────────────── */
function _doUndo() {
  if (!_undoState) return;
  const s = _undoState;
  _undoState = null;
  _removeOverlay();

  if (s.type === 'input') {
    const { el, start, length, original } = s;
    el.setRangeText(original, start, start + length, 'end');
    el.focus();
    el.setSelectionRange(start, start + original.length);
  } else if (s.type === 'span') {
    s.span.replaceWith(document.createTextNode(s.original));
  }
}

/* ── cancel / error ──────────────────────────────────────── */
function _cancelLoading(hint) {
  _removeOverlay();

  if (_ctx?.type === 'input' && _ctx.el) {
    const { el, markStart, original } = _ctx;
    const idx = (el.value || '').indexOf(MARK, Math.max(0, markStart - 5));
    if (idx !== -1) el.setRangeText(original, idx, idx + MARK.length, 'end');
    el.style.background = el.dataset.paOldBg || '';
    delete el.dataset.paOldBg;
  } else if (_ctx?.loadingSpan) {
    _ctx.loadingSpan.replaceWith(document.createTextNode(_ctx.original || ''));
  }
  _ctx = null;
  _undoState = null;

  if (hint) _overlayError(hint);
}

/* ── overlay helpers ─────────────────────────────────────── */
function _overlaySpinner(msg) {
  _removeOverlay();
  _overlay = document.createElement('div');
  _overlay.className = 'pa-overlay';
  _overlay.innerHTML = `
    <div class="pa-overlay-label">PromptAgent</div>
    <div class="pa-loading-row">
      <div class="pa-spinner"></div>
      <span>${_esc(msg)}</span>
    </div>`;
  document.body.appendChild(_overlay);
}

function _overlayResult(result, autoClose) {
  _removeOverlay();
  const showUndo = _undoEnabled && !!_undoState;
  _overlay = document.createElement('div');
  _overlay.className = 'pa-overlay';
  const preview = result.length > 500 ? result.slice(0, 500) + '…' : result;
  _overlay.innerHTML = `
    <div class="pa-overlay-label">PromptAgent — 优化完成</div>
    <div class="pa-result-text">${_esc(preview)}</div>
    <div class="pa-actions">
      ${showUndo ? '<button class="pa-btn pa-btn-undo" id="_pa_undo">↩ 撤销</button>' : ''}
      <button class="pa-btn pa-btn-secondary" id="_pa_close">关闭</button>
      <button class="pa-btn pa-btn-primary"   id="_pa_copy">复制完整内容</button>
    </div>`;
  document.body.appendChild(_overlay);

  if (showUndo) {
    _overlay.querySelector('#_pa_undo').onclick = _doUndo;
  }
  _overlay.querySelector('#_pa_close').onclick = _removeOverlay;
  _overlay.querySelector('#_pa_copy').onclick  = () => {
    navigator.clipboard.writeText(result).then(() => {
      const btn = _overlay?.querySelector('#_pa_copy');
      if (btn) { btn.textContent = '已复制 ✓'; btn.style.background = '#28a745'; }
    });
  };
  // Skip auto-close when undo is available so user has time to act
  if (autoClose && !showUndo) setTimeout(_removeOverlay, 5000);
}

function _overlayError(msg) {
  _removeOverlay();
  _overlay = document.createElement('div');
  _overlay.className = 'pa-overlay';
  _overlay.innerHTML = `
    <div class="pa-overlay-label" style="color:#ff3b30">PromptAgent — 出错了</div>
    <div style="color:#1d1d1f;margin-bottom:10px">${_esc(msg)}</div>
    <div class="pa-actions">
      <button class="pa-btn pa-btn-secondary" id="_pa_close">关闭</button>
    </div>`;
  document.body.appendChild(_overlay);
  _overlay.querySelector('#_pa_close').onclick = _removeOverlay;
  setTimeout(_removeOverlay, 6000);
}

function _removeOverlay() {
  if (_overlay) { _overlay.remove(); _overlay = null; }
}

/* ── utils ───────────────────────────────────────────────── */
function _isEditableInput(el) {
  if (!el) return false;
  const tag = el.tagName?.toLowerCase();
  if (tag === 'textarea') return true;
  if (tag === 'input') {
    const t = (el.type || 'text').toLowerCase();
    return ['text','search','url','email','','password'].includes(t);
  }
  return false;
}

function _isContentEditable(el) {
  return el?.isContentEditable === true;
}

function _esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
