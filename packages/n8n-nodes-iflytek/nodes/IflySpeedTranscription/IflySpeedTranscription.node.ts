import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { credential, executeItems, getOperation, getString } from '../common';

export class IflySpeedTranscription implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Speed Transcription', name: 'iflySpeedTranscription', icon: 'fa:microphone', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Speed Transcription' },
    description: 'Create and query iFlytek MP3 transcription tasks.',
    inputs: ['main'], outputs: ['main'], credentials: [credential], properties: [
      {
        displayName: 'Operation', name: 'operation', type: 'options', default: 'createTask', options: [
          { name: 'Create Task', value: 'createTask' }, { name: 'Get Task', value: 'getTask' },
          { name: 'Get Result', value: 'getResult' },
        ],
      },
      {
        displayName: 'Binary Property', name: 'binaryPropertyName', type: 'string', default: 'data',
        description: 'Binary property containing MP3 audio.', displayOptions: { show: { operation: ['createTask'] } },
      },
      {
        displayName: 'Task ID', name: 'taskId', type: 'string', default: '',
        description: 'Task ID returned by Create Task.', displayOptions: { show: { operation: ['getTask', 'getResult'] } },
      },
      { displayName: 'Language', name: 'language', type: 'string', default: 'zh_cn', displayOptions: { show: { operation: ['createTask'] } } },
      { displayName: 'Accent', name: 'accent', type: 'string', default: 'mandarin', displayOptions: { show: { operation: ['createTask'] } } },
      { displayName: 'Domain', name: 'domain', type: 'string', default: 'pro_ost_ed', displayOptions: { show: { operation: ['createTask'] } } },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index) => {
      const operation = getOperation(this, index, 'createTask', ['createTask', 'getTask', 'getResult']);
      if (operation === 'createTask') return {
        skill: 'iflytek-speed-transcription', operation, input: {},
        parameters: {
          language: getString(this, 'language', index, 'zh_cn'),
          accent: getString(this, 'accent', index, 'mandarin'),
          domain: getString(this, 'domain', index, 'pro_ost_ed'),
        },
        binaryInputs: { audio: getString(this, 'binaryPropertyName', index, 'data') },
      };
      return {
        skill: 'iflytek-speed-transcription', operation, input: {},
        parameters: { taskId: getString(this, 'taskId', index, '') },
      };
    });
  }
}
