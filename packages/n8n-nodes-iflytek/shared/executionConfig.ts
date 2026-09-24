import { ExecutionError } from './errors';

function integer(env: NodeJS.ProcessEnv, name: string, fallback: number, min: number, max: number): number {
  const raw = env[name];
  if (raw === undefined) return fallback;
  if (!/^(0|[1-9][0-9]*)$/.test(raw)) throw new ExecutionError('INVALID_INPUT');
  const value = Number(raw);
  if (!Number.isSafeInteger(value) || value < min || value > max) throw new ExecutionError('INVALID_INPUT');
  return value;
}

// Administrator settings only; read lazily so invalid settings cannot prevent node registration.
export function executionLimits(env = process.env) {
  return {
    concurrent: integer(env, 'IFLYTEK_MAX_CONCURRENT_PROCESSES', 2, 1, 16),
    queued: integer(env, 'IFLYTEK_MAX_QUEUED_REQUESTS', 32, 0, 256),
    timeoutMs: integer(env, 'IFLYTEK_TIMEOUT_MS', 120_000, 1000, 600_000),
  };
}

export function executionLogging(env = process.env): boolean {
  const value = env.IFLYTEK_LOG_EXECUTIONS ?? 'false';
  if (value !== 'true' && value !== 'false') throw new ExecutionError('INVALID_INPUT');
  return value === 'true';
}
