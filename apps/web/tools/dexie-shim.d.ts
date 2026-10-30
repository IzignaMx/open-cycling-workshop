declare module 'dexie' {
  export function liveQuery<T>(query: () => Promise<T>): {
    subscribe(observer: { next(value: T): void; error(error: unknown): void }): {
      unsubscribe(): void
    }
  }

  export interface Collection<T> {
    limit(value: number): Collection<T>
    toArray(): Promise<T[]>
    keys(): Promise<unknown[]>
    uniqueKeys(): Promise<unknown[]>
    first(): Promise<T | undefined>
    reverse(): Collection<T>
    count(): Promise<number>
  }

  export interface WhereClause<T> {
    equals(value: unknown): Collection<T>
    between(
      lower: unknown,
      upper: unknown,
      includeLower?: boolean,
      includeUpper?: boolean,
    ): Collection<T>
  }

  export interface Table<T, K = unknown> {
    get(key: K): Promise<T | undefined>
    add(value: T): Promise<K>
    count(): Promise<number>
    hook(name: 'updating' | 'deleting', callback: () => never): void
    put(value: T): Promise<K>
    bulkPut(values: T[]): Promise<K>
    delete(key: K): Promise<void>
    bulkDelete(keys: K[]): Promise<void>
    toArray(): Promise<T[]>
    where(index: string): WhereClause<T>
    orderBy(index: string): Collection<T>
  }

  export interface Transaction {
    db: Dexie
    idbtrans: IDBTransaction
    parent?: Transaction
    table<T = unknown>(name: string): Table<T>
  }

  export interface Version {
    stores(schema: Record<string, string>): Version
    upgrade(callback: (transaction: Transaction) => void | Promise<void>): Version
  }

  export default class Dexie {
    static currentTransaction: Transaction
    constructor(name: string)
    version(version: number): Version
    on(event: 'populate', callback: (transaction: Transaction) => Promise<void>): void
    on(event: 'versionchange', callback: () => void): void
    close(): void
    transaction<T>(
      mode: 'rw' | 'r',
      tables: unknown[],
      callback: (transaction: Transaction) => PromiseLike<T> | T,
    ): Promise<T>
    transaction<T>(mode: 'rw' | 'r', ...args: unknown[]): Promise<T>
  }
}
