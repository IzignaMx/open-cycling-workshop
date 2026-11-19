import type { Page } from '@playwright/test'
import type {
  CaptureCheckpoint,
  CaptureDraftContent,
} from '../../src/access-kernel/capture-checkpoint-types.js'
import { DATABASE } from './authenticated-workshop.js'

/** Bounded readonly observation of this disposable origin, never create or mutate a DB. */
export async function captureSnapshot(page: Page) {
  return page.evaluate(async (name) => {
    const opened = indexedDB.open(name)
    opened.onupgradeneeded = () => opened.transaction!.abort()
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      opened.onsuccess = () => resolve(opened.result)
      opened.onerror = () => reject(opened.error)
    })
    const read = <T>(request: IDBRequest<T>) =>
      new Promise<T>((resolve, reject) => {
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
    try {
      const tx = db.transaction(['captureCheckpoints', 'captureDraftContents'], 'readonly')
      const [checkpoints, contents] = await Promise.all([
        read(tx.objectStore('captureCheckpoints').getAll(undefined, 3)) as Promise<
          CaptureCheckpoint[]
        >,
        read(tx.objectStore('captureDraftContents').getAll(undefined, 5)) as Promise<
          CaptureDraftContent[]
        >,
      ])
      if (checkpoints.length > 2 || contents.length > 4)
        throw new Error('Unexpected fixture capture scope')
      // Loading legitimately advances observedAt. Preserve all other metadata
      // and payload bytes, not the wall-clock observation timestamp.
      return {
        checkpoints: checkpoints.map(({ observedAt, ...stable }) => {
          void observedAt
          return stable
        }),
        contents,
      }
    } finally {
      db.close()
    }
  }, DATABASE)
}
