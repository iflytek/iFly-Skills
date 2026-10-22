import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { executeItems, textItem, textProperties, credential } from '../common';

export class IflyTextProofread implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Text Proofread', name: 'iflyTextProofread', icon: 'fa:spell-check', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Text Proofread' }, description: 'Proofread Chinese text with iFlytek.',
    inputs: ['main'], outputs: ['main'], credentials: [credential], properties: [...textProperties],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index) => textItem(this, index, 'iflytek-text-proofread', 'check'));
  }
}

