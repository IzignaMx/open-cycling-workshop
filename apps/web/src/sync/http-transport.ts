import type { ChangePage, MutationEnvelope, PushResponse, SyncTransport } from './types.js'

export class SyncTransportError extends Error {
  constructor(readonly status: number) {
    super(`sync transport failed with HTTP ${status}`)
  }
}

export class HttpSyncTransport implements SyncTransport {
  constructor(
    private readonly apiBaseUrl: string,
    private readonly tokenProvider: () => string | null,
    private readonly fetcher: typeof fetch = fetch,
  ) {}

  async push(mutations: MutationEnvelope[]): Promise<PushResponse> {
    const response = await this.request('/api/v1/sync/mutations', {
      method: 'POST',
      body: JSON.stringify({ mutations }),
    })
    return (await response.json()) as PushResponse
  }

  async pull(cursor: number, locationId: string | null): Promise<ChangePage> {
    const params = new URLSearchParams({ cursor: String(cursor) })
    if (locationId) params.set('location_id', locationId)
    const response = await this.request(`/api/v1/sync/changes?${params.toString()}`, { method: 'GET' })
    return (await response.json()) as ChangePage
  }

  private async request(path: string, init: RequestInit): Promise<Response> {
    const token = this.tokenProvider()
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json')
    if (init.body) headers.set('Content-Type', 'application/json')
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await this.fetcher(`${this.apiBaseUrl}${path}`, { ...init, headers })
    if (!response.ok) throw new SyncTransportError(response.status)
    return response
  }
}
