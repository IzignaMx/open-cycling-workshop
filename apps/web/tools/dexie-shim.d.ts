declare module 'dexie' {
  export interface Collection<T> {
    limit(value: number): Collection<T>
    toArray(): Promise<T[]>
  }

  export interface WhereClause<T> {
    equals(value: unknown): Collection<T>
  }

  export interface Table<T, K = unknown> {
    get(key: K): Promise<T | undefined>
    put(value: T): Promise<K>
    bulkPut(values: T[]): Promise<K>
    bulkDelete(keys: K[]): Promise<void>
    toArray(): Promise<T[]>
    where(index: string): WhereClause<T>
    orderBy(index: string): Collection<T>
  }

  export default class Dexie {
    constructor(name: string)
    version(version: number): { stores(schema: Record<string, string>): void }
    transaction<T>(mode: 'rw' | 'r', ...args: unknown[]): Promise<T>
  }
}
