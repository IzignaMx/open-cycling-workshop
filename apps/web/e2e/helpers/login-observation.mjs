// Test-only: observe the real destination login without retrieving its body via CDP.
// Runtime binds fetch at bootstrap; install before this disposable page's first goto.
export async function installLoginObserver(page, origin) {
  await page.addInitScript((expectedOrigin) => {
    if (window.top !== window || window.location.origin !== expectedOrigin) return
    const key = '__ocwpLoginObservation'
    const invalid = () => new Error('Invalid login observation')
    if (window[key]) throw invalid()
    const originalFetch = window.fetch
    const loginUrl = new URL('/api/v1/auth/login', expectedOrigin).href
    let active = null
    let used = false
    const matches = (input, init) => {
      try {
        const request = input instanceof Request ? input : null
        const method = (init?.method ?? request?.method ?? 'GET').toUpperCase()
        const url = new URL(request?.url ?? input, window.location.href)
        return method === 'POST' && url.href === loginUrl
      } catch {
        return false
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
        const bytes = new Uint8Array(32_768)
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
          typeof body !== 'object' ||
          Array.isArray(body) ||
          body.token_type !== 'bearer' ||
          typeof body.access_token !== 'string' ||
          body.access_token.length < 1 ||
          body.access_token.length > 16_384 ||
          /\s/.test(body.access_token)
        )
          throw invalid()
        // This bearer remains inside the page-owned closure. Only independent
        // body validity and equality booleans may cross the observation boundary.
        return body.access_token
      } finally {
        cancel()
        state.cancel = null
        reader.releaseLock()
      }
    }
    function wrappedFetch(...args) {
      // Ownership starts with the request, so an earlier request cannot satisfy
      // a newly armed observation when its response eventually arrives.
      const state = active
      const matching = state && matches(args[0], args[1])
      if (matching) state.count++
      let pending
      try {
        pending = originalFetch.apply(this, args)
      } catch (error) {
        if (matching && active === state) state.failed = true
        throw error
      }
      return pending.then(
        (response) => {
          if (matching && active === state && state.count === 1) {
            if (response.status !== 200 || response.redirected || response.url !== loginUrl) {
              state.failed = true
            } else {
              // Never await the clone before returning the app's original Response.
              // Native and parse errors cannot disclose private response content.
              state.pending = read(response, state).catch(() => {
                if (active === state) state.failed = true
              })
            }
          }
          return response
        },
        (error) => {
          if (matching && active === state) state.failed = true
          throw error
        },
      )
    }
    window.fetch = wrappedFetch
    window[key] = {
      arm() {
        if (used) throw invalid()
        used = true
        active = { count: 0, failed: false, pending: null, cancel: null }
      },
      async finish() {
        const state = active
        if (!state || state.count !== 1 || state.failed || !state.pending) throw invalid()
        const issuedToken = await state.pending
        if (active !== state || state.count !== 1 || state.failed || !issuedToken) throw invalid()
        let issuedMatchesStored = false
        try {
          const stored = JSON.parse(sessionStorage.getItem('ocwp.session.v2'))
          issuedMatchesStored = typeof stored?.token === 'string' && stored.token === issuedToken
        } catch {
          // Storage is comparison evidence only, never a replacement response.
        }
        return { bodyValidated: true, issuedMatchesStored }
      },
      dispose() {
        const state = active
        active = null
        state?.cancel?.()
        if (state) {
          state.pending = null
          state.cancel = null
        }
        if (window.fetch === wrappedFetch) window.fetch = originalFetch
        delete window[key]
      },
    }
  }, origin)
}

export async function observeLogin(page, action) {
  let failure, result
  let failed = false
  try {
    await page.evaluate(() => {
      const observer = window.__ocwpLoginObservation
      if (!observer) throw new Error('Invalid login observation')
      observer.arm()
    })
    // Preserve the full UI/readiness and Playwright response-metadata checks.
    // The real body was already consumed from its independent clone in-page.
    await action()
    result = await page.evaluate(() => {
      const observer = window.__ocwpLoginObservation
      if (!observer) throw new Error('Invalid login observation')
      return observer.finish()
    })
  } catch (error) {
    failed = true
    failure = error
  }
  try {
    await page.evaluate(() => window.__ocwpLoginObservation?.dispose())
  } catch {
    if (!failed) throw new Error('Login observation cleanup failed')
  }
  if (failed) throw failure
  return result
}
