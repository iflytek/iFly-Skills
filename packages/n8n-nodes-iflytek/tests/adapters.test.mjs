import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cp, mkdtemp, mkdir, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const { PythonRunner } = require('../dist/shared/PythonRunner.js');
const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pythonExecutable = process.env.IFLY_TEST_PYTHON
  || spawnSync('python', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' }).stdout.trim();
const credentials = { appId: 'app', apiKey: 'key', apiSecret: 'secret' };

const fakeScripts = {
  'iflytek-translate/scripts/translate.py': `URL = 'https://example.invalid'
def _normalize_lang(value): return value
def _build_body(app, text, source, target): return text
def _build_headers(key, secret, body): return {}
def _http_post(url, body, headers): return {'ok': True}
def _parse_result(response): return ({'src': 'hello', 'dst': '你好', 'from': 'en', 'to': 'cn'}, None)
`,
  'iflytek-text-proofread/scripts/text_proofread.py': `API_URL = 'https://example.invalid'
def _build_auth_url(url, key, secret): return url
def _build_body(app, text): return {'text': text}
def _http_post(url, body, app): return {'ok': True}
def _parse_result(response): return {'code': 200, 'data': {'checklist': []}}
`,
  'iflytek-ocr-invoice/scripts/invoice.py': `def recognize_invoice(path, app, key, secret):
    assert path.endswith('.pdf')
    return {'invoice': 'raw'}
def extract_result(data): return '{"total": 12}'
`,
  'iflytek-hyper-tts/scripts/xfei_hyper_tts.py': `DEFAULT_VOICE = 'voice'
FREE_VOICES = [{'vcn': 'voice'}]
VOICE_LIST = [{'vcn': 'voice'}]
class XfeiHyperTTSClient:
    def __init__(self, app_id, api_key, api_secret): pass
    def synthesize(self, text, output_path, **kwargs):
        with open(output_path, 'wb') as stream: stream.write(b'fake-mp3')
        return {'success': True, 'text_length': len(text)}
`,
  'iflytek-pdf-image-ocr/scripts/image_ocr.py': `class IflyImageOCRClient:
    def __init__(self, app_id, api_key, api_secret):
        assert (app_id, api_key, api_secret) == ('app', 'key', 'secret')
    def ocr(self, path, result_format):
        assert path.endswith('.png')
        return {'text': 'image text', 'format': result_format}
`,
  'iflytek-pdf-image-ocr/scripts/pdf_ocr.py': `class IflyPdfOCRClient:
    def __init__(self, app_id, api_secret):
        assert (app_id, api_secret) == ('pdf-app', 'pdf-secret')
    def start_task(self, pdf_path=None, pdf_url=None, export_format='word'):
        assert pdf_path and pdf_path.name.endswith('.pdf')
        return {'flag': True, 'data': {'taskNo': 'pdf-task-1', 'status': 'WAITING', 'format': export_format}}
    def query_status(self, task_no):
        assert task_no == 'pdf-task-1'
        return {'flag': True, 'data': {'taskNo': task_no, 'status': 'FINISH', 'downloadUrl': 'https://example.invalid/result'}}
`,
  'iflytek-speed-transcription/scripts/transcribe.py': `class XfeiSpeedTranscription:
    def __init__(self, app_id, api_key, api_secret):
        assert (app_id, api_key, api_secret) == ('app', 'key', 'secret')
    def upload_small_file(self, path):
        assert str(path).endswith('.mp3')
        return 'https://example.invalid/audio.mp3'
    def upload_large_file(self, path):
        return self.upload_small_file(path)
    def create_task(self, audio_url, file_path=None, **kwargs):
        assert audio_url.endswith('.mp3')
        return 'audio-task-1'
    def query_task(self, task_id):
        assert task_id == 'audio-task-1'
        return {'code': 0, 'data': {'task_id': task_id, 'task_status': '3', 'result': {'lattice': []}}}
    def _parse_result(self, raw):
        return {'task_id': raw['data']['task_id'], 'task_status': raw['data']['task_status'], 'text': 'hello audio', 'segments': [], 'raw': raw}
`,
  'iflytek-image-understanding/scripts/image_understanding.py': `def read_image_base64(path):
    assert path.endswith('.jpg')
    return 'base64-image'
def run_understanding(app_id, api_key, api_secret, messages, domain, temperature, max_tokens, raw):
    assert (app_id, api_key, api_secret) == ('app', 'key', 'secret')
    assert messages[0]['content'] == 'base64-image'
    return 'a generated description'
`,
  'iflytek-video-translate/scripts/xfei_video_translate.py': `class XfeiVideoTranslateClient:
    def __init__(self, api_key, api_secret):
        assert (api_key, api_secret) == ('video-key', 'video-secret')
    def create_task(self, file_url, src_lang, dest_lang, task_name=None):
        assert file_url == 'https://example.invalid/video.mp4'
        return {'taskId': 'video-task-1', 'source': src_lang, 'target': dest_lang, 'name': task_name}
    def list_tasks(self):
        return {'tasks': [{'taskId': 'video-task-1'}]}
    def get_task(self, task_id):
        assert task_id == 'video-task-1'
        return {'taskId': task_id, 'status': 'DONE'}
    def confirm_transcript(self, task_id, force_rerun=False):
        return {'taskId': task_id, 'confirmed': True, 'forceRerun': force_rerun}
`,
  'iflytek-voiceclone-tts/scripts/voiceclone.py': `class TrainClient:
    def __init__(self, app_id, api_key):
        assert (app_id, api_key) == ('voice-app', 'voice-key')
    def get_training_text(self, text_id):
        return {'code': 0, 'flag': True, 'data': {'textId': text_id, 'textSegs': [{'segId': 1}]}}
    def create_task(self, **kwargs):
        assert kwargs['sex'] == 2
        return {'code': 0, 'flag': True, 'data': 901}
    def upload_audio_file(self, task_id, audio_path, text_id, seg_id):
        assert str(audio_path).endswith('.wav')
        return {'code': 0, 'flag': True, 'data': {'uploaded': True, 'taskId': task_id}}
    def upload_audio_url(self, task_id, audio_url, text_id, seg_id):
        return {'code': 0, 'flag': True, 'data': {'uploaded': True, 'url': audio_url}}
    def submit_task(self, task_id):
        return {'code': 0, 'flag': True, 'data': {'submitted': True, 'taskId': task_id}}
    def get_task_status(self, task_id):
        return {'code': 0, 'flag': True, 'data': {'trainStatus': 1, 'assetId': 'res-1'}}
class VoiceCloneSynthesizer:
    def __init__(self, app_id, api_key, api_secret, res_id, args):
        assert (app_id, api_key, api_secret, res_id, args.format) == ('voice-app', 'voice-key', 'voice-secret', 'res-1', 'mp3')
    def synthesize(self, text):
        assert text == 'hello clone'
        return b'fake-clone-mp3'
`,
};

async function fixture(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'ifly-adapter-test-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const runtimeRoot = path.join(root, 'runtime');
  const temporaryRoot = path.join(root, 'invocations');
  await mkdir(path.join(runtimeRoot, 'bridge'), { recursive: true });
  await mkdir(temporaryRoot);
  await cp(path.join(packageRoot, 'runtime/bridge/bridge.py'), path.join(runtimeRoot, 'bridge/bridge.py'));
  await cp(path.join(packageRoot, 'runtime/bridge/operations.json'), path.join(runtimeRoot, 'bridge/operations.json'));
  // This fixture isolates bridge field mapping. Real compatibility behavior is
  // covered separately by atomic-clients.test.mjs against the staged Skill files.
  await writeFile(path.join(runtimeRoot, 'bridge/skill_compat.py'), `
def image_ocr_client(module, *args): return module.IflyImageOCRClient(*args)
def transcription_client(module, *args): return module.XfeiSpeedTranscription(*args)
def proofread_post(module, *args): return module._http_post(*args)
def hyper_synthesize(module, client, **kwargs): return client.synthesize(**kwargs)
def run_understanding(module, *args, **kwargs): return module.run_understanding(*args, **kwargs)
def voice_synthesize(module, client, text): return client.synthesize(text)
`);
  for (const [relative, source] of Object.entries(fakeScripts)) {
    const target = path.join(runtimeRoot, 'skills', relative);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, source);
  }
  return { runner: new PythonRunner({ pythonExecutable, runtimeRoot, temporaryRoot, timeoutMs: 5000 }), temporaryRoot };
}

const consume = async (result, files) => ({ result, files });

test('packaged bridge adapters map text, binary, invoice, TTS, and local voices', async (t) => {
  const { runner, temporaryRoot } = await fixture(t);
  const translation = await runner.run({
    skill: 'iflytek-translate', operation: 'translate', input: { text: 'hello' },
    parameters: { fromLanguage: 'en', toLanguage: 'cn' }, credentials,
  }, consume);
  assert.equal(translation.result.data.translatedText, '你好');

  const proofread = await runner.run({
    skill: 'iflytek-text-proofread', operation: 'check', files: { text: { data: Buffer.from('文本') } },
    credentials,
  }, consume);
  assert.equal(proofread.result.data.result.code, 200);

  const invoice = await runner.run({
    skill: 'iflytek-ocr-invoice', operation: 'recognize', files: { image: { data: Buffer.from('%PDF-1.7') } },
    credentials,
  }, consume);
  assert.equal(invoice.result.data.result.total, 12);

  const tts = await runner.run({
    skill: 'iflytek-hyper-tts', operation: 'synthesize', input: { text: 'hello' }, credentials,
  }, consume);
  assert.equal(tts.files[0].mimeType, 'audio/mpeg');
  assert.equal(tts.files[0].data.toString(), 'fake-mp3');

  const voices = await runner.run({ skill: 'iflytek-hyper-tts', operation: 'listVoices' }, consume);
  assert.equal(voices.result.data.defaultVoice, 'voice');

  const imageOcr = await runner.run({
    skill: 'iflytek-pdf-image-ocr', operation: 'recognizeImage',
    files: { image: { data: Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x69, 0x6d, 0x61, 0x67, 0x65]) } },
    parameters: { resultFormat: 'json' }, credentials,
  }, consume);
  assert.equal(imageOcr.result.data.result.text, 'image text');

  const pdf = await runner.run({
    skill: 'iflytek-pdf-image-ocr', operation: 'createPdfTask',
    files: { pdf: { data: Buffer.from('%PDF-1.7 fake') } },
    parameters: { exportFormat: 'markdown' }, credentials: { appId: 'pdf-app', apiSecret: 'pdf-secret' },
  }, consume);
  assert.equal(pdf.result.data.taskNo, 'pdf-task-1');
  const pdfResult = await runner.run({
    skill: 'iflytek-pdf-image-ocr', operation: 'getResult',
    parameters: { taskNo: 'pdf-task-1' }, credentials: { appId: 'pdf-app', apiSecret: 'pdf-secret' },
  }, consume);
  assert.equal(pdfResult.result.data.completed, true);

  const transcription = await runner.run({
    skill: 'iflytek-speed-transcription', operation: 'createTask',
    files: { audio: { data: Buffer.from('fake audio') } }, parameters: { language: 'zh_cn' }, credentials,
  }, consume);
  assert.equal(transcription.result.data.taskId, 'audio-task-1');
  const transcriptionTask = await runner.run({
    skill: 'iflytek-speed-transcription', operation: 'getTask',
    parameters: { taskId: 'audio-task-1' }, credentials,
  }, consume);
  assert.equal(transcriptionTask.result.data.status, '3');
  const transcriptionResult = await runner.run({
    skill: 'iflytek-speed-transcription', operation: 'getResult',
    parameters: { taskId: 'audio-task-1' }, credentials,
  }, consume);
  assert.equal(transcriptionResult.result.data.text, 'hello audio');

  const understanding = await runner.run({
    skill: 'iflytek-image-understanding', operation: 'analyze',
    files: { image: { data: Buffer.from([0xff, 0xd8, 0xff, 0x69, 0x6d, 0x61, 0x67, 0x65]) } },
    parameters: { question: 'What is shown?', domain: 'general', temperature: 0.4, maxTokens: 128 }, credentials,
  }, consume);
  assert.equal(understanding.result.data.text, 'a generated description');

  const videoCredentials = { appId: 'unused', apiKey: 'video-key', apiSecret: 'video-secret' };
  const videoCreate = await runner.run({
    skill: 'iflytek-video-translate', operation: 'createTask',
    parameters: { fileUrl: 'https://example.invalid/video.mp4', sourceLanguage: 'en', targetLanguage: 'zh', taskName: 'demo' },
    credentials: videoCredentials,
  }, consume);
  assert.equal(videoCreate.result.data.result.taskId, 'video-task-1');
  const videoList = await runner.run({ skill: 'iflytek-video-translate', operation: 'listTasks', input: {}, parameters: {}, credentials: videoCredentials }, consume);
  assert.equal(videoList.result.data.result.tasks.length, 1);
  const videoTask = await runner.run({ skill: 'iflytek-video-translate', operation: 'getTask', parameters: { taskId: 'video-task-1' }, credentials: videoCredentials }, consume);
  assert.equal(videoTask.result.data.result.status, 'DONE');
  const confirmed = await runner.run({ skill: 'iflytek-video-translate', operation: 'confirmTranscript', parameters: { taskId: 'video-task-1', forceRerun: true }, credentials: videoCredentials }, consume);
  assert.equal(confirmed.result.data.forceRerun, true);

  const voiceTrainingCredentials = { appId: 'voice-app', apiKey: 'voice-key' };
  const trainingText = await runner.run({ skill: 'iflytek-voiceclone-tts', operation: 'getTrainingText', parameters: { textId: 5001 }, credentials: voiceTrainingCredentials }, consume);
  assert.equal(trainingText.result.data.result.data.textId, 5001);
  const training = await runner.run({ skill: 'iflytek-voiceclone-tts', operation: 'createTraining', parameters: { name: 'demo', sex: 'female', engine: 'omni_v1', language: 'cn' }, credentials: voiceTrainingCredentials }, consume);
  assert.equal(training.result.data.result.data, 901);
  const upload = await runner.run({ skill: 'iflytek-voiceclone-tts', operation: 'uploadSample', parameters: { taskId: 901, textId: 5001, segmentId: 1, audioFormat: 'wav', confirmBinarySubmission: true }, files: { audio: { data: Buffer.from('fake wav') } }, credentials: voiceTrainingCredentials }, consume);
  assert.equal(upload.result.data.result.data.uploaded, true);
  const submitted = await runner.run({ skill: 'iflytek-voiceclone-tts', operation: 'submitTraining', parameters: { taskId: 901 }, credentials: voiceTrainingCredentials }, consume);
  assert.equal(submitted.result.data.result.data.submitted, true);
  const trained = await runner.run({ skill: 'iflytek-voiceclone-tts', operation: 'getTraining', parameters: { taskId: 901 }, credentials: voiceTrainingCredentials }, consume);
  assert.equal(trained.result.data.resourceId, 'res-1');
  const clone = await runner.run({ skill: 'iflytek-voiceclone-tts', operation: 'synthesize', input: { text: 'hello clone' }, parameters: { resId: 'res-1', format: 'mp3' }, credentials: { appId: 'voice-app', apiKey: 'voice-key', apiSecret: 'voice-secret' } }, consume);
  assert.equal(clone.files[0].mimeType, 'audio/mpeg');
  assert.equal(clone.files[0].data.toString(), 'fake-clone-mp3');
  assert.deepEqual(await readdir(temporaryRoot), []);
});
