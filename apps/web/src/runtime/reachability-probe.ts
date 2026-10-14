import { RuntimeHttpError } from './transport.js'

export type ReachabilityResult<T> = { value: T } | { error: unknown }
export interface ReachabilityTask<T> {
  expiresAt: number
  current(): boolean
  inspect(): Promise<void>
  request(signal: AbortSignal, current: () => boolean): Promise<T>
  complete(result: ReachabilityResult<T>, current: () => boolean): Promise<void>
  invalid(): void
}
interface Clock {
  now(): number
  set(action: () => void, delay: number): unknown
  clear(handle: unknown): void
}

/** Read-only hints, never offline authority. One transport stays owned until it settles. */
export class ReachabilityProbe<T> {
  #task: ReachabilityTask<T> | null = null
  #timer: unknown = null
  #flight: AbortController | null = null
  #delay = 2000
  #observedAt = 0
  constructor(
    private readonly clock: Clock = {
      now: Date.now,
      set: (action, delay) => setTimeout(action, delay),
      clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
    },
  ) {}
  start(task: ReachabilityTask<T>) {
    this.cancel()
    this.#task = task
    this.#delay = 2000
    this.#observedAt = this.clock.now()
    this.schedule(task)
  }
  cancel() {
    this.#task = null
    if (this.#timer !== null) this.clock.clear(this.#timer)
    this.#timer = null
    // Do not release single-flight ownership until even an abort-ignoring fetch settles.
    this.#flight?.abort()
  }
  private valid(task: ReachabilityTask<T>): boolean {
    if (this.#task !== task || !task.current()) return false
    const now = this.clock.now()
    if (
      !Number.isFinite(now) ||
      !Number.isFinite(task.expiresAt) ||
      now < this.#observedAt ||
      now >= task.expiresAt
    ) {
      this.cancel()
      task.invalid()
      return false
    }
    this.#observedAt = now
    return true
  }
  private schedule(task: ReachabilityTask<T>) {
    if (this.#flight || this.#timer !== null || !this.valid(task)) return
    this.#timer = this.clock.set(
      () => {
        this.#timer = null
        void this.run(task)
      },
      Math.min(this.#delay, task.expiresAt - this.clock.now()),
    )
  }
  private async run(task: ReachabilityTask<T>) {
    if (!this.valid(task) || this.#flight) return
    const flight = new AbortController()
    this.#flight = flight
    let deadline: unknown = null
    let timedOut = false
    const current = () => !flight.signal.aborted && this.valid(task)
    try {
      await task.inspect()
      if (!current()) return
      // The deadline covers fetch and streamed body consumption; it never renews the lease.
      deadline = this.clock.set(
        () => {
          timedOut = true
          this.valid(task)
          flight.abort()
        },
        Math.min(10000, task.expiresAt - this.clock.now()),
      )
      let result: ReachabilityResult<T>
      try {
        result = { value: await task.request(flight.signal, current) }
      } catch (error) {
        result = { error }
      }
      if (deadline !== null) this.clock.clear(deadline)
      deadline = null
      if (timedOut) return
      if (!current()) return
      if (
        'error' in result &&
        result.error instanceof RuntimeHttpError &&
        result.error.code === 'network_error'
      )
        return
      // Preserve a received refusal. The caller invalidates the expected owner before holding.
      this.#flight = null
      await task.complete(result, current)
      if (this.#task === task) this.#task = null
    } catch {
      if (this.valid(task)) {
        this.cancel()
        task.invalid()
      }
    } finally {
      if (deadline !== null) this.clock.clear(deadline)
      if (this.#flight === flight) this.#flight = null
      if (this.#task === task) this.#delay = Math.min(30000, this.#delay * 2)
      if (this.#task) this.schedule(this.#task)
    }
  }
}
