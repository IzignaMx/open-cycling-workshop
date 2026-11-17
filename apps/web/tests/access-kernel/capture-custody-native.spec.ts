import { test, expect, type Page, type APIRequestContext, type TestInfo } from '@playwright/test'
import {
  expectedProvenance,
  verifyArtifactProvenance,
} from '../../tools/capture-custody-browser/prepare.mjs'
import type {
  CaptureCheckpoint,
  CaptureDraftContent,
} from '../../src/access-kernel/capture-checkpoint-types.js'
import type { ContextTicket } from '../../src/access-kernel/types.js'
import type { CaptureVisitScope } from '../../src/runtime/capture-visit.js'

type Owner = Record<string, string>
type Bundle = {
  format: 1
  kind: 'inert-capture-custody'
  owner: Owner
  capturedAt: number
  checkpoint: CaptureCheckpoint
  contents: CaptureDraftContent[]
}
type Descriptor = {
  name: string
  now: number
  ticket: ContextTicket
  scope: CaptureVisitScope
  checkpointId: string
  generation: string
  owner: Owner
}
type Result = {
  kind: string
  reason?: string
  bundle?: Bundle
  observation?: string
  operationalUse?: string
}
interface Harness {
  seedSource(name: string, now: number): Promise<Descriptor>
  sourceBytes(descriptor: Descriptor): Promise<string>
  snapshot(descriptor: Descriptor): Promise<Result>
  editSource(descriptor: Descriptor, text: string): Promise<Result>
  run(descriptor: Descriptor): Promise<Result>
  initializeTarget(name: string): Promise<void>
  stage(
    name: string,
    transferId: string,
    bundle: Bundle,
    owner: Owner,
    now: number,
  ): Promise<Result>
  read(name: string, transferId: string, owner: Owner, now: number): Promise<Result>
  targetBytes(name: string): Promise<string>
  targetStores(name: string): Promise<string[]>
  corrupt(name: string, transferId: string): Promise<void>
  outerAbort(
    name: string,
    transferId: string,
    bundle: Bundle,
    owner: Owner,
    now: number,
    mode: 'stage' | 'read',
  ): Promise<{ result: Result; aborted: boolean; rows: number }>
  cleanup(descriptor: Descriptor | null, name: string | null): Promise<void>
}
declare global {
  interface Window {
    custodyHarness: Harness
  }
}
const A = 'http://127.0.0.1:5182',
  B = 'http://127.0.0.1:5183'
async function open(page: Page, origin: string) {
  await page.goto(origin)
  await page.waitForFunction(() => !!window.custodyHarness)
  expect(await page.evaluate(() => location.origin)).toBe(origin)
  expect(await page.evaluate(() => navigator.serviceWorker.controller)).toBeNull()
}
async function provenance(request: APIRequestContext, info: TestInfo) {
  const expected = await expectedProvenance()
  for (const origin of [A, B]) {
    const response = await request.get(`${origin}/provenance.json`)
    expect(response.ok()).toBe(true)
    const actual = await response.json()
    verifyArtifactProvenance(actual, expected)
    for (const [path, metadata] of Object.entries(expected.assets)) {
      const response = await request.get(`${origin}/${path}`)
      expect(response.ok()).toBe(true)
      const bytes = new Uint8Array(await response.body())
      expect(bytes.byteLength).toBe(metadata.bytes)
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (b) =>
        b.toString(16).padStart(2, '0'),
      ).join('')
      expect(hash).toBe(metadata.sha256)
    }
    await info.attach(`custody-harness-provenance-${new URL(origin).port}`, {
      body: JSON.stringify(actual),
      contentType: 'application/json',
    })
  }
}
const sourceBytes = (page: Page, descriptor: Descriptor) =>
  page.evaluate((descriptor) => window.custodyHarness.sourceBytes(descriptor), descriptor)
const targetBytes = (page: Page, name: string) =>
  page.evaluate((name) => window.custodyHarness.targetBytes(name), name)
async function bundleAt(page: Page, descriptor: Descriptor) {
  const result = await page.evaluate(
    (descriptor) => window.custodyHarness.snapshot(descriptor),
    descriptor,
  )
  expect(result.kind).toBe('snapshot')
  if (!result.bundle) throw Error('Expected synthetic source bundle')
  return result.bundle
}
async function assertInertTarget(page: Page, name: string, source: string) {
  expect(await page.evaluate((name) => window.custodyHarness.targetStores(name), name)).toEqual([
    'custody',
  ])
  expect(
    await page.evaluate(
      async (source) => (await indexedDB.databases()).some((db) => db.name === source),
      source,
    ),
  ).toBe(false)
}

test('native cross-origin custody retains exact v1 package after another-tab drift and B reload', async ({
  context,
  request,
  browser,
}, info) => {
  await provenance(request, info)
  const a = await context.newPage(),
    b = await context.newPage(),
    editor = await context.newPage()
  await open(a, A)
  await open(b, B)
  await open(editor, A)
  expect(a.context()).toBe(b.context())
  expect(editor.context()).toBe(a.context())
  const sourceName = 'ocwp-synthetic-custody-source-transfer',
    targetName = 'ocwp-synthetic-custody-target-transfer'
  const descriptor = await a.evaluate(
    ({ name, now }) => window.custodyHarness.seedSource(name, now),
    { name: sourceName, now: Date.now() },
  )
  await b.evaluate((name) => window.custodyHarness.initializeTarget(name), targetName)
  const original = await bundleAt(a, descriptor),
    before = await sourceBytes(a, descriptor)
  const originalTTL = original.contents.map((row) => ({
    channel: row.channel,
    firstPersistedAt: row.firstPersistedAt,
    expiresAt: row.expiresAt,
  }))
  let editDuringStage = false
  const transfers: { result: Result; bundle: Bundle }[] = []
  await a.exposeFunction('custodyTransport', async (bundle: Bundle) => {
    // Explicit test-driver transport: only detached bundle crosses the origins.
    const result = await b.evaluate(
      ({ name, bundle, owner, now }) =>
        window.custodyHarness.stage(name, 'transfer-1', bundle, owner, now),
      { name: targetName, bundle, owner: descriptor.owner, now: descriptor.now },
    )
    transfers.push({ result, bundle })
    if (editDuringStage) {
      const edit = await editor.evaluate(
        (descriptor) =>
          window.custodyHarness.editSource(descriptor, 'Synthetic concurrent source edit'),
        descriptor,
      )
      expect(edit.kind).toBe('ack')
    }
    return result
  })
  try {
    expect(
      await a.evaluate((descriptor) => window.custodyHarness.run(descriptor), descriptor),
    ).toEqual({
      kind: 'custody_retained',
      observation: 'source_unchanged_at_check',
      operationalUse: 'forbidden',
    })
    expect(await sourceBytes(a, descriptor)).toBe(before)
    expect(transfers[0]?.result).toEqual({ kind: 'staged' })
    const retainedBytes = await targetBytes(b, targetName)
    editDuringStage = true
    expect(
      await a.evaluate((descriptor) => window.custodyHarness.run(descriptor), descriptor),
    ).toEqual({
      kind: 'custody_retained',
      observation: 'source_changed',
      operationalUse: 'forbidden',
    })
    expect(transfers[1]?.result).toEqual({ kind: 'already_staged' })
    expect(transfers.map((transfer) => transfer.bundle)).toEqual([original, original])
    const changedSource = await bundleAt(a, descriptor),
      afterEdit = await sourceBytes(a, descriptor)
    expect(afterEdit).not.toBe(before)
    expect(await sourceBytes(editor, descriptor)).toBe(afterEdit)
    expect(changedSource.contents.find((row) => row.channel === 'customer')?.draft).toMatchObject({
      displayName: 'Synthetic concurrent source edit',
    })
    expect(
      changedSource.contents.map((row) => ({
        channel: row.channel,
        firstPersistedAt: row.firstPersistedAt,
        expiresAt: row.expiresAt,
      })),
    ).toEqual(originalTTL)
    expect(await targetBytes(b, targetName)).toBe(retainedBytes)
    await assertInertTarget(b, targetName, sourceName)
    // This reload resets all harness maps; the target is opened existing-only, never reseeded.
    await b.reload()
    await b.waitForFunction(() => !!window.custodyHarness)
    const read = await b.evaluate(
      ({ name, owner, now }) => window.custodyHarness.read(name, 'transfer-1', owner, now),
      { name: targetName, owner: descriptor.owner, now: descriptor.now + 1000 },
    )
    expect(read).toEqual({ kind: 'custody', bundle: original })
    expect(JSON.stringify(read.bundle)).toBe(JSON.stringify(original))
    expect(await targetBytes(b, targetName)).toBe(retainedBytes)
    await assertInertTarget(b, targetName, sourceName)
    expect(await sourceBytes(a, descriptor)).toBe(afterEdit)
    await info.attach('native-custody-drift-reload', {
      body: JSON.stringify({
        browser: browser.version(),
        origins: [A, B],
        original,
        originalTTL,
        transfers,
        changedSource,
        retainedBytes,
        read,
        scope:
          'Synthetic inert package transport; not exclusive handover, operational restore, actual App/SW, offline execution or process restart',
      }),
      contentType: 'application/json',
    })
  } finally {
    await editor.close()
    await a.evaluate((descriptor) => window.custodyHarness.cleanup(descriptor, null), descriptor)
    await b.evaluate((name) => window.custodyHarness.cleanup(null, name), targetName)
  }
})

test('native custody rejects owner, collision, corruption and nested outer-abort access', async ({
  context,
  request,
  browser,
}, info) => {
  await provenance(request, info)
  const a = await context.newPage(),
    b = await context.newPage()
  await open(a, A)
  await open(b, B)
  expect(a.context()).toBe(b.context())
  const descriptor = await a.evaluate(
    ({ name, now }) => window.custodyHarness.seedSource(name, now),
    { name: 'ocwp-synthetic-custody-source-guards', now: Date.now() },
  )
  const name = 'ocwp-synthetic-custody-target-guards'
  await b.evaluate((name) => window.custodyHarness.initializeTarget(name), name)
  const bundle = await bundleAt(a, descriptor),
    before = await sourceBytes(a, descriptor)
  const owner = descriptor.owner,
    now = descriptor.now
  try {
    const wrongSource = await a.evaluate(
      (descriptor) =>
        window.custodyHarness.snapshot({
          ...descriptor,
          ticket: { ...descriptor.ticket, tabAttemptId: 'synthetic-other-tab-owner' },
        }),
      descriptor,
    )
    expect(wrongSource).toEqual({ kind: 'refused', reason: 'authority' })
    const wrongOwner = { ...owner, userId: 'synthetic-other-owner' }
    const ownerStage = await b.evaluate(
      ({ name, bundle, owner, now }) =>
        window.custodyHarness.stage(name, 'wrong-owner', bundle, owner, now),
      { name, bundle, owner: wrongOwner, now },
    )
    expect(ownerStage).toEqual({ kind: 'refused', reason: 'invalid' })
    expect(await targetBytes(b, name)).toBe('[]')
    const outerResults = []
    for (const mode of ['stage', 'read'] as const) {
      const result = await b.evaluate(
        ({ name, bundle, owner, now, mode }) =>
          window.custodyHarness.outerAbort(name, `outer-${mode}`, bundle, owner, now, mode),
        { name, bundle, owner, now, mode },
      )
      expect(result).toEqual({
        result: { kind: 'refused', reason: 'nested_transaction' },
        aborted: true,
        rows: 0,
      })
      expect(await targetBytes(b, name)).toBe('[]')
      outerResults.push({ mode, ...result })
    }
    expect(
      await b.evaluate(
        ({ name, bundle, owner, now }) =>
          window.custodyHarness.stage(name, 'guarded', bundle, owner, now),
        { name, bundle, owner, now },
      ),
    ).toEqual({ kind: 'staged' })
    const intactBytes = await targetBytes(b, name)
    const collision = structuredClone(bundle)
    const customer = collision.contents.find((row) => row.channel === 'customer')
    if (!customer || customer.channel !== 'customer') throw Error('Missing customer')
    customer.draft.displayName = 'Different valid custody bytes'
    expect(
      await b.evaluate(
        ({ name, bundle, owner, now }) =>
          window.custodyHarness.stage(name, 'guarded', bundle, owner, now),
        { name, bundle: collision, owner, now },
      ),
    ).toEqual({ kind: 'refused', reason: 'conflict' })
    const ownerRead = await b.evaluate(
      ({ name, owner, now }) => window.custodyHarness.read(name, 'guarded', owner, now),
      { name, owner: wrongOwner, now },
    )
    expect(ownerRead).toEqual({ kind: 'refused', reason: 'unavailable' })
    expect(await targetBytes(b, name)).toBe(intactBytes)
    await b.evaluate((name) => window.custodyHarness.corrupt(name, 'guarded'), name)
    const corruptedBytes = await targetBytes(b, name)
    const corruptRead = await b.evaluate(
      ({ name, owner, now }) => window.custodyHarness.read(name, 'guarded', owner, now),
      { name, owner, now },
    )
    expect(corruptRead).toEqual({ kind: 'refused', reason: 'unavailable' })
    expect(await targetBytes(b, name)).toBe(corruptedBytes)
    expect(await sourceBytes(a, descriptor)).toBe(before)
    await assertInertTarget(b, name, descriptor.name)
    await info.attach('native-custody-guard-refusals', {
      body: JSON.stringify({
        browser: browser.version(),
        wrongSource,
        ownerStage,
        ownerRead,
        outerResults,
        corruptRead,
        intactBytes,
        corruptedBytes,
        operationalStores: [],
        scope: 'Native test-only custody guards; no actual application or operational import',
      }),
      contentType: 'application/json',
    })
  } finally {
    await a.evaluate((descriptor) => window.custodyHarness.cleanup(descriptor, null), descriptor)
    await b.evaluate((name) => window.custodyHarness.cleanup(null, name), name)
  }
})
