import { lstat, readFile, realpath } from 'node:fs/promises';
import * as path from 'node:path';
import { credentialNames, type CredentialField } from './credentialEnv';
import { ExecutionError } from './errors';
import { isObject } from './protocol';

export interface Operation { skill: string; operation: string; credentials: CredentialField[]; artifactMimeTypes: string[] }
export const defaultRuntimeRoot = path.resolve(__dirname, '../../runtime');
export async function runtimeFile(root: string, relative: string): Promise<string> {
  const base = await realpath(root);
  let target = base;
  for (const part of relative.split('/')) {
    if (!part || part === '.' || part === '..' || part.includes('\\') || part.includes(':')) {
      throw new ExecutionError('RUNTIME_MISSING');
    }
    target = path.join(target, part);
    if ((await lstat(target)).isSymbolicLink()) throw new ExecutionError('RUNTIME_MISSING');
  }
  if (!(await lstat(target)).isFile()) throw new ExecutionError('RUNTIME_MISSING');
  return target;
}
export async function operationDefinition(root: string, skill: string, operation: string): Promise<Operation> {
  if (!/^[a-z0-9-]+$/.test(skill) || !/^[a-zA-Z][a-zA-Z0-9]*$/.test(operation)) {
    throw new ExecutionError('UNSUPPORTED_OPERATION');
  }
  let document;
  try {
    document = JSON.parse(await readFile(await runtimeFile(root, 'bridge/operations.json'), 'utf8'));
    if (document.protocolVersion !== 1 || !Array.isArray(document.operations)) throw new Error();
    const unique = new Set();
    for (const entry of document.operations) {
      if (!isObject(entry) || typeof entry.skill !== 'string' || typeof entry.operation !== 'string'
        || !Array.isArray(entry.credentials) || !entry.credentials.every((v) => Object.hasOwn(credentialNames, String(v)))
        || !Array.isArray(entry.artifactMimeTypes) || !entry.artifactMimeTypes.every((v) => typeof v === 'string')
        || unique.has(`${entry.skill}/${entry.operation}`)) throw new Error();
      unique.add(`${entry.skill}/${entry.operation}`);
    }
  } catch { throw new ExecutionError('RUNTIME_MISSING'); }
  const entry = document.operations.find((v: Operation) => v.skill === skill && v.operation === operation);
  if (!entry) throw new ExecutionError('UNSUPPORTED_OPERATION');
  return entry;
}
