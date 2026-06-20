(() => {
  "use strict";

  const SPEED_STEP = 1.25;
  const MIN_SPEED = 0.1;
  const MAX_SPEED = 16;
  const DEFAULT_FRAME_MS = 100;

  let decoder = null;
  let frameCount = 0;
  let frameIndex = 0;
  let speed = 1;
  let paused = false;
  let timerId = 0;
  let renderToken = 0;
  let canvas = null;
  let context = null;
  let hud = null;

  function directWebpImage() {
    const image = document.querySelector("img");
    if (!image) {
      return null;
    }
    const source = image.currentSrc || image.src || location.href;
    const looksLikeWebp = /\.webp(?:$|[?#])/i.test(source) || document.contentType === "image/webp";
    if (!looksLikeWebp) {
      return null;
    }
    const bodyChildren = Array.from(document.body?.children || []).filter((child) => {
      if (child === image) {
        return true;
      }
      const rect = child.getBoundingClientRect?.();
      return rect && rect.width > 0 && rect.height > 0;
    });
    return bodyChildren.length <= 1 ? image : null;
  }

  async function start() {
    if (window.__webpPlaybackControllerActive) {
      return;
    }
    const image = directWebpImage();
    if (!image) {
      return;
    }
    window.__webpPlaybackControllerActive = true;

    installShell(image);
    if (!("ImageDecoder" in window)) {
      showFatal("ImageDecoder is not available in this browser.");
      return;
    }

    try {
      const source = image.currentSrc || image.src || location.href;
      const { data, type } = await loadWebpBytes(source);
      decoder = new ImageDecoder({ data, type });
      await decoder.tracks.ready;
      const track = decoder.tracks.selectedTrack;
      frameCount = Number(track?.frameCount || 0);
      if (!frameCount || frameCount < 1) {
        frameCount = 1;
      }
      installKeyboardControls();
      await renderFrame(0);
      scheduleNext();
    } catch (error) {
      showFatal(`Could not control this WebP: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  async function loadWebpBytes(source) {
    const errors = [];
    const forceCapture = location.hash.includes("webp-controller-debugger");
    if (!forceCapture) {
      try {
        const response = await fetch(source, { credentials: "include", cache: "force-cache" });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return {
          data: await response.arrayBuffer(),
          type: response.headers.get("content-type") || "image/webp",
        };
      } catch (error) {
        errors.push(`fetch: ${error instanceof Error ? error.message : String(error)}`);
      }

      try {
        return await loadWebpBytesWithXhr(source);
      } catch (error) {
        errors.push(`xhr: ${error instanceof Error ? error.message : String(error)}`);
      }

      try {
        return await loadWebpBytesWithExtension(source);
      } catch (error) {
        errors.push(`extension: ${error instanceof Error ? error.message : String(error)}`);
      }
    } else {
      errors.push("capture test mode");
    }

    try {
      return await loadWebpBytesWithCapture(source);
    } catch (error) {
      errors.push(`capture: ${error instanceof Error ? error.message : String(error)}`);
    }

    try {
      return await loadWebpBytesWithDebugger(source);
    } catch (error) {
      errors.push(`debugger: ${error instanceof Error ? error.message : String(error)}`);
    }

    try {
      await requestCaptureReload(source);
      showFatal("Reloading once so Chrome can capture this local WebP.");
      return await new Promise(() => {});
    } catch (error) {
      errors.push(`capture reload: ${error instanceof Error ? error.message : String(error)}`);
    }

    throw new Error(errors.join("; "));
  }

  function loadWebpBytesWithXhr(source) {
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("GET", source, true);
      request.responseType = "arraybuffer";
      request.onload = () => {
        if (request.status && (request.status < 200 || request.status >= 300)) {
          reject(new Error(`HTTP ${request.status}`));
          return;
        }
        if (!request.response) {
          reject(new Error("empty response"));
          return;
        }
        resolve({
          data: request.response,
          type: request.getResponseHeader("content-type") || "image/webp",
        });
      };
      request.onerror = () => reject(new Error("network error"));
      request.onabort = () => reject(new Error("aborted"));
      request.ontimeout = () => reject(new Error("timed out"));
      request.timeout = 30000;
      request.send();
    });
  }

  async function loadWebpBytesWithExtension(source) {
    if (!globalThis.chrome?.runtime?.sendMessage) {
      throw new Error("extension messaging unavailable");
    }
    const init = await sendExtensionMessage({ type: "webp-load-init", source });
    if (!init.ok) {
      throw new Error(init.error || "background load failed");
    }
    try {
      let base64 = "";
      for (let index = 0; index < Number(init.chunks || 0); index += 1) {
        const response = await sendExtensionMessage({ type: "webp-load-chunk", id: init.id, index });
        if (!response.ok) {
          throw new Error(response.error || `chunk ${index} failed`);
        }
        base64 += response.chunk || "";
      }
      return {
        data: base64ToArrayBuffer(base64, Number(init.size || 0)),
        type: init.type || "image/webp",
      };
    } finally {
      void sendExtensionMessage({ type: "webp-load-release", id: init.id }).catch(() => {});
    }
  }

  async function loadWebpBytesWithDebugger(source) {
    return loadWebpBytesFromBackground({ type: "webp-debugger-load", source });
  }

  async function loadWebpBytesWithCapture(source) {
    return loadWebpBytesFromBackground({ type: "webp-captured-load", source });
  }

  async function requestCaptureReload(source) {
    const response = await sendExtensionMessage({ type: "webp-capture-reload", source });
    if (!response.ok) {
      throw new Error(response.error || "background reload capture failed");
    }
  }

  async function loadWebpBytesFromBackground(message) {
    const init = await sendExtensionMessage(message);
    if (!init.ok) {
      throw new Error(init.error || "background load failed");
    }
    try {
      let base64 = "";
      for (let index = 0; index < Number(init.chunks || 0); index += 1) {
        const response = await sendExtensionMessage({ type: "webp-load-chunk", id: init.id, index });
        if (!response.ok) {
          throw new Error(response.error || `chunk ${index} failed`);
        }
        base64 += response.chunk || "";
      }
      return {
        data: base64ToArrayBuffer(base64, Number(init.size || 0)),
        type: init.type || "image/webp",
      };
    } finally {
      void sendExtensionMessage({ type: "webp-load-release", id: init.id }).catch(() => {});
    }
  }

  function sendExtensionMessage(message) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(message, (response) => {
        const error = chrome.runtime.lastError;
        if (error) {
          reject(new Error(error.message));
          return;
        }
        resolve(response || {});
      });
    });
  }

  function base64ToArrayBuffer(base64, expectedSize) {
    const binary = atob(base64);
    const size = expectedSize > 0 ? expectedSize : binary.length;
    const bytes = new Uint8Array(size);
    for (let index = 0; index < binary.length && index < bytes.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes.buffer;
  }

  function installShell(image) {
    image.style.display = "none";
    document.documentElement.style.background = "#101010";
    document.body.style.margin = "0";
    document.body.style.minHeight = "100vh";
    document.body.style.background = "#101010";
    document.body.style.display = "grid";
    document.body.style.placeItems = "center";
    document.body.style.overflow = "hidden";

    canvas = document.createElement("canvas");
    canvas.id = "webp-controller-canvas";
    canvas.style.maxWidth = "100vw";
    canvas.style.maxHeight = "100vh";
    canvas.style.width = "auto";
    canvas.style.height = "auto";
    canvas.style.display = "block";
    canvas.style.background = "#101010";
    canvas.style.imageRendering = "auto";
    context = canvas.getContext("2d", { alpha: false });

    hud = document.createElement("div");
    hud.id = "webp-controller-hud";
    hud.style.position = "fixed";
    hud.style.left = "12px";
    hud.style.bottom = "12px";
    hud.style.zIndex = "2147483647";
    hud.style.padding = "8px 10px";
    hud.style.borderRadius = "6px";
    hud.style.background = "rgba(0, 0, 0, 0.72)";
    hud.style.color = "#f4f4f4";
    hud.style.font = "13px/1.35 system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    hud.style.whiteSpace = "nowrap";
    hud.style.userSelect = "none";
    hud.style.pointerEvents = "none";

    document.body.append(canvas, hud);
    updateHud();
  }

  function installKeyboardControls() {
    document.addEventListener(
      "keydown",
      (event) => {
        const key = event.key;
        if (key === "+" || key === "=") {
          event.preventDefault();
          speed = Math.min(MAX_SPEED, speed * SPEED_STEP);
          restartTimer();
          updateHud();
          return;
        }
        if (key === "-" || key === "_") {
          event.preventDefault();
          speed = Math.max(MIN_SPEED, speed / SPEED_STEP);
          restartTimer();
          updateHud();
          return;
        }
        if (key === " " || key.toLowerCase() === "p" || key === "Pause") {
          event.preventDefault();
          paused = !paused;
          restartTimer();
          updateHud();
          return;
        }
        if (key.toLowerCase() === "r") {
          event.preventDefault();
          paused = false;
          void renderFrame(0).then(scheduleNext);
          return;
        }
        if (key === "ArrowLeft") {
          event.preventDefault();
          void stepFrame(-1);
          return;
        }
        if (key === "ArrowRight") {
          event.preventDefault();
          void stepFrame(1);
        }
      },
      true,
    );
  }

  async function stepFrame(delta) {
    clearTimer();
    const next = wrapFrame(frameIndex + delta);
    await renderFrame(next);
    if (!paused) {
      scheduleNext();
    }
  }

  async function renderFrame(index) {
    if (!decoder || !context || !canvas) {
      return DEFAULT_FRAME_MS;
    }
    const token = ++renderToken;
    const safeIndex = wrapFrame(index);
    const result = await decoder.decode({ frameIndex: safeIndex, completeFramesOnly: true });
    if (token !== renderToken) {
      result.image.close();
      return DEFAULT_FRAME_MS;
    }

    const image = result.image;
    const width = image.displayWidth || image.codedWidth || image.visibleRect?.width || 1;
    const height = image.displayHeight || image.codedHeight || image.visibleRect?.height || 1;
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    context.drawImage(image, 0, 0, width, height);
    const durationMs = Math.max(20, Math.round((Number(image.duration) || DEFAULT_FRAME_MS * 1000) / 1000));
    image.close();
    frameIndex = safeIndex;
    canvas.dataset.frameIndex = String(frameIndex);
    canvas.dataset.frameCount = String(frameCount);
    canvas.dataset.speed = speed.toFixed(2);
    canvas.dataset.paused = String(paused);
    canvas.dataset.durationMs = String(durationMs);
    updateHud();
    return durationMs;
  }

  function scheduleNext(delayMs = Number(canvas?.dataset.durationMs || DEFAULT_FRAME_MS)) {
    clearTimer();
    if (paused || frameCount <= 1) {
      return;
    }
    const scaledDelay = Math.max(10, Math.round(delayMs / speed));
    timerId = window.setTimeout(async () => {
      const durationMs = await renderFrame(frameIndex + 1);
      scheduleNext(durationMs);
    }, scaledDelay);
  }

  function restartTimer() {
    clearTimer();
    if (!paused) {
      scheduleNext();
    }
  }

  function clearTimer() {
    if (timerId) {
      window.clearTimeout(timerId);
      timerId = 0;
    }
  }

  function wrapFrame(index) {
    if (frameCount <= 0) {
      return 0;
    }
    return ((index % frameCount) + frameCount) % frameCount;
  }

  function updateHud() {
    if (canvas) {
      canvas.dataset.frameIndex = String(frameIndex);
      canvas.dataset.frameCount = String(frameCount);
      canvas.dataset.speed = speed.toFixed(2);
      canvas.dataset.paused = String(paused);
    }
    if (!hud) {
      return;
    }
    const state = paused ? "paused" : "playing";
    hud.textContent = `WebP ${state} | frame ${frameIndex + 1}/${Math.max(frameCount, 1)} | ${speed.toFixed(2)}x | +/- speed | Space/P pause | R restart | <- -> step`;
  }

  function showFatal(message) {
    if (!hud) {
      return;
    }
    hud.textContent = `WebP controller: ${message}`;
    hud.style.background = "rgba(120, 0, 0, 0.82)";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => void start(), { once: true });
  } else {
    void start();
  }
})();
