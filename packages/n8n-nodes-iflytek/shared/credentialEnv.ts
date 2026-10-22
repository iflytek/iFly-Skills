import { ExecutionError } from './errors';

export const credentialNames = { appId: 'IFLY_APP_ID', apiKey: 'IFLY_API_KEY', apiSecret: 'IFLY_API_SECRET' } as const;
export type CredentialField = keyof typeof credentialNames;
export type Credentials = Partial<Record<CredentialField, string>>;

export function credentialEnvironment(required: CredentialField[], credentials: Credentials = {}): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {};
  // Deliberately excludes ambient credentials, Python paths, proxies and Node options.
  const allowed = new Set(['PATH', 'SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE', 'PATHEXT', 'LANG', 'LC_ALL']);
  for (const [name, value] of Object.entries(process.env)) {
    if (allowed.has(name.toUpperCase())) env[name] = value;
  }
  for (const field of required) {
    const value = credentials[field];
    if (typeof value !== 'string' || !value.trim() || value.includes('\0')) throw new ExecutionError('AUTH_FAILED');
    env[credentialNames[field]] = value;
  }
  return env;
}
