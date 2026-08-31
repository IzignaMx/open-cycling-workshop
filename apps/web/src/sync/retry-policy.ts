/** Bounded exponential backoff for transient sync failures.
 *
 * Classification lives with the callers: network-level failures map to the
 * offline state and temporary HTTP failures (5xx) map to the error state;
 * both are transient and re-attempt under this policy. Permanent failures
 * never reach this policy — they leave the retry queue and surface in the
 * Conflict Center instead of looping forever.
 */

export interface RetryPlan {
  /** Milliseconds to wait before the next attempt. */
  delayMs: number
  /** True once the bounded budget is spent; callers stop scheduling. */
  exhausted: boolean
}

const BASE_DELAY_MS = 2_000
const MAX_DELAY_MS = 30_000
const MAX_ATTEMPTS = 8

export function retryPlan(attempt: number): RetryPlan {
  const safe = Math.max(0, Math.floor(attempt))
  if (safe >= MAX_ATTEMPTS) {
    return { delayMs: MAX_DELAY_MS, exhausted: true }
  }
  const delayMs = Math.min(BASE_DELAY_MS * 2 ** safe, MAX_DELAY_MS)
  return { delayMs, exhausted: false }
}
