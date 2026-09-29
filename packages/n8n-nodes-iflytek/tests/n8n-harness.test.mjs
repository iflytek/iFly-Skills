import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import test from 'node:test';
import { readNodeTypes } from '../scripts/n8n-harness.mjs';

async function endpoint(t, respond) {
  const server = createServer(respond);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => {
    server.close(resolve);
    server.closeAllConnections();
  }));
  return `http://127.0.0.1:${server.address().port}`;
}

test('n8n metadata readiness tolerates a missing file and a partially written JSON response', async t => {
  let requests = 0;
  const types = [{ name: '@iflytekopensource/n8n-nodes-iflytek.iflyHyperTts' }];
  const url = await endpoint(t, (request, response) => {
    assert.equal(request.url, '/types/nodes.json');
    assert.equal(request.headers.cookie, 'test-session=local');
    requests++;
    if (requests === 1) response.writeHead(404).end();
    else response.end(requests === 2 ? '[{"name":"partially written' : JSON.stringify(types));
  });
  assert.deepEqual(await readNodeTypes(url, 'test-session=local', 3000), types);
  assert.equal(requests, 3);
});

test('n8n metadata polling fails within its deadline without logging the response body', async t => {
  const url = await endpoint(t, (_, response) => response.end('["private-metadata'));
  await assert.rejects(readNodeTypes(url, '', 100), error => {
    assert.match(error.message, /Timed out: complete n8n node type metadata/);
    assert.match(error.message, /Incomplete or invalid JSON/);
    assert.ok(!error.message.includes('private-metadata'));
    return true;
  });
});

test('n8n metadata polling rejects authentication failures and unexpected JSON structures', async t => {
  for (const [status, body, expected] of [[401, '', /HTTP 401/], [200, '{}', /must be an array/]]) {
    let requests = 0;
    const url = await endpoint(t, (_, response) => {
      requests++;
      response.writeHead(status).end(body);
    });
    await assert.rejects(readNodeTypes(url, '', 1000), expected);
    assert.equal(requests, 1);
  }
});

test('complete node metadata is returned unchanged so registration assertions still detect missing nodes', async t => {
  const url = await endpoint(t, (_, response) => response.end('[]'));
  assert.deepEqual(await readNodeTypes(url, '', 1000), []);
});
