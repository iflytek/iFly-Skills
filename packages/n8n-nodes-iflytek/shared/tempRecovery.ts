import { lstat, readFile, readdir, realpath, rm } from 'node:fs/promises';
import { hostname, tmpdir } from 'node:os';
import * as path from 'node:path';

export interface RecoveryOptions {
  root: string; minAgeMs: number; apply?: boolean; workersStopped?: boolean;
}

// Offline recovery only: a killed worker can leave descendants before recording their PIDs.
// Never infer that all descendants stopped just because the owner PID no longer exists.
export async function recoverTemporaryDirectories(options: RecoveryOptions) {
  if (!path.isAbsolute(options.root) || !Number.isSafeInteger(options.minAgeMs)
    || options.minAgeMs < 3_600_000 || options.apply && !options.workersStopped) {
    throw new Error('Use an absolute dedicated root and age >= 1 hour. Applying requires --workers-stopped.');
  }
  const root = await realpath(options.root);
  if (root === path.parse(root).root || root === await realpath(tmpdir()) || (await lstat(options.root)).isSymbolicLink()) {
    throw new Error('Use a dedicated real invocation root, not a system temporary directory or symlink.');
  }
  const result: { name: string; action: 'retained' | 'eligible' | 'removed'; reason: string }[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (!/^ifly-exec-[a-zA-Z0-9]{6}$/.test(entry.name)) continue;
    const target = path.join(root, entry.name);
    const retain = (reason: string) => result.push({ name: entry.name, action: 'retained', reason });
    if (!entry.isDirectory() || entry.isSymbolicLink()) { retain('unsafe-path'); continue; }
    try {
      const marker = path.join(target, '.ifly-owner.json');
      const markerStat = await lstat(marker);
      if (!markerStat.isFile() || markerStat.isSymbolicLink() || markerStat.nlink !== 1 || markerStat.size > 1024) {
        retain('invalid-owner'); continue;
      }
      const owner = JSON.parse(await readFile(marker, 'utf8'));
      if (owner.version !== 1 || owner.hostname !== hostname() || !Number.isSafeInteger(owner.pid) || owner.pid <= 0
        || !Number.isSafeInteger(owner.createdAt) || owner.createdAt <= 0) { retain('invalid-or-foreign-owner'); continue; }
      const stat = await lstat(target);
      if (Date.now() - Math.max(owner.createdAt, stat.mtimeMs) < options.minAgeMs) { retain('too-recent'); continue; }
      try { process.kill(owner.pid, 0); retain('owner-alive'); continue; }
      catch (error) {
        if ((error as NodeJS.ErrnoException).code !== 'ESRCH') { retain('owner-status-unknown'); continue; }
      }
      if (path.dirname(target) !== root || (await lstat(target)).isSymbolicLink() || await realpath(target) !== target) {
        retain('unsafe-path'); continue;
      }
      if (options.apply) await rm(target, { recursive: true, maxRetries: 3, retryDelay: 100 });
      result.push({ name: entry.name, action: options.apply ? 'removed' : 'eligible', reason: 'expired-owner-stopped' });
    } catch { retain('inspection-or-removal-failed'); }
  }
  return result;
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const value = (key: string) => args[args.indexOf(key) + 1];
  const allowed = new Set(['--root', '--min-age-hours', '--apply', '--workers-stopped']);
  try {
    for (let i = 0; i < args.length; i++) {
      if (!allowed.has(args[i])) throw new Error('Unknown argument');
      if (args[i] === '--root' || args[i] === '--min-age-hours') {
        if (!args[++i] || args[i].startsWith('--')) throw new Error('Missing argument');
      }
    }
    if (!args.includes('--root')) throw new Error('Missing --root');
    void recoverTemporaryDirectories({ root: value('--root'),
      minAgeMs: Number(args.includes('--min-age-hours') ? value('--min-age-hours') : 24) * 3_600_000,
      apply: args.includes('--apply'), workersStopped: args.includes('--workers-stopped'),
    }).then(result => console.log(JSON.stringify(result, null, 2))).catch(() => {
      console.error('Recovery failed. Verify the dedicated root, age and stopped-worker requirement.'); process.exitCode = 1;
    });
  } catch {
    console.error('Usage: node tempRecovery.js --root <absolute-directory> [--min-age-hours 24] [--apply --workers-stopped]');
    process.exitCode = 1;
  }
}
