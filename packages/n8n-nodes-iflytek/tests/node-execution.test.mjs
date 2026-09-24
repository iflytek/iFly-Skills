import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const { PythonRunner } = require('../dist/shared/PythonRunner.js');
const credentials = { appId: 'offline-app', apiKey: 'offline-key', apiSecret: 'offline-secret' };
const samples = {
  IflyTranslate: ['iflytek-translate', ['translate'], { fromLanguage: 'en', toLanguage: 'cn' }],
  IflyTextProofread: ['iflytek-text-proofread', ['check']],
  IflyOcrInvoice: ['iflytek-ocr-invoice', ['recognize']],
  IflyHyperTts: ['iflytek-hyper-tts', ['synthesize', 'listVoices']],
  IflyPdfImageOcr: ['iflytek-pdf-image-ocr', ['recognizeImage', 'createPdfTask', 'getPdfTask', 'getResult'], { taskNo: 'pdf-task' }],
  IflySpeedTranscription: ['iflytek-speed-transcription', ['createTask', 'getTask', 'getResult'], { taskId: 'audio-task' }],
  IflyImageUnderstanding: ['iflytek-image-understanding', ['analyze'], { question: 'Describe this image' }],
  IflyVideoTranslate: ['iflytek-video-translate', ['createTask', 'listTasks', 'getTask', 'confirmTranscript'],
    { taskId: 'video-task', fileUrl: 'https://example.invalid/video.mp4', forceRerun: true }],
  IflyVoicecloneTts: ['iflytek-voiceclone-tts', ['getTrainingText', 'createTraining', 'uploadSample', 'submitTraining', 'getTraining', 'synthesize'],
    { taskId: 901, resId: 'voice-resource', confirmBinarySubmission: true }],
  IflyContractReview: ['iflytek-contract-intelligence-review', ['review']],
  IflyAnimatedSketch: ['animated-sketch-diagram', ['renderHtmlToGif']],
};

function fixture(t, name, values = {}, count = 1) {
  const Node = require(`../dist/nodes/${name}/${name}.node.js`)[name];
  const node = new Node();
  const defaults = Object.fromEntries(node.description.properties.map(p => [p.name, p.default]));
  const parameters = { ...defaults, text: 'test input', ...values };
  const reads = [], auth = [], calls = [];
  const before = process.env.IFLYTEK_PYTHON_EXECUTABLE;
  process.env.IFLYTEK_PYTHON_EXECUTABLE = process.execPath;
  t.after(() => {
    if (before === undefined) delete process.env.IFLYTEK_PYTHON_EXECUTABLE;
    else process.env.IFLYTEK_PYTHON_EXECUTABLE = before;
  });
  t.mock.method(PythonRunner.prototype, 'run', async (request, consume) => {
    calls.push(request);
    return consume({ protocolVersion: 1, requestId: 'offline', ok: true,
      status: 'succeeded', data: { operation: request.operation }, artifacts: [], meta: { durationMs: 0 } }, []);
  });
  const context = {
    getNode: () => ({ name, type: node.description.name, typeVersion: 1, position: [0, 0], parameters }),
    getInputData: () => Array.from({ length: count }, () => ({ json: {} })),
    getExecutionCancelSignal: () => undefined,
    getNodeParameter: (key, index, fallback) => Object.hasOwn(parameters, key) ? parameters[key] : fallback,
    getCredentials: async (type, index) => { auth.push({ type, index }); return credentials; },
    continueOnFail: () => false,
    helpers: { getBinaryDataBuffer: async (index, field) => {
      reads.push({ index, field });
      if (field !== 'data') throw new Error('No such binary property');
      return Buffer.from('binary input');
    } },
  };
  return { run: () => node.execute.call(context), context, reads, auth, calls };
}

for (const [name, [skill, operations, parameters]] of Object.entries(samples)) {
  for (const operation of operations) {
    test(`${name}.${operation} executes the registered operation with paired items`, async (t) => {
      const f = fixture(t, name, { ...parameters, operation }, 2);
      const [items] = await f.run();
      assert.equal(f.calls.length, 2);
      const local = operation === 'listVoices' || operation === 'renderHtmlToGif';
      assert.equal(f.auth.length, local ? 0 : 2);
      const binaryKey = name === 'IflyOcrInvoice' || name === 'IflyImageUnderstanding' || operation === 'recognizeImage'
        ? 'image' : operation === 'createPdfTask' ? 'pdf'
          : operation === 'uploadSample' || (name === 'IflySpeedTranscription' && operation === 'createTask') ? 'audio' : undefined;
      for (const [index, request] of f.calls.entries()) {
        assert.equal(request.skill, skill);
        assert.equal(request.operation, operation);
        assert.deepEqual(request.credentials, local ? undefined : credentials);
        assert.deepEqual(Object.keys(request.files), binaryKey ? [binaryKey] : []);
        assert.deepEqual(items[index].pairedItem, { item: index });
        assert.equal(items[index].json.data.operation, operation);
      }
      if (operation === 'uploadSample') assert.equal(f.calls[0].parameters.confirmBinarySubmission, true);
      if (operation === 'confirmTranscript') assert.equal(f.calls[0].parameters.forceRerun, true);
      if (name === 'IflyContractReview') assert.equal(f.calls[0].outputBinaryPrefix, 'report');
      if (name === 'IflyAnimatedSketch') assert.equal(f.calls[0].outputBinaryPrefix, 'image');
    });
  }
}

test('direct text takes precedence over an absent binary field in every text node', async (t) => {
  for (const name of ['IflyTranslate', 'IflyTextProofread', 'IflyHyperTts', 'IflyVoicecloneTts', 'IflyContractReview', 'IflyAnimatedSketch']) {
    await t.test(name, async (st) => {
      const f = fixture(st, name, { operation: 'synthesize', text: 'direct', inputBinaryField: 'missing' });
      await f.run();
      assert.equal(f.calls[0].input.text, 'direct');
      assert.deepEqual(f.reads, []);
    });
  }
});

test('UTF-8 binary input and contract document input map to the correct bridge fields', async (t) => {
  await t.test('text fallback', async (st) => {
    const f = fixture(st, 'IflyTranslate', { text: '', inputBinaryField: 'data' });
    await f.run();
    assert.equal(f.calls[0].input.text, undefined);
    assert.equal(f.calls[0].files.text.data.toString(), 'binary input');
  });
  await t.test('contract PDF', async (st) => {
    const f = fixture(st, 'IflyContractReview', { format: 'pdf' });
    await f.run();
    assert.deepEqual(Object.keys(f.calls[0].files), ['document']);
    assert.equal(f.calls[0].parameters.format, 'pdf');
  });
});

test('PDF and voice URLs bypass the default binary property', async (t) => {
  for (const [name, values] of [
    ['IflyPdfImageOcr', { operation: 'createPdfTask', pdfUrl: 'https://example.invalid/input.pdf' }],
    ['IflyVoicecloneTts', { operation: 'uploadSample', audioUrl: 'https://example.invalid/input.wav', taskId: 901 }],
  ]) await t.test(name, async (st) => {
    const f = fixture(st, name, values);
    f.context.helpers.getBinaryDataBuffer = () => { throw new Error('URL must bypass binary reads'); };
    await f.run();
    assert.deepEqual(Object.keys(f.calls[0].files), []);
    for (const [key, value] of Object.entries(values)) {
      if (key !== 'operation') assert.equal(f.calls[0].parameters[key], value);
    }
  });
});

test('unknown operations never fall through to a paid action', async (t) => {
  for (const name of ['IflyHyperTts', 'IflyVoicecloneTts', 'IflyPdfImageOcr', 'IflySpeedTranscription', 'IflyVideoTranslate']) {
    await t.test(name, async (st) => {
      for (const operation of ['unknown', 42]) {
        const f = fixture(st, name, { operation });
        await assert.rejects(f.run(), /UNSUPPORTED_OPERATION/);
        assert.deepEqual(f.calls, []);
        assert.deepEqual(f.auth, []);
      }
    });
  }
});
