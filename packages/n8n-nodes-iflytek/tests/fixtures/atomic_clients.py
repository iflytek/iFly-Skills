"""Exercise real packaged Skill clients through bridge adapters with offline transports."""
import base64
import hashlib
import hmac
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack, redirect_stderr
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

RUNTIME = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location('bridge', RUNTIME / 'bridge/bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
load_module = bridge.load_packaged_module


def encoded(value):
    return base64.b64encode(value.encode()).decode()


class Response:
    status_code = 200
    def __init__(self, value):
        self.value = value
    def json(self):
        return self.value
    def read(self):
        return json.dumps(self.value).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class Socket:
    def __init__(self, status):
        self.frames = iter([json.dumps({'header': {'code': 0}, 'payload': {
            'audio': {'status': status, 'audio': encoded('audio bytes')}}})])
        self.closed = False
    def send(self, data):
        self.request = json.loads(data)
    def recv(self):
        return next(self.frames, '')
    def close(self):
        self.closed = True


class AtomicClients(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='ifly-atomic-test-')))
        self.stack.enter_context(patch.dict(os.environ, {
            'TMP': str(self.root), 'IFLY_APP_ID': 'app', 'IFLY_API_KEY': 'key', 'IFLY_API_SECRET': 'secret'}))
        self.stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('Unexpected network')))
        self.modules = {}
        self.original_definitions = []
        self.stack.enter_context(patch.object(bridge, 'load_packaged_module', side_effect=self.module))
    def module(self, name):
        if name not in self.modules:
            module = load_module(name)
            self.modules[name] = module
            for key, value in vars(module).items():
                if isinstance(value, (types.FunctionType, type)):
                    self.original_definitions.append((module, key, value))
                    if isinstance(value, type) and value.__module__ == module.__name__:
                        for member, definition in vars(value).items():
                            if isinstance(definition, types.FunctionType):
                                self.original_definitions.append((value, member, definition))
        return self.modules[name]
    def tearDown(self):
        for owner, name, definition in self.original_definitions:
            self.assertIs(getattr(owner, name), definition, f'Adapter changed original {name}')
    def client(self, skill, script):
        return self.module(f'skills/{skill}/scripts/{script}.py')
    def request(self, parameters=None, text='hello', files=None):
        return {'input': {'files': files} if files is not None else {'text': text}, 'parameters': parameters or {}}
    def file(self, name, data):
        (self.root / name).write_bytes(data)
        return name
    def failed(self, action):
        with self.assertRaises(bridge.BridgeError) as caught:
            action()
        self.assertEqual(caught.exception.code, 'UPSTREAM_ERROR')
    def signature(self, url, method='POST'):
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        self.assertEqual(query['host'], [parts.netloc])
        origin = f"host: {parts.netloc}\ndate: {query['date'][0]}\n{method} {parts.path} HTTP/1.1"
        signature = base64.b64encode(hmac.new(b'secret', origin.encode(), hashlib.sha256).digest()).decode()
        self.assertIn(signature, base64.b64decode(query['authorization'][0]).decode())

    def test_image_ocr_real_signing_payload_and_error(self):
        module = self.client('iflytek-pdf-image-ocr', 'image_ocr')
        request = self.request({'resultFormat': 'markdown'}, files={'image': self.file('image', b'\x89PNG\r\n\x1a\nimage')})
        def post(url, **kwargs):
            self.signature(url)
            body = kwargs['json']
            self.assertEqual(body['header']['app_id'], 'app')
            self.assertEqual(body['payload']['image']['encoding'], 'png')
            self.assertEqual(body['parameter']['ocr']['result_format'], 'markdown')
            return Response({'header': {'code': 0}, 'payload': {'result': {'text': encoded('recognized')}}})
        with patch.object(module.requests, 'post', side_effect=post):
            data, _ = bridge.recognize_image(request)
        self.assertEqual(data['result']['text'], 'recognized')
        with patch.object(module.requests, 'post', return_value=Response({'header': {'code': 1}})):
            self.failed(lambda: bridge.recognize_image(request))

    def test_pdf_binary_path_url_and_query_use_real_client(self):
        module = self.client('iflytek-pdf-image-ocr', 'pdf_ocr')
        seen = []
        def post(url, **kwargs):
            seen.append(kwargs)
            self.assertTrue(url.endswith('/start'))
            self.assertEqual(kwargs['headers']['appId'], 'app')
            stamp = kwargs['headers']['timestamp']
            digest = hashlib.md5(('app' + stamp).encode()).hexdigest()
            signature = base64.b64encode(hmac.new(b'secret', digest.encode(), hashlib.sha1).digest()).decode()
            self.assertEqual(kwargs['headers']['signature'], signature)
            return Response({'flag': True, 'data': {'taskNo': 'pdf-task', 'status': 'WAITING'}})
        request = self.request({'exportFormat': 'markdown'}, files={'pdf': self.file('pdf', b'%PDF-1.7 test')})
        with patch.object(module.requests, 'post', side_effect=post):
            self.assertEqual(bridge.create_pdf_task(request)[0]['taskNo'], 'pdf-task')
            bridge.create_pdf_task(self.request({'pdfUrl': 'https://example.invalid/a.pdf'}))
        self.assertEqual(seen[0]['files']['file'], ('pdf-input.pdf', b'%PDF-1.7 test', 'application/pdf'))
        self.assertIsNone(seen[1]['files'])
        self.assertEqual(seen[1]['data']['pdfUrl'], 'https://example.invalid/a.pdf')
        with patch.object(module.requests, 'get', return_value=Response({'flag': True, 'data': {'status': 'FINISH'}})) as get:
            for operation in ['getPdfTask', 'getResult']:
                result, _ = bridge.OPERATIONS[('iflytek-pdf-image-ocr', operation)](self.request({'taskNo': 'pdf-task'}))
                self.assertTrue(result['completed'])
                self.assertEqual(get.call_args.kwargs['params'], {'taskNo': 'pdf-task'})
        with patch.object(module.requests, 'post', return_value=Response({'flag': False, 'code': 1})):
            self.failed(lambda: bridge.create_pdf_task(request))

    def test_translation_real_body_digest_and_result(self):
        module = self.client('iflytek-translate', 'translate')
        def http(request, **kwargs):
            body = json.loads(request.data)
            self.assertEqual(body['business'], {'from': 'cn', 'to': 'en'})
            self.assertEqual(base64.b64decode(body['data']['text']).decode(), '你好')
            self.assertEqual(request.get_header('Digest'), 'SHA-256=' + base64.b64encode(hashlib.sha256(request.data).digest()).decode())
            return Response({'code': 0, 'data': {'result': {'from': 'cn', 'to': 'en',
                'trans_result': {'src': '你好', 'dst': 'hello'}}}})
        with patch.object(module.urllib.request, 'urlopen', side_effect=http):
            result, _ = bridge.translate(self.request({'fromLanguage': 'zh'}, text='你好'))
        self.assertEqual(result['translatedText'], 'hello')

    def test_proofread_real_response_and_nested_service_errors(self):
        module = self.client('iflytek-text-proofread', 'text_proofread')
        for code in [200, 500]:
            def http(request, **kwargs):
                self.signature(request.full_url)
                self.assertEqual(request.get_header('Host'), urlsplit(request.full_url).netloc)
                self.assertEqual(base64.b64decode(json.loads(request.data)['payload']['text']['text']).decode(), 'hello')
                return Response({'header': {'code': 0}, 'payload': {'output_result': {
                    'text': encoded(json.dumps({'code': code, 'data': {'checklist': []}}))}}})
            with patch.object(module.urllib.request, 'urlopen', side_effect=http):
                if code == 200:
                    self.assertEqual(bridge.proofread(self.request())[0]['result']['code'], 200)
                else:
                    self.failed(lambda: bridge.proofread(self.request()))

    def test_invoice_real_pdf_encoding_and_result_parser(self):
        module = self.client('iflytek-ocr-invoice', 'invoice')
        request = self.request(files={'image': self.file('invoice', b'%PDF-1.7 test')})
        def http(req, **kwargs):
            self.signature(req.full_url)
            self.assertEqual(json.loads(req.data)['payload']['image']['encoding'], 'pdf')
            return Response({'header': {'code': 0}, 'payload': {'output_text_result': {'text': encoded('{"total":12}')}}})
        with patch.object(module.urllib.request, 'urlopen', side_effect=http):
            self.assertEqual(bridge.recognize_invoice(request)[0]['result']['total'], 12)

    def test_invoice_http_and_connection_errors_are_upstream_failures(self):
        module = self.client('iflytek-ocr-invoice', 'invoice')
        request = self.request(files={'image': self.file('invoice', b'%PDF-1.7 test')})
        failures = [
            module.urllib.error.HTTPError('https://example.invalid/invoice', 500, 'server error',
                                          None, io.BytesIO(b'{"header":{"code":11201}}')),
            module.urllib.error.URLError('connection failed'),
        ]
        for failure in failures:
            with self.subTest(type=type(failure).__name__), redirect_stderr(io.StringIO()), \
                    patch.object(module.urllib.request, 'urlopen', side_effect=failure):
                self.failed(lambda: bridge.recognize_invoice(request))

    def test_hyper_tts_final_frame_required_and_no_temporary_output_path(self):
        module = self.client('iflytek-hyper-tts', 'xfei_hyper_tts')
        for status in [1, 2]:
            socket = Socket(status)
            with patch.object(module.websocket, 'create_connection', return_value=socket):
                if status == 1:
                    self.failed(lambda: bridge.synthesize(self.request()))
                    self.assertFalse((self.root / 'speech.mp3').exists())
                else:
                    data, artifacts = bridge.synthesize(self.request())
                    self.assertNotIn('output_path', data)
                    self.assertEqual((self.root / artifacts[0]['relativePath']).read_bytes(), b'audio bytes')
            self.assertTrue(socket.closed)
            self.assertEqual(socket.request['header']['app_id'], 'app')

    def test_image_understanding_real_frames_and_interrupted_result(self):
        module = self.client('iflytek-image-understanding', 'image_understanding')
        request = self.request({'question': 'What is shown?'}, files={'image': self.file('image', b'\xff\xd8\xffimage')})
        for status in [1, 2]:
            def communicate(url, message):
                self.signature(url, 'GET')
                self.assertEqual(json.loads(message)['payload']['message']['text'][1]['content'], 'What is shown?')
                return [json.dumps({'header': {'code': 0}, 'payload': {'choices': {'status': status, 'text': [{'content': 'description'}]}}})]
            with patch.object(module, 'ws_communicate', side_effect=communicate):
                if status == 1:
                    self.failed(lambda: bridge.analyze_image(request))
                else:
                    self.assertEqual(bridge.analyze_image(request)[0]['text'], 'description')

    def test_transcription_real_upload_task_query_and_single_digest_prefix(self):
        module = self.client('iflytek-speed-transcription', 'transcribe')
        request = self.request(files={'audio': self.file('audio', b'MP3 input')})
        def post(url, **kwargs):
            self.assertEqual(kwargs['headers']['digest'].count('SHA-256='), 1)
            if url.endswith('/file/upload'):
                return Response({'code': 0, 'data': {'url': 'https://example.invalid/a.mp3'}})
            body = json.loads(kwargs['data'])
            self.assertEqual(body['common']['app_id'], 'app')
            if url.endswith('/pro_create'):
                self.assertEqual(body['data']['encoding'], 'lame')
                return Response({'code': 0, 'data': {'task_id': 'task'}})
            self.assertEqual(body['business']['task_id'], 'task')
            return Response({'code': 0, 'data': {'task_id': 'task', 'task_status': '3', 'result': {'lattice': []}}})
        with patch.object(module.requests, 'post', side_effect=post):
            self.assertEqual(bridge.create_transcription_task(request)[0]['taskId'], 'task')
            self.assertEqual(bridge.get_transcription_task(self.request({'taskId': 'task'}))[0]['status'], '3')
            self.assertEqual(bridge.get_transcription_result(self.request({'taskId': 'task'}))[0]['segments'], [])

    def test_transcription_exact_multiple_chunk_upload_retains_final_bytes(self):
        module = self.client('iflytek-speed-transcription', 'transcribe')
        client = bridge.skill_compat.transcription_client(module, 'app', 'key', 'secret')
        client.chunk_size = 4
        chunks = []
        def post(url, **kwargs):
            if url.endswith('/upload'):
                header = ('Content-Type: ' + kwargs['headers']['content-type'] + '\r\n\r\n').encode()
                message = BytesParser(policy=policy.default).parsebytes(header + kwargs['data'])
                chunks.extend(part.get_payload(decode=True) for part in message.iter_parts() if part.get_param('name', header='content-disposition') == 'data')
            return Response({'code': 0, 'data': {'upload_id': 'upload', 'url': 'https://example.invalid/a.mp3'}})
        self.file('audio', b'abcdefgh')
        with patch.object(module.requests, 'post', side_effect=post):
            client.upload_large_file(self.root / 'audio')
        self.assertEqual(chunks, [b'abcd', b'efgh'])

    def test_video_all_operations_use_real_paths_and_parameters(self):
        module = self.client('iflytek-video-translate', 'xfei_video_translate')
        seen = []
        def http(method, url, **kwargs):
            self.signature(url, method)
            seen.append((method, urlsplit(url).path, json.loads(kwargs['data']) if 'data' in kwargs else None))
            return Response({'code': 0, 'data': {'taskId': 'video-task'}})
        with patch.object(module.requests, 'post', side_effect=lambda url, **kw: http('POST', url, **kw)), \
                patch.object(module.requests, 'get', side_effect=lambda url, **kw: http('GET', url, **kw)):
            bridge.video_create_task(self.request({'fileUrl': 'https://example.invalid/video.mp4'}))
            bridge.video_list_tasks({'input': {}, 'parameters': {}})
            bridge.video_get_task(self.request({'taskId': 'video-task'}))
            bridge.video_confirm_transcript(self.request({'taskId': 'video-task', 'forceRerun': True}))
        self.assertEqual([row[0] for row in seen], ['POST', 'GET', 'GET', 'POST'])
        self.assertTrue(seen[-1][1].endswith('/tasks/video-task/segments/transcript/confirm'))
        self.assertEqual(seen[-1][2], {'force_rerun': True})
        self.assertEqual(seen[0][2]['file_url'], 'https://example.invalid/video.mp4')

    def test_voice_training_real_endpoints_and_binary_submission_confirmation(self):
        module = self.client('iflytek-voiceclone-tts', 'voiceclone')
        seen = []
        def http(request, **kwargs):
            if request.full_url == module.AUTH_TOKEN_URL:
                self.assertEqual(json.loads(request.data)['base']['appid'], 'app')
                return Response({'retcode': '000000', 'accesstoken': 'token'})
            seen.append(request)
            self.assertEqual(request.get_header('X-appid'), 'app')
            self.assertEqual(request.get_header('X-token'), 'token')
            return Response({'code': 0, 'flag': True, 'data': {'trainStatus': 1, 'assetId': 'resource'}})
        with patch.object(module.urllib.request, 'urlopen', side_effect=http):
            for operation in ['getTrainingText', 'createTraining', 'submitTraining', 'getTraining']:
                bridge.OPERATIONS[('iflytek-voiceclone-tts', operation)](self.request({'taskId': 901}))
            data, _ = bridge.voice_upload_sample(self.request({'taskId': 901, 'audioUrl': 'https://example.invalid/a.wav'}))
            self.assertFalse(data['trainingSubmitted'])
            self.assertTrue(seen[-1].full_url.endswith('/audio/v1/add'))
            request = self.request({'taskId': 901}, files={'audio': self.file('audio', b'RIFF-sample')})
            count = len(seen)
            with self.assertRaises(bridge.BridgeError) as caught:
                bridge.voice_upload_sample(request)
            self.assertEqual(caught.exception.code, 'INVALID_INPUT')
            self.assertEqual(len(seen), count)
            request['parameters']['confirmBinarySubmission'] = True
            self.assertTrue(bridge.voice_upload_sample(request)[0]['trainingSubmitted'])
            self.assertTrue(seen[-1].full_url.endswith('/task/submitWithAudio'))
            self.assertIn(b'RIFF-sample', seen[-1].data)

    def test_voice_training_failed_business_response_is_not_success(self):
        module = self.client('iflytek-voiceclone-tts', 'voiceclone')
        def http(request, **kwargs):
            return Response({'retcode': '000000', 'accesstoken': 'token'} if request.full_url == module.AUTH_TOKEN_URL
                            else {'code': 999, 'flag': False, 'data': None})
        with patch.object(module.urllib.request, 'urlopen', side_effect=http):
            self.failed(lambda: bridge.voice_get_training_text(self.request()))

    def test_voice_synthesis_requires_final_audio_and_closes_transport(self):
        module = self.client('iflytek-voiceclone-tts', 'voiceclone')
        import websocket
        for status in [1, 2]:
            socket = Socket(status)
            with patch.object(websocket, 'create_connection', return_value=socket) as connect, \
                    patch.object(module, 'SimpleWebSocket', side_effect=AssertionError('Legacy insecure transport must not run')):
                request = self.request({'resId': 'resource'})
                if status == 1:
                    self.failed(lambda: bridge.voice_synthesize(request))
                else:
                    data, artifacts = bridge.voice_synthesize(request)
                    self.assertEqual(data['bytes'], len(b'audio bytes'))
                    self.assertEqual((self.root / artifacts[0]['relativePath']).read_bytes(), b'audio bytes')
                self.signature(connect.call_args.args[0], 'GET')
                self.assertNotIn('sslopt', connect.call_args.kwargs)
                self.assertEqual(socket.request['header']['res_id'], 'resource')
            self.assertTrue(socket.closed)

    def test_voice_transport_errors_close_without_writing_audio(self):
        self.client('iflytek-voiceclone-tts', 'voiceclone')
        import websocket
        for error in [TimeoutError('timeout'), ConnectionError('disconnected')]:
            socket = Socket(1)
            with patch.object(socket, 'recv', side_effect=error), patch.object(websocket, 'create_connection', return_value=socket):
                self.failed(lambda: bridge.voice_synthesize(self.request({'resId': 'resource'})))
            self.assertTrue(socket.closed)
            self.assertFalse((self.root / 'voice-clone.mp3').exists())


if __name__ == '__main__':
    unittest.main()
