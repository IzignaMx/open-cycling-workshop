import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('offline Dexie shim stays ambient declarations and exposes only the intended table delete API', () => {
  const source = readFileSync(new URL('../../tools/dexie-shim.d.ts', import.meta.url), 'utf8')
  assert.match(source, /^declare module 'dexie' \{/)
  assert.match(source, /export interface Table<T, K = unknown> \{/)
  assert.match(source, /delete\(key: K\): Promise<void>/)
  assert.doesNotMatch(source, /^import |BrandingSnapshotRepository|async |await /m)
})
