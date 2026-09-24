import type { IExecuteFunctions, INodeType, INodeTypeDescription } from 'n8n-workflow';
import { credential, executeItems, getOperation, getString } from '../common';

export class IflyVideoTranslate implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'iFlytek Video Translate', name: 'iflyVideoTranslate', icon: 'fa:film', group: ['transform'],
    version: 1, defaults: { name: 'iFlytek Video Translate' },
    description: 'Create and manage iFlytek video translation tasks.',
    inputs: ['main'], outputs: ['main'], credentials: [credential], properties: [
      {
        displayName: 'Operation', name: 'operation', type: 'options', default: 'createTask', options: [
          { name: 'Create Task', value: 'createTask' }, { name: 'List Tasks', value: 'listTasks' },
          { name: 'Get Task', value: 'getTask' }, { name: 'Confirm Transcript', value: 'confirmTranscript' },
        ],
      },
      {
        displayName: 'Video URL', name: 'fileUrl', type: 'string', default: '',
        description: 'Public HTTP(S) URL of the source video.', displayOptions: { show: { operation: ['createTask'] } },
      },
      { displayName: 'Source Language', name: 'sourceLanguage', type: 'string', default: 'en', displayOptions: { show: { operation: ['createTask'] } } },
      { displayName: 'Target Language', name: 'targetLanguage', type: 'string', default: 'zh', displayOptions: { show: { operation: ['createTask'] } } },
      { displayName: 'Task Name', name: 'taskName', type: 'string', default: 'video_translate_task', displayOptions: { show: { operation: ['createTask'] } } },
      {
        displayName: 'Task ID', name: 'taskId', type: 'string', default: '',
        description: 'Task ID returned by Create Task.', displayOptions: { show: { operation: ['getTask', 'confirmTranscript'] } },
      },
      {
        displayName: 'Force Rerun', name: 'forceRerun', type: 'boolean', default: false,
        description: 'Request a rerun after transcript confirmation.', displayOptions: { show: { operation: ['confirmTranscript'] } },
      },
    ],
  };

  async execute(this: IExecuteFunctions) {
    return executeItems(this, (index) => {
      const operation = getOperation(this, index, 'createTask', ['createTask', 'listTasks', 'getTask', 'confirmTranscript']);
      if (operation === 'createTask') return {
        skill: 'iflytek-video-translate', operation, input: {}, parameters: {
          fileUrl: getString(this, 'fileUrl', index, ''),
          sourceLanguage: getString(this, 'sourceLanguage', index, 'en'),
          targetLanguage: getString(this, 'targetLanguage', index, 'zh'),
          taskName: getString(this, 'taskName', index, 'video_translate_task'),
        },
      };
      if (operation === 'listTasks') return { skill: 'iflytek-video-translate', operation, input: {}, parameters: {} };
      return { skill: 'iflytek-video-translate', operation, input: {}, parameters: {
        taskId: getString(this, 'taskId', index, ''),
        ...(operation === 'confirmTranscript' ? { forceRerun: this.getNodeParameter('forceRerun', index, false) } : {}),
      } };
    });
  }
}
