export type CaptureAppEvidence = {
  source_commit: string
  source_tree: string
  lock_sha256: string
  database: string
  assets: Record<string, { bytes: number; sha256: string }>
}
export type CaptureAppResponse = {
  status: number
  headers: Record<string, string>
  body: Uint8Array
}
export type CaptureAppServer = {
  readonly listening: boolean
  once(event: 'listening', callback: () => void): CaptureAppServer
  once(event: 'error', callback: (error: Error) => void): CaptureAppServer
  close(callback: (error?: Error) => void): CaptureAppServer
  replaceCaptureApp(directory: string | URL): void
}
export function trustedCaptureAppEvidence(kind: 'old' | 'current'): CaptureAppEvidence
export function captureAsset(raw: string): string | null
export function createCaptureAppAdmission(expected: CaptureAppEvidence): Readonly<{
  replace(directory: string | URL): void
  respond(method: string, raw: string): CaptureAppResponse
}>
export function startCaptureAppServer(
  directory: string | URL,
  port: number,
  expected?: CaptureAppEvidence,
): CaptureAppServer
