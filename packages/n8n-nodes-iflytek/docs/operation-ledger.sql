-- Example business database schema. Never install this in n8n's internal database.
-- Optional: run once in your own PostgreSQL database, then wire the queries into
-- your workflow or application. iFlytek nodes do not manage this table for you.
-- Store request digests and task references, not credentials or document contents.
CREATE TABLE ifly_operation_ledger (
    scope text NOT NULL,
    skill text NOT NULL,
    operation text NOT NULL,
    operation_key text NOT NULL,
    request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
    state text NOT NULL DEFAULT 'pending_submission' CHECK (state IN (
        'pending_submission', 'submitted', 'submission_unknown', 'succeeded', 'failed'
    )),
    task_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, skill, operation, operation_key)
);

-- Execute with query parameters. Only a returned row authorizes an upstream submission.
-- INSERT INTO ifly_operation_ledger (scope, skill, operation, operation_key, request_sha256)
-- VALUES ($1, $2, $3, $4, $5)
-- ON CONFLICT (scope, skill, operation, operation_key) DO NOTHING
-- RETURNING state;

-- With no inserted row, read the existing digest/state and reject a different digest.
-- Never automatically resubmit pending_submission or submission_unknown records.
-- After receiving a task ID, update only the matching pending record:
-- UPDATE ifly_operation_ledger SET state = 'submitted', task_id = $6, updated_at = now()
-- WHERE scope = $1 AND skill = $2 AND operation = $3 AND operation_key = $4
--   AND request_sha256 = $5 AND state = 'pending_submission';
