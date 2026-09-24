import * as path from 'node:path';
import { NodeOperationError } from 'n8n-workflow';
import type {
  IDataObject, IExecuteFunctions, INodeExecutionData, INodeProperties, INodeTypeDescription,
} from 'n8n-workflow';
import { ExecutionError } from '../shared/errors';
import { executeSkill, type ItemOperation } from '../shared/executeSkill';
import { PythonRunner } from '../shared/PythonRunner';

export const credential: NonNullable<INodeTypeDescription['credentials']>[number] = {
  name: 'iflyApi', required: true,
};

export const textProperties: INodeProperties[] = [
  {
    displayName: 'Text', name: 'text', type: 'string', typeOptions: { rows: 5 },
    default: '', description: 'Text to process. Leave empty when a binary text field is selected.',
  },
  {
    displayName: 'Input Binary Field', name: 'inputBinaryField', type: 'string', default: '',
    placeholder: 'data', description: 'Optional binary property containing UTF-8 text.',
  },
];

export function runner(): PythonRunner {
  const executable = process.env.IFLYTEK_PYTHON_EXECUTABLE;
  if (!executable || !path.isAbsolute(executable)) throw new ExecutionError('INVALID_INPUT');
  const temporaryRoot = process.env.IFLYTEK_TMP_ROOT;
  if (temporaryRoot !== undefined && !path.isAbsolute(temporaryRoot)) throw new ExecutionError('INVALID_INPUT');
  return new PythonRunner({
    pythonExecutable: executable, temporaryRoot,
    chromeExecutable: process.env.IFLYTEK_CHROME_EXECUTABLE,
    ffmpegExecutable: process.env.IFLYTEK_FFMPEG_EXECUTABLE,
  });
}

function parameter(context: IExecuteFunctions, name: string, index: number, fallback: unknown = ''): unknown {
  return context.getNodeParameter(name, index, fallback);
}

export async function executeItems(
  context: IExecuteFunctions,
  build: (index: number) => ItemOperation,
): Promise<INodeExecutionData[][]> {
  let executionRunner: PythonRunner;
  try { executionRunner = runner(); }
  catch (error) {
    const message = error instanceof ExecutionError ? `${error.code}: ${error.message}` : 'INVALID_INPUT';
    throw new NodeOperationError(context.getNode(), message);
  }
  const output: INodeExecutionData[] = [];
  for (const [index] of context.getInputData().entries()) {
    try {
      output.push(await executeSkill(context, executionRunner, index, build(index)));
    } catch (error) {
      if (!context.continueOnFail()) throw error;
      const message = error instanceof Error ? error.message : 'PROCESS_EXIT: The Python process failed without a valid result.';
      output.push({ json: { error: message } as IDataObject, pairedItem: { item: index } });
    }
  }
  return [output];
}

export function textItem(
  context: IExecuteFunctions, index: number, skill: string, operation: string,
  parameters: IDataObject = {},
): ItemOperation {
  const textValue = parameter(context, 'text', index);
  const binaryValue = parameter(context, 'inputBinaryField', index);
  const binary = typeof binaryValue === 'string' ? binaryValue.trim() : '';
  const input: IDataObject = {};
  if (typeof textValue === 'string' && textValue.length > 0) input.text = textValue;
  return {
    skill, operation, input, parameters,
    binaryInputs: binary && input.text === undefined ? { text: binary } : undefined,
  };
}

export function getString(context: IExecuteFunctions, name: string, index: number, fallback: string): string {
  const value = parameter(context, name, index, fallback);
  return typeof value === 'string' ? value : fallback;
}

export function getOperation(context: IExecuteFunctions, index: number, fallback: string, allowed: string[]): string {
  const value = parameter(context, 'operation', index, fallback);
  if (typeof value !== 'string' || !allowed.includes(value)) {
    throw new NodeOperationError(context.getNode(), 'UNSUPPORTED_OPERATION: This operation is not enabled.', { itemIndex: index });
  }
  return value;
}

export function getNumber(context: IExecuteFunctions, name: string, index: number, fallback: number): number {
  const value = parameter(context, name, index, fallback);
  return typeof value === 'number' ? value : fallback;
}
