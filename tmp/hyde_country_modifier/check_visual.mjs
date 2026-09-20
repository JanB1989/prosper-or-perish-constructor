import { chromium } from 'file:///C:/Users/Anwender/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const source = process.argv[2], outputDir = process.argv[3];
const browser = await chromium.launch({headless:true, executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
const results=[];
for (const width of [1024,736,360]) {
  const page=await browser.newPage({viewport:{width,height:950},deviceScaleFactor:1});
  const errors=[]; page.on('pageerror',e=>errors.push(String(e))); page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.goto(pathToFileURL(path.resolve(source)).href,{waitUntil:'networkidle'}); await page.waitForTimeout(800);
  const result=await page.evaluate(()=>({canvases:[...document.querySelectorAll('canvas')].map(x=>[x.width,x.height]),overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth,title:document.querySelector('h1')?.textContent}));
  const screenshot=path.join(outputDir,`hyde-country-factor-${width}.png`); await page.screenshot({path:screenshot,fullPage:true});
  results.push({width,...result,errors,screenshot}); await page.close();
}
await browser.close(); console.log(JSON.stringify(results,null,2));
