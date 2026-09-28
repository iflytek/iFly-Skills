import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { releaseTag, validateFileList, verifyRuntime } from '../scripts/prepare-release.mjs';
import { validatePublished } from '../scripts/verify-registry.mjs';

test('release channels reject ambiguous versions', () => {
  assert.equal(releaseTag('0.1.0'), 'latest');
  assert.equal(releaseTag('0.2.0-beta.1'), 'beta');
  for (const version of ['0.1', 'v0.1.0', '0.1.0-dev.0', '01.1.0', '0.1.0-beta.01', 'latest', '../package']) assert.throws(() => releaseTag(version));
});

test('packed releases require registered code, runtime files, user docs and templates', async () => {
  const pkg = JSON.parse(await readFile(new URL('../package.json', import.meta.url)));
  const manifest = JSON.parse(await readFile(new URL('../runtime/manifest.json', import.meta.url)));
  const names = ['package.json', 'README.md', 'README.en.md', 'CHANGELOG.md', 'LICENSE',
    ...pkg.n8n.nodes, ...pkg.n8n.credentials, 'runtime/manifest.json',
    ...Object.keys(manifest.files).map(name => 'runtime/' + name),
    ...['proofread-and-translate', 'invoice-recognition', 'text-to-speech'].map(name => `workflows/${name}.json`)];
  const files = names.map(path => ({ path }));
  validateFileList(files, pkg, manifest);
  assert.throws(() => validateFileList(files.filter(file => file.path !== pkg.n8n.nodes[0]), pkg, manifest), /Missing packed file/);
  for (const name of ['runtime/../outside', 'runtime/.env', 'runtime/__pycache__/file.pyc', 'tests/fixture.json', 'node_modules/secret']) {
    assert.throws(() => validateFileList([...files, { path: name }], pkg, manifest));
  }
});

test('artifact checks detect changed runtime bytes and published tarballs', async t => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'ifly-release-test-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(path.join(root, 'runtime'));
  const bytes = Buffer.from('same-size-source');
  const manifest = { files: { 'bridge.py': { bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') } } };
  await writeFile(path.join(root, 'runtime/bridge.py'), bytes);
  await verifyRuntime(root, manifest);
  await writeFile(path.join(root, 'runtime/bridge.py'), Buffer.from('changed--source!'));
  await assert.rejects(verifyRuntime(root, manifest), /Runtime hash mismatch/);
  const release = { package: 'n8n-nodes-iflytek', version: '0.1.0', n8n: {}, keywords: ['n8n-community-node-package'],
    integrity: 'sha512-' + createHash('sha512').update(bytes).digest('base64'), sha256: manifest.files['bridge.py'].sha256 };
  const metadata = { name: release.package, version: release.version, n8n: {}, keywords: release.keywords, dist: { integrity: release.integrity } };
  validatePublished(metadata, release, bytes);
  assert.throws(() => validatePublished(metadata, release, Buffer.from('changed artifact')));
  assert.throws(() => validatePublished({ ...metadata, n8n: { nodes: [] } }, release, bytes));
});

test('workflow exports are inactive, unbound and connect only valid nodes', async () => {
  const directory = new URL('../workflows/', import.meta.url);
  const files = await readdir(directory);
  assert.equal(files.length, 3);
  for (const filename of files) {
    const workflow = JSON.parse(await readFile(new URL(filename, directory)));
    assert.equal(workflow.active, false);
    assert.equal(workflow.pinData, undefined);
    const names = new Set(workflow.nodes.map(node => node.name));
    assert.equal(names.size, workflow.nodes.length);
    assert.equal(workflow.nodes.filter(node => node.type === 'n8n-nodes-base.manualTrigger').length, 1);
    for (const node of workflow.nodes) {
      assert.equal(node.credentials, undefined);
      assert.ok(!node.retryOnFail);
      assert.ok(!/webhook|scheduleTrigger|httpRequest|code$/.test(node.type));
    }
    for (const [source, connection] of Object.entries(workflow.connections)) {
      assert.ok(names.has(source));
      for (const output of connection.main.flat()) assert.ok(names.has(output.node));
    }
  }
});
