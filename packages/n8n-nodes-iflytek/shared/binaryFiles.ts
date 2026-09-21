import { lstat, mkdtemp, open, realpath, rm, writeFile } from 'node:fs/promises';
import * as path from 'node:path';
import { tmpdir } from 'node:os';
import { ExecutionError } from './errors';
import type { Artifact } from './protocol';

export interface InputFile { data: Buffer }
export interface OutputFile { data: Buffer; fileName: string; mimeType: string }
export class InvocationDirectory {
  private constructor(readonly root: string, private readonly parent: string) {}
  static async create(parent = tmpdir()): Promise<InvocationDirectory> {
    const base = await realpath(parent);
    return new InvocationDirectory(await mkdtemp(path.join(base, 'ifly-exec-')), base);
  }
  async writeInputs(inputs: Record<string, InputFile>, maxBytes: number): Promise<Record<string, string>> {
    const result: Record<string, string> = Object.create(null);
    let total = 0;
    if (Object.keys(inputs).length > 16) throw new ExecutionError('INVALID_INPUT');
    for (const [key, file] of Object.entries(inputs)) {
      if (!/^[a-zA-Z][a-zA-Z0-9_]{0,63}$/.test(key) || !Buffer.isBuffer(file.data)) throw new ExecutionError('INVALID_INPUT');
      total += file.data.length;
      if (!file.data.length || total > maxBytes) throw new ExecutionError('INVALID_INPUT');
      const name = `input-${Object.keys(result).length}.bin`;
      await writeFile(path.join(this.root, name), file.data, { flag: 'wx', mode: 0o600 });
      result[key] = name;
    }
    return result;
  }
  async collect(artifacts: Artifact[], mimeTypes: string[], maxBytes: number): Promise<OutputFile[]> {
    const outputs: OutputFile[] = [];
    const seen = new Set<string>();
    let total = 0;
    for (const artifact of artifacts) {
      const { relativePath, fileName, mimeType } = artifact;
      const parts = relativePath.split('/');
      if (!relativePath || parts.some((part) => !/^[a-zA-Z0-9_-][a-zA-Z0-9_.-]*$/.test(part)
        || part.endsWith('.') || /^(con|prn|aux|nul|com\d|lpt\d)(\.|$)/i.test(part))
        || /[\\/:\x00-\x1f\x7f]/.test(fileName) || !fileName || fileName.length > 200
        || fileName === '.' || fileName === '..' || !mimeTypes.includes(mimeType)) throw new ExecutionError('INVALID_ARTIFACT');
      let target = this.root;
      try {
        for (const part of parts) {
          target = path.join(target, part);
          if ((await lstat(target)).isSymbolicLink()) throw new Error();
        }
        const resolved = await realpath(target);
        if (!resolved.startsWith(this.root + path.sep) || seen.has(resolved)) throw new Error();
        seen.add(resolved);
        const handle = await open(target, 'r');
        try {
          const stat = await handle.stat();
          if (!stat.isFile() || stat.nlink !== 1 || stat.size <= 0 || total + stat.size > maxBytes) throw new Error();
          // A bounded read avoids a growing file causing an unbounded allocation.
          const data = Buffer.alloc(stat.size + 1);
          let count = 0;
          while (count < data.length) {
            const { bytesRead } = await handle.read(data, count, data.length - count, null);
            if (!bytesRead) break;
            count += bytesRead;
          }
          if (count !== stat.size) throw new Error();
          total += count;
          outputs.push({ data: data.subarray(0, count), fileName, mimeType });
        } finally { await handle.close(); }
      } catch { throw new ExecutionError('INVALID_ARTIFACT'); }
    }
    return outputs;
  }
  async cleanup(): Promise<void> {
    try {
      // Check the absolute target immediately before recursive deletion.
      if (path.dirname(this.root) !== this.parent || !path.basename(this.root).startsWith('ifly-exec-')
        || (await lstat(this.root)).isSymbolicLink() || await realpath(this.root) !== this.root) throw new Error();
      await rm(this.root, { recursive: true, maxRetries: 3, retryDelay: 100 });
    } catch { throw new ExecutionError('CLEANUP_FAILED'); }
  }
}
