// Messages are controlled locally; never expose stderr, argv, env or exception text.
export const messages = {
  INVALID_INPUT: 'Invalid input or execution configuration.',
  UNSUPPORTED_OPERATION: 'This operation is not enabled in the installed package.',
  AUTH_FAILED: 'Required iFLYTEK credentials are missing or invalid.',
  PYTHON_NOT_FOUND: 'Python could not be started. Configure an absolute Python executable path.',
  DEPENDENCY_MISSING: 'Install the Python dependencies listed in runtime/requirements/requirements-core.lock.',
  RUNTIME_MISSING: 'The packaged Python runtime is missing or invalid. Rebuild or reinstall the package.',
  PROCESS_TIMEOUT: 'The execution deadline was exceeded; no automatic retry was performed.',
  EXECUTION_CANCELLED: 'Execution was cancelled.',
  QUEUE_FULL: 'The Python execution queue is full.',
  PROCESS_EXIT: 'The Python process failed without a valid result.',
  PROCESS_IO: 'Communication with the Python process failed.',
  PROCESS_TERMINATION_FAILED: 'The child process tree could not be confirmed stopped.',
  OUTPUT_LIMIT_EXCEEDED: 'The Python output exceeded the configured size limit.',
  INVALID_PROTOCOL: 'The Python response did not satisfy the execution protocol.',
  INVALID_ARTIFACT: 'A generated file failed path, type or size validation.',
  BINARY_IO: 'The n8n binary data could not be read or stored.',
  CLEANUP_FAILED: 'The invocation directory could not be removed.',
  RATE_LIMITED: 'The upstream service rejected the request because of a rate limit.',
  UPSTREAM_ERROR: 'The upstream service reported an error.',
  SUBMISSION_UNKNOWN: 'The submission outcome is unknown. Verify its status before retrying.',
} as const;

export type ErrorCode = keyof typeof messages;
export class ExecutionError extends Error {
  readonly retryable = false;
  requestId?: string;
  constructor(readonly code: ErrorCode) {
    super(messages[code]);
    this.name = 'IflyExecutionError';
  }
}
export function safeError(error: unknown, fallback: ErrorCode = 'PROCESS_EXIT'): ExecutionError {
  return error instanceof ExecutionError ? error : new ExecutionError(fallback);
}
