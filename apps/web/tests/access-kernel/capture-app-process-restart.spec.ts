import { test, expect, chromium } from '@playwright/test'
import { runRestart } from '../../tools/capture-app/process-restart.mjs'
import { witnessId } from '../../tools/capture-app/fixture.mjs'
import { hash } from '../../tools/capture-app/provenance.mjs'
import {
  database,
  verify,
  fixture,
  snapshot,
  legacyNotice,
  installStartupBarrier,
} from './capture-app-support.js'

// Persistent contexts also receive the runner's tracing hooks. This suite owns
// both process traces explicitly; reload cases retain the global trace setting.
test.use({ trace: 'off' })

const env = (globalThis as unknown as { process: { env: Record<string, string | undefined> } })
  .process.env
for (const [kind, port] of [
  ['old', 5180],
  ['current', 5181],
] as const) {
  test(`actual ${kind} App/SW offline graceful process restart ${kind === 'old' ? 'deletes' : 'preserves'} future bytes`, async ({
    request,
  }, info) => {
    const origin = `http://127.0.0.1:${port}`
    const evidence = await verify(origin, kind, request, info)
    const failures: { url: string; error: string | null }[] = []
    let browserVersion: string | undefined
    try {
      const lifecycle = await runRestart({
        launch: async (profile, options) => {
          const context = await chromium.launchPersistentContext(profile, {
            ...options,
            ...(env.OCWP_CHROMIUM_EXECUTABLE
              ? { executablePath: env.OCWP_CHROMIUM_EXECUTABLE }
              : {}),
          })
          // Runner tracing is disabled above; retain a manual trace for each process.
          try {
            await context.tracing.start({ screenshots: true, snapshots: true, sources: true })
          } catch (error) {
            await context.close()
            throw error
          }
          return context
        },
        finish: async (context, phase) => {
          const path = info.outputPath(`process-phase-${phase}.zip`)
          await context.tracing.stop({ path })
          await info.attach(`process-phase-${phase}-trace`, {
            path,
            contentType: 'application/zip',
          })
        },
        first: async (context, identity) => {
          browserVersion = context.browser()!.version()
          const page = context.pages()[0]!
          await installStartupBarrier(page, origin)
          await page.goto(origin, { waitUntil: 'networkidle' })
          // start() awaits cleanup before inspecting legacy work and publishing this notice.
          await expect(legacyNotice(page)).toBeVisible()
          await expect(page.locator('[data-runtime-state="LOCKED"]')).toBeVisible()
          await page.waitForFunction(
            async (name) => (await indexedDB.databases()).some((db) => db.name === name),
            database,
          )
          await page.evaluate(async () => {
            await navigator.serviceWorker.ready
          })
          await page.waitForFunction(
            () => navigator.serviceWorker.controller?.state === 'activated',
          )
          const controller = await page.evaluate(
            () => navigator.serviceWorker.controller?.scriptURL,
          )
          expect(controller).toBe(`${origin}/sw.js`)
          expect(await snapshot(page)).toEqual({ contents: [], checkpoints: [], journal: [] })
          const seeded = fixture(Date.now() - 1000)
          await page.evaluate(
            async ({ name, seeded }) => {
              const db = await new Promise<IDBDatabase>((resolve, reject) => {
                const req = indexedDB.open(name)
                req.onupgradeneeded = () => {
                  req.transaction?.abort()
                  reject(Error('Missing App database'))
                }
                req.onsuccess = () => resolve(req.result)
                req.onerror = () => reject(req.error)
              })
              try {
                const tx = db.transaction(
                  ['captureDraftContents', 'captureCheckpoints', 'operationJournal'],
                  'readwrite',
                )
                const done = new Promise<void>((resolve, reject) => {
                  tx.oncomplete = () => resolve()
                  tx.onerror = () => reject(tx.error)
                  tx.onabort = () => reject(tx.error)
                })
                tx.objectStore('captureCheckpoints').add(seeded.checkpoint)
                for (const row of [seeded.customer, seeded.future, seeded.witness])
                  tx.objectStore('captureDraftContents').add(row)
                tx.objectStore('operationJournal').add(seeded.journal)
                await done
              } finally {
                db.close()
              }
            },
            { name: database, seeded },
          )
          const before = await snapshot(page)
          expect(before.contents).toEqual([seeded.customer, seeded.future, seeded.witness])
          expect(before.checkpoints).toEqual([seeded.checkpoint])
          expect(before.journal).toEqual([seeded.journal])
          await info.attach('before-native-IDB', {
            body: JSON.stringify(before),
            contentType: 'application/json',
          })

          // Persist a blank last tab so restoring the owned profile cannot run App before offline admission.
          await page.goto('about:blank')
          return { seeded, before, controller, identity }
        },
        second: async (context, original, identities) => {
          const { seeded, before, controller } = original
          const page = context.pages()[0]!
          page.on('requestfailed', (r) =>
            failures.push({ url: r.url(), error: r.failure()?.errorText ?? null }),
          )
          expect(await page.evaluate(() => navigator.onLine)).toBe(false)
          const response = await page.goto(origin, { waitUntil: 'networkidle' })
          expect(response?.fromServiceWorker()).toBe(true)
          expect(response?.ok()).toBe(true)
          expect(hash(await response!.body())).toBe(evidence.assets['index.html']!.sha256)
          await expect(legacyNotice(page)).toBeVisible()
          expect(await page.evaluate(() => navigator.onLine)).toBe(false)
          expect(await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL)).toBe(
            controller,
          )
          const probe = `/uncached-restart-probe-${Date.now()}`
          expect(
            await page.evaluate(async (path) => {
              try {
                await fetch(path, { cache: 'no-store' })
                return false
              } catch {
                return true
              }
            }, probe),
          ).toBe(true)
          await expect
            .poll(() => failures.some((failure) => failure.url === origin + probe))
            .toBe(true)
          await expect(page.locator('[data-runtime-state="LOCKED"]')).toBeVisible()
          await expect
            .poll(async () =>
              (await snapshot(page)).contents.some((r) => r.checkpointId === witnessId),
            )
            .toBe(false)
          const after = await snapshot(page)
          expect(after.journal).toEqual(before.journal)
          expect(JSON.stringify(after.journal)).toBe(JSON.stringify(before.journal))
          expect(after.contents.find((r) => r.channel === 'customer')).toEqual(seeded.customer)
          if (kind === 'old') {
            expect(after.contents).toEqual([seeded.customer])
            expect(after.checkpoints[0]).toMatchObject({
              ...seeded.checkpoint,
              observedAt: expect.any(Number),
              order: {
                revision: 2,
                state: 'UNAVAILABLE',
                attemptId: null,
                contentStartedAt: null,
                contentExpiresAt: null,
              },
            })
          } else {
            expect(after.contents).toEqual([seeded.customer, seeded.future])
            expect(JSON.stringify(after.contents[1])).toBe(JSON.stringify(seeded.future))
            expect(after.checkpoints).toEqual(before.checkpoints)
          }

          await info.attach('process-restart-native-evidence', {
            body: JSON.stringify({
              before,
              after,
              identities,
              controller,
              failures,
              browser: context.browser()!.version(),
              navigationFromServiceWorker: response?.fromServiceWorker(),
              navigationSha256: hash(await response!.body()),
              lifecycle:
                'graceful owned Chromium process restart, same synthetic profile, offline from second launch',
              scope:
                'independent old/current artifacts; not crash, handover, update or G1–G6 closure',
            }),
            contentType: 'application/json',
          })
        },
      })
      await info.attach('confirmed-process-lifecycle', {
        body: JSON.stringify(lifecycle),
        contentType: 'application/json',
      })
    } finally {
      await info.attach('restart-browser-and-network-diagnostics', {
        body: JSON.stringify({ browser: browserVersion, failures }),
        contentType: 'application/json',
      })
    }
  })
}
