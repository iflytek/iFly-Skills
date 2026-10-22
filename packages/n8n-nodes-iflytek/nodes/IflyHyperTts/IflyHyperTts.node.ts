import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { executeItems, getNumber, getOperation, getString, textItem, textProperties } from '../common';

export class IflyHyperTts implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Hyper TTS', name: 'iflyHyperTts', icon: 'fa:volume-up', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Hyper TTS' }, description: 'Synthesize speech or inspect bundled voices with iFlytek.',
    inputs: ['main'], outputs: ['main'], credentials: [{ name: 'iflyApi', required: false }], properties: [
      {
        displayName: 'Operation', name: 'operation', type: 'options', default: 'synthesize', options: [
          { name: 'Synthesize', value: 'synthesize' }, { name: 'List Voices', value: 'listVoices' },
        ],
      },
      ...textProperties,
      { displayName: 'Voice', name: 'voice', type: 'string', default: 'x5_lingxiaotang_flow' },
      { displayName: 'Speed', name: 'speed', type: 'number', default: 50, typeOptions: { minValue: 0, maxValue: 100 } },
      { displayName: 'Volume', name: 'volume', type: 'number', default: 50, typeOptions: { minValue: 0, maxValue: 100 } },
      { displayName: 'Pitch', name: 'pitch', type: 'number', default: 50, typeOptions: { minValue: 0, maxValue: 100 } },
      { displayName: 'Sample Rate', name: 'sampleRate', type: 'options', default: 24000, options: [
        { name: '8000 Hz', value: 8000 }, { name: '16000 Hz', value: 16000 }, { name: '24000 Hz', value: 24000 },
      ], displayOptions: { show: { operation: ['synthesize'] } } },
      { displayName: 'Role', name: 'role', type: 'string', default: '', displayOptions: { show: { operation: ['synthesize'] } } },
      { displayName: 'Output Binary Property', name: 'outputBinaryPrefix', type: 'string', default: 'audio',
        displayOptions: { show: { operation: ['synthesize'] } } },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index) => {
      const operation = getOperation(this, index, 'synthesize', ['synthesize', 'listVoices']);
      if (operation === 'listVoices') return { skill: 'iflytek-hyper-tts', operation, input: {}, parameters: {} };
      const item = textItem(this, index, 'iflytek-hyper-tts', 'synthesize', {
        voice: getString(this, 'voice', index, 'x5_lingxiaotang_flow'),
        speed: getNumber(this, 'speed', index, 50), volume: getNumber(this, 'volume', index, 50),
        pitch: getNumber(this, 'pitch', index, 50), sampleRate: getNumber(this, 'sampleRate', index, 24000),
        role: getString(this, 'role', index, '') || undefined,
      });
      item.outputBinaryPrefix = getString(this, 'outputBinaryPrefix', index, 'audio');
      return item;
    });
  }
}

