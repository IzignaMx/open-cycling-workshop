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

// Runtime binds fetch at bootstrap, so this must run before the first navigation.
// The init script persists for this disposable page; each document is single-use.
export async function installInventoryContextObserver(page) {
  await page.addInitScript(() => {
    const key = '__ocwpInventoryContextObservation'
    if (window[key]) throw new Error('Invalid inventory context observation')
    const originalFetch = window.fetch
    let active = null
    let used = false
    const invalid = () => new Error('Invalid inventory context observation')
    const matches = (input, init, locationId) => {
      try {
        const request = input instanceof Request ? input : null
        const method = (init?.method ?? request?.method ?? 'GET').toUpperCase()
        const url = new URL(request?.url ?? input, window.location.href)
        return method === 'GET' &&
          url.origin === window.location.origin &&
          url.pathname === '/api/v1/auth/context' &&
          url.searchParams.getAll('selected_location_id').length === 1 &&
          url.searchParams.get('selected_location_id') === locationId
          ? url.href
          : null
      } catch {
        return null
      }
    }
    const read = async (response, state) => {
      const clone = response.clone()
      if (!clone.body) throw invalid()
      const reader = clone.body.getReader()
      const cancel = () => {
        void reader.cancel().catch(() => {})
      }
      state.cancel = cancel
      try {
        let size = 0
        const bytes = new Uint8Array(16_384)
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          if (size + value.byteLength > bytes.byteLength) throw invalid()
          bytes.set(value, size)
          size += value.byteLength
        }
        const body = JSON.parse(
          new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(0, size)),
        )
        if (
          !body ||
          typeof body.offline_until !== 'string' ||
          !Number.isFinite(Date.parse(body.offline_until)) ||
          body.selected_location_id !== state.locationId ||
          (body.snapshot_protocol !== null && body.snapshot_protocol !== 'baseline-v1')
        )
          throw invalid()
        return {
          expiresAt: Date.parse(body.offline_until),
          snapshotProtocol: body.snapshot_protocol,
        }
      } finally {
        cancel()
        state.cancel = null
        reader.releaseLock()
      }
    }
    function wrappedFetch(...args) {
      // Capture at request initiation, not response arrival. Earlier requests and
      // late completions cannot adopt the armed observation's authority.
      const state = active
      const url = state ? matches(args[0], args[1], state.locationId) : null
      if (url) state.count++
      let pending
      try {
        pending = originalFetch.apply(this, args)
      } catch (error) {
        if (url && active === state) state.failed = true
        throw error
      }
      return pending.then(
        (response) => {
          if (url && active === state && state.count === 1) {
            if (response.status !== 200 || response.redirected || response.url !== url) {
              state.failed = true
            } else {
              // Do not await the clone: application receives its original Response.
              // Catch locally so private native/parse errors never reach a report.
              state.pending = read(response, state).catch(() => {
                if (active === state) state.failed = true
              })
            }
          }
          return response
        },
        (error) => {
          if (url && active === state) state.failed = true
          throw error
        },
      )
    }
    window.fetch = wrappedFetch
    window[key] = {
      arm(locationId) {
        if (used || typeof locationId !== 'string' || !locationId) throw invalid()
        used = true
        active = { locationId, count: 0, failed: false, pending: null, cancel: null }
      },
      async finish() {
        const state = active
        if (!state || state.count !== 1 || state.failed || !state.pending) throw invalid()
        const result = await state.pending
        if (active !== state || state.count !== 1 || state.failed || !result) throw invalid()
        return result
      },
      dispose() {
        const state = active
        active = null
        state?.cancel?.()
        if (state) {
          state.pending = null
          state.cancel = null
          state.locationId = null
        }
        if (window.fetch === wrappedFetch) window.fetch = originalFetch
        delete window[key]
      },
    }
  })
}

export async function observeInventoryContext(page, locationId, action) {
  let failure, result
  let failed = false
  try {
    await page.evaluate((selected) => {
      const observer = window.__ocwpInventoryContextObservation
      if (!observer) throw new Error('Invalid inventory context observation')
      observer.arm(selected)
    }, locationId)
    // Keep full action/readiness assertions. The clone was already consumed in
    // the page; no CDP response-body retrieval is needed after readiness.
    await action()
    result = await page.evaluate(() => {
      const observer = window.__ocwpInventoryContextObservation
      if (!observer) throw new Error('Invalid inventory context observation')
      return observer.finish()
    })
  } catch (error) {
    failed = true
    failure = error
  }
  try {
    await page.evaluate(() => window.__ocwpInventoryContextObservation?.dispose())
  } catch {
    // A closed page may prevent cleanup. Preserve an existing action error;
    // cleanup failure by itself must never turn into a successful observation.
    if (!failed) throw new Error('Inventory context observation cleanup failed')
  }
  if (failed) throw failure
  return result
}
