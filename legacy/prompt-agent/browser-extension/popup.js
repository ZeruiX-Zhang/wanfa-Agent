/* ── status check ─────────────────────────────────────── */
document.getElementById('check').addEventListener('click', async () => {
  const text = document.getElementById('statusText');
  const dot  = document.getElementById('dot');
  text.textContent = '检查中...';
  dot.className    = 'dot';
  try {
    const resp = await fetch('http://127.0.0.1:8787/health', {
      signal: AbortSignal.timeout(3000),
    });
    if (resp.ok) {
      text.textContent = '后端运行中';
      dot.className    = 'dot ok';
    } else {
      text.textContent = `后端响应异常 (${resp.status})`;
      dot.className    = 'dot err';
    }
  } catch (_) {
    text.textContent = '后端未启动';
    dot.className    = 'dot err';
  }
});

/* ── undo setting toggle ──────────────────────────────── */
const undoToggle = document.getElementById('undoToggle');

// Load saved value on open
chrome.storage.local.get({ undoEnabled: true }, ({ undoEnabled }) => {
  undoToggle.checked = undoEnabled;
});

// Persist on change
undoToggle.addEventListener('change', () => {
  chrome.storage.local.set({ undoEnabled: undoToggle.checked });
});
