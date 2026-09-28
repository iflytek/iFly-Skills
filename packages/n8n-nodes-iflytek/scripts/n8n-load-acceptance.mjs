// Real n8n webhook load, using local operations only. No service credentials.
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { lstat, readFile, readdir, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';
import { N8nHarness, until } from './n8n-harness.mjs';

const args = process.argv.slice(2);
const allowed = ['--n8n-root', '--community-root', '--python', '--report', '--samples', '--render-samples', '--chrome', '--ffmpeg'];
for (let i = 0; i < args.length; i += 2) assert.ok(allowed.includes(args[i]) && args[i + 1], 'Invalid arguments');
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
for (const key of allowed.slice(0, 4)) assert.ok(args.includes(key), `Missing ${key}`);
const samples = Number(option('--samples', '100'));
const renderSamples = Number(option('--render-samples', '10'));
assert.ok(Number.isSafeInteger(samples) && samples >= 100 && samples <= 1000);
assert.ok(Number.isSafeInteger(renderSamples) && renderSamples >= 10 && renderSamples <= 100);
assert.equal(args.includes('--chrome'), args.includes('--ffmpeg'), 'Specify both rendering executables');
const render = args.includes('--chrome');
const host = new N8nHarness(option('--n8n-root'), option('--community-root'), option('--python'), render ? {
  IFLYTEK_CHROME_EXECUTABLE: path.resolve(option('--chrome')),
  IFLYTEK_FFMPEG_EXECUTABLE: path.resolve(option('--ffmpeg')),
} : {});
const runFile = promisify(execFile);
const clockTicks = Number((await runFile('getconf', ['CLK_TCK'])).stdout.trim());
assert.ok(Number.isFinite(clockTicks) && clockTicks > 0);
const p95 = values => [...values].sort((a, b) => a - b)[Math.ceil(values.length * 0.95) - 1];
const report = { kind: 'real-n8n-webhook-load', measuredAt: new Date().toISOString(), n8n: host.version,
  node: process.versions.node, platform: process.platform, architecture: process.arch,
  cpu: os.cpus()[0]?.model, logicalCpus: os.cpus().length, totalMemoryBytes: os.totalmem(), results: [] };

async function processTree() {
  const { stdout } = await runFile('ps', ['-eo', 'pid=,ppid=,rss=,comm='], { timeout: 5000 });
  const rows = stdout.trim().split('\n').map(line => {
    const [pid, parent, rss, name] = line.trim().split(/\s+/);
    return { pid: Number(pid), parent: Number(parent), rssBytes: Number(rss) * 1024, name };
  });
  const ids = new Set([host.main.child.pid]);
  let previous;
  do { previous = ids.size; for (const row of rows) if (ids.has(row.parent)) ids.add(row.pid); } while (ids.size !== previous);
  return rows.filter(row => ids.has(row.pid));
}
async function diskSize(directory) {
  let bytes = 0;
  for (const entry of await readdir(directory, { withFileTypes: true }).catch(error => {
    if (error.code === 'ENOENT') return []; throw error;
  })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) bytes += await diskSize(file);
    else if (entry.isFile()) bytes += await lstat(file).then(stat => stat.size).catch(error => {
      if (error.code === 'ENOENT') return 0; throw error;
    });
  }
  return bytes;
}
async function cpuTicks() {
  const stat = await readFile(`/proc/${host.main.child.pid}/stat`, 'utf8');
  const fields = stat.slice(stat.lastIndexOf(')') + 2).trim().split(/\s+/);
  return { process: Number(fields[11]) + Number(fields[12]), reapedChildren: Number(fields[13]) + Number(fields[14]) };
}

try {
  await host.start();
  const runtime = path.join(host.communityRoot, 'node_modules/n8n-nodes-iflytek/runtime');
  const manifest = JSON.parse(await readFile(path.join(runtime, 'manifest.json'), 'utf8'));
  report.sourceCommit = manifest.sourceCommit;
  report.sourceTreeDirty = manifest.sourceTreeDirty;
  const scenarios = [{ name: 'voices', calls: samples, node: () => host.node('Local operation',
    'n8n-nodes-iflytek.iflyHyperTts', { operation: 'listVoices' }) }];
  if (render) scenarios.push({ name: 'render', calls: renderSamples, node: () => host.node('Local operation',
    'n8n-nodes-iflytek.iflyAnimatedSketch', { text: '<style>@keyframes move{to{transform:translateX(40px)}}div{animation:move 1s linear infinite}</style><div>Acceptance</div>',
      width: 320, height: 180, fps: 4, durationMs: 1000, scale: 1 }) });
  for (const scenario of scenarios) for (const concurrency of [1, 2, 4]) {
    const hook = `ifly-load-${host.port}-${scenario.name}-${concurrency}`;
    const workflow = await host.create(`Local load ${scenario.name} ${concurrency}`, [
      host.node('Webhook', 'n8n-nodes-base.webhook', { httpMethod: 'GET', path: hook, responseMode: 'lastNode',
        responseData: 'firstEntryJson', options: {} }, { webhookId: hook, typeVersion: 2 }), scenario.node(),
    ]);
    await host.api(`/rest/workflows/${workflow.id}/activate`, 'POST', { versionId: workflow.versionId });
    const request = async (allowNotReady = false) => {
      const started = performance.now();
      const response = await fetch(`${host.url}/webhook/${hook}`, { signal: AbortSignal.timeout(120000) });
      if (allowNotReady && response.status === 404) { await response.body?.cancel(); return false; }
      assert.equal(response.status, 200, 'Webhook failed');
      const body = await response.json();
      if (scenario.name === 'voices') assert.equal(body.data.voices.length, 54);
      else assert.deepEqual(body.data, { width: 320, height: 180, fps: 4, frames: 4 });
      return Math.round(performance.now() - started);
    };
    // One warm-up execution is counted separately from the measured requests.
    await until(() => request(true), 'webhook registration', 20000);
    const baseline = await processTree();
    const baselineIds = new Set(baseline.map(row => row.pid));
    let n8nRssPeakBytes = 0, processTreeRssPeakBytes = 0, pythonPeak = 0, temporaryPeakBytes = 0;
    let sampling, sampleError;
    const sample = async () => {
      const tree = await processTree();
      n8nRssPeakBytes = Math.max(n8nRssPeakBytes, tree.find(row => row.pid === host.main.child.pid)?.rssBytes ?? 0);
      processTreeRssPeakBytes = Math.max(processTreeRssPeakBytes, tree.reduce((sum, row) => sum + row.rssBytes, 0));
      pythonPeak = Math.max(pythonPeak, tree.filter(row => /^python/.test(row.name)).length);
      temporaryPeakBytes = Math.max(temporaryPeakBytes, await diskSize(host.main.temporaryRoot));
    };
    await sample();
    const timer = setInterval(() => {
      if (!sampling) sampling = sample().catch(error => { sampleError = error; }).finally(() => { sampling = undefined; });
    }, 100);
    const durations = [];
    let next = 0;
    const cpuBefore = await cpuTicks();
    const started = performance.now();
    try {
      const results = await Promise.allSettled(Array.from({ length: concurrency }, async () => {
        while (next++ < scenario.calls) durations.push(await request());
      }));
      for (const result of results) if (result.status === 'rejected') throw result.reason;
    } finally { clearInterval(timer); await sampling; }
    const elapsedMs = Math.round(performance.now() - started);
    const cpuAfter = await cpuTicks();
    if (sampleError) throw sampleError;
    const executions = await until(async () => {
      const rows = [];
      const ids = new Set();
      const query = new URLSearchParams({ filter: JSON.stringify({ workflowId: workflow.id }), limit: '100' });
      // The n8n endpoint caps each page at 100, including the warm-up execution.
      for (let page = 0; page <= Math.ceil((scenario.calls + 1) / 100); page++) {
        const response = await host.api('/rest/executions?' + query);
        const batch = response.results ?? response;
        assert.ok(Array.isArray(batch));
        for (const row of batch) {
          assert.ok(!ids.has(row.id), 'Execution pagination repeated an ID');
          ids.add(row.id); rows.push(row);
        }
        if (batch.length < 100 || rows.length >= scenario.calls + 1) break;
        query.set('lastId', batch.at(-1).id);
      }
      return rows.length === scenario.calls + 1 && rows.every(row => row.status === 'success') ? rows : false;
    }, 'all webhook executions saved');
    const last = await host.execution(executions[0].id);
    assert.equal(last.mode, 'webhook');
    if (scenario.name === 'render') {
      const item = last.data.resultData.runData['Local operation'][0].data.main[0][0];
      const bytes = await host.binary(item.binary.image);
      assert.match(bytes.subarray(0, 6).toString(), /^GIF8[79]a$/);
      const decoded = await runFile(host.python, ['-I', '-B', '-c',
        'import io,base64,sys; from PIL import Image; im=Image.open(io.BytesIO(base64.b64decode(sys.argv[1]))); assert im.size==(320,180) and im.n_frames==4',
        bytes.toString('base64')], { timeout: 10000 });
      assert.equal(decoded.stderr, '');
    }
    assert.deepEqual(await readdir(host.main.temporaryRoot), []);
    const remaining = (await processTree()).filter(row => !baselineIds.has(row.pid));
    assert.equal(remaining.length, 0, 'Unexpected child processes remain');
    assert.equal(durations.length, scenario.calls);
    report.results.push({ scenario: scenario.name, concurrency, calls: durations.length, warmupCalls: 1,
      successRate: 1, p95Ms: p95(durations), maxMs: Math.max(...durations), totalMs: elapsedMs,
      n8nCpuMs: Math.round((cpuAfter.process - cpuBefore.process) * 1000 / clockTicks),
      reapedChildCpuMs: Math.round((cpuAfter.reapedChildren - cpuBefore.reapedChildren) * 1000 / clockTicks),
      n8nRssPeakBytes, processTreeRssPeakBytes, sampledPythonPeak: pythonPeak, temporaryPeakBytes,
      sampleIntervalMs: 100, residualInvocationDirectories: 0, residualNewChildProcesses: 0 });
    await host.api(`/rest/workflows/${workflow.id}/deactivate`, 'POST', {});
    console.log(`${scenario.name} concurrency ${concurrency}: ${durations.length} passed, P95 ${p95(durations)} ms`);
  }
} finally { await host.cleanup(); }
report.cleaned = true;
report.boundary = 'Real single-process n8n production webhooks, local Python and optional browser rendering. Includes HTTP and n8n scheduling; excludes paid services, account quotas, queue-mode transport and business billing. RSS sampling can miss short peaks; results are a baseline, not a capacity SLA.';
await writeFile(path.resolve(option('--report')), JSON.stringify(report, null, 2) + '\n');
