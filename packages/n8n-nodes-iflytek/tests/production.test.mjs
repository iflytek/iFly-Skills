import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { cp, lstat, mkdir, mkdtemp, readFile, readdir, realpath, rm, symlink, utimes, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const require = createRequire(import.meta.url);
const { executionLimits, executionLogging } = require('../dist/shared/executionConfig.js');
const { ExecutionQueue } = require('../dist/shared/executionQueue.js');
const { PythonRunner } = require('../dist/shared/PythonRunner.js');
const { recoverTemporaryDirectories } = require('../dist/shared/tempRecovery.js');
const { executionObserver } = require('../dist/shared/telemetry.js');
const pkg = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const python = process.env.IFLY_TEST_PYTHON || spawnSync('python', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' }).stdout?.trim();

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'ifly-production-test-'));
  t.after(async () => {
    assert.equal(path.dirname(await realpath(root)), await realpath(os.tmpdir()));
    await rm(root, { recursive: true, force: true, maxRetries: 3 });
  });
  return root;
}

test('administrator limits are bounded and reject ambiguous configuration', () => {
  assert.deepEqual(executionLimits({}), { concurrent: 2, queued: 32, timeoutMs: 120000 });
  assert.deepEqual(executionLimits({ IFLYTEK_MAX_CONCURRENT_PROCESSES: '4', IFLYTEK_MAX_QUEUED_REQUESTS: '0',
    IFLYTEK_TIMEOUT_MS: '300000' }), { concurrent: 4, queued: 0, timeoutMs: 300000 });
  for (const name of ['IFLYTEK_MAX_CONCURRENT_PROCESSES', 'IFLYTEK_MAX_QUEUED_REQUESTS', 'IFLYTEK_TIMEOUT_MS']) {
    for (const value of ['-1', '1.5', '', ' 2', '1e2', '99999999999']) {
      assert.throws(() => executionLimits({ [name]: value }), { code: 'INVALID_INPUT' });
    }
  }
  assert.equal(executionLogging({}), false);
  assert.equal(executionLogging({ IFLYTEK_LOG_EXECUTIONS: 'true' }), true);
  assert.throws(() => executionLogging({ IFLYTEK_LOG_EXECUTIONS: 'yes' }), { code: 'INVALID_INPUT' });
});

test('configurable queue stays bounded, cancels FIFO waiters and recovers capacity', async () => {
  const queue = new ExecutionQueue(1, 2);
  const first = await queue.acquire(new AbortController().signal);
  const cancel = new AbortController();
  const canceled = queue.acquire(cancel.signal).catch(error => error);
  const next = queue.acquire(new AbortController().signal);
  await assert.rejects(queue.acquire(new AbortController().signal), { code: 'QUEUE_FULL' });
  cancel.abort(new Error('test cancellation'));
  assert.equal((await canceled).message, 'test cancellation');
  first(); first();
  const release = await next;
  assert.deepEqual(queue.snapshot(), { active: 1, queued: 0, limit: 1, capacity: 2 });
  release();
  assert.equal(queue.snapshot().active, 0);
  const noWait = new ExecutionQueue(1, 0);
  const releaseNoWait = await noWait.acquire(new AbortController().signal);
  await assert.rejects(noWait.acquire(new AbortController().signal), { code: 'QUEUE_FULL' });
  releaseNoWait();
});

test('execution metadata correlates success and failure without forwarding payloads', async t => {
  const root = await fixture(t);
  await mkdir(path.join(root, 'bridge'));
  await mkdir(path.join(root, 'invocations'));
  await cp(path.join(pkg, 'tests/fixtures/process.py'), path.join(root, 'bridge/bridge.py'));
  await writeFile(path.join(root, 'bridge/operations.json'), JSON.stringify({ protocolVersion: 1, operations: [
    { skill: 'iflytek-hyper-tts', operation: 'listVoices', credentials: [], artifactMimeTypes: [] },
  ] }));
  const runner = new PythonRunner({ pythonExecutable: python, runtimeRoot: root,
    temporaryRoot: path.join(root, 'invocations') });
  const events = [];
  const request = { skill: 'iflytek-hyper-tts', operation: 'listVoices', input: { text: 'secret-do-not-forward' },
    credentials: { apiKey: 'secret-do-not-forward' }, observer: event => events.push(event) };
  await runner.run(request, async result => result);
  await assert.rejects(runner.run({ ...request, parameters: { mode: 'business_error' } }, async result => result),
    { code: 'UPSTREAM_ERROR' });
  assert.deepEqual(events.map(e => e.event), ['started', 'finished', 'started', 'finished']);
  assert.equal(events[0].requestId, events[1].requestId);
  assert.notEqual(events[1].requestId, events[3].requestId);
  assert.equal(events[1].status, 'succeeded');
  assert.equal(events[3].errorCode, 'UPSTREAM_ERROR');
  assert.equal(events[3].exitCode, 1);
  assert.ok(events[1].durationMs >= events[1].queueMs);
  assert.ok(!JSON.stringify(events).includes('secret-do-not-forward'));
  await runner.run({ ...request, observer: () => { throw new Error('broken log sink'); } }, async result => result);
  assert.deepEqual(await readdir(path.join(root, 'invocations')), []);
});

test('public URLs reject private destinations and ambiguous syntax without network traffic', () => {
  const output = spawnSync(python, ['-I', '-B', '-X', 'utf8', path.join(pkg, 'tests/fixtures/public_urls.py'), path.join(pkg, 'runtime')],
    { encoding: 'utf8', windowsHide: true, timeout: 10000 });
  assert.equal(output.status, 0, output.stderr);
  assert.match(output.stderr, /Ran 4 tests/);
});

test('n8n log adapter emits metadata only when explicitly enabled', t => {
  const previous = process.env.IFLYTEK_LOG_EXECUTIONS;
  t.after(() => { if (previous === undefined) delete process.env.IFLYTEK_LOG_EXECUTIONS; else process.env.IFLYTEK_LOG_EXECUTIONS = previous; });
  const logged = [];
  const context = { getNode: () => ({ type: '@iflytekopensource/n8n-nodes-iflytek-skills.iflyHyperTts', name: 'private-node-name' }),
    getExecutionId: () => '123', logger: { info: (...args) => logged.push(args) } };
  process.env.IFLYTEK_LOG_EXECUTIONS = 'false';
  assert.equal(executionObserver(context, 0), undefined);
  process.env.IFLYTEK_LOG_EXECUTIONS = 'true';
  executionObserver(context, 2)({ event: 'finished', requestId: 'safe-id' });
  assert.equal(logged[0][1].executionId, '123');
  assert.equal(logged[0][1].itemIndex, 2);
  assert.ok(!JSON.stringify(logged).includes('private-node-name'));
});

test('offline recovery removes only expired stopped owners and protects active, foreign and unsafe paths', async t => {
  const root = await fixture(t);
  const old = Date.now() - 48 * 3600000;
  const stoppedPid = await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['-e', ''], { windowsHide: true });
    child.on('error', reject); child.on('close', () => resolve(child.pid));
  });
  const make = async (suffix, owner, time = old) => {
    const directory = path.join(root, 'ifly-exec-' + suffix);
    await mkdir(directory);
    await writeFile(path.join(directory, '.ifly-owner.json'), JSON.stringify({ version: 1, hostname: os.hostname(),
      pid: stoppedPid, createdAt: time, ...owner }));
    await writeFile(path.join(directory, 'payload'), 'private sample');
    await utimes(directory, time / 1000, time / 1000);
    return directory;
  };
  const dead = await make('dead01', {});
  await make('alive1', { pid: process.pid });
  await make('other1', { hostname: 'foreign-host' });
  await make('recent', {}, Date.now());
  await mkdir(path.join(root, 'unrelated'));
  const outside = await fixture(t);
  await writeFile(path.join(outside, 'keep'), 'keep');
  await symlink(outside, path.join(root, 'ifly-exec-linked'), process.platform === 'win32' ? 'junction' : 'dir');
  const options = { root, minAgeMs: 24 * 3600000 };
  const dry = await recoverTemporaryDirectories(options);
  assert.equal(dry.find(x => x.name === 'ifly-exec-dead01').action, 'eligible');
  assert.ok((await lstat(dead)).isDirectory());
  await assert.rejects(recoverTemporaryDirectories({ ...options, apply: true }));
  const applied = await recoverTemporaryDirectories({ ...options, apply: true, workersStopped: true });
  assert.equal(applied.filter(x => x.action === 'removed').length, 1);
  assert.equal(applied.find(x => x.name === 'ifly-exec-alive1').reason, 'owner-alive');
  assert.equal(await readFile(path.join(outside, 'keep'), 'utf8'), 'keep');
  assert.ok((await readdir(root)).includes('unrelated'));
  await assert.rejects(recoverTemporaryDirectories({ root: os.tmpdir(), minAgeMs: 3600000 }));
});
