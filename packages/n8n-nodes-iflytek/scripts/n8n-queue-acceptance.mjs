// Real PostgreSQL/Redis/n8n infrastructure; fee handling is an explicit business-ledger simulation.
import assert from 'node:assert/strict';
import { execFile, spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdir, mkdtemp, readFile, readdir, realpath, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';
import { availablePort, delay, N8nHarness, until } from './n8n-harness.mjs';

const args = process.argv.slice(2);
const option = name => args[args.indexOf(name) + 1];
const keys = ['--n8n-root', '--community-root', '--python', '--postgres-bin', '--postgres-share', '--redis', '--report'];
for (let i = 0; i < args.length; i += 2) assert.ok(keys.includes(args[i]) && args[i + 1], 'Invalid argument');
for (const key of keys) assert.ok(args.includes(key), `Missing ${key}`);
const runFile = promisify(execFile);
const root = await mkdtemp(path.join(os.tmpdir(), 'ifly-queue-accept-'));
const services = [];
let host, pool, admin;
const report = { kind: 'real-n8n-queue-recovery', assertions: {} };
async function launch(executable, args) {
  const child = spawn(executable, args, { cwd: root, env: process.env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const record = { child, exited: false, log: '' };
  const collect = data => { record.log = (record.log + data).slice(-20000); };
  child.stdout.on('data', collect); child.stderr.on('data', collect);
  child.on('error', error => { record.error = error.code; });
  child.on('close', () => { record.exited = true; });
  services.push(record);
  return record;
}
try {
  const postgres = option('--postgres-bin');
  const pgPort = await availablePort(), redisPort = await availablePort();
  await mkdir(path.join(root, 'sockets'));
  await runFile(path.join(postgres, 'initdb'), ['-D', path.join(root, 'postgres'), '-U', 'iflytest',
    '--auth=trust', '--no-locale', '-E', 'UTF8', '-L', option('--postgres-share')], { timeout: 60000 });
  await launch(path.join(postgres, 'postgres'), ['-D', path.join(root, 'postgres'), '-h', '127.0.0.1', '-p', pgPort,
    '-k', path.join(root, 'sockets')]);
  await launch(option('--redis'), ['--bind', '127.0.0.1', '--port', redisPort, '--save', '', '--appendonly', 'no', '--dir', root]);
  await until(async () => {
    try { await runFile(path.join(postgres, 'pg_isready'), ['-h', '127.0.0.1', '-p', pgPort], { timeout: 2000 }); return true; }
    catch { return false; }
  }, 'PostgreSQL ready');
  const require = createRequire(path.join(path.resolve(option('--n8n-root')), 'package.json'));
  const { Client, Pool } = require('pg');
  const pgConfig = { host: '127.0.0.1', port: Number(pgPort), user: 'iflytest', database: 'postgres' };
  admin = new Client(pgConfig); await admin.connect();
  await admin.query('CREATE DATABASE ifly_n8n');
  await admin.query('CREATE DATABASE ifly_business');
  pool = new Pool({ ...pgConfig, database: 'ifly_business', max: 8 });
  await pool.query(await readFile(new URL('../docs/operation-ledger.sql', import.meta.url), 'utf8'));
  host = new N8nHarness(option('--n8n-root'), option('--community-root'), option('--python'), {
    EXECUTIONS_MODE: 'queue', OFFLOAD_MANUAL_EXECUTIONS_TO_WORKERS: 'true',
    DB_TYPE: 'postgresdb', DB_POSTGRESDB_HOST: '127.0.0.1', DB_POSTGRESDB_PORT: pgPort,
    DB_POSTGRESDB_DATABASE: 'ifly_n8n', DB_POSTGRESDB_USER: 'iflytest', DB_POSTGRESDB_PASSWORD: '',
    QUEUE_BULL_REDIS_HOST: '127.0.0.1', QUEUE_BULL_REDIS_PORT: redisPort,
    N8N_DEFAULT_BINARY_DATA_MODE: 'database',
  });
  await host.start();
  report.n8n = host.version;
  const workerA = await host.launch('worker-a', ['worker', '--concurrency=2']);
  await until(() => /worker.*ready/i.test(workerA.lines), 'first worker ready');
  console.log('Queue worker A ready');
  const text = JSON.stringify({ taskId: 'simulated-upstream-task', operationKey: 'fixture-operation', text: 'durable binary' });
  const workflow = await host.create('Cross-worker durable Wait and binary', [
    host.node('Start', 'n8n-nodes-base.manualTrigger'),
    host.node('Before wait', 'n8n-nodes-iflytek.iflyHyperTts', { operation: 'listVoices' }),
    host.node('Input', 'n8n-nodes-base.set', { mode: 'raw', jsonOutput: JSON.stringify({ payload: text }), options: {} }, { typeVersion: 3.4 }),
    host.node('Binary', 'n8n-nodes-base.convertToFile', { operation: 'toText', sourceProperty: 'payload', binaryPropertyName: 'data', options: { fileName: 'fixture.txt' } }),
    host.node('Wait', 'n8n-nodes-base.wait', { resume: 'timeInterval', amount: 70, unit: 'seconds', options: {} }, { typeVersion: 1.1 }),
    host.node('Extract', 'n8n-nodes-base.extractFromFile', { operation: 'text', binaryPropertyName: 'data', destinationKey: 'text', options: {} }),
    host.node('After wait', 'n8n-nodes-iflytek.iflyHyperTts', { operation: 'listVoices' }),
  ]);
  const id = await host.run(workflow);
  const waiting = await host.completed(id, 'waiting');
  assert.ok(workerA.lines.includes('iflytek.execution'), 'Actual node ran on worker A');
  const binary = waiting.data.resultData.runData.Binary[0].data.main[0][0].binary.data;
  assert.match(binary.id, /^database/);
  assert.equal((await host.binary(binary)).toString(), text);
  assert.deepEqual(await readdir(workerA.temporaryRoot), []);
  await host.stop(workerA, true);
  await host.stop(host.main, true);
  report.assertions.stoppedWorkerAndMainDuringWait = true;
  // A restarted main and different worker must use the same durable execution record.
  host.main = await host.launch('restarted-main');
  await until(() => fetch(host.url + '/healthz/readiness').then(r => r.ok).catch(() => false), 'restarted main ready');
  const workerB = await host.launch('worker-b', ['worker', '--concurrency=2']);
  await until(() => /worker.*ready/i.test(workerB.lines), 'second worker ready');
  console.log('Queue worker B ready; waiting for durable execution to resume');

  const digest = createHash('sha256').update('same fee-bearing request').digest('hex');
  const values = ['fixture', 'skill', 'createTask', 'operation-1', digest];
  const claim = 'INSERT INTO ifly_operation_ledger (scope, skill, operation, operation_key, request_sha256) VALUES ($1,$2,$3,$4,$5) ON CONFLICT (scope,skill,operation,operation_key) DO NOTHING RETURNING state';
  const claims = await Promise.all(Array.from({ length: 20 }, () => pool.query(claim, values)));
  const simulatedSubmissions = claims.reduce((sum, value) => sum + value.rowCount, 0);
  assert.equal(simulatedSubmissions, 1);
  // Simulate acceptance upstream with a lost response. The record is retained for reconciliation.
  await pool.query("UPDATE ifly_operation_ledger SET state='submission_unknown', updated_at=now() WHERE operation_key=$1", ['operation-1']);
  assert.equal((await pool.query(claim, values)).rowCount, 0);
  const changed = [...values.slice(0, 4), createHash('sha256').update('different request').digest('hex')];
  assert.equal((await pool.query(claim, changed)).rowCount, 0);
  const record = (await pool.query('SELECT request_sha256,state FROM ifly_operation_ledger WHERE operation_key=$1', ['operation-1'])).rows[0];
  assert.equal(record.state, 'submission_unknown');
  assert.notEqual(record.request_sha256, changed[4], 'Caller must reject the mismatched digest');
  report.assertions.businessLedger = { concurrentClaims: 20, simulatedSubmissions,
    responseLossState: record.state, duplicateClaimBlocked: true, differentInputDetected: true };

  const complete = await until(async () => {
    const execution = await host.execution(id);
    return ['success', 'error', 'crashed', 'canceled'].includes(execution.status) ? execution : false;
  }, 'cross-worker resume', 150000);
  assert.equal(complete.status, 'success', complete.data?.resultData?.error?.message);
  const runs = complete.data.resultData.runData;
  assert.equal(runs.Extract[0].data.main[0][0].json.text, text);
  assert.equal(runs['After wait'][0].data.main[0][0].json.data.voices.length, 54);
  assert.ok(workerB.lines.includes('iflytek.execution'), 'Actual node ran on worker B');
  assert.notEqual(workerA.child.pid, workerB.child.pid);
  assert.equal(runs['Before wait'].length, 1, 'The completed pre-Wait node was not replayed');
  assert.equal((await host.binary(binary)).toString(), text);
  assert.deepEqual(await readdir(workerB.temporaryRoot), []);
  report.assertions.crossWorkerResume = true;
  report.assertions.binaryMode = 'database';
  report.assertions.binaryAfterRestart = true;
  report.assertions.preWaitNodeNotReplayed = true;
  report.assertions.workerPidsDiffer = true;
  report.assertions.residualInvocationDirectories = 0;
  report.boundary = 'Real local Linux processes, PostgreSQL, Redis, n8n queue and database binary; not Docker, S3 or multi-host networking. Local listVoices only; task identity and lost paid response are simulations, not provider-level exactly-once guarantees.';
} finally {
  await host?.cleanup();
  await pool?.end(); await admin?.end();
  for (const service of services.reverse()) {
    if (service.exited) continue;
    try { process.kill(-service.child.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    try { await until(() => service.exited, 'service stopped', 10000); }
    catch { process.kill(-service.child.pid, 'SIGKILL'); await delay(250); }
  }
  assert.equal(path.dirname(await realpath(root)), await realpath(os.tmpdir()));
  await rm(root, { recursive: true, force: true, maxRetries: 3 });
}
report.cleaned = true;
await writeFile(path.resolve(option('--report')), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
