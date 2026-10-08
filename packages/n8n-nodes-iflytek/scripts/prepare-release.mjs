import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export function releaseTag(version) {
  assert.match(version, /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-beta\.(?:0|[1-9]\d*))?$/, 'Use a stable version or an explicit -beta.N version');
  return version.includes('-') ? 'beta' : 'latest';
}

export function releaseNotes(changelog, version) {
  releaseTag(version);
  const lines = changelog.replace(/\r\n/g, '\n').split('\n');
  const matches = lines.flatMap((line, index) => line.trimEnd() === `## ${version}` ? [index] : []);
  assert.equal(matches.length, 1, `Expected exactly one changelog section: ## ${version}`);
  const start = matches[0];
  const next = lines.findIndex((line, index) => index > start && /^##[ \t]+/.test(line));
  const end = next === -1 ? lines.length : next;
  assert.ok(lines.slice(start + 1, end).join('\n').trim(), `Empty changelog section: ## ${version}`);
  return lines.slice(start, end).join('\n').trim() + '\n';
}

export function validateFileList(files, pkg, manifest) {
  const names = files.map(file => file.path);
  assert.equal(new Set(names).size, names.length, 'Duplicate packed files');
  for (const name of names) {
    assert.ok(!name.split('/').some(part => !part || part === '.' || part === '..') && !name.includes('\\'), 'Unsafe archive path');
    assert.ok(/^(?:dist\/(?:nodes|credentials|shared)\/|runtime\/|docs\/|workflows\/)/.test(name)
      || ['package.json', 'README.md', 'README.zh-CN.md', 'CHANGELOG.md', 'LICENSE'].includes(name), `Unexpected packed file: ${name}`);
    assert.ok(!/(?:^|\/)(?:node_modules|__pycache__|\.env[^/]*)(?:\/|$)|\.(?:pyc|log|tgz|pem|key)$/.test(name), `Unwanted packed file: ${name}`);
  }
  for (const name of ['package.json', 'README.md', 'README.zh-CN.md', 'CHANGELOG.md', 'LICENSE',
    ...pkg.n8n.nodes, ...pkg.n8n.credentials, 'runtime/manifest.json',
    ...Object.keys(manifest.files).map(name => 'runtime/' + name),
    ...['proofread-and-translate', 'invoice-recognition', 'text-to-speech'].map(name => `workflows/${name}.json`)]) {
    assert.ok(names.includes(name), `Missing packed file: ${name}`);
  }
}

export async function verifyRuntime(root, manifest) {
  for (const [name, expected] of Object.entries(manifest.files)) {
    assert.ok(!name.includes('\\') && !name.split('/').some(part => !part || part === '.' || part === '..'), 'Unsafe runtime path');
    const bytes = await readFile(path.join(root, 'runtime', name));
    assert.equal(bytes.length, expected.bytes, `Runtime size mismatch: ${name}`);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), expected.sha256, `Runtime hash mismatch: ${name}`);
  }
}

async function main() {
  const args = process.argv.slice(2);
  assert.ok(args.length >= 2 && args[0] === '--output' && args[1]
    && (args.length === 2 || (args.length === 3 && args[2] === '--allow-dirty')), 'Usage: npm run release:prepare -- --output ABSOLUTE_DIRECTORY [--allow-dirty]');
  assert.ok(path.isAbsolute(args[1]), 'Use an absolute output directory outside the repository');
  const pkgRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const repoRoot = path.resolve(pkgRoot, '../..');
  const output = path.resolve(args[1]);
  const relative = path.relative(repoRoot, output);
  assert.ok(relative.startsWith('..' + path.sep) || path.isAbsolute(relative), 'Release output must be outside the repository');
  const json = async file => JSON.parse(await readFile(file, 'utf8'));
  const pkg = await json(path.join(pkgRoot, 'package.json'));
  const lock = await json(path.join(pkgRoot, 'package-lock.json'));
  const manifest = await json(path.join(pkgRoot, 'runtime/manifest.json'));
  const git = args => execFileSync('git', ['-C', repoRoot, ...args], { encoding: 'utf8' }).trim();
  const sourceCommit = git(['rev-parse', 'HEAD']);
  const sourceTreeDirty = git(['status', '--porcelain']) !== '';
  const distTag = releaseTag(pkg.version);
  const changelog = await readFile(path.join(pkgRoot, 'CHANGELOG.md'), 'utf8');
  const notes = releaseNotes(changelog, pkg.version);
  assert.equal(pkg.name, '@iflytekopensource/n8n-nodes-iflytek-skills');
  assert.equal(lock.name, pkg.name);
  assert.equal(lock.packages[''].name, pkg.name);
  assert.equal(lock.version, pkg.version);
  assert.equal(lock.packages[''].version, pkg.version);
  assert.ok(pkg.keywords.includes('n8n-community-node-package'));
  assert.equal(manifest.sourceCommit, sourceCommit, 'Rebuild from the current commit');
  assert.equal(manifest.sourceTreeDirty, sourceTreeDirty, 'Rebuild after source changes');
  assert.ok(!sourceTreeDirty || args.includes('--allow-dirty'), 'Release builds require a clean checkout');
  await verifyRuntime(pkgRoot, manifest);
  await mkdir(output, { recursive: true });
  assert.equal((await readdir(output)).length, 0, 'Output directory must be empty');
  assert.ok(process.env.npm_execpath, 'Invoke through npm run release:prepare');
  const [packed] = JSON.parse(execFileSync(process.execPath, [process.env.npm_execpath, 'pack', '--ignore-scripts', '--json', '--pack-destination', output],
    { cwd: pkgRoot, encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 }));
  validateFileList(packed.files, pkg, manifest);
  // npm pack flattens @scope/name to scope-name in archive filenames.
  assert.equal(packed.filename, `${pkg.name.replace(/^@/, '').replace('/', '-')}-${pkg.version}.tgz`);
  const tarball = path.join(output, packed.filename);
  const bytes = await readFile(tarball);
  // Stream the archive so GNU tar cannot interpret a Windows drive letter as a remote host.
  const archiveNames = execFileSync('tar', ['-tzf', '-'], { input: bytes, encoding: 'utf8' }).trim().split(/\r?\n/).sort();
  assert.deepEqual(archiveNames, packed.files.map(file => 'package/' + file.path).sort(), 'Tarball contents differ from pack metadata');
  const extracted = await mkdtemp(path.join(os.tmpdir(), 'ifly-release-'));
  try {
    execFileSync('tar', ['-xzf', '-'], { input: bytes, cwd: extracted });
    const installed = path.join(extracted, 'package');
    assert.deepEqual(await json(path.join(installed, 'package.json')), pkg);
    assert.deepEqual(await json(path.join(installed, 'runtime/manifest.json')), manifest);
    await verifyRuntime(installed, manifest);
  } finally {
    await rm(extracted, { recursive: true, force: true });
  }
  const integrity = 'sha512-' + createHash('sha512').update(bytes).digest('base64');
  assert.equal(integrity, packed.integrity);
  const report = { package: pkg.name, version: pkg.version, distTag, filename: packed.filename,
    sourceCommit, sourceTreeDirty, publishable: !sourceTreeDirty, integrity,
    sha256: createHash('sha256').update(bytes).digest('hex'), files: packed.files.length,
    keywords: pkg.keywords, n8n: pkg.n8n, runtimeFiles: Object.keys(manifest.files).length };
  await writeFile(path.join(output, 'release.json'), JSON.stringify(report, null, 2) + '\n');
  await writeFile(path.join(output, 'runtime-manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  await writeFile(path.join(output, 'SHA256SUMS'), `${report.sha256}  ${packed.filename}\n`);
  await writeFile(path.join(output, 'CHANGELOG.md'), changelog);
  await writeFile(path.join(output, 'RELEASE_NOTES.md'), notes);
  console.log(JSON.stringify(report, null, 2));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main();
}
