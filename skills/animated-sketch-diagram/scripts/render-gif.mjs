#!/usr/bin/env node
// 逐帧定格 CSS 动画并合成无缝循环 GIF
// 用法: node render-gif.mjs input.html output.gif [--fps 25] [--loop 3000] [--scale 2]
import { chromium } from 'playwright-core';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { globSync } from 'node:fs';

const args = process.argv.slice(2);
const [input, output] = args;
if (!input || !output) {
  console.error('用法: node render-gif.mjs input.html output.gif [--fps 25] [--loop 3000] [--scale 2]');
  process.exit(1);
}
const opt = (name, dflt) => {
  const i = args.indexOf('--' + name);
  return i > -1 ? Number(args[i + 1]) : dflt;
};
const fps = opt('fps', 25);
const loop = opt('loop', 3000); // ms，须与 HTML 里 --loop 一致
const scale = opt('scale', 2); // 默认 2x 截图：1x 的 GIF 文字发糊

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium-browser',
    ...globSync(join(process.env.HOME || '', 'Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium')),
  ].filter(Boolean);
  const hit = candidates.find(p => existsSync(p));
  if (!hit) throw new Error('找不到 Chrome/Chromium，请设置 CHROME_PATH 环境变量');
  return hit;
}

const frames = Math.round((loop / 1000) * fps);
const dir = mkdtempSync(join(tmpdir(), 'sketch-gif-'));
const browser = await chromium.launch({ executablePath: findChrome() });
try {
  const page = await browser.newPage({ deviceScaleFactor: scale });
  await page.goto('file://' + resolve(input));
  await page.evaluate(() => document.fonts.ready);
  const { w, h } = await page.evaluate(() => {
    const el = document.querySelector('.canvas') || document.body;
    const r = el.getBoundingClientRect();
    return { w: Math.ceil(r.width), h: Math.ceil(r.height) };
  });
  await page.setViewportSize({ width: w, height: h });
  // 暂停所有动画，逐帧 seek。GIF 无缝循环靠"所有时长整除 loop"
  await page.evaluate(() => document.getAnimations().forEach(a => a.pause()));
  for (let i = 0; i < frames; i++) {
    const t = (i / fps) * 1000;
    await page.evaluate(t => document.getAnimations().forEach(a => { a.currentTime = t; }), t);
    await page.screenshot({ path: join(dir, `f${String(i).padStart(3, '0')}.png`) });
    process.stdout.write(`\r帧 ${i + 1}/${frames}`);
  }
  console.log('\nffmpeg 合成中…');
  execFileSync('ffmpeg', [
    '-v', 'error', '-y', '-framerate', String(fps), '-i', join(dir, 'f%03d.png'),
    '-vf', 'split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a',
    '-loop', '0', resolve(output),
  ], { stdio: 'inherit' });
  console.log('完成 →', resolve(output));
} finally {
  await browser.close();
  rmSync(dir, { recursive: true, force: true });
}
