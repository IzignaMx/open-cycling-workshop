import type { OcwpDatabase } from '../../local/db.js'
import type { LocalCustomer } from '../../local/types.js'
import { newUuidV7 } from '../../shared/ids.js'
import { buildLocalCustomerCreate, type CreateCustomerInput } from './local-customer.js'

export type { CreateCustomerInput } from './local-customer.js'

export class CustomerLocalRepository {
  constructor(private readonly database: OcwpDatabase) {}

  async create(input: CreateCustomerInput): Promise<LocalCustomer> {
    const { customer, mutation } = buildLocalCustomerCreate(input, {
      now: () => new Date().toISOString(),
      newId: newUuidV7,
    })

    await this.database.transaction(
      'rw',
      this.database.customers,
      this.database.mutationQueue,
      async () => {
        await this.database.customers.put(customer)
        await this.database.mutationQueue.put(mutation)
      },
    )
    return customer
  }
}
