import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

// Import the shipped workflows unchanged, then exercise their routing and
// expressions in copies that replace file access and paid calls with fixtures.
export async function checkTemplates(host, packageRoot) {
  for (const filename of ['proofread-and-translate', 'invoice-recognition', 'text-to-speech']) {
    const template = JSON.parse(await readFile(path.join(packageRoot, 'workflows', filename + '.json'), 'utf8'));
    const original = await host.api('/rest/workflows', 'POST', template);
    host.workflows.push(original);
    assert.equal(original.active, false);
    const fixture = structuredClone(template);
    fixture.name += ' (offline expression test)';
    for (const node of fixture.nodes) {
      let jsonOutput;
      if (node.name === 'Proofread') jsonOutput = '{"data":{"result":{"offlineFixture":true}}}';
      if (node.name === 'Invoice OCR') jsonOutput = '{"data":{"result":{"offlineFixture":true}}}';
      if (node.name === 'Read invoice') jsonOutput = '{}';
      if (['Translate', 'Synthesize'].includes(node.name)) {
        const text = node.parameters.text;
        assert.ok(text.startsWith('={{') && text.endsWith('}}'));
        jsonOutput = '={{ { mappedText: (' + text.slice(3, -2) + ') } }}';
      }
      if (jsonOutput !== undefined) Object.assign(node, { type: 'n8n-nodes-base.set', typeVersion: 3.4,
        parameters: { mode: 'raw', jsonOutput, options: {} } });
    }
    const execute = async candidate => {
      const workflow = await host.api('/rest/workflows', 'POST', candidate);
      host.workflows.push(workflow);
      return (await host.completed(await host.run(workflow))).data.resultData.runData;
    };
    const result = await execute(fixture);
    if (filename === 'proofread-and-translate') {
      assert.ok(result['Review suggestions']);
      assert.equal(result.Translate, undefined, 'Unapproved text must not reach translation');
      fixture.nodes.find(node => node.name === 'Text input').parameters.jsonOutput = JSON.stringify({
        originalText: '原文', approvedText: '人工选定文本', approvedForTranslation: true,
      });
      const approved = await execute(fixture);
      assert.equal(approved.Translate[0].data.main[0][0].json.mappedText, '人工选定文本');
    } else if (filename === 'invoice-recognition') {
      assert.equal(result['Review extracted fields'][0].data.main[0][0].json.requiresHumanReview, true);
    } else {
      assert.equal(result.Synthesize[0].data.main[0][0].json.mappedText, '欢迎使用 iFLYTEK Skills。');
    }
  }
}
