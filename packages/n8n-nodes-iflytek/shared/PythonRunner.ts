import { randomUUID } from 'node:crypto';
import * as path from 'node:path';
import { InvocationDirectory, type InputFile, type OutputFile } from './binaryFiles';
import { credentialEnvironment, type Credentials } from './credentialEnv';
import { ExecutionError, safeError } from './errors';
import { defaultRuntimeRoot, operationDefinition, runtimeFile } from './operationManifest';
import { acquire, runProcess } from './processControl';
import { decodeResponse, isObject, type JsonObject, type Success } from './protocol';

export interface RunRequest {
  skill: string; operation: string; input?: JsonObject; parameters?: JsonObject;
  credentials?: Credentials; files?: Record<string, InputFile>; signal?: AbortSignal;
}
export interface RunnerConfig {
  // Administrator/package configuration only. Never expose these as workflow inputs.
  pythonExecutable: string; runtimeRoot?: string; temporaryRoot?: string;
  nodeExecutable?: string; chromeExecutable?: string; ffmpegExecutable?: string;
  timeoutMs?: number; stdoutBytes?: number; stderrBytes?: number; binaryBytes?: number;
}
export type ExecutionResult = Omit<Success, 'artifacts'>;
const bounded = (value: number | undefined, fallback: number, maximum: number) => {
  const result = value ?? fallback;
  if (!Number.isSafeInteger(result) || result <= 0 || result > maximum) throw new ExecutionError('INVALID_INPUT');
  return result;
};
export class PythonRunner {
  readonly runtimeRoot: string;
  private readonly timeoutMs: number;
  private readonly stdoutBytes: number;
  private readonly stderrBytes: number;
  private readonly binaryBytes: number;
  constructor(private readonly config: RunnerConfig) {
    if (!path.isAbsolute(config.pythonExecutable) || config.pythonExecutable.includes('\0')) throw new ExecutionError('INVALID_INPUT');
    this.runtimeRoot = config.runtimeRoot ?? defaultRuntimeRoot;
    this.timeoutMs = bounded(config.timeoutMs, 120_000, 600_000);
    this.stdoutBytes = bounded(config.stdoutBytes, 8 * 1024 * 1024, 8 * 1024 * 1024);
    this.stderrBytes = bounded(config.stderrBytes, 256 * 1024, 256 * 1024);
    this.binaryBytes = bounded(config.binaryBytes, 32 * 1024 * 1024, 64 * 1024 * 1024);
  }
  async run<T>(request: RunRequest, consume: (result: ExecutionResult, files: OutputFile[]) => Promise<T>): Promise<T> {
    const requestId = randomUUID();
    const controller = new AbortController();
    const abort = () => controller.abort(new ExecutionError('EXECUTION_CANCELLED'));
    request.signal?.addEventListener('abort', abort, { once: true });
    if (request.signal?.aborted) abort();
    const timer = setTimeout(() => controller.abort(new ExecutionError('PROCESS_TIMEOUT')), this.timeoutMs);
    let directory: InvocationDirectory | undefined;
    let release: (() => void) | undefined;
    const check = () => { if (controller.signal.aborted) throw controller.signal.reason; };
    try {
      check();
      const operation = await operationDefinition(this.runtimeRoot, request.skill, request.operation);
      const env = credentialEnvironment(operation.credentials, request.credentials);
      if (operation.skill === 'animated-sketch-diagram') {
        const paths = {
          IFLYTEK_NODE_EXECUTABLE: this.config.nodeExecutable ?? process.execPath,
          IFLYTEK_CHROME_EXECUTABLE: this.config.chromeExecutable,
          IFLYTEK_FFMPEG_EXECUTABLE: this.config.ffmpegExecutable,
        };
        for (const [name, value] of Object.entries(paths)) {
          if (!value || !path.isAbsolute(value) || value.includes('\0')) throw new ExecutionError('INVALID_INPUT');
          env[name] = value;
        }
      }
      const input = request.input ?? {};
      const parameters = request.parameters ?? {};
      if (!isObject(input) || !isObject(parameters) || Object.hasOwn(input, 'files')) throw new ExecutionError('INVALID_INPUT');
      release = await acquire(controller.signal);
      check();
      let bridge: string;
      try { bridge = await runtimeFile(this.runtimeRoot, 'bridge/bridge.py'); }
      catch { throw new ExecutionError('RUNTIME_MISSING'); }
      directory = await InvocationDirectory.create(this.config.temporaryRoot);
      const inputFiles = await directory.writeInputs(request.files ?? {}, this.binaryBytes);
      let bytes: Buffer;
      try {
        bytes = Buffer.from(JSON.stringify({ protocolVersion: 1, requestId,
          input: { ...input, files: inputFiles }, parameters }));
      } catch { throw new ExecutionError('INVALID_INPUT'); }
      if (bytes.length > 1024 * 1024) throw new ExecutionError('INVALID_INPUT');
      env.TMP = directory.root; env.TEMP = directory.root; env.TMPDIR = directory.root;
      check();
      const output = await runProcess({
        executable: this.config.pythonExecutable, bridge, skill: operation.skill, operation: operation.operation,
        cwd: directory.root, env, request: bytes, signal: controller.signal,
        stdoutBytes: this.stdoutBytes, stderrBytes: this.stderrBytes,
      });
      check();
      const response = decodeResponse(output.bytes, requestId, output.exitCode);
      const files = await directory.collect(response.artifacts, operation.artifactMimeTypes, this.binaryBytes);
      check();
      const { artifacts: _artifacts, ...result } = response;
      // n8n persistence completes before invocation files are removed.
      const value = await consume(result, files);
      check();
      return value;
    } catch (error) {
      const safe = safeError(error);
      safe.requestId = requestId;
      throw safe;
    } finally {
      clearTimeout(timer);
      request.signal?.removeEventListener('abort', abort);
      try { await directory?.cleanup(); }
      finally { release?.(); }
    }
  }
}
