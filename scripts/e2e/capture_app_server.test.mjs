import { test } from 'node:test'
import assert from 'node:assert/strict'
import { captureAsset } from './capture_app_server.mjs'
test('capture App host admits only exact safe assets, never backend or fallback routes', () => {
  assert.equal(captureAsset('/'), 'index.html')
  assert.equal(captureAsset('/sw.js?x=1'), 'sw.js')
  for (const path of [
    '/api/v1/login',
    '/unknown',
    '/../../secrets.json',
    '/%2e%2e/x.js',
    '//x.js',
    '/a%5cb.js',
    '/%zz',
  ])
    assert.equal(captureAsset(path), null)
})
