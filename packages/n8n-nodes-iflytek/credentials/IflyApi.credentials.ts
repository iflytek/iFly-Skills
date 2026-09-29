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
      description: 'App ID from your iFLYTEK application',
    },
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'API key from the same iFLYTEK application',
    },
    {
      displayName: 'API Secret',
      name: 'apiSecret',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description: 'API secret from the same iFLYTEK application',
    },
  ];
}
