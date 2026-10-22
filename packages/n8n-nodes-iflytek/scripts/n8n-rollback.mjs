import assert from 'node:assert/strict';
import { readFile, symlink, unlink, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { N8nHarness, until } from './n8n-harness.mjs';

const args = process.argv.slice(2);
const option = name => args[args.indexOf(name) + 1];
const keys = ['--n8n-root', '--baseline-community', '--candidate-community', '--python', '--report'];
for (let i = 0; i < args.length; i += 2) assert.ok(keys.includes(args[i]) && args[i + 1], 'Invalid argument');
for (const key of keys) assert.ok(args.includes(key), `Missing ${key}`);
const host = new N8nHarness(option('--n8n-root'), option('--baseline-community'), option('--python'));
const phases = [];
try {
  await host.start();
  const workflow = await host.create('Retained workflow across package replacement', [
    host.node('Start', 'n8n-nodes-base.manualTrigger'),
    host.node('Voices', '@iflytekopensource/n8n-nodes-iflytek-skills.iflyHyperTts', { operation: 'listVoices' }),
  ]);
  let baseline;
  for (const [phase, community] of [['baseline', option('--baseline-community')], ['candidate', option('--candidate-community')],
    ['rollback', option('--baseline-community')]]) {
    if (phase !== 'baseline') {
      await host.stop(host.main);
      // This symlink belongs to this harness; neither external community directory is removed.
      await unlink(path.join(host.root, 'user/.n8n/nodes'));
      await symlink(path.resolve(community), path.join(host.root, 'user/.n8n/nodes'), 'dir');
      host.main = await host.launch(phase);
      await until(() => fetch(host.url + '/healthz/readiness').then(r => r.ok).catch(() => false), 'replacement ready');
    }
    const result = await host.completed(await host.run(workflow));
    assert.equal(result.workflowId, workflow.id);
    const output = result.data.resultData.runData.Voices[0].data.main[0][0].json.data;
    if (phase === 'baseline') baseline = output;
    else assert.deepEqual(output, baseline);
    const manifest = JSON.parse(await readFile(path.join(community, 'node_modules/@iflytekopensource/n8n-nodes-iflytek-skills/runtime/manifest.json'), 'utf8'));
    phases.push({ phase, workflowIdUnchanged: result.workflowId === workflow.id, status: result.status,
      voices: output.voices.length, runtimeFiles: Object.keys(manifest.files).length });
    console.log('Package replacement passed: ' + phase);
  }
} finally { await host.cleanup(); }
const report = { kind: 'real-n8n-package-rollback', n8n: host.version, phases, cleaned: true,
  boundary: 'Same n8n version, database, encryption key and workflow; package-only replacement. No n8n database migration or paid task replay.' };
await writeFile(path.resolve(option('--report')), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
