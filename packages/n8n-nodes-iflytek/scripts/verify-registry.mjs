import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const registry = 'https://registry.npmjs.org/';

async function get(url, fetchImpl = fetch) {
  const response = await fetchImpl(url, { signal: AbortSignal.timeout(30000) });
  assert.ok(response.ok, `Registry check returned HTTP ${response.status}`);
  return response;
}

export async function keywordSearch(packageName, fetchImpl = fetch) {
  // A keyword qualifier can ignore extra free text. Narrow by brand, then check the community marker.
  const query = 'keywords:iflytek';
  const search = await (await get(registry + '-/v1/search?' + new URLSearchParams({ text: query, size: '250' }), fetchImpl)).json();
  assert.ok(search && Array.isArray(search.objects)
    && search.objects.every(item => typeof item?.package?.name === 'string' && item.package.name.length > 0),
  'Invalid registry search response');
  assert.ok(Number.isInteger(search.total) && search.total >= search.objects.length, 'Invalid registry search total');
  const matched = search.objects.find(item => item?.package?.name === packageName)?.package;
  if (matched) {
    assert.ok(Array.isArray(matched.keywords) && matched.keywords.includes('n8n-community-node-package'),
      'Matched search package is missing the n8n-community-node-package keyword');
  }
  return { query, indexed: Boolean(matched), total: search.total, returned: search.objects.length };
}

export function inspectRegistryReadme(metadata, packedReadme) {
  // Registry README metadata is package-level, not bound to the checked version.
  const matches = typeof metadata.readme === 'string'
    && metadata.readme.replace(/\r\n/g, '\n') === packedReadme.replace(/\r\n/g, '\n');
  return { filename: metadata.readmeFilename ?? null, contentMatchesPackedDefault: matches,
    note: matches ? 'Registry README content matches package/README.md.'
      : 'Registry README metadata is missing or differs from package/README.md. Check the npm page separately; this metadata is not version-specific.' };
}

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
  const packagePath = encodeURIComponent(release.package);
  const metadata = await (await get(registry + packagePath + '/' + encodeURIComponent(release.version))).json();
  const tarball = new URL(metadata.dist.tarball);
  assert.equal(tarball.origin, 'https://registry.npmjs.org');
  const bytes = Buffer.from(await (await get(tarball)).arrayBuffer());
  validatePublished(metadata, release, bytes);
  const tags = await (await get(registry + '-/package/' + packagePath + '/dist-tags')).json();
  assert.equal(tags[release.distTag], release.version, 'Unexpected dist-tag');
  const { query, indexed, total, returned } = await keywordSearch(release.package);
  const packedReadme = execFileSync('tar', ['-xOzf', '-', 'package/README.md'], { input: bytes, encoding: 'utf8' });
  assert.ok(packedReadme.trim(), 'Empty packed README.md');
  const packument = await (await get(registry + packagePath)).json();
  assert.equal(packument.name, release.package);
  const report = { package: release.package, version: release.version, integrityMatches: true,
    distTag: release.distTag, keywordSearchQuery: query, keywordSearchIndexed: indexed,
    keywordSearchTotal: total, keywordSearchReturned: returned,
    searchNote: indexed ? 'Exact package found in brand keyword search with the n8n community keyword.'
      : `Exact package not found in ${returned} of ${total} brand keyword search results. This does not prove the package is unindexed; indexing or ranking may differ. Exact-name installation remains available.`,
    registryReadme: inspectRegistryReadme(packument, packedReadme) };
  await writeFile(path.join(path.dirname(path.resolve(filename)), 'registry-verification.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
