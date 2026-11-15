import test from 'node:test'
import assert from 'node:assert/strict'
import { parseStat, browserPid, waitAbsent, runRestart, identify } from './process-restart.mjs'
const stat = (pid = 42, start = '900') =>
  `${pid} (chrome ) worker) S ${Array(18).fill('0').join(' ')} ${start} 0`
test('parses proc stat with spaces and closing parentheses in comm', () =>
  assert.deepEqual(parseStat(stat(), 42), { pid: 42, starttime: '900' }))
for (const invalid of ['', '42 chrome S', stat(43), stat(42, 'bad')])
  test(`rejects malformed stat ${invalid}`, () => assert.throws(() => parseStat(invalid, 42)))
test('exactly one valid browser PID required', () => {
  assert.equal(
    browserPid({
      processInfo: [
        { type: 'browser', id: 42 },
        { type: 'renderer', id: 43 },
      ],
    }),
    42,
  )
  for (const processInfo of [
    [],
    [{ type: 'browser', id: 0 }],
    [{ type: 'browser', id: 1.5 }],
    [
      { type: 'browser', id: 42 },
      { type: 'browser', id: 43 },
    ],
  ])
    assert.throws(() => browserPid({ processInfo }))
})
const absent = () => {
  throw Object.assign(Error('gone'), { code: 'ENOENT' })
}
test('absence requires ENOENT, not mere disconnect or changed process', async () => {
  let reads = 0
  await waitAbsent(42, {
    read: async () => {
      if (++reads < 3) return stat()
      return absent()
    },
    delay: async () => {},
    attempts: 3,
  })
  assert.equal(reads, 3)
  await assert.rejects(
    waitAbsent(42, { read: async () => stat(42, '901'), delay: async () => {}, attempts: 2 }),
    /still exists/,
  )
})
for (const code of ['EPERM', 'EACCES', 'EIO'])
  test(`proc ${code} fails closed`, async () => {
    await assert.rejects(
      waitAbsent(42, {
        read: async () => {
          throw Object.assign(Error(code), { code })
        },
      }),
      new RegExp(code),
    )
  })
function fake({ samePid = false, badPage = false, failClose = false, failSecond = false } = {}) {
  const calls = []
  let count = 0
  const profiles = {
    create: async () => '/synthetic/profile',
    verify: async (p) => {
      assert.equal(p, '/synthetic/profile')
      calls.push('verify')
    },
    remove: async () => calls.push('remove'),
  }
  const launch = async (profile, options) => {
    calls.push(['launch', profile, options.offline])
    const phase = ++count
    if (failSecond && phase === 2) throw Error('launch uncertain')
    let connected = true
    let closed = false
    const page = {
      url: () => (badPage && phase === 2 ? 'https://unexpected.invalid' : 'about:blank'),
      isClosed: () => closed,
    }
    const browser = { isConnected: () => connected }
    return {
      browser: () => browser,
      pages: () => [page],
      close: async () => {
        calls.push('close')
        if (failClose) throw Error('close failed')
        connected = false
        closed = true
      },
    }
  }
  const identify = async (_context, profile) => {
    assert.equal(profile, '/synthetic/profile')
    return { pid: samePid ? 42 : 41 + count, starttime: String(count) }
  }
  const absent = async (pid) => calls.push(['absent', pid])
  return {
    calls,
    options: {
      launch,
      profiles,
      identify,
      absent,
      first: async () => {
        calls.push('first')
        return 'original-before'
      },
      second: async (_c, before) => {
        assert.equal(before, 'original-before')
        calls.push('second')
      },
    },
  }
}
test('lifecycle closes and proves absence before same profile offline launch', async () => {
  const { calls, options } = fake()
  await runRestart(options)
  assert.deepEqual(
    calls.filter((x) => Array.isArray(x) || ['close', 'first', 'second', 'remove'].includes(x)),
    [
      ['launch', '/synthetic/profile', false],
      'first',
      'close',
      ['absent', 42],
      ['launch', '/synthetic/profile', true],
      'second',
      'close',
      ['absent', 43],
      'remove',
    ],
  )
})
for (const [option, message] of [
  ['samePid', /fresh PID/],
  ['badPage', /blank/],
  ['failClose', /close failed/],
  ['failSecond', /launch uncertain/],
])
  test(`negative lifecycle ${option}`, async () => {
    const { calls, options } = fake({ [option]: true })
    await assert.rejects(runRestart(options), message)
    assert.equal(calls.includes('second'), false)
    if (option === 'failClose' || option === 'failSecond')
      assert.equal(calls.includes('remove'), false)
  })
test('changed profile sentinel stops launch and removal', async () => {
  const { calls, options } = fake()
  options.profiles.verify = async () => {
    throw Error('profile identity changed')
  }
  await assert.rejects(runRestart(options), (error) => {
    assert.ok(error instanceof AggregateError)
    assert.ok(error.errors.every((e) => /identity/.test(e.message)))
    return true
  })
  assert.deepEqual(calls, [])
})

test('termination timeout prevents second launch and profile removal', async () => {
  const { calls, options } = fake()
  options.absent = async () => {
    throw Error('process still exists')
  }
  await assert.rejects(runRestart(options), /still exists/)
  assert.equal(calls.filter((x) => Array.isArray(x) && x[0] === 'launch').length, 1)
  assert.equal(calls.includes('remove'), false)
})
test('closed context without closed pages cannot qualify restart', async () => {
  const { calls, options } = fake()
  const launch = options.launch
  options.launch = async (...args) => {
    const c = await launch(...args)
    c.pages()[0].isClosed = () => false
    return c
  }
  await assert.rejects(runRestart(options), /pages did not close/)
  assert.equal(calls.includes('second'), false)
  assert.equal(calls.includes('remove'), false)
})
test('first phase failure still closes verified owned process before deleting profile', async () => {
  const { calls, options } = fake()
  options.first = async () => {
    throw Error('fixture failed')
  }
  await assert.rejects(runRestart(options), /fixture failed/)
  assert.equal(calls.includes('remove'), true)
  assert.equal(calls.includes('second'), false)
})
test('unknown identity closes context but retains profile and never relaunches', async () => {
  const { calls, options } = fake()
  options.identify = async () => {
    throw Error('CDP unavailable')
  }
  await assert.rejects(runRestart(options), (error) => {
    assert.ok(error instanceof AggregateError)
    assert.match(error.errors[0].message, /CDP unavailable/)
    assert.match(error.errors[1].message, /unknown process/)
    return true
  })
  assert.equal(calls.includes('close'), true)
  assert.equal(calls.includes('remove'), false)
  assert.equal(calls.includes('second'), false)
})

test('identity binds CDP browser PID, proc starttime and exact owned profile argument', async () => {
  let detached = 0
  const context = {
    browser: () => ({
      isConnected: () => true,
      newBrowserCDPSession: async () => ({
        send: async (command) => {
          assert.equal(command, 'SystemInfo.getProcessInfo')
          return { processInfo: [{ type: 'browser', id: 42 }] }
        },
        detach: async () => {
          detached++
        },
      }),
    }),
  }
  const read = async (path) =>
    path.endsWith('/stat') ? stat() : 'chrome\0--user-data-dir=/owned/profile\0'
  assert.deepEqual(await identify(context, '/owned/profile', { read, platform: 'linux' }), {
    pid: 42,
    starttime: '900',
  })
  await assert.rejects(
    identify(context, '/other/profile', { read, platform: 'linux' }),
    /owned profile/,
  )
  assert.equal(detached, 2)
})
test('trace failure still closes process, removes only safe profile and does not relaunch', async () => {
  const { calls, options } = fake()
  options.finish = async () => {
    throw Error('trace failed')
  }
  await assert.rejects(runRestart(options), /trace failed/)
  assert.equal(calls.filter((x) => x === 'close').length, 1)
  assert.equal(calls.includes('remove'), true)
  assert.equal(calls.includes('second'), false)
})
test('primary and cleanup errors are retained without repeating close', async () => {
  const { calls, options } = fake({ failClose: true })
  options.first = async () => {
    throw Error('assertion failed')
  }
  await assert.rejects(runRestart(options), (error) => {
    assert.ok(error instanceof AggregateError)
    assert.deepEqual(
      error.errors.map((e) => e.message),
      ['assertion failed', 'close failed'],
    )
    return true
  })
  assert.equal(calls.filter((x) => x === 'close').length, 1)
  assert.equal(calls.includes('remove'), false)
})

// Configuration regression only: no native browser execution is implied.
test('restart suite opts out of runner tracing while reload keeps global tracing', async () => {
  const { readFileSync } = await import('node:fs')
  const { default: ts } = await import('typescript')
  function declarations(path) {
    const registered = []
    let use = { trace: 'on' }
    const register = (name) => registered.push({ name, use: { ...use } })
    register.use = (value) => {
      use = { ...use, ...value }
    }
    const source = readFileSync(new URL(path, import.meta.url), 'utf8')
    const output = ts.transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    }).outputText
    const exports = {}
    new Function('require', 'exports', output)(
      (name) =>
        name === '@playwright/test'
          ? { test: register, defineConfig: (value) => value, devices: { 'Desktop Chrome': {} } }
          : {},
      exports,
    )
    return { registered, config: exports.default, source }
  }
  const global = declarations('../../playwright.capture-app.config.ts')
  assert.equal(global.config.use.trace, 'on')
  const restart = declarations('../../tests/access-kernel/capture-app-process-restart.spec.ts')
  const reload = declarations('../../tests/access-kernel/capture-app-native.spec.ts')
  assert.equal(restart.registered.length, 2)
  assert.equal(reload.registered.length, 2)
  for (const entry of restart.registered) assert.equal(entry.use.trace, 'off')
  for (const entry of reload.registered) assert.equal(entry.use.trace, 'on')
  assert.match(restart.source, /context\.tracing\.start\(/)
  assert.match(restart.source, /context\.tracing\.stop\(\{ path \}\)/)
  assert.match(restart.source, /process-phase-\$\{phase\}\.zip/)
})
