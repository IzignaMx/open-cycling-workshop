/** Shared byte boundary only; no baseline, context or runtime dependencies. */
export class BoundedHttpError extends Error {
  constructor(readonly code: 'invalid_response' | 'network_error') {
    super(`Bounded response failed: ${code}`)
    this.name = 'BoundedHttpError'
  }
}
function reject(code: 'invalid_response' | 'network_error' = 'invalid_response'): never {
  throw new BoundedHttpError(code)
}
/** Count streamed bytes before decoding/parsing, irrespective of Content-Length. */
export async function readBoundedJson(response: Response, limit: number): Promise<unknown> {
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 1_048_576) return reject()
  const stream = response.body
  if (!stream) return reject()
  const reader = stream.getReader()
  let completed = false
  try {
    const length = response.headers.get('content-length')
    if (
      length !== null &&
      (!/^\d+$/.test(length) || !Number.isSafeInteger(Number(length)) || Number(length) > limit)
    )
      return reject()
    const decoder = new TextDecoder('utf-8', { fatal: true })
    let bytes = 0,
      text = ''
    for (;;) {
      const next = await reader.read().catch(() => reject('network_error'))
      if (next.done) {
        completed = true
        break
      }
      bytes += next.value.byteLength
      if (bytes > limit) return reject()
      text += decoder.decode(next.value, { stream: true })
    }
    text += decoder.decode()
    return JSON.parse(text) as unknown
  } catch (error) {
    if (error instanceof BoundedHttpError) throw error
    return reject()
  } finally {
    if (!completed) {
      try {
        await reader.cancel()
      } catch {
        /* no raw stream errors escape */
      }
    }
    reader.releaseLock()
  }
}
export async function cancelResponse(response: Response): Promise<void> {
  try {
    await response.body?.cancel()
  } catch {
    /* Do not expose stream exceptions. */
  }
}
