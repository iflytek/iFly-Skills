# Voice Clone TTS offline regression tests

This directory is intentionally separate from
`tests/iflytek_speed_transcription`. It tests the Voice Clone TTS WebSocket and
training HTTP reliability fixes only.

The suite uses standard-library fakes and mocks. It does not open network
connections, wait 120 seconds, read real credentials, or retain generated audio
files.

Run it from the repository root:

```shell
python -m unittest discover -s tests/iflytek_voiceclone_tts -p 'test_*.py' -v
```
