import assert from 'node:assert/strict'
import test from 'node:test'
import { navigationFallbackDenylist } from '../../pwa-navigation-policy.mjs'

const excluded = (path) => navigationFallbackDenylist.some((pattern) => pattern.test(path))

test('service worker never rewrites API or health navigation as the SPA', () => {
  for (const path of [
    '/api',
    '/api?x=1',
    '/api/v1/missing',
    '/health',
    '/health/ready',
    '/API/v1/missing',
    '/%61pi/v1/missing',
    '/api%2fv1/missing',
    '//api/v1/missing',
    '/%68ealth/ready',
  ]) {
    assert.equal(excluded(path), true, path)
  }
})

test('offline application navigation keeps its shell fallback', () => {
  for (const path of ['/', '/customers', '/orders/123', '/apiary', '/healthcare']) {
    assert.equal(excluded(path), false, path)
  }
})
