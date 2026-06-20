# WebP Playback Controller

Small unpacked Chrome extension for direct animated WebP pages.

## Install

1. Open `chrome://extensions`.
2. Enable `Developer mode`.
3. Click `Load unpacked`.
4. Select this folder: `tools/chrome-webp-controller`.

If you want to open local `file://` WebPs directly, enable `Allow access to file URLs`
for the extension in `chrome://extensions`. Served `http://localhost/...webp`
files work without that toggle.

For WSL paths opened from Windows Chrome, use the normal unpacked-extension UI
instead of relying on command-line extension loading:

1. Open `chrome://extensions`.
2. Reload `WebP Playback Controller`.
3. Open its Details page.
4. Enable `Allow access to file URLs`.
5. Reopen the WebP, for example
   `file://wsl$/Ubuntu/home/jan/development/ProsperOrPerishConstructor/graphs/savegame_notebooks/exports/absolute/building_levels_current.webp`.

Chrome may briefly show a message that the extension is debugging the browser.
That is expected for WSL/UNC file URLs: Chrome can display those files while
blocking `fetch()`/XHR access from the page, so the extension falls back to
capturing the already-loaded WebP response through Chrome's debugging API.

## Controls

- `+` or `=`: faster
- `-`: slower
- `Space`, `P`, or `Pause`: pause/unpause
- `R`: restart from frame 1 and play
- `Left`: previous frame
- `Right`: next frame

The extension only activates when the current page is a direct `.webp` image.
It replaces Chrome's native animated image view with a canvas so the animation
can be paused, stepped, restarted, and speed-adjusted.

For local files the extension uses background-loader and debugger-capture
fallbacks because Chrome can display `file://` WebPs while blocking direct
content-script reads of the same bytes. If you already loaded the extension
before these fallbacks existed, click the reload icon for the extension in
`chrome://extensions`.

## Test

```bash
node tools/chrome-webp-controller/test_controller.mjs
WEBP_CONTROLLER_TEST_URL="file://$(pwd)/graphs/savegame_notebooks/exports/absolute/building_levels_current.webp" \
  WEBP_CONTROLLER_EXPECTED_FRAMES=2 \
  node tools/chrome-webp-controller/test_controller.mjs
WEBP_CONTROLLER_TEST_URL="file://$(pwd)/graphs/savegame_notebooks/exports/absolute/building_levels_current.webp#webp-controller-debugger" \
  WEBP_CONTROLLER_EXPECTED_FRAMES=2 \
  node tools/chrome-webp-controller/test_controller.mjs
```

The last command forces the Chrome debugger-capture path and is the regression
test for WSL/UNC-style file access failures. Branded Chrome 137+ removed
command-line `--load-extension`, so the automated test uses the bundled
Chromium from Playwright; install/reload the extension manually for normal
Windows Chrome use.
