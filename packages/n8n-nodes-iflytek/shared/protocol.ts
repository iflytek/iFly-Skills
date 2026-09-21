import { TextDecoder } from 'node:util';
import { ExecutionError, messages, type ErrorCode } from './errors';

export type JsonObject = { [key: string]: unknown };
export interface Artifact { relativePath: string; fileName: string; mimeType: string }
export interface Success {
  protocolVersion: 1;
  requestId: string;
  ok: true;
  status: 'succeeded' | 'queued' | 'running';
  data: JsonObject;
  artifacts: Artifact[];
  meta: { durationMs: number };
}
export function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
export function decodeResponse(bytes: Buffer, requestId: string, exitCode: number | null): Success {
  let response: unknown;
  try {
    response = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } catch {
    throw new ExecutionError(bytes.length === 0 && exitCode !== 0 ? 'PROCESS_EXIT' : 'INVALID_PROTOCOL');
  }
  if (!isObject(response) || response.protocolVersion !== 1 || response.requestId !== requestId) {
    throw new ExecutionError('INVALID_PROTOCOL');
  }
  if (response.ok === false) {
    const error = response.error;
    if (exitCode === 0 || !isObject(error) || typeof error.code !== 'string'
      || !Object.hasOwn(messages, error.code) || typeof error.message !== 'string'
      || typeof error.retryable !== 'boolean') throw new ExecutionError('INVALID_PROTOCOL');
    // The code selects a local message; raw upstream messages are never forwarded.
    throw new ExecutionError(error.code as ErrorCode);
  }
  if (exitCode !== 0) throw new ExecutionError('PROCESS_EXIT');
  if (response.ok !== true || !['succeeded', 'queued', 'running'].includes(String(response.status))
    || !isObject(response.data) || !Array.isArray(response.artifacts) || response.artifacts.length > 16
    || !isObject(response.meta) || typeof response.meta.durationMs !== 'number'
    || !Number.isFinite(response.meta.durationMs) || response.meta.durationMs < 0) {
    throw new ExecutionError('INVALID_PROTOCOL');
  }
  for (const artifact of response.artifacts) {
    if (!isObject(artifact) || typeof artifact.relativePath !== 'string'
      || typeof artifact.fileName !== 'string' || typeof artifact.mimeType !== 'string') {
      throw new ExecutionError('INVALID_PROTOCOL');
    }
  }
  if (response.status !== 'succeeded' && (typeof response.data.taskId !== 'string' || !response.data.taskId)) {
    throw new ExecutionError('INVALID_PROTOCOL');
  }
  // Reconstruct the envelope; unrecognized metadata cannot leak paths or diagnostics.
  return {
    protocolVersion: 1, requestId, ok: true, status: response.status as Success['status'],
    data: response.data, artifacts: response.artifacts as Artifact[],
    meta: { durationMs: response.meta.durationMs },
  };
}
