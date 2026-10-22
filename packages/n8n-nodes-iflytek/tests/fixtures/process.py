"""Failure-injection process used only by tests; excluded from npm artifacts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if '--descendant' in sys.argv:
    time.sleep(60)
    sys.exit(0)

if os.environ.get('IFLY_API_KEY') == 'early-exit':
    os.close(0)
    sys.exit(3)

request = json.load(sys.stdin)
mode = request['parameters'].get('mode', 'success')
runtime = Path(__file__).resolve().parent.parent
if mode == 'tree':
    child = subprocess.Popen([sys.executable, '-I', '-B', __file__, '--descendant'])
    (runtime / 'descendant.json').write_text(json.dumps({'pid': child.pid, 'parent': os.getpid()}))
    time.sleep(60)
if mode == 'sleep':
    time.sleep(request['parameters'].get('seconds', 60))
if mode == 'stdout_limit':
    sys.stdout.write('x' * 100000)
    sys.stdout.flush()
    time.sleep(60)
if mode == 'stderr_limit':
    sys.stderr.write('secret-do-not-forward' * 10000)
    sys.stderr.flush()
    time.sleep(60)
if mode == 'exit':
    sys.stderr.write('secret-do-not-forward')
    sys.exit(7)
if mode == 'malformed':
    sys.stdout.write('secret-do-not-forward\n{}\n{}')
    sys.exit(0)

data = {'text': 'hello 你好 🎙', 'cwd': str(Path.cwd()), 'pid': os.getpid()}
artifacts = []
if mode == 'environment':
    data = {key: os.environ.get(key) for key in (
        'IFLY_APP_ID', 'IFLY_API_KEY', 'IFLY_API_SECRET', 'XFEI_API_KEY', 'XFYUN_API_SECRET',
        'PYTHONPATH', 'NODE_OPTIONS', 'N8N_ENCRYPTION_KEY')}
if mode.startswith('artifact'):
    content = b'file-content'
    if request['input'].get('files'):
        content = Path(next(iter(request['input']['files'].values()))).read_bytes()
    Path('result.bin').write_bytes(content)
    target = 'result.bin'
    if mode == 'artifact_empty':
        Path(target).write_bytes(b'')
    if mode == 'artifact_escape':
        target = '../outside.bin'
    if mode == 'artifact_absolute':
        target = str(Path(target).resolve())
    if mode == 'artifact_hardlink':
        os.link(target, 'linked.bin')
        target = 'linked.bin'
    if mode == 'artifact_large':
        Path(target).write_bytes(b'x' * 10000)
    artifacts = [{'relativePath': target, 'fileName': 'result.txt', 'mimeType': 'text/plain'}]
    if mode == 'artifact_mime':
        artifacts[0]['mimeType'] = 'text/html'
    if mode == 'artifact_name':
        artifacts[0]['fileName'] = '../result.txt'
    if mode == 'artifact_duplicate':
        artifacts *= 2
    data = {'bytes': len(content)}

response = {'protocolVersion': 1, 'requestId': request['requestId'], 'ok': True,
            'status': 'succeeded', 'data': data, 'artifacts': artifacts, 'meta': {'durationMs': 0}}
if mode == 'wrong_id':
    response['requestId'] = 'wrong'
if mode == 'wrong_version':
    response['protocolVersion'] = 2
if mode == 'queued':
    response['status'] = 'queued'
    response['data'] = {'taskId': 'task-123'}
if mode == 'false_zero' or mode == 'business_error':
    response = {'protocolVersion': 1, 'requestId': request['requestId'], 'ok': False,
                'error': {'code': 'UPSTREAM_ERROR', 'message': 'secret-do-not-forward', 'retryable': True}}
if mode == 'invalid_utf8':
    sys.stdout.buffer.write(b'\xff')
    sys.exit(0)
encoded = json.dumps(response, ensure_ascii=False).encode('utf-8')
if mode == 'split_utf8':
    for byte in encoded:
        sys.stdout.buffer.write(bytes([byte]))
        sys.stdout.buffer.flush()
else:
    sys.stdout.buffer.write(encoded)
sys.exit(1 if mode in ('business_error', 'success_nonzero') else 0)
