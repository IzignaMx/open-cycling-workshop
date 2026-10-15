// Test-only observations. These do not grant application or server authority.
export function isUnexpectedApiWrite(method, url) {
  const path = new URL(url).pathname
  // Delta paging is a protocol read using POST. It advances server continuation
  // metadata, but cannot deliver the pending domain mutations guarded here.
  return (
    path.startsWith('/api/v1/') &&
    !['GET', 'HEAD', 'OPTIONS'].includes(method) &&
    !(method === 'POST' && path === '/api/v1/sync/deltas/page')
  )
}

export async function observeInventoryContext(page, locationId, action) {
  const origin = new URL(page.url()).origin
  const context = page
    .waitForResponse((candidate) => {
      const url = new URL(candidate.url())
      return (
        candidate.request().method() === 'GET' &&
        candidate.status() === 200 &&
        url.origin === origin &&
        url.pathname === '/api/v1/auth/context' &&
        url.searchParams.getAll('selected_location_id').length === 1 &&
        url.searchParams.get('selected_location_id') === locationId
      )
    })
    // Start body retrieval at response arrival, not after catalog visibility or
    // another action. Never retry a missing body or invent a lease from the clock.
    .then((response) => response.json())
    .then((body) => {
      if (
        !body ||
        typeof body.offline_until !== 'string' ||
        !Number.isFinite(Date.parse(body.offline_until)) ||
        body.selected_location_id !== locationId ||
        (body.snapshot_protocol !== null && body.snapshot_protocol !== 'baseline-v1')
      )
        throw new Error('Invalid inventory context observation')
      return { expiresAt: Date.parse(body.offline_until), snapshotProtocol: body.snapshot_protocol }
    })
  // Attach both error handlers before running the action. Keep its complete
  // readiness assertions, even when the response body finishes first.
  const [observed] = await Promise.all([context, Promise.resolve().then(action)])
  return observed
}
