import assert from 'node:assert/strict'
import test from 'node:test'
import { checkedInOpenBranding } from './readiness-helper.mjs'

// The browser transport is unavailable in the local executor. Model only its
// read-only locator observations; execute the real helper and Playwright expect.
// Native DOM coverage lives in branding-readiness.spec.ts, not in this model.
function observationPage(initial, afterSessionRead) {
  let state = initial
  let clicks = 0
  const assertions = []
  class Locator {
    constructor(kind, enabledOnly = false) {
      this._apiName = 'Locator'
      this.kind = kind
      this.enabledOnly = enabledOnly
    }
    visible() {
      if (this.kind === 'navigation') return false
      if (this.kind === 'session' || this.kind === 'branding') return state === 'connected'
      if (this.kind === 'verify')
        return state === 'enabled' || (state === 'verifying' && !this.enabledOnly)
      throw new Error(`Unexpected locator: ${this.kind}`)
    }
    async isVisible() {
      const visible = this.visible()
      if (this.kind === 'session' && afterSessionRead) {
        state = afterSessionRead
        afterSessionRead = undefined
      }
      return visible
    }
    and(other) {
      assert.equal(other.kind, 'enabled')
      return new Locator(this.kind, true)
    }
    or(other) {
      const union = new Locator('union')
      union.visible = () => this.visible() || other.visible()
      return union
    }
    async click() {
      assert.equal(this.kind, 'verify')
      assert.equal(state, 'enabled', 'never click a missing or disabled verification button')
      clicks++
      state = 'connected'
    }
    async _expect(expression) {
      assertions.push([this.kind, expression])
      assert.ok(['to.be.visible', 'to.be.enabled'].includes(expression))
      const matches =
        expression === 'to.be.visible'
          ? this.visible()
          : this.kind === 'verify' && state === 'enabled'
      return {
        matches,
        received: matches ? 'visible' : 'element(s) not found',
        log: [],
        timedOut: !matches,
      }
    }
  }
  return {
    page: {
      getByRole(role, { name, exact }) {
        assert.equal(exact, true)
        const kind = new Map([
          ['link:Administración', 'navigation'],
          ['button:Verificar acceso a administración', 'verify'],
          ['heading:Mi sesión', 'session'],
          ['region:Marca compartida del taller', 'branding'],
        ]).get(`${role}:${name}`)
        assert.ok(kind, 'use the exact accessible target')
        return new Locator(kind)
      },
      locator(selector) {
        assert.equal(selector, ':enabled')
        return new Locator('enabled')
      },
    },
    clicks: () => clicks,
    assertions,
  }
}

for (const [name, initial, transition, clicks] of [
  ['already connected', 'connected', undefined, 0],
  ['explicit verification', 'enabled', undefined, 1],
  ['automatic admission replaces the disabled button', 'verifying', 'connected', 0],
  ['verification becomes available', 'verifying', 'enabled', 1],
]) {
  test(`branding readiness: ${name}`, async () => {
    const state = observationPage(initial, transition)
    await checkedInOpenBranding()(state.page)
    assert.equal(state.clicks(), clicks)
    assert.deepEqual(state.assertions.slice(-2), [
      ['session', 'to.be.visible'],
      ['branding', 'to.be.visible'],
    ])
  })
}

test('branding readiness refuses a permanently disabled verification button', async () => {
  const state = observationPage('verifying')
  await assert.rejects(checkedInOpenBranding()(state.page), /expect\(|Timeout/)
  assert.equal(state.clicks(), 0)
  assert.ok(!state.assertions.some(([kind]) => kind === 'branding'))
})

test('branding readiness refuses missing administration', async () => {
  const state = observationPage('absent')
  await assert.rejects(checkedInOpenBranding()(state.page), /expect\(|Timeout/)
  assert.equal(state.clicks(), 0)
})
