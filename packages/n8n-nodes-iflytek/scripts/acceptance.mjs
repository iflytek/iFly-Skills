// Local subprocess/resource acceptance. No remote APIs or account credentials.
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { createRequire } from 'node:module';
import { lstat, mkdir, mkdtemp, readFile, readdir, realpath, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
for (let i = 0; i < args.length; i += 2) {
  assert.ok(['--package', '--python', '--samples', '--report'].includes(args[i]) && args[i + 1], 'Invalid arguments');
}
const packageRoot = path.resolve(option('--package', path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')));
const python = option('--python', process.env.IFLY_TEST_PYTHON);
const samples = Number(option('--samples', '100'));
assert.ok(python && path.isAbsolute(python), 'Set IFLY_TEST_PYTHON or --python to an absolute path');
assert.ok(Number.isSafeInteger(samples) && samples >= 100 && samples <= 1000, 'Use 100..1000 samples per concurrency level');
const require = createRequire(path.join(packageRoot, 'package.json'));
const { PythonRunner } = require(path.join(packageRoot, 'dist/shared/PythonRunner.js'));
const { processQueue } = require(path.join(packageRoot, 'dist/shared/executionQueue.js'));
const runFile = promisify(execFile);
const root = await mkdtemp(path.join(os.tmpdir(), 'ifly-acceptance-'));
const invocations = path.join(root, 'invocations');
await mkdir(invocations);
const percentile = values => [...values].sort((a, b) => a - b)[Math.ceil(values.length * 0.95) - 1];
const results = [];
async function diskSize(directory) {
  let total = 0;
  for (const file of await readdir(directory, { withFileTypes: true })) {
    const name = path.join(directory, file.name);
    if (file.isDirectory()) total += await diskSize(name);
    else if (file.isFile()) total += (await lstat(name)).size;
  }
  return total;
}
async function children() {
  if (process.platform !== 'linux') return undefined;
  const { stdout } = await runFile('ps', ['-eo', 'pid=,ppid=,rss=,comm='], { timeout: 2000 });
  const rows = stdout.trim().split('\n').map(line => line.trim().split(/\s+/));
  const pids = new Set([process.pid]);
  for (let pass = 0; pass < 5; pass++) for (const [pid, parent] of rows) if (pids.has(Number(parent))) pids.add(Number(pid));
  const pythonRows = rows.filter(([pid, , , name]) => pids.has(Number(pid)) && /^python/.test(name));
  return { count: pythonRows.length, rssBytes: pythonRows.reduce((sum, row) => sum + Number(row[2]) * 1024, 0) };
}
try {
  const startup = [];
  for (let n = 0; n < 10; n++) {
    const start = performance.now();
    await runFile(python, ['-I', '-B', '-c', 'pass'], { windowsHide: true, timeout: 10000 });
    startup.push(performance.now() - start);
  }
  const runner = new PythonRunner({ pythonExecutable: python, temporaryRoot: invocations });
  for (const concurrency of [1, 2, 4]) {
    let next = 0, succeeded = 0, activePeak = 0, queuedPeak = 0;
    let workerRssPeakBytes = process.memoryUsage().rss, temporaryPeakBytes = 0, pythonPeak = 0, pythonRssPeakBytes = 0;
    const durations = [], queueTimes = [];
    let measuring = false;
    const sample = async () => {
      if (measuring) return;
      measuring = true;
      try {
        const queue = processQueue().snapshot();
        activePeak = Math.max(activePeak, queue.active); queuedPeak = Math.max(queuedPeak, queue.queued);
        workerRssPeakBytes = Math.max(workerRssPeakBytes, process.memoryUsage().rss);
        // Invocation directories may disappear between directory and stat calls.
        temporaryPeakBytes = Math.max(temporaryPeakBytes, await diskSize(invocations).catch(() => 0));
        const child = await children();
        if (child) { pythonPeak = Math.max(pythonPeak, child.count); pythonRssPeakBytes = Math.max(pythonRssPeakBytes, child.rssBytes); }
      } finally { measuring = false; }
    };
    const timer = setInterval(() => { void sample().catch(() => {}); }, 50);
    const start = performance.now();
    try {
      await Promise.all(Array.from({ length: concurrency }, async () => {
        while (next++ < samples) {
          await runner.run({ skill: 'iflytek-hyper-tts', operation: 'listVoices', observer: event => {
            activePeak = Math.max(activePeak, event.active); queuedPeak = Math.max(queuedPeak, event.queued);
            if (event.event === 'finished') { durations.push(event.durationMs); queueTimes.push(event.queueMs); }
          } }, async result => {
            assert.equal(result.ok, true); assert.ok(result.data.voices.length > 0); succeeded++;
          });
        }
      }));
    } finally { clearInterval(timer); while (measuring) await new Promise(resolve => setTimeout(resolve, 10)); }
    assert.deepEqual(await readdir(invocations), []);
    assert.equal(processQueue().snapshot().active, 0);
    assert.equal(processQueue().snapshot().queued, 0);
    const residual = await children();
    if (residual) assert.equal(residual.count, 0);
    assert.equal(succeeded, samples);
    results.push({ concurrency, calls: samples, succeeded, successRate: succeeded / samples,
      totalMs: Math.round(performance.now() - start), p95Ms: percentile(durations), queueP95Ms: percentile(queueTimes),
      workerRssPeakBytes, temporaryPeakBytes, activeSlotPeak: activePeak, queuedPeak,
      ...(process.platform === 'linux' ? { sampledPythonPeak: pythonPeak, sampledPythonRssPeakBytes: pythonRssPeakBytes,
        sampleIntervalMs: 50, residualPythonProcesses: residual.count } : { childResourceSampling: 'not measured on this platform' }),
      residualInvocationDirectories: 0 });
  }
  const manifest = JSON.parse(await readFile(path.join(packageRoot, 'runtime/manifest.json'), 'utf8'));
  const report = { kind: 'local-runner-acceptance', measuredAt: new Date().toISOString(), platform: process.platform,
    osRelease: os.release(), architecture: process.arch, cpu: os.cpus()[0]?.model, logicalCpus: os.cpus().length,
    totalMemoryBytes: os.totalmem(), node: process.versions.node,
    python: (await runFile(python, ['--version'], { windowsHide: true })).stdout.trim(),
    sourceCommit: manifest.sourceCommit, sourceTreeDirty: manifest.sourceTreeDirty,
    limits: processQueue().snapshot(), coldPythonStartupP95Ms: Math.round(percentile(startup)), results,
    boundary: 'Local listVoices only. Excludes remote latency, API quotas, real n8n scheduling, rendering and queue-mode transport.' };
  const serialized = JSON.stringify(report, null, 2) + '\n';
  if (args.includes('--report')) await writeFile(path.resolve(option('--report')), serialized);
  console.log(serialized);
} finally {
  assert.equal(path.dirname(await realpath(root)), await realpath(os.tmpdir()));
  await rm(root, { recursive: true, force: true, maxRetries: 3 });
}
