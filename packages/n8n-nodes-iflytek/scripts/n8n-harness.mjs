// Test-only host for real n8n. It always creates its own user directory and account.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomBytes, randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdir, mkdtemp, realpath, rm, symlink } from 'node:fs/promises';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';

export const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
export async function availablePort() {
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return String(port);
}
export async function until(check, label, timeoutMs = 120000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const result = await check();
    if (result) return result;
    await delay(250);
  }
  throw new Error('Timed out: ' + label);
}

export async function readNodeTypes(url, cookie, timeoutMs = 30000) {
  // n8n can report readiness while its frontend is still streaming nodes.json
  // to disk. Wait for complete JSON; a successful health check is not enough.
  let lastResponse = 'No response';
  try {
    return await until(async () => {
      const response = await fetch(url + '/types/nodes.json', {
        headers: { cookie }, signal: AbortSignal.timeout(Math.min(timeoutMs, 5000)),
      });
      if (response.status === 404 || response.status === 503) {
        lastResponse = `HTTP ${response.status}`;
        await response.body?.cancel();
        return false;
      }
      if (!response.ok) {
        await response.body?.cancel();
        throw new Error(`Node type metadata: HTTP ${response.status}`);
      }
      const text = await response.text();
      let types;
      try { types = JSON.parse(text); }
      catch (error) {
        if (!(error instanceof SyntaxError)) throw error;
        lastResponse = `Incomplete or invalid JSON (${text.length} characters)`;
        return false;
      }
      assert.ok(Array.isArray(types), 'Node type metadata must be an array');
      return types;
    }, 'complete n8n node type metadata', timeoutMs);
  } catch (error) {
    // Do not print the multi-megabyte metadata body on a parsing failure.
    throw new Error(`${error.message}; last response: ${lastResponse}`, { cause: error });
  }
}

export class N8nHarness {
  constructor(n8nRoot, communityRoot, python, extraEnv = {}) {
    assert.equal(process.platform, 'linux', 'This infrastructure harness targets Linux; run it in WSL or CI.');
    this.n8nRoot = path.resolve(n8nRoot);
    this.communityRoot = path.resolve(communityRoot);
    this.python = path.resolve(python);
    const require = createRequire(path.join(this.n8nRoot, 'package.json'));
    this.version = require('./package.json').version;
    this.parse = require('flatted').parse;
    this.extraEnv = extraEnv;
    this.children = [];
    this.logs = [];
    this.workflows = [];
    this.executions = [];
  }
  async prepare() {
    this.root = await mkdtemp(path.join(os.tmpdir(), 'ifly-n8n-accept-'));
    this.port = await availablePort();
    this.url = 'http://127.0.0.1:' + this.port;
    await mkdir(path.join(this.root, 'user/.n8n'), { recursive: true });
    await symlink(this.communityRoot, path.join(this.root, 'user/.n8n/nodes'), 'dir');
    this.env = { ...process.env, PATH: path.dirname(process.execPath) + path.delimiter + (process.env.PATH ?? ''),
      N8N_USER_FOLDER: path.join(this.root, 'user'),
      NODE_COMPILE_CACHE: path.join(this.root, 'compile-cache'),
      N8N_HOST: '127.0.0.1', N8N_LISTEN_ADDRESS: '127.0.0.1', N8N_PORT: this.port,
      N8N_PROTOCOL: 'http', N8N_SECURE_COOKIE: 'false', N8N_ENCRYPTION_KEY: randomBytes(32).toString('hex'),
      N8N_DIAGNOSTICS_ENABLED: 'false', N8N_VERSION_NOTIFICATIONS_ENABLED: 'false', N8N_TEMPLATES_ENABLED: 'false',
      N8N_PERSONALIZATION_ENABLED: 'false', N8N_UNVERIFIED_PACKAGES_ENABLED: 'true',
      N8N_DEFAULT_BINARY_DATA_MODE: 'filesystem', N8N_LOG_LEVEL: 'info', N8N_LOG_FORMAT: 'json',
      IFLYTEK_PYTHON_EXECUTABLE: this.python, IFLYTEK_LOG_EXECUTIONS: 'true', ...this.extraEnv };
  }
  async launch(name, args = ['start']) {
    const temporaryRoot = path.join(this.root, name + '-invocations');
    await mkdir(temporaryRoot, { recursive: true });
    const env = { ...this.env, IFLYTEK_TMP_ROOT: temporaryRoot, N8N_RUNNERS_BROKER_PORT: await availablePort() };
    const processHandle = spawn(process.execPath, [path.join(this.n8nRoot, 'bin/n8n'), ...args], {
      cwd: this.root, env, detached: true, stdio: ['ignore', 'pipe', 'pipe'],
    });
    const record = { name, child: processHandle, temporaryRoot, exited: false, lines: '' };
    this.children.push(record);
    const collect = data => {
      record.lines = (record.lines + data).slice(-2000000);
      this.logs.push({ process: name, text: String(data) });
      if (this.logs.length > 5000) this.logs.shift();
    };
    processHandle.stdout.on('data', collect);
    processHandle.stderr.on('data', collect);
    processHandle.on('error', error => { record.error = error.code; });
    processHandle.on('close', code => { record.exited = true; record.exitCode = code; });
    return record;
  }
  async start() {
    await this.prepare();
    this.main = await this.launch('main');
    try {
      await until(async () => {
        if (this.main.exited) throw new Error('n8n exited during startup: ' + this.main.exitCode);
        return await fetch(this.url + '/healthz/readiness').then(r => r.ok).catch(() => false);
      }, 'n8n ready');
    } catch (error) {
      throw new Error(error.message + '\n' + this.main.lines.slice(-6000));
    }
    await this.api('/rest/owner/setup', 'POST', { email: 'acceptance@example.invalid', firstName: 'Local', lastName: 'Acceptance',
      password: 'A1!' + randomBytes(20).toString('hex') });
    return this;
  }
  async api(route, method = 'GET', body) {
    const response = await fetch(this.url + route, { method,
      headers: { 'content-type': 'application/json', ...(this.cookie ? { cookie: this.cookie } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(30000) });
    const cookies = response.headers.getSetCookie();
    if (cookies.length) this.cookie = cookies.map(cookie => cookie.split(';')[0]).join('; ');
    const text = await response.text();
    const parsed = text ? JSON.parse(text) : null;
    if (!response.ok) throw new Error(`${method} ${route}: ${response.status} ${parsed?.message ?? ''}`);
    return parsed?.data ?? parsed;
  }
  node(name, type, parameters = {}, extra = {}) {
    return { id: randomUUID(), name, type, typeVersion: 1, position: [0, 0], parameters, ...extra };
  }
  async create(name, nodes) {
    const connections = {};
    for (let index = 0; index < nodes.length - 1; index++) {
      connections[nodes[index].name] = { main: [[{ node: nodes[index + 1].name, type: 'main', index: 0 }]] };
    }
    const workflow = await this.api('/rest/workflows', 'POST', { name, nodes, connections,
      settings: { executionOrder: 'v1', saveManualExecutions: true, saveDataSuccessExecution: 'all', saveDataErrorExecution: 'all' } });
    this.workflows.push(workflow);
    return workflow;
  }
  async run(workflow) {
    const result = await this.api('/rest/workflows/' + workflow.id + '/run', 'POST', { triggerToStartFrom: { name: workflow.nodes[0].name } });
    assert.ok(result.executionId);
    this.executions.push(result.executionId);
    return result.executionId;
  }
  async execution(id) {
    const result = await this.api('/rest/executions/' + id + '?includeData=true');
    if (typeof result.data === 'string') result.data = this.parse(result.data);
    return result;
  }
  async completed(id, status = 'success') {
    const result = await until(async () => {
      const execution = await this.execution(id);
      return ['success', 'error', 'canceled', 'crashed', 'waiting'].includes(execution.status) ? execution : false;
    }, 'execution completion');
    assert.equal(result.status, status, result.data?.resultData?.error?.message);
    return result;
  }
  async binary(meta) {
    const response = await fetch(this.url + '/rest/binary-data?' + new URLSearchParams({ id: meta.id, action: 'download',
      fileName: meta.fileName, mimeType: meta.mimeType }), { headers: { cookie: this.cookie } });
    assert.equal(response.status, 200);
    return Buffer.from(await response.arrayBuffer());
  }
  async stop(record, hard = false) {
    if (record.exited) return;
    try { process.kill(-record.child.pid, hard ? 'SIGKILL' : 'SIGTERM'); }
    catch (error) { if (error.code !== 'ESRCH') throw error; }
    try { await until(() => record.exited, 'process stop', 15000); }
    catch { process.kill(-record.child.pid, 'SIGKILL'); await until(() => record.exited, 'forced stop', 10000); }
  }
  async cleanup() {
    for (const record of [...this.children].reverse()) await this.stop(record);
    if (this.root) {
      assert.equal(path.dirname(await realpath(this.root)), await realpath(os.tmpdir()));
      assert.ok(path.basename(this.root).startsWith('ifly-n8n-accept-'));
      await rm(this.root, { recursive: true, force: true, maxRetries: 3 });
    }
  }
}
