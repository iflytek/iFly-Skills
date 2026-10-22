import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { credential, executeItems, getString, textItem, textProperties } from '../common';

export class IflyContractReview implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Contract Review', name: 'iflyContractReview', icon: 'fa:file-text-o', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Contract Review' },
    description: 'Extract and review a contract with shared iFLYTEK credentials. Results require human review.',
    inputs: ['main'], outputs: ['main'], credentials: [credential], properties: [
      {
        displayName: 'Input Format', name: 'format', type: 'options', default: 'text', options: [
          { name: 'Text', value: 'text' }, { name: 'PDF', value: 'pdf' }, { name: 'DOCX', value: 'docx' },
          { name: 'PNG', value: 'png' }, { name: 'JPEG', value: 'jpg' }, { name: 'BMP', value: 'bmp' },
        ], description: 'Contracts are limited to 4000 extracted characters. PDF input is limited to 8 pages.',
      },
      ...textProperties.map(property => ({ ...property, displayOptions: { show: { format: ['text'] } } })),
      {
        displayName: 'Binary Property', name: 'binaryPropertyName', type: 'string', default: 'data',
        displayOptions: { hide: { format: ['text'] } }, description: 'Binary property containing the contract (up to 20 MiB).',
      },
      {
        displayName: 'Image Extraction', name: 'imageMethod', type: 'options', default: 'ocr',
        displayOptions: { show: { format: ['png', 'jpg', 'bmp'] } },
        options: [{ name: 'OCR', value: 'ocr' }, { name: 'Image Understanding', value: 'understanding' }],
        description: 'Image understanding is model inference and requires checking against the original image. No automatic fallback.',
      },
      {
        displayName: 'Language', name: 'lang', type: 'options', default: 'zh', options: [
          { name: 'Chinese', value: 'zh' }, { name: 'English', value: 'en' }, { name: 'Bilingual', value: 'bilingual' },
        ],
      },
      {
        displayName: 'Review Mode', name: 'reviewMode', type: 'options', default: 'standard', options: [
          { name: 'Quick', value: 'quick' }, { name: 'Standard', value: 'standard' }, { name: 'Deep', value: 'deep' },
        ],
      },
      {
        displayName: 'Focus Areas', name: 'focus', type: 'multiOptions', default: [], options: [
          { name: 'Payment', value: 'payment' }, { name: 'Liability', value: 'liability' },
          { name: 'Renewal', value: 'renewal' }, { name: 'Intellectual Property', value: 'ip' },
          { name: 'Confidentiality', value: 'confidentiality' }, { name: 'Dispute', value: 'dispute' },
        ],
      },
      {
        displayName: 'Translate Summary to English', name: 'needTranslation', type: 'boolean', default: false,
        description: 'Whether to translate the Chinese model summary using the text translation service.',
      },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index) => {
      const format = getString(this, 'format', index, 'text');
      const parameters = {
        format, lang: getString(this, 'lang', index, 'zh'),
        reviewMode: getString(this, 'reviewMode', index, 'standard'),
        focus: this.getNodeParameter('focus', index, []) as string[],
        needTranslation: this.getNodeParameter('needTranslation', index, false) as boolean,
        imageMethod: ['png', 'jpg', 'bmp'].includes(format) ? getString(this, 'imageMethod', index, 'ocr') : 'ocr',
      };
      const item = format === 'text'
        ? textItem(this, index, 'iflytek-contract-intelligence-review', 'review', parameters)
        : { skill: 'iflytek-contract-intelligence-review', operation: 'review', input: {}, parameters,
          binaryInputs: { document: getString(this, 'binaryPropertyName', index, 'data') } };
      return { ...item, outputBinaryPrefix: 'report' };
    });
  }
}
