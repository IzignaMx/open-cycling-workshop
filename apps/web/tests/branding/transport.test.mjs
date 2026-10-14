import test from 'node:test'
import assert from 'node:assert/strict'
import { createBrandingTransport } from '../../.tmp-branding/src/features/branding/transport.js'
const incarnation = '01900000-0000-7000-8000-000000000001'
const source = {
  token: 'synthetic',
  organizationId: 'org',
  locationId: 'loc',
  datasetIncarnation: incarnation,
  isCurrent: () => true,
}
const profile = {
  schema_version: 1,
  organization_id: 'org',
  location_id: 'loc',
  dataset_incarnation: incarnation,
  version: 0,
  display_name: 'Taller',
  palette_id: 'bosque',
  logo_state: 'none',
  logo: null,
  logo_diagnostic: null,
  updated_at: null,
  updated_by: null,
}
function response(url, value, status = 200, headers = {}) {
  const r = new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers },
  })
  Object.defineProperty(r, 'url', { value: url })
  return r
}
test('branding uses captured private protocol1 URL with native fetch receiver', async () => {
  let called, init
  const http = createBrandingTransport({
    apiRealm: 'https://test.example/api/v1',
    fetch: function (url, options) {
      assert.equal(this, globalThis)
      called = url
      init = options
      return Promise.resolve(response(url, profile))
    },
  })
  assert.deepEqual(await http.read(source), profile)
  assert.equal(called, 'https://test.example/api/v1/locations/loc/branding')
  assert.equal(init.headers['X-OCWP-Write-Protocol'], '1')
  assert.equal(init.credentials, 'omit')
  assert.equal(init.cache, 'no-store')
})
test('branding rejects cross-scope/incarnation and uncacheable success', async () => {
  for (const value of [
    { ...profile, organization_id: 'other' },
    { ...profile, location_id: 'other' },
    { ...profile, dataset_incarnation: '01900000-0000-7000-8000-000000000002' },
  ]) {
    const http = createBrandingTransport({
      apiRealm: 'https://test.example/api/v1',
      fetch: async (url) => response(url, value),
    })
    await assert.rejects(http.read(source), (e) => e.code === 'invalid_response')
  }
  const http = createBrandingTransport({
    apiRealm: 'https://test.example/api/v1',
    fetch: async (url) => response(url, profile, 200, { 'cache-control': 'public' }),
  })
  await assert.rejects(http.read(source), (e) => e.code === 'invalid_response')
})
test('current 401/403 classified before untrusted or stalled body; stale denial inert', async () => {
  for (const status of [401, 403]) {
    const http = createBrandingTransport({
      apiRealm: 'https://test.example/api/v1',
      fetch: async (url) => {
        const r = new Response(new ReadableStream(), { status })
        Object.defineProperty(r, 'url', { value: url })
        return r
      },
    })
    await assert.rejects(http.read(source), (e) => e.status === status)
  }
  let current = true
  const http = createBrandingTransport({
    apiRealm: 'https://test.example/api/v1',
    fetch: async (url) => {
      current = false
      return response(url, {}, 401)
    },
  })
  await assert.rejects(
    http.read({ ...source, isCurrent: () => current }),
    (e) => e.code === 'stale_request',
  )
})
test('body cap enforced while streaming despite false content length', async () => {
  const http = createBrandingTransport({
    apiRealm: 'https://test.example/api/v1',
    fetch: async (url) => response(url, 'x'.repeat(393216), 200, { 'content-length': '1' }),
  })
  await assert.rejects(http.read(source), (e) => e.code === 'invalid_response')
})
test('save sends exactly one CAS; stale version refusal and malformed success never replay', async () => {
  for (const status of [409, 200]) {
    let calls = 0
    const http = createBrandingTransport({
      apiRealm: 'https://test.example/api/v1',
      fetch: async (url) => {
        calls++
        return response(
          url,
          status === 409
            ? { error: { code: 'stale_branding_version', message: 'private' } }
            : profile,
          status,
        )
      },
    })
    await assert.rejects(
      http.save(source, {
        expected_version: 0,
        display_name: 'Taller',
        palette_id: 'bosque',
        logo_png_base64: null,
      }),
    )
    assert.equal(calls, 1)
  }
})
