import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { executeItems, getString, textItem, textProperties, credential } from '../common';

export class IflyTranslate implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Translate', name: 'iflyTranslate', icon: 'fa:language', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Translate' }, description: 'Translate text with iFlytek.',
    inputs: ['main'], outputs: ['main'], credentials: [credential], properties: [
      ...textProperties,
      { displayName: 'Source Language', name: 'fromLanguage', type: 'string', default: 'cn' },
      { displayName: 'Target Language', name: 'toLanguage', type: 'string', default: 'en' },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index) => textItem(this, index, 'iflytek-translate', 'translate', {
      fromLanguage: getString(this, 'fromLanguage', index, 'cn'),
      toLanguage: getString(this, 'toLanguage', index, 'en'),
    }));
  }
}

