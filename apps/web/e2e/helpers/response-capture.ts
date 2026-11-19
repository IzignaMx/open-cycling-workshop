/** Test-only: consume the matched response while the triggering action is running.
 * The caller owns its bounded response waiter and page/context teardown. No new
 * listener, retry, fallback body or timeout is installed here.
 */
export async function captureResponseDuring<T, R>(
  response: Promise<T>,
  action: () => Promise<unknown>,
  capture: (response: T) => Promise<R>,
): Promise<R> {
  const captured = response.then(capture)
  // Register both rejection handlers before starting the action, including a
  // synchronous action throw. A later teardown rejection cannot go unhandled.
  const [value] = await Promise.all([captured, Promise.resolve().then(action)])
  return value
}
