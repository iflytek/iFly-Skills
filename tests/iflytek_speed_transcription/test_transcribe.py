#!/usr/bin/env python3
'''Offline regression tests for iflytek-speed-transcription.'''

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / 'skills'
    / 'iflytek-speed-transcription'
    / 'scripts'
    / 'transcribe.py'
)
SPEC = importlib.util.spec_from_file_location(
    'iflytek_speed_transcription_transcribe', SCRIPT_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f'Unable to load transcription module from {SCRIPT_PATH}')
transcribe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = transcribe
SPEC.loader.exec_module(transcribe)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class SpeedTranscriptionRegressionTests(unittest.TestCase):
    def setUp(self):
        self.client = transcribe.XfeiSpeedTranscription(
            'test-app-id', 'test-api-key', 'test-api-secret'
        )

    def test_exact_multiple_of_five_mib_uploads_every_full_chunk(self):
        chunk_size = 5 * 1024 * 1024
        chunk_markers = [b'A', b'B', b'C', b'D', b'E', b'F']
        captured_chunks = []

        def capture_multipart(fields):
            chunk_data = fields['data'][1]
            captured_chunks.append(
                (
                    fields['slice_id'],
                    len(chunk_data),
                    chunk_data[:1],
                    chunk_data[-1:],
                    hashlib.sha256(chunk_data).hexdigest(),
                )
            )
            return b'encoded-multipart', 'multipart/form-data; boundary=test'

        def fake_call_api(url, _body, _content_type):
            if url.endswith(self.client.mpupload_init):
                return {'code': 0, 'data': {'upload_id': 'upload-123'}}
            if url.endswith(self.client.mpupload_upload):
                return {'code': 0}
            if url.endswith(self.client.mpupload_complete):
                return {'code': 0, 'data': {'url': 'https://example.test/audio'}}
            self.fail(f'Unexpected API URL: {url}')

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / 'exact-multiple.mp3'
            with file_path.open('wb') as audio_file:
                for marker in chunk_markers:
                    audio_file.write(marker * chunk_size)

            with (
                mock.patch.object(
                    transcribe,
                    'encode_multipart_formdata',
                    side_effect=capture_multipart,
                ),
                mock.patch.object(
                    self.client, '_call_api', side_effect=fake_call_api
                ),
                redirect_stdout(io.StringIO()),
            ):
                result_url = self.client.upload_large_file(file_path)

        self.assertEqual(result_url, 'https://example.test/audio')
        self.assertEqual(
            [item[0] for item in captured_chunks],
            list(range(1, len(chunk_markers) + 1)),
        )
        self.assertEqual(
            [item[1] for item in captured_chunks],
            [chunk_size] * len(chunk_markers),
        )
        self.assertEqual(
            [(item[2], item[3]) for item in captured_chunks],
            [(marker, marker) for marker in chunk_markers],
        )
        self.assertEqual(
            [item[4] for item in captured_chunks],
            [
                hashlib.sha256(marker * chunk_size).hexdigest()
                for marker in chunk_markers
            ],
        )

    def test_digest_uses_real_body_and_has_one_prefix(self):
        body = json.dumps(
            {'common': {'app_id': 'test-app-id'}, 'business': {'task_id': '42'}},
            separators=(',', ':'),
        ).encode('utf-8')

        headers = self.client._assemble_auth_header(
            'https://ost-api.xfyun.cn/v2/ost/query',
            'application/json',
            body=body,
        )

        expected_digest = 'SHA-256=' + base64.b64encode(
            hashlib.sha256(body).digest()
        ).decode('ascii')
        self.assertEqual(headers['digest'], expected_digest)
        self.assertEqual(headers['digest'].count('SHA-256='), 1)
        self.assertNotIn('SHA-256=SHA-256=', headers['digest'])

        response_date = headers['date']
        signature_origin = (
            'host: ost-api.xfyun.cn\n'
            f'date: {response_date}\n'
            'POST /v2/ost/query HTTP/1.1\n'
            f'digest: {expected_digest}'
        )
        expected_signature = base64.b64encode(
            hmac.new(
                b'test-api-secret',
                signature_origin.encode('utf-8'),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode('ascii')
        self.assertIn(
            f'signature={chr(34)}{expected_signature}{chr(34)}',
            headers['authorization'],
        )

    def test_action_query_routes_existing_task_without_file_path(self):
        fake_client = mock.Mock()
        parsed_result = {'task_id': 'task-123', 'text': 'done'}

        with (
            mock.patch.object(
                sys,
                'argv',
                [
                    'transcribe.py',
                    '--action',
                    'query',
                    '--task-id',
                    'task-123',
                    '--poll-interval',
                    '1',
                ],
            ),
            mock.patch.object(
                transcribe,
                'load_config',
                return_value=('app', 'key', 'secret'),
            ),
            mock.patch.object(
                transcribe,
                'XfeiSpeedTranscription',
                return_value=fake_client,
            ),
            mock.patch.object(
                transcribe,
                'wait_for_result',
                return_value=parsed_result,
            ) as wait_mock,
            mock.patch.object(
                transcribe, 'write_or_print_result'
            ) as output_mock,
            redirect_stdout(io.StringIO()),
        ):
            transcribe.main()

        wait_mock.assert_called_once_with(fake_client, 'task-123', 1)
        output_mock.assert_called_once_with(parsed_result, 'text', None)
        fake_client.transcribe.assert_not_called()

    def test_query_business_error_is_not_reported_as_query_failure(self):
        response = FakeResponse({'code': 10043, 'message': 'audioCoding decode fail'})

        with mock.patch.object(transcribe.requests, 'post', return_value=response):
            with self.assertRaises(transcribe.ApiBusinessError) as raised:
                self.client.query_task('task-123')

        message = str(raised.exception)
        self.assertIn('Transcription task failed:', message)
        self.assertNotIn('Query failed:', message)
        self.assertNotIsInstance(raised.exception, transcribe.ApiTransportError)

    def test_query_transport_error_uses_transport_exception(self):
        with mock.patch.object(
            transcribe.requests,
            'post',
            side_effect=transcribe.RequestException('connection unavailable'),
        ):
            with self.assertRaises(transcribe.ApiTransportError) as raised:
                self.client.query_task('task-123')

        message = str(raised.exception)
        self.assertIn('Query request failed:', message)
        self.assertNotIn('Transcription task failed:', message)
        self.assertNotIsInstance(raised.exception, transcribe.ApiBusinessError)

    def test_create_business_error_is_wrapped_only_once(self):
        response = FakeResponse({'code': 90001, 'message': 'invalid request'})

        with mock.patch.object(transcribe.requests, 'post', return_value=response):
            with self.assertRaises(transcribe.ApiBusinessError) as raised:
                self.client.create_task('https://example.test/audio.mp3')

        message = str(raised.exception)
        self.assertEqual(message.count('Create task failed:'), 1)
        self.assertIn('invalid request', message)
        self.assertNotIsInstance(raised.exception, transcribe.ApiTransportError)

    def test_failed_transcription_task_is_not_a_query_failure(self):
        fake_client = mock.Mock()
        fake_client.query_task.return_value = {
            'code': 0,
            'data': {
                'task_status': '-1',
                'message': '10043 / audioCoding decode fail',
            },
        }

        with self.assertRaises(transcribe.ApiBusinessError) as raised:
            transcribe.wait_for_result(fake_client, 'task-123', poll_interval=1)

        message = str(raised.exception)
        self.assertIn('Transcription task failed:', message)
        self.assertNotIn('Query failed:', message)
        fake_client.query_task.assert_called_once_with('task-123')


if __name__ == '__main__':
    unittest.main()
