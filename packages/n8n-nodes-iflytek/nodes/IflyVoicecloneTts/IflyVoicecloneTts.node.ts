import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { credential, executeItems, getNumber, getOperation, getString, textItem, textProperties } from '../common';
import type { ItemOperation } from '../../shared/executeSkill';

export class IflyVoicecloneTts implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Voice Clone TTS', name: 'iflyVoicecloneTts', icon: 'fa:microphone', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Voice Clone TTS' },
    description: 'Manage custom voice training tasks and synthesize with a trained voice.',
    inputs: ['main'], outputs: ['main'], credentials: [credential], properties: [
      {
        displayName: 'Operation', name: 'operation', type: 'options', default: 'getTrainingText', options: [
          { name: 'Get Training Text', value: 'getTrainingText' }, { name: 'Create Training', value: 'createTraining' },
          { name: 'Upload Sample', value: 'uploadSample' }, { name: 'Submit Training', value: 'submitTraining' },
          { name: 'Get Training', value: 'getTraining' }, { name: 'Synthesize', value: 'synthesize' },
        ],
      },
      { displayName: 'Text ID', name: 'textId', type: 'number', default: 5001, displayOptions: { show: { operation: ['getTrainingText', 'uploadSample'] } } },
      {
        displayName: 'Task ID', name: 'taskId', type: 'number', default: 0,
        description: 'Training task ID.', displayOptions: { show: { operation: ['uploadSample', 'submitTraining', 'getTraining'] } },
      },
      { displayName: 'Task Name', name: 'name', type: 'string', default: 'voice_clone_task', displayOptions: { show: { operation: ['createTraining'] } } },
      {
        displayName: 'Sex', name: 'sex', type: 'options', default: 'female', options: [
          { name: 'Female', value: 'female' }, { name: 'Male', value: 'male' },
        ], displayOptions: { show: { operation: ['createTraining'] } },
      },
      { displayName: 'Engine', name: 'engine', type: 'string', default: 'omni_v1', displayOptions: { show: { operation: ['createTraining'] } } },
      {
        displayName: 'Language', name: 'language', type: 'options', default: 'cn', options: [
          { name: 'Chinese', value: 'cn' }, { name: 'English', value: 'en' }, { name: 'Japanese', value: 'jp' },
          { name: 'Korean', value: 'ko' }, { name: 'Russian', value: 'ru' },
        ], displayOptions: { show: { operation: ['createTraining'] } },
      },
      { displayName: 'Resource Name', name: 'resourceName', type: 'string', default: '', displayOptions: { show: { operation: ['createTraining'] } } },
      { displayName: 'Callback URL', name: 'callbackUrl', type: 'string', default: '', displayOptions: { show: { operation: ['createTraining'] } } },
      {
        displayName: 'Audio Binary Property', name: 'audioBinaryProperty', type: 'string', default: 'data',
        description: 'Binary sample, up to 3 MiB. Uploading a binary sample also submits training; confirmation is required.', displayOptions: { show: { operation: ['uploadSample'] } },
      },
      { displayName: 'Audio URL', name: 'audioUrl', type: 'string', default: '', description: 'When set, ignores the binary property and only adds audio. Submit Training separately.', displayOptions: { show: { operation: ['uploadSample'] } } },
      {
        displayName: 'Confirm Binary Upload and Training Submission', name: 'confirmBinarySubmission', type: 'boolean', default: false,
        description: 'Whether to allow the binary upload endpoint to submit training. Query Get Training afterward; do not submit it again.',
        displayOptions: { show: { operation: ['uploadSample'] } },
      },
      {
        displayName: 'Audio Format', name: 'audioFormat', type: 'options', default: 'wav', options: [
          { name: 'WAV', value: 'wav' }, { name: 'MP3', value: 'mp3' }, { name: 'M4A', value: 'm4a' }, { name: 'PCM', value: 'pcm' },
        ], displayOptions: { show: { operation: ['uploadSample'] } },
      },
      { displayName: 'Segment ID', name: 'segmentId', type: 'number', default: 1, displayOptions: { show: { operation: ['uploadSample'] } } },
      ...textProperties,
      { displayName: 'Resource ID', name: 'resId', type: 'string', default: '', displayOptions: { show: { operation: ['synthesize'] } } },
      { displayName: 'Output Format', name: 'format', type: 'options', default: 'mp3', options: [
        { name: 'MP3', value: 'mp3' }, { name: 'PCM', value: 'pcm' }, { name: 'Speex', value: 'speex' }, { name: 'Opus', value: 'opus' },
      ], displayOptions: { show: { operation: ['synthesize'] } } },
      { displayName: 'Volume', name: 'volume', type: 'number', default: 50, typeOptions: { minValue: 0, maxValue: 100 }, displayOptions: { show: { operation: ['synthesize'] } } },
      { displayName: 'Speed', name: 'speed', type: 'number', default: 50, typeOptions: { minValue: 0, maxValue: 100 }, displayOptions: { show: { operation: ['synthesize'] } } },
      { displayName: 'Pitch', name: 'pitch', type: 'number', default: 50, typeOptions: { minValue: 0, maxValue: 100 }, displayOptions: { show: { operation: ['synthesize'] } } },
      { displayName: 'Sample Rate', name: 'sampleRate', type: 'options', default: 24000, options: [
        { name: '8000 Hz', value: 8000 }, { name: '16000 Hz', value: 16000 }, { name: '24000 Hz', value: 24000 },
      ], displayOptions: { show: { operation: ['synthesize'] } } },
      { displayName: 'Output Binary Property', name: 'outputBinaryPrefix', type: 'string', default: 'audio', displayOptions: { show: { operation: ['synthesize'] } } },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index): ItemOperation => {
      const operation = getOperation(this, index, 'getTrainingText', [
        'getTrainingText', 'createTraining', 'uploadSample', 'submitTraining', 'getTraining', 'synthesize',
      ]);
      if (operation === 'getTrainingText') return { skill: 'iflytek-voiceclone-tts', operation, input: {}, parameters: {
        textId: getNumber(this, 'textId', index, 5001),
      } };
      if (operation === 'createTraining') return { skill: 'iflytek-voiceclone-tts', operation, input: {}, parameters: {
        name: getString(this, 'name', index, 'voice_clone_task'), sex: getString(this, 'sex', index, 'female'),
        engine: getString(this, 'engine', index, 'omni_v1'), language: getString(this, 'language', index, 'cn'),
        resourceName: getString(this, 'resourceName', index, '') || undefined,
        callbackUrl: getString(this, 'callbackUrl', index, '') || undefined,
      } };
      if (operation === 'uploadSample') {
        const binary = getString(this, 'audioBinaryProperty', index, 'data').trim();
        const audioUrl = getString(this, 'audioUrl', index, '').trim();
        return { skill: 'iflytek-voiceclone-tts', operation, input: {}, parameters: {
          taskId: getNumber(this, 'taskId', index, 0), textId: getNumber(this, 'textId', index, 5001),
          segmentId: getNumber(this, 'segmentId', index, 1), audioUrl,
          audioFormat: getString(this, 'audioFormat', index, 'wav'),
          confirmBinarySubmission: this.getNodeParameter('confirmBinarySubmission', index, false) as boolean,
        }, binaryInputs: !audioUrl && binary ? { audio: binary } : undefined };
      }
      if (operation === 'submitTraining' || operation === 'getTraining') return { skill: 'iflytek-voiceclone-tts', operation, input: {}, parameters: {
        taskId: getNumber(this, 'taskId', index, 0),
      } };
      const item = textItem(this, index, 'iflytek-voiceclone-tts', 'synthesize', {
        resId: getString(this, 'resId', index, ''), format: getString(this, 'format', index, 'mp3'),
        volume: getNumber(this, 'volume', index, 50), speed: getNumber(this, 'speed', index, 50),
        pitch: getNumber(this, 'pitch', index, 50), sampleRate: getNumber(this, 'sampleRate', index, 24000),
      });
      item.outputBinaryPrefix = getString(this, 'outputBinaryPrefix', index, 'audio');
      return item;
    });
  }
}
