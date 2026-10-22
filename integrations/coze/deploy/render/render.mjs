// Adapted from animated-sketch-diagram's CSS frame / ffmpeg sequence.
// This entry point runs only in the restricted container, without host mounts.
import { chromium } from 'playwright-core';
import { readFileSync, mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

const raw = readFileSync(0);
if (raw.length > 1024 * 1024) throw new Error('Input limit exceeded');
const { html, width, height, fps, loop_ms, scale } = JSON.parse(raw);
for (const [n, min, max] of [[width,64,1600],[height,64,1200],[fps,1,25],[loop_ms,100,5000],[scale,1,2]]) {
  if (!Number.isSafeInteger(n) || n < min || n > max) throw new Error('Invalid options');
}
const frames = Math.ceil(loop_ms * fps / 1000);
if (typeof html !== 'string' || Buffer.byteLength(html) > 262144 || frames * width * height * scale * scale > 120000000) {
  throw new Error('Render budget exceeded');
}
const directory = mkdtempSync('/tmp/coze-render-');
let browser;
try {
  // OS isolation is supplied by the mandatory networkless, non-root container.
  browser = await chromium.launch({ executablePath: '/usr/bin/chromium', timeout: 15000,
    chromiumSandbox: false, args: ['--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: scale,
    javaScriptEnabled: false, serviceWorkers: 'block', acceptDownloads: false });
  const font = readFileSync('/opt/render/Kalam-400.woff2').toString('base64');
  const style = `<style>@font-face{font-family:Kalam;src:url(data:font/woff2;base64,${font})}</style>`;
  const origin = 'https://coze-render.invalid/';
  await page.context().route('**/*', route => route.request().url() === origin && route.request().isNavigationRequest()
    ? route.fulfill({ contentType: 'text/html; charset=utf-8', body: style + html, headers: {
      'Content-Security-Policy': "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; font-src data:; frame-src 'none'; connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'",
    } }) : route.abort());
  await page.goto(origin, { waitUntil: 'load', timeout: 15000 });
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => document.getAnimations().forEach(animation => animation.pause()));
  for (let index = 0; index < frames; index++) {
    await page.evaluate(time => document.getAnimations().forEach(animation => { animation.currentTime = time; }), index / fps * 1000);
    await page.screenshot({ path: join(directory, `f${String(index).padStart(3, '0')}.png`), timeout: 15000 });
  }
  const output = join(directory, 'diagram.gif');
  execFileSync('/usr/bin/ffmpeg', ['-v','error','-y','-threads','1','-filter_threads','1','-filter_complex_threads','1',
    '-framerate',String(fps),'-i',join(directory,'f%03d.png'),
    '-vf','split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a','-loop','0',output],
    { timeout: 30000, stdio: ['ignore', 'ignore', 'inherit'] });
  const gif = readFileSync(output);
  if (gif.length > 32 * 1024 * 1024) throw new Error('Output limit exceeded');
  process.stdout.write(gif);
} finally {
  try { await browser?.close(); }
  finally { rmSync(directory, { recursive: true, force: true }); }
}
