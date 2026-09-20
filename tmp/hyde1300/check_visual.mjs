import { chromium } from 'file:///C:/Users/Anwender/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const source = process.argv[2];
const outputDir = process.argv[3];
const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe'
});
const results = [];

for (const width of [736, 360]) {
  const page = await browser.newPage({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(pathToFileURL(path.resolve(source)).href, { waitUntil: 'networkidle' });
  await page.waitForTimeout(300);
  const chartCount = await page.locator('svg[role="img"]').count();
  const bodyOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  const clipped = await page.evaluate(() => [...document.querySelectorAll('svg text')].filter(el => {
    const r = el.getBoundingClientRect();
    return r.left < -1 || r.right > document.documentElement.clientWidth + 1;
  }).map(el => el.textContent));
  const screenshot = path.join(outputDir, `hyde-1300-${width}.png`);
  await page.screenshot({ path: screenshot, fullPage: true });
  results.push({ width, chartCount, bodyOverflow, clipped, errors, screenshot });
  await page.close();
}

await browser.close();
console.log(JSON.stringify(results, null, 2));
