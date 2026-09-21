"""One request per process. Only package-owned operations may load skill code."""

import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

BRIDGE_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = BRIDGE_ROOT.parent
MAX_REQUEST_BYTES = 1024 * 1024


class BridgeError(Exception):
    def __init__(self, code):
        self.code = code


class DiscardDiagnostics:
    """Do not retain or forward arbitrary upstream prints or exception details."""
    def write(self, value):
        return len(value)

    def flush(self):
        pass


def load_packaged_module(relative_path):
    target = RUNTIME_ROOT
    for part in relative_path.split('/'):
        if part in ('', '.', '..'):
            raise BridgeError('RUNTIME_MISSING')
        target = target / part
        if target.is_symlink():
            raise BridgeError('RUNTIME_MISSING')
    if not target.is_file() or not target.resolve().is_relative_to(RUNTIME_ROOT):
        raise BridgeError('RUNTIME_MISSING')
    spec = importlib.util.spec_from_file_location('ifly_packaged_skill', target)
    module = importlib.util.module_from_spec(spec)
    # Legacy modules may sys.exit when imports fail. Classify import-time exits
    # separately, without parsing the human-readable diagnostic text.
    try:
        spec.loader.exec_module(module)
    except (ImportError, SystemExit) as error:
        raise BridgeError('DEPENDENCY_MISSING') from error
    return module


def list_voices(request):
    if set(request['input']) - {'files'} or request['input'].get('files') or request['parameters']:
        raise BridgeError('INVALID_INPUT')
    skill = load_packaged_module('skills/iflytek-hyper-tts/scripts/xfei_hyper_tts.py')
    return {'defaultVoice': skill.DEFAULT_VOICE, 'freeVoices': skill.FREE_VOICES, 'voices': skill.VOICE_LIST}, []


# Enable real adapters incrementally. Test adapters are never packaged here.
OPERATIONS = {('iflytek-hyper-tts', 'listVoices'): list_voices}


def reject_constant(_value):
    raise BridgeError('INVALID_INPUT')


def main():
    started = time.monotonic()
    request_id = ''
    try:
        if len(sys.argv) != 5 or sys.argv[1] != '--skill' or sys.argv[3] != '--operation':
            raise BridgeError('INVALID_INPUT')
        payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(payload) > MAX_REQUEST_BYTES:
            raise BridgeError('INVALID_INPUT')
        request = json.loads(payload.decode('utf-8'), parse_constant=reject_constant)
        if not isinstance(request, dict) or request.get('protocolVersion') != 1:
            raise BridgeError('INVALID_INPUT')
        request_id = request.get('requestId', '')
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
            request_id = ''
            raise BridgeError('INVALID_INPUT')
        if set(request) != {'protocolVersion', 'requestId', 'input', 'parameters'}:
            raise BridgeError('INVALID_INPUT')
        if not isinstance(request['input'], dict) or not isinstance(request['parameters'], dict):
            raise BridgeError('INVALID_INPUT')
        key = (sys.argv[2], sys.argv[4])
        manifest = json.loads((BRIDGE_ROOT / 'operations.json').read_text(encoding='utf-8'))
        entry = next((entry for entry in manifest['operations']
                      if (entry['skill'], entry['operation']) == key), None)
        if manifest['protocolVersion'] != 1 or entry is None or key not in OPERATIONS:
            raise BridgeError('UNSUPPORTED_OPERATION')
        fields = {'appId': 'IFLY_APP_ID', 'apiKey': 'IFLY_API_KEY', 'apiSecret': 'IFLY_API_SECRET'}
        if any(not os.environ.get(fields[field], '').strip() for field in entry['credentials']):
            raise BridgeError('AUTH_FAILED')
        with contextlib.redirect_stdout(DiscardDiagnostics()), contextlib.redirect_stderr(DiscardDiagnostics()):
            data, artifacts = OPERATIONS[key](request)
        response = {'protocolVersion': 1, 'requestId': request_id, 'ok': True,
                    'status': 'succeeded', 'data': data, 'artifacts': artifacts,
                    'meta': {'durationMs': round((time.monotonic() - started) * 1000)}}
        encoded = json.dumps(response, ensure_ascii=False, allow_nan=False)
    except BaseException as error:
        if isinstance(error, KeyboardInterrupt):
            code = 'EXECUTION_CANCELLED'
        elif isinstance(error, BridgeError):
            code = error.code
        elif isinstance(error, ImportError):
            code = 'DEPENDENCY_MISSING'
        elif isinstance(error, (ValueError, UnicodeError)):
            code = 'INVALID_INPUT'
        else:
            code = 'PROCESS_EXIT'
        response = {'protocolVersion': 1, 'requestId': request_id, 'ok': False,
                    'error': {'code': code, 'message': code, 'retryable': False}}
        encoded = json.dumps(response, ensure_ascii=False)
        sys.stdout.write(encoded + '\n')
        return 1
    sys.stdout.write(encoded + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
