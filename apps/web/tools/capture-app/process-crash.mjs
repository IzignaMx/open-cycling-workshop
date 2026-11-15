import assert from 'node:assert/strict'
import { mkdtemp, readFile, writeFile, realpath, rm, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { randomUUID, createHash } from 'node:crypto'
import { setTimeout as delay } from 'node:timers/promises'
import { browserPid } from './process-restart.mjs'

const defaults = { timeoutMs: 10000, attempts: 100, pollMs: 50 }
function bounds(limits = {}) {
  const result = { ...defaults, ...limits }
  for (const [key, max] of [
    ['timeoutMs', 30000],
    ['attempts', 100],
    ['pollMs', 1000],
  ])
    assert.ok(
      Number.isInteger(result[key]) && result[key] > 0 && result[key] <= max,
      `Invalid ${key}`,
    )
  return result
}
async function bounded(action, ms, label) {
  let timer
  try {
    return await Promise.race([
      Promise.resolve().then(action),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(Error(`${label} timeout`)), ms)
      }),
    ])
  } finally {
    clearTimeout(timer)
  }
}
export function parseProcessStat(text, pid) {
  assert.ok(Number.isSafeInteger(pid) && pid > 0, 'Invalid PID')
  const match = /^(\d+) \(.*\) ([A-Za-z]) (.*)$/s.exec(text.trim())
  assert.ok(match && Number(match[1]) === pid, 'Malformed proc PID')
  const fields = match[3].split(/\s+/)
  const pgrp = Number(fields[1]),
    session = Number(fields[2]),
    starttime = fields[18]
  assert.ok(
    Number.isSafeInteger(pgrp) && pgrp >= 0 && Number.isSafeInteger(session) && session >= 0,
    'Malformed proc group/session',
  )
  assert.match(starttime ?? '', /^\d+$/, 'Malformed proc starttime')
  return { pid, starttime, pgrp, session }
}
/** Metadata only for unrelated processes. Group/session observations do not prove escape containment. */
export async function scanInventory({ read = readFile, list = readdir } = {}) {
  const entries = await list('/proc')
  const inventory = []
  for (const entry of entries) {
    if (!/^\d+$/.test(entry)) continue
    const pid = Number(entry)
    try {
      inventory.push(parseProcessStat(await read(`/proc/${pid}/stat`, 'utf8'), pid))
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
  }
  return inventory
}
function sameIdentity(a, b) {
  assert.deepEqual(a, b, 'Process identity changed or PID reuse')
}
function mergeKnown(...sets) {
  const known = new Map()
  for (const set of sets)
    for (const p of set) {
      if (known.has(p.pid)) sameIdentity(known.get(p.pid), p)
      known.set(p.pid, p)
    }
  return [...known.values()].sort((a, b) => a.pid - b.pid)
}
export async function identifyCrashProcess(
  context,
  profile,
  {
    read = readFile,
    inventory = scanInventory,
    platform = process.platform,
    timeoutMs = 10000,
  } = {},
) {
  assert.equal(platform, 'linux', 'Crash qualification requires Linux procfs')
  const browser = context.browser()
  assert.ok(browser?.isConnected(), 'No connected owned browser')
  return bounded(
    async () => {
      const cdp = await browser.newBrowserCDPSession()
      try {
        const info = await cdp.send('SystemInfo.getProcessInfo')
        const pid = browserPid(info)
        const identity = parseProcessStat(await read(`/proc/${pid}/stat`, 'utf8'), pid)
        assert.ok(
          identity.pgrp === pid && identity.session === pid,
          'Browser must be independent group/session leader',
        )
        const cmdline = await read(`/proc/${pid}/cmdline`, 'utf8')
        const profileArgs = cmdline.split('\0').filter((a) => a.startsWith('--user-data-dir'))
        assert.deepEqual(
          profileArgs,
          [`--user-data-dir=${profile}`],
          'Browser owned profile argument mismatch',
        )
        const reported = []
        for (const entry of info.processInfo) {
          assert.ok(Number.isSafeInteger(entry.id) && entry.id > 0, 'Invalid CDP process PID')
          const process = parseProcessStat(await read(`/proc/${entry.id}/stat`, 'utf8'), entry.id)
          assert.ok(
            process.pgrp === pid && process.session === pid,
            'CDP process outside owned group/session',
          )
          reported.push(process)
        }
        const observed = await inventory()
        const leader = observed.find((p) => p.pid === pid)
        sameIdentity(identity, leader)
        const known = mergeKnown(
          [identity],
          reported,
          observed.filter((p) => p.pgrp === pid || p.session === pid),
        )
        sameIdentity(identity, parseProcessStat(await read(`/proc/${pid}/stat`, 'utf8'), pid))
        assert.equal(
          await read(`/proc/${pid}/cmdline`, 'utf8'),
          cmdline,
          'Browser command line changed',
        )
        return { ...identity, cmdline, known }
      } finally {
        await cdp.detach()
      }
    },
    timeoutMs,
    'Process identity inspection',
  )
}
export async function waitCrashAbsent(identity, { inventory = scanInventory, ...limits } = {}) {
  const b = bounds(limits)
  const deadline = performance.now() + b.timeoutMs
  for (let attempt = 0; attempt < b.attempts; attempt++) {
    const remaining = deadline - performance.now()
    assert.ok(remaining > 0, 'Process inventory timeout')
    const observed = await bounded(inventory, remaining, 'Process inventory')
    for (const known of identity.known) {
      const present = observed.find((p) => p.pid === known.pid)
      if (present) sameIdentity(known, present)
    }
    if (
      !observed.some(
        (p) =>
          p.pid === identity.pid ||
          identity.known.some((k) => k.pid === p.pid) ||
          p.pgrp === identity.pgrp ||
          p.session === identity.session,
      )
    )
      return
    if (attempt + 1 < b.attempts) await delay(b.pollMs)
  }
  throw Error('Known processes or group/session members remain after bounded wait')
}
function ownedProfiles() {
  let path
  const token = randomUUID()
  return {
    async create() {
      path = await realpath(await mkdtemp(join(tmpdir(), 'ocwp-capture-crash-')))
      await writeFile(join(path, '.ocwp-owned-test-profile'), token, { flag: 'wx' })
      return path
    },
    async verify(candidate) {
      assert.equal(candidate, path, 'Profile changed')
      assert.equal(await realpath(path), path, 'Profile canonical path changed')
      assert.equal(
        await readFile(join(path, '.ocwp-owned-test-profile'), 'utf8'),
        token,
        'Profile sentinel changed',
      )
    },
    async remove(candidate) {
      await this.verify(candidate)
      await rm(candidate, { recursive: true })
    },
  }
}
const termination = () => ({
  pagesClosed: true,
  browserDisconnected: true,
  procAbsent: true,
  groupAbsent: true,
  sessionAbsent: true,
})
// Deliberately narrow: protocol failures, including unsupported Browser.crash, never count as closure.
const transportClosed = (error) =>
  /^(?:cdpSession\.send: )?(?:Target closed|Target page, context or browser has been closed|Session closed\.?)(?:\n[^]*)?$/.test(
    error?.message ?? '',
  )
/** One CDP crash of a verified synthetic profile; no OS signals and no post-dispatch fallback close. */
export async function runCrashRecovery({
  launch,
  first,
  second,
  finish,
  profiles = ownedProfiles(),
  identify = identifyCrashProcess,
  inventory = scanInventory,
  limits = {},
  onEvent = () => {},
}) {
  assert.equal(typeof finish, 'function', 'Pre-crash trace exporter required')
  const b = bounds(limits)
  const call = (fn, label) => bounded(fn, b.timeoutMs, label)
  const profile = await call(() => profiles.create(), 'Profile creation')
  const profileSha256 = createHash('sha256').update(profile).digest('hex')
  let context,
    identity,
    firstIdentity,
    secondIdentity,
    firstTermination,
    secondTermination,
    crashReceipt,
    crashAttempt
  let dispatched = false,
    uncertain = false,
    closeAttempted = false,
    phase = 1,
    traceAttempted = false
  const errors = []
  const emit = (stage) => {
    const metadata = (p) =>
      Object.freeze({ pid: p.pid, starttime: p.starttime, pgrp: p.pgrp, session: p.session })
    const snapshot = identity
      ? Object.freeze({ ...metadata(identity), known: Object.freeze(identity.known.map(metadata)) })
      : undefined
    const result = onEvent(
      Object.freeze({
        stage,
        phase,
        profileSha256,
        identity: snapshot,
        crashAttempt: crashAttempt ? Object.freeze({ ...crashAttempt }) : undefined,
      }),
    )
    assert.ok(!result || typeof result.then !== 'function', 'onEvent must be synchronous')
  }
  const inspect = () =>
    call(() => identify(context, profile, { inventory, timeoutMs: b.timeoutMs }), 'Identity')
  const exportTrace = async () => {
    traceAttempted = true
    await call(() => finish(context, phase), 'Trace export')
  }
  const absent = (id) => waitCrashAbsent(id, { inventory, ...b })
  const observe = async (browser, pages, id) => {
    for (let attempt = 0; attempt < b.attempts; attempt++) {
      if (!browser.isConnected() && pages.every((p) => p.isClosed())) {
        await absent(id)
        return termination()
      }
      if (attempt + 1 < b.attempts) await delay(b.pollMs)
    }
    throw Error('Browser disconnect or closed pages not observed')
  }
  const close = async () => {
    if (!context || closeAttempted || dispatched) return
    closeAttempted = true
    const pages = context.pages(),
      browser = context.browser()
    let traceError
    if (!traceAttempted)
      try {
        await exportTrace()
      } catch (error) {
        traceError = error
      }
    try {
      await call(() => context.close(), 'Graceful close')
      assert.ok(identity, 'Unknown process identity; retain profile')
      const receipt = await observe(browser, pages, identity)
      context = undefined
      uncertain = false
      if (traceError) throw traceError
      return receipt
    } catch (error) {
      if (traceError && error !== traceError)
        throw new AggregateError([traceError, error], 'Trace and close failed')
      throw error
    }
  }
  try {
    await profiles.verify(profile)
    uncertain = true
    context = await call(
      () => launch(profile, { offline: false, serviceWorkers: 'allow' }),
      'First launch',
    )
    identity = firstIdentity = await inspect()
    emit('identified')
    const before = await first(context, identity)
    await exportTrace()
    await profiles.verify(profile)
    const fresh = await inspect()
    sameIdentity({ ...identity, known: undefined }, { ...fresh, known: undefined })
    identity = firstIdentity = { ...fresh, known: mergeKnown(identity.known, fresh.known) }
    const browser = context.browser(),
      pages = context.pages()
    assert.ok(
      browser?.isConnected() && pages.length > 0 && pages.every((p) => !p.isClosed()),
      'Owned browser/pages not live before crash',
    )
    const cdp = await call(() => browser.newBrowserCDPSession(), 'Crash session')
    // Revalidate after session creation, immediately before the sole crash dispatch.
    await profiles.verify(profile)
    const finalIdentity = await inspect()
    sameIdentity({ ...identity, known: undefined }, { ...finalIdentity, known: undefined })
    identity = firstIdentity = {
      ...identity,
      known: mergeKnown(identity.known, finalIdentity.known),
    }
    emit('dispatch-begin')
    dispatched = true
    crashAttempt = {
      method: 'Browser.crash',
      dispatched: true,
      commandOutcome: 'pending',
      terminationVerified: false,
    }
    let commandOutcome = 'resolved'
    try {
      await call(() => cdp.send('Browser.crash'), 'Browser.crash')
    } catch (error) {
      if (!transportClosed(error)) {
        crashAttempt.commandOutcome = 'failed'
        throw error
      }
      commandOutcome = 'transport-closed'
    }
    crashAttempt.commandOutcome = commandOutcome
    emit('command-outcome')
    firstTermination = await observe(browser, pages, identity)
    crashAttempt.terminationVerified = true
    emit('absence')
    crashReceipt = { method: 'Browser.crash', commandOutcome, ...firstTermination }
    context = undefined
    uncertain = false
    phase = 2
    dispatched = false
    traceAttempted = false
    await profiles.verify(profile)
    uncertain = true
    await absent(firstIdentity)
    context = await call(
      () => launch(profile, { offline: true, serviceWorkers: 'allow' }),
      'Recovery launch',
    )
    identity = undefined
    identity = secondIdentity = await inspect()
    emit('identified')
    assert.notEqual(identity.pid, firstIdentity.pid, 'Recovery requires fresh PID')
    assert.ok(
      context.pages().length > 0 && context.pages().every((p) => p.url() === 'about:blank'),
      'Recovery must start with blank pages',
    )
    await second(context, before, {
      first: firstIdentity,
      second: secondIdentity,
      profileSha256,
      firstTermination,
      crashReceipt,
    })
    // Include newly created recovery workers in the graceful-close inventory.
    const finalRecovery = await inspect()
    sameIdentity({ ...identity, known: undefined }, { ...finalRecovery, known: undefined })
    identity = { ...identity, known: mergeKnown(identity.known, finalRecovery.known) }
    secondTermination = await close()
    emit('absence')
  } catch (error) {
    errors.push(error)
  }
  try {
    await close()
  } catch (error) {
    errors.push(error)
  }
  if (!uncertain && !context)
    try {
      await profiles.verify(profile)
      if (firstIdentity) await absent(firstIdentity)
      if (secondIdentity) await absent(secondIdentity)
      await profiles.remove(profile)
    } catch (error) {
      errors.push(error)
    }
  if (errors.length) {
    try {
      emit('failure')
    } catch (error) {
      errors.push(error)
    }
    const error =
      errors.length === 1
        ? errors[0]
        : new AggregateError(errors, 'Crash recovery failed with cleanup errors')
    if (crashAttempt) error.crashAttempt = crashAttempt
    throw error
  }
  return {
    first: firstIdentity,
    second: secondIdentity,
    profileSha256,
    firstTermination,
    crashReceipt,
    secondTermination,
  }
}
