import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { readFile, stat } from 'node:fs/promises';
import * as path from 'node:path';
import { promisify } from 'node:util';
import { credentialEnvironment } from './credentialEnv';
import { executionLimits, executionLogging } from './executionConfig';
import { runtimeFile } from './operationManifest';
import { PythonRunner } from './PythonRunner';

export async function preflight(full = false) {
  if (Number(process.versions.node.split('.')[0]) !== 24) throw new Error('Use Node.js 24');
  const root = path.resolve(__dirname, '../..');
  const runtime = path.join(root, 'runtime');
  const manifest = JSON.parse(await readFile(path.join(runtime, 'manifest.json'), 'utf8'));
  const pkg = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'));
  if (manifest.protocolVersion !== 1 || manifest.schemaVersion !== 1 || !manifest.files
    || !Array.isArray(manifest.enabledOperations)) throw new Error('Invalid runtime manifest');
  for (const [name, meta] of Object.entries(manifest.files) as [string, { bytes: number; sha256: string }][]) {
    const content = await readFile(await runtimeFile(runtime, name));
    if (content.length !== meta.bytes || createHash('sha256').update(content).digest('hex') !== meta.sha256) {
      throw new Error('Runtime integrity check failed');
    }
  }
  for (const name of [...pkg.n8n.nodes, ...pkg.n8n.credentials]) {
    if (typeof name !== 'string' || !/^dist\/(nodes|credentials)\/[A-Za-z0-9_/.]+\.js$/.test(name)
      || name.includes('..')) throw new Error('Invalid registration');
    const definition = require(await runtimeFile(root, name));
    if (Object.keys(definition).length !== 1 || typeof Object.values(definition)[0] !== 'function') throw new Error('Invalid registration');
  }
  const python = process.env.IFLYTEK_PYTHON_EXECUTABLE;
  if (!python || !path.isAbsolute(python)) throw new Error('Configure an absolute Python executable');
  const pins: Record<string, string> = {};
  for (const name of ['requirements-core.lock', ...(full ? ['requirements-full.lock'] : [])]) {
    const text = await readFile(await runtimeFile(runtime, `requirements/${name}`), 'utf8');
    for (const line of text.split(/\r?\n/)) {
      const match = /^([\w-]+)==([\w.]+)$/.exec(line);
      if (match) pins[match[1]] = match[2];
    }
  }
  const script = 'import importlib.metadata,json,sys\nassert sys.version_info >= (3,10)\npins=json.loads(sys.argv[1])\nversions={name:importlib.metadata.version(name) for name in pins}\nassert versions==pins\nprint(json.dumps({"python":sys.version.split()[0],"dependencies":versions}))';
  const output = await promisify(execFile)(python, ['-I', '-B', '-X', 'utf8', '-c', script, JSON.stringify(pins)], {
    env: credentialEnvironment([]), windowsHide: true, timeout: 30_000, maxBuffer: 16 * 1024,
  });
  if (full) {
    for (const key of ['IFLYTEK_CHROME_EXECUTABLE', 'IFLYTEK_FFMPEG_EXECUTABLE']) {
      const target = process.env[key];
      if (!target || !path.isAbsolute(target) || !(await stat(target)).isFile()) throw new Error('Configure full runtime executable paths');
    }
    require.resolve('playwright-core');
  }
  const limits = executionLimits();
  const logging = executionLogging();
  const voices = await new PythonRunner({ pythonExecutable: python, temporaryRoot: process.env.IFLYTEK_TMP_ROOT,
    timeoutMs: limits.timeoutMs }).run({ skill: 'iflytek-hyper-tts', operation: 'listVoices' }, async result => result.data);
  return { packageVersion: pkg.version, sourceCommit: manifest.sourceCommit, sourceTreeDirty: manifest.sourceTreeDirty,
    platform: process.platform, architecture: process.arch, node: process.versions.node,
    profile: full ? 'full' : 'core', ...JSON.parse(output.stdout),
    runtimeFiles: Object.keys(manifest.files).length, nodes: pkg.n8n.nodes.length,
    operations: manifest.enabledOperations.length, limits, logging,
    localVoiceCount: Array.isArray(voices.voices) ? voices.voices.length : 0,
  };
}

if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.some(arg => arg !== '--full') || args.length > 1) {
    console.error('Usage: node preflight.js [--full]'); process.exitCode = 1;
  } else {
    void preflight(args.includes('--full')).then(result => console.log(JSON.stringify(result, null, 2))).catch(() => {
      // Dependency tools can include paths and ambient details in their exceptions.
      console.error('Preflight failed. Check package integrity, pinned dependencies and administrator runtime settings.');
      process.exitCode = 1;
    });
  }
}
