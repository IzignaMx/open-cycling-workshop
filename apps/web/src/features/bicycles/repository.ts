import type { OcwpDatabase } from '../../local/db.js'
import type { LocalBicycle } from '../../local/bicycle-types.js'
import { newUuidV7 } from '../../shared/ids.js'
import { buildLocalBicycleCreate, type CreateBicycleInput } from './local-bicycle.js'

export type { CreateBicycleInput } from './local-bicycle.js'

export class BicycleLocalRepository {
  constructor(private readonly database: OcwpDatabase) {}

  async create(input: CreateBicycleInput): Promise<LocalBicycle> {
    const { bicycle, mutation } = buildLocalBicycleCreate(input, {
      now: () => new Date().toISOString(),
      newId: newUuidV7,
    })
    await this.database.transaction(
      'rw',
      this.database.bicycles,
      this.database.mutationQueue,
      async () => {
        await this.database.bicycles.put(bicycle)
        await this.database.mutationQueue.put(mutation)
      },
    )
    return bicycle
  }
}
