const DEFAULT_ENDPOINT = "http://127.0.0.1:8000/api/prompt/capture";
const ENDPOINT_KEY = "captureEndpoint";

const endpointInput = document.getElementById("endpoint");
const noteInput = document.getElementById("note");
const statusNode = document.getElementById("status");

init();

async function init() {
  const { [ENDPOINT_KEY]: endpoint = DEFAULT_ENDPOINT } = await chrome.storage.local.get({
    [ENDPOINT_KEY]: DEFAULT_ENDPOINT,
  });
  endpointInput.value = endpoint;
  document.getElementById("save").addEventListener("click", saveEndpoint);
  document.getElementById("capture").addEventListener("click", captureInput);
}

async function saveEndpoint() {
  await chrome.storage.local.set({ [ENDPOINT_KEY]: endpointInput.value.trim() || DEFAULT_ENDPOINT });
  setStatus("Endpoint saved.");
}

async function captureInput() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const selected = await readSelection(tab);
  const text = (noteInput.value || selected.text || "").trim();
  if (!text) {
    setStatus("Nothing to capture.");
    return;
  }
  const response = await chrome.runtime.sendMessage({
    type: "REALITY_OS_CAPTURE",
    payload: {
      text,
      title: selected.title || tab?.title || "",
      url: selected.url || tab?.url || "",
      capture_method: noteInput.value.trim() ? "popup-note" : "popup-selection",
    },
  });
  setStatus(response?.posted ? "Captured and sent." : "Captured pending.");
}

async function readSelection(tab) {
  if (!tab?.id) return { text: "", title: "", url: "" };
  try {
    return await chrome.tabs.sendMessage(tab.id, { type: "REALITY_OS_READ_SELECTION" });
  } catch (_) {
    return { text: "", title: tab.title || "", url: tab.url || "" };
  }
}

function setStatus(message) {
  statusNode.textContent = message;
}
