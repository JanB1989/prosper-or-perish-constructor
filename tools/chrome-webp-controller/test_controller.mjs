import { createServer } from "node:http";
import { readFile, rm } from "node:fs/promises";
import { spawn } from "node:child_process";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const extensionDir = process.env.WEBP_CONTROLLER_EXTENSION_DIR || resolve(here);
const testWebp = resolve(here, "test_assets", "animated_test.webp");
const chromePath =
  process.env.CHROME_PATH ||
  "/home/jan/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome";
const debugHost = process.env.WEBP_CONTROLLER_DEBUG_HOST || "127.0.0.1";

function sleep(ms) {
  return new Promise((resolveSleep) => setTimeout(resolveSleep, ms));
}

function chromeExitPromise(chrome, isAllowedExit) {
  return new Promise((_, reject) => {
    chrome.once("exit", (code, signal) => {
      if (isAllowedExit()) {
        return;
      }
      reject(new Error(`Chrome exited before test completed: code=${code ?? "null"} signal=${signal ?? "null"}`));
    });
  });
}

function listen(server) {
  return new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
}

async function startServer() {
  const bytes = await readFile(testWebp);
  const server = createServer((request, response) => {
    if (request.url !== "/animated_test.webp") {
      response.writeHead(404);
      response.end("not found");
      return;
    }
    response.writeHead(200, {
      "content-type": "image/webp",
      "cache-control": "no-store",
      "content-length": String(bytes.length),
    });
    response.end(bytes);
  });
  await listen(server);
  const address = server.address();
  return {
    server,
    url: `http://127.0.0.1:${address.port}/animated_test.webp`,
  };
}

async function waitForJson(url) {
  let lastError = null;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return await response.json();
      }
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await sleep(100);
  }
  throw lastError || new Error(`Timed out waiting for ${url}`);
}

async function newTarget(chromeHost, chromePort, url) {
  const endpoint = `http://${chromeHost}:${chromePort}/json/new?${encodeURIComponent(url)}`;
  let response = await fetch(endpoint, { method: "PUT" });
  if (!response.ok) {
    response = await fetch(endpoint);
  }
  if (!response.ok) {
    throw new Error(`Could not create Chrome target: HTTP ${response.status}`);
  }
  return response.json();
}

function connectCdp(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl);
  let nextId = 1;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) {
      return;
    }
    const { resolve: resolvePending, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) {
      reject(new Error(message.error.message || JSON.stringify(message.error)));
      return;
    }
    resolvePending(message.result || {});
  });
  const opened = new Promise((resolveOpen, rejectOpen) => {
    socket.addEventListener("open", resolveOpen, { once: true });
    socket.addEventListener("error", rejectOpen, { once: true });
  });
  return {
    opened,
    close: () => socket.close(),
    send(method, params = {}) {
      const id = nextId;
      nextId += 1;
      const payload = JSON.stringify({ id, method, params });
      return new Promise((resolveSend, rejectSend) => {
        pending.set(id, { resolve: resolveSend, reject: rejectSend });
        socket.send(payload);
      });
    },
  };
}

async function evaluate(cdp, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || "Runtime.evaluate failed");
  }
  return result.result.value;
}

async function state(cdp) {
  return evaluate(
    cdp,
    `(() => {
      const canvas = document.querySelector("#webp-controller-canvas");
      const hud = document.querySelector("#webp-controller-hud");
      const image = document.querySelector("img");
      return {
        url: location.href,
        contentType: document.contentType,
        imageCount: document.images.length,
        imageSrc: image?.currentSrc || image?.src || "",
        exists: !!canvas,
        frameIndex: Number(canvas?.dataset.frameIndex || 0),
        frameCount: Number(canvas?.dataset.frameCount || 0),
        speed: Number(canvas?.dataset.speed || 0),
        paused: canvas?.dataset.paused === "true",
        hud: hud?.textContent || ""
      };
    })()`,
  );
}

async function waitFor(cdp, predicate, label) {
  let latest = null;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    latest = await state(cdp);
    if (predicate(latest)) {
      return latest;
    }
    await sleep(100);
  }
  throw new Error(`Timed out waiting for ${label}. Latest state: ${JSON.stringify(latest)}`);
}

async function key(cdp, keyName, code = keyName) {
  await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: keyName, code });
  await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: keyName, code });
}

async function main() {
  let server = null;
  let url = process.env.WEBP_CONTROLLER_TEST_URL || "";
  if (!url) {
    const started = await startServer();
    server = started.server;
    url = started.url;
  }
  const expectedFrameCount = Number(process.env.WEBP_CONTROLLER_EXPECTED_FRAMES || 4);
  const explicitProfile = process.env.WEBP_CONTROLLER_USER_DATA_DIR || "";
  const profile = explicitProfile || (await mkdtemp(resolve(tmpdir(), "webp-controller-chrome-")));
  const chromePort = 9400 + Math.floor(Math.random() * 500);
  const chromeArgs = [
    "--no-sandbox",
    "--disable-gpu",
    `--user-data-dir=${profile}`,
    `--remote-debugging-address=${process.env.WEBP_CONTROLLER_DEBUG_BIND || "127.0.0.1"}`,
    `--remote-debugging-port=${chromePort}`,
    `--disable-extensions-except=${extensionDir}`,
    `--load-extension=${extensionDir}`,
    "about:blank",
  ];
  if (process.env.WEBP_CONTROLLER_HEADLESS !== "0") {
    chromeArgs.unshift("--headless=new");
  }
  const chrome = spawn(chromePath, chromeArgs);
  if (process.env.WEBP_CONTROLLER_VERBOSE === "1") {
    chrome.stderr.on("data", (chunk) => process.stderr.write(chunk));
    chrome.stdout.on("data", (chunk) => process.stdout.write(chunk));
  } else {
    chrome.stderr.on("data", () => {});
    chrome.stdout.on("data", () => {});
  }

  let cdp = null;
  let allowChromeExit = false;
  const chromeExitedEarly = chromeExitPromise(chrome, () => allowChromeExit);
  try {
    await Promise.race([waitForJson(`http://${debugHost}:${chromePort}/json/version`), chromeExitedEarly]);
    const target = await newTarget(debugHost, chromePort, url);
    const websocketUrl = target.webSocketDebuggerUrl.replace("://127.0.0.1:", `://${debugHost}:`);
    cdp = connectCdp(websocketUrl);
    await cdp.opened;
    await cdp.send("Runtime.enable");
    await cdp.send("Page.enable");

    const ready = await Promise.race([
      waitFor(cdp, (item) => item.exists && item.frameCount >= expectedFrameCount, "controller canvas"),
      chromeExitedEarly,
    ]);
    if (!ready.hud.includes("WebP")) {
      throw new Error(`HUD did not initialize: ${ready.hud}`);
    }
    if (ready.imageCount !== 0) {
      throw new Error(`Native image was not removed: ${JSON.stringify(ready)}`);
    }

    await key(cdp, " ", "Space");
    const paused = await waitFor(cdp, (item) => item.paused, "paused state");
    const pausedFrame = paused.frameIndex;
    await sleep(350);
    const stillPaused = await state(cdp);
    if (stillPaused.frameIndex !== pausedFrame) {
      throw new Error(`Pause failed: frame changed from ${pausedFrame} to ${stillPaused.frameIndex}`);
    }

    await key(cdp, "ArrowRight", "ArrowRight");
    await waitFor(cdp, (item) => item.paused && item.frameIndex === (pausedFrame + 1) % item.frameCount, "right step");

    await key(cdp, "ArrowLeft", "ArrowLeft");
    await waitFor(cdp, (item) => item.paused && item.frameIndex === pausedFrame, "left step");

    await key(cdp, "=", "Equal");
    const faster = await waitFor(cdp, (item) => item.speed > 1, "faster speed");

    await key(cdp, "-", "Minus");
    await waitFor(cdp, (item) => item.speed < faster.speed, "slower speed");

    await key(cdp, "r", "KeyR");
    await waitFor(cdp, (item) => !item.paused && item.frameIndex === 0, "restart");

    console.log("webp controller test passed");
  } finally {
    if (cdp) {
      cdp.close();
    }
    allowChromeExit = true;
    const chromeExited = new Promise((resolveExit) => {
      chrome.once("exit", resolveExit);
    });
    chrome.kill("SIGTERM");
    await Promise.race([chromeExited, sleep(3000)]);
    if (server) {
      server.close();
    }
    if (!explicitProfile) {
      await rm(profile, { recursive: true, force: true });
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
