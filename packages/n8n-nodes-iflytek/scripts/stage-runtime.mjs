import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { lstat, mkdir, mkdtemp, readFile, realpath, rename, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const defaultPackageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

function assertRelativeFile(name) {
  if (typeof name !== 'string' || !/^[a-zA-Z0-9_./-]+$/.test(name)
    || name.split('/').some((part) => !part || part === '.' || part === '..')) {
    throw new Error(`Invalid runtime file: ${name}`);
  }
}

async function readSource(root, relativeFile) {
  assertRelativeFile(relativeFile);
  const base = await realpath(root);
  let target = base;
  for (const part of relativeFile.split('/')) {
    target = path.join(target, part);
    if ((await lstat(target)).isSymbolicLink()) {
      throw new Error(`Symlinks are not allowed in runtime sources: ${relativeFile}`);
    }
  }
  if (!(await lstat(target)).isFile()) {
    throw new Error(`Runtime source is not a file: ${relativeFile}`);
  }
  return readFile(target);
}

// Only fixed build output directories directly inside this package may be removed.
async function removeOutput(packageRoot, directory) {
  const target = path.resolve(directory);
  const name = path.basename(target);
  if (path.dirname(target) !== packageRoot || (name !== 'runtime' && !name.startsWith('.runtime-'))) {
    throw new Error('Refusing to remove a path outside package build outputs');
  }
  let stat;
  try {
    stat = await lstat(target);
  } catch (error) {
    if (error.code === 'ENOENT') return;
    throw error;
  }
  if (!stat.isDirectory() || stat.isSymbolicLink() || await realpath(target) !== target) {
    throw new Error('Build output must be a real directory inside the package');
  }
  await rm(target, { recursive: true });
}

export async function stageRuntime({
  packageRoot = defaultPackageRoot,
  repositoryRoot = path.resolve(defaultPackageRoot, '../..'),
} = {}) {
  packageRoot = await realpath(packageRoot);
  repositoryRoot = await realpath(repositoryRoot);
  const catalogBytes = await readSource(packageRoot, 'skills.json');
  const catalog = JSON.parse(catalogBytes);
  if (catalog.schemaVersion !== 1 || !Array.isArray(catalog.skills)) {
    throw new Error('Unsupported skill catalog');
  }
  const ids = new Set();
  const classes = new Set();
  const names = new Set();
  const files = new Map();
  for (const skill of catalog.skills) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(skill.id)
      || !/^Ifly[A-Za-z0-9]+$/.test(skill.nodeClass)
      || skill.nodeName !== skill.nodeClass[0].toLowerCase() + skill.nodeClass.slice(1)
      || ids.has(skill.id) || classes.has(skill.nodeClass) || names.has(skill.nodeName)
      || !Array.isArray(skill.runtimeFiles)
      || (skill.runtimeFiles.length === 0 && !skill.deferredReason)) {
      throw new Error(`Invalid or duplicate skill entry: ${skill.id}`);
    }
    ids.add(skill.id);
    classes.add(skill.nodeClass);
    names.add(skill.nodeName);
    for (const file of skill.runtimeFiles) {
      assertRelativeFile(file);
      if (!file.startsWith('scripts/') || !file.endsWith('.py')) {
        throw new Error(`Only explicitly listed Python scripts may be bundled: ${file}`);
      }
      const target = `skills/${skill.id}/${file}`;
      if (files.has(target)) throw new Error(`Duplicate runtime file: ${target}`);
      files.set(target, await readSource(repositoryRoot, target));
    }
  }
  const requirementsPath = 'requirements/requirements-core.lock';
  files.set(requirementsPath, await readSource(packageRoot, 'python/requirements-core.lock'));
  files.set('bridge/bridge.py', await readSource(packageRoot, 'python/bridge.py'));
  const operationsBytes = await readSource(packageRoot, 'python/operations.json');
  const operations = JSON.parse(operationsBytes);
  if (operations.protocolVersion !== 1 || !Array.isArray(operations.operations)) {
    throw new Error('Invalid enabled operations manifest');
  }
  const enabled = new Set();
  for (const operation of operations.operations) {
    const skill = catalog.skills.find((entry) => entry.id === operation.skill);
    const key = `${operation.skill}/${operation.operation}`;
    if (!skill?.operations.includes(operation.operation) || enabled.has(key)
      || !Array.isArray(operation.credentials)
      || !operation.credentials.every((name) => ['appId', 'apiKey', 'apiSecret'].includes(name))
      || !Array.isArray(operation.artifactMimeTypes)) throw new Error('Invalid enabled operation');
    enabled.add(key);
  }
  files.set('bridge/operations.json', operationsBytes);

  const git = (args) => execFileSync('git', ['-C', repositoryRoot, ...args], { encoding: 'utf8' }).trim();
  const manifest = {
    schemaVersion: 1,
    sourceCommit: git(['rev-parse', 'HEAD']),
    sourceTreeDirty: git(['status', '--porcelain', '--', 'skills', 'packages/n8n-nodes-iflytek']) !== '',
    catalogSha256: sha256(catalogBytes),
    credentialType: 'iflyApi',
    protocolVersion: operations.protocolVersion,
    enabledOperations: operations.operations,
    runtimeRequirements: { python: '>=3.10', pythonRequirements: requirementsPath },
    skills: catalog.skills,
    files: Object.fromEntries([...files].sort(([a], [b]) => a.localeCompare(b))
      .map(([name, bytes]) => [name, { sha256: sha256(bytes), bytes: bytes.length }])),
  };

  // All source validation completes before touching the previous build.
  const temporary = await mkdtemp(path.join(packageRoot, '.runtime-'));
  try {
    for (const [name, bytes] of files) {
      const target = path.join(temporary, ...name.split('/'));
      await mkdir(path.dirname(target), { recursive: true });
      await writeFile(target, bytes);
    }
    await writeFile(path.join(temporary, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
    const output = path.join(packageRoot, 'runtime');
    await removeOutput(packageRoot, output);
    await rename(temporary, output);
  } finally {
    await removeOutput(packageRoot, temporary);
  }
  return manifest;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const manifest = await stageRuntime();
  console.log(`Staged ${Object.keys(manifest.files).length} files from ${manifest.sourceCommit.slice(0, 7)}${manifest.sourceTreeDirty ? ' (local source changes included)' : ''}`);
}
