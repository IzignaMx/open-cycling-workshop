export interface FixtureResponse {
  status: number
  headers: Record<string, string>
  body: string
}
export function fixtureHttp(
  origin: string,
  target: string,
  options?: { method?: 'GET' | 'POST'; headers?: HeadersInit; body?: string },
  fetcher?: typeof fetch,
): Promise<FixtureResponse>
export function fixtureJson(response: FixtureResponse): Record<string, unknown>
