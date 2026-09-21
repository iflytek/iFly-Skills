import { NodeOperationError } from 'n8n-workflow';
import type { IDataObject, IExecuteFunctions, INodeExecutionData } from 'n8n-workflow';
import type { InputFile } from './binaryFiles';
import type { Credentials } from './credentialEnv';
import { ExecutionError, safeError } from './errors';
import { operationDefinition } from './operationManifest';
import { PythonRunner, type RunRequest } from './PythonRunner';

export interface ItemOperation {
  skill: string; operation: string; input?: RunRequest['input']; parameters?: RunRequest['parameters'];
  binaryInputs?: Record<string, string>; outputBinaryPrefix?: string;
}
// Called once per item by future node classes. Default errors propagate through
// n8n; continueOnFail is intentionally the node's responsibility.
export async function executeSkill(
  context: IExecuteFunctions, runner: PythonRunner, itemIndex: number, item: ItemOperation,
): Promise<INodeExecutionData> {
  try {
    if (!Number.isSafeInteger(itemIndex) || itemIndex < 0) throw new ExecutionError('INVALID_INPUT');
    const signal = context.getExecutionCancelSignal();
    if (signal?.aborted) throw new ExecutionError('EXECUTION_CANCELLED');
    const operation = await operationDefinition(runner.runtimeRoot, item.skill, item.operation);
    let credentials: Credentials | undefined;
    if (operation.credentials.length) {
      try { credentials = await context.getCredentials('iflyApi', itemIndex) as Credentials; }
      catch { throw new ExecutionError('AUTH_FAILED'); }
    }
    const prefix = item.outputBinaryPrefix ?? 'data';
    if (!/^[a-zA-Z][a-zA-Z0-9_]{0,63}$/.test(prefix)) throw new ExecutionError('INVALID_INPUT');
    const files: Record<string, InputFile> = Object.create(null);
    if (Object.keys(item.binaryInputs ?? {}).length > 16) throw new ExecutionError('INVALID_INPUT');
    let total = 0;
    for (const [name, property] of Object.entries(item.binaryInputs ?? {})) {
      let data: Buffer;
      try { data = await context.helpers.getBinaryDataBuffer(itemIndex, property); }
      catch { throw new ExecutionError('BINARY_IO'); }
      total += data.length;
      if (total > 64 * 1024 * 1024) throw new ExecutionError('INVALID_INPUT');
      files[name] = { data };
    }
    return await runner.run({ ...item, credentials, files, signal }, async (result, artifacts) => {
      const output: INodeExecutionData = { json: result as unknown as IDataObject, pairedItem: { item: itemIndex } };
      if (artifacts.length) {
        output.binary = {};
        for (const [index, artifact] of artifacts.entries()) {
          try {
            output.binary[index === 0 ? prefix : `${prefix}${index + 1}`] =
              await context.helpers.prepareBinaryData(artifact.data, artifact.fileName, artifact.mimeType);
          } catch { throw new ExecutionError('BINARY_IO'); }
        }
      }
      return output;
    });
  } catch (error) {
    const safe = safeError(error);
    throw new NodeOperationError(context.getNode(), `${safe.code}: ${safe.message}`, {
      itemIndex, description: safe.requestId ? `Request ID: ${safe.requestId}` : undefined,
    });
  }
}
