import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { credential, executeItems, getOperation, getString } from '../common';
import type { ItemOperation } from '../../shared/executeSkill';

export class IflyPdfImageOcr implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek PDF and Image OCR', name: 'iflyPdfImageOcr', icon: 'fa:file-alt', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek PDF and Image OCR' },
    description: 'Recognize images or manage iFlytek PDF OCR tasks.',
    inputs: ['main'], outputs: ['main'], credentials: [credential], properties: [
      {
        displayName: 'Operation', name: 'operation', type: 'options', default: 'recognizeImage', options: [
          { name: 'Recognize Image', value: 'recognizeImage' },
          { name: 'Create PDF Task', value: 'createPdfTask' },
          { name: 'Get PDF Task', value: 'getPdfTask' },
          { name: 'Get Result', value: 'getResult' },
        ],
      },
      {
        displayName: 'Binary Property', name: 'binaryPropertyName', type: 'string', default: 'data',
        description: 'Binary property containing an image or PDF.',
        displayOptions: { show: { operation: ['recognizeImage', 'createPdfTask'] } },
      },
      {
        displayName: 'Result Format', name: 'resultFormat', type: 'options', default: 'json,markdown', options: [
          { name: 'JSON and Markdown', value: 'json,markdown' }, { name: 'JSON', value: 'json' },
          { name: 'Markdown', value: 'markdown' },
        ], displayOptions: { show: { operation: ['recognizeImage'] } },
      },
      {
        displayName: 'PDF URL', name: 'pdfUrl', type: 'string', default: '',
        description: 'Optional public HTTP(S) URL. When set, the binary property is ignored.',
        displayOptions: { show: { operation: ['createPdfTask'] } },
      },
      {
        displayName: 'Export Format', name: 'exportFormat', type: 'options', default: 'word', options: [
          { name: 'Word', value: 'word' }, { name: 'Markdown', value: 'markdown' }, { name: 'JSON', value: 'json' },
        ], displayOptions: { show: { operation: ['createPdfTask'] } },
      },
      {
        displayName: 'Task Number', name: 'taskNo', type: 'string', default: '',
        description: 'Task number returned by Create PDF Task.',
        displayOptions: { show: { operation: ['getPdfTask', 'getResult'] } },
      },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index): ItemOperation => {
      const operation = getOperation(this, index, 'recognizeImage', ['recognizeImage', 'createPdfTask', 'getPdfTask', 'getResult']);
      if (operation === 'recognizeImage') return {
        skill: 'iflytek-pdf-image-ocr', operation, input: {},
        parameters: { resultFormat: getString(this, 'resultFormat', index, 'json,markdown') },
        binaryInputs: { image: getString(this, 'binaryPropertyName', index, 'data') },
      };
      if (operation === 'createPdfTask') {
        const binary = getString(this, 'binaryPropertyName', index, 'data').trim();
        const url = getString(this, 'pdfUrl', index, '').trim();
        return {
          skill: 'iflytek-pdf-image-ocr', operation, input: {},
          parameters: { pdfUrl: url, exportFormat: getString(this, 'exportFormat', index, 'word') },
          binaryInputs: !url && binary ? { pdf: binary } : undefined,
        };
      }
      return {
        skill: 'iflytek-pdf-image-ocr', operation, input: {},
        parameters: { taskNo: getString(this, 'taskNo', index, '') },
      };
    });
  }
}
