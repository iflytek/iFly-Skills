import { spawn } from 'node:child_process';
import * as path from 'node:path';
import { ExecutionError } from './errors';

// One bounded queue shared by every Runner in this Node.js worker.
let active = 0;
interface Waiter { start: () => void; signal: AbortSignal; abort: () => void }
const waiting: Waiter[] = [];
export function acquire(signal: AbortSignal): Promise<() => void> {
  return new Promise((resolve, reject) => {
    const start = () => {
      signal.removeEventListener('abort', abort);
      active++;
      let released = false;
      resolve(() => {
        if (released) return;
        released = true;
        active--;
        waiting.shift()?.start();
      });
    };
    const abort = () => {
      const index = waiting.findIndex((entry) => entry.start === start);
      if (index !== -1) waiting.splice(index, 1);
      reject(signal.reason);
    };
    if (signal.aborted) { reject(signal.reason); return; }
    if (active < 2) { start(); return; }
    if (waiting.length >= 32) { reject(new ExecutionError('QUEUE_FULL')); return; }
    signal.addEventListener('abort', abort, { once: true });
    waiting.push({ start, signal, abort });
  });
}

async function stopTree(pid: number): Promise<void> {
  if (process.platform === 'win32') {
    // Fixed executable and numeric PID arguments only; never invoke a shell.
    const systemRoot = process.env.SystemRoot ?? process.env.SYSTEMROOT;
    if (!systemRoot || !path.isAbsolute(systemRoot)) throw new ExecutionError('PROCESS_TERMINATION_FAILED');
    await new Promise<void>((resolve, reject) => {
      const killer = spawn(path.join(systemRoot, 'System32/taskkill.exe'), ['/PID', String(pid), '/T', '/F'], {
        shell: false, windowsHide: true, stdio: 'ignore',
      });
      const timer = setTimeout(() => { killer.kill(); reject(new ExecutionError('PROCESS_TERMINATION_FAILED')); }, 5000);
      killer.once('error', () => { clearTimeout(timer); reject(new ExecutionError('PROCESS_TERMINATION_FAILED')); });
      killer.once('close', (code) => {
        clearTimeout(timer);
        if (code === 0) { resolve(); return; }
        try { process.kill(pid, 0); reject(new ExecutionError('PROCESS_TERMINATION_FAILED')); }
        catch (error) {
          if ((error as NodeJS.ErrnoException).code === 'ESRCH') resolve();
          else reject(new ExecutionError('PROCESS_TERMINATION_FAILED'));
        }
      });
    });
  } else {
    const kill = (signal: NodeJS.Signals) => {
      try { process.kill(-pid, signal); }
      catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw new ExecutionError('PROCESS_TERMINATION_FAILED'); }
    };
    kill('SIGTERM');
    await new Promise((resolve) => setTimeout(resolve, 250));
    kill('SIGKILL');
  }
}

export interface ProcessOptions {
  executable: string; bridge: string; skill: string; operation: string;
  cwd: string; env: NodeJS.ProcessEnv; request: Buffer; signal: AbortSignal;
  stdoutBytes: number; stderrBytes: number;
}
export function runProcess(options: ProcessOptions): Promise<{ bytes: Buffer; exitCode: number | null }> {
  return new Promise((resolve, reject) => {
    if (options.signal.aborted) { reject(options.signal.reason); return; }
    const child = spawn(options.executable, ['-I', '-B', '-u', '-X', 'utf8', options.bridge,
      '--skill', options.skill, '--operation', options.operation], {
      shell: false, windowsHide: true, detached: process.platform !== 'win32',
      cwd: options.cwd, env: options.env, stdio: ['pipe', 'pipe', 'pipe'],
    });
    const chunks: Buffer[] = [];
    let stdoutSize = 0;
    let stderrSize = 0;
    let failure: ExecutionError | undefined;
    let termination: Promise<void> | undefined;
    let settled = false;
    let watchdog: NodeJS.Timeout | undefined;
    const finish = () => {
      settled = true;
      clearTimeout(watchdog);
      options.signal.removeEventListener('abort', abort);
    };
    const stop = (error: ExecutionError) => {
      if (settled || failure) return;
      failure = error;
      if (child.pid) {
        termination = stopTree(child.pid).catch(() => { failure = new ExecutionError('PROCESS_TERMINATION_FAILED'); });
      }
      // Bound waiting for close even if an escaped descendant holds a pipe open.
      watchdog = setTimeout(() => {
        if (settled) return;
        child.stdin.destroy(); child.stdout.destroy(); child.stderr.destroy();
        finish();
        reject(new ExecutionError('PROCESS_TERMINATION_FAILED'));
      }, 7000);
    };
    const abort = () => stop(options.signal.reason instanceof ExecutionError
      ? options.signal.reason : new ExecutionError('EXECUTION_CANCELLED'));
    options.signal.addEventListener('abort', abort, { once: true });
    child.once('error', () => stop(new ExecutionError('PYTHON_NOT_FOUND')));
    child.stdin.on('error', () => stop(new ExecutionError('PROCESS_IO')));
    child.stdout.on('error', () => stop(new ExecutionError('PROCESS_IO')));
    child.stderr.on('error', () => stop(new ExecutionError('PROCESS_IO')));
    child.stdout.on('data', (chunk: Buffer) => {
      stdoutSize += chunk.length;
      if (stdoutSize > options.stdoutBytes) stop(new ExecutionError('OUTPUT_LIMIT_EXCEEDED'));
      else if (!failure) chunks.push(chunk);
    });
    child.stderr.on('data', (chunk: Buffer) => {
      stderrSize += chunk.length;
      if (stderrSize > options.stderrBytes) stop(new ExecutionError('OUTPUT_LIMIT_EXCEEDED'));
      // Drain without retaining or forwarding raw diagnostic content.
    });
    child.once('close', async (exitCode) => {
      if (settled) return;
      await termination;
      if (settled) return;
      finish();
      if (failure) reject(failure);
      else resolve({ bytes: Buffer.concat(chunks), exitCode });
    });
    if (options.signal.aborted) abort();
    child.stdin.end(options.request);
  });
}
