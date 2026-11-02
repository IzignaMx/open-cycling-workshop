import assert from 'node:assert/strict'
import test from 'node:test'
import { appHarness } from './capture-component-host.mjs'

function nodes(n) {
  return !n || typeof n !== 'object'
    ? []
    : [n, ...[n.props?.children].flat(Infinity).flatMap(nodes)]
}
for (const path of ['cancel', 'administration', 'login']) {
  for (const accepted of [false, true]) {
    test(`nonready capture voluntary ${path}: confirmation ${accepted ? 'accepts' : 'cancels'} exactly once`, async (t) => {
      const priorWindow = globalThis.window,
        priorDocument = globalThis.document
      const prompts = [],
        calls = []
      globalThis.window = {
        confirm: (message) => {
          prompts.push(message)
          return accepted
        },
      }
      globalThis.document = { querySelector: () => null }
      t.after(() => {
        globalThis.window = priorWindow
        globalThis.document = priorDocument
      })
      const state = {
        phase: path === 'login' ? 'held' : 'verifying',
        identityKey: 'masked',
        user: null,
        context: null,
      }
      const runtime = {
        subscribe() {},
        getSnapshot: () => state,
        branding: { subscribe() {}, getSnapshot: () => ({}) },
        sessionStore: { getToken: () => 'retained' },
        hasUnsentCaptures: () => true,
        logout: async () => {
          calls.push('logout')
        },
        login: async (input) => {
          calls.push(input)
        },
      }
      const app = appHarness(runtime, { layoutEffects: true }),
        tree = app.render()
      if (path === 'cancel')
        await nodes(tree)
          .find((n) => n.props?.children === 'Cancelar')
          .props.onClick()
      else if (path === 'administration') {
        if (app.logoutGuard()()) await runtime.logout()
      } else
        await nodes(tree)
          .find((n) => n.type?.name === 'LoginForm')
          .props.onLogin({ username: 'replacement' })
      assert.equal(
        prompts.length,
        1,
        'masked owner protection must still ask before voluntary discard',
      )
      assert.match(prompts[0], /no confirma ni revierte/)
      assert.equal(calls.length, accepted ? 1 : 0)
    })
  }
}
