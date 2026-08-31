import type { ChangePage, MutationEnvelope, PushResponse, SyncTransport } from './types.js'

export class SyncTransportError extends Error {
  constructor(readonly status: number) {
    super(`sync transport failed with HTTP ${status}`)
  }
}

/**
 * Raised when the request never reaches the backend (network offline,
 * blocked or unreachable). Distinct from HTTP-level failures so callers can
 * treat unreachable networks as the offline state instead of a sync error;
 * navigator.onLine alone is not a reliable signal in all browser states.
 */
export class SyncTransportOfflineError extends Error {
  constructor(cause?: unknown) {
    super('sync transport unreachable (network offline or blocked)')
    if (cause !== undefined) {
      this.cause = cause
    }
  }
}

export class HttpSyncTransport implements SyncTransport {
  constructor(
    private readonly apiBaseUrl: string,
    private readonly tokenProvider: () => string | null,
    // Bind to globalThis: browsers require `fetch` to be invoked with Window as
    // its receiver; a detached reference throws "Illegal invocation".
    private readonly fetcher: typeof fetch = fetch.bind(globalThis),
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
    const response = await this.request(`/api/v1/sync/changes?${params.toString()}`, {
      method: 'GET',
    })
    return (await response.json()) as ChangePage
  }

  private async request(path: string, init: RequestInit): Promise<Response> {
    const token = this.tokenProvider()
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json')
    if (init.body) headers.set('Content-Type', 'application/json')
    if (token) headers.set('Authorization', `Bearer ${token}`)
    let response: Response
    try {
      response = await this.fetcher(`${this.apiBaseUrl}${path}`, { ...init, headers })
    } catch (error) {
      throw new SyncTransportOfflineError(error)
    }
    if (!response.ok) throw new SyncTransportError(response.status)
    return response
  }
}
