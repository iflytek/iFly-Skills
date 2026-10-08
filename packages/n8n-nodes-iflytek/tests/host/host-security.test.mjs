// Run after normal npm ci in the isolated, locked test host.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { gzipSync } from 'node:zlib';
import test from 'node:test';

const root = process.env.IFLY_N8N_HOST_ROOT || path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(root, 'package.json'));
const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf8'));
const entries = (name) => Object.entries(lock.packages).filter(([location]) => location.endsWith('node_modules/' + name));
const from = (location) => createRequire(path.join(root, location, 'package.json'));
function temporary(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ifly-host-security-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return directory;
}

test('installed host and all affected transitive dependency paths use reviewed versions', () => {
  assert.equal(require('n8n/package.json').version, '2.40.7');
  const semver = require('semver');
  for (const [name, range] of Object.entries({
    tar: '>=7.5.21 <8', 'fast-xml-parser': '>=4.5.7 <5 || >=5.5.9 <6',
    'form-data': '>=2.5.6 <3 || >=3.0.5 <4 || >=4.0.6 <5',
    'simple-git': '>=4.0.2 <5', '@simple-git/argv-parser': '>=2.0.1 <3',
    'shell-quote': '>=1.12.0 <2', vm2: '>=3.12.2 <4',
  })) {
    assert.ok(entries(name).length, `Missing dependency: ${name}`);
    for (const [location, pkg] of entries(name)) {
      assert.ok(semver.satisfies(pkg.version, range), `${location}: ${pkg.version}`);
      assert.equal(JSON.parse(fs.readFileSync(path.join(root, location, 'package.json'))).version, pkg.version);
    }
  }
  for (const [location, pkg] of Object.entries(lock.packages)) assert.ok(!pkg.extraneous, location);
  assert.equal(entries('expr-eval').length, 0, 'Do not reintroduce the unused vulnerable evaluator');
});

test('Git library APIs work through n8n dependency paths and retain security guards', async t => {
  const scratch = temporary(t);
  // Keep Git configuration and all writes inside disposable repositories.
  const env = { PATH: process.env.PATH, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: path.join(scratch, 'empty.gitconfig') };
  fs.writeFileSync(env.GIT_CONFIG_GLOBAL, '');
  for (const consumer of ['n8n', 'n8n-nodes-base']) {
    const current = createRequire(require.resolve(`${consumer}/package.json`));
    const { simpleGit, GitPluginError } = current('simple-git');
    const directory = path.join(scratch, consumer);
    fs.mkdirSync(directory);
    const git = simpleGit({
      baseDir: directory, timeout: { block: 10000 },
      allowEnvironment: ['GIT_CONFIG_GLOBAL', 'GIT_CONFIG_NOSYSTEM'],
      unsafe: { allowUnsafeConfigPaths: true }, // Only the empty test configuration path above.
    }).env(env);
    await git.init();
    await git.addConfig('user.name', 'Host Security Test');
    await git.addConfig('user.email', 'host-security@example.invalid');
    fs.writeFileSync(path.join(directory, 'sample.txt'), 'sample');
    await git.add('sample.txt');
    await git.commit('local compatibility check', { '--no-gpg-sign': null });
    assert.equal((await git.status()).isClean(), true, consumer);
    assert.equal((await git.log()).latest.message, 'local compatibility check', consumer);
    assert.equal((await git.show(['HEAD:sample.txt'])), 'sample', consumer);
    for (const key of ['trailer.audit.cmd', 'trailer.audit.command']) {
      await assert.rejects(async () => git.addConfig(key, 'echo blocked'), error =>
        error instanceof GitPluginError && /allowUnsafeCommandBinaries/.test(error.message));
      assert.equal((await git.getConfig(key)).value, null);
    }
    // Check editor detection without invoking any editor or changing process.env.
    const { vulnerabilityCheck } = createRequire(current.resolve('simple-git'))('@simple-git/argv-parser');
    const findings = [...vulnerabilityCheck(['config', '--edit'], { VISUAL: 'echo blocked' })];
    assert.ok(findings.some(finding => finding.category === 'allowUnsafeEditor'), consumer);
    // n8n 2.40.7's built-in Git node does not yet opt into v4's environment guard.
    // Keep this restriction explicit; the isolated host validates the iFLYTEK nodes.
    await assert.rejects(async () => simpleGit({ baseDir: directory }).env({
      GIT_TERMINAL_PROMPT: '0', GIT_ALLOW_PROTOCOL: 'file:git:http:https:ssh',
    }).status(), /environment guard/);
  }
});

test('Daytona shell quoting preserves arguments and rejects line breaks after comments', () => {
  const current = createRequire(require.resolve('@daytona/sdk/package.json'));
  const { quote, parse } = current('shell-quote');
  const args = ['git', 'commit', '-m', 'two words', "a'b", '$HOME', ''];
  assert.deepEqual(parse(quote(args)), args);
  for (const newline of ['\n', '\r', '\u2028', '\u2029']) {
    assert.throws(() => quote(['echo', { comment: 'note' }, `${newline}echo blocked`]), /line terminators/);
  }
});

test('vm2 consumers retain async execution and restricted module resolution', async () => {
  for (const consumer of ['n8n-nodes-base', '@n8n/n8n-nodes-langchain']) {
    const current = createRequire(require.resolve(`${consumer}/package.json`));
    const { VM, NodeVM, makeResolverFromLegacyOptions } = current('vm2');
    const resolver = makeResolverFromLegacyOptions({ external: false, builtin: [] });
    const vm = new NodeVM({ sandbox: { input: 21 }, require: resolver, eval: false, wasm: false });
    assert.equal(await vm.run('module.exports = Promise.resolve(input * 2)'), 42, consumer);
    assert.throws(() => vm.run('module.exports = require("node:fs")'), /Cannot find module|Access denied/);
    assert.throws(() => new VM({ eval: false }).run('eval("1 + 1")'), /Code generation|EvalError/);
  }
  // Exercise the actual n8n Code sandbox wrapper, including its legacy resolver API.
  const base = path.dirname(require.resolve('n8n-nodes-base/package.json'));
  const { JavaScriptSandbox } = require(path.join(base, 'dist/nodes/Code/JavaScriptSandbox.js'));
  const sandbox = new JavaScriptSandbox({ input: 21 }, 'return [{ json: { value: await Promise.resolve(input * 2) } }];', {});
  const result = await sandbox.runCode();
  assert.equal(result[0].json.value, 42);
});

test('current LangChain Calculator works without the removed legacy evaluator', async () => {
  const current = createRequire(require.resolve('@n8n/n8n-nodes-langchain/package.json'));
  const calculatorPath = current.resolve('@langchain/community/tools/calculator');
  assert.throws(() => createRequire(calculatorPath).resolve('expr-eval'), { code: 'MODULE_NOT_FOUND' });
  const { Calculator } = current('@langchain/community/tools/calculator');
  const calculator = new Calculator();
  assert.equal(await calculator.invoke('99 + 99'), '198');
  assert.equal(await calculator.invoke('constructor'), "I don't know how to do that.");
});

test('all XML parsers preserve entity encoding and round-trip normal API payloads', () => {
  const attack = '<!DOCTYPE foo [<!ENTITY l. "INJECTED">]><root>&lt;b&gt;text&lt;/b&gt;</root>';
  for (const [location] of entries('fast-xml-parser')) {
    const { XMLParser, XMLBuilder } = require(path.join(root, location));
    const parser = new XMLParser();
    assert.equal(parser.parse(attack).root, '<b>text</b>', location);
    const document = { Result: { Status: 'OK', Message: 'a & b' } };
    assert.deepEqual(parser.parse(new XMLBuilder().build(document)), document);
  }
});

test('multipart SDK paths escape headers and do not use Math.random for boundaries', () => {
  for (const [location, pkg] of entries('form-data')) {
    if (!pkg.version.startsWith('4.')) continue;
    const FormData = require(path.join(root, location));
    const random = Math.random;
    let form;
    try {
      Math.random = () => { throw new Error('Insecure boundary randomness'); };
      form = new FormData();
      assert.match(form.getBoundary(), /^--------------------------[a-f0-9]{24}$/);
    } finally { Math.random = random; }
    form.append('input"\r\nX-Injected: yes', Buffer.from('payload'), { filename: 'sample"\r\nX-Injected: yes.txt' });
    const body = form.getBuffer().toString();
    assert.ok(!body.includes('\r\nX-Injected:'), location);
    assert.ok(body.includes('%22%0D%0AX-Injected: yes'));
    assert.ok(body.includes('payload'));
  }
});

test('tar upgrades preserve SQLite, node-gyp and cache APIs and stop archive escapes', async t => {
  const scratch = temporary(t);
  for (const consumer of ['sqlite3', 'node-gyp', 'cacache']) {
    const [location] = entries(consumer)[0];
    const tar = from(location)('tar');
    assert.equal(from(location)('tar/package.json').version, '7.5.22', consumer);
    const dir = path.join(scratch, consumer);
    fs.mkdirSync(path.join(dir, 'source', 'top'), { recursive: true });
    fs.writeFileSync(path.join(dir, 'source', 'top', 'sample.h'), 'header');
    const archive = path.join(dir, 'sample.tar.gz');
    await tar.create({ gzip: true, cwd: path.join(dir, 'source'), file: archive }, ['top']);
    fs.mkdirSync(path.join(dir, 'sync'));
    fs.mkdirSync(path.join(dir, 'stream'));
    tar.extract({ file: archive, cwd: path.join(dir, 'sync'), sync: true });
    await pipeline(fs.createReadStream(archive), tar.extract({ cwd: path.join(dir, 'stream'), strip: 1, filter: name => name.endsWith('.h') }));
    assert.equal(fs.readFileSync(path.join(dir, 'sync/top/sample.h'), 'utf8'), 'header');
    assert.equal(fs.readFileSync(path.join(dir, 'stream/sample.h'), 'utf8'), 'header');
    // Tiny deterministic archive; never generate a real resource-exhaustion payload.
    const header = new tar.Header({ path: '../escaped', size: 1, mode: 0o600, type: 'File' });
    header.encode();
    const data = Buffer.concat([header.block, Buffer.from('x'), Buffer.alloc(511 + 1024)]);
    await pipeline(Readable.from([data]), tar.extract({ cwd: path.join(dir, 'sync') }));
    assert.ok(!fs.existsSync(path.join(dir, 'escaped')));
    const bombHeader = new tar.Header({ path: 'bounded', size: 16384, mode: 0o600, type: 'File' });
    bombHeader.encode();
    const compressed = gzipSync(Buffer.concat([bombHeader.block, Buffer.alloc(16384 + 1024)]));
    await assert.rejects(pipeline(Readable.from([compressed]), tar.extract({ cwd: path.join(dir, 'sync'), maxDecompressionRatio: 2 })), /decompression|ratio/i);
  }
  // Exercise the actual SQLite build helper, native driver, and cache consumer.
  const [sqlitePath] = entries('sqlite3')[0];
  fs.mkdirSync(path.join(scratch, 'sqlite-helper'));
  execFileSync(process.execPath, [path.join(root, sqlitePath, 'deps/extract.js'), path.join(scratch, 'sqlite3/sample.tar.gz'), path.join(scratch, 'sqlite-helper')]);
  assert.equal(fs.readFileSync(path.join(scratch, 'sqlite-helper/top/sample.h'), 'utf8'), 'header');
  const sqlite = require('sqlite3');
  const db = new sqlite.Database(':memory:');
  try {
    const row = await new Promise((resolve, reject) => db.get('SELECT 42 AS value', (error, result) => error ? reject(error) : resolve(result)));
    assert.equal(row.value, 42);
  } finally { await new Promise((resolve, reject) => db.close(error => error ? reject(error) : resolve())); }
  const cache = require('cacache');
  await cache.put(path.join(scratch, 'cache'), 'key', 'value');
  assert.equal((await cache.get(path.join(scratch, 'cache'), 'key')).data.toString(), 'value');
});
