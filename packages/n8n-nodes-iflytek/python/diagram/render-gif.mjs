// Package-owned adaptation of the Skill's CSS-frame/ffmpeg rendering sequence.
// The original CLI has no importable entry point. See licenses/animated-sketch-diagram-MIT.txt.
import { chromium } from 'playwright-core';
import { mkdtempSync, readFileSync, rmSync, statSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';

const [input, output, ...args] = process.argv.slice(2);
const option = (key, fallback) => args.includes('--' + key) ? Number(args[args.indexOf('--' + key) + 1]) : fallback;
try {
  const width = option('width', 800), height = option('height', 500), scale = option('scale', 1);
  const fps = option('fps', 10), duration = option('loop', 2000);
  for (const [value, min, max] of [[width, 64, 1600], [height, 64, 1200], [scale, 1, 2], [fps, 1, 25], [duration, 100, 5000]]) {
    if (!Number.isSafeInteger(value) || value < min || value > max) throw new Error('Invalid rendering options');
  }
  const frames = Math.ceil(duration * fps / 1000);
  if (frames * width * height * scale * scale > 120_000_000) throw new Error('Render budget exceeded');
  const chrome = process.env.IFLYTEK_CHROME_EXECUTABLE, ffmpeg = process.env.IFLYTEK_FFMPEG_EXECUTABLE;
  if ([chrome, ffmpeg].some(p => !p || !isAbsolute(p) || !statSync(p).isFile())) throw new Error('Missing runtime');
  if (statSync(input).size > 256 * 1024) throw new Error('HTML exceeds size limit');
  const font = readFileSync(new URL('../../skills/animated-sketch-diagram/assets/fonts/Kalam-400.woff2', import.meta.url)).toString('base64');
  const fontStyle = "<style>@font-face{font-family:Kalam;src:url(data:font/woff2;base64," + font + ") format('woff2');font-weight:400;}</style>";
  let html = readFileSync(input, 'utf8');
  html = /<head(?:\s[^>]*)?>/i.test(html)
    ? html.replace(/<head(?:\s[^>]*)?>/i, match => match + fontStyle)
    : '<!doctype html><html><head>' + fontStyle + '</head><body>' + html + '</body></html>';
  const directory = mkdtempSync(join(tmpdir(), 'sketch-gif-'));
  let browser;
  try {
    browser = await chromium.launch({ executablePath: chrome, chromiumSandbox: true, timeout: 15000 });
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: scale,
      javaScriptEnabled: false, serviceWorkers: 'block', acceptDownloads: false });
    page.setDefaultTimeout(15000);
    const origin = 'https://ifly-diagram.invalid/';
    await page.context().route('**/*', route => route.request().url() === origin && route.request().isNavigationRequest()
      ? route.fulfill({ contentType: 'text/html; charset=utf-8', body: html, headers: {
        'Content-Security-Policy': "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; font-src data:; frame-src 'none'; connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'",
      } }) : route.abort());
    await page.goto(origin, { waitUntil: 'load', timeout: 15000 });
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => document.getAnimations().forEach(animation => animation.pause()));
    for (let index = 0; index < frames; index++) {
      await page.evaluate(time => document.getAnimations().forEach(animation => { animation.currentTime = time; }), index / fps * 1000);
      await page.screenshot({ path: join(directory, `f${String(index).padStart(3, '0')}.png`), timeout: 15000 });
    }
    execFileSync(ffmpeg, [
      '-v', 'error', '-y', '-framerate', String(fps), '-i', join(directory, 'f%03d.png'),
      '-vf', 'split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a',
      '-loop', '0', resolve(output),
    ], { stdio: 'ignore', timeout: 30000, windowsHide: true });
  } finally {
    try { await browser?.close(); }
    finally { rmSync(directory, { recursive: true, force: true }); }
  }
} catch {
  console.error('GIF rendering failed; check input, runtime paths and resource limits.');
  process.exitCode = 1;
}
