import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdtemp, readFile, readdir, rm, writeFile, mkdir, copyFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { bridgeFiles, stageRuntime } from '../scripts/stage-runtime.mjs';

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repositoryRoot = path.resolve(packageRoot, '../..');
const json = async (file) => JSON.parse(await readFile(file, 'utf8'));
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
const catalog = await json(path.join(packageRoot, 'skills.json'));

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'ifly-package-test-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  for (const file of ['skills.json', 'python/requirements-core.lock', 'python/requirements-full.lock', ...bridgeFiles.map(file => `python/${file}`)]) {
    await mkdir(path.dirname(path.join(root, file)), { recursive: true });
    await copyFile(path.join(packageRoot, file), path.join(root, file));
  }
  return root;
}

test('registered compiled credential loads without runtime JS dependencies', async () => {
  const pkg = await json(path.join(packageRoot, 'package.json'));
  assert.equal(pkg.name, 'n8n-nodes-iflytek');
  assert.equal(pkg.private, true);
  assert.ok(pkg.keywords.includes('n8n-community-node-package'));
  assert.deepEqual(pkg.n8n.nodes, [
    'dist/nodes/IflyTranslate/IflyTranslate.node.js',
    'dist/nodes/IflyTextProofread/IflyTextProofread.node.js',
    'dist/nodes/IflyOcrInvoice/IflyOcrInvoice.node.js',
    'dist/nodes/IflyHyperTts/IflyHyperTts.node.js',
    'dist/nodes/IflyPdfImageOcr/IflyPdfImageOcr.node.js',
    'dist/nodes/IflySpeedTranscription/IflySpeedTranscription.node.js',
    'dist/nodes/IflyImageUnderstanding/IflyImageUnderstanding.node.js',
    'dist/nodes/IflyVideoTranslate/IflyVideoTranslate.node.js',
    'dist/nodes/IflyVoicecloneTts/IflyVoicecloneTts.node.js',
    'dist/nodes/IflyContractReview/IflyContractReview.node.js',
    'dist/nodes/IflyAnimatedSketch/IflyAnimatedSketch.node.js',
  ]);
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

test('catalog bundles all repository skills with explicit runtime resources', async () => {
  const directories = (await readdir(path.join(repositoryRoot, 'skills'), { withFileTypes: true }))
    .filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
  assert.equal(directories.length, 11);
  assert.deepEqual(catalog.skills.map(({ id }) => id).sort(), directories);
  assert.equal(new Set(catalog.skills.map(({ nodeClass }) => nodeClass)).size, 11);
  assert.equal(new Set(catalog.skills.map(({ nodeName }) => nodeName)).size, 11);
  assert.equal(catalog.skills.filter(({ runtimeFiles }) => runtimeFiles.length > 0).length, 11);
  const sketch = catalog.skills.find(({ id }) => id === 'animated-sketch-diagram');
  for (const file of ['scripts/render-gif.mjs', 'assets/fonts/Kalam-400.woff2']) {
    assert.ok(sketch.runtimeFiles.includes(file));
  }
  assert.ok(bridgeFiles.includes('diagram/licenses/animated-sketch-diagram-MIT.txt'));
  assert.ok(bridgeFiles.includes('diagram/licenses/Kalam-OFL.txt'));
  for (const skill of catalog.skills) {
    assert.equal(skill.credential, skill.id === 'animated-sketch-diagram' ? null : 'iflyApi');
    assert.equal(skill.deferredReason, undefined);
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
      : path.join(root, 'python', file.startsWith('bridge/') ? file.slice('bridge/'.length) : path.basename(file));
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
