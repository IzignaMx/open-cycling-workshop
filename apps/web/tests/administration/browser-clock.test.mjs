import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import vm from 'node:vm'
import ts from 'typescript'

// Execute the pinned Playwright implementation, rather than reproducing its
// clock arithmetic in a mock. This is protocol/clock evidence, not browser QA.
const require = createRequire(import.meta.url)
const playwrightRequire = createRequire(require.resolve('@playwright/test'))
const coreRequire = createRequire(playwrightRequire.resolve('playwright'))
const bundle = readFileSync(
  join(dirname(coreRequire.resolve('playwright-core/package.json')), 'lib/coreBundle.js'),
  'utf8',
)
function section(start, end) {
  const first = bundle.indexOf(start)
  const last = bundle.indexOf(end, first + start.length)
  assert.ok(first >= 0 && last > first, `installed Playwright must expose ${start}`)
  return bundle.slice(first, last)
}
const injected = section(
  '// packages/playwright-core/src/generated/clockSource.ts',
  '// packages/protocol/src/serializers.ts',
)
const server = section(
  '// packages/playwright-core/src/server/clock.ts',
  '// packages/playwright-core/src/generated/webAuthnSource.ts',
)
const epoch = Date.parse('2026-10-15T02:34:38Z')
class HostDate extends Date {
  constructor(...args) {
    super(...(args.length ? args : [epoch]))
  }
  static now() {
    return epoch
  }
}

function clockHarness(deliveryDelay) {
  let ticks = 0
  let nextTimer = 0
  const browser = vm.createContext({
    Date: HostDate,
    performance: { now: () => ticks },
    setTimeout: (callback, delay) => {
      if (delay === undefined || delay === 0) queueMicrotask(callback)
      return ++nextTimer
    },
    clearTimeout: () => {},
    setInterval: () => ++nextTimer,
    clearInterval: () => {},
    Event: class {},
  })
  const context = {
    _browser: { options: { name: 'chromium' } },
    async addInitScript() {
      return { dispose: async () => {} }
    },
    async safeNonStallingEvaluateInAllFrames(script) {
      if (script.startsWith('globalThis.__pwClock.controller.pauseAt(')) {
        // The host has serialized the pause target. Browser monotonic time
        // advances before delivery, as it can while the runner is busy.
        vm.runInContext(
          'globalThis.beforePauseFired = 0; setTimeout(() => globalThis.beforePauseFired++, 5000)',
          browser,
        )
        ticks += deliveryDelay
        vm.runInContext('globalThis.__pwClock.controller.now()', browser)
      }
      await vm.runInContext(script, browser)
    },
  }
  const host = vm.createContext({
    Date: HostDate,
    nullProgress: {},
    init_progress: () => {},
    __esm: (definition) => Object.values(definition)[0],
  })
  vm.runInContext(`${injected}\n${server}\ninit_clock(); globalThis.ServerClock = Clock;`, host)
  const clock = new host.ServerClock(context)
  return {
    page: {
      clock: {
        install: (options) => clock.install(options?.time?.getTime()),
        pauseAt: (date) => clock.pauseAt(date.getTime()),
        setFixedTime: (date) => clock.setFixedTime(date.getTime()),
        setSystemTime: (date) => clock.setSystemTime(date.getTime()),
        runFor: (duration) => clock.runFor(duration),
      },
    },
    browser,
  }
}

function checkedInClockSetup() {
  const source = ts.createSourceFile(
    'administration.spec.ts',
    readFileSync(new URL('../../e2e/administration.spec.ts', import.meta.url), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
  )
  const title =
    'UI lifecycle: automatic probe revalidation clears a newly entered administration secret'
  const declaration = source.statements.find(
    (statement) =>
      ts.isExpressionStatement(statement) &&
      ts.isCallExpression(statement.expression) &&
      statement.expression.arguments[0]?.text === title,
  )
  assert.ok(declaration, 'the exact probe-secret browser journey must remain registered')
  const statements = declaration.expression.arguments[1].body.statements
  const setup = statements
    .map((statement) => statement.getText(source))
    .filter(
      (text) =>
        /^const probeClockTime = /.test(text) ||
        /^await page\.clock\.(install|pauseAt|setFixedTime|setSystemTime)\(/.test(text),
    )
  assert.ok(setup.length > 0, 'execute the actual checked-in clock setup')
  return vm.runInNewContext(`(async (page, Date) => { ${setup.join('\n')} })`)
}

test('legacy install then host-now pause fails when delivery lets browser time advance', async () => {
  const { page } = clockHarness(25)
  await page.clock.install()
  await assert.rejects(page.clock.pauseAt(new HostDate()), /Cannot fast-forward to the past/)
})

for (const delay of [0, 25, 2_100]) {
  test(`probe-secret clock setup tolerates ${delay} ms delivery delay without firing its timer`, async () => {
    const { page, browser } = clockHarness(delay)
    await checkedInClockSetup()(page, HostDate)
    assert.equal(vm.runInContext('Date.now()', browser), epoch)
    assert.equal(vm.runInContext('performance.timeOrigin', browser), epoch)
    assert.equal(vm.runInContext('performance.now()', browser), delay)
    assert.equal(vm.runInContext('globalThis.beforePauseFired', browser), 0)
    vm.runInContext('globalThis.fired = 0; setTimeout(() => globalThis.fired++, 2000)', browser)
    assert.equal(vm.runInContext('globalThis.fired', browser), 0)
    await page.clock.runFor(1999)
    assert.equal(vm.runInContext('globalThis.fired', browser), 0)
    await page.clock.runFor(101)
    assert.equal(vm.runInContext('globalThis.fired', browser), 1)
    assert.equal(vm.runInContext('Date.now()', browser), epoch + 2100)
    assert.equal(vm.runInContext('globalThis.beforePauseFired', browser), 0)
    await page.clock.runFor(5000 - delay - 2100)
    assert.equal(vm.runInContext('globalThis.beforePauseFired', browser), 1)
  })
}
