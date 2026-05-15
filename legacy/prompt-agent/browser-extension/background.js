const BACKEND = "http://127.0.0.1:8787";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "prompt",
      title: "Prompt → 优化提示词",
      contexts: ["selection"],
    });
    chrome.contextMenus.create({
      id: "level_up",
      title: "Level Up → 存入知识库",
      contexts: ["selection"],
    });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  // Use info.selectionText as primary (already captured at click time)
  let text = info.selectionText || "";
  let url  = tab?.url || "";

  // Also grab via scripting for contenteditable accuracy
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => ({ text: window.getSelection().toString(), url: location.href }),
    });
    if (results?.[0]?.result?.text) {
      text = results[0].result.text;
      url  = results[0].result.url;
    }
  } catch (_) {}

  if (!text.trim()) {
    notify("error", "请先选中文字");
    return;
  }

  if (info.menuItemId === "prompt") {
    await handlePrompt(text, url, tab.id);
  } else {
    await handleLevelUp(text, url, tab.id);
  }
});

/* ── Prompt: optimize in-place ─────────────────────────── */
async function handlePrompt(text, url, tabId) {
  // 1. Tell content script to show loading state immediately
  sendToTab(tabId, { action: "prompt_start", text });

  // 2. Also store capture so desktop UI can pick it up
  fetch(`${BACKEND}/api/capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      selected_text: text,
      source: "browser-extension",
      action: "prompt",
      url,
    }),
  }).catch(() => {});

  // 3. Call generate API
  try {
    const resp = await fetch(`${BACKEND}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_text: text,
        user_goal: "",
        mode: "auto",
        use_knowledge_os: false,
      }),
    });

    if (!resp.ok) {
      const err = await resp.text().catch(() => resp.statusText);
      sendToTab(tabId, {
        action: "prompt_error",
        hint: `优化失败 (${resp.status})：${err.slice(0, 120)}`,
      });
      notify("error", `请求失败 (${resp.status})`);
      return;
    }

    const data   = await resp.json();
    const result = (data.final_prompt || "").trim() || text;

    // 4. Send optimized text back — content script pastes it in-place
    sendToTab(tabId, { action: "prompt_done", result });
    notify("ok", "提示词已优化");

  } catch (e) {
    const hint = (e instanceof TypeError)
      ? "请先启动 PromptAgent 桌面端（后端未运行）"
      : String(e).slice(0, 140);
    sendToTab(tabId, { action: "prompt_error", hint });
    notify("error", hint);
  }
}

/* ── Level Up: save to knowledge base ──────────────────── */
async function handleLevelUp(text, url, tabId) {
  try {
    const resp = await fetch(`${BACKEND}/api/level-up`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_text: text,
        url,
        collection: "level-up",
        tags: ["level-up"],
      }),
    });
    if (!resp.ok) {
      const err = await resp.text().catch(() => resp.statusText);
      notify("error", `存入失败 (${resp.status}): ${err.slice(0, 120)}`);
      return;
    }
    notify("ok", "已存入知识库，桌面端审核队列可查看");
  } catch (e) {
    const hint = (e instanceof TypeError)
      ? "请先启动 PromptAgent 桌面端"
      : String(e).slice(0, 140);
    notify("error", hint);
  }
}

/* ── helpers ────────────────────────────────────────────── */
function sendToTab(tabId, message) {
  chrome.tabs.sendMessage(tabId, message).catch(() => {
    // Content script not yet injected on this page — inject then retry
    chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"],
    }).then(() => {
      chrome.tabs.sendMessage(tabId, message).catch(() => {});
    }).catch(() => {});
  });
}

function notify(level, message) {
  const isErr = level === "error";
  chrome.action?.setBadgeText({ text: isErr ? "ERR" : "✓" });
  chrome.action?.setBadgeBackgroundColor({ color: isErr ? "#ff3b30" : "#28a745" });
  setTimeout(() => chrome.action?.setBadgeText({ text: "" }), 3000);

  try {
    chrome.notifications?.create({
      type: "basic",
      iconUrl: chrome.runtime.getURL("icon.svg"),
      title: "PromptAgent",
      message,
    });
  } catch (_) { /* badge is sufficient */ }
}
