import assert from 'node:assert/strict'
import test from 'node:test'
import { fixtureAsset } from '../../../../scripts/e2e/upgrade_fixture_server.mjs'

test('old-client fixture serves only bounded static paths and never API navigation fallback', () => {
  assert.equal(fixtureAsset('/'), 'index.html')
  assert.equal(fixtureAsset('/workshop/active'), 'index.html')
  assert.equal(fixtureAsset('/sw.js'), 'sw.js')
  assert.equal(fixtureAsset('/assets/old.js'), 'assets/old.js')
  for (const path of [
    '/api',
    '/api/v1/customers',
    '/health/ready',
    '/../package.json',
    '/assets/%2e%2e/secret',
    '//external',
  ])
    assert.equal(fixtureAsset(path), null)
})
