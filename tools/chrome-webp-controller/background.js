"use strict";

const CHUNK_SIZE = 900_000;
const payloads = new Map();
const tabCaptures = new Map();
const requestCaptures = new Map();

chrome.webNavigation.onBeforeNavigate.addListener((details) => {
  if (details.frameId !== 0 || !isWebpUrl(details.url)) {
    return;
  }
  void startTabCapture(details.tabId, details.url);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") {
    return false;
  }
  if (message.type === "webp-load-init") {
    void loadPayload(String(message.source || ""))
      .then((payload) => sendResponse(payload))
      .catch((error) => sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }));
    return true;
  }
  if (message.type === "webp-debugger-load") {
    void loadPayloadFromDebugger(String(message.source || ""), sender.tab?.id)
      .then((payload) => sendResponse(payload))
      .catch((error) => sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }));
    return true;
  }
  if (message.type === "webp-captured-load") {
    void loadPayloadFromCapture(String(message.source || ""), sender.tab?.id)
      .then((payload) => sendResponse(payload))
      .catch((error) => sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }));
    return true;
  }
  if (message.type === "webp-capture-reload") {
    void requestCaptureReload(String(message.source || ""), sender.tab?.id)
      .then((payload) => sendResponse(payload))
      .catch((error) => sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }));
    return true;
  }
  if (message.type === "webp-load-chunk") {
    const payload = payloads.get(String(message.id || ""));
    if (!payload) {
      sendResponse({ ok: false, error: "payload not found" });
      return false;
    }
    const index = Number(message.index || 0);
    const start = index * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, payload.base64.length);
    sendResponse({ ok: true, chunk: payload.base64.slice(start, end) });
    return false;
  }
  if (message.type === "webp-load-release") {
    payloads.delete(String(message.id || ""));
    sendResponse({ ok: true });
    return false;
  }
  return false;
});

chrome.debugger.onEvent.addListener((source, method, params) => {
  if (!source.tabId || !tabCaptures.has(source.tabId)) {
    return;
  }
  if (method === "Network.responseReceived") {
    const url = String(params?.response?.url || "");
    const mimeType = String(params?.response?.mimeType || "");
    if (isWebpUrl(url) || mimeType.includes("image/webp")) {
      requestCaptures.set(params.requestId, { tabId: source.tabId, url, mimeType });
    }
    return;
  }
  if (method === "Network.loadingFinished" && requestCaptures.has(params.requestId)) {
    const request = requestCaptures.get(params.requestId);
    requestCaptures.delete(params.requestId);
    void finishTabCapture(source.tabId, params.requestId, request);
  }
});

chrome.debugger.onDetach.addListener((source) => {
  if (!source.tabId) {
    return;
  }
  const capture = tabCaptures.get(source.tabId);
  if (capture) {
    capture.attached = false;
  }
});

async function loadPayload(source) {
  if (!source) {
    throw new Error("missing source URL");
  }
  const response = await fetch(source, { cache: "force-cache" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = await response.arrayBuffer();
  const base64 = arrayBufferToBase64(data);
  const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const type = response.headers.get("content-type") || "image/webp";
  payloads.set(id, { base64, type });
  return {
    ok: true,
    id,
    type,
    size: data.byteLength,
    chunks: Math.ceil(base64.length / CHUNK_SIZE),
  };
}

async function startTabCapture(tabId, url) {
  const existing = tabCaptures.get(tabId);
  if (!tabId || existing?.attached || existing?.payload) {
    return;
  }
  const target = { tabId };
  const capture = { target, sourceUrl: url, attached: false, payload: null, waiting: [], reloadStarted: false };
  tabCaptures.set(tabId, capture);
  try {
    await debuggerAttach(target);
    capture.attached = true;
    await debuggerCommand(target, "Network.enable", { maxResourceBufferSize: 100_000_000, maxTotalBufferSize: 100_000_000 });
  } catch (error) {
    capture.error = error instanceof Error ? error.message : String(error);
    resolveCaptureWaiters(tabId);
  }
}

async function requestCaptureReload(source, tabId) {
  if (!tabId) {
    throw new Error("missing tab id");
  }
  let capture = tabCaptures.get(tabId);
  if (capture?.payload && (!source || isSameWebpUrl(capture.payload.url, source))) {
    return { ok: true, captured: true };
  }
  if (capture?.reloadStarted) {
    throw new Error(capture.error || "capture reload already attempted");
  }
  if (!capture?.attached) {
    await startTabCapture(tabId, source);
    capture = tabCaptures.get(tabId);
  }
  if (!capture?.attached) {
    throw new Error(capture?.error || "could not attach debugger before reload");
  }
  capture.reloadStarted = true;
  capture.error = null;
  await tabsReload(tabId);
  return { ok: true, reloading: true };
}

async function finishTabCapture(tabId, requestId, request) {
  const capture = tabCaptures.get(tabId);
  if (!capture) {
    return;
  }
  try {
    const body = await debuggerCommand(capture.target, "Network.getResponseBody", { requestId });
    const base64 = body.base64Encoded ? body.body : textToBase64(body.body || "");
    capture.payload = {
      base64,
      type: request.mimeType || "image/webp",
      url: request.url,
    };
  } catch (error) {
    capture.error = error instanceof Error ? error.message : String(error);
  } finally {
    await debuggerDetach(capture.target).catch(() => {});
    capture.attached = false;
    resolveCaptureWaiters(tabId);
  }
}

async function loadPayloadFromCapture(source, tabId) {
  if (!tabId) {
    throw new Error("missing tab id");
  }
  let capture = tabCaptures.get(tabId);
  if (!capture) {
    await startTabCapture(tabId, source);
    capture = tabCaptures.get(tabId);
  }
  if (!capture) {
    throw new Error("capture unavailable");
  }
  if (!capture.payload && !capture.error) {
    await waitForCapture(tabId, 8000);
  }
  if (capture.payload && (!source || isSameWebpUrl(capture.payload.url, source))) {
    return storeBase64Payload(capture.payload.base64, capture.payload.type);
  }
  throw new Error(capture.error || "capture did not find this WebP");
}

function waitForCapture(tabId, timeoutMs) {
  const capture = tabCaptures.get(tabId);
  if (!capture) {
    return Promise.reject(new Error("capture unavailable"));
  }
  return new Promise((resolve) => {
    const timeout = setTimeout(resolve, timeoutMs);
    capture.waiting.push(() => {
      clearTimeout(timeout);
      resolve();
    });
  });
}

function resolveCaptureWaiters(tabId) {
  const capture = tabCaptures.get(tabId);
  if (!capture) {
    return;
  }
  const waiters = capture.waiting.splice(0);
  for (const waiter of waiters) {
    waiter();
  }
}

async function loadPayloadFromDebugger(source, tabId) {
  if (!tabId) {
    throw new Error("missing tab id");
  }
  const target = { tabId };
  let attached = false;
  try {
    await debuggerAttach(target);
    attached = true;
    await debuggerCommand(target, "Page.enable");
    const tree = await debuggerCommand(target, "Page.getResourceTree");
    const urls = resourceUrls(tree?.frameTree);
    const candidates = [...new Set([source, decodeURI(source), ...urls.filter((url) => isSameWebpUrl(url, source))])];
    let lastError = null;
    for (const url of candidates) {
      try {
        const content = await debuggerCommand(target, "Page.getResourceContent", {
          frameId: tree.frameTree.frame.id,
          url,
        });
        const base64 = content.base64Encoded ? content.content : textToBase64(content.content || "");
        return storeBase64Payload(base64, "image/webp");
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError || new Error("resource not found in page tree");
  } finally {
    if (attached) {
      await debuggerDetach(target).catch(() => {});
    }
  }
}

function resourceUrls(frameTree) {
  if (!frameTree) {
    return [];
  }
  const own = [
    frameTree.frame?.url,
    ...(frameTree.resources || []).map((resource) => resource.url),
  ].filter(Boolean);
  const children = (frameTree.childFrames || []).flatMap(resourceUrls);
  return [...own, ...children];
}

function isSameWebpUrl(left, right) {
  return normalizeUrl(left) === normalizeUrl(right) || /\.webp(?:$|[?#])/i.test(left);
}

function isWebpUrl(url) {
  return /\.webp(?:$|[?#])/i.test(String(url || ""));
}

function normalizeUrl(value) {
  try {
    return decodeURI(String(value || "")).replace(/\/+$/g, "");
  } catch {
    return String(value || "").replace(/\/+$/g, "");
  }
}

function debuggerAttach(target) {
  return new Promise((resolve, reject) => {
    chrome.debugger.attach(target, "1.3", () => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve();
    });
  });
}

function debuggerDetach(target) {
  return new Promise((resolve, reject) => {
    chrome.debugger.detach(target, () => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve();
    });
  });
}

function debuggerCommand(target, method, params = {}) {
  return new Promise((resolve, reject) => {
    chrome.debugger.sendCommand(target, method, params, (result) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(result || {});
    });
  });
}

function tabsReload(tabId) {
  return new Promise((resolve, reject) => {
    chrome.tabs.reload(tabId, {}, () => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve();
    });
  });
}

function storeBase64Payload(base64, type) {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  payloads.set(id, { base64, type });
  return {
    ok: true,
    id,
    type,
    size: Math.floor((base64.length * 3) / 4),
    chunks: Math.ceil(base64.length / CHUNK_SIZE),
  };
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let output = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    const slice = bytes.subarray(offset, Math.min(offset + 0x8000, bytes.length));
    output += String.fromCharCode(...slice);
  }
  return btoa(output);
}

function textToBase64(text) {
  return btoa(unescape(encodeURIComponent(text)));
}
