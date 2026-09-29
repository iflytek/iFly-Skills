import assert from 'node:assert/strict';
import { readFile, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { N8nHarness, readNodeTypes, until } from './n8n-harness.mjs';
import { checkTemplates } from './n8n-template-checks.mjs';

const args = process.argv.slice(2);
const option = name => args[args.indexOf(name) + 1];
for (let i = 0; i < args.length; i += 2) {
  assert.ok(['--n8n-root', '--community-root', '--python', '--report'].includes(args[i]) && args[i + 1], 'Invalid argument');
}
for (const key of ['--n8n-root', '--community-root', '--python', '--report']) assert.ok(args.includes(key), `Missing ${key}`);
const host = new N8nHarness(option('--n8n-root'), option('--community-root'), option('--python'));
const report = { kind: 'real-n8n-compatibility', n8n: host.version, assertions: {} };
try {
  await host.start();
  console.log('n8n ready: ' + host.version);
  const types = await readNodeTypes(host.url, host.cookie);
  assert.equal(types.filter(type => type.name.startsWith('@iflytekopensource/n8n-nodes-iflytek.')).length, 11);
  report.assertions.registeredNodes = 11;
  await checkTemplates(host, path.join(host.communityRoot, 'node_modules/@iflytekopensource/n8n-nodes-iflytek'));
  report.assertions.templateImportAndOfflineExpressions = true;
  const workflow = await host.create('Local constants and expressions', [
    host.node('Start', 'n8n-nodes-base.manualTrigger'),
    host.node('Input', 'n8n-nodes-base.set', { mode: 'raw', jsonOutput: '{"operations":["listVoices","listVoices"]}', options: {} }, { typeVersion: 3.4 }),
    host.node('Items', 'n8n-nodes-base.splitOut', { fieldToSplitOut: 'operations', options: {} }),
    host.node('Voices', '@iflytekopensource/n8n-nodes-iflytek.iflyHyperTts', { operation: '={{ $json.operations }}' }),
  ]);
  const execution = await host.completed(await host.run(workflow));
  const items = execution.data.resultData.runData.Voices[0].data.main[0];
  assert.equal(items.length, 2);
  for (const [index, item] of items.entries()) {
    assert.equal(item.pairedItem.item, index);
    assert.equal(item.json.data.voices.length, 54);
  }
  report.assertions.multiItemExpressionsAndPairing = true;
  const errorWorkflow = await host.create('Controlled error continuation', [
    host.node('Start', 'n8n-nodes-base.manualTrigger'),
    host.node('Invalid operation', '@iflytekopensource/n8n-nodes-iflytek.iflyHyperTts', { operation: 'invalidOperation' }, { onError: 'continueRegularOutput' }),
    host.node('After error', 'n8n-nodes-base.noOp'),
  ]);
  const continued = await host.completed(await host.run(errorWorkflow));
  assert.match(continued.data.resultData.runData['After error'][0].data.main[0][0].json.error, /UNSUPPORTED_OPERATION/);
  report.assertions.errorContinuation = true;
  const hookPath = 'ifly-accept-' + host.port;
  const production = await host.create('Production webhook constants', [
    host.node('Webhook', 'n8n-nodes-base.webhook', { httpMethod: 'GET', path: hookPath, responseMode: 'onReceived', options: {} }, { webhookId: hookPath, typeVersion: 2 }),
    host.node('Voices', '@iflytekopensource/n8n-nodes-iflytek.iflyHyperTts', { operation: 'listVoices' }),
  ]);
  await host.api('/rest/workflows/' + production.id + '/activate', 'POST', { versionId: production.versionId });
  const webhookResponse = await until(async () => {
    const response = await fetch(host.url + '/webhook/' + hookPath);
    if (response.status === 404) return false;
    return response;
  }, 'production webhook registration', 20000);
  assert.equal(webhookResponse.status, 200, await webhookResponse.text());
  const productionExecution = await until(async () => {
    const response = await host.api('/rest/executions?' + new URLSearchParams({ filter: JSON.stringify({ workflowId: production.id }) }));
    const rows = response.results ?? response;
    return Array.isArray(rows) && rows.find(row => row.status === 'success');
  }, 'production webhook execution');
  assert.equal((await host.execution(productionExecution.id)).mode, 'webhook');
  report.assertions.productionWebhook = true;
  await host.api('/rest/workflows/' + production.id + '/deactivate', 'POST', {});
  const logs = host.logs.map(row => row.text).join('');
  assert.ok(logs.includes('iflytek.execution'));
  report.assertions.executionMetadataLogged = true;
  assert.deepEqual(await readdir(host.main.temporaryRoot), []);
  report.assertions.residualInvocationDirectories = 0;
  const manifest = JSON.parse(await readFile(path.join(host.communityRoot, 'node_modules/@iflytekopensource/n8n-nodes-iflytek/runtime/manifest.json'), 'utf8'));
  report.sourceCommit = manifest.sourceCommit;
  report.sourceTreeDirty = manifest.sourceTreeDirty;
  report.boundary = 'Real n8n engine with installed community package and Python. Checks template import and fixture-based expressions, local listVoices and controlled input failure; no paid API calls or canvas UI.';
} finally {
  await host.cleanup();
}
report.cleaned = true;
await writeFile(path.resolve(option('--report')), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
