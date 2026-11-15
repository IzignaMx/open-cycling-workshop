import test from 'node:test'
import assert from 'node:assert/strict'
import {
  runCrashRecovery,
  parseProcessStat,
  scanInventory,
  identifyCrashProcess,
  waitCrashAbsent,
} from './process-crash.mjs'
const proc = (pid, starttime = '100', pgrp = pid, session = pid) => ({
  pid,
  starttime,
  pgrp,
  session,
})
const stat = (p) =>
  `${p.pid} (chrome ) worker) S 1 ${p.pgrp} ${p.session} ${Array(15).fill('0').join(' ')} ${p.starttime} 0`
const missing = () => {
  throw Object.assign(Error('gone'), { code: 'ENOENT' })
}
function fake(mode) {
  const calls = []
  let phase = 0
  let dead = false
  const profiles = {
    create: async () => '/owned',
    verify: async () => {
      calls.push('verify')
      if (mode === 'sentinel') throw Error('sentinel')
    },
    remove: async () => calls.push('remove'),
  }
  const launch = async (p, o) => {
    phase++
    dead = false
    calls.push(`launch${phase}:${o.offline}`)
    let connected = true,
      closed = false
    return {
      browser: () => ({
        isConnected: () => connected,
        newBrowserCDPSession: async () => ({
          send: async (command) => {
            calls.push(command)
            if (mode === 'hang') return new Promise(() => {})
            if (mode === 'unsupported')
              throw Error("Protocol error (Browser.crash): 'Browser.crash' wasn't found")
            if (mode === 'protocol') throw Error('Protocol error invalid parameters')
            dead = true
            connected = mode === 'connected'
            closed = mode !== 'pages'
            if (mode === 'transport') throw Error('Target closed')
            return {}
          },
          detach: async () => {},
        }),
      }),
      pages: () => [
        {
          url: () => (mode === 'notblank' && phase === 2 ? 'https://invalid' : 'about:blank'),
          isClosed: () => closed,
        },
      ],
      close: async () => {
        calls.push(`close${phase}`)
        connected = false
        closed = true
        dead = true
      },
    }
  }
  let inspections = 0
  const identify = async () => {
    inspections++
    const p = proc(
      mode === 'samepid' ? 42 : 41 + phase,
      mode === 'changed' && inspections === 2 ? '101' : '100',
    )
    return { ...p, cmdline: 'chrome\0--user-data-dir=/owned\0', known: [p] }
  }
  return {
    calls,
    options: {
      launch,
      profiles,
      identify,
      inventory: async () =>
        mode === 'inventoryerror'
          ? Promise.reject(Error('EACCES'))
          : dead
            ? mode === 'survivor'
              ? [proc(55, '100', 42, 42)]
              : []
            : [proc(41 + phase)],
      first: async () => {
        calls.push('first')
        return 'before'
      },
      second: async (c, b, r) => {
        assert.equal(b, 'before')
        assert.equal(r.crashReceipt.method, 'Browser.crash')
        calls.push('second')
      },
      finish: async (c, p) => {
        calls.push(`trace${p}`)
        if (mode === 'trace' && p === 1) throw Error('trace failed')
      },
      limits: { timeoutMs: 30, attempts: 2, pollMs: 1 },
    },
  }
}
test('parse metadata safely with parentheses', () =>
  assert.deepEqual(parseProcessStat(stat(proc(42)), 42), proc(42)))
test('crash precedes offline recovery and only recovery is closed', async () => {
  const f = fake()
  const r = await runCrashRecovery(f.options)
  assert.equal(r.crashReceipt.groupAbsent, true)
  assert.equal(f.calls.filter((c) => c === 'Browser.crash').length, 1)
  assert.ok(f.calls.indexOf('trace1') < f.calls.indexOf('Browser.crash'))
  assert.ok(f.calls.indexOf('Browser.crash') < f.calls.indexOf('launch2:true'))
  assert.ok(!f.calls.includes('close1'))
  assert.ok(f.calls.includes('close2'))
  assert.ok(f.calls.includes('remove'))
})
test('transport closure accepted only with complete absence', async () => {
  const f = fake('transport')
  assert.equal((await runCrashRecovery(f.options)).crashReceipt.commandOutcome, 'transport-closed')
})
for (const mode of [
  'unsupported',
  'protocol',
  'hang',
  'connected',
  'pages',
  'survivor',
  'inventoryerror',
])
  test(`post-dispatch uncertainty ${mode} retains profile without fallback close/relaunch`, async () => {
    const f = fake(mode)
    await assert.rejects(runCrashRecovery(f.options))
    assert.ok(!f.calls.includes('close1'))
    assert.ok(!f.calls.includes('launch2:true'))
    assert.ok(!f.calls.includes('remove'))
  })
for (const mode of ['changed', 'trace', 'sentinel'])
  test(`pre-dispatch ${mode} never crashes`, async () => {
    const f = fake(mode)
    await assert.rejects(runCrashRecovery(f.options))
    assert.ok(!f.calls.includes('Browser.crash'))
    assert.ok(!f.calls.includes('launch2:true'))
  })
for (const mode of ['samepid', 'notblank'])
  test(`recovery ${mode} cannot qualify`, async () => {
    const f = fake(mode)
    await assert.rejects(runCrashRecovery(f.options))
    assert.ok(!f.calls.includes('second'))
    assert.ok(f.calls.includes('close2'))
  })
test('inventory reads metadata only and fails permission errors', async () => {
  const paths = []
  const list = async () => ['42', 'abc', '43']
  const read = async (path) => {
    paths.push(path)
    return path.includes('/42/') ? stat(proc(42)) : missing()
  }
  assert.deepEqual(await scanInventory({ list, read }), [proc(42)])
  assert.deepEqual(paths, ['/proc/42/stat', '/proc/43/stat'])
  await assert.rejects(
    scanInventory({
      list,
      read: async () => {
        throw Object.assign(Error('denied'), { code: 'EACCES' })
      },
    }),
    /denied/,
  )
})
test('PID reuse and escaped known process fail absence', async () => {
  for (const p of [proc(42, '200'), proc(77, '100', 88, 88)])
    await assert.rejects(
      waitCrashAbsent(
        { ...proc(42), known: [proc(42), proc(77)] },
        { inventory: async () => [p], attempts: 1, timeoutMs: 30 },
      ),
      /reuse|remain/,
    )
})
test('identity binds owned profile and independent group/session leader', async () => {
  const context = {
    browser: () => ({
      isConnected: () => true,
      newBrowserCDPSession: async () => ({
        send: async () => ({
          processInfo: [
            { type: 'browser', id: 42 },
            { type: 'renderer', id: 43 },
          ],
        }),
        detach: async () => {},
      }),
    }),
  }
  const read = async (path) =>
    path.endsWith('cmdline')
      ? 'chrome\0--user-data-dir=/owned\0'
      : stat(proc(Number(path.split('/')[2]), '100', 42, 42))
  const inventory = async () => [proc(42), proc(43, '100', 42, 42), proc(99)]
  const r = await identifyCrashProcess(context, '/owned', { read, inventory, platform: 'linux' })
  assert.equal(r.known.length, 2)
  await assert.rejects(
    identifyCrashProcess(context, '/other', { read, inventory, platform: 'linux' }),
    /profile/,
  )
  await assert.rejects(
    identifyCrashProcess(context, '/owned', {
      read: async (path) =>
        path.endsWith('cmdline') ? 'chrome\0--user-data-dir=/owned\0' : stat(proc(42, '100', 7, 7)),
      inventory,
      platform: 'linux',
    }),
    /leader/,
  )
})
test('CDP process outside owned group/session is rejected before dispatch', async () => {
  const context = {
    browser: () => ({
      isConnected: () => true,
      newBrowserCDPSession: async () => ({
        send: async () => ({
          processInfo: [
            { type: 'browser', id: 42 },
            { type: 'renderer', id: 43 },
          ],
        }),
        detach: async () => {},
      }),
    }),
  }
  await assert.rejects(
    identifyCrashProcess(context, '/owned', {
      platform: 'linux',
      read: async (path) =>
        path.endsWith('cmdline')
          ? 'chrome\0--user-data-dir=/owned\0'
          : stat(proc(Number(path.split('/')[2]))),
      inventory: async () => [proc(42), proc(43)],
    }),
    /outside owned/,
  )
})
test('failed dispatched crash preserves attempt receipt', async () => {
  const f = fake('unsupported')
  await assert.rejects(runCrashRecovery(f.options), (e) => {
    assert.deepEqual(e.crashAttempt, {
      method: 'Browser.crash',
      dispatched: true,
      commandOutcome: 'failed',
      terminationVerified: false,
    })
    return true
  })
})
test('returning process before recovery launch retains profile', async () => {
  const f = fake()
  let scans = 0
  f.options.inventory = async () => (++scans === 1 ? [] : [proc(42)])
  await assert.rejects(runCrashRecovery(f.options))
  assert.ok(!f.calls.includes('launch2:true'))
  assert.ok(!f.calls.includes('remove'))
})
test('PID reuse before profile deletion retains profile', async () => {
  const f = fake()
  let scans = 0
  f.options.inventory = async () => (++scans < 4 ? [] : [proc(42, '999')])
  await assert.rejects(runCrashRecovery(f.options), /reuse/)
  assert.ok(!f.calls.includes('remove'))
})
test('events retain sanitized immutable dispatch and failure evidence', async () => {
  const f = fake('unsupported'),
    events = []
  f.options.onEvent = (e) => {
    events.push(e)
    assert.ok(Object.isFrozen(e))
    assert.ok(!JSON.stringify(e).includes('cmdline'))
  }
  await assert.rejects(runCrashRecovery(f.options))
  assert.ok(events.some((e) => e.stage === 'dispatch-begin'))
  assert.equal(events.at(-1).stage, 'failure')
  assert.equal(events.at(-1).crashAttempt.commandOutcome, 'failed')
  assert.ok(
    events.findIndex((e) => e.stage === 'dispatch-begin') <
      events.findIndex((e) => e.stage === 'failure'),
  )
})
test('event consumer refusal before dispatch does not crash', async () => {
  const f = fake()
  f.options.onEvent = (e) => {
    if (e.stage === 'dispatch-begin') throw Error('collector failed')
  }
  await assert.rejects(runCrashRecovery(f.options))
  assert.ok(!f.calls.includes('Browser.crash'))
})
for (const text of ['', '42 chrome S', stat(proc(43)), stat(proc(42)).replace('100 0', 'bad 0')])
  test(`malformed metadata refused: ${text}`, () => assert.throws(() => parseProcessStat(text, 42)))
test('missing mandatory trace exporter refuses before creating profile', async () => {
  const f = fake()
  delete f.options.finish
  await assert.rejects(runCrashRecovery(f.options), /exporter/)
  assert.deepEqual(f.calls, [])
})
test('owned process inspection timeout never crashes and retains profile', async () => {
  const f = fake()
  f.options.identify = () => new Promise(() => {})
  await assert.rejects(runCrashRecovery(f.options))
  assert.ok(!f.calls.includes('Browser.crash'))
  assert.ok(!f.calls.includes('remove'))
  assert.equal(f.calls.filter((c) => c === 'close1').length, 1)
})
test('ambiguous recovery launch never deletes retained profile', async () => {
  const f = fake()
  const launch = f.options.launch
  f.options.launch = async (p, o) => {
    if (o.offline) throw Error('uncertain recovery launch')
    return launch(p, o)
  }
  await assert.rejects(runCrashRecovery(f.options), /uncertain recovery/)
  assert.ok(!f.calls.includes('remove'))
  assert.ok(!f.calls.includes('close1'))
})
test('recovery trace failure closes recovery once before propagating', async () => {
  const f = fake()
  const finish = f.options.finish
  f.options.finish = async (c, p) => {
    if (p === 2) throw Error('recovery trace failed')
    await finish(c, p)
  }
  await assert.rejects(runCrashRecovery(f.options), /recovery trace/)
  assert.equal(f.calls.filter((c) => c === 'close2').length, 1)
})
test('recovery close uncertainty retains profile without repeated close', async () => {
  const f = fake()
  const launch = f.options.launch
  f.options.launch = async (p, o) => {
    const c = await launch(p, o)
    if (o.offline)
      c.close = async () => {
        f.calls.push('close2')
        throw Error('close uncertain')
      }
    return c
  }
  await assert.rejects(runCrashRecovery(f.options), /close uncertain/)
  assert.ok(!f.calls.includes('remove'))
  assert.equal(f.calls.filter((c) => c === 'close2').length, 1)
})
test('owned profile exact argument rejects prefix spoof and duplicates', async () => {
  for (const args of [
    'chrome\0--user-data-dir=/owned-extra\0',
    'chrome\0--user-data-dir=/owned\0--user-data-dir=/other\0',
  ]) {
    const context = {
      browser: () => ({
        isConnected: () => true,
        newBrowserCDPSession: async () => ({
          send: async () => ({ processInfo: [{ type: 'browser', id: 42 }] }),
          detach: async () => {},
        }),
      }),
    }
    await assert.rejects(
      identifyCrashProcess(context, '/owned', {
        platform: 'linux',
        read: async (path) => (path.endsWith('cmdline') ? args : stat(proc(42))),
        inventory: async () => [proc(42)],
      }),
      /profile/,
    )
  }
})
test('pinned TargetClosedError prefix and browser logs accepted with full absence only', async () => {
  const f = fake('transport')
  const launch = f.options.launch
  f.options.launch = async (...args) => {
    const c = await launch(...args),
      browser = c.browser(),
      session = await browser.newBrowserCDPSession(),
      send = session.send
    session.send = async (command) => {
      try {
        return await send(command)
      } catch {
        throw Error(
          'cdpSession.send: Target page, context or browser has been closed\nBrowser logs:\nsynthetic',
        )
      }
    }
    c.browser = () => ({ ...browser, newBrowserCDPSession: async () => session })
    return c
  }
  assert.equal((await runCrashRecovery(f.options)).crashReceipt.commandOutcome, 'transport-closed')
})
test('hung inventory fails bounded without recovery or deletion', async () => {
  const f = fake()
  f.options.inventory = () => new Promise(() => {})
  await assert.rejects(runCrashRecovery(f.options), /timeout/)
  assert.ok(!f.calls.includes('launch2:true'))
  assert.ok(!f.calls.includes('remove'))
  assert.ok(!f.calls.includes('close1'))
})
test('helper never uses OS signals or command execution', async () => {
  const { readFile } = await import('node:fs/promises')
  const source = await readFile(new URL('./process-crash.mjs', import.meta.url), 'utf8')
  assert.doesNotMatch(
    source,
    /process\.kill|child_process|\.kill\(|SIGKILL|SIGTERM|execFile|spawn\(/,
  )
})
function pendingFake(mode) {
  const f = fake(mode),
    launch = f.options.launch
  let rejectCommand
  f.options.launch = async (...args) => {
    const c = await launch(...args)
    if (args[1].offline) return c
    const browser = c.browser(),
      session = await browser.newBrowserCDPSession(),
      send = session.send
    session.send = async (command) => {
      const pending = new Promise((_, reject) => {
        rejectCommand = reject
      })
      if (mode !== 'hang') await send(command)
      return pending
    }
    c.browser = () => ({ ...browser, newBrowserCDPSession: async () => session })
    return c
  }
  return {
    ...f,
    reject: () => rejectCommand(Error('Protocol error (Browser.crash): method not found')),
  }
}
test('pending crash command qualifies only through independent complete termination', async () => {
  const f = pendingFake()
  const events = []
  f.options.onEvent = (e) => events.push(e)
  const result = await runCrashRecovery(f.options)
  assert.equal(result.crashReceipt.commandOutcome, 'unacknowledged-terminated')
  assert.equal(result.crashReceipt.procAbsent, true)
  assert.equal(result.crashReceipt.browserDisconnected, true)
  assert.equal(events.find((e) => e.stage === 'absence').crashAttempt.terminationVerified, true)
  assert.equal(f.calls.filter((c) => c === 'Browser.crash').length, 1)
  assert.ok(!f.calls.includes('close1'))
  assert.ok(f.calls.includes('launch2:true'))
  assert.ok(f.calls.includes('remove'))
})
for (const mode of ['hang', 'connected', 'pages', 'inventoryerror', 'survivor'])
  test(`pending command with ${mode} never recovers`, async () => {
    const f = pendingFake(mode)
    await assert.rejects(runCrashRecovery(f.options))
    assert.ok(!f.calls.includes('launch2:true'))
    assert.ok(!f.calls.includes('remove'))
    assert.ok(!f.calls.includes('close1'))
  })
test('pending command PID reuse never recovers', async () => {
  const f = pendingFake()
  f.options.inventory = async () => [proc(42, '999')]
  await assert.rejects(runCrashRecovery(f.options), /reuse/)
  assert.ok(!f.calls.includes('launch2:true'))
  assert.ok(!f.calls.includes('remove'))
})
test('protocol rejection during independent observation vetoes absence', async () => {
  const f = pendingFake()
  f.options.inventory = async () => {
    f.reject()
    return []
  }
  await assert.rejects(runCrashRecovery(f.options), /method not found/)
  assert.ok(!f.calls.includes('launch2:true'))
  assert.ok(!f.calls.includes('remove'))
})
test('late protocol rejection at reopen gate vetoes recovery', async () => {
  const f = pendingFake()
  let scans = 0
  f.options.inventory = async () => {
    if (++scans === 2) f.reject()
    return []
  }
  await assert.rejects(runCrashRecovery(f.options), /method not found/)
  assert.ok(!f.calls.includes('launch2:true'))
  assert.ok(!f.calls.includes('remove'))
})
test('late protocol rejection at deletion gate retains profile', async () => {
  const f = pendingFake()
  let scans = 0
  f.options.inventory = async () => {
    if (++scans === 4) f.reject()
    return []
  }
  await assert.rejects(runCrashRecovery(f.options), /method not found/)
  assert.ok(f.calls.includes('launch2:true'))
  assert.ok(!f.calls.includes('remove'))
})
test('complete termination need not wait for the command deadline', { timeout: 1000 }, async () => {
  const f = pendingFake()
  f.options.limits.timeoutMs = 5000
  assert.equal(
    (await runCrashRecovery(f.options)).crashReceipt.commandOutcome,
    'unacknowledged-terminated',
  )
})
test('late protocol rejection at final return gate is not reported as success', async () => {
  const f = pendingFake()
  const remove = f.options.profiles.remove
  f.options.profiles.remove = async () => {
    await remove()
    f.reject()
  }
  await assert.rejects(runCrashRecovery(f.options), /method not found/)
  assert.ok(f.calls.includes('remove'))
})
test('command rejection after failed observation remains handled', async () => {
  const f = pendingFake('connected')
  await assert.rejects(runCrashRecovery(f.options))
  f.reject()
  await new Promise((resolve) => setImmediate(resolve))
  assert.ok(!f.calls.includes('launch2:true'))
  assert.ok(!f.calls.includes('remove'))
})
