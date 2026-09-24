import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

test('real atomic Skill clients and n8n adapters pass transport-level offline regressions', () => {
  const pkg = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const python = process.env.IFLY_TEST_PYTHON
    || spawnSync('python', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' }).stdout.trim();
  const result = spawnSync(python, ['-I', '-B', '-X', 'utf8',
    path.join(pkg, 'tests/fixtures/atomic_clients.py'), path.join(pkg, 'runtime')], { encoding: 'utf8', timeout: 60000 });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stderr, /Ran 15 tests/);
});
