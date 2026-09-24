import { executionLimits } from './executionConfig';
import { ExecutionError } from './errors';

interface Waiter { start: () => void; signal: AbortSignal; abort: () => void }

export class ExecutionQueue {
  private active = 0;
  private readonly waiting: Waiter[] = [];
  constructor(readonly limit: number, readonly capacity: number) {
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 16
      || !Number.isSafeInteger(capacity) || capacity < 0 || capacity > 256) throw new ExecutionError('INVALID_INPUT');
  }
  snapshot() { return { active: this.active, queued: this.waiting.length, limit: this.limit, capacity: this.capacity }; }
  acquire(signal: AbortSignal): Promise<() => void> {
    return new Promise((resolve, reject) => {
      const start = () => {
        signal.removeEventListener('abort', abort);
        this.active++;
        let released = false;
        resolve(() => {
          if (released) return;
          released = true;
          this.active--;
          this.waiting.shift()?.start();
        });
      };
      const abort = () => {
        const index = this.waiting.findIndex((entry) => entry.start === start);
        if (index !== -1) this.waiting.splice(index, 1);
        reject(signal.reason ?? new ExecutionError('EXECUTION_CANCELLED'));
      };
      if (signal.aborted) { abort(); return; }
      if (this.active < this.limit) { start(); return; }
      if (this.waiting.length >= this.capacity) { reject(new ExecutionError('QUEUE_FULL')); return; }
      signal.addEventListener('abort', abort, { once: true });
      this.waiting.push({ start, signal, abort });
    });
  }
}

// Shared by every node in this process; change limits by restarting the worker.
let workerQueue: ExecutionQueue | undefined;
export function processQueue(): ExecutionQueue {
  if (!workerQueue) {
    const limits = executionLimits();
    workerQueue = new ExecutionQueue(limits.concurrent, limits.queued);
  }
  return workerQueue;
}
