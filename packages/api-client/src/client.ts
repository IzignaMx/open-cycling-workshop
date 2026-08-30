import type {
  ChangePageResponse,
  CurrentUserResponse,
  CustomerCreateRequest,
  CustomerResponse,
  LoginRequest,
  LoginResponse,
  PushMutationsRequest,
  PushMutationsResponse,
} from './generated.js'

export interface ApiClientOptions {
  baseUrl: string
  tokenProvider(): string | null
  fetcher?: typeof fetch
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API request failed with HTTP ${status}`)
  }
}

export class ApiClient {
  readonly #baseUrl: string
  readonly #tokenProvider: () => string | null
  readonly #fetcher: typeof fetch

  constructor(options: ApiClientOptions) {
    this.#baseUrl = options.baseUrl.replace(/\/$/, '')
    this.#tokenProvider = options.tokenProvider
    this.#fetcher = options.fetcher ?? fetch
  }

  async login(input: LoginRequest): Promise<LoginResponse> {
    return this.#json<LoginResponse>(
      '/api/v1/auth/login',
      { method: 'POST', body: JSON.stringify(input) },
      false,
    )
  }

  async me(): Promise<CurrentUserResponse> {
    return this.#json<CurrentUserResponse>('/api/v1/auth/me', { method: 'GET' })
  }

  async logoutAll(): Promise<void> {
    await this.#json<null>('/api/v1/auth/logout-all', { method: 'POST' })
  }

  async createCustomer(input: CustomerCreateRequest): Promise<CustomerResponse> {
    return this.#json<CustomerResponse>('/api/v1/customers', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  async pushMutations(input: PushMutationsRequest): Promise<PushMutationsResponse> {
    return this.#json<PushMutationsResponse>('/api/v1/sync/mutations', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  async pullChanges(cursor: number, locationId?: string | null): Promise<ChangePageResponse> {
    const params = new URLSearchParams({ cursor: String(cursor) })
    if (locationId) params.set('location_id', locationId)
    return this.#json<ChangePageResponse>(`/api/v1/sync/changes?${params.toString()}`, {
      method: 'GET',
    })
  }

  async #json<T>(path: string, init: RequestInit, authenticated = true): Promise<T> {
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json')
    if (init.body) headers.set('Content-Type', 'application/json')
    const token = authenticated ? this.#tokenProvider() : null
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await this.#fetcher(`${this.#baseUrl}${path}`, { ...init, headers })
    const body = response.status === 204 ? null : await response.json()
    if (!response.ok) throw new ApiError(response.status, body)
    return body as T
  }
}
