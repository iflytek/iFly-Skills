"""Package-owned compatibility for unmodified upstream Skill modules.

Subclasses and call-local globals preserve the original source and module state.
The bridge runs one request per process; these helpers never patch installed files.
"""
import base64
import hashlib
import hmac
import json
import math
from datetime import datetime, timezone
from email.utils import format_datetime
from types import FunctionType, SimpleNamespace
from urllib.parse import urlencode, urlsplit
import urllib.request


class _NoTrainingRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Signed headers and audio must never follow a redirect to another endpoint.
        raise RuntimeError('Voice training redirects are not allowed')


def voice_training_client(module, app_id, api_key):
    # Keep the Skill's signing, bodies and parsing, but use verified HTTPS only.
    # A private opener avoids changing urllib's process-wide configuration.
    opener = urllib.request.build_opener(_NoTrainingRedirect())
    overrides = {
        'AUTH_TOKEN_URL': 'https://avatar-hci.xfyousheng.com/aiauth/v1/token',
        'TRAIN_BASE_URL': 'https://opentrain.xfyousheng.com/voice_train',
        'urllib': SimpleNamespace(request=SimpleNamespace(
            Request=urllib.request.Request, urlopen=opener.open)),
    }

    class Training(module.TrainClient):
        def _get_token(self):
            return _call_with_globals(module.TrainClient._get_token, overrides, self)

        def _post(self, path, body):
            return _call_with_globals(module.TrainClient._post, overrides, self, path, body)

        def upload_audio_file(self, *args, **kwargs):
            return _call_with_globals(module.TrainClient.upload_audio_file, overrides, self, *args, **kwargs)

    return Training(app_id, api_key)


def _call_with_globals(function, overrides, *args, **kwargs):
    wrapped = FunctionType(function.__code__, {**function.__globals__, **overrides},
                           function.__name__, function.__defaults__, function.__closure__)
    wrapped.__kwdefaults__ = function.__kwdefaults__
    return wrapped(*args, **kwargs)


def image_ocr_client(module, app_id, api_key, api_secret):
    class ImageOCR(module.IflyImageOCRClient):
        def _generate_auth_url(self):
            endpoint = urlsplit(self.API_HOST)
            date = format_datetime(datetime.now(timezone.utc), usegmt=True)
            origin = f'host: {endpoint.netloc}\ndate: {date}\nPOST {endpoint.path} HTTP/1.1'
            signature = base64.b64encode(hmac.new(self.api_secret.encode(), origin.encode(), hashlib.sha256).digest()).decode()
            auth = (f'hmac username="{self.api_key}", algorithm="hmac-sha256", '
                    f'headers="host date request-line", signature="{signature}"')
            return self.API_HOST + '?' + urlencode({
                'authorization': base64.b64encode(auth.encode()).decode(), 'host': endpoint.netloc, 'date': date})
    return ImageOCR(app_id, api_key, api_secret)


def proofread_post(module, url, body, app_id):
    # Preserve the Skill's request body and response parser; match Host to its signed URL.
    request = module.urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        'Content-Type': 'application/json', 'host': urlsplit(url).netloc, 'app_id': app_id}, method='POST')
    with module.urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode('utf-8'))


def transcription_client(module, app_id, api_key, api_secret):
    class Transcription(module.XfeiSpeedTranscription):
        def _assemble_auth_header(self, requset_url, file_data_type, method='POST', body=''):
            # Sign the actual JSON or multipart bytes, independently of the
            # upstream helper's historical digest-prefix convention.
            endpoint = urlsplit(requset_url)
            date = format_datetime(datetime.now(timezone.utc), usegmt=True)
            body_bytes = body.encode('utf-8') if isinstance(body, str) else body
            digest = 'SHA-256=' + base64.b64encode(hashlib.sha256(body_bytes).digest()).decode()
            origin = f'host: {endpoint.hostname}\ndate: {date}\n{method} {endpoint.path} HTTP/1.1\ndigest: {digest}'
            signature = base64.b64encode(hmac.new(self.api_secret.encode(), origin.encode(), hashlib.sha256).digest()).decode()
            return {
                'host': endpoint.hostname, 'date': date, 'digest': digest,
                'content-type': file_data_type,
                'authorization': (f'api_key="{self.api_key}", algorithm="hmac-sha256", '
                                  f'headers="host date request-line digest", signature="{signature}"'),
            }

        def upload_large_file(self, file_path):
            request_id = self._generate_request_id()
            common = {'app_id': self.app_id, 'request_id': request_id}
            base = f'https://{self.upload_host}'

            def call(endpoint, body, content_type='application/json'):
                result = self._call_api(base + endpoint, body, content_type)
                if result.get('code') != 0:
                    raise RuntimeError('Transcription upload failed')
                return result

            result = call(self.mpupload_init, json.dumps(common))
            common['upload_id'] = result['data']['upload_id']
            size = file_path.stat().st_size
            with file_path.open('rb') as stream:
                for index in range(math.ceil(size / self.chunk_size)):
                    # read() returns the remaining bytes, including a full final chunk.
                    data = stream.read(self.chunk_size)
                    body, content_type = module.encode_multipart_formdata({
                        **common, 'slice_id': index + 1, 'data': (str(file_path), data)})
                    call(self.mpupload_upload, body, content_type)
            return call(self.mpupload_complete, json.dumps(common))['data']['url']
    return Transcription(app_id, api_key, api_secret)


class _CompleteAudioSocket:
    def __init__(self, socket):
        self.socket = socket
        self.completed = False

    def __getattr__(self, name):
        return getattr(self.socket, name)

    def recv(self):
        raw = self.socket.recv()
        if not raw:
            raise RuntimeError('Speech stream ended without a final audio frame')
        response = json.loads(raw)
        self.completed = response.get('header', {}).get('code') == 0 and response.get('payload', {}).get('audio', {}).get('status') == 2
        return raw


def hyper_synthesize(module, client, **kwargs):
    sockets = []
    def connect(*args, **options):
        socket = _CompleteAudioSocket(module.websocket.create_connection(*args, **options))
        sockets.append(socket)
        return socket
    # Reuse the original request, parser and file output with a call-local transport.
    result = _call_with_globals(module.XfeiHyperTTSClient.synthesize,
                                {'websocket': SimpleNamespace(create_connection=connect)}, client, **kwargs)
    if not sockets or not sockets[-1].completed:
        raise RuntimeError('Incomplete speech stream')
    return result


def run_understanding(module, *args, **kwargs):
    def communicate(*values, **options):
        frames = module.ws_communicate(*values, **options)
        decoded = [json.loads(frame) for frame in frames]
        if (not decoded or any(frame.get('header', {}).get('code', -1) != 0 for frame in decoded)
                or decoded[-1].get('payload', {}).get('choices', {}).get('status') != 2):
            raise RuntimeError('Incomplete image understanding result')
        return frames
    return _call_with_globals(module.run_understanding, {'ws_communicate': communicate}, *args, **kwargs)


def voice_synthesize(module, client, text):
    import websocket
    # Retain the original signed URL, request builder and response parser. The
    # package transport verifies TLS and avoids the legacy thread/timeout path.
    url = module.build_ws_auth_url(module.TTS_WS_URL, client.api_key, client.api_secret)
    socket = websocket.create_connection(url, timeout=30)
    try:
        socket.send(json.dumps(client._build_request(text)))
        while True:
            raw = socket.recv()
            if not raw:
                raise RuntimeError('Voice stream ended without a final audio frame')
            response = json.loads(raw)
            client._on_message(socket, raw)
            if client.error:
                raise RuntimeError('Voice synthesis failed')
            if response.get('payload', {}).get('audio', {}).get('status') == 2:
                return b''.join(client.audio_chunks)
    finally:
        socket.close()
