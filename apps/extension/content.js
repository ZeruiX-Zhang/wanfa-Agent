chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "REALITY_OS_READ_SELECTION") return false;
  sendResponse({
    text: window.getSelection()?.toString() || "",
    title: document.title || "",
    url: window.location.href,
  });
  return true;
});
