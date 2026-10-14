"""One fixed Skill call per isolated Python process; bounded IO and lifetime."""

import asyncio
import json
import os
from pathlib import Path
import signal
import shutil
import sys
import tempfile
from uuid import uuid4

from .errors import ErrorCode, ServiceError


async def terminate(process):
    if process.returncode is not None:
        return
    if os.name == "nt":
        killer = await asyncio.create_subprocess_exec(
            "taskkill", "/PID", str(process.pid), "/T", "/F",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await killer.wait()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    await process.wait()


class SkillRunner:
    def __init__(self, environment: dict[str, str]):
        self.environment = dict(environment)

    async def call(self, skill: str, action: str, payload: dict, *, timeout: float = 60) -> dict:
        child_env = {key: value for key, value in os.environ.items()
                     if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LANG"}}
        allowed = {"COZE_DATA_DIR", "COZE_ARTIFACT_BASE_URL"}
        if skill == "animated-sketch-diagram":
            allowed.add("COZE_RENDER_IMAGE")
        elif action != "list_voices":
            prefix = "IFLY_CONTRACT" if skill == "iflytek-contract-intelligence-review" else "IFLY"
            allowed.update(prefix + "_" + key for key in ("APP_ID", "API_KEY", "API_SECRET"))
        child_env.update({key: value for key, value in self.environment.items() if key in allowed})
        container = "coze-render-" + uuid4().hex if skill == "animated-sketch-diagram" else None
        if container:
            child_env["COZE_RENDER_CONTAINER_NAME"] = container
        child_env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        with tempfile.TemporaryDirectory(prefix="coze-call-") as directory:
            # Neither argv nor the working directory contains request input or credentials.
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-I", "-B", str(Path(__file__).with_name("worker.py")),
                cwd=directory, env=child_env, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                start_new_session=os.name != "nt")

            async def exchange():
                process.stdin.write(json.dumps({"skill": skill, "action": action, "payload": payload}).encode())
                await process.stdin.drain()
                process.stdin.close()
                chunks, total = [], 0
                while data := await process.stdout.read(65536):
                    total += len(data)
                    if total > 4 * 1024 * 1024:
                        raise ServiceError(ErrorCode.UPSTREAM_PROTOCOL_ERROR)
                    chunks.append(data)
                await process.wait()
                return b"".join(chunks)

            try:
                raw = await asyncio.wait_for(exchange(), timeout)
            except TimeoutError:
                raise ServiceError(ErrorCode.TIMEOUT) from None
            finally:
                await terminate(process)
                # Docker's daemon outlives its CLI. The coordinator also removes the
                # exact per-call container if cancellation killed the worker's finally.
                docker = shutil.which("docker") if container else None
                if docker:
                    cleanup = await asyncio.create_subprocess_exec(
                        docker, "rm", "-f", container, stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL, start_new_session=os.name != "nt",
                        env={k: v for k, v in child_env.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}})
                    try:
                        await asyncio.wait_for(cleanup.wait(), 15)
                    except TimeoutError:
                        await terminate(cleanup)
            try:
                response = json.loads(raw)
                if process.returncode or not isinstance(response, dict):
                    raise ValueError()
                if "error" in response:
                    raise ServiceError(ErrorCode(response["error"]))
                if not isinstance(response["result"], dict):
                    raise ValueError()
                return response["result"]
            except (KeyError, ValueError, TypeError):
                raise ServiceError(ErrorCode.UPSTREAM_PROTOCOL_ERROR) from None
