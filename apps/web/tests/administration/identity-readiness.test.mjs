import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { expectWorkshopIdentity } from '../../e2e/helpers/workshop-identity.mjs'

const expectedIdentity = 'Taller administración A'
function reader(values) {
  let reads = 0
  const page = {
    locator(selector) {
      assert.equal(selector, '.workshop-identity strong')
      return {
        async allTextContents() {
          return values[Math.min(reads++, values.length - 1)]
        },
      }
    },
  }
  return { page, reads: () => reads }
}

test('identity readiness retries a pending fallback until the exact workshop name arrives', async () => {
  // Controlled observations exercise the real Playwright assertion, not a
  // browser or a mutation of the application identity.
  const state = reader([['OCWP'], ['OCWP'], [expectedIdentity]])
  await expectWorkshopIdentity(state.page, expectedIdentity)
  assert.equal(state.reads(), 3)
})

for (const [name, values] of [
  ['fallback never changes', ['OCWP']],
  ['identity is absent', []],
  ['identity is duplicated', [expectedIdentity, expectedIdentity]],
]) {
  test(`identity readiness rejects when ${name}`, async () => {
    const state = reader([values])
    await assert.rejects(expectWorkshopIdentity(state.page, expectedIdentity), (error) => {
      assert.match(error.message, /Taller administración A/)
      assert.match(error.message, /Timeout/)
      return true
    })
    assert.ok(state.reads() > 1, 'negative control must exhaust retrying, not fail a snapshot')
  })
}

test('administration waits for identity before any theme capture without changing its budget', () => {
  const source = readFileSync(new URL('../../e2e/administration.spec.ts', import.meta.url), 'utf8')
  const start = source.indexOf("test('administration preserves mounted drafts")
  const loop = source.indexOf('for (const [index, theme] of THEMES.entries())', start)
  assert.ok(start >= 0 && loop > start)
  assert.match(source.slice(start, loop), /await expectWorkshopIdentity\(page, expectedIdentity\)/)
  const helper = readFileSync(
    new URL('../../e2e/helpers/workshop-identity.mjs', import.meta.url),
    'utf8',
  )
  assert.doesNotMatch(helper, /timeout\s*:|intervals\s*:|waitForTimeout|\.configure\(/)
})
