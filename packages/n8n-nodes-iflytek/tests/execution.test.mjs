import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { mkdtemp, mkdir, cp, readFile, readdir, writeFile, rm, symlink, realpath } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const { PythonRunner } = require('../dist/shared/PythonRunner.js');
const { executeSkill } = require('../dist/shared/executeSkill.js');
const { InvocationDirectory } = require('../dist/shared/binaryFiles.js');
const { acquire } = require('../dist/shared/processControl.js');
const { ExecutionError } = require('../dist/shared/errors.js');
const { credentialEnvironment } = require('../dist/shared/credentialEnv.js');
const pkg = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const discovered = process.env.IFLY_TEST_PYTHON || spawnSync('python', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' }).stdout?.trim();
assert.ok(discovered && path.isAbsolute(discovered), 'Set IFLY_TEST_PYTHON to an absolute Python path with the core dependencies installed.');
const pythonExecutable = discovered;
const skill = 'iflytek-hyper-tts';
const operation = 'listVoices';
const consume = async (result, files) => ({ result, files });
const errorCode = (code) => (error) => {
  assert.equal(error.code, code);
  assert.equal(error.retryable, false);
  assert.ok(!JSON.stringify(error).includes('secret-do-not-forward'));
  assert.ok(!error.message.includes('secret-do-not-forward'));
  return true;
};

async function fixture(t, credentials = []) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'ifly-layer-test-'));
  t.after(async () => {
    // Only this test's mkdtemp path is recursively deleted.
    assert.equal(path.dirname(await realpath(root)), await realpath(os.tmpdir()));
    try { assert.deepEqual(await readdir(path.join(root, 'invocations')), [], 'Invocation directories must be removed'); }
    finally { await rm(root, { recursive: true, force: true, maxRetries: 3 }); }
  });
  const runtimeRoot = path.join(root, 'runtime');
  const temporaryRoot = path.join(root, 'invocations');
  await mkdir(path.join(runtimeRoot, 'bridge'), { recursive: true });
  await mkdir(temporaryRoot);
  await cp(path.join(pkg, 'tests/fixtures/process.py'), path.join(runtimeRoot, 'bridge/bridge.py'));
  await writeFile(path.join(runtimeRoot, 'bridge/operations.json'), JSON.stringify({ protocolVersion: 1,
    operations: [{ skill, operation, credentials, artifactMimeTypes: ['text/plain'] }] }));
  const config = { pythonExecutable, runtimeRoot, temporaryRoot, timeoutMs: 5000 };
  return { root, config, runner: new PythonRunner(config) };
}
const request = (mode, extra = {}) => ({ skill, operation, parameters: { mode }, ...extra });

test('packaged listVoices reads local voice constants without credentials', async (t) => {
  const f = await fixture(t);
  const runner = new PythonRunner({ ...f.config, runtimeRoot: path.join(pkg, 'runtime') });
  const output = await runner.run({ skill, operation }, consume);
  assert.ok(output.result.data.voices.length > 0);
  assert.ok(output.result.data.freeVoices.length > 0);
  assert.equal(output.files.length, 0);
  assert.equal(output.result.ok, true);
  assert.equal(Object.hasOwn(output.result, 'artifacts'), false);
  await assert.rejects(runner.run({ skill, operation, input: { unexpected: true } }, consume), errorCode('INVALID_INPUT'));
  await assert.rejects(runner.run({ skill, operation: 'synthesize' }, consume), errorCode('UNSUPPORTED_OPERATION'));
});

test('UTF-8 chunks, queued results and output envelopes are handled correctly', async (t) => {
  const { runner } = await fixture(t);
  const { result } = await runner.run(request('split_utf8'), consume);
  assert.equal(result.data.text, 'hello 你好 🎙');
  assert.match(result.requestId, /^[a-f0-9-]{36}$/);
  const queued = await runner.run(request('queued'), consume);
  assert.equal(queued.result.status, 'queued');
  assert.equal(queued.result.data.taskId, 'task-123');
});

test('protocol and exit failures are sanitized and never retried', async (t) => {
  const { runner } = await fixture(t);
  for (const [mode, code] of [
    ['malformed', 'INVALID_PROTOCOL'], ['wrong_id', 'INVALID_PROTOCOL'], ['wrong_version', 'INVALID_PROTOCOL'],
    ['false_zero', 'INVALID_PROTOCOL'], ['invalid_utf8', 'INVALID_PROTOCOL'], ['exit', 'PROCESS_EXIT'],
    ['business_error', 'UPSTREAM_ERROR'], ['success_nonzero', 'PROCESS_EXIT'],
  ]) await assert.rejects(runner.run(request(mode), consume), errorCode(code));
});

test('missing executables, missing runtime and early stdin close fail cleanly', async (t) => {
  const f = await fixture(t, ['apiKey']);
  await assert.rejects(new PythonRunner({ ...f.config, pythonExecutable: path.join(f.root, 'missing.exe') })
    .run(request('success', { credentials: { apiKey: 'dummy' } }), consume), errorCode('PYTHON_NOT_FOUND'));
  await assert.rejects(new PythonRunner({ ...f.config, runtimeRoot: f.root })
    .run(request('success'), consume), errorCode('RUNTIME_MISSING'));
  await assert.rejects(f.runner.run(request('success', {
    credentials: { apiKey: 'early-exit' }, input: { text: 'x'.repeat(900000) },
  }), consume), (error) => ['PROCESS_IO', 'PROCESS_EXIT'].includes(error.code));
});

test('per-invocation credential namespaces are isolated from the host and each other', async (t) => {
  const { runner } = await fixture(t, ['appId', 'apiKey', 'apiSecret']);
  const names = ['IFLY_API_KEY', 'XFEI_API_KEY', 'XFYUN_API_SECRET', 'PYTHONPATH', 'NODE_OPTIONS', 'N8N_ENCRYPTION_KEY'];
  const before = Object.fromEntries(names.map((name) => [name, process.env[name]]));
  t.after(() => { for (const name of names) { if (before[name] === undefined) delete process.env[name]; else process.env[name] = before[name]; } });
  for (const name of names) process.env[name] = 'ambient-secret';
  const credentials = (id) => ({ appId: `app-${id}`, apiKey: `key-${id}`, apiSecret: `secret-${id}` });
  const outputs = await Promise.all([1, 2, 3].map((id) => runner.run(request('environment', { credentials: credentials(id) }), consume)));
  for (const [index, output] of outputs.entries()) {
    assert.equal(output.result.data.IFLY_API_KEY, `key-${index + 1}`);
    for (const name of names.filter((name) => name !== 'IFLY_API_KEY')) assert.equal(output.result.data[name], null);
  }
  assert.equal(process.env.IFLY_API_KEY, 'ambient-secret');
  assert.equal(credentialEnvironment([], credentials(1)).IFLY_API_KEY, undefined);
  assert.equal(credentialEnvironment(['apiKey'], credentials(1)).IFLY_APP_ID, undefined);
  await assert.rejects(runner.run(request('environment', { credentials: { apiKey: 'partial' } }), consume), errorCode('AUTH_FAILED'));
});

test('binary round trip uses n8n helpers and preserves pairedItem', async (t) => {
  const { runner, config } = await fixture(t);
  let persisted = false;
  const context = {
    getExecutionCancelSignal: () => undefined,
    getNode: () => ({ name: 'test', type: 'test', typeVersion: 1, position: [0, 0], parameters: {} }),
    getCredentials: () => { throw new Error('No credentials should be requested'); },
    helpers: {
      getBinaryDataBuffer: async (index, property) => { assert.equal(index, 3); assert.equal(property, 'source'); return Buffer.from('input bytes'); },
      prepareBinaryData: async (data, name, mime) => {
        assert.equal(data.toString(), 'input bytes'); assert.equal(name, 'result.txt'); assert.equal(mime, 'text/plain');
        assert.equal((await readdir(config.temporaryRoot)).length, 1, 'Persist before cleanup');
        persisted = true;
        return { data: 'stored-in-n8n', mimeType: mime, fileName: name };
      },
    },
  };
  const output = await executeSkill(context, runner, 3, {
    skill, operation, parameters: { mode: 'artifact' }, binaryInputs: { document: 'source' },
  });
  assert.ok(persisted);
  assert.deepEqual(output.pairedItem, { item: 3 });
  assert.equal(output.binary.data.data, 'stored-in-n8n');
  assert.ok(!JSON.stringify(output).includes('relativePath'));
  assert.deepEqual(await readdir(config.temporaryRoot), []);
  context.helpers.prepareBinaryData = async () => { throw new Error('secret-do-not-forward'); };
  await assert.rejects(executeSkill(context, runner, 3, { skill, operation, parameters: { mode: 'artifact' } }),
    (error) => error.message.includes('BINARY_IO') && error.context.itemIndex === 3 && !JSON.stringify(error).includes('secret-do-not-forward'));
});

test('artifact validation rejects unsafe paths, hardlinks, empty files, types and sizes', async (t) => {
  const f = await fixture(t);
  for (const mode of ['artifact_escape', 'artifact_absolute', 'artifact_hardlink', 'artifact_empty', 'artifact_mime', 'artifact_name', 'artifact_duplicate']) {
    await assert.rejects(f.runner.run(request(mode), consume), errorCode('INVALID_ARTIFACT'));
  }
  const small = new PythonRunner({ ...f.config, binaryBytes: 20 });
  await assert.rejects(small.run(request('artifact_large'), consume), errorCode('INVALID_ARTIFACT'));
  await assert.rejects(small.run(request('artifact', { files: { data: { data: Buffer.alloc(21) } } }), consume), errorCode('INVALID_INPUT'));
  const directory = await InvocationDirectory.create(f.config.temporaryRoot);
  try {
    await writeFile(path.join(f.root, 'outside.txt'), 'outside');
    // Windows directory junctions do not require symlink privileges.
    await symlink(f.root, path.join(directory.root, 'linked'), process.platform === 'win32' ? 'junction' : 'dir');
    await assert.rejects(directory.collect([{ relativePath: 'linked/outside.txt', fileName: 'x.txt', mimeType: 'text/plain' }], ['text/plain'], 100), errorCode('INVALID_ARTIFACT'));
  } finally { await directory.cleanup(); }
  assert.equal(await readFile(path.join(f.root, 'outside.txt'), 'utf8'), 'outside');
});

test('stdout and stderr limits terminate children and clean invocation files', async (t) => {
  const f = await fixture(t);
  const runner = new PythonRunner({ ...f.config, stdoutBytes: 1024, stderrBytes: 1024 });
  for (const mode of ['stdout_limit', 'stderr_limit']) await assert.rejects(runner.run(request(mode), consume), errorCode('OUTPUT_LIMIT_EXCEEDED'));
});

test('deadlines and active/queued cancellation reject without leaking resources', async (t) => {
  const f = await fixture(t);
  const short = new PythonRunner({ ...f.config, timeoutMs: 250 });
  await assert.rejects(short.run(request('sleep'), consume), errorCode('PROCESS_TIMEOUT'));
  const cancel = new AbortController();
  const tasks = [0, 1, 2].map(() => f.runner.run(request('sleep', { signal: cancel.signal }), consume));
  const timer = setTimeout(() => cancel.abort(), 250);
  const results = await Promise.allSettled(tasks);
  clearTimeout(timer);
  for (const result of results) { assert.equal(result.status, 'rejected'); assert.equal(result.reason.code, 'EXECUTION_CANCELLED'); }
  await assert.rejects(f.runner.run(request('success', { signal: cancel.signal }), consume), errorCode('EXECUTION_CANCELLED'));
  assert.equal((await f.runner.run(request('success'), consume)).result.ok, true);
});

test('worker queue caps active work at two and bounds pending work', async () => {
  const controller = new AbortController();
  const first = await acquire(controller.signal);
  const second = await acquire(controller.signal);
  let started = false;
  const third = acquire(controller.signal).then((release) => { started = true; return release; });
  await Promise.resolve();
  assert.equal(started, false);
  first();
  const releaseThird = await third;
  assert.equal(started, true);
  const pending = Array.from({ length: 32 }, () => acquire(controller.signal).catch((error) => error));
  await assert.rejects(acquire(controller.signal), errorCode('QUEUE_FULL'));
  controller.abort(new ExecutionError('EXECUTION_CANCELLED'));
  for (const result of await Promise.all(pending)) assert.equal(result.code, 'EXECUTION_CANCELLED');
  second(); releaseThird();
});

test('cancellation terminates a live descendant as well as its parent', async (t) => {
  const f = await fixture(t);
  const controller = new AbortController();
  const outcome = f.runner.run(request('tree', { signal: controller.signal }), consume).catch((error) => error);
  let pids;
  const deadline = Date.now() + 4000;
  while (Date.now() < deadline) {
    try { pids = JSON.parse(await readFile(path.join(f.config.runtimeRoot, 'descendant.json'), 'utf8')); break; }
    catch { await new Promise((resolve) => setTimeout(resolve, 30)); }
  }
  controller.abort();
  const result = await outcome;
  assert.equal(result.code, 'EXECUTION_CANCELLED');
  assert.ok(pids, 'Descendant process started');
  for (const pid of [pids.parent, pids.pid]) {
    let alive = true;
    for (let attempt = 0; attempt < 30; attempt++) {
      try { process.kill(pid, 0); }
      catch { alive = false; break; }
      if (process.platform === 'linux') {
        try { if ((await readFile(`/proc/${pid}/stat`, 'utf8')).split(' ')[2] === 'Z') { alive = false; break; } } catch { alive = false; break; }
      }
      await new Promise((resolve) => setTimeout(resolve, 30));
    }
    assert.equal(alive, false, `Process ${pid} must be stopped`);
  }
});

test('n8n cancellation signal and credential reads are passed to the execution layer', async (t) => {
  const { runner } = await fixture(t, ['apiKey']);
  const controller = new AbortController();
  const context = {
    getExecutionCancelSignal: () => controller.signal,
    getNode: () => ({ name: 'test', type: 'test', typeVersion: 1, position: [0, 0], parameters: {} }),
    getCredentials: async (type, index) => { assert.equal(type, 'iflyApi'); assert.equal(index, 2); return { apiKey: 'test-key' }; },
    helpers: {},
  };
  const result = await executeSkill(context, runner, 2, { skill, operation, parameters: { mode: 'environment' } });
  assert.equal(result.json.data.IFLY_API_KEY, 'test-key');
  const task = executeSkill(context, runner, 2, { skill, operation, parameters: { mode: 'sleep' } });
  const timer = setTimeout(() => controller.abort(), 250);
  await assert.rejects(task, (error) => error.message.includes('EXECUTION_CANCELLED') && error.context.itemIndex === 2);
  clearTimeout(timer);
  context.getExecutionCancelSignal = () => undefined;
  context.getCredentials = async () => { throw new Error('secret-do-not-forward'); };
  await assert.rejects(executeSkill(context, runner, 2, { skill, operation }),
    (error) => error.message.includes('AUTH_FAILED') && !JSON.stringify(error).includes('secret-do-not-forward'));
});

test('consumer failures and cancellation during persistence still remove files', async (t) => {
  const { runner } = await fixture(t);
  await assert.rejects(runner.run(request('artifact'), async () => { throw new Error('secret-do-not-forward'); }), errorCode('PROCESS_EXIT'));
  const controller = new AbortController();
  await assert.rejects(runner.run(request('artifact', { signal: controller.signal }), async () => {
    controller.abort();
    return 'must not return success';
  }), errorCode('EXECUTION_CANCELLED'));
});

test('real bridge classifies legacy import exits without leaking diagnostics', async (t) => {
  const f = await fixture(t);
  await cp(path.join(pkg, 'runtime/bridge'), path.join(f.config.runtimeRoot, 'bridge'), { recursive: true });
  const scriptRoot = path.join(f.config.runtimeRoot, 'skills/iflytek-hyper-tts/scripts');
  await mkdir(scriptRoot, { recursive: true });
  await writeFile(path.join(scriptRoot, 'xfei_hyper_tts.py'), 'import sys\nprint("secret-do-not-forward")\nsys.exit(1)\n');
  await assert.rejects(f.runner.run({ skill, operation }, consume), errorCode('DEPENDENCY_MISSING'));
  for (const payload of ['{}{}', '{"protocolVersion":1,"requestId":"test","input":NaN,"parameters":{}}', 'x'.repeat(1024 * 1024 + 1)]) {
    const output = await new Promise((resolve, reject) => {
      const child = spawn(pythonExecutable,
        ['-I', '-B', '-X', 'utf8', path.join(f.config.runtimeRoot, 'bridge/bridge.py'), '--skill', skill, '--operation', operation],
        { windowsHide: true, timeout: 3000 });
      let stdout = ''; let stderr = '';
      child.on('error', reject);
      child.stdin.on('error', () => {});
      child.stdout.on('data', (data) => { stdout += data; });
      child.stderr.on('data', (data) => { stderr += data; });
      child.on('close', (code) => resolve({ code, stdout, stderr }));
      child.stdin.end(payload);
    });
    assert.equal(output.code, 1);
    assert.equal(JSON.parse(output.stdout).error.code, 'INVALID_INPUT');
    assert.equal(output.stderr, '');
  }
});
