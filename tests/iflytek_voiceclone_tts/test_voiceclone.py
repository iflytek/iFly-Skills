#!/usr/bin/env python3
'''Offline regression tests for iflytek-voiceclone-tts.'''

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / 'skills'
    / 'iflytek-voiceclone-tts'
    / 'scripts'
    / 'voiceclone.py'
)
SPEC = importlib.util.spec_from_file_location(
    'iflytek_voiceclone_tts_voiceclone', SCRIPT_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f'Unable to load Voice Clone module from {SCRIPT_PATH}')
voiceclone = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = voiceclone
SPEC.loader.exec_module(voiceclone)


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode('utf-8')


class TimeoutWebSocket:
    last_instance = None

    def __init__(
        self,
        url,
        on_message=None,
        on_error=None,
        on_close=None,
        on_open=None,
    ):
        self.url = url
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.on_open = on_open
        self.close_calls = 0
        type(self).last_instance = self

    def connect(self):
        return None

    def close(self):
        self.close_calls += 1


class ClosingWithoutAudioWebSocket(TimeoutWebSocket):
    last_instance = None

    def connect(self):
        self.on_close(self)


class VoiceCloneRegressionTests(unittest.TestCase):
    def setUp(self):
        self.synth_args = SimpleNamespace(
            format='mp3',
            volume=50,
            speed=50,
            pitch=50,
            sample_rate=16000,
        )
        TimeoutWebSocket.last_instance = None
        ClosingWithoutAudioWebSocket.last_instance = None

    def make_synthesizer(self):
        return voiceclone.VoiceCloneSynthesizer(
            'test-app-id',
            'test-api-key',
            'test-api-secret',
            'test-resource-id',
            self.synth_args,
        )

    def test_tts_timeout_closes_websocket_and_raises(self):
        synthesizer = self.make_synthesizer()

        with (
            mock.patch.object(voiceclone, 'SimpleWebSocket', TimeoutWebSocket),
            mock.patch.object(
                voiceclone,
                'build_ws_auth_url',
                return_value='wss://example.test/tts',
            ),
            mock.patch.object(synthesizer.done, 'wait', return_value=False) as wait_mock,
        ):
            with self.assertRaises(TimeoutError) as raised:
                synthesizer.synthesize('timeout test')

        self.assertEqual(
            str(raised.exception),
            'TTS WebSocket timed out after 120 seconds',
        )
        wait_mock.assert_called_once_with(timeout=120)
        self.assertIsNotNone(TimeoutWebSocket.last_instance)
        self.assertEqual(TimeoutWebSocket.last_instance.close_calls, 1)
        self.assertEqual(synthesizer.audio_chunks, [])

    def test_closed_websocket_without_audio_is_an_error(self):
        synthesizer = self.make_synthesizer()

        with (
            mock.patch.object(
                voiceclone,
                'SimpleWebSocket',
                ClosingWithoutAudioWebSocket,
            ),
            mock.patch.object(
                voiceclone,
                'build_ws_auth_url',
                return_value='wss://example.test/tts',
            ),
        ):
            with self.assertRaises(RuntimeError) as raised:
                synthesizer.synthesize('empty audio test')

        self.assertEqual(str(raised.exception), 'TTS returned no audio data')
        self.assertTrue(synthesizer.done.is_set())
        self.assertEqual(synthesizer.audio_chunks, [])

    def test_http_200_json_business_errors_are_rejected(self):
        client = voiceclone.TrainClient('test-app-id', 'test-api-key')
        client.token = 'test-token'
        cases = [
            (
                {'retcode': '100001', 'message': 'training rejected'},
                '100001',
            ),
            (
                {'code': 100002, 'desc': 'invalid training request'},
                '100002',
            ),
        ]

        for payload, expected_code in cases:
            with self.subTest(payload=payload):
                response = FakeHttpResponse(payload)
                with mock.patch.object(
                    voiceclone.urllib.request,
                    'urlopen',
                    return_value=response,
                ):
                    with self.assertRaises(RuntimeError) as raised:
                        client.create_task(name='offline-test')

                message = str(raised.exception)
                self.assertIn('Training API /task/add failed', message)
                self.assertIn(f'code {expected_code}', message)
                self.assertTrue(
                    payload.get('message', payload.get('desc')) in message
                )

    def test_http_200_multipart_business_error_is_rejected(self):
        client = voiceclone.TrainClient('test-app-id', 'test-api-key')
        client.token = 'test-token'
        response = FakeHttpResponse(
            {'retcode': '100003', 'message': 'audio upload rejected'}
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / 'sample.wav'
            audio_path.write_bytes(b'RIFF-offline-test-audio')

            with mock.patch.object(
                voiceclone.urllib.request,
                'urlopen',
                return_value=response,
            ) as urlopen_mock:
                with self.assertRaises(RuntimeError) as raised:
                    client.upload_audio_file(123, str(audio_path))

        message = str(raised.exception)
        self.assertIn('Training API /task/submitWithAudio failed', message)
        self.assertIn('code 100003', message)
        self.assertIn('audio upload rejected', message)
        urlopen_mock.assert_called_once()


if __name__ == '__main__':
    unittest.main()
