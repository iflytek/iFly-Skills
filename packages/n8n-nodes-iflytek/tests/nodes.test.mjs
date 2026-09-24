import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const nodes = [
  require('../dist/nodes/IflyTranslate/IflyTranslate.node.js').IflyTranslate,
  require('../dist/nodes/IflyTextProofread/IflyTextProofread.node.js').IflyTextProofread,
  require('../dist/nodes/IflyOcrInvoice/IflyOcrInvoice.node.js').IflyOcrInvoice,
  require('../dist/nodes/IflyHyperTts/IflyHyperTts.node.js').IflyHyperTts,
  require('../dist/nodes/IflyPdfImageOcr/IflyPdfImageOcr.node.js').IflyPdfImageOcr,
  require('../dist/nodes/IflySpeedTranscription/IflySpeedTranscription.node.js').IflySpeedTranscription,
  require('../dist/nodes/IflyImageUnderstanding/IflyImageUnderstanding.node.js').IflyImageUnderstanding,
  require('../dist/nodes/IflyVideoTranslate/IflyVideoTranslate.node.js').IflyVideoTranslate,
  require('../dist/nodes/IflyVoicecloneTts/IflyVoicecloneTts.node.js').IflyVoicecloneTts,
  require('../dist/nodes/IflyContractReview/IflyContractReview.node.js').IflyContractReview,
  require('../dist/nodes/IflyAnimatedSketch/IflyAnimatedSketch.node.js').IflyAnimatedSketch,
];

test('eleven enabled node classes expose stable n8n metadata', () => {
  const instances = nodes.map((Node) => new Node());
  assert.deepEqual(instances.map(({ description }) => description.name), [
    'iflyTranslate', 'iflyTextProofread', 'iflyOcrInvoice', 'iflyHyperTts',
    'iflyPdfImageOcr', 'iflySpeedTranscription', 'iflyImageUnderstanding',
    'iflyVideoTranslate', 'iflyVoicecloneTts',
    'iflyContractReview', 'iflyAnimatedSketch',
  ]);
  for (const { description } of instances) {
    assert.deepEqual(description.inputs, ['main']);
    assert.deepEqual(description.outputs, ['main']);
    assert.equal(description.version, 1);
  }
  assert.equal(instances[0].description.credentials[0].name, 'iflyApi');
  assert.equal(instances[1].description.credentials[0].name, 'iflyApi');
  assert.equal(instances[2].description.credentials[0].name, 'iflyApi');
  assert.equal(instances[3].description.credentials[0].name, 'iflyApi');
  assert.equal(instances[3].description.credentials[0].required, false);
  assert.deepEqual(instances[3].description.properties.find(({ name }) => name === 'operation').options.map(({ value }) => value), [
    'synthesize', 'listVoices',
  ]);
  assert.deepEqual(instances[4].description.properties.find(({ name }) => name === 'operation').options.map(({ value }) => value), [
    'recognizeImage', 'createPdfTask', 'getPdfTask', 'getResult',
  ]);
  assert.deepEqual(instances[5].description.properties.find(({ name }) => name === 'operation').options.map(({ value }) => value), [
    'createTask', 'getTask', 'getResult',
  ]);
  assert.equal(instances[6].description.properties.find(({ name }) => name === 'operation'), undefined);
  assert.equal(instances[6].description.credentials[0].name, 'iflyApi');
  assert.equal(instances[9].description.credentials[0].name, 'iflyApi');
  assert.equal(instances[10].description.credentials, undefined);
  assert.deepEqual(instances[7].description.properties.find(({ name }) => name === 'operation').options.map(({ value }) => value), [
    'createTask', 'listTasks', 'getTask', 'confirmTranscript',
  ]);
  assert.deepEqual(instances[8].description.properties.find(({ name }) => name === 'operation').options.map(({ value }) => value), [
    'getTrainingText', 'createTraining', 'uploadSample', 'submitTraining', 'getTraining', 'synthesize',
  ]);
});
