import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdtemp, readFile, readdir, rm, writeFile, mkdir, copyFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { stageRuntime } from '../scripts/stage-runtime.mjs';

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repositoryRoot = path.resolve(packageRoot, '../..');
const json = async (file) => JSON.parse(await readFile(file, 'utf8'));
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
const catalog = await json(path.join(packageRoot, 'skills.json'));

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'ifly-package-test-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(path.join(root, 'python'));
  for (const file of ['skills.json', 'python/requirements-core.lock', 'python/bridge.py', 'python/operations.json']) {
    await copyFile(path.join(packageRoot, file), path.join(root, file));
  }
  return root;
}

test('registered compiled credential loads without runtime JS dependencies', async () => {
  const pkg = await json(path.join(packageRoot, 'package.json'));
  assert.equal(pkg.name, 'n8n-nodes-iflytek');
  assert.equal(pkg.private, true);
  assert.ok(pkg.keywords.includes('n8n-community-node-package'));
  assert.deepEqual(pkg.n8n.nodes, []);
  assert.equal(pkg.n8n.credentials.length, 1);
  const { IflyApi } = createRequire(import.meta.url)(path.join(packageRoot, pkg.n8n.credentials[0]));
  const credential = new IflyApi();
  assert.equal(credential.name, 'iflyApi');
  assert.deepEqual(credential.properties.map(({ name }) => name), ['appId', 'apiKey', 'apiSecret']);
  for (const property of credential.properties) {
    assert.equal(property.default, '');
    if (property.name !== 'appId') assert.equal(property.typeOptions.password, true);
  }
});

test('catalog covers all repository skills once and records deferred capabilities', async () => {
  const directories = (await readdir(path.join(repositoryRoot, 'skills'), { withFileTypes: true }))
    .filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
  assert.equal(directories.length, 11);
  assert.deepEqual(catalog.skills.map(({ id }) => id).sort(), directories);
  assert.equal(new Set(catalog.skills.map(({ nodeClass }) => nodeClass)).size, 11);
  assert.equal(new Set(catalog.skills.map(({ nodeName }) => nodeName)).size, 11);
  assert.equal(catalog.skills.filter(({ runtimeFiles }) => runtimeFiles.length > 0).length, 9);
  assert.equal(catalog.skills.flatMap(({ runtimeFiles }) => runtimeFiles).length, 10);
  for (const skill of catalog.skills) {
    assert.equal(skill.credential, skill.id === 'animated-sketch-diagram' ? null : 'iflyApi');
    if (skill.runtimeFiles.length === 0) assert.ok(skill.deferredReason);
  }
});

test('staging preserves source bytes, is reproducible, and removes stale output', async (t) => {
  const root = await fixture(t);
  const manifest = await stageRuntime({ packageRoot: root, repositoryRoot });
  const runtime = path.join(root, 'runtime');
  assert.match(manifest.sourceCommit, /^[a-f0-9]{40}$/);
  assert.equal(typeof manifest.sourceTreeDirty, 'boolean');
  assert.equal(manifest.catalogSha256, digest(await readFile(path.join(root, 'skills.json'))));
  assert.deepEqual(manifest.skills, catalog.skills);
  for (const [file, meta] of Object.entries(manifest.files)) {
    const original = file.startsWith('skills/') ? path.join(repositoryRoot, file)
      : path.join(root, 'python', path.basename(file));
    const bytes = await readFile(path.join(runtime, file));
    assert.deepEqual(bytes, await readFile(original));
    assert.deepEqual(meta, { sha256: digest(bytes), bytes: bytes.length });
  }
  const before = await readFile(path.join(runtime, 'manifest.json'));
  await writeFile(path.join(runtime, 'stale.txt'), 'must not ship');
  await stageRuntime({ packageRoot: root, repositoryRoot });
  assert.deepEqual(await readFile(path.join(runtime, 'manifest.json')), before);
  const actualFiles = (await readdir(runtime, { recursive: true, withFileTypes: true }))
    .filter((entry) => entry.isFile())
    .map((entry) => path.relative(runtime, path.join(entry.parentPath, entry.name)).split(path.sep).join('/')).sort();
  assert.deepEqual(actualFiles, [...Object.keys(manifest.files), 'manifest.json'].sort());
  assert.equal((await readdir(root)).some((name) => name.startsWith('.runtime-')), false);
});

test('invalid or missing sources leave the previous runtime untouched', async (t) => {
  const root = await fixture(t);
  await stageRuntime({ packageRoot: root, repositoryRoot });
  const before = await readFile(path.join(root, 'runtime/manifest.json'));
  for (const source of ['scripts/../../outside.py', '/absolute.py', 'scripts/missing.py']) {
    const invalid = structuredClone(catalog);
    invalid.skills[0].runtimeFiles = [source];
    await writeFile(path.join(root, 'skills.json'), JSON.stringify(invalid));
    await assert.rejects(stageRuntime({ packageRoot: root, repositoryRoot }));
    assert.deepEqual(await readFile(path.join(root, 'runtime/manifest.json')), before);
    assert.equal((await readdir(root)).some((name) => name.startsWith('.runtime-')), false);
  }
});
