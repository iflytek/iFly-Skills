import type { IExecuteFunctions } from 'n8n-workflow';
import type { ErrorCode } from './errors';
import { executionLogging } from './executionConfig';

export interface ExecutionEvent {
  event: 'started' | 'finished';
  requestId: string; skill: string; operation: string; workerPid: number;
  active: number; queued: number; durationMs: number; queueMs: number;
  status?: 'succeeded' | 'failed'; errorCode?: ErrorCode; exitCode?: number | null;
  inputBytes?: number; outputBytes?: number;
}
export type ExecutionObserver = (event: ExecutionEvent) => void;

export function executionObserver(context: IExecuteFunctions, itemIndex: number): ExecutionObserver | undefined {
  if (!executionLogging()) return undefined;
  // No user-supplied node name, input, task IDs, paths, credentials or upstream diagnostics.
  const nodeType = context.getNode().type;
  const executionId = context.getExecutionId?.();
  return (event) => context.logger?.info('iflytek.execution', {
    ...event, itemIndex,
    ...(/^[a-zA-Z0-9_.-]{1,128}$/.test(nodeType) ? { nodeType } : {}),
    ...(typeof executionId === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(executionId) ? { executionId } : {}),
  });
}
