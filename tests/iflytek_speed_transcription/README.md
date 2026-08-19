# Speed Transcription offline regression tests

These tests exercise upload boundaries, request authentication, CLI query
routing, and error classification without contacting the iFLYTEK API.

The multipart test creates a temporary 30 MiB binary file at runtime. No audio
fixture or real API credential is stored in the repository.

Install the isolated test dependency and run the suite from the repository
root:

```shell
python -m pip install -r tests/iflytek_speed_transcription/requirements.txt
python -m unittest discover -s tests/iflytek_speed_transcription -p 'test_*.py' -v
```
