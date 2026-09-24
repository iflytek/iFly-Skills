import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { credential, executeItems, getNumber, getString } from '../common';

export class IflyImageUnderstanding implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Image Understanding', name: 'iflyImageUnderstanding', icon: 'fa:image', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Image Understanding' },
    description: 'Ask iFlytek to describe or answer questions about an image.',
    inputs: ['main'], outputs: ['main'], credentials: [credential], properties: [
      {
        displayName: 'Binary Property', name: 'binaryPropertyName', type: 'string', default: 'data',
        description: 'Binary property containing the image.',
      },
      {
        displayName: 'Question', name: 'question', type: 'string', typeOptions: { rows: 4 },
        default: 'Please describe this image in detail.',
      },
      {
        displayName: 'Model', name: 'domain', type: 'options', default: 'imagev3', options: [
          { name: 'Image v3', value: 'imagev3' }, { name: 'General', value: 'general' },
        ],
      },
      { displayName: 'Temperature', name: 'temperature', type: 'number', default: 0.5, typeOptions: { minValue: 0.01, maxValue: 1 } },
      { displayName: 'Max Tokens', name: 'maxTokens', type: 'number', default: 2048, typeOptions: { minValue: 1, maxValue: 8192 } },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index) => ({
      skill: 'iflytek-image-understanding', operation: 'analyze', input: {},
      parameters: {
        question: getString(this, 'question', index, 'Please describe this image in detail.'),
        domain: getString(this, 'domain', index, 'imagev3'),
        temperature: getNumber(this, 'temperature', index, 0.5),
        maxTokens: getNumber(this, 'maxTokens', index, 2048),
      },
      binaryInputs: { image: getString(this, 'binaryPropertyName', index, 'data') },
    }));
  }
}
