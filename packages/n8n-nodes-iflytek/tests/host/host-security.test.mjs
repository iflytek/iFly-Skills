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
