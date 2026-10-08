import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export function validatePublished(metadata, release, bytes) {
  assert.equal(metadata.name, release.package);
  assert.equal(metadata.version, release.version);
  assert.deepEqual(metadata.n8n, release.n8n);
  assert.deepEqual(metadata.keywords, release.keywords);
  assert.equal(metadata.dist.integrity, release.integrity, 'Registry integrity differs from the reviewed artifact');
  assert.equal('sha512-' + createHash('sha512').update(bytes).digest('base64'), release.integrity);
  assert.equal(createHash('sha256').update(bytes).digest('hex'), release.sha256);
}

async function main() {
  const [flag, filename] = process.argv.slice(2);
  assert.ok(flag === '--release' && filename && process.argv.length === 4, 'Usage: npm run release:verify -- --release release.json');
  const release = JSON.parse(await readFile(filename, 'utf8'));
  assert.equal(release.package, '@iflytekopensource/n8n-nodes-iflytek-skills');
  assert.ok(release.publishable && !release.sourceTreeDirty, 'Use a clean release artifact');
  const get = async url => {
    const response = await fetch(url, { signal: AbortSignal.timeout(30000) });
    assert.ok(response.ok, `Registry check returned HTTP ${response.status}`);
    return response;
  };
  const registry = 'https://registry.npmjs.org/';
  const packagePath = encodeURIComponent(release.package);
  const metadata = await (await get(registry + packagePath + '/' + encodeURIComponent(release.version))).json();
  const tarball = new URL(metadata.dist.tarball);
  assert.equal(tarball.origin, 'https://registry.npmjs.org');
  const bytes = Buffer.from(await (await get(tarball)).arrayBuffer());
  validatePublished(metadata, release, bytes);
  const tags = await (await get(registry + '-/package/' + packagePath + '/dist-tags')).json();
  assert.equal(tags[release.distTag], release.version, 'Unexpected dist-tag');
  const search = await (await get(registry + '-/v1/search?' + new URLSearchParams({ text: 'keywords:n8n-community-node-package ' + release.package, size: '250' }))).json();
  const indexed = search.objects.some(item => item.package.name === release.package);
  const report = { package: release.package, version: release.version, integrityMatches: true,
    distTag: release.distTag, keywordSearchIndexed: indexed,
    searchNote: indexed ? 'Exact package found in keyword search.' : 'Indexing may be delayed; repeat the search later. Exact-name installation remains available.' };
  await writeFile(path.join(path.dirname(path.resolve(filename)), 'registry-verification.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
