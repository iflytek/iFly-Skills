"""Private process entry point; never an HTTP operation or arbitrary module loader."""

import contextlib
import json
import logging
import os
from pathlib import Path
import sys

# -I intentionally excludes cwd. Add only this fixed, repository-owned directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.catalog import Tool
from app.errors import ErrorCode, ServiceError
from app.files import FileAccessError


def main():
    try:
        data = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError()
        request = json.loads(data)
        Tool(request["skill"], request["action"])
        logging.disable(logging.CRITICAL)
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            from app.adapters import invoke
            result = invoke(request["skill"], request["action"], request["payload"])
        response = {"result": result}
    except ServiceError as exc:
        response = {"error": exc.code.value}
    except FileAccessError:
        response = {"error": ErrorCode.INVALID_REQUEST.value}
    except (ImportError, ModuleNotFoundError):
        response = {"error": ErrorCode.DEPENDENCY_UNAVAILABLE.value}
    except TimeoutError:
        response = {"error": ErrorCode.TIMEOUT.value}
    except (Exception, SystemExit):
        response = {"error": ErrorCode.UPSTREAM_ERROR.value}
    raw = json.dumps(response, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(raw) > 4 * 1024 * 1024:
        raw = b'{"error":"UPSTREAM_PROTOCOL_ERROR"}'
    sys.stdout.buffer.write(raw)


if __name__ == "__main__":
    main()
