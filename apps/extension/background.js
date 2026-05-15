const DEFAULT_ENDPOINT = "http://127.0.0.1:8000/api/prompt/capture";
const QUEUE_KEY = "pendingCaptures";
const ENDPOINT_KEY = "captureEndpoint";
const MAX_QUEUE_ITEMS = 25;

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "capture-selection",
      title: "Capture to Reality OS",
      contexts: ["selection"],
    });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "capture-selection") return;
  const selection = await readSelection(tab, info.selectionText || "");
  if (!selection.text.trim()) {
    setBadge("EMPTY", "#8a8f98");
    return;
  }
  const payload = buildCapturePayload(selection, "context-menu");
  await queueCapture(payload);
  await postCapture(payload);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "REALITY_OS_CAPTURE") return false;
  handleRuntimeCapture(message.payload, sender.tab)
    .then((result) => sendResponse(result))
    .catch((error) => sendResponse({ ok: false, error: String(error) }));
  return true;
});

async function handleRuntimeCapture(payload, tab) {
  const page = await readSelection(tab, payload?.text || "");
  const capture = buildCapturePayload(
    {
      ...page,
      text: payload?.text || page.text,
      title: payload?.title || page.title,
      url: payload?.url || page.url,
    },
    payload?.capture_method || "popup"
  );
  await queueCapture(capture);
  const posted = await postCapture(capture);
  return { ok: true, capture, posted };
}

async function readSelection(tab, fallbackText) {
  if (!tab?.id) {
    return { text: fallbackText || "", title: "", url: "" };
  }
  try {
    const response = await chrome.tabs.sendMessage(tab.id, { type: "REALITY_OS_READ_SELECTION" });
    return {
      text: response?.text || fallbackText || "",
      title: response?.title || tab.title || "",
      url: response?.url || tab.url || "",
    };
  } catch (_) {
    return { text: fallbackText || "", title: tab.title || "", url: tab.url || "" };
  }
}

function buildCapturePayload(page, captureMethod) {
  return {
    text: String(page.text || "").slice(0, 20000),
    source: {
      kind: "browser-extension",
      title: String(page.title || ""),
      url: String(page.url || ""),
      content_type: "text/plain",
    },
    trust_level: "untrusted",
    status: "pending_input",
    write_policy: "pending_review_only",
    metadata: {
      capture_method: captureMethod,
      extension: "reality-os-input-capture",
      external_input: true,
      input_only: true,
    },
  };
}

async function postCapture(payload) {
  const { [ENDPOINT_KEY]: endpoint = DEFAULT_ENDPOINT } = await chrome.storage.local.get({
    [ENDPOINT_KEY]: DEFAULT_ENDPOINT,
  });
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(3000),
    });
    setBadge(response.ok ? "SENT" : "QUEUE", response.ok ? "#1f8f4d" : "#8a6f00");
    return response.ok;
  } catch (_) {
    setBadge("QUEUE", "#8a6f00");
    return false;
  }
}

async function queueCapture(payload) {
  const { [QUEUE_KEY]: existing = [] } = await chrome.storage.local.get({ [QUEUE_KEY]: [] });
  const next = [payload, ...existing].slice(0, MAX_QUEUE_ITEMS);
  await chrome.storage.local.set({ [QUEUE_KEY]: next });
}

function setBadge(text, color) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 2500);
}
