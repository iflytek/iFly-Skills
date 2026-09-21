import type { ICredentialType, INodeProperties } from 'n8n-workflow';

export class IflyApi implements ICredentialType {
  name = 'iflyApi';
  displayName = 'iFlytek API';

  // Operations validate their own required subset of this shared credential.
  // No generic HTTP authentication/test: each Python client signs its requests.
  properties: INodeProperties[] = [
    {
      displayName: 'App ID',
      name: 'appId',
      type: 'string',
      default: '',
      description: 'Shared iFLYTEK application ID (IFLY_APP_ID)',
    },
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'Shared iFLYTEK API key (IFLY_API_KEY)',
    },
    {
      displayName: 'API Secret',
      name: 'apiSecret',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'Shared iFLYTEK API secret (IFLY_API_SECRET)',
    },
  ];
}
