import assert from 'node:assert/strict'
import { mkdtemp, readFile, writeFile, realpath, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { randomUUID, createHash } from 'node:crypto'
import { setTimeout as delay } from 'node:timers/promises'

export function parseStat(text, pid) {
  assert.ok(Number.isSafeInteger(pid) && pid > 0, 'Invalid PID')
  const match = /^(\d+) \(.*\) ([A-Za-z]) (.*)$/s.exec(text.trim())
  assert.ok(match && Number(match[1]) === pid, 'Malformed proc stat PID')
  const starttime = match[3].split(/\s+/)[18]
  assert.match(starttime ?? '', /^\d+$/, 'Malformed proc starttime')
  return { pid, starttime }
}
export function browserPid(result) {
  assert.ok(Array.isArray(result?.processInfo), 'Missing process info')
  const browsers = result.processInfo.filter((p) => p.type === 'browser')
  assert.equal(browsers.length, 1, 'Expected exactly one browser process')
  const pid = browsers[0].id
  assert.ok(Number.isSafeInteger(pid) && pid > 0, 'Invalid browser PID')
  return pid
}
export async function identify(
  context,
  profile,
  { read = readFile, platform = process.platform } = {},
) {
  assert.equal(platform, 'linux', 'Process qualification requires Linux procfs')
  const browser = context.browser()
  assert.ok(browser?.isConnected(), 'Persistent context has no connected browser')
  const session = await browser.newBrowserCDPSession()
  try {
    const pid = browserPid(await session.send('SystemInfo.getProcessInfo'))
    const identity = parseStat(await read(`/proc/${pid}/stat`, 'utf8'), pid)
    const args = (await read(`/proc/${pid}/cmdline`, 'utf8')).split('\0')
    assert.ok(args.includes(`--user-data-dir=${profile}`), 'Browser is not using owned profile')
    return identity
  } finally {
    await session.detach()
  }
}
export async function waitAbsent(
  pid,
  { read = (path) => readFile(path, 'utf8'), delay: sleep = delay, attempts = 100 } = {},
) {
  assert.ok(Number.isSafeInteger(pid) && pid > 0, 'Invalid PID')
  assert.ok(Number.isInteger(attempts) && attempts > 0 && attempts <= 100, 'Invalid poll bound')
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      await read(`/proc/${pid}/stat`)
    } catch (error) {
      if (error.code === 'ENOENT') return
      throw error
    }
    if (attempt + 1 < attempts) await sleep(50)
  }
  throw Error(`Owned browser PID ${pid} still exists after bounded wait`)
}
function ownedProfiles() {
  let path
  const token = randomUUID()
  return {
    async create() {
      path = await realpath(await mkdtemp(join(tmpdir(), 'ocwp-capture-restart-')))
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
/** Test-owned graceful process restart only. Uncertain launch/close retains the synthetic profile. */
export async function runRestart({
  launch,
  first,
  second,
  profiles = ownedProfiles(),
  identify: inspect = identify,
  absent = waitAbsent,
  finish = async () => {},
}) {
  const profile = await profiles.create()
  const profileSha256 = createHash('sha256').update(profile).digest('hex')
  let firstTermination
  let secondTermination
  let secondIdentity
  let context
  let identity
  let uncertain = false
  let before
  let firstIdentity
  let closeAttempted = false
  const errors = []
  const close = async (phase) => {
    if (!context || closeAttempted) return
    closeAttempted = true
    const pages = context.pages()
    const browser = context.browser()
    let traceError
    try {
      await finish(context, phase)
    } catch (error) {
      traceError = error
    }
    try {
      await context.close()
      assert.ok(
        pages.every((page) => page.isClosed()),
        'Owned pages did not close',
      )
      assert.equal(browser?.isConnected(), false, 'Owned browser did not disconnect')
      assert.ok(identity, 'Cannot prove unknown process absence')
      await absent(identity.pid)
      context = undefined
      identity = undefined
      uncertain = false
    } catch (error) {
      if (traceError)
        throw new AggregateError([traceError, error], 'Trace and process cleanup failed')
      throw error
    }
    if (traceError) throw traceError
    return { pagesClosed: true, browserDisconnected: true, procAbsent: true }
  }
  let phase = 1
  try {
    await profiles.verify(profile)
    uncertain = true
    context = await launch(profile, { offline: false, serviceWorkers: 'allow' })
    identity = await inspect(context, profile)
    firstIdentity = identity
    before = await first(context, identity)
    firstTermination = await close(1)
    phase = 2
    closeAttempted = false
    await profiles.verify(profile)
    uncertain = true
    context = await launch(profile, { offline: true, serviceWorkers: 'allow' })
    identity = await inspect(context, profile)
    secondIdentity = identity
    assert.notEqual(identity.pid, firstIdentity.pid, 'Restart requires a fresh PID')
    assert.ok(
      context.pages().length > 0 && context.pages().every((page) => page.url() === 'about:blank'),
      'Restart must begin with blank pages',
    )
    await second(context, before, {
      first: firstIdentity,
      second: identity,
      profileSha256,
      firstTermination,
    })
    secondTermination = await close(2)
  } catch (error) {
    errors.push(error)
  }
  try {
    await close(phase)
  } catch (error) {
    errors.push(error)
  }
  if (!uncertain && !context) {
    try {
      await profiles.verify(profile)
      await profiles.remove(profile)
    } catch (error) {
      errors.push(error)
    }
  }
  if (errors.length === 1) throw errors[0]
  if (errors.length > 1) throw new AggregateError(errors, 'Restart failed with cleanup errors')
  return {
    first: firstIdentity,
    second: secondIdentity,
    profileSha256,
    firstTermination,
    secondTermination,
  }
}
