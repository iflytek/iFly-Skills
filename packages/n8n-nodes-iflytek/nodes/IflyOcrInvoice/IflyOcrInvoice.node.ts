import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { executeItems, getString, credential } from '../common';

export class IflyOcrInvoice implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Invoice OCR', name: 'iflyOcrInvoice', icon: 'fa:file-invoice', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Invoice OCR' }, description: 'Recognize invoice and receipt images with iFlytek.',
    inputs: ['main'], outputs: ['main'], credentials: [credential], properties: [
      {
        displayName: 'Binary Property', name: 'binaryPropertyName', type: 'string', default: 'data',
        description: 'Binary property containing the invoice image or PDF.',
      },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index) => ({
      skill: 'iflytek-ocr-invoice', operation: 'recognize', input: {}, parameters: {},
      binaryInputs: { image: getString(this, 'binaryPropertyName', index, 'data') },
    }));
  }
}

