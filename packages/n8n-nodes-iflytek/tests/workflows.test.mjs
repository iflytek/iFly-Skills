import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const require = createRequire(import.meta.url);
const { PythonRunner } = require('../dist/shared/PythonRunner.js');
const { IflyAnimatedSketch } = require('../dist/nodes/IflyAnimatedSketch/IflyAnimatedSketch.node.js');
const { IflyContractReview } = require('../dist/nodes/IflyContractReview/IflyContractReview.node.js');
const pkg = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pythonExecutable = process.env.IFLY_TEST_PYTHON
  || spawnSync('python', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' }).stdout?.trim();
assert.ok(pythonExecutable && path.isAbsolute(pythonExecutable));
const renderConfig = {
  pythonExecutable, chromeExecutable: process.env.IFLY_TEST_CHROME, ffmpegExecutable: process.env.IFLY_TEST_FFMPEG,
};
const canRender = Boolean(renderConfig.chromeExecutable && renderConfig.ffmpegExecutable);
const consume = async (result, files) => ({ result, files });
const renderRequest = {
  skill: 'animated-sketch-diagram', operation: 'renderHtmlToGif',
  input: { text: '<div>hello</div>' }, parameters: {},
};

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'ifly-workflow-test-'));
  const temporaryRoot = path.join(root, 'invocations');
  await mkdir(temporaryRoot);
  t.after(async () => {
    try { assert.deepEqual(await readdir(temporaryRoot), [], 'Invocation files must be removed'); }
    finally { await rm(root, { recursive: true, force: true, maxRetries: 3 }); }
  });
  return { root, temporaryRoot };
}

test('actual contract clients, orchestration, reports and restricted HTML validation pass offline', () => {
  const output = spawnSync(pythonExecutable, ['-I', '-B', '-X', 'utf8',
    path.join(pkg, 'tests/fixtures/workflows.py'), path.join(pkg, 'runtime')],
  { encoding: 'utf8', timeout: 60000 });
  assert.equal(output.status, 0, output.stdout + output.stderr);
  assert.match(output.stderr, /Ran 10 tests/);
});

test('contract requires shared credentials before executing', async (t) => {
  const f = await fixture(t);
  await assert.rejects(new PythonRunner({ pythonExecutable, temporaryRoot: f.temporaryRoot }).run({
    skill: 'iflytek-contract-intelligence-review', operation: 'review', input: { text: 'contract' },
  }, consume), { code: 'AUTH_FAILED' });
});

test('renderer gets only fixed administrator runtime paths and no API credentials', async (t) => {
  const f = await fixture(t);
  const runtimeRoot = path.join(f.root, 'runtime');
  await mkdir(path.join(runtimeRoot, 'bridge'), { recursive: true });
  await writeFile(path.join(runtimeRoot, 'bridge/operations.json'), JSON.stringify({ protocolVersion: 1,
    operations: [{ skill: renderRequest.skill, operation: renderRequest.operation, credentials: [], artifactMimeTypes: [] }] }));
  await writeFile(path.join(runtimeRoot, 'bridge/bridge.py'), `import json, os, sys
r = json.load(sys.stdin)
assert not any(k.startswith(('IFLY_', 'XFEI_', 'XFYUN_')) for k in os.environ)
assert 'NODE_OPTIONS' not in os.environ and 'PYTHONPATH' not in os.environ
print(json.dumps({'protocolVersion': 1, 'requestId': r['requestId'], 'ok': True,
 'status': 'succeeded', 'data': {k: os.environ[k] for k in
 ['IFLYTEK_NODE_EXECUTABLE', 'IFLYTEK_CHROME_EXECUTABLE', 'IFLYTEK_FFMPEG_EXECUTABLE']},
 'artifacts': [], 'meta': {'durationMs': 0}}))
`);
  const config = { pythonExecutable, runtimeRoot, temporaryRoot: f.temporaryRoot,
    chromeExecutable: process.execPath, ffmpegExecutable: process.execPath };
  const result = await new PythonRunner(config).run({
    ...renderRequest, credentials: { appId: 'unused', apiKey: 'unused', apiSecret: 'unused' },
  }, consume);
  assert.deepEqual(Object.values(result.result.data), [process.execPath, process.execPath, process.execPath]);
  await assert.rejects(new PythonRunner({ ...config, chromeExecutable: 'relative' }).run(renderRequest, consume),
    { code: 'INVALID_INPUT' });
});

test('restricted renderer rejects unsafe input and missing runtime dependencies cleanly', async (t) => {
  const f = await fixture(t);
  const runner = new PythonRunner({ pythonExecutable, temporaryRoot: f.temporaryRoot,
    chromeExecutable: path.join(f.root, 'missing-chrome'), ffmpegExecutable: path.join(f.root, 'missing-ffmpeg') });
  await assert.rejects(runner.run({ ...renderRequest, input: { text: '<script>fetch("http://localhost")</script>' } }, consume),
    { code: 'INVALID_INPUT' });
  await assert.rejects(runner.run(renderRequest, consume), { code: 'DEPENDENCY_MISSING' });
  await assert.rejects(runner.run({ ...renderRequest, parameters: { fps: 26 } }, consume), { code: 'INVALID_INPUT' });
});

test('real Python to Node to Chromium to ffmpeg produces a decoded animated GIF', { skip: !canRender }, async (t) => {
  const f = await fixture(t);
  const runner = new PythonRunner({ ...renderConfig, temporaryRoot: f.temporaryRoot, timeoutMs: 60000 });
  const html = await readFile(path.join(pkg, 'runtime/bridge/diagram/workflow.html'), 'utf8');
  const output = await runner.run({ ...renderRequest, input: { text: html },
    parameters: { fps: 4, durationMs: 2000 } }, consume);
  assert.equal(output.files.length, 1);
  assert.equal(output.files[0].mimeType, 'image/gif');
  assert.equal(output.files[0].fileName, 'diagram.gif');
  assert.deepEqual(output.result.data, { width: 800, height: 500, frames: 8, fps: 4 });
  const decoded = spawnSync(pythonExecutable, ['-I', '-B', '-c', `import io, sys
from PIL import Image
im = Image.open(io.BytesIO(sys.stdin.buffer.read()))
assert im.size == (800, 500)
assert im.n_frames == 8
first = im.convert('RGB')
assert first.getpixel((0, 0)) == (248, 241, 227)
assert first.getpixel((60, 230)) != first.getpixel((0, 0))
im.seek(1)
assert first.tobytes() != im.convert('RGB').tobytes()
`], { input: output.files[0].data, timeout: 10000 });
  assert.equal(decoded.status, 0, decoded.stderr.toString());
});

test('real render cancellation stops the invocation and removes browser/frame files', { skip: !canRender }, async (t) => {
  const f = await fixture(t);
  const controller = new AbortController();
  const runner = new PythonRunner({ ...renderConfig, temporaryRoot: f.temporaryRoot, timeoutMs: 60000 });
  const pending = runner.run({ ...renderRequest, parameters: { fps: 25, durationMs: 5000 }, signal: controller.signal }, consume);
  const timer = setTimeout(() => controller.abort(), 1500);
  try { await assert.rejects(pending, { code: 'EXECUTION_CANCELLED' }); }
  finally { clearTimeout(timer); }
});

test('node execution maps credential-free GIF binary, item pairing and errors', { skip: !canRender }, async (t) => {
  const f = await fixture(t);
  const env = {
    IFLYTEK_PYTHON_EXECUTABLE: pythonExecutable, IFLYTEK_CHROME_EXECUTABLE: renderConfig.chromeExecutable,
    IFLYTEK_FFMPEG_EXECUTABLE: renderConfig.ffmpegExecutable, IFLYTEK_TMP_ROOT: f.temporaryRoot,
  };
  const before = Object.fromEntries(Object.keys(env).map(key => [key, process.env[key]]));
  Object.assign(process.env, env);
  t.after(() => { for (const [key, value] of Object.entries(before)) {
    if (value === undefined) delete process.env[key]; else process.env[key] = value;
  } });
  let persisted = false;
  const context = {
    getNode: () => ({ name: 'render', type: 'iflyAnimatedSketch', typeVersion: 1, position: [0, 0], parameters: {} }),
    getInputData: () => [{ json: {} }], getExecutionCancelSignal: () => undefined,
    getNodeParameter: (name, index, fallback) => ({
      text: '<div style="color: #222">Diagram</div>', width: 160, height: 120, fps: 1, durationMs: 1000,
    })[name] ?? fallback,
    getCredentials: () => { throw new Error('Renderer must not request credentials'); },
    continueOnFail: () => false,
    helpers: {
      prepareBinaryData: async (data, fileName, mimeType) => {
        assert.match(data.subarray(0, 6).toString(), /^GIF8[79]a$/);
        assert.ok((await readdir(f.temporaryRoot)).length > 0, 'Persist before cleanup');
        persisted = true;
        return { data: data.toString('base64'), fileName, mimeType };
      },
    },
  };
  const [[item]] = await new IflyAnimatedSketch().execute.call(context);
  assert.ok(persisted);
  assert.equal(item.binary.image.mimeType, 'image/gif');
  assert.deepEqual(item.pairedItem, { item: 0 });
  assert.deepEqual(await readdir(f.temporaryRoot), []);
  context.continueOnFail = () => true;
  const [[error]] = await new IflyContractReview().execute.call(context);
  assert.match(error.json.error, /AUTH_FAILED/);
  assert.deepEqual(error.pairedItem, { item: 0 });
});
