import type { SyncStore, SyncTransport } from './types.js'

export interface SyncCoordinatorOptions {
  store: SyncStore
  transport: SyncTransport
  locationId: string | null
  batchSize?: number
}

export interface SyncRunResult {
  status: 'offline' | 'synced'
  pushed: number
  conflicts: number
  pulled: number
  cursor: number
}

export class SyncCoordinator {
  readonly #store: SyncStore
  readonly #transport: SyncTransport
  readonly #locationId: string | null
  readonly #batchSize: number

  constructor(options: SyncCoordinatorOptions) {
    this.#store = options.store
    this.#transport = options.transport
    this.#locationId = options.locationId
    this.#batchSize = options.batchSize ?? 100
  }

  async runOnce({ online }: { online: boolean }): Promise<SyncRunResult> {
    if (!online) {
      return {
        status: 'offline',
        pushed: 0,
        conflicts: 0,
        pulled: 0,
        cursor: await this.#store.getCursor(),
      }
    }

    const pending = await this.#store.listPending(this.#batchSize)
    let conflictCount = 0
    if (pending.length > 0) {
      const pushed = await this.#transport.push(pending)
      const pendingIds = new Set(pending.map((mutation) => mutation.mutation_id))
      const matchingResults = pushed.results.filter((result) => pendingIds.has(result.mutation_id))
      const acknowledged = matchingResults
        .filter((result) => result.status === 'applied')
        .map((result) => result.mutation_id)
      if (acknowledged.length > 0) {
        await this.#store.markAcknowledged(acknowledged)
      }
      const conflicts = matchingResults.filter((result) => result.status === 'conflict')
      conflictCount = conflicts.length
      if (conflictCount > 0) {
        await this.#store.recordConflicts(conflicts)
      }
    }

    const cursor = await this.#store.getCursor()
    const page = await this.#transport.pull(cursor, this.#locationId)
    if (page.items.length > 0 || page.next_cursor !== cursor) {
      await this.#store.mergeAndAdvance(page.items, page.next_cursor)
    }

    return {
      status: 'synced',
      pushed: pending.length,
      conflicts: conflictCount,
      pulled: page.items.length,
      cursor: page.next_cursor,
    }
  }
}
