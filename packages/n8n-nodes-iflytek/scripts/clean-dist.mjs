import { lstat, realpath, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(packageRoot, 'dist');
try {
  const stat = await lstat(output);
  if (!stat.isDirectory() || stat.isSymbolicLink() || await realpath(output) !== output) {
    throw new Error('dist must be a real directory inside the package');
  }
  await rm(output, { recursive: true });
} catch (error) {
  if (error?.code !== 'ENOENT') throw error;
}
